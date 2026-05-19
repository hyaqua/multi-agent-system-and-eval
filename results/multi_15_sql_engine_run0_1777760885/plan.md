# Final Revised Implementation Plan: SQL Engine in Python

## Project Overview
A REPL-based SQL query engine that reads CSV files as tables. It uses a custom lexer/parser to support a subset of SQL, executes queries on in‑memory tables, and outputs results as a formatted ASCII table. No external libraries – only Python standard library.

---

## 1. Files to Create and Their Purposes

| File               | Purpose                                                                                   |
|--------------------|-------------------------------------------------------------------------------------------|
| `main.py`          | Entry point, REPL loop, command dispatch (LOAD, SAVE, SQL).                               |
| `lexer.py`         | Tokenizes input string into tokens. Tracks position for error reporting.                  |
| `parser.py`        | Parses token stream into AST (Select, Insert, Load, Save). Builds syntax tree nodes.      |
| `executor.py`      | Executes AST nodes. Maintains table store, handles queries, JOINs, aggregation, INSERT.   |
| `table.py`         | `Table` class: loads/saves CSV, stores columns and rows, provides basic access methods.   |
| `formatter.py`     | Formats query results as an ASCII table with aligned columns.                             |
| `error.py`         | Custom `SQLError` with position, used for syntax/semantic errors.                         |
| `samples/`         | Directory containing example CSV files: `users.csv`, `orders.csv`, and `queries.txt`.    |
| `README.md`        | Brief usage instructions.                                                                 |
| `tests/`           | (Optional) Automated test script that runs queries from `queries.txt` and validates outputs. |

---

## 2. Architecture

### Module Interactions
```
User Input (terminal)
        │
        ▼
   main.py (REPL)
        │
        ├─── If command is LOAD/SAVE → executor.py
        │
        └─── Otherwise:
                │
                ├── lexer.tokenize(input) → tokens
                │
                └── parser.parse(tokens)  → AST
                        │
                        ▼
                  executor.execute(ast)  → result rows
                        │
                        ▼
                  formatter.format(result) → display
```

- **Lexer**: Converts raw input to a list of tokens with type, value, and position.
- **Parser**: Recursive descent. Converts token list into AST nodes:
  - `SelectStatement` (columns, table source, where, order_by, limit, group_by)
  - `InsertStatement` (table, values)
  - `LoadCommand` (table name, file path)
  - `SaveCommand` (table name, file path)
- **Table**: In‑memory structure. Columns as list of strings; rows as list of dicts (column→value). All values stored as strings. Helper methods: `load_csv(path)`, `save_csv(path)`, `append_row(dict)`.
- **Executor**: Holds a dict `tables: dict[str, Table]`. Implements:
  - `execute_select(ast)` → returns list of dicts (result rows) with correct columns.
    Internally: scans table(s), applies WHERE filtering, ORDER BY, LIMIT, GROUP BY, aggregation.
  - `execute_insert(ast)` → appends row.
  - `execute_load(ast)` → loads CSV, stores table.
  - `execute_save(ast)` → saves table to CSV.
- **Formatter**: Takes list of dicts + column order, computes column widths, prints ASCII border, left‑aligns all cells (or right‑align numbers if desired). Uses `str()` on values.

### Data Flow for a SELECT
1. Identify source: if not a join → one `Table` object; if `INNER JOIN` → create a joined temporary table (list of dicts) using nested loop on ON equality.
2. Apply WHERE clause: filter rows by evaluating condition tree (comparison operators, AND/OR). Use a recursive evaluator.
3. If GROUP BY present: group rows by the grouped columns; for each group compute aggregate functions on other columns.
   - **Critical fix:** Output column order must match the exact order of expressions in the `SELECT` clause. The executor must iterate over `ast.columns` and, for each column expression, decide if it’s a group column or an aggregate, building each output row in that same sequence. (See Section 5.7 for detailed correction.)
