"""Compiler: recursive descent parser that emits bytecode for the VM."""

from typing import List, Optional

from lexer import Token, EOF, NEWLINE, INDENT, DEDENT, NUMBER, STRING, IDENTIFIER
from lexer import PRINT, IF, ELSE, WHILE, DEF, RETURN
from lexer import PLUS, MINUS, STAR, SLASH, EQ
from lexer import EQ_EQ, NOT_EQ, LT, GT, LE, GE
from lexer import LPAREN, RPAREN, COLON, COMMA
from opcodes import Opcode, CodeObject, BINARY_OPS, COMPARE_OPS


class SyntaxError(Exception):
    """Raised for syntax errors during compilation."""

    def __init__(self, message: str, line_no: int = 0):
        super().__init__(f"Syntax error at line {line_no}: {message}")
        self.line_no = line_no


# Precedence levels (higher = binds tighter)
PRECEDENCE = {
    'assignment': 1,
    'comparison': 2,
    'addition': 3,
    'multiplication': 4,
}

COMPARISON_TOKENS = {EQ_EQ, NOT_EQ, LT, GT, LE, GE}
ADDITION_TOKENS = {PLUS, MINUS}
MULTIPLICATION_TOKENS = {STAR, SLASH}

# Tokens that can start a statement
STATEMENT_STARTERS = {PRINT, IF, WHILE, DEF, RETURN, IDENTIFIER}


