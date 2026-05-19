"""Virtual Machine: executes bytecode with a stack-based architecture."""

import opcodes as opc


class RuntimeError_(Exception):
    """Runtime error with line number information."""

    def __init__(self, message, line=None):
        if line is not None:
            super().__init__(f"Runtime error at line {line}: {message}")
        else:
            super().__init__(f"Runtime error: {message}")
        self.line = line


class Function:
    """A callable wrapper around a Code object."""

    def __init__(self, code, vm):
        self.code = code
        self.vm = vm

    def __repr__(self):
        return f"<Function {self.code.name!r}>"


class Frame:
    """A call frame on the call stack."""

    def __init__(self, code, globals_dict):
        self.code = code
        self.ip = 0                      # instruction pointer
        self.stack = []                  # operand stack
        self.locals = [None] * code.nlocals  # local variables
        self.globals = globals_dict


class VirtualMachine:
    """Executes compiled Code objects."""

    def __init__(self):
        self.globals = {}       # name → value
        self.frames = []        # call stack of Frame objects

    def run(self, code):
        """Execute a top-level Code object."""
        # Create initial frame
        frame = Frame(code, self.globals)
        self.frames.append(frame)

        try:
            self._execute()
        except RuntimeError_:
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise RuntimeError_(str(e))

    def _current_frame(self):
        return self.frames[-1] if self.frames else None

    def _execute(self):
        while self.frames:
            frame = self._current_frame()
            code = frame.code

            while frame.ip < len(code.bytecode):
                instr, operand = code.bytecode[frame.ip]

                if instr == opc.LOAD_CONST:
                    frame.stack.append(code.constants[operand])

                elif instr == opc.LOAD_NULL:
                    frame.stack.append(None)

                elif instr == opc.LOAD_FAST:
                    if operand >= len(frame.locals):
                        raise RuntimeError_(
                            f"Local variable index {operand} out of range"
                        )
                    val = frame.locals[operand]
                    if val is None and operand < len(frame.locals):
                        # Uninitialized local
                        local_name = code.local_names[operand] if operand < len(code.local_names) else f"#{operand}"
                        raise RuntimeError_(
                            f"Local variable '{local_name}' referenced before assignment"
                        )
                    frame.stack.append(val)

                elif instr == opc.STORE_FAST:
                    if operand >= len(frame.locals):
                        raise RuntimeError_(
                            f"Local variable index {operand} out of range"
                        )
                    val = frame.stack.pop()
                    frame.locals[operand] = val

                elif instr == opc.LOAD_GLOBAL:
                    name = code.constants[operand]
                    if name not in frame.globals:
                        raise RuntimeError_(
                            f"Undefined variable '{name}'"
                        )
                    frame.stack.append(frame.globals[name])

                elif instr == opc.STORE_GLOBAL:
                    name = code.constants[operand]
                    val = frame.stack.pop()
                    frame.globals[name] = val

                elif instr == opc.BINARY_ADD:
                    b = frame.stack.pop()
                    a = frame.stack.pop()
                    # Allow string concatenation
                    if isinstance(a, str) or isinstance(b, str):
                        frame.stack.append(str(a) + str(b))
                    else:
                        frame.stack.append(a + b)

                elif instr == opc.BINARY_SUB:
                    b = frame.stack.pop()
                    a = frame.stack.pop()
                    self._check_numeric(a, b, "-")
                    frame.stack.append(a - b)

                elif instr == opc.BINARY_MUL:
                    b = frame.stack.pop()
                    a = frame.stack.pop()
                    self._check_numeric(a, b, "*")
                    frame.stack.append(a * b)

                elif instr == opc.BINARY_DIV:
                    b = frame.stack.pop()
                    a = frame.stack.pop()
                    self._check_numeric(a, b, "/")
                    if b == 0:
                        raise RuntimeError_("Division by zero")
                    frame.stack.append(a / b)

                elif instr == opc.UNARY_NEG:
                    a = frame.stack.pop()
                    self._check_numeric(a, None, "unary -")
                    frame.stack.append(-a)

                elif instr == opc.COMPARE_OP:
                    b = frame.stack.pop()
                    a = frame.stack.pop()
                    op = operand
                    if op == "==":
                        result = a == b
                    elif op == "!=":
                        result = a != b
                    elif op == "<":
                        result = a < b
                    elif op == ">":
                        result = a > b
                    elif op == "<=":
                        result = a <= b
                    elif op == ">=":
                        result = a >= b
                    else:
                        raise RuntimeError_(f"Unknown comparison operator: {op}")
                    frame.stack.append(result)

                elif instr == opc.POP_JUMP_IF_FALSE:
                    condition = frame.stack.pop()
                    if not condition:
                        frame.ip = operand
                        continue  # skip ip increment

                elif instr == opc.JUMP:
                    frame.ip = operand
                    continue  # skip ip increment

                elif instr == opc.CALL:
                    nargs = operand
                    # Arguments are on the stack in order (last arg on top)
                    args = []
                    for _ in range(nargs):
                        args.insert(0, frame.stack.pop())
                    func_obj = frame.stack.pop()

                    if isinstance(func_obj, Function):
                        func_code = func_obj.code

                        # Check argument count
                        if len(args) != func_code.nlocals:
                            raise RuntimeError_(
                                f"Function '{func_code.name}' expects {func_code.nlocals} "
                                f"arguments, got {len(args)}"
                            )

                        # Create new frame
                        new_frame = Frame(func_code, self.globals)
                        # Set arguments as locals
                        new_frame.locals = list(args)
                        # Pad if needed (should already match)
                        while len(new_frame.locals) < func_code.nlocals:
                            new_frame.locals.append(None)

                        self.frames.append(new_frame)
                        # Continue to next frame execution
                        frame.ip += 1
                        break  # inner loop; outer while will pick up new frame
                    else:
                        raise RuntimeError_(f"'{func_obj}' is not callable")

                elif instr == opc.RETURN:
                    return_value = frame.stack.pop() if frame.stack else None
                    self.frames.pop()
                    if self.frames:
                        # Push return value onto caller's stack
                        self._current_frame().stack.append(return_value)
                    # If no more frames, we're done
                    break  # exit inner while

                elif instr == opc.MAKE_FUNCTION:
                    code_obj = frame.stack.pop()
                    func = Function(code_obj, self)
                    frame.stack.append(func)

                elif instr == opc.PRINT:
                    val = frame.stack.pop()
                    # Print without newline if it's a string that already has one,
                    # but default to print() behavior
                    print(val)

                else:
                    raise RuntimeError_(f"Unknown opcode: {instr}")

                frame.ip += 1

            # If we broke out of inner loop due to CALL, continue outer loop
            # Otherwise, frame was popped (return), continue

        # Execution complete

    def _check_numeric(self, a, b, op_name):
        """Ensure operands are numeric."""
        if not isinstance(a, (int, float)):
            raise RuntimeError_(
                f"Operator '{op_name}' requires numeric operands, got {type(a).__name__}"
            )
        if b is not None and not isinstance(b, (int, float)):
            raise RuntimeError_(
                f"Operator '{op_name}' requires numeric operands, got {type(b).__name__}"
            )
