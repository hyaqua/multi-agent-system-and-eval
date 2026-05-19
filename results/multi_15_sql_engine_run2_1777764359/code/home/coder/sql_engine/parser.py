"""Recursive descent parser for SQL subset.

Builds an AST from a token list. Reports syntax errors with source position.
"""

from lexer import (
    Token,
    TOK_EOF, TOK_IDENTIFIER, TOK_STRING, TOK_NUMBER,
    TOK_COMMA, TOK_SEMICOLON, TOK_LPAREN, TOK_RPAREN,
    TOK_EQ, TOK_NEQ, TOK_LT, TOK_GT, TOK_LE, TOK_GE,
    TOK_DOT, TOK_STAR, TOK_PLUS, TOK_MINUS, TOK_SLASH,
    TOK_SELECT, TOK_FROM, TOK_WHERE, TOK_AND, TOK_OR,
    TOK_ORDER, TOK_BY, TOK_ASC, TOK_DESC, TOK_LIMIT,
    TOK_GROUP, TOK_INSERT, TOK_INTO, TOK_VALUES,
    TOK_INNER, TOK_JOIN, TOK_ON,
    TOK_LOAD, TOK_TO, TOK_SAVE,
    TOK_COUNT, TOK_SUM, TOK_AVG, TOK_MIN, TOK_MAX,
    TOK_AS,
    TOKEN_NAMES,
)
from ast import (
    SelectStmt, InsertStmt, LoadStmt, SaveStmt,
    ColumnRef, Literal, StarExpression,
    Comparison, BinaryOp, FunctionCall,
    JoinClause, OrderByItem,
)
from error import ParseError


AGGREGATE_FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}


