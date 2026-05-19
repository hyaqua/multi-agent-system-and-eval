"""SQL Parser - Parses tokens into AST nodes."""

from dataclasses import dataclass, field
from enum import Enum, auto
from lexer import TokenType, Token, Lexer


class ASTNode:
    pass


@dataclass
class LoadStatement(ASTNode):
    table: str
    filename: str


@dataclass
class SaveStatement(ASTNode):
    table: str
    filename: str


@dataclass
class InsertStatement(ASTNode):
    table: str
    values: list[str]


@dataclass
class ColumnRef(ASTNode):
    name: str
    table: str | None = None

    def __repr__(self):
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name


class AggFunc(Enum):
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()


@dataclass
class AggCall(ASTNode):
    func: AggFunc
    arg: ColumnRef | None  # None for COUNT(*)


@dataclass
class SelectColumn(ASTNode):
    """A single column in SELECT: either a ColumnRef, AggCall, or Star."""
    expr: ColumnRef | AggCall | None  # None means *
    alias: str | None = None


@dataclass
class BinaryOp(ASTNode):
    op: str  # AND, OR
    left: 'Expr'
    right: 'Expr'


@dataclass
class Comparison(ASTNode):
    op: str  # =, !=, <, >, <=, >=
    left: ColumnRef
    right: str | int | float | ColumnRef  # literal value or column ref


# Expr is a condition in WHERE
Expr = BinaryOp | Comparison


@dataclass
class JoinClause(ASTNode):
    table: str
    left_col: ColumnRef
    right_col: ColumnRef


@dataclass
class OrderItem(ASTNode):
    column: ColumnRef
    direction: str  # 'ASC' or 'DESC'


@dataclass
class SelectStatement(ASTNode):
    columns: list[SelectColumn]  # empty list means SELECT *
    table: str
    alias: str | None = None
    where: Expr | None = None
    group_by: list[ColumnRef] = field(default_factory=list)
    order_by: list[OrderItem] = field(default_factory=list)
    limit: int | None = None
    join: JoinClause | None = None


