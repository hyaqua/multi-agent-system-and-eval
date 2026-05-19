"""Bytecode instruction opcodes for the stack-based VM."""

# Stack operations
LOAD_CONST = "LOAD_CONST"        # Push constant from pool
LOAD_FAST = "LOAD_FAST"          # Push local variable
STORE_FAST = "STORE_FAST"        # Store into local variable
LOAD_GLOBAL = "LOAD_GLOBAL"      # Push global variable by name index
STORE_GLOBAL = "STORE_GLOBAL"    # Store into global variable

# Arithmetic
BINARY_ADD = "BINARY_ADD"
BINARY_SUB = "BINARY_SUB"
BINARY_MUL = "BINARY_MUL"
BINARY_DIV = "BINARY_DIV"

# Unary
UNARY_NEG = "UNARY_NEG"

# Comparison
COMPARE_OP = "COMPARE_OP"

# Jumps
POP_JUMP_IF_FALSE = "POP_JUMP_IF_FALSE"
JUMP = "JUMP"

# Functions
CALL = "CALL"
RETURN = "RETURN"
MAKE_FUNCTION = "MAKE_FUNCTION"

# I/O
PRINT = "PRINT"

# Stack manipulation
POP = "POP"

# Special
LOAD_NULL = "LOAD_NULL"
