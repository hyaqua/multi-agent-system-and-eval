"""
Query executor for the SQL engine.
Takes AST nodes from the parser and executes them against stored tables.
"""

from typing import List, Dict, Any, Optional, Union

from parser import (
    SelectStmt, InsertStmt, LoadStmt, SaveStmt,
    ColumnRef, StarSelect, AggregateCall, Literal,
    Comparison, BinaryOp, OrderExpr, JoinClause, Statement,
)
from storage import Storage


class ExecutorError(Exception):
    """Raised when query execution encounters a problem."""
    pass


class Executor:
    """Executes parsed SQL statements against the storage layer."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def execute(self, stmt: Statement) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a parsed statement.
        Returns a list of rows for SELECT, or None for other statements.
        """
        if isinstance(stmt, SelectStmt):
            return self._execute_select(stmt)
        elif isinstance(stmt, InsertStmt):
            self._execute_insert(stmt)
            return None
        elif isinstance(stmt, LoadStmt):
            self._execute_load(stmt)
            return None
        elif isinstance(stmt, SaveStmt):
            self._execute_save(stmt)
            return None
        else:
            raise ExecutorError(f"Unknown statement type: {type(stmt).__name__}")

    # ── LOAD / SAVE / INSERT ──────────────────

    def _execute_load(self, stmt: LoadStmt):
        self.storage.load_csv(stmt.table, stmt.filename)

    def _execute_save(self, stmt: SaveStmt):
        self.storage.save_csv(stmt.table, stmt.filename)

    def _execute_insert(self, stmt: InsertStmt):
        self.storage.insert_row(stmt.table, stmt.values)

    # ── SELECT ────────────────────────────────

    def _execute_select(self, stmt: SelectStmt) -> List[Dict[str, Any]]:
        """Execute a full SELECT statement."""
        # Load the base table
        rows = self.storage.get_table(stmt.table)
        columns = self.storage.get_columns(stmt.table)

        # Track which columns belong to which table (needed for JOIN resolution)
        table_columns: Dict[str, List[str]] = {stmt.table: list(columns)}

        # ── JOINs ────────────────────────────
        for join in stmt.joins:
            rows, table_columns = self._apply_join(rows, stmt.table, table_columns, join)

        # ── WHERE ────────────────────────────
        if stmt.where is not None:
            rows = [
                row for row in rows
                if self._eval_condition(row, stmt.where, stmt.table, table_columns)
            ]

        # ── Aggregation / GROUP BY ──────────
        has_aggregates = any(isinstance(c, AggregateCall) for c in stmt.columns)

        if stmt.group_by or has_aggregates:
            rows = self._execute_aggregation(rows, stmt, table_columns)

            # ORDER BY and LIMIT after aggregation
            if stmt.order_by:
                rows = self._apply_order_by(rows, stmt.order_by)
            if stmt.limit is not None:
                rows = rows[:stmt.limit]
            return rows

        # ── Project columns ─────────────────
        result = self._project_columns(rows, stmt.columns, stmt.table, table_columns)

        # ── ORDER BY ────────────────────────
        if stmt.order_by:
            result = self._apply_order_by(result, stmt.order_by)

        # ── LIMIT ───────────────────────────
        if stmt.limit is not None:
            result = result[:stmt.limit]

        return result

    # ── JOIN ──────────────────────────────────

    def _apply_join(
        self,
        rows: List[Dict[str, Any]],
        base_table: str,
        table_columns: Dict[str, List[str]],
        join: JoinClause,
    ) -> tuple:
        """Perform an INNER JOIN, returning (new_rows, updated_table_columns)."""
        join_table = join.table
        join_rows = self.storage.get_table(join_table)
        join_cols = self.storage.get_columns(join_table)
        table_columns[join_table] = list(join_cols)

        new_rows = []
        for left_row in rows:
            left_val = self._resolve_column(left_row, join.left_col, base_table, table_columns)
            for right_row in join_rows:
                right_val = self._resolve_column(right_row, join.right_col, join_table, table_columns)
                if left_val == right_val:
                    merged = {}
                    # Prefix columns with table name to avoid ambiguity
                    for col in table_columns[base_table]:
                        key = f"{base_table}.{col}"
                        merged[key] = self._resolve_column(
                            left_row, ColumnRef(col, base_table), base_table, table_columns
                        )
                    for t in list(table_columns.keys()):
                        if t == base_table:
                            continue
                        for col in table_columns[t]:
                            key = f"{t}.{col}"
                            # Value comes from the appropriate row
                            if t == join_table:
                                merged[key] = self._resolve_column(
                                    right_row, ColumnRef(col, join_table), join_table, table_columns
                                )
                            # (Other tables already in left_row should be preserved)
                            elif key in left_row:
                                merged[key] = left_row[key]
                    new_rows.append(merged)

        # Update column list for the result
        return new_rows, table_columns

    # ── COLUMN RESOLUTION ────────────────────

    def _resolve_column(
        self,
        row: Dict[str, Any],
        col_ref: ColumnRef,
        default_table: str,
        table_columns: Dict[str, List[str]],
    ) -> Any:
        """
        Resolve a column reference to its value in a row.
        Handles table-qualified (table.col) and unqualified references.
        """
        if col_ref.table is not None:
            # Explicit table.col
            key = f"{col_ref.table}.{col_ref.name}"
            if key in row:
                return row[key]
            # If no table prefix in row (uncommon after JOIN), try bare name
            if col_ref.name in row:
                return row[col_ref.name]
            raise ExecutorError(
                f"Column '{col_ref.table}.{col_ref.name}' not found in row"
            )
        else:
            # Unqualified column name
            if col_ref.name in row:
                return row[col_ref.name]
            # Search all tables for prefixed version
            for t_name in table_columns:
                key = f"{t_name}.{col_ref.name}"
                if key in row:
                    return row[key]
            # Try default table prefix
            if default_table:
                key = f"{default_table}.{col_ref.name}"
                if key in row:
                    return row[key]
            raise ExecutorError(
                f"Column '{col_ref.name}' not found. Available columns: {list(row.keys())}"
            )

    # ── WHERE CONDITION EVALUATION ───────────

    def _eval_condition(
        self,
        row: Dict[str, Any],
        condition: Union[Comparison, BinaryOp],
        default_table: str,
        table_columns: Dict[str, List[str]],
    ) -> bool:
        """Evaluate a WHERE condition against a single row."""
        if isinstance(condition, Comparison):
            left_val = self._resolve_column(row, condition.left, default_table, table_columns)
            right_val = condition.right.value
            op = condition.op

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
                else:
                    raise ExecutorError(f"Unknown comparison operator: {op}")
            except TypeError:
                # If types are incomparable (e.g. string < int), treat as False
                return False

        elif isinstance(condition, BinaryOp):
            left_result = self._eval_condition(row, condition.left, default_table, table_columns)
            right_result = self._eval_condition(row, condition.right, default_table, table_columns)
            if condition.op == 'AND':
                return left_result and right_result
            elif condition.op == 'OR':
                return left_result or right_result
            else:
                raise ExecutorError(f"Unknown logical operator: {condition.op}")

        else:
            raise ExecutorError(f"Unknown condition type: {type(condition).__name__}")

    # ── PROJECTION ───────────────────────────

    def _project_columns(
        self,
        rows: List[Dict[str, Any]],
        select_cols: List[Union[StarSelect, ColumnRef, AggregateCall]],
        default_table: str,
        table_columns: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        """Project rows down to the selected columns."""
        # SELECT * → return all columns as-is
        if any(isinstance(c, StarSelect) for c in select_cols):
            return rows

        result = []
        for row in rows:
            new_row = {}
            for col in select_cols:
                if isinstance(col, ColumnRef):
                    val = self._resolve_column(row, col, default_table, table_columns)
                    new_row[col.name] = val
                elif isinstance(col, AggregateCall):
                    pass  # Aggregates are handled in _execute_aggregation
            result.append(new_row)
        return result

    # ── AGGREGATION / GROUP BY ───────────────

    def _execute_aggregation(
        self,
        rows: List[Dict[str, Any]],
        stmt: SelectStmt,
        table_columns: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        """
        Execute GROUP BY and/or aggregate functions.
        If no GROUP BY but there are aggregates, treat all rows as one group.
        """
        # Partition rows into groups
        if stmt.group_by:
            groups: Dict[tuple, List[Dict]] = {}
            group_keys: List[tuple] = []
            for row in rows:
                key = tuple(
                    self._resolve_column(row, gb_col, stmt.table, table_columns)
                    for gb_col in stmt.group_by
                )
                if key not in groups:
                    groups[key] = []
                    group_keys.append(key)
                groups[key].append(row)
        else:
            # One group containing all rows
            groups = {(): rows}
            group_keys = [()]

        # Compute result for each group
        result = []
        for gk in group_keys:
            group_rows = groups[gk]
            new_row: Dict[str, Any] = {}

            # Add GROUP BY columns to output
            if stmt.group_by:
                for gb_col, val in zip(stmt.group_by, gk):
                    new_row[gb_col.name] = val

            # Compute each selected column
            for col in stmt.columns:
                if isinstance(col, ColumnRef):
                    # Non-aggregate column: take value from first row in group
                    val = self._resolve_column(group_rows[0], col, stmt.table, table_columns)
                    new_row[col.name] = val

                elif isinstance(col, AggregateCall):
                    func = col.func
                    if isinstance(col.arg, str) and col.arg == '*':
                        agg_col = None
                    else:
                        agg_col = col.arg  # ColumnRef

                    display = col.display_name

                    if func == 'COUNT':
                        if agg_col is None:
                            new_row[display] = len(group_rows)
                        else:
                            vals = [
                                self._resolve_column(r, agg_col, stmt.table, table_columns)
                                for r in group_rows
                            ]
                            new_row[display] = sum(1 for v in vals if v is not None)

                    elif func == 'SUM':
                        vals = [
                            self._resolve_column(r, agg_col, stmt.table, table_columns)
                            for r in group_rows
                        ]
                        numeric_vals = [v for v in vals if v is not None and isinstance(v, (int, float))]
                        new_row[display] = sum(numeric_vals) if numeric_vals else 0

                    elif func == 'AVG':
                        vals = [
                            self._resolve_column(r, agg_col, stmt.table, table_columns)
                            for r in group_rows
                        ]
                        numeric_vals = [v for v in vals if v is not None and isinstance(v, (int, float))]
                        new_row[display] = sum(numeric_vals) / len(numeric_vals) if numeric_vals else 0

                    elif func == 'MIN':
                        vals = [
                            self._resolve_column(r, agg_col, stmt.table, table_columns)
                            for r in group_rows
                        ]
                        clean = [v for v in vals if v is not None]
                        new_row[display] = min(clean) if clean else None

                    elif func == 'MAX':
                        vals = [
                            self._resolve_column(r, agg_col, stmt.table, table_columns)
                            for r in group_rows
                        ]
                        clean = [v for v in vals if v is not None]
                        new_row[display] = max(clean) if clean else None

                elif isinstance(col, StarSelect):
                    # SELECT * with GROUP BY doesn't make sense; skip
                    pass

            result.append(new_row)

        return result

    # ── ORDER BY ─────────────────────────────

    def _apply_order_by(
        self,
        rows: List[Dict[str, Any]],
        order_by: List[OrderExpr],
    ) -> List[Dict[str, Any]]:
        """Sort rows by the given ORDER BY expressions."""
        # Apply sort keys in reverse order (stable sort preserves earlier sorts)
        for ob in reversed(order_by):
            col_name = ob.column.name
            reverse = (ob.direction == 'DESC')

            def sort_key(r):
                val = r.get(col_name)
                # None values sort last regardless of direction
                return (val is None, val if val is not None else '')

            try:
                rows = sorted(rows, key=sort_key, reverse=reverse)
            except TypeError:
                # If mixed types, convert to string
                rows = sorted(
                    rows,
                    key=lambda r, cn=col_name: (
                        r.get(cn) is None,
                        str(r.get(cn)) if r.get(cn) is not None else ''
                    ),
                    reverse=reverse,
                )
        return rows
