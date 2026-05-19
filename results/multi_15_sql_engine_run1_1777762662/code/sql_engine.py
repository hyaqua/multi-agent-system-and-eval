#!/usr/bin/env python3
"""SQL Query Engine – REPL over CSV files using standard library only."""

import sys
import os

from lexer import tokenize, LexerError
from parser import Parser, ParseError
from executor import Executor, ExecutionError
from formatter import format_table


def main():
    executor = Executor()
    print("SQL Query Engine (CSV-backed)")
    print('Type SQL statements ending with ; or type "exit" to quit.')
    print()

    buffer = []

    while True:
        try:
            if buffer:
                prompt = '... '
            else:
                prompt = '> '

            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = line.strip()

        # Check for exit
        if stripped.lower() == 'exit' and not buffer:
            break

        buffer.append(line)

        # Check if statement is complete (ends with semicolon)
        full_text = ' '.join(buffer)
        if ';' in full_text:
            # Process all statements in the buffer
            text = ' '.join(buffer)
            buffer = []

            # Split by semicolons to handle multiple statements
            statements = text.split(';')
            for stmt_text in statements:
                stmt_text = stmt_text.strip()
                if not stmt_text:
                    continue

                try:
                    tokens = tokenize(stmt_text)
                    parser = Parser(tokens)
                    ast = parser.parse()

                    if ast is None:
                        continue

                    columns, rows = executor.execute(ast)
                    print(format_table(columns, rows))

                except (LexerError, ParseError) as e:
                    print(f"Error: {e.message}")
                except ExecutionError as e:
                    print(f"Error: {str(e)}")
                except Exception as e:
                    print(f"Unexpected error: {str(e)}")


if __name__ == '__main__':
    main()
