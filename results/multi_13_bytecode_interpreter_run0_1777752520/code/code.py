"""Code object: holds bytecode, constant pool, and debug info."""


class Code:
    """Represents a compiled chunk of bytecode."""

    def __init__(self, bytecode, constants, local_names, name="<module>"):
        self.bytecode = bytecode          # List of (opcode, operand) tuples
        self.constants = constants        # List of constant values (int, float, str, Code)
        self.local_names = local_names    # Tuple of local variable name strings
        self.nlocals = len(local_names)
        self.name = name                  # For debugging

    def __repr__(self):
        return f"<Code {self.name!r}, {len(self.bytecode)} instrs, {len(self.constants)} constants, {len(self.local_names)} locals>"
