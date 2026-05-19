"""Compiler: parses tokens and emits bytecode instructions."""

from typing import List, Tuple, Dict, Optional
from lexer import Token, TokenType, Lexer
from opcode import Opcode

# An instruction is a tuple: (opcode, operand, line_number)
Instruction = Tuple[Opcode, any, int]

# A function object stored for later execution
class CompiledFunction:
    def __init__(self, name: str, param_names: List[str], body: List[Instruction]):
        self.name = name
        self.param_names = param_names
        self.body = body


class CompilerError(Exception):
    def __init__(self, message: str, line: int, col: int = 0):
        self.message = message
        self.line = line
        self.col = col
        location = f"line {line}"
        if col > 0:
            location += f", col {col}"
        super().__init__(f"Syntax error at {location}: {message}")


class Compiler:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.bytecode: List[Instruction] = []
        self.functions: Dict[str, CompiledFunction] = {}
        self._loop_stack: List[Tuple[int, int]] = []  # For break/continue tracking (not used yet)

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _advance(self) -> Token:
        tok = self._current()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _consume(self, type_: TokenType, error_msg: str) -> Token:
        if self._check(type_):
            return self._advance()
        tok = self._current()
        raise CompilerError(error_msg, tok.line, tok.col)

    def _emit(self, opcode: Opcode, operand=None, line: int = None) -> int:
        """Emit an instruction. Returns the index of the emitted instruction."""
        if line is None:
            line = self._current().line
        idx = len(self.bytecode)
        self.bytecode.append((opcode, operand, line))
        return idx

    def _emit_at(self, index: int, opcode: Opcode, operand=None, line: int = None):
        """Replace an instruction at a given index (for backpatching jumps)."""
        if line is None:
            line = self._current().line
        self.bytecode[index] = (opcode, operand, line)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def compile(self) -> Tuple[List[Instruction], Dict[str, CompiledFunction]]:
        """Compile the entire program. Returns (main_bytecode, function_table)."""
        self._parse_program()
        self._emit(Opcode.HALT, None)
        return self.bytecode, self.functions

    def _parse_program(self):
        """program -> statement* EOF"""
        while not self._check(TokenType.EOF):
            self._parse_statement()

    def _parse_statement(self):
        """Dispatch on the first token to determine statement type."""
        tok = self._current()

        if tok.type == TokenType.IF:
            self._parse_if()
        elif tok.type == TokenType.WHILE:
            self._parse_while()
        elif tok.type == TokenType.DEF:
            self._parse_function_def()
        elif tok.type == TokenType.PRINT:
            self._parse_print()
        elif tok.type == TokenType.RETURN:
            self._parse_return()
        elif tok.type == TokenType.LBRACE:
            self._parse_block()
        elif tok.type == TokenType.IDENTIFIER:
            # Could be assignment or function call as statement
            # Look ahead: if next is '=', it's assignment
            if self._peek(1).type == TokenType.ASSIGN:
                self._parse_assignment()
            else:
                # Function call as statement (discard result)
                self._parse_expression()
                self._emit(Opcode.POP, None)
        elif tok.type == TokenType.EOF:
            return
        else:
            # Try expression statement
            self._parse_expression()
            self._emit(Opcode.POP, None)

    def _parse_block(self):
        """block -> '{' statement* '}'"""
        self._consume(TokenType.LBRACE, "Expected '{'")
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            self._parse_statement()
        self._consume(TokenType.RBRACE, "Expected '}'")

    def _parse_assignment(self):
        """assignment -> IDENTIFIER '=' expression"""
        ident_tok = self._consume(TokenType.IDENTIFIER, "Expected identifier")
        self._consume(TokenType.ASSIGN, "Expected '='")
        self._parse_expression()
        self._emit(Opcode.STORE_VAR, ident_tok.value, ident_tok.line)

    def _parse_print(self):
        """print statement: 'print' expression"""
        tok = self._advance()  # consume 'print'
        self._parse_expression()
        self._emit(Opcode.PRINT, None, tok.line)

    def _parse_return(self):
        """return statement: 'return' expression? """
        tok = self._advance()  # consume 'return'
        if self._check(TokenType.RBRACE, TokenType.EOF):
            # bare return
            self._emit(Opcode.LOAD_CONST, None, tok.line)
        else:
            self._parse_expression()
        self._emit(Opcode.RETURN, None, tok.line)

    def _parse_if(self):
        """if_statement -> 'if' expression block ('else' block)?"""
        tok = self._advance()  # consume 'if'
        line = tok.line

        # Parse condition
        self._parse_expression()

        # Jump if false to else (or end)
        jmp_if_false_idx = self._emit(Opcode.JMP_IF_FALSE, None, line)

        # Parse then-block
        self._parse_block()

        # After then-block, jump past else block
        jmp_past_else_idx = self._emit(Opcode.JMP, None, line)

        # Patch the JMP_IF_FALSE to jump here (start of else or end)
        else_start = len(self.bytecode)
        self._emit_at(jmp_if_false_idx, Opcode.JMP_IF_FALSE, else_start, line)

        if self._match(TokenType.ELSE):
            self._parse_block()

        # Patch the jump past else
        end = len(self.bytecode)
        self._emit_at(jmp_past_else_idx, Opcode.JMP, end, line)

    def _parse_while(self):
        """while_statement -> 'while' expression block"""
        tok = self._advance()  # consume 'while'
        line = tok.line

        loop_start = len(self.bytecode)

        # Parse condition
        self._parse_expression()

        # Jump if false to after the loop body
        jmp_if_false_idx = self._emit(Opcode.JMP_IF_FALSE, None, line)

        # Parse body
        self._parse_block()

        # Jump back to loop start
        self._emit(Opcode.JMP, loop_start, line)

        # Patch JMP_IF_FALSE to after the loop
        loop_end = len(self.bytecode)
        self._emit_at(jmp_if_false_idx, Opcode.JMP_IF_FALSE, loop_end, line)

    def _parse_function_def(self):
        """function_def -> 'def' IDENTIFIER '(' [params] ')' block"""
        def_tok = self._advance()  # consume 'def'
        line = def_tok.line

        name_tok = self._consume(TokenType.IDENTIFIER, "Expected function name")
        func_name = name_tok.value

        self._consume(TokenType.LPAREN, "Expected '(' after function name")

        # Parse parameters
        param_names: List[str] = []
        if not self._check(TokenType.RPAREN):
            # Parse first parameter
            param_tok = self._consume(TokenType.IDENTIFIER, "Expected parameter name")
            param_names.append(param_tok.value)
            while self._match(TokenType.COMMA):
                param_tok = self._consume(TokenType.IDENTIFIER, "Expected parameter name")
                param_names.append(param_tok.value)

        self._consume(TokenType.RPAREN, "Expected ')' after parameters")

        # Compile the body with a sub-compiler
        body_compiler = Compiler([])
        body_compiler.tokens = self.tokens
        body_compiler.pos = self.pos
        body_compiler._parse_block()

        # Update our position to after the block
        self.pos = body_compiler.pos

        # Ensure function body ends with RETURN
        body_code = body_compiler.bytecode
        if not body_code or body_code[-1][0] != Opcode.RETURN:
            body_compiler._emit(Opcode.LOAD_CONST, None, line)
            body_compiler._emit(Opcode.RETURN, None, line)
            body_code = body_compiler.bytecode

        func = CompiledFunction(func_name, param_names, body_code)
        self.functions[func_name] = func

    # ------------------------------------------------------------------
    # Expression parsing (recursive descent with correct precedence)
    # ------------------------------------------------------------------

    def _parse_expression(self):
        """expression -> comparison (('==' | '!=') comparison)*"""
        self._parse_comparison()
        while self._check(TokenType.EQ, TokenType.NEQ):
            op_tok = self._advance()
            self._parse_comparison()
            if op_tok.type == TokenType.EQ:
                self._emit(Opcode.EQ, None, op_tok.line)
            else:
                self._emit(Opcode.NEQ, None, op_tok.line)

    def _parse_comparison(self):
        """comparison -> term (('<' | '>' | '<=' | '>=') term)*"""
        self._parse_term()
        while self._check(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op_tok = self._advance()
            self._parse_term()
            op_map = {
                TokenType.LT: Opcode.LT,
                TokenType.GT: Opcode.GT,
                TokenType.LTE: Opcode.LTE,
                TokenType.GTE: Opcode.GTE,
            }
            self._emit(op_map[op_tok.type], None, op_tok.line)

    def _parse_term(self):
        """term -> factor (('+' | '-') factor)*"""
        self._parse_factor()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            self._parse_factor()
            if op_tok.type == TokenType.PLUS:
                self._emit(Opcode.ADD, None, op_tok.line)
            else:
                self._emit(Opcode.SUB, None, op_tok.line)

    def _parse_factor(self):
        """factor -> unary (('*' | '/') unary)*"""
        self._parse_unary()
        while self._check(TokenType.STAR, TokenType.SLASH):
            op_tok = self._advance()
            self._parse_unary()
            if op_tok.type == TokenType.STAR:
                self._emit(Opcode.MUL, None, op_tok.line)
            else:
                self._emit(Opcode.DIV, None, op_tok.line)

    def _parse_unary(self):
        """unary -> ('-')? primary"""
        if self._match(TokenType.MINUS):
            tok = self._current()
            # Need to negate: parse primary, then NEG
            self._parse_unary()
            self._emit(Opcode.NEG, None, tok.line)
        else:
            self._parse_primary()

    def _parse_primary(self):
        """primary -> NUMBER | STRING | IDENTIFIER | '(' expression ')' | func_call"""
        tok = self._current()

        if tok.type == TokenType.NUMBER:
            self._advance()
            self._emit(Opcode.LOAD_CONST, tok.value, tok.line)
        elif tok.type == TokenType.STRING:
            self._advance()
            self._emit(Opcode.LOAD_CONST, tok.value, tok.line)
        elif tok.type == TokenType.IDENTIFIER:
            self._advance()
            # Check if followed by '(' -> function call
            if self._check(TokenType.LPAREN):
                self._parse_function_call(tok.value, tok.line)
            else:
                self._emit(Opcode.LOAD_VAR, tok.value, tok.line)
        elif tok.type == TokenType.LPAREN:
            self._advance()
            self._parse_expression()
            self._consume(TokenType.RPAREN, "Expected ')'")
        else:
            raise CompilerError(f"Unexpected token: {tok.type.name} ('{tok.value}')", tok.line, tok.col)

    def _parse_function_call(self, func_name: str, line: int):
        """func_call -> IDENTIFIER '(' [args] ')'"""
        self._consume(TokenType.LPAREN, "Expected '('")  # already checked

        arg_count = 0
        if not self._check(TokenType.RPAREN):
            self._parse_expression()
            arg_count = 1
            while self._match(TokenType.COMMA):
                self._parse_expression()
                arg_count += 1

        self._consume(TokenType.RPAREN, "Expected ')' after arguments")
        self._emit(Opcode.CALL, (func_name, arg_count), line)
