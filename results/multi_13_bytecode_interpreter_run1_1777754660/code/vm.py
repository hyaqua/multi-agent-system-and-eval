"""Virtual Machine: executes bytecode using a stack-based architecture."""

from typing import Any, Dict, List, Optional

from opcodes import Opcode, Instruction, CodeObject


class Function:
    """A callable function object that wraps a CodeObject."""

    def __init__(self, code: CodeObject, globals_dict: Dict[str, Any]):
        self.code = code
        self.globals = globals_dict

    def __repr__(self):
        return f"<Function {self.code.name}>"


class CallFrame:
    """A single execution frame on the call stack."""

    def __init__(self, code: CodeObject, globals_dict: Dict[str, Any],
                 return_pc: int = 0, return_frame: Optional['CallFrame'] = None):
        self.instructions = code.instructions
        self.constants = code.constants
        self.locals: Dict[str, Any] = {}
        self.globals = globals_dict
        self.return_pc = return_pc
        self.return_frame = return_frame
        self.code = code  # For reference


class RuntimeError_(Exception):
    """Raised for runtime errors during VM execution."""

    def __init__(self, message: str, line_no: int = 0):
        super().__init__(f"Runtime error at line {line_no}: {message}")
        self.line_no = line_no


class VirtualMachine:
    """Executes bytecode instructions."""

    def __init__(self, code_object: CodeObject):
        self.code = code_object
        self.globals: Dict[str, Any] = {}
        self.stack: List[Any] = []
        self.call_stack: List[CallFrame] = []
        self.pc: int = 0
        self.current_frame: Optional[CallFrame] = None

    def run(self) -> None:
        """Execute the bytecode."""
        # Create top-level frame
        main_frame = CallFrame(self.code, self.globals, return_pc=0, return_frame=None)
        self.current_frame = main_frame
        self.call_stack.append(main_frame)
        self.pc = 0

        while self.current_frame is not None:
            frame = self.current_frame
            if self.pc >= len(frame.instructions):
                # Implicit return — shouldn't happen if code is well-formed
                break

            instr = frame.instructions[self.pc]
            self.pc += 1

            try:
                self.execute(instr, frame)
            except RuntimeError_:
                raise
            except Exception as e:
                raise RuntimeError_(str(e), instr.line_no)

    def execute(self, instr: Instruction, frame: CallFrame) -> None:
        """Execute a single instruction."""
        op = instr.opcode

        if op == Opcode.PUSH_CONST:
            const_idx = instr.operand
            if const_idx < 0 or const_idx >= len(frame.constants):
                raise RuntimeError_(
                    f"Constant index {const_idx} out of range", instr.line_no)
            self.stack.append(frame.constants[const_idx])

        elif op == Opcode.LOAD_VAR:
            name = instr.operand
            # Search local scope first, then global
            if name in frame.locals:
                self.stack.append(frame.locals[name])
            elif name in frame.globals:
                self.stack.append(frame.globals[name])
            else:
                raise RuntimeError_(
                    f"Undefined variable '{name}'", instr.line_no)

        elif op == Opcode.STORE_VAR:
            name = instr.operand
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on STORE_VAR", instr.line_no)
            value = self.stack.pop()
            # Store in local if we're inside a function and the variable exists
            # in locals or we are inside a function (store to locals).
            # Actually, for global assignment, store to globals.
            # The rule: if we're in a function AND the variable exists in locals,
            # or we're in a function, store to locals. Otherwise globals.
            # Simpler: if we're in a function (frame has a return_frame), store to locals.
            # But for functions to modify globals, we need a different approach.
            # Let's follow Python's rule: assignment always goes to locals inside
            # a function, unless declared global. For simplicity, assign to locals
            # if inside a function, else globals.
            if frame.return_frame is not None:
                # Inside a function — store to locals
                frame.locals[name] = value
            else:
                # Top level — store to globals
                frame.globals[name] = value

        elif op == Opcode.BINARY_ADD:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on BINARY_ADD", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            # Allow string concatenation
            if isinstance(a, str) and isinstance(b, str):
                self.stack.append(a + b)
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                self.stack.append(a + b)
            else:
                raise RuntimeError_(
                    f"Cannot add types {type(a).__name__} and {type(b).__name__}",
                    instr.line_no)

        elif op == Opcode.BINARY_SUB:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on BINARY_SUB", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                self.stack.append(a - b)
            else:
                raise RuntimeError_(
                    f"Cannot subtract types {type(a).__name__} and {type(b).__name__}",
                    instr.line_no)

        elif op == Opcode.BINARY_MUL:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on BINARY_MUL", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                self.stack.append(a * b)
            elif isinstance(a, str) and isinstance(b, int):
                self.stack.append(a * b)
            elif isinstance(a, int) and isinstance(b, str):
                self.stack.append(a * b)
            else:
                raise RuntimeError_(
                    f"Cannot multiply types {type(a).__name__} and {type(b).__name__}",
                    instr.line_no)

        elif op == Opcode.BINARY_DIV:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on BINARY_DIV", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                raise RuntimeError_(
                    f"Cannot divide types {type(a).__name__} and {type(b).__name__}",
                    instr.line_no)
            if b == 0:
                raise RuntimeError_("Division by zero", instr.line_no)
            self.stack.append(a / b)

        elif op == Opcode.COMPARE_EQ:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_EQ", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a == b)

        elif op == Opcode.COMPARE_NE:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_NE", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a != b)

        elif op == Opcode.COMPARE_LT:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_LT", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a < b)

        elif op == Opcode.COMPARE_GT:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_GT", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a > b)

        elif op == Opcode.COMPARE_LE:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_LE", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a <= b)

        elif op == Opcode.COMPARE_GE:
            if len(self.stack) < 2:
                raise RuntimeError_("Stack underflow on COMPARE_GE", instr.line_no)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a >= b)

        elif op == Opcode.JUMP:
            self.pc += instr.operand

        elif op == Opcode.JUMP_IF_FALSE:
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on JUMP_IF_FALSE", instr.line_no)
            condition = self.stack.pop()
            if not condition:
                self.pc += instr.operand

        elif op == Opcode.PRINT:
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on PRINT", instr.line_no)
            value = self.stack.pop()
            print(self.format_value(value))

        elif op == Opcode.DEF_FUNC:
            const_idx = instr.operand
            if const_idx < 0 or const_idx >= len(frame.constants):
                raise RuntimeError_(
                    f"Constant index {const_idx} out of range", instr.line_no)
            func_code = frame.constants[const_idx]
            if not isinstance(func_code, CodeObject):
                raise RuntimeError_(
                    f"Constant at index {const_idx} is not a CodeObject", instr.line_no)
            func_obj = Function(func_code, frame.globals)
            self.stack.append(func_obj)

        elif op == Opcode.CALL:
            arg_count = instr.operand
            if len(self.stack) < arg_count + 1:
                raise RuntimeError_(
                    f"Stack underflow on CALL: need {arg_count + 1} values, "
                    f"got {len(self.stack)}", instr.line_no)
            # Pop arguments in reverse order
            args = []
            for _ in range(arg_count):
                args.insert(0, self.stack.pop())
            # Pop the function
            func_obj = self.stack.pop()
            if not isinstance(func_obj, Function):
                raise RuntimeError_(
                    f"'{type(func_obj).__name__}' object is not callable",
                    instr.line_no)

            func_code = func_obj.code
            if len(args) != func_code.param_count:
                raise RuntimeError_(
                    f"Function '{func_code.name}' expects {func_code.param_count} "
                    f"arguments, got {len(args)}", instr.line_no)

            # Create new frame
            new_frame = CallFrame(
                func_code,
                func_obj.globals,
                return_pc=self.pc,
                return_frame=frame
            )
            # Bind arguments to parameter names in local scope
            for param_name, arg_value in zip(func_code.param_names, args):
                new_frame.locals[param_name] = arg_value

            # Switch to new frame
            self.current_frame = new_frame
            self.call_stack.append(new_frame)
            self.pc = 0

        elif op == Opcode.RETURN:
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on RETURN", instr.line_no)
            return_value = self.stack.pop()

            # Pop current frame
            if len(self.call_stack) > 0:
                self.call_stack.pop()

            # Return to caller
            if frame.return_frame is not None:
                self.current_frame = frame.return_frame
                self.pc = frame.return_pc
                self.stack.append(return_value)
            else:
                # Top-level return — execution ends
                self.current_frame = None

        elif op == Opcode.UNARY_NEG:
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on UNARY_NEG", instr.line_no)
            value = self.stack.pop()
            if not isinstance(value, (int, float)):
                raise RuntimeError_(
                    f"Cannot negate type {type(value).__name__}", instr.line_no)
            self.stack.append(-value)

        elif op == Opcode.POP:
            if len(self.stack) < 1:
                raise RuntimeError_("Stack underflow on POP", instr.line_no)
            self.stack.pop()

        else:
            raise RuntimeError_(f"Unknown opcode: {op}", instr.line_no)

    @staticmethod
    def format_value(value: Any) -> str:
        """Format a value for printing."""
        if value is None:
            return "None"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            # Pretty print floats
            if value == int(value):
                return str(int(value))
            return str(value)
        return str(value)
