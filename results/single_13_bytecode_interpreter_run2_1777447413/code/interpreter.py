#!/usr/bin/env python3
"""
Bytecode Interpreter for a Simple Programming Language

Three stages:
  1. Lexer  - tokenizes source code
  2. Compiler - parses tokens into bytecode instructions
  3. VM - stack-based virtual machine that executes bytecode

Usage: python interpreter.py <source_file>
"""

import sys
from enum import Enum, auto
from typing import Any

# =============================================================================
# Token Types
# =============================================================================

class TokenType(Enum):
    # Literals
    INTEGER_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()

    # Identifier
    IDENTIFIER = auto()

    # Keywords
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    DEF = auto()
    RETURN = auto()
    PRINT = auto()

    # Operators
    PLUS = auto()        # +
    MINUS = auto()       # -
    STAR = auto()        # *
    SLASH = auto()       # /
    EQ = auto()          # ==
    NEQ = auto()         # !=
    LT = auto()          # <
    GT = auto()          # >
    LE = auto()          # <=
    GE = auto()          # >=
    ASSIGN = auto()      # =

    # Delimiters
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACE = auto()      # {
    RBRACE = auto()      # }
    COMMA = auto()       # ,
    SEMICOLON = auto()   # ;

    # Special
    EOF = auto()


KEYWORDS = {
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "def": TokenType.DEF,
    "return": TokenType.RETURN,
    "print": TokenType.PRINT,
}


class Token:
    def __init__(self, token_type: TokenType, value: Any, line: int):
        self.type = token_type
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"


# =============================================================================
# Lexer
# =============================================================================

class LexerError(Exception):
    def __init__(self, message: str, line: int):
        self.message = message
        self.line = line
        super().__init__(f"Lexer error at line {line}: {message}")


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1

    def tokenize(self) -> list:
        tokens = []
        while self.pos < len(self.source):
            c = self.source[self.pos]

            # Whitespace
            if c in " \t\r":
                self.pos += 1
                continue

            # Newline
            if c == "\n":
                self.line += 1
                self.pos += 1
                continue

            # Single-line comment
            if c == "/" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "/":
                self.pos += 2
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self.pos += 1
                continue

            # String literals
            if c == '"':
                tokens.append(self._read_string())
                continue

            # Numbers
            if c.isdigit():
                tokens.append(self._read_number())
                continue

            # Identifiers and keywords
            if c.isalpha() or c == "_":
                tokens.append(self._read_identifier())
                continue

            # Multi-character operators
            if c == "=":
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                    tokens.append(Token(TokenType.EQ, "==", self.line))
                    self.pos += 2
                else:
                    tokens.append(Token(TokenType.ASSIGN, "=", self.line))
                    self.pos += 1
                continue

            if c == "!":
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                    tokens.append(Token(TokenType.NEQ, "!=", self.line))
                    self.pos += 2
                else:
                    raise LexerError(f"Unexpected character '!' (did you mean '!='?)", self.line)
                continue

            if c == "<":
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                    tokens.append(Token(TokenType.LE, "<=", self.line))
                    self.pos += 2
                else:
                    tokens.append(Token(TokenType.LT, "<", self.line))
                    self.pos += 1
                continue

            if c == ">":
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                    tokens.append(Token(TokenType.GE, ">=", self.line))
                    self.pos += 2
                else:
                    tokens.append(Token(TokenType.GT, ">", self.line))
                    self.pos += 1
                continue

            # Single-character tokens
            single_char_map = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                ",": TokenType.COMMA,
                ";": TokenType.SEMICOLON,
            }

            if c in single_char_map:
                tokens.append(Token(single_char_map[c], c, self.line))
                self.pos += 1
                continue

            raise LexerError(f"Unexpected character: {c!r}", self.line)

        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens

    def _read_string(self) -> Token:
        line = self.line
        self.pos += 1  # skip opening quote
        result = []
        while self.pos < len(self.source):
            c = self.source[self.pos]
            if c == '"':
                self.pos += 1
                return Token(TokenType.STRING_LITERAL, "".join(result), line)
            if c == "\\" and self.pos + 1 < len(self.source):
                next_c = self.source[self.pos + 1]
                if next_c == '"':
                    result.append('"')
                elif next_c == "\\":
                    result.append("\\")
                elif next_c == "n":
                    result.append("\n")
                elif next_c == "t":
                    result.append("\t")
                else:
                    result.append(next_c)
                self.pos += 2
            elif c == "\n":
                raise LexerError("Unterminated string literal (newline in string)", line)
            else:
                result.append(c)
                self.pos += 1
        raise LexerError("Unterminated string literal", line)

    def _read_number(self) -> Token:
        line = self.line
        start = self.pos
        is_float = False
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            self.pos += 1
        if self.pos < len(self.source) and self.source[self.pos] == ".":
            # Check if next char is a digit (to distinguish from method calls like 5.foo)
            if self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                is_float = True
                self.pos += 1
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    self.pos += 1
        num_str = self.source[start:self.pos]
        if is_float:
            return Token(TokenType.FLOAT_LITERAL, float(num_str), line)
        else:
            return Token(TokenType.INTEGER_LITERAL, int(num_str), line)

    def _read_identifier(self) -> Token:
        line = self.line
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self.pos += 1
        name = self.source[start:self.pos]
        token_type = KEYWORDS.get(name, TokenType.IDENTIFIER)
        return Token(token_type, name, line)


