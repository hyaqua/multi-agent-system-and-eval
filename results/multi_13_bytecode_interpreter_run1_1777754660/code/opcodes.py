"""Opcodes, Instruction, and CodeObject definitions for the bytecode interpreter."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List


class Opcode(Enum):
    """Bytecode instruction opcodes."""
    PUSH_CONST = auto()      # Push constant from pool by index
    LOAD_VAR = auto()        # Load variable by name
    STORE_VAR = auto()       # Store to variable by name
    BINARY_ADD = auto()      # Pop b, pop a, push a + b
    BINARY_SUB = auto()      # Pop b, pop a, push a - b
    BINARY_MUL = auto()      # Pop b, pop a, push a * b
    BINARY_DIV = auto()      # Pop b, pop a, push a / b
    COMPARE_EQ = auto()      # Pop b, pop a, push a == b
    COMPARE_NE = auto()      # Pop b, pop a, push a != b
    COMPARE_LT = auto()      # Pop b, pop a, push a < b
    COMPARE_GT = auto()      # Pop b, pop a, push a > b
    COMPARE_LE = auto()      # Pop b, pop a, push a <= b
    COMPARE_GE = auto()      # Pop b, pop a, push a >= b
    JUMP = auto()            # Unconditional relative jump
    JUMP_IF_FALSE = auto()   # Pop value; if falsy, jump relative
    PRINT = auto()           # Pop value and print to stdout
    DEF_FUNC = auto()        # Create function from constant CodeObject
    CALL = auto()            # Pop function, pop args, call
    RETURN = auto()          # Pop return value, return to caller
    UNARY_NEG = auto()       # Pop value, push -value
    POP = auto()             # Pop and discard top of stack


@dataclass
class Instruction:
    """A single bytecode instruction."""
    opcode: Opcode
    operand: Any = None
    line_no: int = 0


@dataclass
class CodeObject:
    """A compiled bytecode object containing instructions and constants."""
    instructions: List[Instruction] = field(default_factory=list)
    constants: List[Any] = field(default_factory=list)
    param_count: int = 0
    param_names: List[str] = field(default_factory=list)
    name: str = "<module>"

    def add_constant(self, value: Any) -> int:
        """Add a constant and return its index."""
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def emit(self, opcode: Opcode, operand: Any = None, line_no: int = 0) -> None:
        """Append an instruction to this code object."""
        self.instructions.append(Instruction(opcode, operand, line_no))


# Mapping from token types to compare opcodes and binary opcodes for convenience
COMPARE_OPS = {
    '==': Opcode.COMPARE_EQ,
    '!=': Opcode.COMPARE_NE,
    '<': Opcode.COMPARE_LT,
    '>': Opcode.COMPARE_GT,
    '<=': Opcode.COMPARE_LE,
    '>=': Opcode.COMPARE_GE,
}

BINARY_OPS = {
    '+': Opcode.BINARY_ADD,
    '-': Opcode.BINARY_SUB,
    '*': Opcode.BINARY_MUL,
    '/': Opcode.BINARY_DIV,
}
