# Revised Bytecode Interpreter – Implementation Plan

This plan addresses all feedback: line‑number annotated syntax errors, line‑numbered runtime errors, operand type safety, a command‑line driver, and three example programs that exercise every required feature.  
Every component is built using only the Python standard library.

---

## Overview

The interpreter pipeline remains **Lexer → Compiler → Virtual Machine**.  
All error reporting uses standard `SyntaxError` (with a proper `lineno`) for syntax issues and a custom `RuntimeError` (with a `lineno` attribute) for runtime issues.  
A debug line mapping inside the `Code` object connects each bytecode instruction to its source line, guaranteeing precise runtime error locations.

---

## Files and Their Responsibilities

1. **`tokens.py`**  
   - `Token` class with fields: `type`, `value`, `line`, `col`.  
   - Token type constants: `NUMBER`, `STRING`, `ID`, `KEYWORD`, `OP`, `DELIM`, `EOF`.

2. **`lexer.py`**  
   - `Lexer` class that scans source text and returns a list of `Token`s.  
   - **Critical**: on an invalid character, raise  
     ```python
     raise SyntaxError(f"Invalid character: ...", (None, self.line, None, None))
     ```  
     This form ensures that `e.lineno` is set to the correct integer line.  
   - Handles integer, float, string literals (with escape sequences), identifiers, keywords, operators, delimiters, and single‑line comments (`#`).

3. **`opcodes.py`**  
   - Enum or constants for all bytecode instructions. The complete set remains unchanged.

4. **`code.py`**  
   - `Code` object that holds:
     - `bytecode`: list of `(opcode, operand)` tuples.
     - `constants`: list of literal values and nested `Code` objects (for functions).
     - `local_names`: list of parameter/local variable names (for functions).
     - `nlocals`: number of local slots.
     - `lines`: **debug line mapping** – an integer list with one entry per instruction, storing the source line number for that instruction.  
   - Provides an `emit(op, arg, line)` method that appends the instruction and the line number.

5. **`compiler.py`**  
   - `Compiler` class that uses recursive descent parsing.  
   - Emits a `Code` object for the top‑level script; each function definition yields a **separate** `Code` object (with its own constants, locals, and line mapping) that is stored as a constant in the enclosing scope.  
   - **Error handling**: all parse errors must raise an exception that inherits from `SyntaxError`.  
     Define  
     ```python
     class CompileError(SyntaxError):
         pass
     ```  
     in `compiler.py` and raise `CompileError(msg, (None, token.line, None, None))`.  
     This guarantees that a single `except SyntaxError` in `main.py` catches both lexical and syntactical errors.  
   - The compiler tracks the current token’s line number and passes it to `code.emit(op, arg, line)`.  
   - Variable resolution distinguishes global from local variables according to the scoping rules.

6. **`vm.py`**  
   - `VirtualMachine` class that executes a `Code` object.  
   - Maintains a call stack of frames; each frame carries the `Code`, an instruction pointer (`ip`), an operand stack, and an array of local variables.  
   - **Runtime error reporting**:  
     - Define a custom exception:  
       ```python
       class RuntimeError(Exception):
           def __init__(self, message, lineno):
               super().__init__(message)
               self.lineno = lineno
       ```  
     - On any runtime error (division by zero, undefined variable, type error, …), read the line number from `frame.code.lines[frame.ip]` and raise `RuntimeError(msg, line)`.  
   - **Type checks for operators**:  
     - `UNARY_MINUS`: if the operand is not a number (`int`/`float`), raise `RuntimeError` with the line.  
     - `COMPARE_OP` with `<`, `>`, `<=`, `>=`: if either operand is not a number, raise `RuntimeError` with the line.  
     - Arithmetic operators (`+`, `-`, `*`, `/`): already check division by zero; add a check that both operands are numbers, raising `RuntimeError` with the line otherwise.  
   - The `PRINT` opcode outputs values to `stdout`.

