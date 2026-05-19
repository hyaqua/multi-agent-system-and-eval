"""Virtual Machine: executes bytecode using a stack-based architecture."""

from typing import List, Dict, Any, Optional, Tuple
from opcode import Opcode, OPCODE_NAMES
from compiler import Instruction, CompiledFunction


class VMRuntimeError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        location = f"line {line}" if line > 0 else "runtime"
        super().__init__(f"Runtime error at {location}: {message}")


class CallFrame:
    """Represents a function call frame with its own code, IP, and locals."""
    def __init__(self, code: List[Instruction], ip: int = 0,
                 locals_dict: Dict[str, Any] = None,
                 return_address: int = None,
                 caller_code: List[Instruction] = None):
        self.code = code
        self.ip = ip
        self.locals = locals_dict if locals_dict is not None else {}
        self.return_address = return_address
        self.caller_code = caller_code


class VM:
    def __init__(self, bytecode: List[Instruction], functions: Dict[str, CompiledFunction]):
        self.functions = functions    # Function table: name -> CompiledFunction
        self.stack: List[Any] = []    # Value stack (shared across frames)
        self.call_stack: List[CallFrame] = []  # Call frames
        self.globals: Dict[str, Any] = {}      # Global variables

        # Create initial frame for main program
        main_frame = CallFrame(code=bytecode, ip=0)
        self.call_stack.append(main_frame)

    def _current_frame(self) -> CallFrame:
        return self.call_stack[-1]

    def _get_line(self, instr: Instruction) -> int:
        return instr[2] if len(instr) > 2 else 0

    def _resolve_variable(self, name: str, line: int = 0) -> Any:
        """Look up a variable: check all frames' locals (innermost first), then globals."""
        # Search call stack from top (innermost) to bottom
        for frame in reversed(self.call_stack):
            if name in frame.locals:
                return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise VMRuntimeError(f"Undefined variable '{name}'", line)

    def _set_variable(self, name: str, value: Any):
        """Set a variable in the innermost scope's locals, or globals at top level."""
        frame = self._current_frame()
        # If the variable exists in an outer scope, update it there
        for f in reversed(self.call_stack):
            if name in f.locals:
                f.locals[name] = value
                return
        # Otherwise, if in a function, set in function locals; else globals
        if len(self.call_stack) > 1:
            frame.locals[name] = value
        else:
            self.globals[name] = value

    def _is_truthy(self, value: Any) -> bool:
        """Determine truthiness for conditionals."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        return True

    def run(self, debug: bool = False):
        """Execute the bytecode."""
        while self.call_stack:
            frame = self._current_frame()
            if frame.ip < 0 or frame.ip >= len(frame.code):
                # End of current frame's code
                if len(self.call_stack) > 1:
                    # Implicit return from function
                    self.stack.append(None)
                    self._do_return(0)
                    continue
                else:
                    break  # Main program finished naturally

            instr = frame.code[frame.ip]
            opcode, operand, line = instr
            frame.ip += 1

            if debug:
                self._debug_instr(instr, frame)

            try:
                self._execute(opcode, operand, line)
            except VMRuntimeError:
                raise
            except Exception as e:
                raise VMRuntimeError(str(e), line)

    def _debug_instr(self, instr: Instruction, frame: CallFrame):
        opcode, operand, line = instr
        name = OPCODE_NAMES.get(opcode, str(opcode))
        op_str = f" {operand!r}" if operand is not None else ""
        stack_preview = f" stack={self.stack[-4:]}" if self.stack else ""
        frame_info = f" frame_depth={len(self.call_stack)}"
        print(f"  [{frame.ip-1:04d}] {name:15s}{op_str:20s}  ; line {line}{stack_preview}{frame_info}")

    def _execute(self, opcode: Opcode, operand: Any, line: int):
        if opcode == Opcode.LOAD_CONST:
            self.stack.append(operand)

        elif opcode == Opcode.LOAD_VAR:
            value = self._resolve_variable(operand, line)
            self.stack.append(value)

        elif opcode == Opcode.STORE_VAR:
            if not self.stack:
                raise VMRuntimeError("Stack underflow on STORE_VAR", line)
            value = self.stack.pop()
            self._set_variable(operand, value)

        elif opcode == Opcode.POP:
            if self.stack:
                self.stack.pop()

        elif opcode == Opcode.ADD:
            self._check_stack(2, "ADD", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a + b)

        elif opcode == Opcode.SUB:
            self._check_stack(2, "SUB", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a - b)

        elif opcode == Opcode.MUL:
            self._check_stack(2, "MUL", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a * b)

        elif opcode == Opcode.DIV:
            self._check_stack(2, "DIV", line)
            b = self.stack.pop()
            a = self.stack.pop()
            if b == 0:
                raise VMRuntimeError("Division by zero", line)
            self.stack.append(a / b)

        elif opcode == Opcode.NEG:
            self._check_stack(1, "NEG", line)
            a = self.stack.pop()
            self.stack.append(-a)

        elif opcode == Opcode.EQ:
            self._check_stack(2, "EQ", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a == b)

        elif opcode == Opcode.NEQ:
            self._check_stack(2, "NEQ", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a != b)

        elif opcode == Opcode.LT:
            self._check_stack(2, "LT", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a < b)

        elif opcode == Opcode.GT:
            self._check_stack(2, "GT", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a > b)

        elif opcode == Opcode.LTE:
            self._check_stack(2, "LTE", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a <= b)

        elif opcode == Opcode.GTE:
            self._check_stack(2, "GTE", line)
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a >= b)

        elif opcode == Opcode.JMP:
            frame = self._current_frame()
            frame.ip = operand

        elif opcode == Opcode.JMP_IF_FALSE:
            self._check_stack(1, "JMP_IF_FALSE", line)
            condition = self.stack.pop()
            if not self._is_truthy(condition):
                frame = self._current_frame()
                frame.ip = operand

        elif opcode == Opcode.JMP_IF_TRUE:
            self._check_stack(1, "JMP_IF_TRUE", line)
            condition = self.stack.pop()
            if self._is_truthy(condition):
                frame = self._current_frame()
                frame.ip = operand

        elif opcode == Opcode.CALL:
            func_name, arg_count = operand
            self._do_call(func_name, arg_count, line)

        elif opcode == Opcode.RETURN:
            self._do_return(line)

        elif opcode == Opcode.PRINT:
            self._check_stack(1, "PRINT", line)
            value = self.stack.pop()
            self._print_value(value)

        elif opcode == Opcode.HALT:
            # Clear call stack to end execution
            self.call_stack.clear()
            return

        else:
            raise VMRuntimeError(f"Unknown opcode: {opcode}", line)

    def _check_stack(self, needed: int, op_name: str, line: int):
        if len(self.stack) < needed:
            raise VMRuntimeError(f"Stack underflow: {op_name} needs {needed} values, "
                                 f"but stack has {len(self.stack)}", line)

    def _do_call(self, func_name: str, arg_count: int, line: int):
        """Call a function."""
        if func_name not in self.functions:
            raise VMRuntimeError(f"Undefined function '{func_name}'", line)

        func = self.functions[func_name]

        if arg_count != len(func.param_names):
            raise VMRuntimeError(
                f"Function '{func_name}' expects {len(func.param_names)} arguments, "
                f"but got {arg_count}", line
            )

        # Pop arguments from stack (in reverse order)
        args = []
        for _ in range(arg_count):
            if not self.stack:
                raise VMRuntimeError(f"Stack underflow: not enough arguments for call to '{func_name}'", line)
            args.insert(0, self.stack.pop())

        # Bind parameters to local variables
        locals_dict = {}
        for param_name, arg_value in zip(func.param_names, args):
            locals_dict[param_name] = arg_value

        # Create new frame for the function
        new_frame = CallFrame(
            code=func.body,
            ip=0,
            locals_dict=locals_dict,
        )
        self.call_stack.append(new_frame)

    def _do_return(self, line: int):
        """Return from a function call."""
        if not self.stack:
            return_value = None
        else:
            return_value = self.stack.pop()

        if len(self.call_stack) <= 1:
            # Returning from main - just halt
            self.stack.append(return_value)
            self.call_stack.clear()
            return

        # Pop current frame
        self.call_stack.pop()

        # Push return value onto stack for caller
        self.stack.append(return_value)

    def _print_value(self, value):
        """Print a value to stdout."""
        if value is None:
            print("null")
        elif isinstance(value, bool):
            print("true" if value else "false")
        elif isinstance(value, float):
            if value == int(value):
                print(f"{value:.1f}")
            else:
                print(repr(value))
        else:
            print(str(value))


def disassemble(bytecode: List[Instruction], functions: Dict[str, CompiledFunction] = None):
    """Print a disassembly of the bytecode."""
    print("=== MAIN ===")
    for i, (opcode, operand, line) in enumerate(bytecode):
        name = OPCODE_NAMES.get(opcode, str(opcode))
        op_str = f" {operand!r}" if operand is not None else ""
        print(f"  {i:04d}  {name:15s}{op_str:20s}  ; line {line}")

    if functions:
        for func_name, func in functions.items():
            print(f"\n=== FUNCTION {func_name} ({', '.join(func.param_names)}) ===")
            for i, (opcode, operand, line) in enumerate(func.body):
                name = OPCODE_NAMES.get(opcode, str(opcode))
                op_str = f" {operand!r}" if operand is not None else ""
                print(f"  {i:04d}  {name:15s}{op_str:20s}  ; line {line}")
