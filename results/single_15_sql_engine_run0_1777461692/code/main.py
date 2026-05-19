#!/usr/bin/env python3
"""SQL Engine REPL - Main entry point.

A simple SQL query engine that reads CSV files as tables and supports
a subset of SQL for querying them.
"""

import os
import sys
import traceback

from lexer import Lexer, LexerError, TokenType
from parser import Parser, ParseError
from executor import Executor, ExecutorError
from table import Table, TableError
from formatter import format_table


# Sample data
SAMPLE_USERS_CSV = """id,name,age,email,city
1,Alice,30,alice@example.com,New York
2,Bob,25,bob@example.com,Los Angeles
3,Charlie,35,charlie@example.com,Chicago
4,Diana,28,diana@example.com,New York
5,Eve,22,eve@example.com,Boston
6,Frank,40,frank@example.com,Los Angeles
7,Grace,33,grace@example.com,Chicago
8,Henry,27,henry@example.com,Boston
9,Iris,31,iris@example.com,New York
10,Jack,29,jack@example.com,Los Angeles
"""

SAMPLE_ORDERS_CSV = """order_id,user_id,product,amount,date
1,1,Laptop,1200.00,2024-01-15
2,1,Mouse,25.50,2024-01-16
3,2,Keyboard,75.00,2024-01-17
4,3,Monitor,350.00,2024-01-18
5,3,Laptop,1200.00,2024-02-01
6,5,Headphones,80.00,2024-02-05
7,1,Webcam,60.00,2024-02-10
8,4,Keyboard,75.00,2024-02-12
9,2,Monitor,350.00,2024-03-01
10,6,Mouse,25.50,2024-03-05
11,7,Laptop,1200.00,2024-03-10
12,3,Headphones,80.00,2024-03-15
13,8,Webcam,60.00,2024-04-01
14,9,Keyboard,75.00,2024-04-05
15,10,Monitor,350.00,2024-04-10
"""

SAMPLE_PRODUCTS_CSV = """product_id,name,category,price,stock
1,Laptop,Electronics,1200.00,50
2,Mouse,Electronics,25.50,200
3,Keyboard,Electronics,75.00,150
4,Monitor,Electronics,350.00,75
5,Headphones,Electronics,80.00,100
6,Webcam,Electronics,60.00,80
7,Desk,Furniture,250.00,30
8,Chair,Furniture,180.00,45
9,Lamp,Furniture,45.00,120
10,Notebook,Stationery,5.00,500
"""


def create_sample_files(data_dir='/tmp'):
    """Create sample CSV files if they don't exist."""
    samples = {
        'users.csv': SAMPLE_USERS_CSV,
        'orders.csv': SAMPLE_ORDERS_CSV,
        'products.csv': SAMPLE_PRODUCTS_CSV,
    }
    for filename, content in samples.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content.lstrip('\n'))


def print_help():
    """Print help text."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    SQL Query Engine                          ║
╠══════════════════════════════════════════════════════════════╣
║ Commands:                                                   ║
║   LOAD table FROM 'file.csv'   - Load a CSV file as table   ║
║   SAVE table TO 'file.csv'     - Save a table to CSV        ║
║   SELECT ... FROM ...          - Query tables               ║
║   INSERT INTO ... VALUES ...   - Insert a row               ║
║                                                             ║
║ SQL Features:                                               ║
║   SELECT *, SELECT col1, col2, ...                          ║
║   WHERE with =, !=, <, >, <=, >=                           ║
║   AND / OR logical operators                                ║
║   ORDER BY col [ASC|DESC], ...                              ║
║   LIMIT number                                              ║
║   COUNT, SUM, AVG, MIN, MAX aggregates                      ║
║   GROUP BY column(s)                                        ║
║   INNER JOIN table ON condition                             ║
║                                                             ║
║ Other:                                                      ║
║   .help    - Show this help                                 ║
║   .tables  - List loaded tables                             ║
║   .schema  - Show table columns                             ║
║   .exit    - Exit the REPL                                  ║
║   quit / exit - Also exits                                  ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_tables(executor: Executor):
    """Print list of loaded tables."""
    if not executor.tables:
        print("No tables loaded.")
        return
    print("\nLoaded tables:")
    for name, table in executor.tables.items():
        print(f"  {name}: {len(table.rows)} rows, {len(table.columns)} columns")
        print(f"    Columns: {', '.join(table.columns)}")
    print()


def print_schema(executor: Executor, table_name: str = None):
    """Print schema for a table or all tables."""
    if table_name:
        if table_name not in executor.tables:
            print(f"Table '{table_name}' not found.")
            return
        table = executor.tables[table_name]
        print(f"\nTable: {table_name}")
        print(f"  Rows: {len(table.rows)}")
        print(f"  Columns:")
        for col in table.columns:
            # Show sample values
            sample_vals = [str(row[col]) for row in table.rows[:3]]
            print(f"    {col}: {', '.join(sample_vals)}")
        print()
    else:
        print_tables(executor)


def process_meta_command(cmd: str, executor: Executor) -> bool:
    """Process meta-commands like .help, .tables, .exit. Returns True to exit."""
    parts = cmd.strip().split()
    cmd_name = parts[0].lower()

    if cmd_name in ('.exit', 'exit', 'quit'):
        print("Goodbye!")
        return True

    if cmd_name == '.help':
        print_help()
        return False

    if cmd_name == '.tables':
        print_tables(executor)
        return False

    if cmd_name == '.schema':
        if len(parts) > 1:
            print_schema(executor, parts[1])
        else:
            print_schema(executor)
        return False

    return False


def run_repl():
    """Run the interactive REPL loop."""
    executor = Executor()

    print_help()

    # Auto-load sample files from /tmp (workspace may be read-only)
    data_dir = '/tmp'
    create_sample_files(data_dir)
    sample_files = {
        'users': os.path.join(data_dir, 'users.csv'),
        'orders': os.path.join(data_dir, 'orders.csv'),
        'products': os.path.join(data_dir, 'products.csv'),
    }
    for table_name, filename in sample_files.items():
        if os.path.exists(filename):
            try:
                executor.tables[table_name] = Table.load_csv(table_name, filename)
                print(f"Auto-loaded '{filename}' as table '{table_name}'.")
            except Exception as e:
                print(f"  Could not load {filename}: {e}")

    print("\nEnter SQL queries or .help for help.")

    while True:
        try:
            user_input = input("\nsql> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Check for meta-commands
        if user_input.startswith('.') or user_input.lower() in ('exit', 'quit'):
            if process_meta_command(user_input, executor):
                break
            continue

        # Parse and execute SQL
        try:
            # Lex
            lexer = Lexer(user_input)
            tokens = lexer.tokenize()

            # Filter out EOF for parser check
            non_eof = [t for t in tokens if t.type != TokenType.EOF]
            if not non_eof:
                continue

            # Parse
            parser = Parser(tokens)
            ast = parser.parse()

            if ast is None:
                continue

            # Execute
            result = executor.execute(ast)

            # Display results
            if result is not None:
                columns, rows = result
                print(format_table(columns, rows))

        except (LexerError, ParseError) as e:
            print(f"Syntax error: {e}")
        except ExecutorError as e:
            print(f"Error: {e}")
        except TableError as e:
            print(f"Table error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    run_repl()