class Compiler:
    """Compiles a token stream into a CodeObject."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.code = CodeObject()
        self.in_function = False

    def compile(self) -> CodeObject:
        """Compile the token stream into a CodeObject."""
        self.parse_module()
        return self.code

    def parse_module(self) -> None:
        """Parse the top-level module."""
        self.skip_newlines()
        while not self.is_at_end():
            self.parse_statement()
            self.skip_newlines()

        # Implicit return None at end of module
        self.code.emit(Opcode.PUSH_CONST, self.code.add_constant(None))
        self.code.emit(Opcode.RETURN)

    # ── helpers ─────────────────────────────────────────────────────

    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(EOF, None, 0)

    def peek(self, offset: int = 1) -> Token:
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return Token(EOF, None, 0)

    def advance(self) -> Token:
        tok = self.current()
        self.pos += 1
        return tok

    def expect(self, token_type: str, error_msg: str = "") -> Token:
        tok = self.current()
        if tok.type != token_type:
            msg = error_msg or f"Expected {token_type}, got {tok}"
            raise SyntaxError(msg, tok.line_no)
        return self.advance()

    def skip_newlines(self) -> None:
        """Consume any NEWLINE tokens."""
        while self.current().type == NEWLINE:
            self.advance()

    def is_at_end(self) -> bool:
        return self.current().type == EOF

    def skip_to_next_statement(self) -> None:
        """Skip NEWLINEs and look ahead."""
        self.skip_newlines()

    # ── statement parsing ───────────────────────────────────────────

    def parse_statement(self) -> None:
        """Parse a single statement."""
        tok = self.current()

        if tok.type == PRINT:
            self.parse_print()
        elif tok.type == IF:
            self.parse_if()
        elif tok.type == WHILE:
            self.parse_while()
        elif tok.type == DEF:
            self.parse_def()
        elif tok.type == RETURN:
            self.parse_return()
        elif tok.type == IDENTIFIER:
            # Could be assignment or function call expression
            if self.peek().type == EQ:
                self.parse_assignment()
            else:
                # Expression statement (function call, etc.)
                self.parse_expression()
                # Discard the result value by emitting a POP-like behavior.
                # We'll add a POP opcode, or just push None over it.
                # Actually, for expression statements, the value remains
                # on the stack. We need to pop it. Let's add POP to opcodes.
                # But for now, we can just not worry — the value will be
                # cleaned up. However this can cause stack growth.
                # Let me add a POP opcode to handle this properly.
                self.code.emit(Opcode.POP, None, tok.line_no)
        elif tok.type == NEWLINE:
            self.advance()
        else:
            raise SyntaxError(f"Unexpected token: {tok}", tok.line_no)

    def parse_print(self) -> None:
        """Parse 'print expr'."""
        tok = self.advance()  # consume PRINT
        self.parse_expression()
        self.code.emit(Opcode.PRINT, None, tok.line_no)

    def parse_assignment(self) -> None:
        """Parse 'name = expr'."""
        name_tok = self.expect(IDENTIFIER, "Expected variable name")
        self.expect(EQ, "Expected '='")
        self.parse_expression()
        self.code.emit(Opcode.STORE_VAR, name_tok.value, name_tok.line_no)

    def parse_if(self) -> None:
        """Parse 'if expr: block [else: block]'."""
        tok = self.advance()  # consume IF
        self.parse_expression()
        self.expect(COLON, "Expected ':' after if condition")

        # Expect NEWLINE then INDENT
        self.expect(NEWLINE, "Expected newline after ':'")
        self.expect(INDENT, "Expected indented block after if")

        # Emit JUMP_IF_FALSE with placeholder; patch later
        jump_if_false_idx = len(self.code.instructions)
        self.code.emit(Opcode.JUMP_IF_FALSE, 0, tok.line_no)

        # Parse the if-body
        self.skip_newlines()
        while not self.is_at_end() and self.current().type != DEDENT:
            self.parse_statement()
            self.skip_newlines()

        # Consume DEDENT
        if self.current().type == DEDENT:
            self.advance()

        # Check for else
        self.skip_newlines()
        has_else = self.current().type == ELSE
        if has_else:
            # Emit unconditional jump over else block
            jump_over_else_idx = len(self.code.instructions)
            self.code.emit(Opcode.JUMP, 0, tok.line_no)
            # Patch the JUMP_IF_FALSE to jump to here (start of else block)
            target = len(self.code.instructions)
            self.patch_jump(jump_if_false_idx, target)
            # Parse else
            self.advance()  # consume ELSE
            self.expect(COLON, "Expected ':' after else")
            self.expect(NEWLINE, "Expected newline after ':'")
            self.expect(INDENT, "Expected indented block after else")
            self.skip_newlines()
            while not self.is_at_end() and self.current().type != DEDENT:
                self.parse_statement()
                self.skip_newlines()
            if self.current().type == DEDENT:
                self.advance()
            # Patch the unconditional jump to after the else block
            target_after_else = len(self.code.instructions)
            self.patch_jump(jump_over_else_idx, target_after_else)
        else:
            # Patch JUMP_IF_FALSE to after the if-body
            target = len(self.code.instructions)
            self.patch_jump(jump_if_false_idx, target)

    def parse_while(self) -> None:
        """Parse 'while expr: block'."""
        tok = self.advance()  # consume WHILE
        loop_start = len(self.code.instructions)
        self.parse_expression()
        self.expect(COLON, "Expected ':' after while condition")
        self.expect(NEWLINE, "Expected newline after ':'")
        self.expect(INDENT, "Expected indented block after while")

        # Emit JUMP_IF_FALSE with placeholder
        jump_if_false_idx = len(self.code.instructions)
        self.code.emit(Opcode.JUMP_IF_FALSE, 0, tok.line_no)

        # Parse body
        self.skip_newlines()
        while not self.is_at_end() and self.current().type != DEDENT:
            self.parse_statement()
            self.skip_newlines()

        # Consume DEDENT
        if self.current().type == DEDENT:
            self.advance()

        # Jump back to loop start
        back_offset = loop_start - len(self.code.instructions) - 1
        self.code.emit(Opcode.JUMP, back_offset, tok.line_no)

        # Patch the exit jump
        target = len(self.code.instructions)
        self.patch_jump(jump_if_false_idx, target)

    def parse_def(self) -> None:
        """Parse 'def name(params): block' and compile the body."""
        tok = self.advance()  # consume DEF
        name_tok = self.expect(IDENTIFIER, "Expected function name")
        self.expect(LPAREN, "Expected '(' after function name")
        params = self.parse_param_list()
        self.expect(COLON, "Expected ':' after function definition")
        self.expect(NEWLINE, "Expected newline after ':'")
        self.expect(INDENT, "Expected indented block after function definition")

        # Save current code context
        old_code = self.code
        old_in_func = self.in_function
        self.code = CodeObject(name=name_tok.value)
        self.in_function = True

        # Set up parameters
        self.code.param_count = len(params)
        self.code.param_names = params

        # Parse function body
        self.skip_newlines()
        while not self.is_at_end() and self.current().type != DEDENT:
            self.parse_statement()
            self.skip_newlines()

        # Consume DEDENT
        if self.current().type == DEDENT:
            self.advance()

        # Implicit return None at end
        self.code.emit(Opcode.PUSH_CONST, self.code.add_constant(None))
        self.code.emit(Opcode.RETURN, None, tok.line_no)

        func_code = self.code
        self.code = old_code
        self.in_function = old_in_func

        # Add function CodeObject to constants and emit DEF_FUNC + STORE_VAR
        const_idx = self.code.add_constant(func_code)
        self.code.emit(Opcode.DEF_FUNC, const_idx, tok.line_no)
        self.code.emit(Opcode.STORE_VAR, name_tok.value, tok.line_no)

    def parse_return(self) -> None:
        """Parse 'return expr'."""
        tok = self.advance()  # consume RETURN
        if not self.in_function:
            raise SyntaxError("'return' outside of function", tok.line_no)
        # Check if bare return (next token is NEWLINE, DEDENT, or EOF)
        if self.current().type in (NEWLINE, EOF, DEDENT):
            # bare return → return None
            self.code.emit(Opcode.PUSH_CONST, self.code.add_constant(None), tok.line_no)
        else:
            self.parse_expression()
        self.code.emit(Opcode.RETURN, None, tok.line_no)

    def parse_param_list(self) -> List[str]:
        """Parse a parameter list: (name, name, ...) """
        params: List[str] = []
        if self.current().type == RPAREN:
            self.advance()
            return params
        # Parse first parameter
        tok = self.expect(IDENTIFIER, "Expected parameter name")
        params.append(tok.value)
        while self.current().type == COMMA:
            self.advance()  # consume ','
            tok = self.expect(IDENTIFIER, "Expected parameter name")
            params.append(tok.value)
        self.expect(RPAREN, "Expected ')' after parameter list")
        return params

    # ── expression parsing (precedence climbing) ────────────────────

    def parse_expression(self, min_prec: int = 0) -> None:
        """Parse an expression using precedence climbing."""
        # Parse prefix (atom or unary)
        self.parse_prefix()

        # Parse infix operators while precedence >= min_prec
        while True:
            tok = self.current()
            prec = self.get_precedence(tok.type)
            if prec is None or prec < min_prec:
                break
            self.advance()  # consume operator
            # Parse right-hand side with higher precedence
            self.parse_expression(prec + 1)
            # Emit the operation
            self.emit_operator(tok)

    def parse_prefix(self) -> None:
        """Parse a prefix expression (atom or unary operator)."""
        tok = self.current()

        if tok.type == NUMBER:
            self.advance()
            self.code.emit(Opcode.PUSH_CONST, self.code.add_constant(tok.value), tok.line_no)

        elif tok.type == STRING:
            self.advance()
            self.code.emit(Opcode.PUSH_CONST, self.code.add_constant(tok.value), tok.line_no)

        elif tok.type == IDENTIFIER:
            self.advance()
            # Check for function call
            if self.current().type == LPAREN:
                self.parse_function_call(tok)
            else:
                self.code.emit(Opcode.LOAD_VAR, tok.value, tok.line_no)

        elif tok.type == LPAREN:
            self.advance()
            self.parse_expression()
            self.expect(RPAREN, "Expected ')'")

        elif tok.type == MINUS:
            # Unary minus
            self.advance()
            self.parse_prefix()
            self.code.emit(Opcode.UNARY_NEG, None, tok.line_no)

        elif tok.type == PLUS:
            # Unary plus: just parse the operand (no-op)
            self.advance()
            self.parse_prefix()

        else:
            raise SyntaxError(f"Unexpected token in expression: {tok}", tok.line_no)

    def parse_function_call(self, name_tok: Token) -> None:
        """Parse function call arguments and emit CALL."""
        self.advance()  # consume '('
        # Load the function
        self.code.emit(Opcode.LOAD_VAR, name_tok.value, name_tok.line_no)
        arg_count = 0
        if self.current().type != RPAREN:
            self.parse_expression()
            arg_count += 1
            while self.current().type == COMMA:
                self.advance()  # consume ','
                self.parse_expression()
                arg_count += 1
        self.expect(RPAREN, "Expected ')' after function arguments")
        self.code.emit(Opcode.CALL, arg_count, name_tok.line_no)

    def get_precedence(self, token_type: str) -> Optional[int]:
        """Return the precedence level for a token type, or None."""
        if token_type == EQ:
            return PRECEDENCE['assignment']
        if token_type in COMPARISON_TOKENS:
            return PRECEDENCE['comparison']
        if token_type in ADDITION_TOKENS:
            return PRECEDENCE['addition']
        if token_type in MULTIPLICATION_TOKENS:
            return PRECEDENCE['multiplication']
        return None

    def emit_operator(self, tok: Token) -> None:
        """Emit the bytecode for an operator token."""
        if tok.type in BINARY_OPS:
            self.code.emit(BINARY_OPS[tok.type], None, tok.line_no)
        elif tok.type in COMPARE_OPS:
            self.code.emit(COMPARE_OPS[tok.type], None, tok.line_no)
        elif tok.type == EQ:
            raise SyntaxError("Assignment not allowed in expression", tok.line_no)

    # ── jump patching ──────────────────────────────────────────────

    def patch_jump(self, instr_index: int, target_index: int) -> None:
        """Patch a jump instruction with the correct relative offset."""
        instr = self.code.instructions[instr_index]
        offset = target_index - (instr_index + 1)
        instr.operand = offset
