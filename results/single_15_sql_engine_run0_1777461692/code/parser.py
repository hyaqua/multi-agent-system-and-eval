"""Recursive descent parser for SQL queries."""

from typing import Optional

from lexer import Token, TokenType, Lexer, AGGREGATE_FUNCTIONS
from ast_nodes import (
    ColumnRef, StarSelect, Literal, BinaryOp, AggregateFunc,
    AliasedExpr, OrderItem, JoinClause,
    SelectStmt, InsertStmt, LoadStmt, SaveStmt,
)


class ParseError(Exception):
    """Error raised during parsing with position info."""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.token = token
        if token:
            msg = f"Parse error at line {token.line}, col {token.col}: {message}\n  Got token: {token.type.name} '{token.value}'"
        else:
            msg = f"Parse error: {message}"
        super().__init__(msg)


class Parser:
    """Recursive descent parser for SQL."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        """Return the current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self) -> Token:
        """Return the current token without consuming."""
        return self.current()

    def consume(self) -> Token:
        """Consume and return the current token."""
        token = self.current()
        self.pos += 1
        return token

    def expect(self, token_type: TokenType, error_msg: str = "") -> Token:
        """Expect a token of given type or raise error."""
        token = self.peek()
        if token.type != token_type:
            msg = error_msg or f"Expected {token_type.name}, got {token.type.name}"
            raise ParseError(msg, token)
        return self.consume()

    def match(self, token_type: TokenType) -> bool:
        """Check if current token matches type without consuming."""
        return self.peek().type == token_type

    def match_consume(self, token_type: TokenType) -> Optional[Token]:
        """If current token matches type, consume and return it."""
        if self.match(token_type):
            return self.consume()
        return None

    def parse(self):
        """Parse a complete statement."""
        token = self.peek()

        if token.type == TokenType.LOAD:
            return self.parse_load()
        elif token.type == TokenType.SAVE:
            return self.parse_save()
        elif token.type == TokenType.SELECT:
            return self.parse_select()
        elif token.type == TokenType.INSERT:
            return self.parse_insert()
        elif token.type == TokenType.EOF:
            return None
        else:
            raise ParseError(f"Unexpected token at start of statement: {token.type.name}", token)

    # ============================================================
    # LOAD / SAVE
    # ============================================================

    def parse_load(self) -> LoadStmt:
        """Parse LOAD table FROM 'filename'."""
        self.consume()  # LOAD
        table_token = self.expect(TokenType.IDENTIFIER, "Expected table name after LOAD")
        table_name = table_token.value
        self.expect(TokenType.FROM, "Expected FROM after table name in LOAD")
        filename_token = self.expect(TokenType.STRING, "Expected string filename after FROM")
        self._expect_eof_or_semicolon()
        return LoadStmt(table=table_name, filename=filename_token.value)

    def parse_save(self) -> SaveStmt:
        """Parse SAVE table TO 'filename'."""
        self.consume()  # SAVE
        table_token = self.expect(TokenType.IDENTIFIER, "Expected table name after SAVE")
        table_name = table_token.value
        # 'TO' is not a keyword - it's lexed as IDENTIFIER
        to_token = self.expect(TokenType.IDENTIFIER, "Expected TO after table name in SAVE")
        if to_token.value.upper() != 'TO':
            raise ParseError(f"Expected TO, got '{to_token.value}'", to_token)
        filename_token = self.expect(TokenType.STRING, "Expected string filename after TO")
        self._expect_eof_or_semicolon()
        return SaveStmt(table=table_name, filename=filename_token.value)

    # ============================================================
    # INSERT
    # ============================================================

    def parse_insert(self) -> InsertStmt:
        """Parse INSERT INTO table VALUES (v1, v2, ...)."""
        self.consume()  # INSERT
        self.expect(TokenType.INTO, "Expected INTO after INSERT")
        table_token = self.expect(TokenType.IDENTIFIER, "Expected table name after INSERT INTO")
        table_name = table_token.value
        self.expect(TokenType.VALUES, "Expected VALUES after table name")
        self.expect(TokenType.LPAREN, "Expected ( after VALUES")
        values = self._parse_value_list()
        self.expect(TokenType.RPAREN, "Expected ) after value list")
        self._expect_eof_or_semicolon()
        return InsertStmt(table=table_name, values=values)

    def _parse_value_list(self) -> list:
        """Parse a comma-separated list of literal values."""
        values = [self._parse_literal()]
        while self.match_consume(TokenType.COMMA):
            values.append(self._parse_literal())
        return values

    def _parse_literal(self):
        """Parse a literal value (number or string)."""
        token = self.peek()
        if token.type == TokenType.NUMBER:
            self.consume()
            # Return as int if no decimal point
            if '.' in token.value:
                return Literal(float(token.value))
            return Literal(int(token.value))
        elif token.type == TokenType.STRING:
            self.consume()
            return Literal(token.value)
        else:
            raise ParseError(f"Expected a literal value (number or string), got {token.type.name}", token)

    # ============================================================
    # SELECT
    # ============================================================

    def parse_select(self) -> SelectStmt:
        """Parse SELECT statement."""
        self.consume()  # SELECT

        # Parse select list
        columns = self._parse_select_list()

        # FROM
        self.expect(TokenType.FROM, "Expected FROM clause")
        table_token = self.expect(TokenType.IDENTIFIER, "Expected table name after FROM")
        table_name = table_token.value

        # Optional JOIN clause(s)
        joins = []
        while self.match(TokenType.INNER):
            joins.append(self._parse_join())

        # Optional WHERE
        where = None
        if self.match_consume(TokenType.WHERE):
            where = self._parse_expression()

        # Optional GROUP BY
        group_by = []
        if self.match(TokenType.GROUP):
            self.consume()
            self.expect(TokenType.BY, "Expected BY after GROUP")
            group_by = self._parse_group_by_list()

        # Optional ORDER BY
        order_by = []
        if self.match(TokenType.ORDER):
            self.consume()
            self.expect(TokenType.BY, "Expected BY after ORDER")
            order_by = self._parse_order_by_list()

        # Optional LIMIT
        limit = None
        if self.match_consume(TokenType.LIMIT):
            limit_token = self.expect(TokenType.NUMBER, "Expected number after LIMIT")
            limit = int(limit_token.value)

        self._expect_eof_or_semicolon()

        return SelectStmt(
            columns=columns,
            table=table_name,
            joins=joins,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        )

    def _parse_select_list(self) -> list:
        """Parse the column list after SELECT."""
        items = [self._parse_select_item()]
        while self.match_consume(TokenType.COMMA):
            items.append(self._parse_select_item())
        return items

    def _parse_select_item(self):
        """Parse a single item in the SELECT list."""
        expr = self._parse_primary()

        # Check for optional AS alias
        if self.match_consume(TokenType.AS):
            alias_token = self.expect(TokenType.IDENTIFIER, "Expected alias name after AS")
            return AliasedExpr(expr=expr, alias=alias_token.value)

        return expr

    def _parse_primary(self):
        """Parse a primary expression: aggregate, column ref, literal, or parenthesized expr."""
        token = self.peek()

        # Aggregate function
        if token.type in (TokenType.COUNT, TokenType.SUM, TokenType.AVG, TokenType.MIN, TokenType.MAX):
            return self._parse_aggregate()

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self.consume()
            expr = self._parse_expression()
            self.expect(TokenType.RPAREN, "Expected )")
            return expr

        # Star
        if token.type == TokenType.STAR:
            self.consume()
            return StarSelect()

        # Column reference or literal
        return self._parse_value()

    def _parse_value(self):
        """Parse a value: column reference or literal."""
        token = self.peek()

        if token.type == TokenType.IDENTIFIER:
            ident = self.consume()
            # Check for table.column syntax
            if self.match_consume(TokenType.DOT):
                col_token = self.expect(TokenType.IDENTIFIER, "Expected column name after .")
                return ColumnRef(name=col_token.value, table=ident.value)
            return ColumnRef(name=ident.value)

        return self._parse_literal()

    def _parse_aggregate(self) -> AggregateFunc:
        """Parse an aggregate function call."""
        func_token = self.consume()
        func_name = func_token.value.upper()

        self.expect(TokenType.LPAREN, f"Expected ( after {func_name}")
        arg = self._parse_primary()
        self.expect(TokenType.RPAREN, f"Expected ) after argument of {func_name}")

        alias = None
        if self.match_consume(TokenType.AS):
            alias_token = self.expect(TokenType.IDENTIFIER, "Expected alias after AS")
            alias = alias_token.value

        return AggregateFunc(func_name=func_name, arg=arg, alias=alias)

    # ============================================================
    # Expression parsing (WHERE clause, JOIN conditions)
    # ============================================================

    def _parse_expression(self):
        """Parse an expression: OR level (lowest precedence)."""
        return self._parse_or()

    def _parse_or(self):
        """Parse OR expressions."""
        left = self._parse_and()
        while self.match_consume(TokenType.OR):
            right = self._parse_and()
            left = BinaryOp(op='OR', left=left, right=right)
        return left

    def _parse_and(self):
        """Parse AND expressions."""
        left = self._parse_comparison()
        while self.match_consume(TokenType.AND):
            right = self._parse_comparison()
            left = BinaryOp(op='AND', left=left, right=right)
        return left

    def _parse_comparison(self):
        """Parse comparison expressions (=, !=, <, >, <=, >=)."""
        left = self._parse_value()

        token = self.peek()
        if token.type in (TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT,
                          TokenType.LE, TokenType.GE):
            op_token = self.consume()
            op_map = {
                TokenType.EQ: '=',
                TokenType.NE: '!=',
                TokenType.LT: '<',
                TokenType.GT: '>',
                TokenType.LE: '<=',
                TokenType.GE: '>=',
            }
            right = self._parse_value()
            return BinaryOp(op=op_map[op_token.type], left=left, right=right)

        return left

    # ============================================================
    # JOIN
    # ============================================================

    def _parse_join(self) -> JoinClause:
        """Parse INNER JOIN table ON condition."""
        self.consume()  # INNER
        self.expect(TokenType.JOIN, "Expected JOIN after INNER")
        table_token = self.expect(TokenType.IDENTIFIER, "Expected table name after JOIN")
        table_name = table_token.value
        self.expect(TokenType.ON, "Expected ON after table name in JOIN")
        condition = self._parse_expression()
        return JoinClause(table=table_name, condition=condition)

    # ============================================================
    # GROUP BY
    # ============================================================

    def _parse_group_by_list(self) -> list:
        """Parse GROUP BY column list."""
        columns = [self._parse_column_ref()]
        while self.match_consume(TokenType.COMMA):
            columns.append(self._parse_column_ref())
        return columns

    def _parse_column_ref(self) -> ColumnRef:
        """Parse a column reference, possibly with table prefix."""
        token = self.expect(TokenType.IDENTIFIER, "Expected column name")
        if self.match_consume(TokenType.DOT):
            col_token = self.expect(TokenType.IDENTIFIER, "Expected column name after .")
            return ColumnRef(name=col_token.value, table=token.value)
        return ColumnRef(name=token.value)

    # ============================================================
    # ORDER BY
    # ============================================================

    def _parse_order_by_list(self) -> list:
        """Parse ORDER BY items."""
        items = [self._parse_order_item()]
        while self.match_consume(TokenType.COMMA):
            items.append(self._parse_order_item())
        return items

    def _parse_order_item(self) -> OrderItem:
        """Parse a single ORDER BY item."""
        expr = self._parse_value()
        direction = "ASC"

        if self.match(TokenType.ASC):
            self.consume()
            direction = "ASC"
        elif self.match(TokenType.DESC):
            self.consume()
            direction = "DESC"

        return OrderItem(expr=expr, direction=direction)

    # ============================================================
    # Helpers
    # ============================================================

    def _expect_eof_or_semicolon(self):
        """Verify we're at end of statement."""
        token = self.peek()
        if token.type == TokenType.SEMICOLON:
            self.consume()
        elif token.type != TokenType.EOF:
            raise ParseError(f"Unexpected token after end of statement: {token.type.name} '{token.value}'", token)


def parse_sql(text: str):
    """Parse a SQL string and return the AST, or raise ParseError."""
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()
