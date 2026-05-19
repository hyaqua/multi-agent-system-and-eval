"""Compiler: parses tokens and emits bytecode instructions.

Implements recursive-descent parsing for expressions with correct
operator precedence, and compiles statements into stack-machine bytecode.
"""

from enum import Enum, auto
from typing import List, Tuple, Any, Optional
from lexer import Token, TokenType, LexerError


class OpCode(Enum):
    """Bytecode instruction set."""
    PUSH_CONST = auto()     # Push constant value
    LOAD_VAR = auto()       # Push variable value
    STORE_VAR = auto()      # Pop and store to variable
    ADD = auto()            # Pop b, pop a, push a+b
    SUB = auto()            # Pop b, pop a, push a-b
    MUL = auto()            # Pop b, pop a, push a*b
    DIV = auto()            # Pop b, pop a, push a/b
    NEG = auto()            # Pop a, push -a
    CMP_EQ = auto()         # Pop b, pop a, push a==b
    CMP_NE = auto()         # Pop b, pop a, push a!=b
    CMP_LT = auto()         # Pop b, pop a, push a<b
    CMP_GT = auto()         # Pop b, pop a, push a>b
    CMP_LE = auto()         # Pop b, pop a, push a<=b
    CMP_GE = auto()         # Pop b, pop a, push a>=b
    JMP = auto()            # Unconditional jump
    JMP_IF_FALSE = auto()   # Pop condition; jump if false
    CALL = auto()           # Call function (name, nargs)
    RETURN = auto()         # Return from function
    PRINT = auto()          # Pop and print to stdout
    POP = auto()            # Discard top of stack
    DEF_FUNC = auto()       # Define function (name, params, addr)
    HALT = auto()           # Stop execution


# An instruction is a tuple: (OpCode, arg1, arg2, ...)
Instruction = Tuple

# A FunctionObject stores metadata for a compiled function
class FunctionObject:
    def __init__(self, name: str, params: List[str], start_addr: int):
        self.name = name
        self.params = params
        self.start_addr = start_addr

    def __repr__(self):
        return (f"FunctionObject({self.name}, params={self.params}, "
                f"addr={self.start_addr})")


class CompilerError(Exception):
    """Raised when the compiler encounters a syntax error."""

    def __init__(self, message: str, line: int = 0, col: int = 0,
                 filename: str = '<unknown>'):
        self.line = line
        self.col = col
        self.filename = filename
        super().__init__(f"{filename}:{line}:{col}: {message}")


