# Implementation Plan: SQL Query Engine in Python (Standard Library Only) – Revised & Bug‑Fixed

This revised plan incorporates **all review feedback**: complete rewrite of INNER JOIN qualification, correct aggregate execution without GROUP BY, mandatory error for ambiguous non‑aggregate columns, removal of dead code/unused imports, and line‑length compliance. The plan is now extremely detailed so that the implementation cannot misinterpret the required behaviour.

---

## 1. Files & Responsibilities (unchanged)

| File | Purpose |
|------|---------|
| `sql_engine.py` | Main entry point: REPL loop, command dispatch. |
| `lexer.py` | Tokenizer – converts raw SQL text into a token stream with position info. |
| `parser.py` | Recursive‑descent parser – builds AST; raises `ParseError` on syntax errors. |
| `ast_nodes.py` | Simple data‑classes for AST nodes (Select, Insert, Load, Save, conditions, etc.). |
| `executor.py` | Core executor – maintains in‑memory tables, executes all statements. |
| `formatter.py` | Takes a result set (list of dicts, column order) and returns formatted ASCII table. |
| `samples/` | Contains `users.csv`, `orders.csv`, `example_queries.txt`. Generated automatically. |

---

## 2. Architecture & Data Flow (clarified)

```
User Input → REPL → Lexer → Parser → AST
                                  ↓
                            Executor (DB State)
                                  ↓
                   Result Set (list of dicts, column order)
                                  ↓
                            Formatter → Console
```

- **DB State**: each table is a dict `{"columns": [...], "rows": [ {"col": val, ...}, ...]}`.  
  Row keys are **unqualified column names** as read from CSV headers.  
- **JOIN path**: before joining, **every row’s keys** are prefixed with `<table_name>.` (or an alias if specified).  
  During the entire join pipeline (ON evaluation, subsequent WHERE/GROUP BY/ORDER BY, projection) **only qualified keys** exist.  
  Unqualified references are resolved **after** the join result is built by suffix matching (must be unambiguous).  
- **No join**: rows remain unqualified throughout.  
- **Aggregates without GROUP BY**: all filtered rows become **one group**; the result has exactly one row.  
- **GROUP BY**: rows partitioned by the grouping columns; each group produces one output row containing those grouping columns (first value encountered) and the requested aggregates.  
  Any non‑aggregate column not in the GROUP BY list must raise an `ExecutionError`.

---

## 3. Implementation Order (updated with critical focus)

1. **Project scaffolding** – Files, basic module interfaces.  
2. **Lexer** – Token definitions, scanning logic, position tracking.  
3. **Parser** – Build AST for all statement types, error handling with position.  
4. **Executor: LOAD/SAVE/INSERT** – Table storage and persistence.  
5. **SELECT basics** – FROM single table, column projection (`*` and explicit names).  
6. **WHERE, AND/OR, comparisons** – Filtering with type coercion.  
7. **ORDER BY, LIMIT** – Sorting (unified sort keys) and row slicing.  
8. **Aggregate functions + GROUP BY** – **Implement correctly** (see Section 5.1).  
9. **INNER JOIN** – **Implement correctly** (see Section 5.2).  
10. **Formatter** – ASCII table output, display qualified column names when present.  
11. **REPL integration** – Multi‑line input, error display.  
12. **Sample data & queries** – Generate CSV files and example queries.  
13. **Polishing & Clean‑up** – Remove unused imports, dead code, fix line lengths, flake8 compliance (see Section 5.3).

---

## 4. Libraries

- `csv`, `re`, `itertools` (groupby is acceptable) – no external packages.

---

## 5. Detailed Feature Implementation – Critical Fixes Only

The following subsections describe exactly how the broken features must be realised. Code that is already working (LOAD, SAVE, INSERT, simple SELECT, WHERE, ORDER BY, LIMIT) is not repeated.

### 5.1 Aggregate Functions (COUNT, SUM, AVG, MIN, MAX)

The executor must implement `execute_select` with a clear **three‑phase check**:

#### 5.1.1 Detection of aggregates and non‑aggregate columns
```python
# In execute_select, after FROM and WHERE processing, before grouping:
has_aggregate = any(isinstance(sel, Aggregate) for sel in planar_select_items)
plain_columns = [
    sel for sel in planar_select_items
    if isinstance(sel, ColumnRef) and not sel.inside_aggregate
]
group_cols = stmt.group_by or []   # list of ColumnRef
```

#### 5.1.2 Single‑group mode (no GROUP BY clause)
If `has_aggregate` is `True` **and** `not group_cols`:
- **If `plain_columns` is not empty**, raise an `ExecutionError`:
  `column "colname" must appear in the GROUP BY clause or be used in an aggregate function`
- Treat **all filtered rows** as one group → `groups = [filtered_rows]`.

#### 5.1.3 Multi‑group mode (GROUP BY provided)
- Partition `filtered_rows` by the values of the grouping columns.
- Use a dictionary keyed by a tuple of group values; each group is a list of rows.
- **Validate that every `plain_columns` element appears in `group_cols`**; if not, raise `ExecutionError` with the same message as above.

#### 5.1.4 Aggregate computation (for each group)
For each group:
- Build one output row containing:
  - For each grouping column → the first row’s value for that column.
  - For each aggregate item → computed value.
- Aggregate logic:
  - `COUNT(*)` → `len(group)`
  - `COUNT(col)` → number of rows where `col` is not empty string and not None (after qualification).
  - `SUM(col)` → sum of numeric values (skip rows where conversion fails); if none, result `None`.
  - `AVG(col)` → average of numeric values; if none, result `None`.
  - `MIN(col)`, `MAX(col)` → use numeric comparison if possible, else string comparison; treat missing values as skip (do not include them in comparison); if no valid values, result `None`.

