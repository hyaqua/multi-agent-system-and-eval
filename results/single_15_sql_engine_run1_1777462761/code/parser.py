"""
SQL Parser for the SQL query engine.
Converts tokens from the lexer into AST nodes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

from lexer import Token, TokenType


# ──────────────────────────────────────────────
# AST Node Definitions
# ──────────────────────────────────────────────

@dataclass
class ColumnRef:
    """Reference to a column, optionally qualified with a table name."""
    name: str
    table: Optional[str] = None


@dataclass
class StarSelect:
    """Represents SELECT *."""
    pass


@dataclass
class AggregateCall:
    """An aggregate function call like COUNT(*), SUM(salary), etc."""
    func: str                     # COUNT, SUM, AVG, MIN, MAX
    arg: Union[ColumnRef, str]    # ColumnRef or '*' (for COUNT(*))

    @property
    def display_name(self) -> str:
        if isinstance(self.arg, str) and self.arg == '*':
            return f"{self.func}(*)"
        else:
            return f"{self.func}({self.arg.name})"


@dataclass
class Literal:
    """A literal value (string, number)."""
    value: Any


# Expression types that can appear in WHERE clauses
ExprNode = Union['Comparison', 'BinaryOp']


@dataclass
class Comparison:
    """A comparison like column op literal."""
    left: ColumnRef
    op: str       # =, !=, <, >, <=, >=
    right: Literal


@dataclass
class BinaryOp:
    """A logical AND or OR combining two expressions."""
    left: ExprNode
    op: str       # AND or OR
    right: ExprNode


@dataclass
class OrderExpr:
    """An ORDER BY entry: column and direction."""
    column: ColumnRef
    direction: str = 'ASC'   # ASC or DESC


@dataclass
class JoinClause:
    """An INNER JOIN clause."""
    table: str
    left_col: ColumnRef
    right_col: ColumnRef


@dataclass
class SelectStmt:
    """A SELECT statement."""
    columns: List[Union[StarSelect, ColumnRef, AggregateCall]]
    table: str
    joins: List[JoinClause] = field(default_factory=list)
    where: Optional[ExprNode] = None
    group_by: List[ColumnRef] = field(default_factory=list)
    order_by: List[OrderExpr] = field(default_factory=list)
    limit: Optional[int] = None


@dataclass
class InsertStmt:
    """An INSERT INTO statement."""
    table: str
    values: List[Any]


@dataclass
class LoadStmt:
    """A LOAD statement to load a CSV file."""
    table: str
    filename: str


@dataclass
class SaveStmt:
    """A SAVE statement to save a table to CSV."""
    table: str
    filename: str


# Union type for all statement kinds
Statement = Union[SelectStmt, InsertStmt, LoadStmt, SaveStmt]


# ──────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────

class ParserError(Exception):
    """Raised when the parser encounters invalid syntax."""

    def __init__(self, message: str, token: Token):
        self.token = token
        if token.type == TokenType.EOF:
            detail = "end of input"
        else:
            detail = f"'{token.value}'"
        super().__init__(f"Syntax Error: {message} near {detail} at position {token.pos}")


class Parser:
    """Recursive-descent parser for SQL statements."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ── Helpers ──────────────────────────────

    def peek(self) -> Token:
        """Return the current token without consuming it."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def match(self, *types: TokenType) -> Optional[Token]:
        """If the current token matches one of the given types, consume and return it."""
        if self.peek().type in types:
            return self.advance()
        return None

    def expect(self, type_: TokenType, error_msg: str = None) -> Token:
        """Consume a token of the expected type or raise an error."""
        tok = self.peek()
        if tok.type != type_:
            if error_msg is None:
                error_msg = f"Expected {type_.name}"
            raise ParserError(error_msg, tok)
        return self.advance()

    def require_eof(self):
        """Ensure there are no unexpected tokens after the statement."""
        if self.peek().type != TokenType.EOF:
            raise ParserError(
                f"Unexpected token after end of statement",
                self.peek()
            )

    # ── Entry point ─────────────────────────

    def parse(self) -> Statement:
        """Parse a complete SQL statement and return an AST node."""
        tok = self.peek()

        if tok.type == TokenType.SELECT:
            return self.parse_select()
        elif tok.type == TokenType.INSERT:
            return self.parse_insert()
        elif tok.type == TokenType.LOAD:
            return self.parse_load()
        elif tok.type == TokenType.SAVE:
            return self.parse_save()
        else:
            raise ParserError(
                f"Unexpected token. Expected SELECT, INSERT, LOAD, or SAVE",
                tok
            )

    # ── SELECT statement ────────────────────

    def parse_select(self) -> SelectStmt:
        """Parse SELECT ... FROM ... [JOIN ...] [WHERE ...] [GROUP BY ...] [ORDER BY ...] [LIMIT ...]"""
        self.expect(TokenType.SELECT)
        columns = self._parse_select_columns()

        self.expect(TokenType.FROM, "Expected FROM after SELECT columns")
        table = self.expect(TokenType.IDENTIFIER, "Expected table name after FROM").value

        # Optional JOINs (can be multiple)
        joins = []
        while self.peek().type == TokenType.INNER:
            joins.append(self._parse_join())

        # Optional WHERE
        where = None
        if self.match(TokenType.WHERE):
            where = self._parse_expression()

        # Optional GROUP BY
        group_by = []
        if self.match(TokenType.GROUP):
            self.expect(TokenType.BY, "Expected BY after GROUP")
            group_by = self._parse_column_list()

        # Optional ORDER BY
        order_by = []
        if self.match(TokenType.ORDER):
            self.expect(TokenType.BY, "Expected BY after ORDER")
            order_by = self._parse_order_list()

        # Optional LIMIT
        limit = None
        if self.match(TokenType.LIMIT):
            limit_tok = self.expect(TokenType.NUMBER, "Expected number after LIMIT")
            limit = int(limit_tok.value)

        # Optional semicolon
        self.match(TokenType.SEMICOLON)

        self.require_eof()

        return SelectStmt(
            columns=columns,
            table=table,
            joins=joins,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        )

    def _parse_select_columns(self) -> List[Union[StarSelect, ColumnRef, AggregateCall]]:
        """Parse the column list in SELECT: either * or a comma-separated list."""
        if self.match(TokenType.STAR):
            return [StarSelect()]

        columns = []
        while True:
            columns.append(self._parse_select_column())
            if not self.match(TokenType.COMMA):
                break
        return columns

    def _parse_select_column(self) -> Union[ColumnRef, AggregateCall]:
        """Parse a single column in SELECT: col_name, table.col, or AGG(col)."""
        tok = self.peek()

        # Check for aggregate function
        if tok.type in (TokenType.COUNT, TokenType.SUM, TokenType.AVG,
                        TokenType.MIN, TokenType.MAX):
            func_name = self.advance().value
            self.expect(TokenType.LPAREN, f"Expected '(' after {func_name}")
            if self.match(TokenType.STAR):
                arg = '*'
            else:
                arg = self._parse_column_ref()
            self.expect(TokenType.RPAREN, f"Expected ')' after {func_name} argument")
            return AggregateCall(func=func_name, arg=arg)

        # Otherwise it's a column reference
        return self._parse_column_ref()

    def _parse_column_ref(self) -> ColumnRef:
        """Parse a column reference: name or table.name."""
        name = self.expect(TokenType.IDENTIFIER, "Expected column name").value
        if self.match(TokenType.DOT):
            table = name
            col = self.expect(TokenType.IDENTIFIER, "Expected column name after '.'").value
            return ColumnRef(name=col, table=table)
        return ColumnRef(name=name)

    def _parse_column_list(self) -> List[ColumnRef]:
        """Parse a comma-separated list of column references."""
        cols = [self._parse_column_ref()]
        while self.match(TokenType.COMMA):
            cols.append(self._parse_column_ref())
        return cols

    # ── JOIN clause ─────────────────────────

    def _parse_join(self) -> JoinClause:
        """Parse INNER JOIN table ON col = col."""
        self.expect(TokenType.INNER)
        self.expect(TokenType.JOIN, "Expected JOIN after INNER")
        table = self.expect(TokenType.IDENTIFIER, "Expected table name after JOIN").value
        self.expect(TokenType.ON, "Expected ON after JOIN table")
        left = self._parse_column_ref()
        self.expect(TokenType.EQ, "Expected '=' in JOIN ON condition")
        right = self._parse_column_ref()
        return JoinClause(table=table, left_col=left, right_col=right)

    # ── ORDER BY ────────────────────────────

    def _parse_order_list(self) -> List[OrderExpr]:
        """Parse a comma-separated list of ORDER BY expressions."""
        orders = []
        while True:
            col = self._parse_column_ref()
            direction = 'ASC'
            if self.peek().type in (TokenType.ASC, TokenType.DESC):
                direction = self.advance().value
            orders.append(OrderExpr(column=col, direction=direction))
            if not self.match(TokenType.COMMA):
                break
        return orders

    # ── WHERE expression ────────────────────

    def _parse_expression(self) -> ExprNode:
        """Parse a WHERE expression: OR has lowest precedence, AND next, then comparisons."""
        return self._parse_or()

    def _parse_or(self) -> ExprNode:
        left = self._parse_and()
        while self.match(TokenType.OR):
            right = self._parse_and()
            left = BinaryOp(left=left, op='OR', right=right)
        return left

    def _parse_and(self) -> ExprNode:
        left = self._parse_comparison()
        while self.match(TokenType.AND):
            right = self._parse_comparison()
            left = BinaryOp(left=left, op='AND', right=right)
        return left

    def _parse_comparison(self) -> ExprNode:
        """Parse a comparison or parenthesized expression."""
        # Handle parenthesized expressions
        if self.match(TokenType.LPAREN):
            expr = self._parse_expression()
            self.expect(TokenType.RPAREN, "Expected ')' after expression")
            return expr

        left = self._parse_column_ref()
        op_token = self.match(TokenType.EQ, TokenType.NEQ, TokenType.LT,
                              TokenType.GT, TokenType.LTE, TokenType.GTE)
        if not op_token:
            raise ParserError(
                "Expected comparison operator (=, !=, <, >, <=, >=) after column",
                self.peek()
            )
        right = self._parse_literal()
        return Comparison(left=left, op=op_token.value, right=right)

    def _parse_literal(self) -> Literal:
        """Parse a literal value (string or number)."""
        tok = self.peek()
        if tok.type == TokenType.STRING:
            return Literal(self.advance().value)
        elif tok.type == TokenType.NUMBER:
            return Literal(self.advance().value)
        else:
            raise ParserError("Expected a literal value (string or number)", tok)

    # ── INSERT statement ────────────────────

    def parse_insert(self) -> InsertStmt:
        """Parse INSERT INTO table VALUES (v1, v2, ...)"""
        self.expect(TokenType.INSERT)
        self.expect(TokenType.INTO, "Expected INTO after INSERT")
        table = self.expect(TokenType.IDENTIFIER, "Expected table name after INSERT INTO").value
        self.expect(TokenType.VALUES, "Expected VALUES after table name")
        self.expect(TokenType.LPAREN, "Expected '(' before value list")
        values = []
        while True:
            values.append(self._parse_literal().value)
            if not self.match(TokenType.COMMA):
                break
        self.expect(TokenType.RPAREN, "Expected ')' after value list")
        self.match(TokenType.SEMICOLON)
        self.require_eof()
        return InsertStmt(table=table, values=values)

    # ── LOAD statement ──────────────────────

    def parse_load(self) -> LoadStmt:
        """Parse LOAD table_name FROM 'filename'"""
        self.expect(TokenType.LOAD)
        table = self.expect(TokenType.IDENTIFIER, "Expected table name after LOAD").value
        self.expect(TokenType.FROM, "Expected FROM after table name in LOAD")
        filename = self.expect(TokenType.STRING, "Expected quoted filename after FROM").value
        self.match(TokenType.SEMICOLON)
        self.require_eof()
        return LoadStmt(table=table, filename=filename)

    # ── SAVE statement ──────────────────────

    def parse_save(self) -> SaveStmt:
        """Parse SAVE table_name TO 'filename'"""
        self.expect(TokenType.SAVE)
        table = self.expect(TokenType.IDENTIFIER, "Expected table name after SAVE").value
        self.expect(TokenType.TO, "Expected TO after table name in SAVE")
        filename = self.expect(TokenType.STRING, "Expected quoted filename after TO").value
        self.match(TokenType.SEMICOLON)
        self.require_eof()
        return SaveStmt(table=table, filename=filename)
