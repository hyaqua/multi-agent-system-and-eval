"""Virtual Machine: executes bytecode instructions."""

from compiler import Instruction, Opcode, Function


class RuntimeError_(Exception):
    """Raised on runtime errors during VM execution."""
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Runtime error at line {line}: {message}")
        self.line = line


class VirtualMachine:
    """Stack-based virtual machine that executes bytecode."""

    def __init__(self, constants: list, instructions: list[Instruction],
                 names: list[str]):
        self.constants = constants
        self.names = names
        self.instructions = instructions

        # Execution state
        self.ip = 0
        self.stack: list = []
        self.call_stack: list[tuple[int, list[Instruction], dict]] = []
        self.globals: dict = {}
        self.current_locals: dict = self.globals
        self.current_instructions: list[Instruction] = instructions

    def execute(self):
        """Run the program until completion."""
        while self.ip < len(self.current_instructions):
            instr = self.current_instructions[self.ip]
            self.ip += 1

            try:
                self._dispatch(instr)
            except RuntimeError_:
                raise
            except Exception as e:
                raise RuntimeError_(str(e), instr.line)

    def _dispatch(self, instr: Instruction):
        """Execute a single instruction."""
        op = instr.opcode
        arg = instr.arg

        if op == Opcode.PUSH_CONST:
            value = self.constants[arg]
            self.stack.append(value)

        elif op == Opcode.LOAD_VAR:
            name = self.names[arg]
            if name in self.current_locals:
                self.stack.append(self.current_locals[name])
            elif name in self.globals:
                self.stack.append(self.globals[name])
            else:
                raise RuntimeError_(
                    f"Undefined variable '{name}'", instr.line
                )

        elif op == Opcode.STORE_VAR:
            name = self.names[arg]
            value = self.stack.pop()
            # If we're inside a function (call stack not empty),
            # store in local scope; otherwise store in globals.
            if self.call_stack:
                self.current_locals[name] = value
            else:
                self.globals[name] = value

        elif op == Opcode.POP:
            self.stack.pop()

        elif op == Opcode.ADD:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a + b)

        elif op == Opcode.SUB:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a - b)

        elif op == Opcode.MUL:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a * b)

        elif op == Opcode.DIV:
            b = self.stack.pop()
            a = self.stack.pop()
            if b == 0:
                raise RuntimeError_("Division by zero", instr.line)
            self.stack.append(a / b)

        elif op == Opcode.NEG:
            a = self.stack.pop()
            self.stack.append(-a)

        elif op == Opcode.EQ:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a == b))

        elif op == Opcode.NE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a != b))

        elif op == Opcode.LT:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a < b))

        elif op == Opcode.GT:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a > b))

        elif op == Opcode.LE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a <= b))

        elif op == Opcode.GE:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(int(a >= b))

        elif op == Opcode.NOT:
            a = self.stack.pop()
            # Falsy: 0, 0.0, "", None
            self.stack.append(int(not a))

        elif op == Opcode.JMP:
            self.ip += arg - 1  # -1 because ip was already incremented

        elif op == Opcode.JZ:
            condition = self.stack.pop()
            if not condition:
                self.ip += arg - 1

        elif op == Opcode.PRINT:
            value = self.stack.pop()
            print(value)

        elif op == Opcode.MAKE_FUNCTION:
            func_obj = self.constants[arg]
            if not isinstance(func_obj, Function):
                raise RuntimeError_(
                    f"Expected Function in constant pool, got {type(func_obj).__name__}",
                    instr.line
                )
            self.stack.append(func_obj)

        elif op == Opcode.CALL:
            arg_count = arg
            # Pop function object
            func_obj = self.stack.pop()
            if not isinstance(func_obj, Function):
                raise RuntimeError_(
                    f"Expected Function, got {type(func_obj).__name__}",
                    instr.line
                )

            # Pop arguments (in reverse order)
            args = []
            for _ in range(arg_count):
                args.insert(0, self.stack.pop())

            if len(args) != func_obj.param_count:
                raise RuntimeError_(
                    f"Function expects {func_obj.param_count} arguments, "
                    f"got {len(args)}",
                    instr.line
                )

            # Create new local scope
            new_locals = {}
            for param_idx, arg_val in zip(func_obj.param_names, args):
                param_name = self.names[param_idx]
                new_locals[param_name] = arg_val

            # Push current frame to call stack
            self.call_stack.append(
                (self.ip, self.current_instructions, self.current_locals)
            )

            # Switch to function
            self.current_instructions = func_obj.instructions
            self.current_locals = new_locals
            self.ip = 0

        elif op == Opcode.RET:
            return_value = self.stack.pop()

            if not self.call_stack:
                # Return from top-level: push value back and halt
                self.stack.append(return_value)
                self.ip = len(self.current_instructions)  # halt
            else:
                # Restore previous frame
                return_ip, prev_instructions, prev_locals = self.call_stack.pop()
                self.current_instructions = prev_instructions
                self.current_locals = prev_locals
                self.ip = return_ip
                # Push return value to caller's stack
                self.stack.append(return_value)

        else:
            raise RuntimeError_(f"Unknown opcode: {op}", instr.line)
