# SQL Engine Implementation Plan

## Overview
A Python REPL-based SQL query engine that reads CSV files as tables and supports a subset of SQL. It uses only the standard library. The system comprises a lexer, parser, query executor, table storage, and a formatted output renderer.

## Files and Purposes
- `main.py` – entry point; launches REPL.
- `lexer.py` – tokenizer; converts input string into a list of tokens with location tracking.
- `ast.py` – AST node classes for statements and expressions.
- `parser.py` – recursive descent parser; builds AST from token list, reports syntax errors with source position.
- `database.py` – in‑memory table store; loads/saves CSV, manages rows and column metadata.
- `executor.py` – interprets AST against database; handles SELECT, INSERT, LOAD, SAVE, joins, aggregates, ordering, limiting.
- `formatter.py` – renders query results as an ASCII table with aligned columns.
- `error.py` – custom exception classes (e.g., `ParseError`, `QueryError`).
- `repl.py` – input loop, command accumulation (supporting multi‑line input until semicolon), integrates all components.
- `samples/` – directory containing example CSV files (`users.csv`, `orders.csv`).
- `README.md` – usage instructions and list of example queries demonstrating all features.

## Architecture
```
User Input
   │
   ▼
 REPL (repl.py)
   │
   ├── Lexer (lexer.py) → token stream with positions
   ├── Parser (parser.py) → AST (ast.py)
   ├── Executor (executor.py) ── uses Database (database.py)
   ├── Formatter (formatter.py)
   └── Error handling (error.py)
```

- **REPL** reads lines until a semicolon is encountered, then passes the complete statement to the lexer and parser.
- **Parser** returns an AST root node. On failure it raises `ParseError` with a message that includes line and column.
- **Executor** receives the AST and the `Database` instance. It performs the appropriate action (load, save, insert, select) and returns a result dict: `{ 'type': 'table', 'columns': [...], 'rows': [...] }` for selects, or a status string for other commands.
- **Formatter** takes a table result and prints a nicely aligned ASCII table.
- **Database** holds tables as `Table` objects: a list of column names and a list of row tuples. It uses `csv.reader`/`csv.writer` for file I/O.

## Implementation Order
1. **Database layer** (`database.py`) – Table class, load/save CSV, insert row, retrieve table.
2. **Lexer** (`lexer.py`) – token definitions, scanner with position tracking.
3. **AST definitions** (`ast.py`) – nodes for all statement and expression types.
4. **Parser** (`parser.py`) – grammar implementation, error reporting via `ParseError`.
5. **Executor** (`executor.py`) – evaluate `SELECT`, `INSERT`, `LOAD`, `SAVE`. Implement WHERE, AND/OR, ORDER BY, LIMIT, aggregate functions, GROUP BY, INNER JOIN step‑by‑step.
6. **Formatter** (`formatter.py`) – column width calculation, left/right alignment logic, printing borders.
7. **REPL** (`repl.py`) + `main.py` – input handling, integration.
8. **Sample files & README** – create `users.csv`, `orders.csv`, document example queries.

## Libraries Used
- Standard library only: `csv`, `re`, `sys`, `os`, `io`, `textwrap` (optional). No external packages.

## Feature Implementation Details

### LOAD command
- Parser: `LOAD identifier FROM string_literal`
- Executor calls `database.load_csv(table_name, filepath)`. The file is opened with `csv.reader`, first row becomes column names, remaining rows stored as tuples. Overwrites any existing table with that name.

### SAVE command
- Parser: `SAVE identifier TO string_literal` or `SAVE identifier TO file`
- Executor calls `database.save_csv(table_name, filepath)`, writing header and rows with `csv.writer`.

### INSERT INTO
- Parser: `INSERT INTO identifier VALUES (value_list)`
- Executor validates the table exists, checks that the number of values matches the column count, then appends the row tuple to the table.

### SELECT with specific columns / SELECT *
- `SELECT col1, col2 FROM table` → project only those columns.
- `SELECT *` → project all columns in table order.
- Executor obtains the table, applies projection.

