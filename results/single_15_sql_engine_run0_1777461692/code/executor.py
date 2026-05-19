"""Query executor - evaluates AST nodes against loaded tables."""

from typing import Any, Optional

from ast_nodes import (
    ColumnRef, StarSelect, Literal, BinaryOp, AggregateFunc,
    AliasedExpr, OrderItem, JoinClause,
    SelectStmt, InsertStmt, LoadStmt, SaveStmt,
)
from table import Table, TableError


class ExecutorError(Exception):
    """Error during query execution."""
    pass


def _is_numeric(val):
    """Check if a value is numeric (int or float)."""
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _to_number(val):
    """Try to convert a value to number, return original if not possible."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            try:
                return float(val)
            except ValueError:
                pass
    return val


def _compare_values(left_val, right_val, op: str) -> bool:
    """Compare two values using the given operator."""
    # Handle None
    if left_val is None or right_val is None:
        if op == '=':
            return left_val is None and right_val is None
        if op == '!=':
            return not (left_val is None and right_val is None)
        return False  # None comparisons with <, >, <=, >= are False

    # Try numeric comparison
    l_num = _to_number(left_val)
    r_num = _to_number(right_val)

    if _is_numeric(l_num) and _is_numeric(r_num):
        left_val, right_val = l_num, r_num

    try:
        if op == '=':
            return left_val == right_val
        elif op == '!=':
            return left_val != right_val
        elif op == '<':
            return left_val < right_val
        elif op == '>':
            return left_val > right_val
        elif op == '<=':
            return left_val <= right_val
        elif op == '>=':
            return left_val >= right_val
    except TypeError:
        return False

    return False


class Executor:
    """Executes SQL AST nodes against loaded tables."""

    def __init__(self):
        self.tables: dict[str, Table] = {}

    # ================================================================
    # Main dispatch
    # ================================================================

    def execute(self, ast) -> Optional[list]:
        """Execute an AST node. Returns rows for SELECT, None for others."""
        if ast is None:
            return None

        if isinstance(ast, LoadStmt):
            return self._exec_load(ast)
        elif isinstance(ast, SaveStmt):
            return self._exec_save(ast)
        elif isinstance(ast, InsertStmt):
            return self._exec_insert(ast)
        elif isinstance(ast, SelectStmt):
            return self._exec_select(ast)
        else:
            raise ExecutorError(f"Unknown statement type: {type(ast).__name__}")

    def get_table(self, name: str) -> Table:
        """Get a table by name, or raise error."""
        if name not in self.tables:
            raise ExecutorError(f"Table '{name}' is not loaded")
        return self.tables[name]

    # ================================================================
    # LOAD / SAVE / INSERT
    # ================================================================

    def _exec_load(self, ast: LoadStmt) -> Optional[list]:
        """Load a CSV file as a table."""
        table = Table.load_csv(ast.table, ast.filename)
        self.tables[ast.table] = table
        print(f"Loaded table '{ast.table}' with {len(table)} rows and {len(table.columns)} columns.")
        return None

    def _exec_save(self, ast: SaveStmt) -> Optional[list]:
        """Save a table to CSV."""
        table = self.get_table(ast.table)
        table.save_csv(ast.filename)
        print(f"Saved table '{ast.table}' ({len(table)} rows) to '{ast.filename}'.")
        return None

    def _exec_insert(self, ast: InsertStmt) -> Optional[list]:
        """Insert a row into a table."""
        table = self.get_table(ast.table)
        row = table.insert_row(ast.values)
        print(f"Inserted 1 row into '{ast.table}'.")
        return None

    # ================================================================
    # SELECT execution
    # ================================================================

    def _exec_select(self, ast: SelectStmt) -> list:
        """Execute a SELECT statement."""
        # 1. Get base table rows
        base_table = self.get_table(ast.table)
        rows = list(base_table.rows)  # copy

        # Add __table__ metadata for join resolution
        for row in rows:
            row['__table__'] = ast.table

        # Build column-to-table mapping
        col_to_table = {col: ast.table for col in base_table.columns}
        all_columns = list(base_table.columns)

        # 2. Process JOINs
        for join in ast.joins:
            join_table = self.get_table(join.table)
            new_rows = []

            for left_row in rows:
                for right_row in join_table.rows:
                    # Combine rows with table prefixes for duplicate columns
                    combined = dict(left_row)
                    combined['__table__'] = left_row.get('__table__', ast.table)
                    right_table_name = join.table

                    for col, val in right_row.items():
                        if col in combined and col != '__table__':
                            # Column name conflict - prefix with table name
                            combined[f"{right_table_name}.{col}"] = val
                            # Also keep un-prefixed if from left table
                            combined[f"{ast.table}.{col}"] = combined[col]
                        else:
                            combined[col] = val

                    # Evaluate join condition
                    if self._evaluate_expression(join.condition, combined, col_to_table):
                        new_rows.append(combined)

            rows = new_rows
            # Update column-to-table mapping
            for col in join_table.columns:
                if col in col_to_table:
                    # Conflict - both need table prefix for disambiguation
                    pass
                else:
                    col_to_table[col] = join.table
                all_columns.append(col)

        # 3. Apply WHERE filter
        if ast.where:
            filtered = []
            for row in rows:
                if self._evaluate_expression(ast.where, row, col_to_table):
                    filtered.append(row)
            rows = filtered

        # 4. Handle GROUP BY and aggregates
        if ast.group_by or self._has_aggregates(ast.columns):
            rows = self._process_group_by_and_aggregates(ast, rows, base_table.columns, col_to_table)

        # 5. Apply ORDER BY
        if ast.order_by:
            rows = self._apply_order_by(rows, ast.order_by, col_to_table)

        # 6. Apply LIMIT
        if ast.limit is not None:
            rows = rows[:ast.limit]

        # 7. Project columns
        result_columns, result_rows = self._project_columns(ast.columns, rows, col_to_table)

        return result_columns, result_rows

    # ================================================================
    # Expression evaluation
    # ================================================================

    def _evaluate_expression(self, expr, row: dict, col_to_table: dict) -> Any:
        """Evaluate an expression against a row."""
        if isinstance(expr, ColumnRef):
            return self._resolve_column(expr, row, col_to_table)
        elif isinstance(expr, Literal):
            return expr.value
        elif isinstance(expr, BinaryOp):
            left = self._evaluate_expression(expr.left, row, col_to_table)
            right = self._evaluate_expression(expr.right, row, col_to_table)

            if expr.op in ('AND', 'OR'):
                if expr.op == 'AND':
                    return bool(left) and bool(right)
                else:
                    return bool(left) or bool(right)
            else:
                return _compare_values(left, right, expr.op)
        elif isinstance(expr, AggregateFunc):
            # Aggregates are handled specially in GROUP BY processing
            raise ExecutorError("Aggregate function not allowed in this context")
        elif isinstance(expr, StarSelect):
            raise ExecutorError("* not allowed in this context")
        elif isinstance(expr, AliasedExpr):
            return self._evaluate_expression(expr.expr, row, col_to_table)
        else:
            raise ExecutorError(f"Unknown expression type: {type(expr).__name__}")

    def _resolve_column(self, col_ref: ColumnRef, row: dict, col_to_table: dict):
        """Resolve a column reference to its value in a row."""
        # Try table-qualified name first
        if col_ref.table:
            key = f"{col_ref.table}.{col_ref.name}"
            if key in row:
                return row[key]
            # Also try bare name
            if col_ref.name in row:
                return row[col_ref.name]
        else:
            # Try bare name
            if col_ref.name in row:
                return row[col_ref.name]
            # Try with any table prefix
            for key in row:
                if key.endswith(f".{col_ref.name}"):
                    return row[key]

        raise ExecutorError(f"Column '{col_ref}' not found in row")

    # ================================================================
    # Aggregates and GROUP BY
    # ================================================================

    def _has_aggregates(self, columns: list) -> bool:
        """Check if any column in the select list is an aggregate function."""
        for col in columns:
            if isinstance(col, AggregateFunc):
                return True
            if isinstance(col, AliasedExpr) and isinstance(col.expr, AggregateFunc):
                return True
        return False

    def _process_group_by_and_aggregates(
        self, ast: SelectStmt, rows: list, base_columns: list, col_to_table: dict
    ) -> list:
        """Process GROUP BY and aggregate functions, returning grouped rows."""
        if ast.group_by:
            # Group rows by GROUP BY columns
            groups = {}
            for row in rows:
                key = tuple(
                    self._evaluate_expression(col, row, col_to_table)
                    for col in ast.group_by
                )
                if key not in groups:
                    groups[key] = []
                groups[key].append(row)

            # Compute aggregates for each group
            result_rows = []
            for group_key, group_rows in groups.items():
                new_row = {}
                # Add GROUP BY columns
                for i, col in enumerate(ast.group_by):
                    col_name = col.name if isinstance(col, ColumnRef) else str(col)
                    new_row[col_name] = group_key[i]

                # Compute select list
                for col in ast.columns:
                    self._eval_select_item(col, group_rows, new_row, col_to_table)

                result_rows.append(new_row)

            return result_rows
        else:
            # Aggregates over all rows
            new_row = {}
            for col in ast.columns:
                self._eval_select_item(col, rows, new_row, col_to_table)
            return [new_row]

    def _eval_select_item(self, col, rows: list, target_row: dict, col_to_table: dict):
        """Evaluate a select item (possibly aggregate) and add to target row."""
        if isinstance(col, AggregateFunc):
            name = col.alias or f"{col.func_name}({col.arg})"
            target_row[name] = self._compute_aggregate(col, rows, col_to_table)
        elif isinstance(col, AliasedExpr):
            if isinstance(col.expr, AggregateFunc):
                name = col.alias or f"{col.expr.func_name}({col.expr.arg})"
                target_row[name] = self._compute_aggregate(col.expr, rows, col_to_table)
            else:
                name = col.alias or self._col_name(col.expr)
                if rows:
                    target_row[name] = self._evaluate_expression(col.expr, rows[0], col_to_table)
        elif isinstance(col, StarSelect):
            # Should be handled earlier
            pass
        elif isinstance(col, ColumnRef):
            name = col.name
            if rows:
                target_row[name] = self._evaluate_expression(col, rows[0], col_to_table)
        else:
            if rows:
                name = self._col_name(col)
                target_row[name] = self._evaluate_expression(col, rows[0], col_to_table)

    def _compute_aggregate(self, agg: AggregateFunc, rows: list, col_to_table: dict) -> Any:
        """Compute an aggregate function over rows."""
        func_name = agg.func_name

        if func_name == 'COUNT':
            if isinstance(agg.arg, StarSelect):
                return len(rows)
            else:
                values = [
                    self._evaluate_expression(agg.arg, row, col_to_table)
                    for row in rows
                ]
                return sum(1 for v in values if v is not None)

        # For other aggregates, collect values
        values = []
        for row in rows:
            val = self._evaluate_expression(agg.arg, row, col_to_table)
            if val is not None:
                val = _to_number(val)
                if _is_numeric(val):
                    values.append(val)

        if not values:
            return None if func_name != 'COUNT' else 0

        if func_name == 'SUM':
            return sum(values)
        elif func_name == 'AVG':
            return sum(values) / len(values)
        elif func_name == 'MIN':
            return min(values)
        elif func_name == 'MAX':
            return max(values)
        else:
            raise ExecutorError(f"Unknown aggregate function: {func_name}")

    # ================================================================
    # ORDER BY
    # ================================================================

    def _apply_order_by(self, rows: list, order_items: list, col_to_table: dict) -> list:
        """Sort rows by ORDER BY items."""

        def sort_key(row):
            keys = []
            for item in order_items:
                val = self._evaluate_expression(item.expr, row, col_to_table)
                # Handle None for sorting
                if val is None:
                    val = ''  # Sort None as empty string
                # Normalize for sorting: numbers before strings
                if _is_numeric(val):
                    keys.append((0, val, ''))
                else:
                    keys.append((1, 0, str(val)))
            return keys

        # Sort in reverse for DESC, then handle direction per-column
        # We'll sort multiple times, once per column, stable sort
        result = list(rows)
        for item in reversed(order_items):
            reverse = item.direction.upper() == 'DESC'

            def single_key(row):
                val = self._evaluate_expression(item.expr, row, col_to_table)
                if val is None:
                    val = ''
                if _is_numeric(val):
                    return (0, val, '')
                return (1, 0, str(val))

            result.sort(key=single_key, reverse=reverse)

        return result

    # ================================================================
    # Column projection
    # ================================================================

    def _project_columns(
        self, columns: list, rows: list, col_to_table: dict
    ) -> tuple[list, list]:
        """Project SELECT columns from rows. Returns (column_names, result_rows)."""
        # Check if StarSelect is present
        has_star = any(isinstance(c, StarSelect) for c in columns)

        if has_star:
            # Get all columns from rows
            all_cols = []
            seen = set()
            for row in rows:
                for key in row:
                    if key != '__table__' and key not in seen:
                        all_cols.append(key)
                        seen.add(key)

            result_columns = all_cols
            result_rows = []
            for row in rows:
                result_rows.append([row.get(c) for c in result_columns])
            return result_columns, result_rows

        # Specific columns
        result_columns = []
        col_exprs = []

        for col in columns:
            if isinstance(col, AggregateFunc):
                name = col.alias or f"{col.func_name}({col.arg})"
                result_columns.append(name)
                col_exprs.append(col)
            elif isinstance(col, AliasedExpr):
                name = col.alias or self._col_name(col.expr)
                result_columns.append(name)
                col_exprs.append(col.expr)
            elif isinstance(col, ColumnRef):
                result_columns.append(col.name)
                col_exprs.append(col)
            elif isinstance(col, StarSelect):
                # Should not get here, but handle anyway
                pass
            else:
                result_columns.append(str(col))
                col_exprs.append(col)

        # Build result rows
        result_rows = []
        for row in rows:
            result_row = []
            for expr in col_exprs:
                try:
                    val = self._evaluate_expression(expr, row, col_to_table)
                    result_row.append(val)
                except ExecutorError:
                    result_row.append(None)
            result_rows.append(result_row)

        # If GROUP BY or aggregates were used, rows might already have the values
        # Let's check if the first row has keys matching result_columns
        if rows and result_columns:
            first = rows[0]
            new_result_rows = []
            for row in rows:
                r = []
                for c in result_columns:
                    if c in row:
                        r.append(row[c])
                    else:
                        r.append(None)
                new_result_rows.append(r)
            if any(r for r in new_result_rows if any(v is not None for v in r)):
                result_rows = new_result_rows

        return result_columns, result_rows

    def _col_name(self, expr) -> str:
        """Get a display name for an expression."""
        if isinstance(expr, ColumnRef):
            return expr.name
        if isinstance(expr, AggregateFunc):
            return f"{expr.func_name}({expr.arg})"
        return str(expr)
