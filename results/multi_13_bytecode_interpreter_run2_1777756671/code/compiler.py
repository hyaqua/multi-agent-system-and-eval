"""Compiler: parses tokens and emits bytecode instructions."""

from dataclasses import dataclass, field
from enum import Enum, auto
from tokens import Token, TokenType


class Opcode(Enum):
    """Bytecode instruction opcodes."""
    PUSH_CONST = auto()
    LOAD_VAR = auto()
    STORE_VAR = auto()
    POP = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    NEG = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    NOT = auto()
    JMP = auto()
    JZ = auto()          # Jump if zero (pop, if falsy jump)
    CALL = auto()
    RET = auto()
    MAKE_FUNCTION = auto()
    PRINT = auto()


@dataclass
class Instruction:
    """A single bytecode instruction."""
    opcode: Opcode
    arg: int = 0
    line: int = 0

    def __repr__(self):
        return f"Instruction({self.opcode.name}, {self.arg}, line={self.line})"


@dataclass
class Function:
    """Represents a compiled function stored in the constant pool."""
    instructions: list[Instruction]
    param_count: int
    param_names: list[int]  # indices into the names table


class CompileError(Exception):
    """Raised on syntax errors during compilation."""
    def __init__(self, message: str, line: int):
        super().__init__(f"Syntax error at line {line}: {message}")
        self.line = line