class Compiler:
    """Recursive-descent compiler that produces bytecode from tokens."""

    def __init__(self, tokens: List[Token], filename: str = '<unknown>'):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        self.code: List[Instruction] = []
        self.functions: dict = {}  # name -> FunctionObject

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self) -> Tuple[List[Instruction], dict]:
        """Compile the token stream. Returns (code, functions_dict)."""
        # Compile statements until EOF
        while not self._check(TokenType.EOF):
            self._compile_stmt()

        self._emit(OpCode.HALT)
        return self.code, self.functions

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _compile_stmt(self):
        """Compile a single statement (simple or compound)."""
        if self._match(TokenType.PRINT):
            self._compile_print()
            self._expect(TokenType.NEWLINE)
        elif self._match(TokenType.IF):
            self._compile_if()
            # compound statement — NEWLINE already consumed internally
        elif self._match(TokenType.WHILE):
            self._compile_while()
            # compound statement — NEWLINE already consumed internally
        elif self._match(TokenType.DEF):
            self._compile_func_def()
            # compound statement — NEWLINE already consumed internally
        elif self._match(TokenType.RETURN):
            self._compile_return()
            self._expect(TokenType.NEWLINE)
        elif (self._check(TokenType.IDENT)
              and self._peek_next()
              and self._peek_next().type == TokenType.EQ):
            # Assignment: IDENT = expr
            name_token = self._advance()
            self._advance()  # Skip '='
            self._compile_expr()
            self._emit(OpCode.STORE_VAR, name_token.value)
            self._expect(TokenType.NEWLINE)
        else:
            # Expression statement (bare expression or function call)
            self._compile_expr()
            self._emit(OpCode.POP)  # Discard result
            self._expect(TokenType.NEWLINE)

    def _compile_print(self):
        """Compile: print expr"""
        self._compile_expr()
        self._emit(OpCode.PRINT)

    def _compile_return(self):
        """Compile: return [expr]"""
        if self._check(TokenType.NEWLINE):
            # Bare return => return None
            self._emit(OpCode.PUSH_CONST, None)
        else:
            self._compile_expr()
        self._emit(OpCode.RETURN)

    def _compile_if(self):
        """Compile: if expr : block [else : block]"""
        # Condition
        self._compile_expr()
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        # Emit conditional jump placeholder
        jmp_to_else_idx = len(self.code)
        self._emit(OpCode.JMP_IF_FALSE, 0)

        # Compile if-body
        while (not self._check(TokenType.DEDENT)
               and not self._check(TokenType.EOF)):
            self._compile_stmt()

        self._expect(TokenType.DEDENT)

        # Jump over else block
        jmp_to_end_idx = len(self.code)
        self._emit(OpCode.JMP, 0)

        # Patch JMP_IF_FALSE to point here (start of else or end)
        else_start = len(self.code)
        self.code[jmp_to_else_idx] = (OpCode.JMP_IF_FALSE, else_start)

        # Optional else block
        if self._match(TokenType.ELSE):
            self._expect(TokenType.COLON)
            self._expect(TokenType.NEWLINE)
            self._expect(TokenType.INDENT)

            while (not self._check(TokenType.DEDENT)
                   and not self._check(TokenType.EOF)):
                self._compile_stmt()

            self._expect(TokenType.DEDENT)

        # Patch the end-of-if jump
        end_addr = len(self.code)
        self.code[jmp_to_end_idx] = (OpCode.JMP, end_addr)

    def _compile_while(self):
        """Compile: while expr : block"""
        loop_start = len(self.code)

        # Condition
        self._compile_expr()
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        # If condition is false, jump to after the loop
        jmp_to_end_idx = len(self.code)
        self._emit(OpCode.JMP_IF_FALSE, 0)

        # Compile body
        while (not self._check(TokenType.DEDENT)
               and not self._check(TokenType.EOF)):
            self._compile_stmt()

        self._expect(TokenType.DEDENT)

        # Jump back to condition
        self._emit(OpCode.JMP, loop_start)

        # Patch exit jump
        end_addr = len(self.code)
        self.code[jmp_to_end_idx] = (OpCode.JMP_IF_FALSE, end_addr)

    def _compile_func_def(self):
        """Compile: def IDENT ( params ) : block"""
        name = self._expect(TokenType.IDENT).value
        self._expect(TokenType.LPAREN)

        params = []
        if not self._check(TokenType.RPAREN):
            params.append(self._expect(TokenType.IDENT).value)
            while self._match(TokenType.COMMA):
                params.append(self._expect(TokenType.IDENT).value)

        self._expect(TokenType.RPAREN)
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        # Jump over the function body in the instruction stream
        jmp_idx = len(self.code)
        self._emit(OpCode.JMP, 0)  # placeholder

        func_start = len(self.code)

        # Compile function body
        while (not self._check(TokenType.DEDENT)
               and not self._check(TokenType.EOF)):
            self._compile_stmt()

        # Implicit return None at end of function
        if (not self.code
                or self.code[-1][0] != OpCode.RETURN):
            self._emit(OpCode.PUSH_CONST, None)
            self._emit(OpCode.RETURN)

        self._expect(TokenType.DEDENT)

        # Patch the jump to skip past the function body
        after_func = len(self.code)
        self.code[jmp_idx] = (OpCode.JMP, after_func)

        # Emit DEF_FUNC — at runtime this stores the function object
        self._emit(OpCode.DEF_FUNC, name, params, func_start)

    # ------------------------------------------------------------------
    # Expressions (recursive descent with precedence)
    # ------------------------------------------------------------------

    def _compile_expr(self):
        """Entry point for expression compilation."""
        self._compile_comparison()

    def _compile_comparison(self):
        """comparison -> addition (('=='|'!='|'<'|'>'|'<='|'>=') addition)*"""
        self._compile_addition()

        cmp_ops = {
            TokenType.EQ_EQ: OpCode.CMP_EQ,
            TokenType.NOT_EQ: OpCode.CMP_NE,
            TokenType.LT: OpCode.CMP_LT,
            TokenType.GT: OpCode.CMP_GT,
            TokenType.LT_EQ: OpCode.CMP_LE,
            TokenType.GT_EQ: OpCode.CMP_GE,
        }

        while self._peek() and self._peek().type in cmp_ops:
            op_token = self._advance()
            self._compile_addition()
            self._emit(cmp_ops[op_token.type])

    def _compile_addition(self):
        """addition -> multiplication (('+'|'-') multiplication)*"""
        self._compile_multiplication()

        while self._peek() and self._peek().type in (TokenType.PLUS,
                                                      TokenType.MINUS):
            op_token = self._advance()
            self._compile_multiplication()
            if op_token.type == TokenType.PLUS:
                self._emit(OpCode.ADD)
            else:
                self._emit(OpCode.SUB)

    def _compile_multiplication(self):
        """multiplication -> unary (('*'|'/') unary)*"""
        self._compile_unary()

        while self._peek() and self._peek().type in (TokenType.STAR,
                                                      TokenType.SLASH):
            op_token = self._advance()
            self._compile_unary()
            if op_token.type == TokenType.STAR:
                self._emit(OpCode.MUL)
            else:
                self._emit(OpCode.DIV)

    def _compile_unary(self):
        """unary -> '-' unary | call"""
        if self._match(TokenType.MINUS):
            self._compile_unary()
            self._emit(OpCode.NEG)
        else:
            self._compile_call()

    def _compile_call(self):
        """call -> primary ('(' [args] ')')?"""
        self._compile_primary()

        # After a primary that is an IDENT, we may have a function call
        # But also, after a parenthesized expression or literal, '(' is
        # not valid. We only allow calls on identifiers.
        # However, we already compiled the primary. We need to detect
        # if the last instruction was LOAD_VAR followed by '('.
        # Easiest: check if current token is '(' and the primary was
        # an identifier. We restructure to handle this inside _compile_primary.

    def _compile_primary(self):
        """primary -> NUMBER | STRING | IDENT ['(' args ')'] | '(' expr ')'"""
        if self._match(TokenType.NUMBER):
            self._emit(OpCode.PUSH_CONST, self._prev().value)

        elif self._match(TokenType.STRING):
            self._emit(OpCode.PUSH_CONST, self._prev().value)

        elif self._match(TokenType.IDENT):
            name = self._prev().value
            if self._match(TokenType.LPAREN):
                # Function call
                nargs = self._compile_args()
                self._expect(TokenType.RPAREN)
                self._emit(OpCode.CALL, name, nargs)
            else:
                self._emit(OpCode.LOAD_VAR, name)

        elif self._match(TokenType.LPAREN):
            self._compile_expr()
            self._expect(TokenType.RPAREN)

        else:
            tok = self._peek()
            if tok:
                raise CompilerError(
                    f"Expected expression, got {tok.type.name} ('{tok.value}')",
                    line=tok.line, col=tok.col, filename=self.filename)
            else:
                raise CompilerError(
                    "Unexpected end of input in expression",
                    line=0, col=0, filename=self.filename)

    def _compile_args(self) -> int:
        """Compile function arguments. Returns the number of arguments."""
        nargs = 0
        if not self._check(TokenType.RPAREN):
            self._compile_expr()
            nargs = 1
            while self._match(TokenType.COMMA):
                self._compile_expr()
                nargs += 1
        return nargs

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Optional[Token]:
        """Return the current token without consuming it."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _peek_next(self) -> Optional[Token]:
        """Return the next token without consuming it."""
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return None

    def _advance(self) -> Token:
        """Consume and return the current token."""
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            self.pos += 1
            return tok
        # Should not happen if checking before advancing
        raise CompilerError("Unexpected end of token stream",
                            filename=self.filename)

    def _prev(self) -> Optional[Token]:
        """Return the most recently consumed token."""
        if self.pos > 0:
            return self.tokens[self.pos - 1]
        return None

    def _check(self, token_type: TokenType) -> bool:
        """Check if current token has the given type."""
        tok = self._peek()
        return tok is not None and tok.type == token_type

    def _match(self, token_type: TokenType) -> bool:
        """If current token matches type, consume and return True."""
        if self._check(token_type):
            self._advance()
            return True
        return False

    def _expect(self, token_type: TokenType) -> Token:
        """Consume current token; error if it doesn't match."""
        tok = self._peek()
        if tok is None:
            raise CompilerError(
                f"Expected {token_type.name}, but reached end of input",
                filename=self.filename)

        if tok.type != token_type:
            raise CompilerError(
                f"Expected {token_type.name}, got {tok.type.name} "
                f"('{tok.value}')",
                line=tok.line, col=tok.col, filename=self.filename)

        return self._advance()

    def _emit(self, opcode: OpCode, *args):
        """Append an instruction to the code."""
        self.code.append((opcode,) + args)
