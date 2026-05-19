#!/usr/bin/env python3
"""SQL Query Engine REPL - Main entry point."""

import sys
import os

from lexer import Lexer
from parser import Parser, ParseError, parse_sql
from executor import Executor, ExecutionError
from formatter import format_ascii_table


def print_help():
    print("""
SQL Query Engine - Supported Commands:

  LOAD table_name FROM 'filename.csv'
  SAVE table_name TO 'filename.csv'
  SELECT columns FROM table [JOIN ...] [WHERE ...] [GROUP BY ...] [ORDER BY ...] [LIMIT n]
  INSERT INTO table VALUES (v1, v2, ...)

Examples:
  LOAD users FROM 'users.csv'
  SELECT * FROM users
  SELECT name, age FROM users WHERE age > 18
  SELECT name, age FROM users ORDER BY age DESC LIMIT 5
  SELECT dept, COUNT(*), AVG(salary) FROM employees GROUP BY dept
  SELECT u.name, o.total FROM users u INNER JOIN orders o ON u.id = o.user_id
  INSERT INTO users VALUES ('John', '30', 'NYC')
  SAVE users TO 'users_export.csv'

Commands:
  .help     - Show this help
  .tables   - List loaded tables
  .schema   - Show schema of all loaded tables
  .quit     - Exit the REPL
  .load     - Load and run a SQL file
""")


def main():
    print("=== SQL Query Engine ===")
    print("Type SQL queries or .help for commands. .quit to exit.")
    print()

    executor = Executor()
    history = []

    while True:
        try:
            # Read input
            line = input("sql> ").strip()

            # Handle empty input
            if not line:
                continue

            # Handle multi-line input (ending with semicolon)
            while not line.endswith(';') and not line.startswith('.') and line:
                continuation = input(" ... ").strip()
                if not continuation:
                    break
                line += ' ' + continuation
                if line.endswith(';'):
                    break

            # Remove trailing semicolon for parsing
            if line.endswith(';'):
                line = line[:-1].strip()

            if not line:
                continue

            history.append(line)

            # Handle dot commands
            if line.startswith('.'):
                cmd = line.lower().split()[0]
                if cmd == '.quit' or cmd == '.exit':
                    print("Goodbye!")
                    break
                elif cmd == '.help':
                    print_help()
                elif cmd == '.tables':
                    if executor.tables:
                        print("Loaded tables:")
                        for name, table in executor.tables.items():
                            print(f"  {name}: {len(table.rows)} rows, {len(table.columns)} columns")
                    else:
                        print("No tables loaded.")
                elif cmd == '.schema':
                    if executor.tables:
                        for name, table in executor.tables.items():
                            cols = ', '.join(table.columns)
                            print(f"  {name} ({cols}): {len(table.rows)} rows")
                    else:
                        print("No tables loaded.")
                elif cmd == '.load':
                    parts = line.split(maxsplit=1)
                    if len(parts) < 2:
                        print("Usage: .load <filename>")
                    else:
                        filename = parts[1]
                        run_sql_file(filename, executor)
                else:
                    print(f"Unknown command: {cmd}. Type .help for help.")
                continue

            # Parse and execute SQL
            try:
                statement = parse_sql(line)
            except ParseError as e:
                print(f"Syntax error: {e}")
                # Show position indicator
                print(f"  {line}")
                print(f"  {' ' * e.pos}^")
                continue

            try:
                result = executor.execute(statement)
            except ExecutionError as e:
                print(f"Execution error: {e.message}")
                continue
            except Exception as e:
                print(f"Error: {e}")
                continue

            if isinstance(result, str):
                print(result)
            else:
                print(format_ascii_table(result))

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("Goodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")


def run_sql_file(filename: str, executor: Executor):
    """Run SQL statements from a file."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    with open(filename, 'r') as f:
        content = f.read()

    # Remove comment lines (lines starting with --)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)

    # Split by semicolons and process each statement
    statements = content.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            parsed = parse_sql(stmt)
            result = executor.execute(parsed)
            if isinstance(result, str):
                print(result)
            else:
                print(format_ascii_table(result))
        except ParseError as e:
            print(f"Syntax error in '{stmt[:50]}...': {e}")
        except ExecutionError as e:
            print(f"Execution error in '{stmt[:50]}...': {e.message}")
        except Exception as e:
            print(f"Error in '{stmt[:50]}...': {e}")


if __name__ == '__main__':
    main()
