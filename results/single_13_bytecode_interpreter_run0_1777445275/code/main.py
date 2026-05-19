#!/usr/bin/env python3
"""Main entry point for the bytecode interpreter.

Usage: python main.py <source_file> [--debug] [--disassemble]
"""

import sys
import os
from lexer import Lexer, LexerError
from compiler import Compiler, CompilerError
from vm import VM, VMRuntimeError, disassemble


def run_file(filepath: str, debug: bool = False, show_disassembly: bool = False):
    """Read a source file, compile it, and execute it."""
    if not os.path.exists(filepath):
        print(f"Error: File not found: '{filepath}'", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r') as f:
        source = f.read()

    # Stage 1: Lexing
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        sys.exit(1)

    if debug:
        print("[DEBUG] Tokens:")
        for tok in tokens:
            print(f"  {tok}")
        print()

    # Stage 2: Compilation
    try:
        compiler = Compiler(tokens)
        bytecode, functions = compiler.compile()
    except CompilerError as e:
        print(f"Compilation error: {e}", file=sys.stderr)
        sys.exit(1)

    if show_disassembly:
        disassemble(bytecode, functions)
        if not debug:
            print()

    if debug and not show_disassembly:
        disassemble(bytecode, functions)
        print()

    # Stage 3: Execution
    try:
        vm = VM(bytecode, functions)
        vm.run(debug=debug)
    except VMRuntimeError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python main.py <source_file> [--debug] [--disassemble]", file=sys.stderr)
        print()
        print("Options:")
        print("  --debug         Enable debug output (tokens, bytecode, execution trace)")
        print("  --disassemble   Show bytecode disassembly before execution")
        sys.exit(1)

    filepath = None
    debug = False
    show_disassembly = False

    for arg in args:
        if arg == '--debug':
            debug = True
        elif arg == '--disassemble':
            show_disassembly = True
        elif not arg.startswith('--'):
            filepath = arg
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    if filepath is None:
        print("Error: No source file specified.", file=sys.stderr)
        sys.exit(1)

    run_file(filepath, debug=debug, show_disassembly=show_disassembly)


if __name__ == '__main__':
    main()
