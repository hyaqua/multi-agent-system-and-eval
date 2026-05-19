#!/usr/bin/env python3
"""Bytecode Interpreter: reads .lang files and executes them.

Usage:
    python interpreter.py <source_file.lang>
"""

import sys
import argparse

from lexer import Lexer, LexerError
from compiler import Compiler, SyntaxError as CompilerSyntaxError
from vm import VirtualMachine, RuntimeError_ as VMRuntimeError


def main():
    parser = argparse.ArgumentParser(
        description="Bytecode Interpreter for .lang files"
    )
    parser.add_argument(
        "source_file",
        help="Path to the source .lang file to execute"
    )
    args = parser.parse_args()

    # Read source file
    try:
        with open(args.source_file, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {args.source_file}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Phase 1: Lexing
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        sys.exit(1)

    # Phase 2: Compilation
    try:
        compiler = Compiler(tokens)
        code_object = compiler.compile()
    except CompilerSyntaxError as e:
        print(f"Syntax error: {e}", file=sys.stderr)
        sys.exit(1)

    # Phase 3: Execution
    try:
        vm = VirtualMachine(code_object)
        vm.run()
    except VMRuntimeError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
