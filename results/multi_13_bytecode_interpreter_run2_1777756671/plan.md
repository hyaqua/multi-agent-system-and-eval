# Bytecode Interpreter Implementation Plan

## Overview
We will build a simple programming language interpreter with three stages:
1. **Lexer** – converts source code into a stream of tokens.
2. **Compiler/Parser** – transforms tokens into a sequence of bytecode instructions.
3. **Virtual Machine (VM)** – executes the bytecode on a stack-based architecture.

The language supports variables, arithmetic, comparisons, `if`/`else`, `while` loops, function definitions/calls, and a `print` statement. The entire project uses only the Python standard library.

## Files and Their Purposes
| File | Purpose |
|------|---------|
| `tokens.py` | Defines `TokenType` enum and `Token` data class. |
| `lexer.py` | `Lexer` class that tokenizes source text into `Token` objects, tracks line numbers. |
| `compiler.py` | `Compiler` class that parses tokens and emits a list of `Instruction`s (bytecode). Includes parsing logic (recursive descent). |
| `vm.py` | `VirtualMachine` class that executes the instruction list using a stack, call stack, and variable scopes. |
| `main.py` | Entry point – reads source file from command‑line argument, runs the pipeline, and reports errors. |
| `examples/` | Directory containing at least three example programs that exercise all features. |

## Architecture and Interaction
```
Source file → Lexer → list[Token] → Compiler → (constant_pool, list[Instruction]) → VirtualMachine → output
```
- The `Lexer` reads a raw string and produces a flat list of `Token` objects, each with a type, literal value, and source line number.
- The `Compiler` consumes the token list using a recursive descent parser. It builds a **constant pool** (numbers, strings, function bytecode) and a linear list of `Instruction` objects. The global (top‑level) code is compiled as a “program” bytecode block.
- The `VirtualMachine` takes the program bytecode, the constant pool, and an initial global variable dictionary. It executes instructions one by one, maintaining:
  - a data stack (for expression evaluation)
  - a **call stack** of frames (`{ local_vars: dict, return_address: int }`)
  - an instruction pointer (`ip`)
  - a global variable dictionary
- Functions are compiled into separate bytecode blocks stored in the constant pool. A `MAKE_FUNCTION` instruction creates a function object from that block. A `CALL` instruction sets up a new frame, binds arguments to parameter names, and jumps to the function’s bytecode. `RET` unwinds the frame and pushes the return value back to the caller.

## Implementation Order
1. **`tokens.py`** – Define token types and the `Token` namedtuple/dataclass.  
2. **`lexer.py`** – Build the Lexer with full tokenization and comment handling.  
3. **`compiler.py`** – Implement the parser and bytecode emitter. Start with expressions and variable assignment, then add control flow and functions.  
4. **`vm.py`** – Implement the VM with basic arithmetic and variable handling, then extend to support conditionals, loops, and function calls.  
5. **`main.py`** – Wire everything together, add command‑line argument handling and error reporting.  
6. **`examples/`** – Write example programs and test the complete system.

## Libraries
- **Python 3 standard library only**. Use `sys` for command‑line arguments, `dataclasses` or `namedtuple` for data structures, and `enum` for token types. No external dependencies.

## Detailed Feature Implementation

### 1. Lexer
- **Token types:** `NUMBER` (int/float), `STRING`, `IDENTIFIER`, `KEYWORD` (if, else, while, def, print, return, end), `OPERATOR` (+, -, *, /, ==, !=, <, >, <=, >=, =), `DELIMITER` ( `:` , `,` , `(` , `)` ), `NEWLINE`, `EOF`.
- `Lexer.__init__(source)` stores the string, index, and current line number.
- `Lexer.tokenize()` loops over characters, skips whitespace, advances line numbers on `\n`.
- **Comments:** `//` until end of line; skip those characters.
- **Numbers:** read digits and optional decimal point; classify as `int` or `float`.
- **Strings:** read between `" "` supporting escape `\"` (basic).
- **Identifiers/keywords:** after checking keywords, return `IDENTIFIER` with the name.
- **Operators/delimiters:** match longest possible (e.g., `==` before `=`).
- Tokens carry a `line` attribute for error messages.

### 2. Compiler (Parser + Bytecode Emitter)
- **Grammar** (informal):  
  `program = statement_list`  
  `statement_list = { statement }` (end of block marked by `end` keyword or EOF)  
  `statement = assignment | if_statement | while_loop | function_def | print_statement | return_statement | expression`  
  `assignment = IDENTIFIER '=' expression`  
  `if_statement = 'if' expression ':' statement_list { 'else' ':' statement_list } 'end'`  
  `while_loop = 'while' expression ':' statement_list 'end'`  
  `function_def = 'def' IDENTIFIER '(' [IDENTIFIER {',' IDENTIFIER}] ')' ':' statement_list 'end'`  
  `print_statement = 'print' expression`  
  `return_statement = 'return' [ expression ]`  
  Expressions: standard precedence (comparison < addition < multiplication < unary < primary).  
  Primary: `NUMBER`, `STRING`, `IDENTIFIER`, `'(' expression ')'`, function_call.  
  Function call: `IDENTIFIER '(' [ expression {',' expression} ] ')'`.