### WHERE clause with comparisons and AND/OR
- Represented as an expression tree (`BinaryOp` nodes for AND/OR, `Comparison` nodes for =, !=, <, >, <=, >=).
- During row evaluation, the expression is recursively evaluated. `Comparison` compares a column value (from row dict) with a literal or another column. AND/OR apply Python’s logical operators (early termination).
- Missing columns or type mismatches raise a clear error.

### ORDER BY (ASC/DESC)
- After filtering, rows are sorted using Python’s `sorted()` with a key function that evaluates the ORDER BY expressions. Each expression produces a tuple (value, is_desc) to allow mixed directions. `ASC` is default.

### LIMIT
- After sorting, simply slice `rows[:limit]`.

### Aggregate functions (COUNT, SUM, AVG, MIN, MAX)
- Implemented in executor.
- **No GROUP BY**: treat entire table as one group. Compute each aggregate over all rows. Output a single row with aggregate results (and only aggregate columns allowed in SELECT). If non‑aggregate columns are present without GROUP BY, raise an error.
- **With GROUP BY**: rows are grouped by the GROUP BY expressions. For each group, aggregates are computed over that group’s rows. The result row contains the group‑by columns and aggregate values. Only columns in GROUP BY or inside aggregate functions may appear in SELECT; otherwise an error is reported.
- Aggregates ignore `NULL` values (we don’t have NULL in CSV, but treat empty string as NULL? For simplicity, we treat empty cells as empty strings, aggregates skip empty strings for numeric functions if needed). We’ll treat all values as strings; numeric functions will attempt to convert to float, ignoring non‑numeric gracefully or raising an error.

### GROUP BY
- Performed by building a dictionary: key = tuple of group‑by expression values, value = list of rows in that group.
- Then for each group, evaluate the SELECT list (group‑by columns + aggregates).

### INNER JOIN
- Syntax: `SELECT ... FROM table1 INNER JOIN table2 ON condition`
- Executor: load both tables. Produce a combined row set by nested loops: for each row in table1, for each row in table2, evaluate the ON condition. If true, combine the two row dicts into one.
  - Column naming: if a column name exists in both tables, the ON condition and SELECT must use `table.column` qualification. Unqualified names are resolved by first checking the left table, then the right table; ambiguous references cause an error.
- The resulting joined table is then passed through WHERE, GROUP BY, etc. as if it were a normal table.

### Formatted ASCII table
- `formatter.py` builds a display grid:
  - Each column’s width = max(len(header), max(len(str(cell)) for cell in column).
  - Left‑align strings, right‑align numbers (detect via `isinstance(value, (int, float))`). All data from CSV is string, but executor may convert to numeric for comparisons/aggregates; the final output values are what the user selected, so if an aggregate returns a float, it will be right‑aligned.
  - Print horizontal separator lines (`+---+`), header row, separator, each data row, final separator.

### Syntax error messages
- The lexer records `line` and `column` for each token.
- The parser, on unexpected token, calls a helper to raise `ParseError(f"Expected ... but found ... at line X, column Y")`.
- The REPL catches `ParseError` and prints the message in red (optional) or just plain.

### REPL loop
- Prompts `sql> ` for the first line, then `...> ` for continuation lines until a semicolon is found.
- On empty input, continue.
- Exits on `exit` or `quit` (case‑insensitive) or EOF.
- After statement execution, prints the result table or a success message.
- Catches any other exception (`QueryError`, general) and prints a clean error without crashing.

## Sample CSV Files
- `samples/users.csv`: `id,name,age,city`
- `samples/orders.csv`: `order_id,user_id,product,amount`

## Example Queries (to be included in README)
- `LOAD users FROM 'samples/users.csv';`
- `SELECT * FROM users;`
- `SELECT name, age FROM users WHERE age > 25;`
- `SELECT city, COUNT(*) FROM users GROUP BY city ORDER BY COUNT(*) DESC;`
- `SELECT users.name, orders.product FROM users INNER JOIN orders ON users.id = orders.user_id;`
- `INSERT INTO users VALUES (4, 'Alice', 30, 'London');`
- `SAVE users TO 'samples/users_modified.csv';`

---

This plan provides a clear, ordered path from data layer to full REPL, ensuring each feature is built incrementally and tested with the sample data.