class Parser:
    """Recursive descent parser."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self) -> Token:
        """Look at current token."""
        return self.current()

    def peek_type(self) -> int:
        return self.current().type

    def consume(self) -> Token:
        """Return current token and advance."""
        tok = self.current()
        self.pos += 1
        return tok

    def expect(self, tok_type: int) -> Token:
        """Consume a token of the expected type or raise an error."""
        if self.peek_type() == tok_type:
            return self.consume()
        expected = TOKEN_NAMES.get(tok_type, str(tok_type))
        found = TOKEN_NAMES.get(self.peek_type(), str(self.peek_type()))
        raise ParseError(
            f"Expected {expected} but found {found}",
            line=self.peek().line,
            column=self.peek().column
        )

    def skip_semicolons(self):
        """Skip any trailing semicolons."""
        while self.peek_type() == TOK_SEMICOLON:
            self.consume()

    # ===== Top Level =====

    def parse(self) -> 'ASTNode':
        """Parse the entire input and return an AST statement."""
        tok_type = self.peek_type()

        if tok_type == TOK_SELECT:
            stmt = self.parse_select()
            self.skip_semicolons()
            if self.peek_type() != TOK_EOF:
                raise ParseError(
                    f"Unexpected token after statement: {TOKEN_NAMES.get(self.peek_type(), self.peek().value)}",
                    line=self.peek().line,
                    column=self.peek().column
                )
            return stmt
        elif tok_type == TOK_INSERT:
            stmt = self.parse_insert()
            self.skip_semicolons()
            if self.peek_type() != TOK_EOF:
                raise ParseError(
                    f"Unexpected token after statement",
                    line=self.peek().line,
                    column=self.peek().column
                )
            return stmt
        elif tok_type == TOK_LOAD:
            stmt = self.parse_load()
            self.skip_semicolons()
            if self.peek_type() != TOK_EOF:
                raise ParseError(
                    f"Unexpected token after statement",
                    line=self.peek().line,
                    column=self.peek().column
                )
            return stmt
        elif tok_type == TOK_SAVE:
            stmt = self.parse_save()
            self.skip_semicolons()
            if self.peek_type() != TOK_EOF:
                raise ParseError(
                    f"Unexpected token after statement",
                    line=self.peek().line,
                    column=self.peek().column
                )
            return stmt
        elif tok_type == TOK_EOF:
            raise ParseError("Empty query", line=self.peek().line, column=self.peek().column)
        else:
            found = TOKEN_NAMES.get(tok_type, self.peek().value)
            raise ParseError(
                f"Unexpected token '{found}'. Expected SELECT, INSERT, LOAD, or SAVE.",
                line=self.peek().line,
                column=self.peek().column
            )

    # ===== SELECT =====

    def parse_select(self) -> SelectStmt:
        stmt = SelectStmt()
        self.expect(TOK_SELECT)

        # Parse column list
        self._parse_select_columns(stmt)

        # FROM
        self.expect(TOK_FROM)

        # Table name
        stmt.table = self._parse_identifier()

        # JOIN clauses
        while self.peek_type() == TOK_INNER:
            stmt.joins.append(self._parse_join())

        # WHERE
        if self.peek_type() == TOK_WHERE:
            self.consume()
            stmt.where = self._parse_expression()

        # GROUP BY
        if self.peek_type() == TOK_GROUP:
            self.consume()
            self.expect(TOK_BY)
            stmt.group_by = self._parse_expression_list()

        # ORDER BY
        if self.peek_type() == TOK_ORDER:
            self.consume()
            self.expect(TOK_BY)
            stmt.order_by = self._parse_order_by_list()

        # LIMIT
        if self.peek_type() == TOK_LIMIT:
            self.consume()
            tok = self.expect(TOK_NUMBER)
            if not isinstance(tok.value, int):
                raise ParseError(
                    "LIMIT must be an integer",
                    line=tok.line, column=tok.column
                )
            stmt.limit = tok.value

        return stmt

    def _parse_select_columns(self, stmt: SelectStmt):
        """Parse the column list in SELECT."""
        if self.peek_type() == TOK_STAR:
            self.consume()
            stmt.columns.append(StarExpression())
        else:
            stmt.columns = self._parse_select_expr_list()

    def _parse_select_expr_list(self) -> list:
        """Parse a comma-separated list of select expressions."""
        exprs = [self._parse_select_expr()]
        while self.peek_type() == TOK_COMMA:
            self.consume()
            exprs.append(self._parse_select_expr())
        return exprs

    def _parse_select_expr(self):
        """Parse a single select expression: column, aggregate, or arithmetic."""
        # Check if it's an aggregate function
        if self.peek_type() in (TOK_COUNT, TOK_SUM, TOK_AVG, TOK_MIN, TOK_MAX):
            func_name = self.consume().value
            self.expect(TOK_LPAREN)
            arg = self._parse_expression()  # could be * or column ref
            self.expect(TOK_RPAREN)

            # Optional alias
            alias = None
            if self.peek_type() == TOK_AS:
                self.consume()
                alias = self._parse_identifier()
            elif self.peek_type() == TOK_IDENTIFIER:
                alias = self._parse_identifier()

            # Validate argument for COUNT(*)
            if func_name == 'COUNT' and isinstance(arg, StarExpression):
                pass  # COUNT(*) is ok
            elif isinstance(arg, StarExpression):
                raise ParseError(
                    f"Only COUNT supports * as argument",
                    line=self.peek().line, column=self.peek().column
                )

            return FunctionCall(func_name, arg, alias)

        # Otherwise it's a column reference or expression
        expr = self._parse_expression()

        # Optional alias
        if self.peek_type() == TOK_AS:
            self.consume()
            alias = self._parse_identifier()
            if isinstance(expr, ColumnRef):
                expr = ColumnRef(expr.name, expr.table)
                # We handle aliases differently - wrap in a FunctionCall with alias concept
                # Actually let's just store alias on ColumnRef too, or handle in executor
                # For simplicity, we track aliases separately
        elif self.peek_type() == TOK_IDENTIFIER and isinstance(expr, ColumnRef):
            alias = self._parse_identifier()

        return expr

    # ===== INSERT =====

    def parse_insert(self) -> InsertStmt:
        self.expect(TOK_INSERT)
        self.expect(TOK_INTO)
        table = self._parse_identifier()
        self.expect(TOK_VALUES)
        self.expect(TOK_LPAREN)
        values = self._parse_value_list()
        self.expect(TOK_RPAREN)
        return InsertStmt(table, values)

    def _parse_value_list(self) -> list[Expression]:
        """Parse a comma-separated list of literal values."""
        values = [self._parse_primary()]
        while self.peek_type() == TOK_COMMA:
            self.consume()
            values.append(self._parse_primary())
        return values

    # ===== LOAD =====

    def parse_load(self) -> LoadStmt:
        self.expect(TOK_LOAD)
        table = self._parse_identifier()
        self.expect(TOK_FROM)
        tok = self.expect(TOK_STRING)
        return LoadStmt(table, tok.value)

    # ===== SAVE =====

    def parse_save(self) -> SaveStmt:
        self.expect(TOK_SAVE)
        table = self._parse_identifier()
        self.expect(TOK_TO)
        tok = self.expect(TOK_STRING)
        return SaveStmt(table, tok.value)

    # ===== JOIN =====

    def _parse_join(self) -> JoinClause:
        self.expect(TOK_INNER)
        self.expect(TOK_JOIN)
        table = self._parse_identifier()
        self.expect(TOK_ON)
        condition = self._parse_expression()
        return JoinClause(table, condition)

    # ===== ORDER BY =====

    def _parse_order_by_list(self) -> list[OrderByItem]:
        items = [self._parse_order_by_item()]
        while self.peek_type() == TOK_COMMA:
            self.consume()
            items.append(self._parse_order_by_item())
        return items

    def _parse_order_by_item(self) -> OrderByItem:
        expr = self._parse_expression()
        desc = False
        if self.peek_type() == TOK_DESC:
            self.consume()
            desc = True
        elif self.peek_type() == TOK_ASC:
            self.consume()
        return OrderByItem(expr, desc)

    # ===== Expression Parsing (precedence: OR < AND < comparison < arithmetic < primary) =====

    def _parse_expression(self) -> Expression:
        """Parse logical expression (AND/OR)."""
        return self._parse_or()

    def _parse_or(self) -> Expression:
        left = self._parse_and()
        while self.peek_type() == TOK_OR:
            self.consume()
            right = self._parse_and()
            left = BinaryOp(left, 'OR', right)
        return left

    def _parse_and(self) -> Expression:
        left = self._parse_comparison()
        while self.peek_type() == TOK_AND:
            self.consume()
            right = self._parse_comparison()
            left = BinaryOp(left, 'AND', right)
        return left

    def _parse_comparison(self) -> Expression:
        """Parse a comparison or fall through to arithmetic."""
        left = self._parse_additive()
        if self.peek_type() in (TOK_EQ, TOK_NEQ, TOK_LT, TOK_GT, TOK_LE, TOK_GE):
            op = self.consume().value
            right = self._parse_additive()
            return Comparison(left, op, right)
        return left

    def _parse_additive(self) -> Expression:
        """Parse + and - operations."""
        left = self._parse_multiplicative()
        while self.peek_type() in (TOK_PLUS, TOK_MINUS):
            op = self.consume().value
            right = self._parse_multiplicative()
            left = BinaryOp(left, op, right)
        return left

    def _parse_multiplicative(self) -> Expression:
        """Parse * and / operations."""
        left = self._parse_primary()
        while self.peek_type() in (TOK_STAR, TOK_SLASH):
            op = self.consume().value
            right = self._parse_primary()
            left = BinaryOp(left, op, right)
        return left

    def _parse_primary(self) -> Expression:
        """Parse a primary expression: literal, column reference, star, or parenthesized expression."""
        tok = self.peek()

        if tok.type == TOK_STAR:
            self.consume()
            return StarExpression()

        if tok.type == TOK_NUMBER:
            self.consume()
            return Literal(tok.value)

        if tok.type == TOK_STRING:
            self.consume()
            return Literal(tok.value)

        if tok.type == TOK_IDENTIFIER:
            return self._parse_column_or_agg()

        if tok.type == TOK_LPAREN:
            self.consume()
            expr = self._parse_expression()
            self.expect(TOK_RPAREN)
            return expr

        raise ParseError(
            f"Unexpected token '{TOKEN_NAMES.get(tok.type, tok.value)}'",
            line=tok.line,
            column=tok.column
        )

    def _parse_column_or_agg(self) -> Expression:
        """Parse a column reference (possibly qualified) or an aggregate function call."""
        name = self._parse_identifier()

        # Check for ( to see if it's an aggregate function call in expression context
        if self.peek_type() == TOK_LPAREN:
            func_name = name.upper()
            if func_name in AGGREGATE_FUNCTIONS:
                self.consume()  # (
                arg = self._parse_expression()
                self.expect(TOK_RPAREN)
                return FunctionCall(func_name, arg)
            else:
                raise ParseError(
                    f"Unknown function '{name}'",
                    line=self.peek().line, column=self.peek().column
                )

        # Check for dot for table.column qualification
        if self.peek_type() == TOK_DOT:
            self.consume()
            col_name = self._parse_identifier()
            return ColumnRef(col_name, table=name)

        return ColumnRef(name)

    def _parse_identifier(self) -> str:
        """Parse and return an identifier string."""
        tok = self.expect(TOK_IDENTIFIER)
        # Return the original value (preserve case for table/column names)
        # The value is the original lexeme
        return tok.value

    def _parse_expression_list(self) -> list[Expression]:
        """Parse a comma-separated list of expressions."""
        exprs = [self._parse_expression()]
        while self.peek_type() == TOK_COMMA:
            self.consume()
            exprs.append(self._parse_expression())
        return exprs


def parse(tokens: list[Token]) -> 'ASTNode':
    """Convenience function to parse a list of tokens."""
    parser = Parser(tokens)
    return parser.parse()
