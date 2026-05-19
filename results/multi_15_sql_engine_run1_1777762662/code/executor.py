"""Core executor – maintains in‑memory tables and executes SQL statements."""

import csv
import os
from ast_nodes import (
    Star, ColumnRef, Literal, AggregateCall, BinaryOp, OrderItem, JoinClause
)


class ExecutionError(Exception):
    pass


def try_numeric(value):
    """Try to convert a value to int or float for comparison."""
    if not isinstance(value, str):
        return value
    # Try int first, then float
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return value


def compare_values(left, right, op):
    """Compare two values with type coercion."""
    # Try numeric comparison
    l_num = try_numeric(left)
    r_num = try_numeric(right)

    if isinstance(l_num, (int, float)) and isinstance(r_num, (int, float)):
        left_v = l_num
        right_v = r_num
    else:
        left_v = str(left)
        right_v = str(right)

    if op == '=':
        return left_v == right_v
    elif op == '!=':
        return left_v != right_v
    elif op == '<':
        return left_v < right_v
    elif op == '>':
        return left_v > right_v
    elif op == '<=':
        return left_v <= right_v
    elif op == '>=':
        return left_v >= right_v
    return False


def evaluate_expression(expr, row, tables=None):
    """Evaluate an expression against a row dict."""
    if isinstance(expr, ColumnRef):
        return resolve_column_value(expr, row, tables)
    elif isinstance(expr, Literal):
        return expr.value
    elif isinstance(expr, BinaryOp):
        return evaluate_binary_op(expr, row, tables)
    return None


def resolve_column_value(col_ref, row, tables=None):
    """Get the value of a column reference from a row."""
    if col_ref.table:
        key = f"{col_ref.table}.{col_ref.name}"
        return row.get(key, '')
    else:
        # Unqualified name – look through row keys
        # If it's a joined row, keys are like "table.column"
        if col_ref.name in row:
            return row[col_ref.name]
        # Try matching against qualified keys
        for key, val in row.items():
            if '.' in key and key.split('.', 1)[1] == col_ref.name:
                return val
        return ''


def evaluate_binary_op(binop, row, tables=None):
    """Evaluate a BinaryOp expression."""
    if binop.op in ('AND', 'OR'):
        left_val = evaluate_expression(binop.left, row, tables)
        if binop.op == 'AND':
            if not left_val:
                return False
            return bool(evaluate_expression(binop.right, row, tables))
        else:  # OR
            if left_val:
                return True
            return bool(evaluate_expression(binop.right, row, tables))

    # Comparison operators
    left_val = evaluate_expression(binop.left, row, tables)
    right_val = evaluate_expression(binop.right, row, tables)
    return compare_values(left_val, right_val, binop.op)


