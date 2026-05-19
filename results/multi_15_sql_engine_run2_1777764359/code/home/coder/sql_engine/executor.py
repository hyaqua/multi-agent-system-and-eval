"""Query executor - interprets AST against the database.

Handles SELECT, INSERT, LOAD, SAVE, joins, aggregates, ordering, limiting.
"""

from database import Database, Table
from ast import (
    SelectStmt, InsertStmt, LoadStmt, SaveStmt,
    ColumnRef, Literal, StarExpression,
    Comparison, BinaryOp, FunctionCall,
    JoinClause, OrderByItem,
)
from error import QueryError


def _eval_expression(expr, row: dict, tables: dict, table_name: str = None) -> object:
    """Evaluate an expression against a row (column_name -> value dict).

    Args:
        expr: The expression AST node.
        row: dict mapping column_name (possibly unqualified) to value.
        tables: dict of table_name -> table for resolving qualified refs.
        table_name: the "primary" table name (for unqualified resolution).
    """
    if isinstance(expr, Literal):
        return expr.value

    elif isinstance(expr, ColumnRef):
        return _resolve_column(expr, row, tables, table_name)

    elif isinstance(expr, StarExpression):
        raise QueryError("STAR expression not valid in this context.")

    elif isinstance(expr, Comparison):
        left_val = _eval_expression(expr.left, row, tables, table_name)
        right_val = _eval_expression(expr.right, row, tables, table_name)
        return _compare(left_val, right_val, expr.op)

    elif isinstance(expr, BinaryOp):
        left_val = _eval_expression(expr.left, row, tables, table_name)
        right_val = _eval_expression(expr.right, row, tables, table_name)
        if expr.op == 'AND':
            return _to_bool(left_val) and _to_bool(right_val)
        elif expr.op == 'OR':
            return _to_bool(left_val) or _to_bool(right_val)
        elif expr.op == '+':
            return _to_num(left_val) + _to_num(right_val)
        elif expr.op == '-':
            return _to_num(left_val) - _to_num(right_val)
        elif expr.op == '*':
            return _to_num(left_val) * _to_num(right_val)
        elif expr.op == '/':
            return _to_num(left_val) / _to_num(right_val)
        else:
            raise QueryError(f"Unknown binary operator: {expr.op}")

    elif isinstance(expr, FunctionCall):
        raise QueryError("Aggregate functions must be evaluated in SELECT context.")

    else:
        raise QueryError(f"Unknown expression type: {type(expr).__name__}")


def _resolve_column(col_ref: ColumnRef, row: dict, tables: dict, table_name: str) -> object:
    """Resolve a column reference to a value from the row."""
    if col_ref.table:
        # Qualified: table.column
        key = f"{col_ref.table}.{col_ref.name}"
        if key in row:
            return row[key]
        raise QueryError(f"Column '{col_ref.table}.{col_ref.name}' not found.")
    else:
        # Unqualified: try column name directly
        if col_ref.name in row:
            return row[col_ref.name]
        # Try with table prefix if there's a primary table
        if table_name:
            key = f"{table_name}.{col_ref.name}"
            if key in row:
                return row[key]
        raise QueryError(f"Column '{col_ref.name}' not found in row.")


def _compare(left, right, op: str) -> bool:
    """Compare two values with the given operator."""
    # Try numeric comparison first
    try:
        lnum = float(left)
        rnum = float(right)
        if op == '=':
            return lnum == rnum
        elif op == '!=':
            return lnum != rnum
        elif op == '<':
            return lnum < rnum
        elif op == '>':
            return lnum > rnum
        elif op == '<=':
            return lnum <= rnum
        elif op == '>=':
            return lnum >= rnum
    except (ValueError, TypeError):
        pass

    # Fall back to string comparison
    left_str = str(left) if left is not None else ''
    right_str = str(right) if right is not None else ''
    if op == '=':
        return left_str == right_str
    elif op == '!=':
        return left_str != right_str
    elif op == '<':
        return left_str < right_str
    elif op == '>':
        return left_str > right_str
    elif op == '<=':
        return left_str <= right_str
    elif op == '>=':
        return left_str >= right_str
    else:
        raise QueryError(f"Unknown comparison operator: {op}")