4. Apply ORDER BY (after grouping) using Python’s `sorted` with custom keys.
5. Apply LIMIT: slice rows.
6. Select columns: for each row produce a dict with only requested columns (including aliases if needed), preserving the order given in the `SELECT` list.

---

## 3. Implementation Order

1. **`table.py`** – `Table` class: `__init__`, `load_csv`, `save_csv`, `rows` property, column names.
   - Test with manual script.
2. **`error.py`** – `SQLError` with message and optional position.
3. **`lexer.py`** – Tokenizer with basic tokens (keywords, identifiers, strings, numbers, operators, punctuation). Key: handle quoted strings, numbers.
4. **`parser.py`** – Minimal initial parser for `LOAD`, `SAVE`, `SELECT * FROM table`, `INSERT INTO`.
5. **`executor.py`** – Basic executors for the above.
6. **`formatter.py`** – ASCII table formatter.
7. **`main.py`** – REPL loop integrating lexer, parser, executor, formatter. Basic error display.
8. **Add features incrementally**:
   - WHERE clause (comparisons, AND/OR) → extend lexer, parser, executor.
   - ORDER BY → add to parser and executor.
   - LIMIT.
   - Aggregate functions (COUNT, SUM, AVG, MIN, MAX) without GROUP BY.
   - GROUP BY with aggregates – implement according to the **corrected specification in Section 5.7**.
   - INNER JOIN support.
   - INSERT fully.
   - SAVE command.
9. **Bug fix: GROUP BY output column order** – Refactor `_apply_group_by` to build result columns and each group’s row in the exact order of `ast.columns` (see Section 5.7). This step is essential to pass the mandatory test query `SELECT SUM(age), city FROM users GROUP BY city`.
10. **Sample files** – Create `samples/orders.csv` and `samples/queries.txt` with the content defined in Section 5.12. Verify all features work by running the queries, especially the GROUP BY ordering.
11. **Polish**: Error messages with position, handling edge cases (e.g., division by zero in AVG, type mismatches), operator precedence, parentheses in expressions.
12. **Testing** (optional but recommended): Create a script in `tests/` that loads the sample CSVs and runs all queries from `queries.txt`, comparing outputs against expected results to validate end‑to‑end correctness.

---

## 4. Libraries Used
- `csv` (standard library) – for reading/writing CSV.
- `re` – for lexer token patterns.
- `math` – not needed; all calculations in Python.
- All other modules (`sys`, `os`) are standard.

---

## 5. Feature Implementation Details

### 5.1 LOAD and SAVE Commands
- **Lexer**: Tokens `LOAD`, `SAVE`, `FROM`, identifiers, strings for filenames.
- **Parser**: Expects `LOAD table_name FROM 'path'` → produces `LoadCommand(identifier, string)`.
- **Executor**: `load` calls `Table.load_csv(filepath)`, stores in `self.tables[table_name]`. `save` calls `table.save_csv(filepath)`.

### 5.2 SELECT with Column Names / SELECT *
- **Parser**: `SELECT col1, col2 FROM table` → `SelectStatement(columns=[Column('col1'), Column('col2')], table='users')`. `SELECT *` uses special `Star()` node.
- **Executor**: Iterates rows, for each row extracts requested columns (or all if star). Creates result dict with column order.

### 5.3 WHERE Clause
- **Parser**: `WHERE` clause parsed as conjunction of conditions. Supports operators `=`, `!=`, `<`, `>`, `<=`, `>=`. Operands: column name or literal (string or number). AND/OR combine conditions into tree (`And`, `Or`). Parentheses change precedence.
- **Executor**: Recursive function `eval_condition(cond, row)`. Comparisons: attempt numeric conversion (float) for both operands; if both succeed, use numeric compare, otherwise string compare.