class Executor:
    def __init__(self):
        self.tables = {}  # table_name -> {"columns": [...], "rows": [{...}, ...]}

    def execute(self, statement):
        """Execute a parsed statement and return (columns, rows)."""
        from ast_nodes import (
            LoadStatement, SaveStatement, InsertStatement, SelectStatement
        )

        if isinstance(statement, LoadStatement):
            return self.execute_load(statement)
        elif isinstance(statement, SaveStatement):
            return self.execute_save(statement)
        elif isinstance(statement, InsertStatement):
            return self.execute_insert(statement)
        elif isinstance(statement, SelectStatement):
            return self.execute_select(statement)
        else:
            raise ExecutionError(f"Unknown statement type: {type(statement).__name__}")

    def execute_load(self, stmt):
        """Load a CSV file into a table."""
        filepath = stmt.filepath
        if not os.path.exists(filepath):
            raise ExecutionError(f"File not found: {filepath}")

        try:
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                if columns is None:
                    raise ExecutionError(f"No columns found in {filepath}")
                rows = []
                for row in reader:
                    rows.append(dict(row))
                self.tables[stmt.table_name] = {
                    'columns': list(columns),
                    'rows': rows
                }
            return (['Result'], [{'Result': f'Loaded {len(rows)} rows into {stmt.table_name}'}])
        except Exception as e:
            raise ExecutionError(str(e))

    def execute_save(self, stmt):
        """Save a table to a CSV file."""
        if stmt.table_name not in self.tables:
            raise ExecutionError(f"Table not found: {stmt.table_name}")

        table = self.tables[stmt.table_name]
        try:
            with open(stmt.filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=table['columns'])
                writer.writeheader()
                for row in table['rows']:
                    writer.writerow(row)
            return (['Result'],
                    [{'Result': f'Saved {len(table["rows"])} rows to {stmt.filepath}'}])
        except Exception as e:
            raise ExecutionError(str(e))

    def execute_insert(self, stmt):
        """Insert a row into a table."""
        if stmt.table_name not in self.tables:
            raise ExecutionError(f"Table not found: {stmt.table_name}")

        table = self.tables[stmt.table_name]
        columns = table['columns']

        if len(stmt.values) != len(columns):
            raise ExecutionError(
                f"Expected {len(columns)} values but got {len(stmt.values)}"
            )

        row = {}
        for col, val in zip(columns, stmt.values):
            if isinstance(val, Literal):
                row[col] = val.value
            else:
                row[col] = val

        table['rows'].append(row)
        return (['Result'], [{'Result': f'Inserted 1 row into {stmt.table_name}'}])

    def execute_select(self, stmt):
        """Execute a SELECT statement."""
        from_tables = stmt.from_tables
        base_table = from_tables[0]

        if base_table not in self.tables:
            raise ExecutionError(f"Table not found: {base_table}")

        # Get base rows
        base_data = self.tables[base_table]

        # If there's a join, build joined rows
        if stmt.join:
            rows = self._perform_join(base_data, stmt.join)
        else:
            rows = []
            for row in base_data['rows']:
                rows.append(dict(row))  # Shallow copy

        # WHERE filtering
        if stmt.where:
            filtered = []
            for row in rows:
                if evaluate_expression(stmt.where, row, self.tables):
                    filtered.append(row)
            rows = filtered

        # GROUP BY
        if stmt.group_by:
            rows = self._do_group_by(rows, stmt)

        # Determine output columns
        columns, rows = self._project_select_items(stmt, rows, stmt.join)

        # ORDER BY
        if stmt.order_by:
            self._do_order_by(rows, stmt.order_by)

        # LIMIT
        if stmt.limit is not None:
            rows = rows[:stmt.limit]

        return (columns, rows)

    def _perform_join(self, base_data, join_clause):
        """Nested-loop INNER JOIN."""
        join_table_name = join_clause.table_name
        if join_table_name not in self.tables:
            raise ExecutionError(f"Table not found: {join_table_name}")

        join_data = self.tables[join_table_name]
        joined_rows = []

        left_col = join_clause.left_col
        right_col = join_clause.right_col

        for left_row in base_data['rows']:
            # Create qualified version of left row
            left_qualified = {}
            for col, val in left_row.items():
                left_qualified[f"{base_data['columns']}" if False else f"{self._find_table_for_column(col)}.{col}"] = val

            for right_row in join_data['rows']:
                # Get left value
                left_val = self._get_qualified_value(left_row, left_col, base_data['columns'],
                                                     self._find_table_for_column(left_col.name,
                                                                                 [base_data]))
                right_val = self._get_qualified_value(right_row, right_col, join_data['columns'],
                                                      join_table_name)

                if compare_values(left_val, right_val, '='):
                    combined = {}
                    # Add all columns from base table qualified
                    for col in base_data['columns']:
                        key = f"{self._get_table_name_for(base_data, left_row) if False else self._find_table_for_columns(col, [base_data])}.{col}"
                        # Actually, use the from_table name
                        key = f"{self._find_table_for_columns(col, [base_data])}.{col}"
                        combined[key] = left_row.get(col, '')

                    # Add all columns from join table qualified
                    for col in join_data['columns']:
                        key = f"{join_table_name}.{col}"
                        combined[key] = right_row.get(col, '')

                    joined_rows.append(combined)

        return joined_rows

    def _find_table_for_columns(self, col_name, table_list):
        """Find which table a column belongs to (list of table names)."""
        for table_name, table_data in self.tables.items():
            if col_name in table_data['columns']:
                if table_name in [t if isinstance(t, str) else t for t in
                                  [table_list[0] if table_list else '']]:
                    return table_name
        # Default: return first table
        if table_list:
            return table_list[0] if isinstance(table_list[0], str) else str(table_list[0])
        return ''

    def _find_table_for_column(self, col_name, table_data_list=None):
        """Find table for an unqualified column."""
        if table_data_list is None:
            for tname, tdata in self.tables.items():
                if col_name in tdata['columns']:
                    return tname
        return ''

    def _get_table_name_for(self, table_data, row=None):
        """Get table name from table data."""
        for tname, tdata in self.tables.items():
            if tdata is table_data:
                return tname
        return ''

    def _get_qualified_value(self, row, col_ref, columns, table_name):
        """Get value for a column reference."""
        if col_ref.table:
            key = f"{col_ref.table}.{col_ref.name}"
            return row.get(key, row.get(col_ref.name, ''))
        else:
            # Unqualified - look in row and in the table's columns
            if col_ref.name in row:
                return row[col_ref.name]
            key = f"{table_name}.{col_ref.name}"
            if key in row:
                return row[key]
            return ''

    def _do_group_by(self, rows, stmt):
        """Perform GROUP BY and compute aggregates."""
        group_cols = stmt.group_by
        groups = {}

        for row in rows:
            # Build group key
            key_parts = []
            for col_ref in group_cols:
                val = resolve_column_value(col_ref, row, self.tables)
                key_parts.append(str(val))
            group_key = tuple(key_parts)

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(row)

        result_rows = []
        for group_key, group_rows in groups.items():
            result_row = {}

            # Add grouping column values
            for i, col_ref in enumerate(group_cols):
                val = resolve_column_value(col_ref, group_rows[0], self.tables)
                # Store with the column name (qualified or not)
                if col_ref.table:
                    key = f"{col_ref.table}.{col_ref.name}"
                else:
                    key = col_ref.name
                result_row[key] = val

            # Compute aggregates
            for item in stmt.select_items:
                if isinstance(item, AggregateCall):
                    agg_name = item.func_name
                    arg = item.arg
                    agg_key = self._make_aggregate_key(item)

                    if isinstance(arg, Star):
                        if agg_name == 'COUNT':
                            result_row[agg_key] = len(group_rows)
                    elif isinstance(arg, ColumnRef):
                        values = []
                        for row in group_rows:
                            v = resolve_column_value(arg, row, self.tables)
                            values.append(v)

                        if agg_name == 'COUNT':
                            result_row[agg_key] = len(values)
                        elif agg_name == 'SUM':
                            result_row[agg_key] = self._agg_sum(values)
                        elif agg_name == 'AVG':
                            result_row[agg_key] = self._agg_avg(values)
                        elif agg_name == 'MIN':
                            result_row[agg_key] = self._agg_min(values)
                        elif agg_name == 'MAX':
                            result_row[agg_key] = self._agg_max(values)

            result_rows.append(result_row)

        return result_rows

    def _make_aggregate_key(self, agg_call):
        """Create a unique key for an aggregate result."""
        if isinstance(agg_call.arg, Star):
            return f"{agg_call.func_name}(*)"
        elif agg_call.arg.table:
            return f"{agg_call.func_name}({agg_call.arg.table}.{agg_call.arg.name})"
        else:
            return f"{agg_call.func_name}({agg_call.arg.name})"

    def _agg_sum(self, values):
        total = 0.0
        for v in values:
            n = try_numeric(v)
            if isinstance(n, (int, float)):
                total += n
        return total

    def _agg_avg(self, values):
        total = 0.0
        count = 0
        for v in values:
            n = try_numeric(v)
            if isinstance(n, (int, float)):
                total += n
                count += 1
        if count == 0:
            return 0.0
        return total / count

    def _agg_min(self, values):
        numeric_vals = []
        for v in values:
            n = try_numeric(v)
            if isinstance(n, (int, float)):
                numeric_vals.append(n)

        if numeric_vals:
            return min(numeric_vals)
        # String comparison
        str_vals = [str(v) for v in values if v != '']
        if str_vals:
            return min(str_vals)
        return ''

    def _agg_max(self, values):
        numeric_vals = []
        for v in values:
            n = try_numeric(v)
            if isinstance(n, (int, float)):
                numeric_vals.append(n)

        if numeric_vals:
            return max(numeric_vals)
        str_vals = [str(v) for v in values if v != '']
        if str_vals:
            return max(str_vals)
        return ''

    def _project_select_items(self, stmt, rows, join_info=None):
        """Determine output columns and project rows based on select items."""
        if not rows:
            return ([], [])

        has_star = any(isinstance(item, Star) for item in stmt.select_items)
        has_qualified_star = any(
            isinstance(item, ColumnRef) and item.name == '*'
            for item in stmt.select_items
        )

        if has_star:
            # Select all columns from the first row's keys
            columns = list(rows[0].keys())
            projected = rows
            return (columns, projected)

        if has_qualified_star:
            # Find the qualified star
            for item in stmt.select_items:
                if isinstance(item, ColumnRef) and item.name == '*':
                    prefix = item.table + '.'
                    columns = [k for k in rows[0].keys() if k.startswith(prefix)]
                    projected = []
                    for row in rows:
                        proj_row = {k: row.get(k, '') for k in columns}
                        projected.append(proj_row)
                    return (columns, projected)

        # Explicit column/aggregate list
        columns = []
        for item in stmt.select_items:
            if isinstance(item, ColumnRef):
                if item.table:
                    columns.append(f"{item.table}.{item.name}")
                else:
                    # Resolve unqualified name
                    resolved = self._resolve_unqualified_col(item.name, rows, join_info)
                    columns.append(resolved)
            elif isinstance(item, AggregateCall):
                columns.append(self._make_aggregate_key(item))

        # Now project
        projected = []
        for row in rows:
            proj_row = {}
            for i, item in enumerate(stmt.select_items):
                col_name = columns[i]
                if isinstance(item, ColumnRef):
                    val = resolve_column_value(item, row, self.tables)
                    proj_row[col_name] = val
                elif isinstance(item, AggregateCall):
                    proj_row[col_name] = row.get(col_name, '')
            projected.append(proj_row)

        return (columns, projected)

    def _resolve_unqualified_col(self, name, rows, join_info):
        """Resolve an unqualified column name to its qualified form."""
        if not rows:
            return name

        first_row = rows[0]
        # Check if name exists unqualified
        if name in first_row:
            return name

        # Look for qualified matches
        matches = []
        for key in first_row.keys():
            if '.' in key and key.split('.', 1)[1] == name:
                matches.append(key)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            raise ExecutionError(f"Ambiguous column reference: {name}")
        return name

    def _do_order_by(self, rows, order_items):
        """Sort rows by order items."""

        def sort_key(row):
            keys = []
            for item in order_items:
                val = resolve_column_value(item.column_ref, row, self.tables)
                n = try_numeric(val)
                # For sorting, use numeric if possible
                if isinstance(n, (int, float)):
                    keys.append((0, n, ''))
                else:
                    keys.append((1, 0, str(val)))
                # Reverse for DESC
                if item.direction == 'DESC':
                    # We'll handle direction in the sort
                    pass
            return keys

        # Python's sort is stable, so we can sort by each key in reverse order
        # Or compute a composite key with negation for DESC
        def composite_key(row):
            parts = []
            for item in order_items:
                val = resolve_column_value(item.column_ref, row, self.tables)
                n = try_numeric(val)
                if isinstance(n, (int, float)):
                    v = n
                    is_str = False
                else:
                    v = str(val)
                    is_str = True

                if item.direction == 'DESC':
                    # For numeric, negate; for string, use tricky reverse
                    if not is_str:
                        parts.append((0, -v, ''))
                    else:
                        # We can't easily negate strings, so handle differently
                        parts.append((1, 0, _reverse_string_for_sort(v)))
                else:
                    if not is_str:
                        parts.append((0, v, ''))
                    else:
                        parts.append((0, 0, v))
            return parts

        rows.sort(key=composite_key)


def _reverse_string_for_sort(s):
    """Create a sortable representation for descending string order."""
    # Map each character to its inverse for sorting
    return ''.join(chr(255 - ord(c)) if ord(c) < 256 else chr(65535 - ord(c)) for c in s)
