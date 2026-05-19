"""AST node classes for SQL statements and expressions."""


class ASTNode:
    """Base class for all AST nodes."""
    pass


# ===== Expressions =====

class Expression(ASTNode):
    """Base class for expressions."""
    pass


class ColumnRef(Expression):
    """A column reference, optionally qualified with a table name."""

    def __init__(self, name: str, table: str = None):
        self.name = name
        self.table = table  # None if unqualified

    def __repr__(self):
        if self.table:
            return f"ColumnRef({self.table}.{self.name})"
        return f"ColumnRef({self.name})"


class Literal(Expression):
    """A literal value (string or number)."""

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Literal({self.value!r})"


class StarExpression(Expression):
    """SELECT * expression."""
    def __repr__(self):
        return "Star()"


class Comparison(Expression):
    """A comparison: left OP right."""

    def __init__(self, left: Expression, op: str, right: Expression):
        self.left = left
        self.op = op   # '=', '!=', '<', '>', '<=', '>='
        self.right = right

    def __repr__(self):
        return f"Comparison({self.left} {self.op} {self.right})"


class BinaryOp(Expression):
    """AND or OR combination of two expressions."""

    def __init__(self, left: Expression, op: str, right: Expression):
        self.left = left
        self.op = op   # 'AND' or 'OR'
        self.right = right

    def __repr__(self):
        return f"BinaryOp({self.left} {self.op} {self.right})"


class FunctionCall(Expression):
    """An aggregate function call: COUNT, SUM, AVG, MIN, MAX."""

    def __init__(self, func_name: str, arg: Expression, alias: str = None):
        self.func_name = func_name.upper()
        self.arg = arg  # Expression or StarExpression for COUNT(*)
        self.alias = alias

    def __repr__(self):
        return f"FunctionCall({self.func_name}({self.arg}))"


# ===== Statements =====

class Statement(ASTNode):
    """Base class for all statements."""
    pass


class SelectStmt(Statement):
    """A SELECT query."""

    def __init__(self):
        self.columns: list[Expression] = []     # list of expressions (ColumnRef, StarExpression, FunctionCall)
        self.table: str = None                   # FROM table
        self.joins: list['JoinClause'] = []       # INNER JOIN clauses
        self.where: Expression = None             # WHERE expression
        self.group_by: list[Expression] = []      # GROUP BY expressions
        self.order_by: list['OrderByItem'] = []   # ORDER BY items
        self.limit: int = None                    # LIMIT value


class JoinClause(ASTNode):
    """An INNER JOIN clause."""

    def __init__(self, table: str, on_condition: Expression):
        self.table = table
        self.on_condition = on_condition


class OrderByItem(ASTNode):
    """An item in ORDER BY."""

    def __init__(self, expr: Expression, desc: bool = False):
        self.expr = expr
        self.desc = desc


class InsertStmt(Statement):
    """INSERT INTO statement."""

    def __init__(self, table: str, values: list[Expression]):
        self.table = table
        self.values = values


class LoadStmt(Statement):
    """LOAD table FROM file."""

    def __init__(self, table: str, filepath: str):
        self.table = table
        self.filepath = filepath


class SaveStmt(Statement):
    """SAVE table TO file."""

    def __init__(self, table: str, filepath: str):
        self.table = table
        self.filepath = filepath
