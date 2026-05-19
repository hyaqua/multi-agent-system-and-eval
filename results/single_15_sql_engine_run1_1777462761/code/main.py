#!/usr/bin/env python3
"""
SQL Query Engine – REPL
========================
A lightweight SQL query engine that reads CSV files as tables and supports
a subset of SQL for querying them. Built using only the Python standard library.

Usage:
    python main.py          # Start the REPL
    python main.py --demo   # Run built-in demo queries
"""

import sys
import os

from lexer import Lexer, LexerError
from parser import Parser, ParserError
from executor import Executor, ExecutorError
from storage import Storage
from formatter import format_table


HELP_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║                    SQL Query Engine Help                     ║
╠══════════════════════════════════════════════════════════════╣
║ Commands:                                                    ║
║   LOAD <name> FROM '<file>'     Load a CSV file as a table   ║
║   SAVE <name> TO '<file>'       Save a table to CSV          ║
║   SELECT ... FROM ...           Query data                   ║
║   INSERT INTO <name> VALUES ... Add a row to a table         ║
║   EXIT / QUIT                   Exit the REPL                ║
║   HELP                          Show this help               ║
╠══════════════════════════════════════════════════════════════╣
║ SELECT syntax:                                               ║
║   SELECT <cols> FROM <table>                                 ║
║     [INNER JOIN <t2> ON <c1> = <c2>]                         ║
║     [WHERE <condition>]                                      ║
║     [GROUP BY <cols>]                                        ║
║     [ORDER BY <cols> [ASC|DESC]]                             ║
║     [LIMIT <n>]                                              ║
║                                                              ║
║ <cols> can be:                                               ║
║   *                      All columns                         ║
║   col1, col2             Specific columns                    ║
║   table.col              Qualified column (for JOINs)        ║
║   COUNT(*), SUM(col),    Aggregate functions                 ║
║   AVG(col), MIN(col),                                       ║
║   MAX(col)                                                   ║
║                                                              ║
║ WHERE operators: =, !=, <, >, <=, >=, AND, OR                ║
╚══════════════════════════════════════════════════════════════╝
"""

DEMO_QUERIES = [
    # Load sample data
    "LOAD users FROM 'sample_users.csv'",
    "LOAD orders FROM 'sample_orders.csv'",

    # Basic SELECT
    "SELECT * FROM users",
    "SELECT name, age FROM users",

    # WHERE with comparisons
    "SELECT name, age, city FROM users WHERE age > 25",
    "SELECT name, salary FROM users WHERE city = 'Chicago'",

    # WHERE with AND/OR
    "SELECT name, age, city FROM users WHERE age >= 30 AND city = 'New York'",
    "SELECT name, city FROM users WHERE city = 'Boston' OR city = 'Chicago'",

    # ORDER BY
    "SELECT name, salary FROM users ORDER BY salary DESC",
    "SELECT name, age, city FROM users ORDER BY city ASC, age DESC",

    # LIMIT
    "SELECT name, age FROM users ORDER BY age DESC LIMIT 3",

    # Aggregate functions (without GROUP BY)
    "SELECT COUNT(*) FROM users",
    "SELECT AVG(salary), MIN(salary), MAX(salary) FROM users",
    "SELECT SUM(salary) FROM users",

    # GROUP BY with aggregates
    "SELECT city, COUNT(*) FROM users GROUP BY city",
    "SELECT city, AVG(salary), MIN(age), MAX(age) FROM users GROUP BY city",

    # INNER JOIN
    "SELECT users.name, orders.product, orders.amount FROM users INNER JOIN orders ON users.name = orders.user_name",
    "SELECT users.name, users.city, COUNT(orders.id) FROM users INNER JOIN orders ON users.name = orders.user_name GROUP BY users.name, users.city",

    # INSERT
    "INSERT INTO users VALUES ('Iris', 27, 'Seattle', 68000)",

    # Verify INSERT
    "SELECT * FROM users WHERE name = 'Iris'",

    # SAVE (use /tmp since workspace may be read-only)
    "SAVE users TO '/tmp/export_users.csv'",

    # Show the export worked
    "LOAD users_copy FROM '/tmp/export_users.csv'",
    "SELECT COUNT(*) FROM users_copy",
]


def print_demo_header(title: str):
    """Print a formatted demo section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_demo(storage: Storage, executor: Executor):
    """Run a series of demonstration queries."""
    print_demo_header("SQL Query Engine – Feature Demo")
    print("Running demonstration queries...")

    for i, query in enumerate(DEMO_QUERIES, 1):
        print_demo_header(f"Query {i}: {query}")
        try:
            _process_query(query, storage, executor)
        except Exception as e:
            print(f"  Error: {e}")

    # Clean up export file
    if os.path.exists('/tmp/export_users.csv'):
        os.remove('/tmp/export_users.csv')

    print_demo_header("Demo Complete")


def _process_query(query: str, storage: Storage, executor: Executor):
    """Tokenize, parse, execute, and display results for a single query."""
    lexer = Lexer(query)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    stmt = parser.parse()

    result = executor.execute(stmt)

    if result is not None:
        print(format_table(result))
        print(f"({len(result)} row(s) returned)")


def repl():
    """Run the interactive REPL loop."""
    storage = Storage()
    executor = Executor(storage)

    print("╔══════════════════════════════════════════════════╗")
    print("║           SQL Query Engine (Python)              ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Type SQL queries, HELP, or EXIT to quit         ║")
    print("║  Start with: LOAD users FROM 'sample_users.csv'  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    while True:
        try:
            query = input("sql> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue

        upper = query.upper()

        if upper in ('EXIT', 'QUIT'):
            print("Goodbye!")
            break

        if upper == 'HELP':
            print(HELP_TEXT)
            continue

        try:
            _process_query(query, storage, executor)
        except LexerError as e:
            print(f"Lexer Error: {e}")
        except ParserError as e:
            print(f"Parser Error: {e}")
        except ExecutorError as e:
            print(f"Execution Error: {e}")
        except FileNotFoundError as e:
            print(f"File Error: {e}")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected Error ({type(e).__name__}): {e}")


def main():
    if '--demo' in sys.argv:
        storage = Storage()
        executor = Executor(storage)
        run_demo(storage, executor)
    else:
        repl()


if __name__ == '__main__':
    main()
