#!/usr/bin/env python3
"""Main entry point for the bytecode interpreter.

Usage: python main.py <source_file>

Reads a source file, tokenizes it, compiles to bytecode, and executes.
"""

import sys
import os
from lexer import Lexer, LexerError
from compiler import Compiler, CompilerError
from vm import VM, RuntimeError as VMRuntimeError


def run_file(filepath: str):
    """Read, compile, and execute a source file."""
    if not os.path.isfile(filepath):
        print(f"Error: File not found: '{filepath}'", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    filename = os.path.basename(filepath)

    # Stage 1: Lexing
    try:
        lexer = Lexer(source, filename=filename)
        tokens = lexer.tokens
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        sys.exit(1)

    # Optional: print tokens for debugging
    # for t in tokens:
    #     print(t)

    # Stage 2: Compilation
    try:
        compiler = Compiler(tokens, filename=filename)
        code, functions = compiler.compile()
    except CompilerError as e:
        print(f"Syntax error: {e}", file=sys.stderr)
        sys.exit(1)

    # Stage 3: Execution
    try:
        vm = VM(code, functions, filename=filename)
        vm.run()
    except VMRuntimeError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <source_file>", file=sys.stderr)
        print("Example: python main.py examples/fib.txt", file=sys.stderr)
        sys.exit(1)

    run_file(sys.argv[1])


if __name__ == '__main__':
    main()
