"""Query Executor - Executes parsed SQL statements against loaded tables."""

from parser import (
    ASTNode, LoadStatement, SaveStatement, InsertStatement,
    SelectStatement, SelectColumn, ColumnRef, AggCall, AggFunc,
    Comparison, BinaryOp, JoinClause, OrderItem, ParseError,
)
from table import Table, load_csv, save_csv, _typed_compare, _typed_sort_key
from formatter import format_ascii_table


class ExecutionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class Executor:
    def __init__(self):
        self.tables: dict[str, Table] = {}

    def execute(self, statement: ASTNode) -> Table | str:
        if isinstance(statement, LoadStatement):
            return self._exec_load(statement)
        elif isinstance(statement, SaveStatement):
            return self._exec_save(statement)
        elif isinstance(statement, InsertStatement):
            return self._exec_insert(statement)
        elif isinstance(statement, SelectStatement):
            return self._exec_select(statement)
        else:
            raise ExecutionError(f"Unknown statement type: {type(statement)}")

    def _exec_load(self, stmt: LoadStatement) -> str:
        table = load_csv(stmt.table, stmt.filename)
        self.tables[stmt.table] = table
        return f"Loaded table '{stmt.table}' with {len(table.rows)} rows from '{stmt.filename}'"

    def _exec_save(self, stmt: SaveStatement) -> str:
        if stmt.table not in self.tables:
            raise ExecutionError(f"Table '{stmt.table}' not found")
        save_csv(self.tables[stmt.table], stmt.filename)
        return f"Saved table '{stmt.table}' ({len(self.tables[stmt.table].rows)} rows) to '{stmt.filename}'"

    def _exec_insert(self, stmt: InsertStatement) -> str:
        if stmt.table not in self.tables:
            raise ExecutionError(f"Table '{stmt.table}' not found")
        table = self.tables[stmt.table]
        if len(stmt.values) != len(table.columns):
            raise ExecutionError(
                f"INSERT has {len(stmt.values)} values, but table '{stmt.table}' has {len(table.columns)} columns"
            )
        table.rows.append(stmt.values)
        return f"Inserted 1 row into '{stmt.table}'"

    def _exec_select(self, stmt: SelectStatement) -> Table:
        # Resolve source table
        if stmt.table not in self.tables:
            raise ExecutionError(f"Table '{stmt.table}' not found")

        left_table = self.tables[stmt.table]

        # Handle JOIN
        if stmt.join:
            result_rows, result_columns = self._execute_join(stmt, left_table)
        else:
            result_rows = [row[:] for row in left_table.rows]
            result_columns = list(left_table.columns)

        # Apply WHERE
        if stmt.where:
            result_rows = self._apply_where(result_rows, result_columns, stmt.where, stmt.table, stmt.join)

        # Handle GROUP BY and aggregates
        if stmt.group_by:
            result_rows, result_columns = self._apply_group_by(
                result_rows, result_columns, stmt.group_by, stmt.columns, stmt.table, stmt.join
            )
        elif self._has_aggregates(stmt.columns):
            # Aggregates without GROUP BY -> single row result
            result_rows, result_columns = self._apply_aggregate_all(
                result_rows, result_columns, stmt.columns, stmt.table
            )
        else:
            # Project columns (no aggregates)
            result_rows, result_columns = self._project_columns(
                result_rows, result_columns, stmt.columns, stmt.table, stmt.join
            )

        # Apply ORDER BY
        if stmt.order_by:
            result_rows = self._apply_order_by(result_rows, result_columns, stmt.order_by)

        # Apply LIMIT
        if stmt.limit is not None:
            result_rows = result_rows[:stmt.limit]

        return Table(name="result", columns=result_columns, rows=result_rows)

    def _execute_join(self, stmt: SelectStatement, left_table: Table):
        join = stmt.join
        if join.table not in self.tables:
            raise ExecutionError(f"Join table '{join.table}' not found")
        right_table = self.tables[join.table]

        # Build column map for the joined result
        # Prefix right table columns with table name to avoid conflicts
        left_cols = [f"{left_table.name}.{c}" for c in left_table.columns]
        right_cols = [f"{right_table.name}.{c}" for c in right_table.columns]
        result_columns = left_cols + right_cols

        # Find join column indices
        left_join_col = join.left_col.name
        right_join_col = join.right_col.name

        if join.left_col.table:
            if join.left_col.table != left_table.name:
                raise ExecutionError(f"Left join column table '{join.left_col.table}' does not match '{left_table.name}'")
        if join.right_col.table:
            if join.right_col.table != right_table.name:
                raise ExecutionError(f"Right join column table '{join.right_col.table}' does not match '{right_table.name}'")

        left_idx = left_table.column_index(left_join_col)
        right_idx = right_table.column_index(right_join_col)

        # Build hash map for right table
        right_map: dict[str, list[list[str]]] = {}
        for row in right_table.rows:
            key = row[right_idx]
            if key not in right_map:
                right_map[key] = []
            right_map[key].append(row)

        result_rows = []
        for left_row in left_table.rows:
            key = left_row[left_idx]
            if key in right_map:
                for right_row in right_map[key]:
                    result_rows.append(left_row + right_row)

        return result_rows, result_columns

    def _resolve_column_index(self, columns: list[str], ref: ColumnRef, table_name: str,
                               join: JoinClause | None) -> int:
        """Resolve a column reference to an index in the result columns."""
        if ref.table:
            name = f"{ref.table}.{ref.name}"
            if name in columns:
                return columns.index(name)
            raise ExecutionError(f"Column '{name}' not found in result. Available: {', '.join(columns)}")
        else:
            # Try to find the column, preferring the main table if join
            target = f"{table_name}.{ref.name}"
            if target in columns:
                return columns.index(target)
            # Try bare name
            if ref.name in columns:
                return columns.index(ref.name)
            # If join, also try join table
            if join:
                target = f"{join.table}.{ref.name}"
                if target in columns:
                    return columns.index(target)
            raise ExecutionError(f"Column '{ref.name}' not found. Available: {', '.join(columns)}")

    def _apply_where(self, rows: list[list[str]], columns: list[str],
                     expr, table_name: str, join: JoinClause | None) -> list[list[str]]:
        return [row for row in rows if self._eval_expr(row, columns, expr, table_name, join)]

    def _eval_expr(self, row: list[str], columns: list[str], expr,
                   table_name: str, join: JoinClause | None) -> bool:
        if isinstance(expr, Comparison):
            return self._eval_comparison(row, columns, expr, table_name, join)
        elif isinstance(expr, BinaryOp):
            left_val = self._eval_expr(row, columns, expr.left, table_name, join)
            right_val = self._eval_expr(row, columns, expr.right, table_name, join)
            if expr.op == 'AND':
                return left_val and right_val
            elif expr.op == 'OR':
                return left_val or right_val
            else:
                raise ExecutionError(f"Unknown logical operator: {expr.op}")
        else:
            raise ExecutionError(f"Unknown expression type: {type(expr)}")

    def _eval_comparison(self, row: list[str], columns: list[str],
                         comp: Comparison, table_name: str, join: JoinClause | None) -> bool:
        left_idx = self._resolve_column_index(columns, comp.left, table_name, join)
        left_val = row[left_idx]

        if isinstance(comp.right, ColumnRef):
            right_idx = self._resolve_column_index(columns, comp.right, table_name, join)
            right_val = row[right_idx]
        else:
            right_val = str(comp.right)

        return _typed_compare(left_val, right_val, comp.op)

    def _has_aggregates(self, columns: list[SelectColumn]) -> bool:
        if not columns:
            return False  # SELECT *
        return any(isinstance(col.expr, AggCall) for col in columns)

    def _project_columns(self, rows: list[list[str]], columns: list[str],
                         select_cols: list[SelectColumn], table_name: str,
                         join: JoinClause | None) -> tuple[list[list[str]], list[str]]:
        if not select_cols:
            # SELECT * - keep all columns
            return rows, columns

        new_columns = []
        indices = []
        for sc in select_cols:
            if isinstance(sc.expr, ColumnRef):
                idx = self._resolve_column_index(columns, sc.expr, table_name, join)
                new_columns.append(sc.expr.name)
                indices.append(idx)
            elif isinstance(sc.expr, AggCall):
                # Should not happen here; handled separately
                raise ExecutionError("Unexpected aggregate in projection")

        new_rows = [[row[i] for i in indices] for row in rows]
        return new_rows, new_columns

    def _apply_aggregate_all(self, rows: list[list[str]], columns: list[str],
                              select_cols: list[SelectColumn], table_name: str) -> tuple[list[list[str]], list[str]]:
        """Apply aggregates across all rows (no GROUP BY)."""
        new_columns = []
        values = []

        for sc in select_cols:
            if isinstance(sc.expr, AggCall):
                name, val = self._compute_aggregate(sc.expr, rows, columns, table_name)
                new_columns.append(name)
                values.append(str(val))
            elif isinstance(sc.expr, ColumnRef):
                # Non-aggregate column with no GROUP BY - just take first row's value
                idx = self._resolve_column_index(columns, sc.expr, table_name, None)
                new_columns.append(sc.expr.name)
                if rows:
                    values.append(rows[0][idx])
                else:
                    values.append('')

        return [values], new_columns

    def _apply_group_by(self, rows: list[list[str]], columns: list[str],
                        group_cols: list[ColumnRef], select_cols: list[SelectColumn],
                        table_name: str, join: JoinClause | None) -> tuple[list[list[str]], list[str]]:
        """Apply GROUP BY and compute aggregates per group."""
        # Get group column indices
        group_indices = []
        group_col_names = []
        for gc in group_cols:
            idx = self._resolve_column_index(columns, gc, table_name, join)
            group_indices.append(idx)
            group_col_names.append(gc.name)

        # Group rows
        groups: dict[tuple, list[list[str]]] = {}
        for row in rows:
            key = tuple(row[i] for i in group_indices)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        # Build output columns and compute
        new_columns = list(group_col_names)
        agg_defs = []  # (name, AggCall or ColumnRef, bool_is_aggregate)

        for sc in select_cols:
            if isinstance(sc.expr, AggCall):
                agg_name = self._agg_display_name(sc.expr)
                new_columns.append(agg_name)
                agg_defs.append((agg_name, sc.expr, True))
            elif isinstance(sc.expr, ColumnRef):
                # Check if this column is already in group_by columns
                if sc.expr.name in group_col_names:
                    # Already included, skip to avoid duplication
                    continue
                new_columns.append(sc.expr.name)
                agg_defs.append((sc.expr.name, sc.expr, False))

        # Build result
        result_rows = []
        for key, group_rows in groups.items():
            result_row = list(key)
            for name, defn, is_agg in agg_defs:
                if is_agg:
                    _, val = self._compute_aggregate(defn, group_rows, columns, table_name)
                    result_row.append(str(val))
                else:
                    # Non-aggregate column in group - take first row's value
                    idx = self._resolve_column_index(columns, defn, table_name, join)
                    result_row.append(group_rows[0][idx])
            result_rows.append(result_row)

        # If there are no rows, still produce correct empty result
        if not rows and not groups:
            result_rows = []

        return result_rows, new_columns

    def _compute_aggregate(self, agg: AggCall, rows: list[list[str]],
                           columns: list[str], table_name: str) -> tuple[str, int | float]:
        """Compute an aggregate on a set of rows. Returns (display_name, value)."""
        name = self._agg_display_name(agg)

        if agg.func == AggFunc.COUNT:
            if agg.arg is None:
                # COUNT(*)
                return name, len(rows)
            else:
                idx = self._resolve_column_index(columns, agg.arg, table_name, None)
                # COUNT(column) - count non-empty values
                count = sum(1 for row in rows if row[idx] != '')
                return name, count

        # For other aggregates, need numeric values
        idx = self._resolve_column_index(columns, agg.arg, table_name, None)
        nums = []
        for row in rows:
            val = row[idx]
            if val == '' or val is None:
                continue
            try:
                nums.append(float(val))
            except ValueError:
                pass  # Skip non-numeric values

        if agg.func == AggFunc.SUM:
            return name, sum(nums) if nums else 0
        elif agg.func == AggFunc.AVG:
            return name, sum(nums) / len(nums) if nums else 0
        elif agg.func == AggFunc.MIN:
            return name, min(nums) if nums else 0
        elif agg.func == AggFunc.MAX:
            return name, max(nums) if nums else 0
        else:
            raise ExecutionError(f"Unknown aggregate function: {agg.func}")

    def _agg_display_name(self, agg: AggCall) -> str:
        """Generate display name for an aggregate."""
        func_name = agg.func.name
        arg_name = '*' if agg.arg is None else agg.arg.name
        return f"{func_name}({arg_name})"

    def _apply_order_by(self, rows: list[list[str]], columns: list[str],
                        order_items: list[OrderItem]) -> list[list[str]]:
        """Sort rows by ORDER BY columns."""

        def sort_key(row):
            keys = []
            for item in order_items:
                if item.column.name not in columns:
                    raise ExecutionError(f"ORDER BY column '{item.column.name}' not found in result")
                idx = columns.index(item.column.name)
                val = _typed_sort_key(row[idx])
                # Reverse for DESC
                if item.direction == 'DESC':
                    # Negate numbers, reverse string comparison
                    if val[0] == 0:  # numeric
                        keys.append((0, -val[1], ''))
                    else:
                        # For strings, we need a different approach for DESC
                        # Use a tuple that sorts in reverse
                        keys.append((1, 0, _reverse_str(val[2])))
                else:
                    keys.append(val)
            return keys

        return sorted(rows, key=sort_key)


def _reverse_str(s: str) -> str:
    """Reverse a string for descending sort."""
    return ''.join(chr(255 - ord(c)) if ord(c) < 256 else c for c in s)
