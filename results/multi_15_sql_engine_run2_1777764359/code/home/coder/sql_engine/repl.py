"""REPL input loop - handles multi-line input, integrates all components."""

import sys
from lexer import tokenize
from parser import parse
from database import Database
from executor import Executor
from formatter import format_table
from error import ParseError, QueryError


def run_repl():
    """Run the SQL engine REPL."""
    db = Database()
    executor = Executor(db)

    print("SQL Query Engine REPL")
    print("Enter SQL statements ending with ';' or 'exit'/'quit' to quit.")
    print()

    while True:
        try:
            # Read first line
            try:
                line = input("sql> ")
            except EOFError:
                print()
                break

            # Accumulate lines until semicolon
            buffer = line
            while ';' not in buffer:
                # Check for exit
                stripped = buffer.strip().lower()
                if stripped in ('exit', 'quit'):
                    print("Goodbye!")
                    return

                try:
                    continuation = input("...> ")
                except EOFError:
                    print()
                    break
                buffer += " " + continuation

            # Check for exit
            stripped = buffer.strip().rstrip(';').strip().lower()
            if stripped in ('exit', 'quit'):
                print("Goodbye!")
                return

            # Skip empty input
            if not buffer.strip() or buffer.strip() == ';':
                continue

            # Process the statement
            _process_statement(buffer, db, executor)

        except KeyboardInterrupt:
            print()
            continue

    print("Goodbye!")


def _process_statement(source: str, db: Database, executor: Executor):
    """Tokenize, parse, and execute a single statement."""
    try:
        tokens = tokenize(source)
    except ParseError as e:
        print(f"Syntax error: {e}")
        return

    try:
        ast = parse(tokens)
    except ParseError as e:
        print(f"Syntax error: {e}")
        return

    try:
        result = executor.execute(ast)
    except QueryError as e:
        print(f"Query error: {e}")
        return
    except Exception as e:
        print(f"Error: {e}")
        return

    # Display result
    if result['type'] == 'table':
        output = format_table(result['columns'], result['rows'])
        print(output)
    elif result['type'] == 'message':
        print(result['message'])
    else:
        print(f"Unknown result type: {result.get('type')}")


if __name__ == '__main__':
    run_repl()