7. **`main.py`** – Command‑Line Entry Point  
   - Reads a source file path from `sys.argv[1]`.  
   - Opens and reads the source code.  
   - Runs the lexer, then the compiler.  
   - **Error handling**:  
     ```python
     try:
         tokens = Lexer(source).scan()
         code = Compiler(tokens).compile()
         VirtualMachine().run(code)
     except SyntaxError as e:
         print(f"Syntax error at line {e.lineno}: {e.msg}", file=sys.stderr)
         sys.exit(1)
     except RuntimeError as e:
         print(f"Runtime error at line {e.lineno}: {e.args[0]}", file=sys.stderr)
         sys.exit(1)
     ```  
     Because `CompileError` inherits from `SyntaxError`, all syntax errors (lexer and parser) are caught by the same handler.  
   - Normal `print` output goes to `stdout`.

8. **`examples/`** – Three Example Programs  
   Each file resides in the `examples/` directory and demonstrates the full feature set.

---

## Detailed Design – Must‑Have Fixes

### 1. Syntax Error Line Numbers

- **Lexer**: `raise SyntaxError(msg, (None, line, None, None))` ensures `e.lineno` is set.  
- **Compiler**: `CompileError` inherits `SyntaxError`; raised with `(msg, (None, token.line, None, None))` so that `e.lineno` contains the offending line.  
- **`main.py`** catches only `SyntaxError` – it covers both.

### 2. Runtime Error Line Numbers

- **`Code` object** carries a `lines` list.  
- **Compiler** records the current token’s line in every `emit()`.  
- **VM**’s `RuntimeError` is always created with `lineno = frame.code.lines[frame.ip]`.  
- **`main.py`** prints `Runtime error at line {e.lineno}: ...`.

### 3. Type Checks for Comparison and Unary Operators

- `UNARY_MINUS`: check `isinstance(a, (int, float))`.  
- `COMPARE_OP` with `<`, `>`, `<=`, `>=`: check both operands are numeric.  
- Failure raises `RuntimeError` with the current instruction’s line, never a raw `TypeError`.

### 4. Command‑Line Entry Point (`main.py`)

- Mandatory: accept source file as `sys.argv[1]`.  
- Read, lex, compile, run, handle errors as above.  
- No other interactive modes.

### 5. Three Example Programs (`examples/` directory)

The following source files **must** be present:

#### `examples/calculator.yal`
```
# Demonstrates arithmetic, precedence, parentheses, and print
x = 5 + 3 * 2;
print x;        # output 11
y = (x - 1) / 2;
print y;        # output 5
```

#### `examples/factorial.yal`
```
# Calculates factorial of 5 using a while loop
n = 5;
result = 1;
while (n > 1) {
    result = result * n;
    n = n - 1;
}
print result;   # output 120
```

#### `examples/fibonacci.yal`
```
# Recursive Fibonacci function
def fib(n, a, b) {
    if (n == 0) {
        return a;
    } else {
        return fib(n - 1, b, a + b);
    }
}
print fib(10, 0, 1);   # output 55
```

These programs exercise variables, arithmetic, conditionals, loops, functions (including recursion), parameters, return values, and `print`.

### 6. Function Compilation Isolation

- Each `def` statement creates a **new** `Code` object.  
- That object has its own `constants`, `local_names`, `nlocals`, and `lines` list.  
- No mutable state is shared with the parent scope, eliminating subtle variable resolution bugs.

---

## Implementation Order (Re‑confirmed)

1. `tokens.py` and `lexer.py` – with proper `SyntaxError` tuple.  
2. `opcodes.py` – full instruction set.  
3. `code.py` – `Code` with `lines` and `emit()`.  
4. `compiler.py` – parser with `CompileError(SyntaxError)`, line‑number recording, and isolated function code objects.  
5. `vm.py` – execution loop, custom `RuntimeError`, operand type guards, line‑number retrieval.  
6. `main.py` – command‑line driver, unified error handling.  
7. `examples/` – three specified source files.

---

## Summary

The revised plan eliminates every gap: syntax errors carry line numbers, runtime errors carry line numbers, dangerous type mismatches are caught early with line annotations, the system is invoked from a standard `main.py`, and example programs verify end‑to‑end correctness. All other features remain unchanged and functional.