# =============================================================================
# OpCodes
# =============================================================================

class OpCode(Enum):
    PUSH_CONST = auto()     # Push constant from constants pool
    LOAD_VAR = auto()       # Push variable value
    STORE_VAR = auto()      # Pop and store into variable
    POP = auto()            # Discard top of stack
    ADD = auto()            # a + b
    SUB = auto()            # a - b
    MUL = auto()            # a * b
    DIV = auto()            # a / b
    NEG = auto()            # -a
    EQ = auto()             # a == b
    NEQ = auto()            # a != b
    LT = auto()             # a < b
    GT = auto()             # a > b
    LE = auto()             # a <= b
    GE = auto()             # a >= b
    JMP = auto()            # Unconditional jump
    JMP_IF_FALSE = auto()   # Pop and jump if falsy
    CALL = auto()           # Call function
    RETURN = auto()         # Return from function
    PRINT = auto()          # Print top of stack
    HALT = auto()           # Stop execution


# =============================================================================
# Compiler
# =============================================================================

class CompilerError(Exception):
    def __init__(self, message: str, line: int):
        self.message = message
        self.line = line
        super().__init__(f"Syntax error at line {line}: {message}")


class FunctionPrototype:
    """Stores compiled function information."""
    def __init__(self, name: str, params: list, bytecode: list, constants: list):
        self.name = name
        self.params = params
        self.bytecode = bytecode
        self.constants = constants


