"""Main entry point for the bytecode interpreter.

Usage: python main.py <source_file>
"""

import sys
from lexer import Lexer, LexError
from compiler import Compiler, CompileError
from vm import VirtualMachine, RuntimeError_


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <source_file>", file=sys.stderr)
        sys.exit(1)

    source_path = sys.argv[1]

    try:
        with open(source_path, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {source_path}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Lexing
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexError as e:
        print(f"Lex error: {e}", file=sys.stderr)
        sys.exit(1)

    # Compilation
    try:
        compiler = Compiler(tokens)
        constants, instructions, names = compiler.compile()
    except CompileError as e:
        print(f"Compile error: {e}", file=sys.stderr)
        sys.exit(1)

    # Execution
    try:
        vm = VirtualMachine(constants, instructions, names)
        vm.execute()
    except RuntimeError_ as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
