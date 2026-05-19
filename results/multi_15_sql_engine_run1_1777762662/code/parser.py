"""Recursive-descent parser for SQL statements."""

from lexer import Token, EOF, KEYWORD, IDENTIFIER, NUMBER, STRING, STAR, COMMA, \
    SEMICOLON, LPAREN, RPAREN, EQUALS, NOT_EQUALS, LESS, GREATER, \
    LESS_EQ, GREATER_EQ, DOT
from ast_nodes import (
    LoadStatement, SaveStatement, InsertStatement, SelectStatement,
    ColumnRef, Literal, Star, AggregateCall, BinaryOp, OrderItem, JoinClause
)


class ParseError(Exception):
    def __init__(self, message, line=None, col=None):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(message)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind, value=None):
        tok = self.peek()
        if tok.kind != kind or (value is not None and tok.value.upper() != value.upper()):
            expected_desc = value if value else kind
            raise ParseError(
                f"Syntax error at line {tok.line}, column {tok.col}: "
                f"expected {expected_desc} but got {tok.value!r}",
                tok.line, tok.col
            )
        return self.advance()

    def match(self, kind, value=None):
        tok = self.peek()
        if tok.kind == kind:
            if value is None:
                return True
            return tok.value.upper() == value.upper()
        return False

    def parse(self):
        """Parse one SQL statement. Returns a Statement or None for empty input."""
        tok = self.peek()
        if tok.kind == EOF:
            return None
        if tok.kind == SEMICOLON:
            self.advance()
            return None

        if tok.kind == KEYWORD:
            kw = tok.value.upper()
            if kw == 'LOAD':
                return self.parse_load()
            elif kw == 'SAVE':
                return self.parse_save()
            elif kw == 'INSERT':
                return self.parse_insert()
            elif kw == 'SELECT':
                return self.parse_select()
            else:
                raise ParseError(
                    f"Syntax error at line {tok.line}, column {tok.col}: "
                    f"unexpected keyword {tok.value!r}",
                    tok.line, tok.col
                )
        else:
            raise ParseError(
                f"Syntax error at line {tok.line}, column {tok.col}: "
                f"expected a statement keyword but got {tok.value!r}",
                tok.line, tok.col
            )

    def parse_name(self):
        """Parse a plain identifier and return its string value."""
        tok = self.expect(IDENTIFIER)
        return tok.value

    def parse_load(self):
        self.expect(KEYWORD, 'LOAD')
        table_name = self.parse_name()
        self.expect(KEYWORD, 'FROM')
        filepath = self.expect(STRING).value
        # Strip surrounding quotes
        filepath = filepath[1:-1]
        return LoadStatement(table_name, filepath)

    def parse_save(self):
        self.expect(KEYWORD, 'SAVE')
        table_name = self.parse_name()
        self.expect(KEYWORD, 'TO')
        filepath = self.expect(STRING).value
        filepath = filepath[1:-1]
        return SaveStatement(table_name, filepath)

    def parse_insert(self):
        self.expect(KEYWORD, 'INSERT')
        self.expect(KEYWORD, 'INTO')
        table_name = self.parse_name()
        self.expect(KEYWORD, 'VALUES')
        self.expect(LPAREN)
        values = self.parse_value_list()
        self.expect(RPAREN)
        return InsertStatement(table_name, values)

    def parse_value_list(self):
        values = []
        while True:
            values.append(self.parse_literal())
            if self.match(COMMA):
                self.advance()
            else:
                break
        return values

    def parse_literal(self):
        tok = self.peek()
        if tok.kind == NUMBER:
            self.advance()
            # Determine if integer or float
            if '.' in tok.value:
                return Literal(float(tok.value))
            return Literal(int(tok.value))
        elif tok.kind == STRING:
            self.advance()
            return Literal(tok.value[1:-1])  # strip quotes
        else:
            raise ParseError(
                f"Syntax error at line {tok.line}, column {tok.col}: "
                f"expected a literal value but got {tok.value!r}",
                tok.line, tok.col
            )

    def parse_identifier(self):
        tok = self.expect(IDENTIFIER)
        table = None
        name = tok.value
        # Check for qualified name: table.column
        if self.match(DOT):
            self.advance()
            col_tok = self.expect(IDENTIFIER)
            table = name
            name = col_tok.value
        return ColumnRef(name, table)

    def parse_maybe_qualified_star(self):
        """Parse * or table.*"""
        if self.match(STAR):
            self.advance()
            return Star()
        tok = self.expect(IDENTIFIER)
        if self.match(DOT):
            self.advance()
            self.expect(STAR)
            return ColumnRef('*', tok.value)
        # It's just an identifier - but we expected star context
        # Rewind: this shouldn't happen due to grammar, but handle gracefully
        return ColumnRef(tok.value, None)

    def parse_select(self):
        self.expect(KEYWORD, 'SELECT')

        select_items = self.parse_select_items()

        self.expect(KEYWORD, 'FROM')

        # Parse from tables
        from_tables = []
        table_name = self.parse_identifier().name
        from_tables.append(table_name)

        join = None

        # Check for INNER JOIN
        if self.match(KEYWORD, 'INNER'):
            self.advance()  # INNER
            self.expect(KEYWORD, 'JOIN')
            join_table = self.parse_identifier().name
            self.expect(KEYWORD, 'ON')
            left_col = self.parse_identifier()
            self.expect(EQUALS)
            right_col = self.parse_identifier()
            join = JoinClause(join_table, left_col, right_col)
            from_tables.append(join_table)

        where = None
        if self.match(KEYWORD, 'WHERE'):
            self.advance()
            where = self.parse_or_expression()

        group_by = None
        if self.match(KEYWORD, 'GROUP'):
            self.advance()
            self.expect(KEYWORD, 'BY')
            group_by = self.parse_column_list()

        order_by = None
        if self.match(KEYWORD, 'ORDER'):
            self.advance()
            self.expect(KEYWORD, 'BY')
            order_by = self.parse_order_items()

        limit = None
        if self.match(KEYWORD, 'LIMIT'):
            self.advance()
            limit_tok = self.expect(NUMBER)
            limit = int(limit_tok.value)

        stmt = SelectStatement(select_items, from_tables, where,
                               order_by, limit, group_by)
        stmt.join = join
        return stmt

    def parse_select_items(self):
        items = []
        while True:
            items.append(self.parse_select_item())
            if self.match(COMMA):
                self.advance()
            else:
                break
        return items

    def parse_select_item(self):
        # Could be: *, table.*, aggregate(col), col, table.col
        if self.match(STAR):
            self.advance()
            return Star()
        # Check for qualified star: table.*
        # Look ahead
        if self.match(IDENTIFIER):
            # Save position
            saved_pos = self.pos
            tok = self.advance()
            if self.match(DOT):
                self.advance()
                if self.match(STAR):
                    self.advance()
                    return ColumnRef('*', tok.value)
                elif self.match(IDENTIFIER):
                    # It's table.column - consume and return
                    col_tok = self.advance()
                    # Check if this is actually an aggregate call
                    if self.match(LPAREN):
                        # aggregate function with table.col
                        self.advance()
                        arg = ColumnRef(col_tok.value, tok.value)
                        self.expect(RPAREN)
                        return AggregateCall(tok.value, arg)
                    return ColumnRef(col_tok.value, tok.value)
                else:
                    raise ParseError(
                        f"Syntax error at line {self.peek().line}, column {self.peek().col}: "
                        f"expected column name or * after dot",
                        self.peek().line, self.peek().col
                    )
            elif self.match(LPAREN):
                # aggregate function: COUNT, SUM, AVG, MIN, MAX
                self.advance()
                arg = self.parse_aggregate_arg()
                self.expect(RPAREN)
                return AggregateCall(tok.value, arg)
            else:
                # Plain unqualified column
                return ColumnRef(tok.value, None)

        raise ParseError(
            f"Syntax error at line {self.peek().line}, column {self.peek().col}: "
            f"expected column name, *, or aggregate function",
            self.peek().line, self.peek().col
        )

    def parse_aggregate_arg(self):
        if self.match(STAR):
            self.advance()
            return Star()
        return self.parse_identifier()

    def parse_column_list(self):
        cols = []
        while True:
            cols.append(self.parse_identifier())
            if self.match(COMMA):
                self.advance()
            else:
                break
        return cols

    def parse_order_items(self):
        items = []
        while True:
            col = self.parse_identifier()
            direction = 'ASC'
            if self.match(KEYWORD, 'ASC'):
                self.advance()
                direction = 'ASC'
            elif self.match(KEYWORD, 'DESC'):
                self.advance()
                direction = 'DESC'
            items.append(OrderItem(col, direction))
            if self.match(COMMA):
                self.advance()
            else:
                break
        return items

    def parse_or_expression(self):
        left = self.parse_and_expression()
        while self.match(KEYWORD, 'OR'):
            self.advance()
            right = self.parse_and_expression()
            left = BinaryOp(left, 'OR', right)
        return left

    def parse_and_expression(self):
        left = self.parse_comparison()
        while self.match(KEYWORD, 'AND'):
            self.advance()
            right = self.parse_comparison()
            left = BinaryOp(left, 'AND', right)
        return left

    def parse_comparison(self):
        # Could be a parenthesized expression
        if self.match(LPAREN):
            self.advance()
            expr = self.parse_or_expression()
            self.expect(RPAREN)
            return expr

        left = self.parse_operand()
        if self.match(EQUALS):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '=', right)
        elif self.match(NOT_EQUALS):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '!=', right)
        elif self.match(LESS):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '<', right)
        elif self.match(GREATER):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '>', right)
        elif self.match(LESS_EQ):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '<=', right)
        elif self.match(GREATER_EQ):
            self.advance()
            right = self.parse_operand()
            return BinaryOp(left, '>=', right)
        else:
            return left

    def parse_operand(self):
        if self.match(NUMBER) or self.match(STRING):
            return self.parse_literal()
        return self.parse_identifier()