class Compiler:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0
        self.instructions: list = []   # Each: (OpCode, operand, line)
        self.constants: list = []      # Constants pool

    def compile(self) -> tuple:
        """Returns (instructions, constants)."""
        self._parse_program()
        return self.instructions, self.constants

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _peek(self) -> Token:
        return self._current()

    def _advance(self) -> Token:
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, token_type: TokenType, error_msg: str = None) -> Token:
        tok = self._peek()
        if tok.type != token_type:
            if error_msg is None:
                error_msg = f"Expected {token_type.name}, got {tok.type.name} ({tok.value!r})"
            raise CompilerError(error_msg, tok.line)
        return self._advance()

    def _match(self, token_type: TokenType) -> bool:
        if self._peek().type == token_type:
            self._advance()
            return True
        return False

    def _add_constant(self, value: Any) -> int:
        """Add a constant to the pool and return its index."""
        self.constants.append(value)
        return len(self.constants) - 1

    def _emit(self, opcode: OpCode, operand: Any, line: int):
        self.instructions.append((opcode, operand, line))

    def _emit_line(self, opcode: OpCode, operand: Any):
        """Emit with current token's line number."""
        self.instructions.append((opcode, operand, self._current().line))

    # ------------------------------------------------------------------
    # Program = Statement*
    # ------------------------------------------------------------------

    def _parse_program(self):
        while self._peek().type != TokenType.EOF:
            self._parse_statement()
            # Optional semicolon after statement
            self._match(TokenType.SEMICOLON)
        self._emit_line(OpCode.HALT, None)

    # ------------------------------------------------------------------
    # Statement parsing
    # ------------------------------------------------------------------

    def _parse_statement(self):
        tok = self._peek()

        if tok.type == TokenType.IF:
            self._parse_if()
        elif tok.type == TokenType.WHILE:
            self._parse_while()
        elif tok.type == TokenType.DEF:
            self._parse_function_def()
        elif tok.type == TokenType.RETURN:
            self._parse_return()
        elif tok.type == TokenType.PRINT:
            self._parse_print()
        elif tok.type == TokenType.LBRACE:
            self._parse_block()
        elif tok.type == TokenType.IDENTIFIER:
            # Could be assignment or expression statement
            # Look ahead: if next is ASSIGN, it's assignment
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.ASSIGN:
                self._parse_assignment()
            else:
                self._parse_expr_statement()
        elif tok.type in (TokenType.INTEGER_LITERAL, TokenType.FLOAT_LITERAL,
                          TokenType.STRING_LITERAL, TokenType.LPAREN,
                          TokenType.MINUS, TokenType.PLUS):
            self._parse_expr_statement()
        elif tok.type == TokenType.SEMICOLON:
            self._advance()  # Empty statement
        elif tok.type == TokenType.RBRACE:
            return  # End of block, handled by caller
        elif tok.type == TokenType.EOF:
            return
        else:
            raise CompilerError(f"Unexpected token: {tok.type.name} ({tok.value!r})", tok.line)

    def _parse_assignment(self):
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected variable name")
        self._expect(TokenType.ASSIGN, "Expected '='")
        self._parse_expr()
        self._emit(OpCode.STORE_VAR, name_tok.value, name_tok.line)

    def _parse_expr_statement(self):
        self._parse_expr()
        # Expression value is discarded
        self._emit_line(OpCode.POP, None)

    def _parse_if(self):
        line = self._advance().line  # 'if'
        self._expect(TokenType.LPAREN, "Expected '(' after 'if'")
        self._parse_expr()
        self._expect(TokenType.RPAREN, "Expected ')' after if condition")

        # Jump past the if-body if condition is false
        # We'll emit JMP_IF_FALSE with a placeholder; patch later
        jump_to_else_idx = len(self.instructions)
        self._emit(OpCode.JMP_IF_FALSE, -1, line)

        self._parse_statement()  # if-body (could be a block or single statement)
        self._match(TokenType.SEMICOLON)

        if self._match(TokenType.ELSE):
            # Jump past else-body after if-body completes
            jump_to_end_idx = len(self.instructions)
            self._emit(OpCode.JMP, -1, self._current().line)

            # Patch the JMP_IF_FALSE to jump here (to else-body)
            self.instructions[jump_to_else_idx] = (OpCode.JMP_IF_FALSE, len(self.instructions), line)

            self._parse_statement()  # else-body
            self._match(TokenType.SEMICOLON)

            # Patch the JMP to jump past else-body
            self.instructions[jump_to_end_idx] = (OpCode.JMP, len(self.instructions), self.instructions[jump_to_end_idx][2])
        else:
            # Patch JMP_IF_FALSE to jump past if-body
            self.instructions[jump_to_else_idx] = (OpCode.JMP_IF_FALSE, len(self.instructions), line)

    def _parse_while(self):
        line = self._advance().line  # 'while'
        loop_start = len(self.instructions)

        self._expect(TokenType.LPAREN, "Expected '(' after 'while'")
        self._parse_expr()
        self._expect(TokenType.RPAREN, "Expected ')' after while condition")

        # Jump past loop body if condition is false
        jump_to_end_idx = len(self.instructions)
        self._emit(OpCode.JMP_IF_FALSE, -1, line)

        self._parse_statement()  # loop body
        self._match(TokenType.SEMICOLON)

        # Jump back to condition
        self._emit(OpCode.JMP, loop_start, line)

        # Patch the JMP_IF_FALSE
        end_pos = len(self.instructions)
        self.instructions[jump_to_end_idx] = (OpCode.JMP_IF_FALSE, end_pos, line)

    def _parse_function_def(self):
        line = self._advance().line  # 'def'
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected function name")
        func_name = name_tok.value

        self._expect(TokenType.LPAREN, "Expected '(' after function name")
        params = self._parse_params()
        self._expect(TokenType.RPAREN, "Expected ')' after parameters")

        # Compile the function body
        body_instructions, body_constants = self._compile_function_body(params)

        # Add an implicit return if the body doesn't end with one
        if not body_instructions or body_instructions[-1][0] != OpCode.RETURN:
            # Push None and return
            none_idx = len(body_constants)
            body_constants.append(None)
            body_instructions.append((OpCode.PUSH_CONST, none_idx, line))
            body_instructions.append((OpCode.RETURN, None, line))

        # Create function prototype and add to constants pool
        func_proto = FunctionPrototype(func_name, params, body_instructions, body_constants)
        const_idx = self._add_constant(func_proto)

        # Emit code to load the function and store it in a variable
        self._emit(OpCode.PUSH_CONST, const_idx, line)
        self._emit(OpCode.STORE_VAR, func_name, line)

    def _compile_function_body(self, params: list) -> tuple:
        """Compile statements inside { } as a function body. Returns (instructions, constants)."""
        # Save current compiler state
        saved_instructions = self.instructions
        saved_constants = self.constants

        self.instructions = []
        self.constants = []

        self._expect(TokenType.LBRACE, "Expected '{' to start function body")

        while self._peek().type != TokenType.RBRACE and self._peek().type != TokenType.EOF:
            self._parse_statement()
            self._match(TokenType.SEMICOLON)

        self._expect(TokenType.RBRACE, "Expected '}' to close function body")

        result = (self.instructions, self.constants)

        # Restore compiler state
        self.instructions = saved_instructions
        self.constants = saved_constants

        return result

    def _parse_params(self) -> list:
        """Parse function parameters. Returns list of parameter name strings."""
        params = []
        if self._peek().type == TokenType.IDENTIFIER:
            params.append(self._advance().value)
            while self._match(TokenType.COMMA):
                params.append(self._expect(TokenType.IDENTIFIER, "Expected parameter name").value)
        return params

    def _parse_return(self):
        line = self._advance().line  # 'return'
        if self._peek().type in (TokenType.SEMICOLON, TokenType.RBRACE, TokenType.EOF):
            # Return with no value -> return None
            none_idx = self._add_constant(None)
            self._emit(OpCode.PUSH_CONST, none_idx, line)
        else:
            self._parse_expr()
        self._emit(OpCode.RETURN, None, line)

    def _parse_print(self):
        line = self._advance().line  # 'print'
        self._expect(TokenType.LPAREN, "Expected '(' after 'print'")
        self._parse_expr()
        self._expect(TokenType.RPAREN, "Expected ')' after print argument")
        self._emit(OpCode.PRINT, None, line)

    def _parse_block(self):
        self._advance()  # '{'
        while self._peek().type != TokenType.RBRACE and self._peek().type != TokenType.EOF:
            self._parse_statement()
            self._match(TokenType.SEMICOLON)
        self._expect(TokenType.RBRACE, "Expected '}' to close block")

    # ------------------------------------------------------------------
    # Expression parsing (recursive descent with precedence)
    # ------------------------------------------------------------------

    def _parse_expr(self):
        """Lowest precedence: comparison operators."""
        self._parse_comparison()

    def _parse_comparison(self):
        """comparison → addition (('==' | '!=' | '<' | '>' | '<=' | '>=') addition)*"""
        self._parse_addition()
        while self._peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT,
                                      TokenType.GT, TokenType.LE, TokenType.GE):
            op_tok = self._advance()
            self._parse_addition()
            op_map = {
                TokenType.EQ: OpCode.EQ,
                TokenType.NEQ: OpCode.NEQ,
                TokenType.LT: OpCode.LT,
                TokenType.GT: OpCode.GT,
                TokenType.LE: OpCode.LE,
                TokenType.GE: OpCode.GE,
            }
            self._emit(op_map[op_tok.type], None, op_tok.line)

    def _parse_addition(self):
        """addition → multiplication (('+' | '-') multiplication)*"""
        self._parse_multiplication()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            self._parse_multiplication()
            if op_tok.type == TokenType.PLUS:
                self._emit(OpCode.ADD, None, op_tok.line)
            else:
                self._emit(OpCode.SUB, None, op_tok.line)

    def _parse_multiplication(self):
        """multiplication → unary (('*' | '/') unary)*"""
        self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH):
            op_tok = self._advance()
            self._parse_unary()
            if op_tok.type == TokenType.STAR:
                self._emit(OpCode.MUL, None, op_tok.line)
            else:
                self._emit(OpCode.DIV, None, op_tok.line)

    def _parse_unary(self):
        """unary → '-' unary | primary"""
        if self._match(TokenType.MINUS):
            line = self.tokens[self.pos - 1].line if self.pos > 0 else self._current().line
            self._parse_unary()
            self._emit(OpCode.NEG, None, line)
        else:
            self._parse_primary()

    def _parse_primary(self):
        """primary → NUMBER | STRING | IDENTIFIER ('(' args? ')')? | '(' expr ')'"""
        tok = self._peek()

        if tok.type == TokenType.INTEGER_LITERAL:
            self._advance()
            idx = self._add_constant(tok.value)
            self._emit(OpCode.PUSH_CONST, idx, tok.line)

        elif tok.type == TokenType.FLOAT_LITERAL:
            self._advance()
            idx = self._add_constant(tok.value)
            self._emit(OpCode.PUSH_CONST, idx, tok.line)

        elif tok.type == TokenType.STRING_LITERAL:
            self._advance()
            idx = self._add_constant(tok.value)
            self._emit(OpCode.PUSH_CONST, idx, tok.line)

        elif tok.type == TokenType.IDENTIFIER:
            name_tok = self._advance()
            if self._match(TokenType.LPAREN):
                # Function call
                arg_count = self._parse_args()
                self._expect(TokenType.RPAREN, "Expected ')' after function arguments")
                # Load the function variable
                self._emit(OpCode.LOAD_VAR, name_tok.value, name_tok.line)
                self._emit(OpCode.CALL, arg_count, name_tok.line)
            else:
                # Variable reference
                self._emit(OpCode.LOAD_VAR, name_tok.value, name_tok.line)

        elif tok.type == TokenType.LPAREN:
            self._advance()
            self._parse_expr()
            self._expect(TokenType.RPAREN, "Expected ')'")

        else:
            raise CompilerError(f"Unexpected token in expression: {tok.type.name} ({tok.value!r})", tok.line)

    def _parse_args(self) -> int:
        """Parse function call arguments. Returns the number of arguments."""
        count = 0
        if self._peek().type != TokenType.RPAREN:
            self._parse_expr()
            count += 1
            while self._match(TokenType.COMMA):
                self._parse_expr()
                count += 1
        return count