### 5.4 ORDER BY
- **Parser**: `ORDER BY col1 ASC, col2 DESC` → list of `(column_name, ascending)`.
- **Executor**: After filtering, sort rows with `sorted(rows, key=lambda r: ...)`. Key tuple: for each order spec, extract value (optionally cast to float if numeric). `ascending` flag determines order.

### 5.5 LIMIT
- **Parser**: `LIMIT number` → integer.
- **Executor**: Slice rows `limit` after ORDER BY.

### 5.6 Aggregate Functions (without GROUP BY)
- **Parser**: In SELECT list, function calls: `COUNT(*)`, `SUM(age)`, `AVG(salary)`, `MIN(name)`, `MAX(price)`. Valid anywhere in SELECT; mixing aggregates with non‑grouped columns without GROUP BY is an error.
- **Executor**: If no GROUP BY, run a single aggregation pass: iterate rows, collect values per aggregate function, compute final result. For `COUNT(*)`, just count rows. Non‑aggregated columns are omitted from result. Return one row. The output order of values follows the `SELECT` list exactly.

### 5.7 GROUP BY with Aggregates (Corrected – Bug Fix)
- **Parser**: `GROUP BY col1, col2` list of columns. Only grouped columns and aggregates allowed in SELECT.
- **Current bug**: The implementation places all group columns before all aggregate columns in the output, regardless of the order specified in the `SELECT` clause. This causes column misalignment and violates user intent (e.g., `SELECT SUM(age), city FROM users GROUP BY city` incorrectly shows city first).
- **Fix** (replaces previous logic in `_apply_group_by`):
  1. **Determine output column list** from `ast.columns` directly. Do not reorder.
  2. Group rows by the combination of all columns listed in `GROUP BY` (key = tuple of the group column values).
  3. For each group, build an output row (`out_row`) by iterating over each expression in `ast.columns`:
     - If the expression is a **plain column** (a `Column` node), that column *must* be one of the `GROUP BY` columns; take its value from the group key (the value shared by all rows in that group).
     - If the expression is an **aggregate function call** (e.g., `FunctionCall(SUM, 'amount')`), compute the aggregate value for the current group using the rows belonging to that group.
     - The key in `out_row` should be the string representation of the expression (e.g., `"age"` or `"SUM(age)"`), exactly as it appears in the `SELECT` list.
  4. Append this `out_row` to the result rows.
  5. The final projection (step 6 in data flow) can then simply use `ast.columns` as the order and extract each key from the result row dictionaries, guaranteeing alignment.
- **No assumption** is made about group columns appearing first. The output columns follow the user’s written `SELECT` list exactly.

### 5.8 INNER JOIN
- **Parser**: `table1 INNER JOIN table2 ON table1.col = table2.col` in the FROM clause. Simplified: only one join, no aliases; ON condition is an equality between two columns.
- **Executor**: Load both tables, perform nested loop: for each row in table1, for each row in table2, if `row1[col1] == row2[col2]`, create new combined row dict (prefix column names to avoid collisions, e.g., `table1.col`, `table2.col`). Set as working table for the rest of the query. Column references in WHERE/SELECT must include table qualifier; handle appropriately.

### 5.9 INSERT INTO
- **Parser**: `INSERT INTO table (col1, col2) VALUES (val1, val2)` or without column list (values in order of all columns).
- **Executor**: Build a dict, call `table.append_row(dict)`. Columns not provided get empty string.

### 5.10 Formatted ASCII Table Output
- **`formatter.py`**: Takes list of dicts and column names. Compute `max(len(str(row[col])))` for each column; also `len(col)`. Table border with `+`, `-`, `|`. Print headers, separator, rows. Left‑align all cells (pad right with spaces). Optionally detect numeric columns and right‑align those.

### 5.11 Syntax Error Messages
- **Lexer**: If unknown token, raise `SQLError("Unexpected character", pos)`.
- **Parser**: When expected token not found, raise `SQLError("Expected X but got Y", token.pos)`. Each rule catches mismatches and throws with location.
- **Main**: In REPL, catch `SQLError`, print `^` pointer below the error position using line/column.