class Compiler:
    """Recursive descent parser that emits bytecode."""

    def __init__(self, tokens: list[Token], shared_constants: list | None = None,
                 shared_names: list | None = None,
                 shared_name_to_index: dict | None = None):
        self.tokens = tokens
        self.pos = 0

        # Constant pool: numbers, strings, Function objects
        if shared_constants is not None:
            self.constants = shared_constants
        else:
            self.constants = []

        # Name table: variable/function names
        if shared_names is not None:
            self.names = shared_names
        else:
            self.names = []
        if shared_name_to_index is not None:
            self.name_to_index = shared_name_to_index
        else:
            self.name_to_index = {}

        # Emitted instructions
        self.instructions: list[Instruction] = []

    def _current(self) -> Token:
        """Return the current token."""
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _peek(self) -> Token:
        """Look at current token without consuming."""
        return self.tokens[self.pos]

    def _check(self, token_type: TokenType, value: str | None = None) -> bool:
        """Check if current token matches type and optional value."""
        tok = self._peek()
        if tok.type != token_type:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def _match(self, token_type: TokenType, value: str | None = None) -> bool:
        """If current token matches, consume it and return True."""
        if self._check(token_type, value):
            self._advance()
            return True
        return False

    def _expect(self, token_type: TokenType, value: str | None = None,
                error_msg: str = "") -> Token:
        """Consume token matching type/value or raise error."""
        if self._match(token_type, value):
            return self.tokens[self.pos - 1]
        tok = self._peek()
        if error_msg:
            raise CompileError(error_msg, tok.line)
        expected = value if value else token_type.name
        raise CompileError(
            f"Expected {expected}, got {tok.value!r} ({tok.type.name})",
            tok.line
        )

    def _skip_newlines(self):
        """Skip any NEWLINE tokens."""
        while self._match(TokenType.NEWLINE):
            pass

    def _add_constant(self, value) -> int:
        """Add a value to the constant pool and return its index."""
        self.constants.append(value)
        return len(self.constants) - 1

    def _add_name(self, name: str) -> int:
        """Add a name to the name table and return its index."""
        if name not in self.name_to_index:
            self.name_to_index[name] = len(self.names)
            self.names.append(name)
        return self.name_to_index[name]

    def _emit(self, opcode: Opcode, arg: int = 0) -> int:
        """Emit an instruction and return its index."""
        line = self._peek().line if self.pos < len(self.tokens) else 0
        instr = Instruction(opcode, arg, line)
        self.instructions.append(instr)
        return len(self.instructions) - 1

    def compile(self) -> tuple[list, list[Instruction], list[str]]:
        """Compile the token stream. Returns (constants, instructions, names)."""
        self._parse_statement_list(stop_on_end=False)
        return self.constants, self.instructions, self.names

    # ── Statement parsing ──────────────────────────────────────────

    def _parse_statement_list(self, stop_on_end: bool = True):
        """Parse a sequence of statements until 'end' or EOF."""
        while True:
            self._skip_newlines()
            tok = self._peek()

            # Stop conditions
            if tok.type == TokenType.EOF:
                break
            if stop_on_end and tok.type == TokenType.KEYWORD and tok.value == 'end':
                break
            # 'else' also ends the current block (handled by if parser)
            if tok.type == TokenType.KEYWORD and tok.value == 'else':
                break

            self._parse_statement()

    def _parse_statement(self):
        """Parse a single statement."""
        tok = self._peek()

        # Keywords that start statements
        if tok.type == TokenType.KEYWORD:
            if tok.value == 'if':
                self._parse_if()
                return
            elif tok.value == 'while':
                self._parse_while()
                return
            elif tok.value == 'def':
                self._parse_function_def()
                return
            elif tok.value == 'print':
                self._parse_print()
                return
            elif tok.value == 'return':
                self._parse_return()
                return
            elif tok.value == 'end':
                # 'end' should be handled by the statement list parser
                raise CompileError("Unexpected 'end'", tok.line)
            elif tok.value == 'else':
                raise CompileError("Unexpected 'else' without 'if'", tok.line)

        # Check for assignment: IDENTIFIER '='
        if tok.type == TokenType.IDENTIFIER:
            # Peek ahead (skip newlines) to see if next token is '='
            saved_pos = self.pos
            self._advance()  # skip identifier
            self._skip_newlines()
            if self._check(TokenType.OPERATOR, '='):
                # It's an assignment
                self.pos = saved_pos
                self._parse_assignment()
                return
            # Not an assignment, rewind and parse as expression
            self.pos = saved_pos

        # Fallback: expression statement
        self._parse_expression_statement()

    def _parse_assignment(self):
        """Parse: IDENTIFIER '=' expression"""
        name_token = self._expect(TokenType.IDENTIFIER)
        name_idx = self._add_name(name_token.value)
        self._expect(TokenType.OPERATOR, '=', "Expected '=' in assignment")
        self._parse_expression()
        self._emit(Opcode.STORE_VAR, name_idx)

    def _parse_expression_statement(self):
        """Parse an expression used as a statement; discard its value."""
        self._parse_expression()
        self._emit(Opcode.POP)

    def _parse_print(self):
        """Parse: 'print' expression"""
        self._advance()  # consume 'print'
        self._parse_expression()
        self._emit(Opcode.PRINT)

    def _parse_return(self):
        """Parse: 'return' [ expression ]"""
        tok = self._advance()  # consume 'return'
        # If next token is a statement terminator (newline, end, else, eof),
        # return with default value 0.
        self._skip_newlines()
        cur = self._peek()
        if (cur.type == TokenType.KEYWORD and cur.value in ('end', 'else')) or \
           cur.type == TokenType.EOF:
            # Return 0
            const_idx = self._add_constant(0)
            self._emit(Opcode.PUSH_CONST, const_idx)
        else:
            self._parse_expression()
        self._emit(Opcode.RET)

    # ── If / Else ──────────────────────────────────────────────────

    def _parse_if(self):
        """Parse: 'if' expression ':' statement_list [ 'else' ':' statement_list ] 'end'"""
        self._advance()  # consume 'if'
        self._parse_expression()
        self._expect(TokenType.DELIMITER, ':', "Expected ':' after if condition")

        # Emit JZ placeholder (will be patched to jump to else or end)
        jz_idx = self._emit(Opcode.JZ, 0)

        # Parse then-branch
        self._parse_statement_list(stop_on_end=False)
        # stop_on_end=False because we handle 'end' and 'else' explicitly

        # If there's an else branch
        if self._check(TokenType.KEYWORD, 'else'):
            # Emit JMP to skip else branch (placeholder)
            jmp_idx = self._emit(Opcode.JMP, 0)

            # Patch JZ to jump here (start of else)
            else_target = len(self.instructions)
            self.instructions[jz_idx].arg = else_target - jz_idx

            self._advance()  # consume 'else'
            self._expect(TokenType.DELIMITER, ':', "Expected ':' after else")

            # Parse else-branch
            self._parse_statement_list(stop_on_end=False)

            # Expect 'end'
            self._expect(TokenType.KEYWORD, 'end', "Expected 'end' after if/else block")

            # Patch JMP to jump to after the if/else
            end_target = len(self.instructions)
            self.instructions[jmp_idx].arg = end_target - jmp_idx
        else:
            # No else: patch JZ to jump to after the then-branch
            self._expect(TokenType.KEYWORD, 'end', "Expected 'end' after if block")
            end_target = len(self.instructions)
            self.instructions[jz_idx].arg = end_target - jz_idx

    # ── While Loop ─────────────────────────────────────────────────

    def _parse_while(self):
        """Parse: 'while' expression ':' statement_list 'end'"""
        self._advance()  # consume 'while'

        loop_start = len(self.instructions)

        self._parse_expression()
        self._expect(TokenType.DELIMITER, ':', "Expected ':' after while condition")

        # Emit JZ placeholder (jump to end of loop)
        jz_idx = self._emit(Opcode.JZ, 0)

        # Parse loop body
        self._parse_statement_list(stop_on_end=False)

        # Expect 'end'
        self._expect(TokenType.KEYWORD, 'end', "Expected 'end' after while block")

        # Emit JMP back to loop start
        self._emit(Opcode.JMP, loop_start - len(self.instructions))

        # Patch JZ to jump to after the loop
        end_target = len(self.instructions)
        self.instructions[jz_idx].arg = end_target - jz_idx

    # ── Function Definition ────────────────────────────────────────

    def _parse_function_def(self):
        """Parse: 'def' IDENTIFIER '(' [ params ] ')' ':' statement_list 'end'

        Emits MAKE_FUNCTION followed by STORE_VAR to bind the name.
        """
        self._advance()  # consume 'def'
        name_token = self._expect(TokenType.IDENTIFIER, error_msg="Expected function name")
        func_name_idx = self._add_name(name_token.value)

        self._expect(TokenType.DELIMITER, '(', "Expected '(' after function name")

        # Parse parameter list
        param_names: list[int] = []
        if not self._check(TokenType.DELIMITER, ')'):
            # First parameter
            param_token = self._expect(TokenType.IDENTIFIER, error_msg="Expected parameter name")
            param_names.append(self._add_name(param_token.value))
            # Additional parameters
            while self._match(TokenType.DELIMITER, ','):
                param_token = self._expect(TokenType.IDENTIFIER, error_msg="Expected parameter name")
                param_names.append(self._add_name(param_token.value))

        self._expect(TokenType.DELIMITER, ')', "Expected ')' after parameters")
        self._expect(TokenType.DELIMITER, ':', "Expected ':' before function body")

        # Compile the function body using a sub-compiler that shares constants/names
        func_compiler = Compiler(
            self.tokens,
            shared_constants=self.constants,
            shared_names=self.names,
            shared_name_to_index=self.name_to_index,
        )
        func_compiler.pos = self.pos

        # The function body: parse statements until 'end'
        func_compiler._parse_statement_list(stop_on_end=True)

        # Add implicit return at end of function body if not already terminated
        if (not func_compiler.instructions or
                func_compiler.instructions[-1].opcode != Opcode.RET):
            const_idx = func_compiler._add_constant(0)
            func_compiler._emit(Opcode.PUSH_CONST, const_idx)
            func_compiler._emit(Opcode.RET)

        # Consume 'end'
        func_compiler._expect(TokenType.KEYWORD, 'end', "Expected 'end' after function body")
        self.pos = func_compiler.pos

        # Store function bytecode in constant pool
        func_obj = Function(
            instructions=func_compiler.instructions,
            param_count=len(param_names),
            param_names=param_names,
        )
        const_idx = self._add_constant(func_obj)

        # Emit MAKE_FUNCTION and STORE_VAR
        self._emit(Opcode.MAKE_FUNCTION, const_idx)
        self._emit(Opcode.STORE_VAR, func_name_idx)

    # ── Expression Parsing (Precedence Climbing) ───────────────────

    # Precedence levels
    PREC_NONE = 0
    PREC_COMPARISON = 1
    PREC_TERM = 2       # +, -
    PREC_FACTOR = 3     # *, /
    PREC_UNARY = 4

    def _parse_expression(self, min_precedence: int = 0):
        """Parse an expression using precedence climbing."""
        # Parse prefix (unary or primary)
        tok = self._peek()

        # Unary operators
        if tok.type == TokenType.OPERATOR and tok.value == '-':
            self._advance()
            self._parse_expression(self.PREC_UNARY)
            self._emit(Opcode.NEG)
            return
        if tok.type == TokenType.OPERATOR and tok.value == '!':
            self._advance()
            self._parse_expression(self.PREC_UNARY)
            self._emit(Opcode.NOT)
            return

        # Parse primary
        self._parse_primary()

        # Parse infix operators
        while True:
            tok = self._peek()

            if tok.type == TokenType.OPERATOR:
                op = tok.value

                if op in ('==', '!='):
                    prec = self.PREC_COMPARISON
                elif op in ('<', '>', '<=', '>='):
                    prec = self.PREC_COMPARISON
                elif op in ('+', '-'):
                    prec = self.PREC_TERM
                elif op in ('*', '/'):
                    prec = self.PREC_FACTOR
                else:
                    break

                if prec <= min_precedence:
                    break

                self._advance()
                self._parse_expression(prec)

                # Emit the operator instruction
                opcode_map = {
                    '+': Opcode.ADD, '-': Opcode.SUB,
                    '*': Opcode.MUL, '/': Opcode.DIV,
                    '==': Opcode.EQ, '!=': Opcode.NE,
                    '<': Opcode.LT, '>': Opcode.GT,
                    '<=': Opcode.LE, '>=': Opcode.GE,
                }
                self._emit(opcode_map[op])
            else:
                break

    def _parse_primary(self):
        """Parse a primary expression: NUMBER, STRING, IDENTIFIER, '(' expr ')', function_call."""
        tok = self._peek()

        if tok.type == TokenType.NUMBER:
            self._advance()
            # Parse as int or float
            value_str = tok.value
            if '.' in value_str:
                value = float(value_str)
            else:
                value = int(value_str)
            const_idx = self._add_constant(value)
            self._emit(Opcode.PUSH_CONST, const_idx)

        elif tok.type == TokenType.STRING:
            self._advance()
            const_idx = self._add_constant(tok.value)
            self._emit(Opcode.PUSH_CONST, const_idx)

        elif tok.type == TokenType.IDENTIFIER:
            self._advance()
            name_idx = self._add_name(tok.value)

            # Check for function call: identifier '('
            if self._check(TokenType.DELIMITER, '('):
                self._parse_function_call(name_idx)
            else:
                self._emit(Opcode.LOAD_VAR, name_idx)

        elif tok.type == TokenType.DELIMITER and tok.value == '(':
            self._advance()  # skip '('
            self._parse_expression()
            self._expect(TokenType.DELIMITER, ')', "Expected ')'")

        else:
            raise CompileError(
                f"Unexpected token: {tok.value!r} ({tok.type.name})",
                tok.line
            )

    def _parse_function_call(self, func_name_idx: int):
        """Parse: '(' [ expression { ',' expression } ] ')'

        The function name has already been consumed and its name index provided.
        We emit LOAD_VAR for the function, then evaluate arguments, then CALL.
        """
        self._advance()  # consume '('

        # Evaluate arguments
        arg_count = 0
        if not self._check(TokenType.DELIMITER, ')'):
            self._parse_expression()
            arg_count = 1
            while self._match(TokenType.DELIMITER, ','):
                self._parse_expression()
                arg_count += 1

        self._expect(TokenType.DELIMITER, ')', "Expected ')' after function arguments")

        # Emit LOAD_VAR for the function, then CALL
        self._emit(Opcode.LOAD_VAR, func_name_idx)
        self._emit(Opcode.CALL, arg_count)
