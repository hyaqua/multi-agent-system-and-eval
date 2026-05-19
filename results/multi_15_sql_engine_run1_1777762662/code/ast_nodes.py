"""AST node definitions for the SQL engine."""


class Statement:
    """Base class for all statements."""
    pass


class LoadStatement(Statement):
    def __init__(self, table_name, filepath):
        self.table_name = table_name
        self.filepath = filepath


class SaveStatement(Statement):
    def __init__(self, table_name, filepath):
        self.table_name = table_name
        self.filepath = filepath


class InsertStatement(Statement):
    def __init__(self, table_name, values):
        self.table_name = table_name
        self.values = values


class ColumnRef:
    def __init__(self, name, table=None):
        self.table = table  # None if unqualified
        self.name = name


class Literal:
    def __init__(self, value):
        self.value = value


class Star:
    """Represents * in SELECT."""
    pass


class AggregateCall:
    def __init__(self, func_name, arg):
        self.func_name = func_name.upper()  # COUNT, SUM, AVG, MIN, MAX
        self.arg = arg  # ColumnRef or Star


class BinaryOp:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right


class OrderItem:
    def __init__(self, column_ref, direction='ASC'):
        self.column_ref = column_ref
        self.direction = direction.upper()


class JoinClause:
    def __init__(self, table_name, left_col, right_col):
        self.table_name = table_name
        self.left_col = left_col  # ColumnRef
        self.right_col = right_col  # ColumnRef


class SelectStatement(Statement):
    def __init__(self, select_items, from_tables, where=None,
                 order_by=None, limit=None, group_by=None):
        self.select_items = select_items  # list of ColumnRef, AggregateCall, or Star
        self.from_tables = from_tables  # list of table names (first is primary)
        self.where = where  # BinaryOp or None
        self.order_by = order_by  # list of OrderItem or None
        self.limit = limit  # int or None
        self.group_by = group_by  # list of ColumnRef or None
        self.join = None  # JoinClause or None