- **Constant pool:** During parsing, collect numbers, strings, and function bytecode blocks in a list. Instructions reference constants by index.
- **Opcodes:**  
  `PUSH_CONST(index)`, `LOAD_VAR(name_index)`, `STORE_VAR(name_index)`, `POP`, `ADD`, `SUB`, `MUL`, `DIV`, `NEG`, `EQ`, `NE`, `LT`, `GT`, `LE`, `GE`, `NOT`, `JMP(offset)`, `JZ(offset)`, `CALL`, `RET`, `MAKE_FUNCTION(const_index)`, `PRINT`.
- **Parsing strategy:** Recursive descent.  
  - Expressions built with precedence climbing (`parse_expression(min_precedence)`).  
  - Statements expect newline as separator but ignore them after tokens; the main loop reads statements until a `DELIMITER` `:` or `end` is encountered. Blocks are delimited by `:` and `end`.
  - For `if`/`while`, emit conditional jumps using `JZ`. Backward jumps for loops are calculated by recording `ip` positions.
  - For function definitions: compile the function body into its own set of instructions and a parameter list, store that in the constant pool, then emit `MAKE_FUNCTION` with that constant index. The function object will be placed on the stack. To bind the function to a name, the definition is followed by an assignment (e.g., `def foo(x): … end` is equivalent to `foo = <function>`; we can automatically emit a `STORE_VAR` using the function name).
  - Return statements emit the expression (or a default `PUSH_CONST 0`) followed by `RET`.
- **Variable names:** Internally store all names (identifiers) in a name dictionary and refer to them by index. `STORE_VAR(name_idx)` and `LOAD_VAR(name_idx)` use that. This makes scope lookup cheap.
- **Error messages:** On syntax error, raise a custom `CompileError` with the current token’s line and a descriptive message.

### 3. Virtual Machine
- **State:** `ip` (instruction pointer), `stack`, `call_stack`, `globals` (dict), `current_frame` (local vars dict), `instructions`, `constants`, `names`.
- **Execution loop:** Fetch instruction, switch on opcode.
  - `PUSH_CONST`: push `constants[arg]` onto stack.
  - `LOAD_VAR`: get name from `names[arg]`; look in `current_frame` first, then `globals`; error if undefined (report line from instruction).
  - `STORE_VAR`: pop value, store in `current_frame` if inside a function (call stack not empty), else in `globals`.
  - Arithmetic/comparison ops: pop operands, perform operation, push result. `DIV` checks for division by zero.
  - `JMP`: add offset to `ip`.
  - `JZ`: pop value; if it’s falsy (0), jump by offset; else continue.
  - `POP`: discard top of stack.
  - `PRINT`: pop value, write to stdout.
  - `CALL`: pop function object from stack; then pop `arg_count` (stored in function object) values from stack, create new frame with `local_vars` populated from the parameter names, push return address (current `ip+1`) to call_stack, and jump to function’s bytecode.
  - `RET`: pop return value from stack; restore previous frame from call_stack (if any), set `ip` to return address, push return value onto caller’s stack. If no call_stack, program halts.
  - `MAKE_FUNCTION`: create a `Function` object (bytecode, parameter count, name list) from constant and push it.
- **Error handling:** On division by zero or undefined variable, raise `RuntimeError` with line number from the current instruction.

### 4. Command-Line Interface (`main.py`)
- Read file path from `sys.argv[1]`.
- Open and read the file.
- Run `Lexer`, get token list.
- Run `Compiler`, obtain `instructions` and `constants`.
- Instantiate `VirtualMachine` and call `execute()`.
- Catch `CompileError` or `RuntimeError`, print error with line number and exit with non-zero code.
- Otherwise, exit normally.

### 5. Example Programs
- `examples/arithmetic.lang`: Demonstrates variable assignment, arithmetic with parentheses, and `print`.
- `examples/control_flow.lang`: Shows `if/else`, `while` loop, comparison operators.
- `examples/functions.lang`: Defines a recursive factorial function, calls it, and prints the result; also shows return values and parameter passing.

All examples use the same syntax (blocks with `:` and `end`), illustrate both `int` and `float` usage, and cover edge cases like empty `else` or early `return`.

---

## Summary
The implementation builds a classic compiler pipeline: lexer → parser/emitter → stack VM. The design keeps scope handling simple (global + local frames), uses a constant pool for all literals and function code, and tracks source lines for accurate error reporting. The plan is ordered so that each component can be individually developed and tested before integration. The final system will accept a source file and execute it, printing output and providing clear error messages for syntax and runtime problems.