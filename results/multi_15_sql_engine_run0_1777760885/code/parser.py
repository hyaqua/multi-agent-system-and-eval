"""Parser: recursive descent, converts token list into AST nodes."""

from error import SQLError
from lexer import (
    TK_KEYWORD, TK_IDENTIFIER, TK_NUMBER, TK_STRING,
    TK_OPERATOR, TK_PUNCTUATION, TK_EOF,
)


# ── AST Node classes ──────────────────────────────────────────────

class ASTNode:
    pass

class Column(ASTNode):
    """A column reference: possibly qualified (table.column) or just column."""
    def __init__(self, name, table=None):
        self.name = name       # column name (string)
        self.table = table     # table qualifier (string or None)

    def __repr__(self):
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name

class Star(ASTNode):
    """SELECT * or table.*"""
    def __init__(self, table=None):
        self.table = table

    def __repr__(self):
        if self.table:
            return f"{self.table}.*"
        return "*"

class FunctionCall(ASTNode):
    """Aggregate: COUNT, SUM, AVG, MIN, MAX with optional argument."""
    def __init__(self, name, arg):
        self.name = name       # e.g. "COUNT", "SUM"
        self.arg = arg         # Column or Star or None

    def __repr__(self):
        arg_s = str(self.arg) if self.arg else ""
        return f"{self.name}({arg_s})"

class Literal(ASTNode):
    """String or number literal."""
    def __init__(self, value):
        self.value = value     # string (from TK_STRING or TK_NUMBER)

    def __repr__(self):
        return repr(self.value)

class BinaryOp(ASTNode):
    """Comparison or logical: left op right."""
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"({self.left} {self.op} {self.right})"

class SelectStatement(ASTNode):
    def __init__(self, columns, table, where=None, order_by=None,
                 limit=None, group_by=None, having=None, join=None):
        self.columns = columns         # list of Column / Star / FunctionCall
        self.table = table             # string (table name) for simple FROM
        self.where = where             # BinaryOp or None
        self.order_by = order_by       # list of (Column, ascending) or None
        self.limit = limit             # int or None
        self.group_by = group_by       # list of Column or None
        self.having = having           # BinaryOp or None
        self.join = join               # JoinNode or None

    def __repr__(self):
        parts = [f"SELECT {self.columns} FROM {self.table}"]
        if self.join:
            parts.append(f"JOIN {self.join}")
        if self.where:
            parts.append(f"WHERE {self.where}")
        if self.group_by:
            parts.append(f"GROUP BY {self.group_by}")
        if self.having:
            parts.append(f"HAVING {self.having}")
        if self.order_by:
            parts.append(f"ORDER BY {self.order_by}")
        if self.limit:
            parts.append(f"LIMIT {self.limit}")
        return " ".join(parts)

class JoinNode(ASTNode):
    """INNER JOIN table2 ON left = right"""
    def __init__(self, table, left_col, right_col):
        self.table = table             # string: table name to join
        self.left_col = left_col       # Column (qualified)
        self.right_col = right_col     # Column (qualified)

    def __repr__(self):
        return f"INNER JOIN {self.table} ON {self.left_col} = {self.right_col}"

class InsertStatement(ASTNode):
    def __init__(self, table, columns, values):
        self.table = table
        self.columns = columns       # list of Column or empty (all columns)
        self.values = values         # list of Literal

    def __repr__(self):
        if self.columns:
            return f"INSERT INTO {self.table} ({self.columns}) VALUES ({self.values})"
        return f"INSERT INTO {self.table} VALUES ({self.values})"

class LoadCommand(ASTNode):
    def __init__(self, table, filepath):
        self.table = table
        self.filepath = filepath

    def __repr__(self):
        return f"LOAD {self.table} FROM '{self.filepath}'"

class SaveCommand(ASTNode):
    def __init__(self, table, filepath):
        self.table = table
        self.filepath = filepath

    def __repr__(self):
        return f"SAVE {self.table} TO '{self.filepath}'"


