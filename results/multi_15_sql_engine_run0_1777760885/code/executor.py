"""Executor: executes AST nodes against the table store."""

from table import Table
from error import SQLError
from parser import (
    SelectStatement, InsertStatement, LoadCommand, SaveCommand,
    Column, Star, FunctionCall, Literal, BinaryOp, JoinNode,
)


def _to_number(val):
    """Try to convert string to float; return None on failure."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _numeric_or_str(val):
    """Return the numeric value if possible, else the string itself."""
    n = _to_number(val)
    return n if n is not None else val


def _resolve_column(col_ref, row, table_name=None, tables_in_scope=None):
    """
    Given a Column reference, return the value from the row.
    If the column has a table qualifier, look up column 'table.column'.
    If not, try plain column, then fallback to 'scope.column'.
    """
    if col_ref.table:
        key = f"{col_ref.table}.{col_ref.name}"
        return row.get(key, "")
    else:
        # Try plain column first
        if col_ref.name in row:
            return row[col_ref.name]
        # Try with table name prefix (for joined rows)
        if tables_in_scope:
            for tname in tables_in_scope:
                key = f"{tname}.{col_ref.name}"
                if key in row:
                    return row[key]
        return row.get(col_ref.name, "")


def _resolve_colname(col_ref, table_name=None):
    """Get the display column name for a Column reference."""
    if col_ref.table:
        return f"{col_ref.table}.{col_ref.name}"
    return col_ref.name


class Executor:
    def __init__(self):
        self.tables = {}  # name -> Table

    def execute(self, ast):
        if ast is None:
            return None, None
        if isinstance(ast, LoadCommand):
            return self.execute_load(ast)
        elif isinstance(ast, SaveCommand):
            return self.execute_save(ast)
        elif isinstance(ast, InsertStatement):
            return self.execute_insert(ast)
        elif isinstance(ast, SelectStatement):
            return self.execute_select(ast)
        else:
            raise SQLError(f"Unknown AST node: {type(ast).__name__}")

    # ── LOAD ──────────────────────────────────────────────────────
    def execute_load(self, ast):
        table = Table(ast.table)
        table.load_csv(ast.filepath)
        self.tables[ast.table] = table
        return None, f"Loaded table '{ast.table}' from '{ast.filepath}' ({len(table.rows)} rows, {len(table.columns)} columns)."

    # ── SAVE ──────────────────────────────────────────────────────
    def execute_save(self, ast):
        if ast.table not in self.tables:
            raise SQLError(f"Table '{ast.table}' not found.")
        table = self.tables[ast.table]
        table.save_csv(ast.filepath)
        return None, f"Saved table '{ast.table}' to '{ast.filepath}' ({len(table.rows)} rows)."

    # ── INSERT ────────────────────────────────────────────────────
    def execute_insert(self, ast):
        if ast.table not in self.tables:
            raise SQLError(f"Table '{ast.table}' not found.")
        table = self.tables[ast.table]

        if ast.columns:
            if len(ast.columns) != len(ast.values):
                raise SQLError(
                    f"Column count ({len(ast.columns)}) does not match value count ({len(ast.values)})."
                )
            row_dict = {}
            for col_ref, val in zip(ast.columns, ast.values):
                row_dict[col_ref.name] = val.value
        else:
            if len(ast.values) != len(table.columns):
                raise SQLError(
                    f"Table '{ast.table}' has {len(table.columns)} columns but {len(ast.values)} values provided."
                )
            row_dict = {}
            for col_name, val in zip(table.columns, ast.values):
                row_dict[col_name] = val.value

        table.add_row(row_dict)
        return None, f"Inserted 1 row into '{ast.table}'."

    # ── SELECT ────────────────────────────────────────────────────
    def execute_select(self, ast):
        # Get the source table(s)
        table_name = ast.table
        if table_name not in self.tables:
            raise SQLError(f"Table '{table_name}' not found.")
        table = self.tables[table_name]
        columns_order = list(table.columns)
        rows = list(table.rows)

        # Track which tables are in scope for column resolution
        tables_in_scope = [table_name]

        # Handle JOIN
        if ast.join:
            join_node = ast.join
            join_table_name = join_node.table
            if join_table_name not in self.tables:
                raise SQLError(f"Table '{join_table_name}' not found in JOIN.")
            join_table = self.tables[join_table_name]
            tables_in_scope.append(join_table_name)

            # Nested loop join
            joined_rows = []
            for r1 in rows:
                for r2 in join_table.rows:
                    # Build combined row with prefixed column names
                    combined = {}
                    for col in table.columns:
                        combined[f"{table_name}.{col}"] = r1.get(col, "")
                    for col in join_table.columns:
                        combined[f"{join_table_name}.{col}"] = r2.get(col, "")

                    # Evaluate ON condition
                    if self._eval_join_condition(join_node, combined, table_name, join_table_name):
                        joined_rows.append(combined)

            rows = joined_rows
            columns_order = [f"{table_name}.{col}" for col in table.columns] + \
                           [f"{join_table_name}.{col}" for col in join_table.columns]

        # Apply WHERE
        if ast.where:
            rows = [r for r in rows if self._eval_condition(ast.where, r, tables_in_scope)]

        # Apply GROUP BY
        result_columns = None
        if ast.group_by:
            rows, result_columns = self._apply_group_by(
                ast.group_by, ast.columns, rows, tables_in_scope
            )
        else:
            # Check for aggregates without GROUP BY
            has_agg = any(isinstance(c, FunctionCall) for c in ast.columns)
            if has_agg:
                # One row aggregation
                agg_row = {}
                out_cols = []
                for col in ast.columns:
                    if isinstance(col, FunctionCall):
                        out_cols.append(str(col))
                        agg_row[str(col)] = self._compute_aggregate(col, rows, None, tables_in_scope)
                    elif isinstance(col, Column):
                        # Non-aggregate column without GROUP BY: error
                        raise SQLError(
                            f"Column '{col}' must appear in GROUP BY clause when used with aggregate functions."
                        )
                    elif isinstance(col, Star):
                        raise SQLError(
                            "Cannot use SELECT * with aggregate functions without GROUP BY."
                        )
                rows = [agg_row]
                result_columns = out_cols

        # Apply HAVING
        if ast.having:
            if not ast.group_by and not has_agg:
                # HAVING without GROUP BY or aggregates
                rows = [r for r in rows if self._eval_condition(ast.having, r, tables_in_scope)]
            else:
                rows = [r for r in rows if self._eval_condition(ast.having, r, tables_in_scope)]

        # Select columns (projection)
        if result_columns is None:
            # Determine output columns from SELECT clause
            out_cols = []
            for col in ast.columns:
                if isinstance(col, Star):
                    if col.table:
                        prefix = f"{col.table}."
                        for c in columns_order:
                            if c.startswith(prefix):
                                out_cols.append(c)
                    else:
                        out_cols = list(columns_order)
                elif isinstance(col, FunctionCall):
                    out_cols.append(str(col))
                elif isinstance(col, Column):
                    # Find the actual column key in rows
                    resolved = self._find_column_key(col, rows, tables_in_scope, columns_order)
                    out_cols.append(resolved)
                else:
                    out_cols.append(str(col))
            result_columns = out_cols

        # Project rows
        projected = []
        for r in rows:
            proj = {}
            for ci, col in enumerate(ast.columns):
                out_key = result_columns[ci]
                if isinstance(col, Star):
                    # Copy all relevant columns
                    for c in columns_order:
                        if col.table:
                            if c.startswith(f"{col.table}."):
                                proj[c] = r.get(c, "")
                        else:
                            proj[c] = r.get(c, "")
                elif isinstance(col, FunctionCall):
                    # Already computed (in group by or aggregate)
                    proj[out_key] = r.get(out_key, "")
                elif isinstance(col, Column):
                    val = _resolve_column(col, r, table_name, tables_in_scope)
                    proj[out_key] = val if val is not None else ""
                else:
                    proj[out_key] = r.get(out_key, "")
            projected.append(proj)

        # If we have a star, result_columns may have been overwritten
        # Recompute from projected
        if any(isinstance(c, Star) for c in ast.columns):
            if projected:
                result_columns = list(projected[0].keys())
            else:
                result_columns = []

        rows = projected

        # Apply ORDER BY
        if ast.order_by:
            rows = self._apply_order_by(rows, ast.order_by, tables_in_scope)

        # Apply LIMIT
        if ast.limit is not None:
            rows = rows[:ast.limit]

        # Final result columns
        if result_columns is None:
            result_columns = list(rows[0].keys()) if rows else []

        return (result_columns, rows, len(rows)), None

    def _find_column_key(self, col_ref, rows, tables_in_scope, columns_order):
        """Find the actual key used in rows for a given Column reference."""
        if col_ref.table:
            key = f"{col_ref.table}.{col_ref.name}"
            return key
        # Try plain column name
        for r in rows:
            if col_ref.name in r:
                return col_ref.name
        # Try with table prefix
        for tname in tables_in_scope:
            key = f"{tname}.{col_ref.name}"
            for r in rows:
                if key in r:
                    return key
        return col_ref.name

    # ── Condition evaluation ──────────────────────────────────────
    def _eval_condition(self, cond, row, tables_in_scope):
        """Recursively evaluate a condition tree against a row."""
        if isinstance(cond, BinaryOp):
            if cond.op in ("AND", "OR"):
                left_val = self._eval_condition(cond.left, row, tables_in_scope)
                right_val = self._eval_condition(cond.right, row, tables_in_scope)
                if cond.op == "AND":
                    return left_val and right_val
                else:
                    return left_val or right_val
            else:
                # Comparison
                left_val = self._eval_value(cond.left, row, tables_in_scope)
                right_val = self._eval_value(cond.right, row, tables_in_scope)
                return self._compare(left_val, right_val, cond.op)
        return True

    def _eval_value(self, node, row, tables_in_scope):
        """Evaluate a value node (Column, Literal, FunctionCall) to a Python value."""
        if isinstance(node, Column):
            v = _resolve_column(node, row, None, tables_in_scope)
            return _numeric_or_str(v)
        elif isinstance(node, Literal):
            return _numeric_or_str(node.value)
        elif isinstance(node, FunctionCall):
            # Allow aggregate in HAVING — compute on the single group row
            # But this is tricky; for HAVING we compute per-group.
            # The row passed here already has the aggregate value computed.
            key = str(node)
            if key in row:
                return _numeric_or_str(row[key])
            return 0
        return node

    def _compare(self, left, right, op):
        """Compare two values with given operator."""
        # Try numeric comparison if both are numbers
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if op == "=":
                return left == right
            elif op in ("!=", "<>"):
                return left != right
            elif op == "<":
                return left < right
            elif op == ">":
                return left > right
            elif op == "<=":
                return left <= right
            elif op == ">=":
                return left >= right
        else:
            # String comparison
            ls = str(left)
            rs = str(right)
            if op == "=":
                return ls == rs
            elif op in ("!=", "<>"):
                return ls != rs
            elif op == "<":
                return ls < rs
            elif op == ">":
                return ls > rs
            elif op == "<=":
                return ls <= rs
            elif op == ">=":
                return ls >= rs
        return False

    def _eval_join_condition(self, join_node, combined_row, table1, table2):
        """Evaluate the ON condition for a JOIN."""
        left_key = f"{join_node.left_col.table}.{join_node.left_col.name}"
        right_key = f"{join_node.right_col.table}.{join_node.right_col.name}"
        return combined_row.get(left_key, "") == combined_row.get(right_key, "")

    # ── ORDER BY ──────────────────────────────────────────────────
    def _apply_order_by(self, rows, order_specs, tables_in_scope):
        """Sort rows by given order specifications."""
        def sort_key(r):
            keys = []
            for col_ref, asc in order_specs:
                v = _resolve_column(col_ref, r, None, tables_in_scope)
                n = _to_number(v)
                # If numeric, use number for correct ordering
                if n is not None:
                    keys.append(n)
                else:
                    keys.append(v if v else "")
            return tuple(keys)

        # Python sort is stable; apply with reverse per spec
        # We need to sort by multiple keys with mixed asc/desc
        # Strategy: sort by least significant key first, then more significant
        for col_ref, asc in reversed(order_specs):
            def make_key(cr=col_ref, a=asc):
                def k(r):
                    v = _resolve_column(cr, r, None, tables_in_scope)
                    n = _to_number(v)
                    val = n if n is not None else (v if v is not None else "")
                    return val
                return k
            rows.sort(key=make_key(), reverse=not asc)
        return rows

    # ── GROUP BY ──────────────────────────────────────────────────
    def _apply_group_by(self, group_cols, select_cols, rows, tables_in_scope):
        """Group rows and compute aggregates."""
        # Build groups
        groups = {}
        for r in rows:
            key_parts = []
            for gc in group_cols:
                v = _resolve_column(gc, r, None, tables_in_scope)
                key_parts.append(v if v is not None else "")
            group_key = tuple(key_parts)

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(r)

        # For each group, compute aggregate functions
        result_rows = []
        result_columns = []

        for group_key, group_rows in groups.items():
            out_row = {}
            # Add group columns
            for i, gc in enumerate(group_cols):
                col_name = _resolve_colname(gc)
                out_row[col_name] = group_key[i]
                if col_name not in result_columns:
                    result_columns.append(col_name)

            # Compute aggregates
            for col in select_cols:
                if isinstance(col, FunctionCall):
                    agg_name = str(col)
                    out_row[agg_name] = self._compute_aggregate(col, group_rows, group_key, tables_in_scope)
                    if agg_name not in result_columns:
                        result_columns.append(agg_name)
                elif isinstance(col, Column):
                    # Non-aggregate column must be in GROUP BY
                    col_name = _resolve_colname(col)
                    if col_name not in [str(gc) for gc in group_cols]:
                        raise SQLError(
                            f"Column '{col}' must appear in GROUP BY clause or be used in an aggregate function."
                        )
                elif isinstance(col, Star):
                    raise SQLError("Cannot use SELECT * with GROUP BY.")

            result_rows.append(out_row)

        return result_rows, result_columns

    def _compute_aggregate(self, func_call, rows, group_key, tables_in_scope):
        """Compute an aggregate function over a set of rows."""
        func_name = func_call.name

        if func_name == "COUNT":
            if func_call.arg is None or isinstance(func_call.arg, Star):
                return str(len(rows))
            else:
                # COUNT(column): count non-empty values
                count = 0
                for r in rows:
                    v = _resolve_column(func_call.arg, r, None, tables_in_scope)
                    if v is not None and v != "":
                        count += 1
                return str(count)

        # For SUM, AVG, MIN, MAX: collect values
        values = []
        for r in rows:
            v = _resolve_column(func_call.arg, r, None, tables_in_scope)
            n = _to_number(v)
            if n is not None:
                values.append(n)

        if func_name == "SUM":
            return str(sum(values)) if values else "0"
        elif func_name == "AVG":
            if not values:
                return "0"
            avg = sum(values) / len(values)
            # Format nicely
            if avg == int(avg):
                return str(int(avg))
            return f"{avg:.4f}".rstrip("0").rstrip(".")
        elif func_name == "MIN":
            if not values:
                # MIN on strings
                str_vals = [_resolve_column(func_call.arg, r, None, tables_in_scope) for r in rows]
                str_vals = [s for s in str_vals if s is not None and s != ""]
                return min(str_vals) if str_vals else ""
            return str(min(values))
        elif func_name == "MAX":
            if not values:
                str_vals = [_resolve_column(func_call.arg, r, None, tables_in_scope) for r in rows]
                str_vals = [s for s in str_vals if s is not None and s != ""]
                return max(str_vals) if str_vals else ""
            return str(max(values))

        return "0"