# =============================================================================
# Virtual Machine
# =============================================================================

class RuntimeError_(Exception):
    def __init__(self, message: str, line: int):
        self.message = message
        self.line = line
        super().__init__(f"Runtime error at line {line}: {message}")


class VM:
    def __init__(self, instructions: list, constants: list):
        self.instructions = instructions
        self.constants = constants
        self.stack: list = []              # Value stack
        self.globals: dict = {}            # Global variables
        self.frames: list = []             # Call stack: list of Frame dicts

    def run(self):
        """Execute the bytecode."""
        # Create top-level frame
        frame = {
            'ip': 0,
            'locals': {},          # Local variables for this frame
            'bytecode': self.instructions,
            'constants': self.constants,
        }
        self.frames.append(frame)

        while self.frames:
            f = self.frames[-1]
            ip = f['ip']

            if ip >= len(f['bytecode']):
                # Implicit return from top-level or function
                self.frames.pop()
                continue

            instr = f['bytecode'][ip]
            opcode, operand, line = instr
            f['ip'] = ip + 1

            try:
                self._execute(opcode, operand, line, f)
            except RuntimeError_:
                raise
            except Exception as e:
                raise RuntimeError_(str(e), line)

    def _execute(self, opcode: OpCode, operand: Any, line: int, frame: dict):
        if opcode == OpCode.PUSH_CONST:
            value = frame['constants'][operand]
            if isinstance(value, FunctionPrototype):
                # Create a runtime function object
                value = Function(value.name, value.params, value.bytecode, value.constants)
            self.stack.append(value)

        elif opcode == OpCode.LOAD_VAR:
            name = operand
            # Check locals first, then globals
            for f in reversed(self.frames):
                if name in f['locals']:
                    self.stack.append(f['locals'][name])
                    break
            else:
                if name in self.globals:
                    self.stack.append(self.globals[name])
                else:
                    raise RuntimeError_(f"Undefined variable: {name!r}", line)

        elif opcode == OpCode.STORE_VAR:
            name = operand
            if not self.stack:
                raise RuntimeError_("Stack underflow on STORE_VAR", line)
            value = self.stack.pop()
            # Store in current frame's locals (or globals for top-level)
            if len(self.frames) == 1:
                self.globals[name] = value
                self.frames[-1]['locals'][name] = value
            else:
                self.frames[-1]['locals'][name] = value

        elif opcode == OpCode.POP:
            if self.stack:
                self.stack.pop()

        elif opcode == OpCode.ADD:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(a + b)

        elif opcode == OpCode.SUB:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(a - b)

        elif opcode == OpCode.MUL:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(a * b)

        elif opcode == OpCode.DIV:
            b = self._pop_op(line)
            a = self._pop_op(line)
            if b == 0:
                raise RuntimeError_("Division by zero", line)
            self.stack.append(a / b)

        elif opcode == OpCode.NEG:
            a = self._pop_op(line)
            self.stack.append(-a)

        elif opcode == OpCode.EQ:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a == b else 0)

        elif opcode == OpCode.NEQ:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a != b else 0)

        elif opcode == OpCode.LT:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a < b else 0)

        elif opcode == OpCode.GT:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a > b else 0)

        elif opcode == OpCode.LE:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a <= b else 0)

        elif opcode == OpCode.GE:
            b = self._pop_op(line)
            a = self._pop_op(line)
            self.stack.append(1 if a >= b else 0)

        elif opcode == OpCode.JMP:
            frame['ip'] = operand

        elif opcode == OpCode.JMP_IF_FALSE:
            condition = self._pop_op(line)
            if not condition:
                frame['ip'] = operand

        elif opcode == OpCode.CALL:
            arg_count = operand
            # Pop function object
            if not self.stack:
                raise RuntimeError_("Stack underflow on CALL (expected function)", line)
            func = self.stack.pop()
            if not isinstance(func, Function):
                raise RuntimeError_(f"Object is not callable: {func!r}", line)

            # Pop arguments
            if len(self.stack) < arg_count:
                raise RuntimeError_(f"Stack underflow: expected {arg_count} arguments", line)

            args = []
            for _ in range(arg_count):
                args.append(self.stack.pop())
            args.reverse()

            if len(args) != len(func.params):
                raise RuntimeError_(
                    f"Function '{func.name}' expects {len(func.params)} arguments, got {len(args)}",
                    line
                )

            # Create new frame
            new_locals = dict(zip(func.params, args))
            new_frame = {
                'ip': 0,
                'locals': new_locals,
                'bytecode': func.bytecode,
                'constants': func.constants,
                'return_addr': frame['ip'],   # where to resume in caller
            }
            self.frames.append(new_frame)

        elif opcode == OpCode.RETURN:
            # Pop return value
            ret_val = None
            if self.stack:
                ret_val = self.stack.pop()

            # Pop current frame, capturing its return_addr
            returning_frame = self.frames.pop()
            resume_addr = returning_frame.get('return_addr')

            if self.frames:
                # Resume caller at the callee's return_addr
                caller = self.frames[-1]
                if resume_addr is not None:
                    caller['ip'] = resume_addr
                # Push return value onto caller's stack
                self.stack.append(ret_val)
            # If no frames left, we're done (HALT will stop the loop)

        elif opcode == OpCode.PRINT:
            val = self._pop_op(line)
            # Format output
            if isinstance(val, str):
                sys.stdout.write(val)
            elif isinstance(val, float):
                # Clean float display
                if val == int(val) and not (val != val):  # not NaN
                    sys.stdout.write(str(int(val)))
                else:
                    sys.stdout.write(repr(val))
            elif val is None:
                sys.stdout.write("null")
            else:
                sys.stdout.write(str(val))
            sys.stdout.write("\n")
            sys.stdout.flush()

        elif opcode == OpCode.HALT:
            # Clear frames to stop execution
            self.frames.clear()

    def _pop_op(self, line: int) -> Any:
        if not self.stack:
            raise RuntimeError_("Stack underflow", line)
        return self.stack.pop()


