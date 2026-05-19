"""AST node definitions for the SQL engine."""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ColumnRef:
    """Reference to a column, optionally qualified with table name."""
    name: str
    table: Optional[str] = None

    def __str__(self):
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name


@dataclass
class StarSelect:
    """SELECT *"""
    table: Optional[str] = None

    def __str__(self):
        if self.table:
            return f"{self.table}.*"
        return "*"


@dataclass
class Literal:
    """A literal value (number or string)."""
    value: Any

    def __str__(self):
        if isinstance(self.value, str):
            return f"'{self.value}'"
        return str(self.value)


@dataclass
class BinaryOp:
    """A binary operation: comparison, AND, OR."""
    op: str
    left: Any
    right: Any

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"


@dataclass
class AggregateFunc:
    """An aggregate function call: COUNT, SUM, AVG, MIN, MAX."""
    func_name: str  # COUNT, SUM, AVG, MIN, MAX
    arg: Any        # ColumnRef, StarSelect, or expression
    alias: Optional[str] = None

    def __str__(self):
        alias_str = f" AS {self.alias}" if self.alias else ""
        return f"{self.func_name}({self.arg}){alias_str}"


@dataclass
class AliasedExpr:
    """An expression with an optional alias."""
    expr: Any
    alias: Optional[str] = None

    def __str__(self):
        if self.alias:
            return f"{self.expr} AS {self.alias}"
        return str(self.expr)


@dataclass
class OrderItem:
    """An ORDER BY item: expression + ASC/DESC."""
    expr: Any
    direction: str = "ASC"  # ASC or DESC

    def __str__(self):
        return f"{self.expr} {self.direction}"


@dataclass
class JoinClause:
    """INNER JOIN clause."""
    table: str
    condition: Any  # BinaryOp for ON condition

    def __str__(self):
        return f"INNER JOIN {self.table} ON {self.condition}"


@dataclass
class SelectStmt:
    """SELECT statement AST node."""
    columns: list  # list of ColumnRef | StarSelect | AggregateFunc | AliasedExpr
    table: str
    joins: list = field(default_factory=list)  # list of JoinClause
    where: Optional[Any] = None
    group_by: list = field(default_factory=list)  # list of ColumnRef
    order_by: list = field(default_factory=list)  # list of OrderItem
    limit: Optional[int] = None

    def __str__(self):
        parts = [f"SELECT {', '.join(str(c) for c in self.columns)}"]
        parts.append(f"FROM {self.table}")
        for j in self.joins:
            parts.append(str(j))
        if self.where:
            parts.append(f"WHERE {self.where}")
        if self.group_by:
            parts.append(f"GROUP BY {', '.join(str(g) for g in self.group_by)}")
        if self.order_by:
            parts.append(f"ORDER BY {', '.join(str(o) for o in self.order_by)}")
        if self.limit is not None:
            parts.append(f"LIMIT {self.limit}")
        return " ".join(parts)


@dataclass
class InsertStmt:
    """INSERT INTO statement AST node."""
    table: str
    values: list  # list of literal values

    def __str__(self):
        vals = ", ".join(str(v) for v in self.values)
        return f"INSERT INTO {self.table} VALUES ({vals})"


@dataclass
class LoadStmt:
    """LOAD command AST node."""
    table: str
    filename: str

    def __str__(self):
        return f"LOAD {self.table} FROM '{self.filename}'"


@dataclass
class SaveStmt:
    """SAVE command AST node."""
    table: str
    filename: str

    def __str__(self):
        return f"SAVE {self.table} TO '{self.filename}'"