### 5.12 Sample Files and Example Queries (Required)
The engine **must** be accompanied by the following files in the `samples/` directory:

#### `samples/orders.csv`
```csv
order_id,user_id,amount,date
1,1,100.00,2023-01-01
2,1,200.00,2023-01-02
3,2,150.00,2023-01-03
4,3,300.00,2023-01-04
```

#### `samples/queries.txt`
This file contains every supported SQL command, demonstrating all features. It can be used for manual REPL testing or for automated verification. The content is:

```sql
LOAD users FROM 'samples/users.csv';
LOAD orders FROM 'samples/orders.csv';
SELECT * FROM users;
SELECT name, age FROM users;
SELECT * FROM users WHERE age > 30;
SELECT * FROM users WHERE age > 25 AND city = 'New York';
SELECT * FROM users WHERE age < 30 OR city = 'Chicago';
SELECT * FROM users ORDER BY age DESC;
SELECT * FROM users ORDER BY city ASC, age DESC;
SELECT * FROM users LIMIT 2;
SELECT COUNT(*) FROM users;
SELECT SUM(amount) FROM orders;
SELECT AVG(age) FROM users;
SELECT MIN(age), MAX(age) FROM users;
SELECT city, COUNT(*) AS cnt FROM users GROUP BY city;
SELECT city, SUM(age) FROM users GROUP BY city;
SELECT city, AVG(age) FROM users GROUP BY city;
-- Crucial GROUP BY order test: aggregate first, then group column
SELECT SUM(age), city FROM users GROUP BY city;
-- Multiple aggregates
SELECT city, COUNT(*), AVG(age) FROM users GROUP BY city;
SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id;
SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id WHERE o.amount > 150;
SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id ORDER BY o.amount DESC;
INSERT INTO users (id, name, age, city) VALUES (4, 'Alice', 28, 'Seattle');
SELECT * FROM users;
SAVE users TO 'samples/users_updated.csv';
```

These queries cover: LOAD, SELECT \*, specific columns, WHERE with comparisons, AND/OR, ORDER BY (single/multiple, ASC/DESC), LIMIT, aggregate functions without GROUP BY, GROUP BY with aggregates (including mixed ordering), INNER JOIN with conditions and sorting, INSERT, and SAVE.

**Verification of GROUP BY ordering fix**: The query `SELECT SUM(age), city FROM users GROUP BY city;` must display the column `SUM(age)` in the first position and `city` in the second, exactly as written. If the output shows city first, the fix has not been applied.

---

## 6. Additional Notes
- String literals in SQL: single‑quoted, e.g., `'text'`. Lexer handles no escapes; raw string between quotes.
- Numeric literals: integer or float (e.g., `123`, `3.14`). Lexer token type `NUMBER`.
- Identifiers: case‑insensitive for keywords, but table/column names are case‑sensitive as they appear in CSV headers.
- Semicolon optional at end of command.
- All values remain strings internally; numeric operations (SUM, AVG, comparisons) will attempt `float()` conversion; if fails, treat as string or skip if appropriate.
- Aggregates like SUM/AVG on non‑numeric column: skip non‑convertible values silently.
- JOIN column naming: we'll prefix with table name (e.g., `users.name`). The ON condition must use `table.column` syntax; parser will recognize this as `<table>.<column>`.
- The entire engine runs in a single process, all tables in memory.
- **Testing**: (Recommended) A test script in `tests/test_queries.py` can load the sample CSVs, execute all commands from `queries.txt`, and assert that the output contains expected patterns (especially the GROUP BY order). This ensures the fix is in place and remains stable. Use `sys.stdout` capture for integration testing.
- **Documentation**: The `README.md` should explain how to start the REPL, load the sample files, and run the provided queries. It should also note the expected behavior of `SELECT SUM(age), city FROM users GROUP BY city`.

---

*End of revised plan.*