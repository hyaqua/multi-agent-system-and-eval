"""Virtual machine that executes bytecode instructions.

A stack-based VM supporting variables, arithmetic, comparisons,
conditionals, loops, function definitions and calls, and print output.
"""

from typing import List, Dict, Any, Tuple
from compiler import OpCode, Instruction, FunctionObject


class RuntimeError(Exception):
    """Raised when the VM encounters a runtime error."""

    def __init__(self, message: str, line: int = 0,
                 filename: str = '<unknown>'):
        self.line = line
        self.filename = filename
        loc = f"{filename}:{line}: " if line > 0 else ""
        super().__init__(f"{loc}{message}")


class CallFrame:
    """Represents a function call frame on the call stack."""

    def __init__(self, return_address: int, locals_dict: Dict[str, Any]):
        self.return_address = return_address
        self.locals = locals_dict


class VM:
    """Stack-based virtual machine for executing compiled bytecode."""

    def __init__(self, code: List[Instruction],
                 functions: Dict[str, FunctionObject],
                 filename: str = '<unknown>'):
        self.code = code
        self.functions = functions  # name -> FunctionObject
        self.filename = filename
        self.stack: List[Any] = []
        self.globals: Dict[str, Any] = {}
        self.locals: Dict[str, Any] = {}  # Current function's local vars
        self.ip = 0  # Instruction pointer
        self.call_stack: List[CallFrame] = []

        # Source line tracking: maps instruction index -> line number
        self._line_map: Dict[int, int] = {}

    def set_line_map(self, line_map: Dict[int, int]):
        """Provide a mapping from instruction address to source line."""
        self._line_map = line_map

    def _current_line(self) -> int:
        """Return the source line for the current instruction, or 0."""
        return self._line_map.get(self.ip, 0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):
        """Execute the bytecode starting at ip=0 until HALT."""
        while self.ip < len(self.code):
            instr = self.code[self.ip]
            op = instr[0]
            self.ip += 1

            try:
                if op == OpCode.PUSH_CONST:
                    self.stack.append(instr[1])

                elif op == OpCode.LOAD_VAR:
                    name = instr[1]
                    val = self._get_var(name)
                    self.stack.append(val)

                elif op == OpCode.STORE_VAR:
                    name = instr[1]
                    val = self.stack.pop()
                    self._set_var(name, val)

                elif op == OpCode.ADD:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(a + b)

                elif op == OpCode.SUB:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(a - b)

                elif op == OpCode.MUL:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(a * b)

                elif op == OpCode.DIV:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    if b == 0:
                        raise RuntimeError(
                            "Division by zero",
                            line=self._current_line(),
                            filename=self.filename)
                    self.stack.append(a / b)

                elif op == OpCode.NEG:
                    a = self.stack.pop()
                    self.stack.append(-a)

                elif op == OpCode.CMP_EQ:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a == b else 0)

                elif op == OpCode.CMP_NE:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a != b else 0)

                elif op == OpCode.CMP_LT:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a < b else 0)

                elif op == OpCode.CMP_GT:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a > b else 0)

                elif op == OpCode.CMP_LE:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a <= b else 0)

                elif op == OpCode.CMP_GE:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.append(1 if a >= b else 0)

                elif op == OpCode.JMP:
                    self.ip = instr[1]

                elif op == OpCode.JMP_IF_FALSE:
                    condition = self.stack.pop()
                    if not condition:
                        self.ip = instr[1]

                elif op == OpCode.CALL:
                    name, nargs = instr[1], instr[2]
                    # Pop arguments in reverse order
                    args = []
                    for _ in range(nargs):
                        args.append(self.stack.pop())
                    args.reverse()

                    if name not in self.functions:
                        raise RuntimeError(
                            f"Undefined function '{name}'",
                            line=self._current_line(),
                            filename=self.filename)

                    func = self.functions[name]

                    if len(args) != len(func.params):
                        raise RuntimeError(
                            f"Function '{name}' expects "
                            f"{len(func.params)} argument(s), "
                            f"got {len(args)}",
                            line=self._current_line(),
                            filename=self.filename)

                    # Save current state
                    self.call_stack.append(
                        CallFrame(self.ip, self.locals))

                    # Set up new local scope
                    self.locals = dict(zip(func.params, args))
                    self.ip = func.start_addr

                elif op == OpCode.RETURN:
                    ret_val = self.stack.pop() if self.stack else None
                    if self.call_stack:
                        frame = self.call_stack.pop()
                        self.ip = frame.return_address
                        self.locals = frame.locals
                        self.stack.append(ret_val)
                    else:
                        # Return from top level — halt gracefully
                        self.ip = len(self.code)
                        break

                elif op == OpCode.PRINT:
                    val = self.stack.pop()
                    self._print_value(val)

                elif op == OpCode.POP:
                    if self.stack:
                        self.stack.pop()

                elif op == OpCode.DEF_FUNC:
                    name, params, start_addr = instr[1], instr[2], instr[3]
                    func_obj = FunctionObject(name, params, start_addr)
                    self.functions[name] = func_obj
                    # Also store as a regular variable so it can be
                    # treated as a first-class value
                    self.globals[name] = func_obj

                elif op == OpCode.HALT:
                    break

                else:
                    raise RuntimeError(
                        f"Unknown opcode: {op}",
                        line=self._current_line(),
                        filename=self.filename)

            except RuntimeError:
                raise
            except Exception as e:
                raise RuntimeError(
                    f"Unexpected error: {e}",
                    line=self._current_line(),
                    filename=self.filename)

    # ------------------------------------------------------------------
    # Variable access
    # ------------------------------------------------------------------

    def _get_var(self, name: str) -> Any:
        """Look up a variable: locals first, then globals."""
        if name in self.locals:
            return self.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise RuntimeError(
            f"Undefined variable '{name}'",
            line=self._current_line(),
            filename=self.filename)

    def _set_var(self, name: str, value: Any):
        """Set a variable: update local if it exists there, else global."""
        if name in self.locals:
            self.locals[name] = value
        else:
            self.globals[name] = value

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _print_value(self, val: Any):
        """Print a value to stdout in a user-friendly format."""
        if isinstance(val, bool):
            print(str(val).lower())
        elif val is None:
            print("None")
        elif isinstance(val, float):
            # Print integers without .0
            if val == int(val) and not (val != val):  # not NaN
                print(int(val))
            else:
                print(val)
        else:
            print(val)
