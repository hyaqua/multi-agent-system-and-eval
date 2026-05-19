"""Compiler: recursive-descent parser that produces bytecode."""

from tokens import NUMBER, STRING, ID, KEYWORD, OP, DELIM, EOF
from code import Code
import opcodes as opc


class CompileError(Exception):
    """Syntax/compile error with line number information."""

    def __init__(self, message, line):
        super().__init__(f"Syntax error at line {line}: {message}")
        self.line = line


class Compiler:
    """Parses tokens and produces a Code object."""

    def __init__(self, tokens, name="<module>"):
        self.tokens = tokens
        self.pos = 0
        self.name = name

        # Constant pool
        self.constants = []
        # Map value → index for deduplication
        self.constant_map = {}

        # Local variable tracking
        self.local_names = []
        self.local_name_map = {}  # name → index

        # Bytecode output
        self.bytecode = []

        # For tracking whether we are in a function scope
        self.is_function_scope = False

    # ─── helpers ────────────────────────────────────────────────────

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self):
        return self.current()

    def consume(self, expected_type=None, expected_value=None):
        tok = self.current()
        if expected_type is not None and tok.type != expected_type:
            raise CompileError(
                f"Expected {expected_type}, got {tok.type} ({tok.value!r})",
                tok.line,
            )
        if expected_value is not None and tok.value != expected_value:
            raise CompileError(
                f"Expected {expected_value!r}, got {tok.value!r}",
                tok.line,
            )
        self.pos += 1
        return tok

    def match(self, type_=None, value=None):
        tok = self.current()
        if tok.type == EOF:
            return False
        if type_ is not None and tok.type != type_:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def add_constant(self, value):
        """Add value to constant pool, return its index."""
        key = (type(value).__name__, value)
        if key not in self.constant_map:
            idx = len(self.constants)
            self.constants.append(value)
            self.constant_map[key] = idx
            return idx
        return self.constant_map[key]

    def emit(self, opcode, operand=None):
        self.bytecode.append((opcode, operand))

    def emit_at(self, index, opcode, operand=None):
        self.bytecode[index] = (opcode, operand)

    def get_local_index(self, name):
        """Get or create a local variable index."""
        if name not in self.local_name_map:
            idx = len(self.local_names)
            self.local_names.append(name)
            self.local_name_map[name] = idx
            return idx
        return self.local_name_map[name]

    def is_local(self, name):
        return name in self.local_name_map

    # ─── semicolon ──────────────────────────────────────────────────

    def _consume_semicolon(self):
        """Optionally consume a semicolon if present."""
        if self.match(DELIM, ";"):
            self.consume(DELIM, ";")

    # ─── expressions ───────────────────────────────────────────────

    def parse_primary(self):
        """Parse a primary expression (literal, identifier, call, grouping)."""
        tok = self.current()

        if tok.type == NUMBER:
            self.consume(NUMBER)
            idx = self.add_constant(tok.value)
            self.emit(opc.LOAD_CONST, idx)
            return

        if tok.type == STRING:
            self.consume(STRING)
            idx = self.add_constant(tok.value)
            self.emit(opc.LOAD_CONST, idx)
            return

        if tok.type == KEYWORD and tok.value == "true":
            self.consume(KEYWORD, "true")
            idx = self.add_constant(True)
            self.emit(opc.LOAD_CONST, idx)
            return

        if tok.type == KEYWORD and tok.value == "false":
            self.consume(KEYWORD, "false")
            idx = self.add_constant(False)
            self.emit(opc.LOAD_CONST, idx)
            return

        if tok.type == ID:
            name = tok.value
            self.consume(ID)

            # Check for function call: id ( args )
            if self.match(DELIM, "("):
                self.consume(DELIM, "(")
                arg_count = 0
                if not self.match(DELIM, ")"):
                    self.parse_expression()
                    arg_count += 1
                    while self.match(DELIM, ","):
                        self.consume(DELIM, ",")
                        self.parse_expression()
                        arg_count += 1
                self.consume(DELIM, ")")

                # Load the function (global lookup for now)
                name_idx = self.add_constant(name)
                self.emit(opc.LOAD_GLOBAL, name_idx)
                self.emit(opc.CALL, arg_count)
                return

            # It's a variable load
            if self.is_local(name):
                idx = self.get_local_index(name)
                self.emit(opc.LOAD_FAST, idx)
            else:
                idx = self.add_constant(name)
                self.emit(opc.LOAD_GLOBAL, idx)
            return

        if tok.type == DELIM and tok.value == "(":
            self.consume(DELIM, "(")
            self.parse_expression()
            self.consume(DELIM, ")")
            return

        raise CompileError(
            f"Unexpected token in expression: {tok.type} ({tok.value!r})",
            tok.line,
        )

    def parse_unary(self):
        """Parse unary minus."""
        if self.match(OP, "-"):
            self.consume(OP, "-")
            self.parse_unary()
            self.emit(opc.UNARY_NEG)
        else:
            self.parse_primary()

    def parse_multiplicative(self):
        """Parse * and / operators."""
        self.parse_unary()
        while self.match(OP) and self.current().value in ("*", "/"):
            op_tok = self.consume(OP)
            self.parse_unary()
            if op_tok.value == "*":
                self.emit(opc.BINARY_MUL)
            else:
                self.emit(opc.BINARY_DIV)

    def parse_additive(self):
        """Parse + and - operators."""
        self.parse_multiplicative()
        while self.match(OP) and self.current().value in ("+", "-"):
            op_tok = self.consume(OP)
            self.parse_multiplicative()
            if op_tok.value == "+":
                self.emit(opc.BINARY_ADD)
            else:
                self.emit(opc.BINARY_SUB)

    def parse_comparison(self):
        """Parse comparison operators."""
        self.parse_additive()
        while self.match(OP) and self.current().value in ("==", "!=", "<", ">", "<=", ">="):
            op_tok = self.consume(OP)
            self.parse_additive()
            self.emit(opc.COMPARE_OP, op_tok.value)

    def parse_expression(self):
        """Parse a full expression (entry point)."""
        self.parse_comparison()

    # ─── statements ─────────────────────────────────────────────────

    def _peek_next_is_assignment(self):
        """Check if the next significant token after current ID is '='."""
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1].value == "="
        return False

    def parse_statement(self):
        """Parse a single statement."""
        tok = self.current()

        if tok.type == KEYWORD and tok.value == "print":
            self.parse_print()
        elif tok.type == KEYWORD and tok.value == "if":
            self.parse_if()
        elif tok.type == KEYWORD and tok.value == "while":
            self.parse_while()
        elif tok.type == KEYWORD and tok.value == "def":
            self.parse_def()
        elif tok.type == KEYWORD and tok.value == "return":
            self.parse_return()
        elif tok.type == ID and self._peek_next_is_assignment():
            self.parse_assignment()
        elif tok.type == ID:
            # Expression statement (function call mostly)
            self.parse_expression()
            self._consume_semicolon()
            # Discard result (pop the value left on stack)
            self.emit(opc.POP)
        elif tok.type == DELIM and tok.value == "}":
            # End of block, nothing to do
            return
        elif tok.type == EOF:
            return
        else:
            raise CompileError(
                f"Unexpected token at start of statement: {tok.type} ({tok.value!r})",
                tok.line,
            )

    def parse_print(self):
        self.consume(KEYWORD, "print")
        self.parse_expression()
        self._consume_semicolon()
        self.emit(opc.PRINT)

    def parse_assignment(self):
        name = self.consume(ID).value
        self.consume(OP, "=")
        self.parse_expression()
        self._consume_semicolon()

        if self.is_function_scope:
            idx = self.get_local_index(name)
            self.emit(opc.STORE_FAST, idx)
        else:
            idx = self.add_constant(name)
            self.emit(opc.STORE_GLOBAL, idx)

    def parse_block(self):
        """Parse { statement* } and return nothing."""
        self.consume(DELIM, "{")
        while not self.match(DELIM, "}"):
            if self.match(EOF):
                raise CompileError("Unterminated block", self.current().line)
            self.parse_statement()
        self.consume(DELIM, "}")

    def parse_if(self):
        self.consume(KEYWORD, "if")
        self.consume(DELIM, "(")
        self.parse_expression()
        self.consume(DELIM, ")")

        # Emit conditional jump; we'll patch later
        jump_if_false_idx = len(self.bytecode)
        self.emit(opc.POP_JUMP_IF_FALSE, None)  # placeholder

        self.parse_block()

        if self.match(KEYWORD, "else"):
            # Need to jump over else block after if body
            jump_over_idx = len(self.bytecode)
            self.emit(opc.JUMP, None)  # placeholder

            # Patch the POP_JUMP_IF_FALSE to land here (after if body, before else)
            after_if = len(self.bytecode)
            self.emit_at(jump_if_false_idx, opc.POP_JUMP_IF_FALSE, after_if)

            self.consume(KEYWORD, "else")
            self.parse_block()

            # Patch the jump over else
            after_else = len(self.bytecode)
            self.emit_at(jump_over_idx, opc.JUMP, after_else)
        else:
            # No else; jump to here if false
            after_if = len(self.bytecode)
            self.emit_at(jump_if_false_idx, opc.POP_JUMP_IF_FALSE, after_if)

    def parse_while(self):
        self.consume(KEYWORD, "while")
        loop_start = len(self.bytecode)
        self.consume(DELIM, "(")
        self.parse_expression()
        self.consume(DELIM, ")")

        jump_if_false_idx = len(self.bytecode)
        self.emit(opc.POP_JUMP_IF_FALSE, None)  # placeholder

        self.parse_block()

        # Jump back to loop start
        self.emit(opc.JUMP, loop_start)

        # Patch the exit jump
        after_loop = len(self.bytecode)
        self.emit_at(jump_if_false_idx, opc.POP_JUMP_IF_FALSE, after_loop)

    def parse_def(self):
        self.consume(KEYWORD, "def")
        func_name = self.consume(ID).value
        self.consume(DELIM, "(")

        # Parse parameters
        param_names = []
        if not self.match(DELIM, ")"):
            param_names.append(self.consume(ID).value)
            while self.match(DELIM, ","):
                self.consume(DELIM, ",")
                param_names.append(self.consume(ID).value)
        self.consume(DELIM, ")")

        # Parse body as a separate compiler that shares constant pool
        body_compiler = Compiler(self.tokens, name=func_name)
        body_compiler.pos = self.pos  # share token stream position
        body_compiler.constants = self.constants
        body_compiler.constant_map = self.constant_map
        body_compiler.is_function_scope = True

        # Set up parameters as locals
        for pname in param_names:
            body_compiler.get_local_index(pname)

        # Parse the function body block
        body_compiler.consume(DELIM, "{")
        while not body_compiler.match(DELIM, "}"):
            if body_compiler.match(EOF):
                raise CompileError("Unterminated function body", body_compiler.current().line)
            body_compiler.parse_statement()
        body_compiler.consume(DELIM, "}")

        # Make sure function ends with a return (implicit LOAD_NULL + RETURN)
        if not body_compiler.bytecode or body_compiler.bytecode[-1][0] != opc.RETURN:
            body_compiler.emit(opc.LOAD_NULL)
            body_compiler.emit(opc.RETURN)

        # Sync position back to main compiler
        self.pos = body_compiler.pos
        self.constants = body_compiler.constants
        self.constant_map = body_compiler.constant_map

        # Create the function code object
        func_code = Code(
            bytecode=list(body_compiler.bytecode),
            constants=list(body_compiler.constants),
            local_names=tuple(body_compiler.local_names),
            name=func_name,
        )

        # The function code itself is a constant
        code_idx = self.add_constant(func_code)

        self.emit(opc.LOAD_CONST, code_idx)
        self.emit(opc.MAKE_FUNCTION)

        # Store the function as a global
        name_idx = self.add_constant(func_name)
        self.emit(opc.STORE_GLOBAL, name_idx)

    def parse_return(self):
        tok = self.consume(KEYWORD, "return")
        if not self.is_function_scope:
            raise CompileError("'return' outside function", tok.line)

        # Check if there's an expression or just semicolon / end of block
        if self.match(DELIM, ";") or self.match(DELIM, "}") or self.match(EOF):
            self._consume_semicolon()
            self.emit(opc.LOAD_NULL)
        else:
            self.parse_expression()
            self._consume_semicolon()
        self.emit(opc.RETURN)

    # ─── main compiling entry ──────────────────────────────────────

    def compile(self):
        """Compile the token stream and return a Code object."""
        while not self.match(EOF):
            self.parse_statement()

        # Ensure the module returns null
        self.emit(opc.LOAD_NULL)
        self.emit(opc.RETURN)

        return Code(
            bytecode=self.bytecode,
            constants=list(self.constants),
            local_names=tuple(self.local_names),
            name=self.name,
        )