class ParseError(Exception):
    def __init__(self, message: str, pos: int):
        self.message = message
        self.pos = pos
        super().__init__(f"Parse error at position {pos}: {message}")


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _advance(self):
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, type_: TokenType, error_msg: str = None) -> Token:
        tok = self._current()
        if tok.type != type_:
            if error_msg is None:
                error_msg = f"Expected {type_.name}, got {tok.type.name} ('{tok.value}')"
            raise ParseError(error_msg, tok.pos)
        return self._advance()

    def _match(self, type_: TokenType) -> bool:
        return self._current().type == type_

    def _match_any(self, *types: TokenType) -> bool:
        return self._current().type in types

    def parse_statement(self) -> ASTNode:
        tok = self._current()
        if tok.type == TokenType.LOAD:
            return self.parse_load()
        elif tok.type == TokenType.SAVE:
            return self.parse_save()
        elif tok.type == TokenType.SELECT:
            return self.parse_select()
        elif tok.type == TokenType.INSERT:
            return self.parse_insert()
        else:
            raise ParseError(f"Unexpected token: '{tok.value}' ({tok.type.name}). Expected LOAD, SAVE, SELECT, or INSERT.", tok.pos)

    def parse_load(self) -> LoadStatement:
        self._expect(TokenType.LOAD)
        table = self._expect(TokenType.IDENTIFIER, "Expected table name after LOAD").value
        # Optional FROM keyword
        if self._match(TokenType.FROM):
            self._advance()
        filename = self._expect(TokenType.STRING, "Expected filename string after LOAD table").value
        return LoadStatement(table=table, filename=filename)

    def parse_save(self) -> SaveStatement:
        self._expect(TokenType.SAVE)
        table = self._expect(TokenType.IDENTIFIER, "Expected table name after SAVE").value
        # Optional TO keyword
        if self._match(TokenType.TO):
            self._advance()
        filename = self._expect(TokenType.STRING, "Expected filename string after SAVE table").value
        return SaveStatement(table=table, filename=filename)

    def parse_insert(self) -> InsertStatement:
        self._expect(TokenType.INSERT)
        self._expect(TokenType.INTO)
        table = self._expect(TokenType.IDENTIFIER, "Expected table name after INSERT INTO").value
        # Optional VALUES keyword
        if self._match(TokenType.VALUES):
            self._advance()
        self._expect(TokenType.LPAREN, "Expected '(' before values list")
        values = []
        while not self._match(TokenType.RPAREN):
            if self._match(TokenType.STRING):
                values.append(self._advance().value)
            elif self._match(TokenType.NUMBER):
                values.append(self._advance().value)
            elif self._match(TokenType.IDENTIFIER):
                values.append(self._advance().value)
            else:
                tok = self._current()
                raise ParseError(f"Expected value, got '{tok.value}'", tok.pos)
            if self._match(TokenType.COMMA):
                self._advance()
        self._expect(TokenType.RPAREN, "Expected ')' after values list")
        return InsertStatement(table=table, values=values)

    def parse_select(self) -> SelectStatement:
        self._expect(TokenType.SELECT)

        columns = self.parse_select_columns()

        self._expect(TokenType.FROM, "Expected FROM after SELECT columns")
        table = self._expect(TokenType.IDENTIFIER, "Expected table name after FROM").value
        alias = None
        if self._match(TokenType.IDENTIFIER):
            # Could be an alias, or it could be a keyword like JOIN, WHERE, etc.
            # Check if next is not a keyword
            kw_types = {TokenType.JOIN, TokenType.INNER, TokenType.WHERE,
                        TokenType.GROUP, TokenType.ORDER, TokenType.LIMIT,
                        TokenType.AND, TokenType.OR}
            if self._current().type not in kw_types:
                alias = self._advance().value

        # Optional JOIN
        join = None
        if self._match(TokenType.INNER):
            self._advance()
            self._expect(TokenType.JOIN, "Expected JOIN after INNER")
            join_table = self._expect(TokenType.IDENTIFIER, "Expected table name after JOIN").value
            self._expect(TokenType.ON, "Expected ON after JOIN table")
            left_col = self.parse_column_ref()
            self._expect(TokenType.EQ, "Expected = in JOIN ON clause")
            right_col = self.parse_column_ref()
            join = JoinClause(table=join_table, left_col=left_col, right_col=right_col)

        # Optional WHERE
        where = None
        if self._match(TokenType.WHERE):
            self._advance()
            where = self.parse_expression()

        # Optional GROUP BY
        group_by = []
        if self._match(TokenType.GROUP):
            self._advance()
            self._expect(TokenType.BY, "Expected BY after GROUP")
            group_by = self.parse_column_list()

        # Optional ORDER BY
        order_by = []
        if self._match(TokenType.ORDER):
            self._advance()
            self._expect(TokenType.BY, "Expected BY after ORDER")
            order_by = self.parse_order_list()

        # Optional LIMIT
        limit = None
        if self._match(TokenType.LIMIT):
            self._advance()
            limit_tok = self._expect(TokenType.NUMBER, "Expected number after LIMIT")
            limit = int(limit_tok.value)

        # Allow trailing semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return SelectStatement(
            columns=columns,
            table=table,
            alias=alias,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            join=join,
        )

    def parse_select_columns(self) -> list[SelectColumn]:
        """Parse SELECT column list."""
        if self._match(TokenType.STAR):
            self._advance()
            return []  # Empty means SELECT *

        columns = []
        while True:
            col = self.parse_single_select_column()
            columns.append(col)
            if self._match(TokenType.COMMA):
                self._advance()
                continue
            break
        return columns

    def parse_single_select_column(self) -> SelectColumn:
        """Parse a single column in SELECT: agg_func(col), col, or table.col."""
        tok = self._current()

        # Check for aggregate function
        agg_types = {
            TokenType.COUNT: AggFunc.COUNT,
            TokenType.SUM: AggFunc.SUM,
            TokenType.AVG: AggFunc.AVG,
            TokenType.MIN: AggFunc.MIN,
            TokenType.MAX: AggFunc.MAX,
        }

        if tok.type in agg_types:
            agg_func = agg_types[tok.type]
            self._advance()
            self._expect(TokenType.LPAREN, f"Expected '(' after {tok.value}")
            if self._match(TokenType.STAR) and agg_func == AggFunc.COUNT:
                self._advance()
                self._expect(TokenType.RPAREN, "Expected ')' after COUNT(*)")
                return SelectColumn(expr=AggCall(func=agg_func, arg=None))
            else:
                col = self.parse_column_ref()
                self._expect(TokenType.RPAREN, "Expected ')' after aggregate argument")
                return SelectColumn(expr=AggCall(func=agg_func, arg=col))

        # Regular column reference
        col = self.parse_column_ref()
        return SelectColumn(expr=col)

    def parse_column_ref(self) -> ColumnRef:
        """Parse a column reference, optionally with table prefix."""
        name = self._expect(TokenType.IDENTIFIER, "Expected column name").value
        if self._match(TokenType.DOT):
            self._advance()
            col_name = self._expect(TokenType.IDENTIFIER, "Expected column name after .").value
            return ColumnRef(name=col_name, table=name)
        return ColumnRef(name=name)

    def parse_column_list(self) -> list[ColumnRef]:
        """Parse comma-separated column references."""
        cols = [self.parse_column_ref()]
        while self._match(TokenType.COMMA):
            self._advance()
            cols.append(self.parse_column_ref())
        return cols

    def parse_order_list(self) -> list[OrderItem]:
        """Parse ORDER BY items."""
        items = []
        while True:
            col = self.parse_column_ref()
            direction = 'ASC'
            if self._match_any(TokenType.ASC, TokenType.DESC):
                direction = self._advance().value
            items.append(OrderItem(column=col, direction=direction))
            if self._match(TokenType.COMMA):
                self._advance()
                continue
            break
        return items

    def parse_expression(self) -> Expr:
        """Parse WHERE clause expression. Handles AND, OR with correct precedence."""
        # OR has lower precedence, AND has higher
        left = self.parse_and_expr()
        while self._match(TokenType.OR):
            op = self._advance().value
            right = self.parse_and_expr()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_and_expr(self) -> Expr:
        left = self.parse_comparison()
        while self._match(TokenType.AND):
            op = self._advance().value
            right = self.parse_comparison()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_comparison(self) -> Comparison:
        """Parse a comparison: col op (literal | col)."""
        left = self.parse_column_ref()
        op_tok = self._current()
        if op_tok.type not in (TokenType.EQ, TokenType.NEQ, TokenType.LT,
                                TokenType.GT, TokenType.LE, TokenType.GE):
            raise ParseError(
                f"Expected comparison operator (=, !=, <, >, <=, >=), got '{op_tok.value}' ({op_tok.type.name})",
                op_tok.pos)
        op = self._advance().value

        # Right side can be a column reference, string, or number
        right_tok = self._current()
        if right_tok.type == TokenType.IDENTIFIER:
            right = self.parse_column_ref()
        elif right_tok.type == TokenType.STRING:
            right = self._advance().value
        elif right_tok.type == TokenType.NUMBER:
            v = self._advance().value
            try:
                right = int(v)
            except ValueError:
                right = float(v)
        else:
            raise ParseError(
                f"Expected value or column name, got '{right_tok.value}' ({right_tok.type.name})",
                right_tok.pos)

        return Comparison(op=op, left=left, right=right)


def parse_sql(text: str) -> ASTNode:
    """Convenience function to parse SQL text."""
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    # Remove EOF for cleaner error reporting, but parser handles it
    parser = Parser(tokens)
    statement = parser.parse_statement()
    # Check for extra tokens
    if parser.pos < len(tokens) and tokens[parser.pos].type != TokenType.EOF:
        tok = tokens[parser.pos]
        raise ParseError(f"Unexpected extra token: '{tok.value}'", tok.pos)
    return statement
