#!/usr/bin/env python3
"""SQL Engine REPL — main entry point."""

import sys
import os

from lexer import tokenize
from parser import parse
from executor import Executor
from formatter import format_table, format_message
from error import SQLError


def print_usage():
    print("Mini SQL Engine")
    print("Commands:")
    print("  LOAD table FROM 'path.csv'   — Load a CSV file as a table")
    print("  SAVE table TO 'path.csv'     — Save a table to a CSV file")
    print("  SELECT ... FROM ...          — Query data")
    print("  INSERT INTO ... VALUES ...   — Insert a row")
    print("  Type 'exit' or 'quit' to quit.")
    print("  Type 'help' for this message.")
    print("  End SQL statements with an optional semicolon.")


def print_error(exception, input_line):
    """Print a syntax error with a caret pointing at the error position."""
    if isinstance(exception, SQLError) and exception.pos:
        line_no, col_no = exception.pos
        print(f"Error at line {line_no}, column {col_no}: {exception.message}")
        # Show the input line
        lines = input_line.split("\n")
        if line_no <= len(lines):
            err_line = lines[line_no - 1]
            print(err_line)
            print(" " * (col_no - 1) + "^")
    else:
        print(f"Error: {exception}")


def main():
    executor = Executor()

    print("Mini SQL Engine — REPL")
    print("Type 'help' for usage, 'exit' to quit.")
    print()

    while True:
        try:
            user_input = input("sql> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if user_input.lower() == "help":
            print_usage()
            continue

        # Handle LOAD and SAVE commands directly (they have their own syntax)
        # But also try to parse them through the normal pipeline
        try:
            tokens = tokenize(user_input)
            ast = parse(tokens)

            if ast is None:
                continue

            result = executor.execute(ast)

            if result is None:
                continue

            data, msg = result

            if msg:
                # Simple message (LOAD, SAVE, INSERT)
                print(format_message(msg))
            elif data:
                columns, rows, count = data
                print(format_table(columns, rows))
            else:
                print(format_message("OK."))

        except SQLError as e:
            print_error(e, user_input)
        except FileNotFoundError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