**Important**: The grouping and aggregate computation must be **called even if `stmt.group_by` is None**, because the single‑group case still needs aggregates.

#### 5.1.5 Aggregates with JOIN
All column resolution during aggregation uses the **qualified keys** that exist after a join (see Section 5.2). The same validation applies.

---

### 5.2 INNER JOIN (Complete Rewrite)

The goal is to produce a result containing rows whose keys are **qualified with the source table name** (or alias). The approach must be **simple, predictable, and free of ambiguous resolution helpers**.

#### 5.2.1 Joining algorithm step‑by‑step

1. **Obtain left and right tables**
   - `left_table` = the table in the FROM clause.
   - `right_table` = the table in the JOIN clause.
   - Aliases default to the table name.

2. **Qualify every row in both tables**
   - For left table: create a new list of dicts `qualified_left` where each key is `f"{left_alias}.{col}"`.
   - For right table: same for `qualified_right`.

3. **Nested‑loop join with ON condition**
   ```python
   joined = []
   for lrow in qualified_left:
       for rrow in qualified_right:
           merged = {**lrow, **rrow}
           if eval_condition(on_cond, merged):
               joined.append(merged)
   ```
   - `eval_condition` is the same function used for WHERE; it resolves column references directly from the merged dict’s keys. Since all keys are qualified, ON clauses using `table.col` work perfectly.

4. **Post‑join column resolution (for SELECT, WHERE, ORDER BY, GROUP BY)**
   - After the join, all row dictionaries contain keys like `"users.id"`, `"orders.amount"`.
   - **Unqualified references** (e.g., `SELECT name`) are resolved by searching the keys of the first joined row:
     - Find all keys that end with `.name`.
     - If exactly one match, use that qualified key.
     - If zero matches, raise `ExecutionError: column 'name' not found`.
     - If multiple matches, raise `ExecutionError: ambiguous column 'name'`.
   - This resolution **must be applied consistently** to all column‑reference nodes in SELECT items, WHERE conditions, ORDER BY items, and GROUP BY columns.
   - `SELECT *` → expand to all qualified keys, sorted alphabetically.

5. **What to delete**
   - Remove any helper functions like `_find_table_for_column`, `_get_qualified_value`, `_resolve_column_ambiguity`, etc. They are no longer needed and are a source of bugs.
   - Remove any code that tries to build joined rows without qualification. The **only** path is the one described above.

6. **Display**
   The formatter will show the qualified column headers (e.g., `users.name`). This is correct and clarifies the data source.

#### 5.2.2 Example flow
Given:
```sql
SELECT users.name, orders.amount FROM users
INNER JOIN orders ON users.id = orders.user_id
```
Tables:
- `users` : columns `id`, `name`
- `orders`: columns `order_id`, `user_id`, `amount`

After qualification:
- left row: `{"users.id":1, "users.name":"Alice"}`
- right row: `{"orders.order_id":101, "orders.user_id":1, "orders.amount":50}`

Merged: `{"users.id":1, "users.name":"Alice", "orders.order_id":101, "orders.user_id":1, "orders.amount":50}`

ON condition: `users.id = orders.user_id` → exact key match → true.

SELECT items resolve `users.name` and `orders.amount` directly.

Result includes named keys; formatter shows `users.name | orders.amount`.

---

### 5.3 Clean‑up of Dead Code, Unused Imports, and Style

During the final polishing phase, the following **specific** items must be addressed:

#### 5.3.1 Unused imports removal
- **`parser.py`**: remove `from lexer import Token` if `Token` is not used directly (likely it’s only used inside lexer, parser may use token type names but not the class).
- **`executor.py`**: remove `from ast_nodes import OrderItem, JoinClause` if they are never instantiated or referenced.
- **`sql_engine.py`**: remove `import sys`, `import os` if they are indeed unused.

#### 5.3.2 Dead local variables
- In `parser.py` method `parse_select_item`, delete the line `saved_pos = self.pos` if it is never used.

#### 5.3.3 Line length violations
- In `executor.py`, lines 249 and 263 (or wherever they end up) exceed 120 characters. Break them logically, e.g., split long list comprehensions or condition chains.

#### 5.3.4 Code style
- Prefer explicit `if/else` over confusing ternary expressions.
- Ensure all public methods have a docstring.
- Run `flake8` on the final codebase and resolve all issues.

#### 5.3.5 Verification
After implementing all fixes, run the full set of example queries from `samples/example_queries.txt` and verify that every feature works:
- INNER JOIN produces correct, qualified rows.
- Aggregates without GROUP BY return a single row with proper values.
- Non‑aggregate column in aggregate‑without‑GROUP‑BY query raises an error.
- Non‑aggregate column missing from GROUP BY in a grouped query raises an error.
- No unused imports or flake8 warnings remain.

---

## 6. Verification Against Review Feedback (updated)

| Issue | Resolution |
|-------|------------|
| INNER JOIN completely broken | Rewritten with mandatory column qualification; all helper removal explicit. |
| Aggregates without GROUP BY return empty | Single‑group fallback must be called; explicit error for non‑aggregate columns added. |
| Missing error for non‑aggregate column | Validation step inserted in both single‑group and multi‑group modes. |
| Unused imports / dead code | Detailed list of exact removals provided. |
| Line length violations | Specific locations flagged for refactoring. |
| `_find_table_for_columns` / other helpers | Explicitly stated to be deleted; only qualified key resolution allowed. |
| Testing | Requirement to run all example queries before finalising. |

---

This revised plan provides **unambiguous, step‑by‑step instructions** for the three critical problem areas. By following it exactly, the implementation will pass all tests and meet the original specification without bugs.