# ── Parser ────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, type, value=None):
        t = self.peek()
        if t.type != type or (value is not None and t.value.upper() != value.upper()):
            expected = value if value else f"type {type}"
            got = f"{t.value!r} (type {t.type})"
            raise SQLError(f"Expected {expected} but got {got}", pos=t.pos)
        return self.consume()

    def match_keyword(self, *keywords):
        t = self.peek()
        if t.type == TK_KEYWORD and t.value in keywords:
            return self.consume()
        return None

    def match_type(self, ttype):
        if self.peek().type == ttype:
            return self.consume()
        return None

    def parse(self):
        """Entry point: dispatch on first keyword."""
        t = self.peek()
        if t.type == TK_EOF:
            return None
        if t.type == TK_KEYWORD:
            kw = t.value
            if kw == "LOAD":
                return self.parse_load()
            elif kw == "SAVE":
                return self.parse_save()
            elif kw == "SELECT":
                return self.parse_select()
            elif kw == "INSERT":
                return self.parse_insert()
            else:
                raise SQLError(f"Unexpected keyword: {kw}", pos=t.pos)
        raise SQLError(f"Unexpected token: {t.value!r}", pos=t.pos)

    # ── LOAD table FROM 'path' ──
    def parse_load(self):
        self.expect(TK_KEYWORD, "LOAD")
        table_name = self.expect(TK_IDENTIFIER).value
        self.expect(TK_KEYWORD, "FROM")
        path_token = self.expect(TK_STRING)
        return LoadCommand(table_name, path_token.value)

    # ── SAVE table TO 'path' ──
    def parse_save(self):
        self.expect(TK_KEYWORD, "SAVE")
        table_name = self.expect(TK_IDENTIFIER).value
        self.expect(TK_KEYWORD, "TO")  # Allow TO or FROM
        path_token = self.expect(TK_STRING)
        return SaveCommand(table_name, path_token.value)

    # ── INSERT INTO table [(cols)] VALUES (vals) ──
    def parse_insert(self):
        self.expect(TK_KEYWORD, "INSERT")
        self.expect(TK_KEYWORD, "INTO")
        table_name = self.expect(TK_IDENTIFIER).value
        columns = []
        if self.peek().type == TK_PUNCTUATION and self.peek().value == "(":
            self.consume()  # (
            columns = self.parse_column_list()
            self.expect(TK_PUNCTUATION, ")")
        self.expect(TK_KEYWORD, "VALUES")
        self.expect(TK_PUNCTUATION, "(")
        values = self.parse_value_list()
        self.expect(TK_PUNCTUATION, ")")
        return InsertStatement(table_name, columns, values)

    def parse_column_list(self):
        cols = []
        cols.append(self.parse_column_ref())
        while self.peek().type == TK_PUNCTUATION and self.peek().value == ",":
            self.consume()
            cols.append(self.parse_column_ref())
        return cols

    def parse_value_list(self):
        vals = []
        vals.append(self.parse_literal())
        while self.peek().type == TK_PUNCTUATION and self.peek().value == ",":
            self.consume()
            vals.append(self.parse_literal())
        return vals

    def parse_literal(self):
        t = self.peek()
        if t.type == TK_STRING:
            self.consume()
            return Literal(t.value)
        elif t.type == TK_NUMBER:
            self.consume()
            return Literal(t.value)
        else:
            raise SQLError(f"Expected a literal but got {t.value!r}", pos=t.pos)

    # ── SELECT ... ──
    def parse_select(self):
        self.expect(TK_KEYWORD, "SELECT")

        # SELECT columns
        columns = self.parse_select_columns()

        # FROM
        self.expect(TK_KEYWORD, "FROM")
        table_token = self.expect(TK_IDENTIFIER)
        table_name = table_token.value

        # Optional JOIN
        join = None
        if self.match_keyword("INNER"):
            self.expect(TK_KEYWORD, "JOIN")
            join_table = self.expect(TK_IDENTIFIER).value
            self.expect(TK_KEYWORD, "ON")
            left_col = self.parse_column_ref()
            self.expect(TK_OPERATOR, "=")
            right_col = self.parse_column_ref()
            join = JoinNode(join_table, left_col, right_col)

        # WHERE
        where = None
        if self.match_keyword("WHERE"):
            where = self.parse_expression()

        # GROUP BY
        group_by = None
        if self.match_keyword("GROUP"):
            self.expect(TK_KEYWORD, "BY")
            group_by = self.parse_column_list()

        # HAVING
        having = None
        if self.match_keyword("HAVING"):
            having = self.parse_expression()

        # ORDER BY
        order_by = None
        if self.match_keyword("ORDER"):
            self.expect(TK_KEYWORD, "BY")
            order_by = self.parse_order_specs()

        # LIMIT
        limit = None
        if self.match_keyword("LIMIT"):
            limit_token = self.expect(TK_NUMBER)
            limit = int(limit_token.value)

        return SelectStatement(
            columns=columns, table=table_name, where=where,
            order_by=order_by, limit=limit,
            group_by=group_by, having=having, join=join,
        )

    def parse_select_columns(self):
        """Parse the SELECT column list."""
        cols = []
        t = self.peek()
        if t.type == TK_OPERATOR and t.value == "*":
            self.consume()
            cols.append(Star())
        else:
            cols.append(self.parse_select_item())
            while self.peek().type == TK_PUNCTUATION and self.peek().value == ",":
                self.consume()
                cols.append(self.parse_select_item())
        return cols

    def parse_select_item(self):
        """Parse a single item in SELECT: column ref, function call, or star."""
        t = self.peek()
        if t.type == TK_OPERATOR and t.value == "*":
            self.consume()
            return Star()
        if t.type == TK_KEYWORD and t.value in ("COUNT", "SUM", "AVG", "MIN", "MAX"):
            return self.parse_function_call()
        return self.parse_column_ref()

    def parse_function_call(self):
        func_name = self.consume().value  # COUNT, SUM, etc.
        self.expect(TK_PUNCTUATION, "(")
        arg = None
        t = self.peek()
        if t.type == TK_OPERATOR and t.value == "*":
            self.consume()
            arg = Star()
        elif t.type == TK_PUNCTUATION and t.value == ")":
            pass  # e.g. COUNT() — treat as COUNT(*)
        else:
            arg = self.parse_column_ref()
        self.expect(TK_PUNCTUATION, ")")
        return FunctionCall(func_name, arg)

    def parse_column_ref(self):
        """Parse a column reference: ident or ident.ident """
        first = self.expect(TK_IDENTIFIER).value
        if self.peek().type == TK_PUNCTUATION and self.peek().value == ".":
            self.consume()
            second = self.expect(TK_IDENTIFIER).value
            return Column(name=second, table=first)
        return Column(name=first)

    # ── ORDER BY ──
    def parse_order_specs(self):
        specs = []
        col = self.parse_column_ref()
        asc = True
        if self.peek().type == TK_KEYWORD and self.peek().value in ("ASC", "DESC"):
            kw = self.consume().value
            asc = (kw == "ASC")
        specs.append((col, asc))
        while self.peek().type == TK_PUNCTUATION and self.peek().value == ",":
            self.consume()
            col = self.parse_column_ref()
            asc = True
            if self.peek().type == TK_KEYWORD and self.peek().value in ("ASC", "DESC"):
                kw = self.consume().value
                asc = (kw == "ASC")
            specs.append((col, asc))
        return specs

    # ── Expression parsing (WHERE, HAVING, ON) ──
    # Precedence (low to high): OR > AND > comparisons
    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.match_keyword("OR"):
            right = self.parse_and()
            left = BinaryOp(left, "OR", right)
        return left

    def parse_and(self):
        left = self.parse_comparison()
        while self.match_keyword("AND"):
            right = self.parse_comparison()
            left = BinaryOp(left, "AND", right)
        return left

    def parse_comparison(self):
        left = self.parse_primary()
        if self.peek().type == TK_OPERATOR and self.peek().value in (
            "=", "!=", "<>", "<", ">", "<=", ">="
        ):
            op = self.consume().value
            right = self.parse_primary()
            left = BinaryOp(left, op, right)
        return left

    def parse_primary(self):
        t = self.peek()
        # Parenthesized expression
        if t.type == TK_PUNCTUATION and t.value == "(":
            self.consume()  # (
            expr = self.parse_expression()
            self.expect(TK_PUNCTUATION, ")")
            return expr
        # Literal
        if t.type == TK_STRING:
            return Literal(self.consume().value)
        if t.type == TK_NUMBER:
            return Literal(self.consume().value)
        # Column reference (possibly table.col)
        if t.type == TK_IDENTIFIER:
            return self.parse_column_ref()
        # Function call (e.g. in HAVING)
        if t.type == TK_KEYWORD and t.value in ("COUNT", "SUM", "AVG", "MIN", "MAX"):
            return self.parse_function_call()
        raise SQLError(f"Unexpected token in expression: {t.value!r}", pos=t.pos)


def parse(tokens):
    """Convenience: parse token list into AST, skip optional semicolon."""
    parser = Parser(tokens)
    ast = parser.parse()
    # Consume optional semicolon
    if parser.peek().type == TK_PUNCTUATION and parser.peek().value == ";":
        parser.consume()
    # Ensure no trailing garbage
    if parser.peek().type != TK_EOF:
        t = parser.peek()
        raise SQLError(f"Unexpected trailing token: {t.value!r}", pos=t.pos)
    return ast