def _to_bool(val) -> bool:
    """Convert a value to boolean."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return len(val) > 0
    if isinstance(val, (int, float)):
        return val != 0
    return bool(val)


def _to_num(val):
    """Convert a value to a number, raising QueryError if not possible."""
    try:
        if isinstance(val, (int, float)):
            return val
        return float(val)
    except (ValueError, TypeError):
        raise QueryError(f"Cannot convert '{val}' to a number.")


def _check_aggregate_context(columns, group_by):
    """Validate that non-aggregate columns are in GROUP BY."""
    non_agg = []
    agg_funcs = []
    for col in columns:
        if isinstance(col, FunctionCall):
            agg_funcs.append(col)
        elif isinstance(col, ColumnRef):
            non_agg.append(col)
        elif isinstance(col, StarExpression):
            pass  # SELECT * is handled separately
        else:
            non_agg.append(col)

    if agg_funcs and not group_by:
        # All columns must be aggregates
        if non_agg:
            raise QueryError(
                "Non-aggregate columns are not allowed without GROUP BY when using aggregate functions."
            )
    return non_agg, agg_funcs


def _build_row(template_row, table: Table, table_name: str) -> dict:
    """Build a row dict from a Table row tuple, prefixing columns with table name."""
    row = {}
    for idx, col_name in enumerate(table.columns):
        row[f"{table_name}.{col_name}"] = template_row[idx]
        row[col_name] = template_row[idx]
    return row


class Executor:
    """Executes AST statements against a Database."""

    def __init__(self, database: Database):
        self.db = database

    def execute(self, stmt) -> dict:
        """Execute a statement and return a result dict."""
        if isinstance(stmt, SelectStmt):
            return self._execute_select(stmt)
        elif isinstance(stmt, InsertStmt):
            return self._execute_insert(stmt)
        elif isinstance(stmt, LoadStmt):
            return self._execute_load(stmt)
        elif isinstance(stmt, SaveStmt):
            return self._execute_save(stmt)
        else:
            raise QueryError(f"Unknown statement type: {type(stmt).__name__}")

    def _execute_load(self, stmt: LoadStmt) -> dict:
        self.db.load_csv(stmt.table, stmt.filepath)
        table = self.db.get_table(stmt.table)
        return {
            'type': 'message',
            'message': f"Loaded table '{stmt.table}' with {table.row_count()} rows."
        }

    def _execute_save(self, stmt: SaveStmt) -> dict:
        self.db.save_csv(stmt.table, stmt.filepath)
        return {
            'type': 'message',
            'message': f"Saved table '{stmt.table}' to '{stmt.filepath}'."
        }

    def _execute_insert(self, stmt: InsertStmt) -> dict:
        table = self.db.get_table(stmt.table)
        # Evaluate all values (they should all be literals)
        values = []
        for expr in stmt.values:
            if isinstance(expr, Literal):
                values.append(expr.value)
            else:
                raise QueryError("INSERT values must be literal values.")

        if len(values) != len(table.columns):
            raise QueryError(
                f"Expected {len(table.columns)} values but got {len(values)}."
            )

        table.insert_row(tuple(values))
        return {
            'type': 'message',
            'message': f"Inserted 1 row into '{stmt.table}'."
        }

    def _execute_select(self, stmt: SelectStmt) -> dict:
        # Get the primary table
        primary_table = self.db.get_table(stmt.table)

        # Build initial row set
        rows = []
        for row_tuple in primary_table.rows:
            row = _build_row(row_tuple, primary_table, stmt.table)
            rows.append(row)

        # Apply JOINs
        tables_ctx = {stmt.table: primary_table}
        for join in stmt.joins:
            join_table = self.db.get_table(join.table)
            tables_ctx[join.table] = join_table
            rows = self._apply_join(rows, join_table, join, stmt.table)

        # Apply WHERE
        if stmt.where:
            rows = self._apply_where(rows, stmt.where, tables_ctx, stmt.table)

        # Handle SELECT *
        if len(stmt.columns) == 1 and isinstance(stmt.columns[0], StarExpression):
            return self._build_star_result(rows, primary_table, stmt)

        # Check for aggregates
        has_aggregate = any(isinstance(c, FunctionCall) for c in stmt.columns)

        if has_aggregate:
            return self._execute_aggregate(rows, stmt, tables_ctx)
        else:
            return self._execute_simple_select(rows, stmt, tables_ctx)

    def _apply_join(self, left_rows: list[dict], join_table: Table,
                    join_clause: JoinClause, primary_table_name: str) -> list[dict]:
        """Perform INNER JOIN."""
        result = []
        for left_row in left_rows:
            for right_tuple in join_table.rows:
                right_row = _build_row(right_tuple, join_table, join_clause.table)
                combined = {**left_row, **right_row}

                # Evaluate ON condition
                try:
                    cond = _eval_expression(
                        join_clause.on_condition, combined,
                        {primary_table_name: None, join_clause.table: None},
                        primary_table_name
                    )
                except QueryError:
                    cond = False

                if _to_bool(cond):
                    result.append(combined)
        return result

    def _apply_where(self, rows: list[dict], where_expr,
                     tables: dict, table_name: str) -> list[dict]:
        result = []
        for row in rows:
            try:
                cond = _eval_expression(where_expr, row, tables, table_name)
            except QueryError:
                cond = False
            if _to_bool(cond):
                result.append(row)
        return result

    def _execute_simple_select(self, rows: list[dict], stmt: SelectStmt,
                                tables: dict) -> dict:
        """Select without aggregates."""
        # Project columns
        projected = []
        for row in rows:
            proj_row = []
            for col_expr in stmt.columns:
                if isinstance(col_expr, ColumnRef):
                    val = _resolve_column(col_expr, row, tables, stmt.table)
                    proj_row.append(val)
                elif isinstance(col_expr, FunctionCall):
                    # Shouldn't happen in simple select, but handle gracefully
                    raise QueryError("Unexpected aggregate in simple select.")
                else:
                    val = _eval_expression(col_expr, row, tables, stmt.table)
                    proj_row.append(val)
            projected.append(tuple(proj_row))

        # Column names
        col_names = []
        for col_expr in stmt.columns:
            if isinstance(col_expr, ColumnRef):
                if col_expr.table:
                    col_names.append(f"{col_expr.table}.{col_expr.name}")
                else:
                    col_names.append(col_expr.name)
            else:
                col_names.append(str(col_expr))

        # ORDER BY
        if stmt.order_by:
            projected = self._apply_order_by(projected, col_names, stmt.order_by,
                                              rows, tables, stmt.table)

        # LIMIT
        if stmt.limit is not None:
            projected = projected[:stmt.limit]

        return {
            'type': 'table',
            'columns': col_names,
            'rows': projected
        }

    def _execute_aggregate(self, rows: list[dict], stmt: SelectStmt,
                            tables: dict) -> dict:
        """Execute SELECT with aggregate functions."""
        if not stmt.group_by:
            # No GROUP BY - one group of all rows
            groups = {(): rows}
            group_col_names = []
            group_col_exprs = []
        else:
            # GROUP BY
            groups = {}
            group_col_exprs = stmt.group_by
            group_col_names = []
            for expr in group_col_exprs:
                if isinstance(expr, ColumnRef):
                    if expr.table:
                        group_col_names.append(f"{expr.table}.{expr.name}")
                    else:
                        group_col_names.append(expr.name)
                else:
                    group_col_names.append(str(expr))

            for row in rows:
                key = tuple(
                    _eval_expression(expr, row, tables, stmt.table)
                    for expr in group_col_exprs
                )
                groups.setdefault(key, []).append(row)

        # Validate: non-aggregate columns must be in GROUP BY
        non_agg_cols = []
        agg_cols = []
        for col in stmt.columns:
            if isinstance(col, FunctionCall):
                agg_cols.append(col)
            elif isinstance(col, ColumnRef):
                # Check if it's in GROUP BY
                found = False
                for gexpr in stmt.group_by:
                    if isinstance(gexpr, ColumnRef):
                        if (col.table == gexpr.table and col.name == gexpr.name) or \
                           (col.table is None and gexpr.table is None and col.name == gexpr.name):
                            found = True
                            break
                if not found:
                    raise QueryError(
                        f"Column '{col.name}' must appear in GROUP BY when using aggregate functions."
                    )
                non_agg_cols.append(col)
            else:
                non_agg_cols.append(col)

        # Build result columns
        result_cols = []
        for col in stmt.columns:
            if isinstance(col, FunctionCall):
                name = col.alias if col.alias else f"{col.func_name}({self._expr_str(col.arg)})"
                result_cols.append(name)
            elif isinstance(col, ColumnRef):
                result_cols.append(col.name)
            else:
                result_cols.append(str(col))

        # Compute results per group
        result_rows = []
        for group_key, group_rows in groups.items():
            result_row = []
            col_idx = 0
            for col in stmt.columns:
                if isinstance(col, FunctionCall):
                    val = self._compute_aggregate(col, group_rows, tables, stmt.table)
                elif isinstance(col, ColumnRef):
                    # Value from group key
                    # Find which group-by index this corresponds to
                    idx = self._find_group_idx(col, group_col_exprs)
                    if idx >= 0:
                        val = group_key[idx]
                    else:
                        # Take first row's value (should be same for all rows in group)
                        val = _eval_expression(col, group_rows[0], tables, stmt.table)
                else:
                    val = group_key[col_idx] if col_idx < len(group_key) else None
                result_row.append(val)
                col_idx += 1
            result_rows.append(tuple(result_row))

        # ORDER BY
        if stmt.order_by:
            result_rows = self._apply_order_by(result_rows, result_cols, stmt.order_by,
                                                None, tables, stmt.table)

        # LIMIT
        if stmt.limit is not None:
            result_rows = result_rows[:stmt.limit]

        return {
            'type': 'table',
            'columns': result_cols,
            'rows': result_rows
        }

    def _find_group_idx(self, col: ColumnRef, group_exprs: list) -> int:
        """Find the index of a column in group by expressions."""
        for i, gexpr in enumerate(group_exprs):
            if isinstance(gexpr, ColumnRef):
                if (col.table == gexpr.table and col.name == gexpr.name) or \
                   (col.table is None and gexpr.table is None and col.name == gexpr.name):
                    return i
        return -1

    def _expr_str(self, expr) -> str:
        """String representation of an expression for display."""
        if isinstance(expr, ColumnRef):
            return expr.name
        elif isinstance(expr, StarExpression):
            return '*'
        return str(expr)

    def _compute_aggregate(self, func: FunctionCall, rows: list[dict],
                           tables: dict, table_name: str) -> object:
        """Compute an aggregate function over a set of rows."""
        func_name = func.func_name

        if func_name == 'COUNT':
            if isinstance(func.arg, StarExpression):
                return len(rows)
            # COUNT(column): count non-empty values
            count = 0
            for row in rows:
                try:
                    val = _eval_expression(func.arg, row, tables, table_name)
                    if val is not None and val != '':
                        count += 1
                except QueryError:
                    pass
            return count

        # For other aggregates, collect values
        values = []
        for row in rows:
            try:
                val = _eval_expression(func.arg, row, tables, table_name)
                if val is not None and val != '':
                    values.append(_to_num(val))
            except (QueryError, ValueError, TypeError):
                pass

        if func_name == 'SUM':
            return sum(values) if values else 0
        elif func_name == 'AVG':
            return sum(values) / len(values) if values else 0
        elif func_name == 'MIN':
            return min(values) if values else None
        elif func_name == 'MAX':
            return max(values) if values else None
        else:
            raise QueryError(f"Unknown aggregate function: {func_name}")

    def _apply_order_by(self, rows: list[tuple], col_names: list[str],
                         order_by: list[OrderByItem],
                         original_rows: list[dict], tables: dict,
                         table_name: str) -> list[tuple]:
        """Sort rows by ORDER BY expressions."""

        def sort_key(row_tuple):
            key_parts = []
            for item in order_by:
                # Find column index
                col_expr = item.expr
                if isinstance(col_expr, ColumnRef):
                    col_name = col_expr.name
                    # Find in column names
                    idx = None
                    for i, cn in enumerate(col_names):
                        if cn == col_name or cn.endswith('.' + col_name):
                            idx = i
                            break
                    if idx is not None:
                        val = row_tuple[idx]
                    elif original_rows:
                        # Try to evaluate from original rows (for aggregate ORDER BY)
                        # This is tricky. For aggregate results, use the result tuple.
                        val = row_tuple[0]  # fallback
                    else:
                        val = row_tuple[0]
                else:
                    # For non-column expressions in ORDER BY
                    val = row_tuple[0]

                # Convert for comparison
                try:
                    val_num = float(val)
                    key_parts.append((0, val_num))  # (type: 0=number, value)
                except (ValueError, TypeError):
                    key_parts.append((1, str(val) if val is not None else ''))

            return tuple(key_parts)

        # Apply sorting
        desc_flags = [item.desc for item in order_by]
        # Python's sorted is stable, so we can sort by each key in reverse order
        # But simpler: just sort with a composite key, reversing based on flags
        # We'll use a single-pass approach
        def final_sort_key(row_tuple):
            parts = []
            for i, item in enumerate(order_by):
                col_expr = item.expr
                if isinstance(col_expr, ColumnRef):
                    col_name = col_expr.name
                    idx = None
                    for j, cn in enumerate(col_names):
                        if cn == col_name or cn.endswith('.' + col_name):
                            idx = j
                            break
                    if idx is not None:
                        val = row_tuple[idx]
                    else:
                        val = ''
                else:
                    val = ''
                # Normalize for sorting
                try:
                    val_num = float(val)
                    parts.append(val_num)
                except (ValueError, TypeError):
                    parts.append(str(val) if val is not None else '')
            return parts

        # Sort with multiple keys using Python's stable sort
        sorted_rows = list(rows)
        # Sort by each ORDER BY item from last to first (stable sort)
        for i in range(len(order_by) - 1, -1, -1):
            item = order_by[i]
            idx = i

            def make_key(idx):
                def key_fn(row_tuple):
                    col_expr = order_by[idx].expr
                    if isinstance(col_expr, ColumnRef):
                        col_name = col_expr.name
                        for j, cn in enumerate(col_names):
                            if cn == col_name or cn.endswith('.' + col_name):
                                val = row_tuple[j]
                                try:
                                    return float(val)
                                except (ValueError, TypeError):
                                    return str(val) if val is not None else ''
                        return ''
                    return row_tuple[0] if row_tuple else ''
                return key_fn

            sorted_rows.sort(key=make_key(i), reverse=order_by[i].desc)

        return sorted_rows

    def _build_star_result(self, rows: list[dict], primary_table: Table,
                            stmt: SelectStmt) -> dict:
        """Build result for SELECT *."""
        # For a simple SELECT * FROM single table (no joins)
        if not stmt.joins:
            # Use original table order
            cols = list(primary_table.columns)
            result_rows = []
            for row_dict in rows:
                result_rows.append(tuple(row_dict[col] for col in cols))

            # ORDER BY
            if stmt.order_by:
                result_rows = self._apply_order_by_star(result_rows, cols, stmt.order_by, rows)

            # LIMIT
            if stmt.limit is not None:
                result_rows = result_rows[:stmt.limit]

            return {'type': 'table', 'columns': cols, 'rows': result_rows}
        else:
            # With joins, collect all column names preserving order
            all_cols = list(primary_table.columns)
            for join in stmt.joins:
                join_table = self.db.get_table(join.table)
                all_cols.extend(join_table.columns)

            result_rows = []
            for row_dict in rows:
                r = []
                for col in all_cols:
                    r.append(row_dict.get(col, ''))
                result_rows.append(tuple(r))

            if stmt.order_by:
                result_rows = self._apply_order_by_star(result_rows, all_cols, stmt.order_by, rows)

            if stmt.limit is not None:
                result_rows = result_rows[:stmt.limit]

            return {'type': 'table', 'columns': all_cols, 'rows': result_rows}

    def _apply_order_by_star(self, rows: list[tuple], col_names: list[str],
                              order_by: list[OrderByItem],
                              original_rows: list[dict]) -> list[tuple]:
        """Apply ORDER BY for SELECT * results."""
        sorted_rows = list(rows)
        for i in range(len(order_by) - 1, -1, -1):
            item = order_by[i]

            def make_key(idx):
                def key_fn(row_tuple):
                    col_expr = order_by[idx].expr
                    if isinstance(col_expr, ColumnRef):
                        col_name = col_expr.name
                        for j, cn in enumerate(col_names):
                            if cn == col_name or cn.endswith('.' + col_name):
                                val = row_tuple[j]
                                try:
                                    return float(val)
                                except (ValueError, TypeError):
                                    return str(val) if val is not None else ''
                        return ''
                    return row_tuple[0] if row_tuple else ''
                return key_fn

            sorted_rows.sort(key=make_key(i), reverse=order_by[i].desc)

        return sorted_rows
