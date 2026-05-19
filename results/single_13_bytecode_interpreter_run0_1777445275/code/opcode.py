"""Opcodes for the bytecode VM."""

from enum import Enum, auto


class Opcode(Enum):
    # Stack operations
    LOAD_CONST = auto()     # Push constant onto stack
    LOAD_VAR = auto()       # Push variable value onto stack
    STORE_VAR = auto()      # Pop stack, store in variable
    POP = auto()            # Discard top of stack

    # Arithmetic
    ADD = auto()            # a + b
    SUB = auto()            # a - b
    MUL = auto()            # a * b
    DIV = auto()            # a / b
    NEG = auto()            # -a

    # Comparisons
    EQ = auto()             # a == b
    NEQ = auto()            # a != b
    LT = auto()             # a < b
    GT = auto()             # a > b
    LTE = auto()            # a <= b
    GTE = auto()            # a >= b

    # Control flow
    JMP = auto()            # Unconditional jump
    JMP_IF_FALSE = auto()   # Pop, if false jump
    JMP_IF_TRUE = auto()    # Pop, if true jump

    # Functions
    CALL = auto()           # Call function
    RETURN = auto()         # Return from function

    # I/O
    PRINT = auto()          # Pop and print

    # Misc
    HALT = auto()           # Stop execution


# Human-readable names for disassembly
OPCODE_NAMES = {
    Opcode.LOAD_CONST: "LOAD_CONST",
    Opcode.LOAD_VAR: "LOAD_VAR",
    Opcode.STORE_VAR: "STORE_VAR",
    Opcode.POP: "POP",
    Opcode.ADD: "ADD",
    Opcode.SUB: "SUB",
    Opcode.MUL: "MUL",
    Opcode.DIV: "DIV",
    Opcode.NEG: "NEG",
    Opcode.EQ: "EQ",
    Opcode.NEQ: "NEQ",
    Opcode.LT: "LT",
    Opcode.GT: "GT",
    Opcode.LTE: "LTE",
    Opcode.GTE: "GTE",
    Opcode.JMP: "JMP",
    Opcode.JMP_IF_FALSE: "JMP_IF_FALSE",
    Opcode.JMP_IF_TRUE: "JMP_IF_TRUE",
    Opcode.CALL: "CALL",
    Opcode.RETURN: "RETURN",
    Opcode.PRINT: "PRINT",
    Opcode.HALT: "HALT",
}