class Function:
    """Runtime function object."""
    def __init__(self, name: str, params: list, bytecode: list, constants: list):
        self.name = name
        self.params = params
        self.bytecode = bytecode
        self.constants = constants

    def __repr__(self):
        return f"<Function {self.name}({', '.join(self.params)})>"


# =============================================================================
# Main Entry Point
# =============================================================================

def run_source(source: str, filename: str = "<source>"):
    """Run source code through the full pipeline: lex -> compile -> execute."""
    # Stage 1: Lex
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Stage 2: Compile
    try:
        compiler = Compiler(tokens)
        instructions, constants = compiler.compile()
    except CompilerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Stage 3: Execute
    try:
        vm = VM(instructions, constants)
        vm.run()
    except RuntimeError_ as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python interpreter.py <source_file>", file=sys.stderr)
        print("       python interpreter.py --example <number>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--example":
        run_example(sys.argv[2] if len(sys.argv) > 2 else "1")
        return

    filepath = sys.argv[1]
    try:
        with open(filepath, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    run_source(source, filepath)


def run_example(num: str):
    """Run one of the built-in examples."""
    examples = {
        "1": """
// Example 1: Arithmetic and Printing
// Demonstrates: variables, arithmetic with precedence, print, comments

x = 10;
y = x * 3 + 5;
print(x);
print(y);

// Operator precedence: * and / before + and -
print(2 + 3 * 4);
print((2 + 3) * 4);

// Float and integer literals
pi = 3.14;
print(pi * 2.0);

// String literals
print("Hello, World!");
print("Line 1\\nLine 2");

// Comparison operators
a = 10;
b = 20;
print(a == b);
print(a != b);
print(a < b);
print(a > b);
print(a <= b);
print(a >= b);
""",

        "2": """
// Example 2: Conditionals and Loops
// Demonstrates: if/else, while loops, nested conditionals

n = 10;
if (n > 5) {
    print(1);
} else {
    print(0);
}

// While loop counting down
i = 5;
while (i > 0) {
    print(i);
    i = i - 1;
}
print("Done!");

// Summation loop
sum = 0;
j = 1;
while (j <= 10) {
    sum = sum + j;
    j = j + 1;
}
print(sum);

// Nested conditionals
val = 15;
if (val > 10) {
    if (val < 20) {
        print(999);
    }
}

// Using comparisons in conditionals
x = 7;
if (x == 7) {
    print("seven");
}
if (x != 8) {
    print("not eight");
}
""",

        "3": """
// Example 3: Functions
// Demonstrates: function definitions, parameters, return values, recursion

def add(a, b) {
    return a + b;
}

print(add(3, 4));
print(add(10, 20));

// Factorial with recursion
def factorial(n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

print(factorial(5));
print(factorial(7));

// Function with no return value
def greet(name) {
    print("Hello,");
    print(name);
}
greet("World");

// Multiple parameters
def multiply3(x, y, z) {
    return x * y * z;
}
print(multiply3(2, 3, 4));

// Function calling another function
def square(x) {
    return x * x;
}
def sum_of_squares(a, b) {
    return square(a) + square(b);
}
print(sum_of_squares(3, 4));
""",
    }

    source = examples.get(num)
    if source is None:
        print(f"Example {num} not found. Available: {', '.join(examples.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Running Example {num} ===\n")
    run_source(source, f"example{num}.lang")


if __name__ == "__main__":
    main()
