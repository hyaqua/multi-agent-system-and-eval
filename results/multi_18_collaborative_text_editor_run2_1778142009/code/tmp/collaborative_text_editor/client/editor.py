"""
Editor logic: local state, OT, cursors, search, replace.
Manages the local document mirror and handles optimistic updates.
"""

import uuid
from collaborative_text_editor.common.ot import (
    apply_operation, inverse_operation, transform,
    offset_to_row_col, row_col_to_offset,
)
from collaborative_text_editor.common.protocol import OP_INSERT, OP_DELETE


class Editor:
    """Manages the local document state and editing operations."""

    def __init__(self, document="", revision=0, username=""):
        self.username = username
        self.doc = document
        self.revision = revision  # latest server revision we've seen

        # Cursor position as offset into document
        self.cursor_offset = 0

        # Pending operations: list of (msg_id, ops, base_revision)
        self.pending_ops = []

        # Remote cursors: username -> (row, col, revision)
        self.remote_cursors = {}

        # Undo stack: list of atomic ops sent (for local undo)
        self.undo_stack = []

        # Sent message IDs for matching acks
        self.sent_ids = set()

        # Search state
        self.search_query = ""
        self.search_matches = []
        self.search_current = -1

        # Replace state
        self.replace_active = False
        self.replace_find = ""
        self.replace_with = ""
        self.replace_matches = []
        self.replace_current = -1

    @property
    def cursor_row(self):
        row, _ = offset_to_row_col(self.doc, self.cursor_offset)
        return row

    @property
    def cursor_col(self):
        _, col = offset_to_row_col(self.doc, self.cursor_offset)
        return col

    def get_lines(self):
        """Return document as list of lines."""
        return self.doc.split('\n')

    def get_line_count(self):
        return self.doc.count('\n') + 1

    # ---- Cursor movement ----

    def move_cursor(self, row, col):
        """Move cursor to absolute row/col position."""
        self.cursor_offset = row_col_to_offset(self.doc, row, col)

    def move_cursor_relative(self, drow, dcol):
        """Move cursor by delta row/col."""
        row, col = offset_to_row_col(self.doc, self.cursor_offset)
        new_row = max(0, row + drow)
        new_col = max(0, col + dcol)
        self.cursor_offset = row_col_to_offset(self.doc, new_row, new_col)

    def move_cursor_to_offset(self, offset):
        """Move cursor to absolute offset."""
        self.cursor_offset = max(0, min(offset, len(self.doc)))

    def move_to_line_start(self):
        row, _ = offset_to_row_col(self.doc, self.cursor_offset)
        self.cursor_offset = row_col_to_offset(self.doc, row, 0)

    def move_to_line_end(self):
        row, _ = offset_to_row_col(self.doc, self.cursor_offset)
        lines = self.get_lines()
        if row < len(lines):
            self.cursor_offset = row_col_to_offset(self.doc, row, len(lines[row]))

    def move_word_left(self):
        """Move cursor to previous word boundary."""
        if self.cursor_offset == 0:
            return
        # Move left past any whitespace/non-word chars
        i = self.cursor_offset - 1
        while i > 0 and not self._is_word_char(self.doc[i]):
            i -= 1
        # Move to start of word
        while i > 0 and self._is_word_char(self.doc[i - 1]):
            i -= 1
        self.cursor_offset = i

    def move_word_right(self):
        """Move cursor to next word boundary."""
        if self.cursor_offset >= len(self.doc):
            return
        # Skip current word
        i = self.cursor_offset
        while i < len(self.doc) and self._is_word_char(self.doc[i]):
            i += 1
        # Skip whitespace/non-word
        while i < len(self.doc) and not self._is_word_char(self.doc[i]):
            i += 1
        self.cursor_offset = i

    def _is_word_char(self, ch):
        return ch.isalnum() or ch == '_'

    def page_up(self, page_size):
        row, col = offset_to_row_col(self.doc, self.cursor_offset)
        new_row = max(0, row - page_size)
        self.cursor_offset = row_col_to_offset(self.doc, new_row, col)

    def page_down(self, page_size):
        row, col = offset_to_row_col(self.doc, self.cursor_offset)
        total_lines = self.get_line_count()
        new_row = min(total_lines - 1, row + page_size)
        self.cursor_offset = row_col_to_offset(self.doc, new_row, col)

    # ---- Local editing (optimistic) ----

    def insert_char(self, char):
        """Insert a character at cursor position. Returns the op."""
        op = {"op": OP_INSERT, "pos": self.cursor_offset, "char": char}
        self._apply_local(op)
        return op

    def delete_char(self, backspace=False):
        """Delete character. If backspace, delete before cursor; else at cursor."""
        if backspace:
            if self.cursor_offset == 0:
                return None
            pos = self.cursor_offset - 1
            char = self.doc[pos] if pos < len(self.doc) else ""
        else:
            if self.cursor_offset >= len(self.doc):
                return None
            pos = self.cursor_offset
            char = self.doc[pos]

        op = {"op": OP_DELETE, "pos": pos, "char": char}
        self._apply_local(op)
        return op

    def _apply_local(self, op):
        """Apply operation locally, update cursor, push to pending."""
        self.doc = apply_operation(self.doc, op)
        # Update cursor
        if op["op"] == OP_INSERT:
            self.cursor_offset = op["pos"] + 1
        elif op["op"] == OP_DELETE:
            self.cursor_offset = op["pos"]

        # Push to pending
        msg_id = str(uuid.uuid4())
        self.pending_ops.append((msg_id, [op], self.revision))
        self.undo_stack.append(dict(op))

        # Update search match positions after edit
        self._invalidate_search()

    def _invalidate_search(self):
        """Clear search matches when document changes."""
        if self.search_matches:
            self.search_matches = []
            self.search_current = -1

    # ---- Apply remote operations ----

    def apply_remote(self, msg):
        """
        Apply a remote operation message.
        msg contains: id, username, ops (list of {op, pos, char}), base_revision
        """
        msg_id = msg.get("id")
        remote_username = msg.get("username", "")
        ops = msg.get("ops", [])
        msg_base_revision = msg.get("base_revision", 0)

        transformed_ops = []

        for op in ops:
            current_op = dict(op)

            # Transform through our pending ops
            for pend_id, pend_ops, pend_rev in self.pending_ops:
                for pend_op in pend_ops:
                    tiebreaker = None
                    if current_op["op"] == OP_INSERT and pend_op["op"] == OP_INSERT:
                        tiebreaker = remote_username
                    current_op = transform(current_op, pend_op, tiebreaker)
                    if current_op is None:
                        break
                if current_op is None:
                    break

            if current_op is not None:
                self.doc = apply_operation(self.doc, current_op)
                transformed_ops.append(current_op)

        # Update revision
        if msg_base_revision >= self.revision:
            self.revision = msg_base_revision + 1

        # If this was our own operation (ack from server), remove from pending
        if msg_id in self.sent_ids or remote_username == self.username:
            self.pending_ops = [
                (pid, pops, prev) for pid, pops, prev in self.pending_ops
                if pid != msg_id
            ]
            self.sent_ids.discard(msg_id)

        # Update remote cursor positions through transformed ops
        if remote_username != self.username:
            if remote_username in self.remote_cursors:
                row, col, rev = self.remote_cursors[remote_username]
                offset = row_col_to_offset(self.doc, row, col)
                # Apply the ops to shift the cursor
                for op in transformed_ops:
                    if op["op"] == OP_INSERT and op["pos"] <= offset:
                        offset += 1
                    elif op["op"] == OP_DELETE and op["pos"] < offset:
                        offset -= 1
                    elif op["op"] == OP_DELETE and op["pos"] == offset:
                        pass  # cursor at deleted char
                new_row, new_col = offset_to_row_col(self.doc, offset)
                self.remote_cursors[remote_username] = (new_row, new_col, self.revision)

        self._invalidate_search()

    # ---- Remote cursor updates ----

    def update_remote_cursor(self, username, position, revision):
        """Update a remote user's cursor position."""
        row = position.get("row", 0)
        col = position.get("col", 0)
        if username != self.username:
            self.remote_cursors[username] = (row, col, revision)

    def get_remote_cursor_line(self, username):
        """Get the line number for a remote user's cursor."""
        if username in self.remote_cursors:
            return self.remote_cursors[username][0]
        return 0

    # ---- Search ----

    def search(self, query):
        """Find all matches for query, return match count."""
        self.search_query = query
        self.search_matches = []
        self.search_current = -1
        if not query:
            return 0
        idx = 0
        while True:
            idx = self.doc.find(query, idx)
            if idx == -1:
                break
            self.search_matches.append(idx)
            idx += 1
        if self.search_matches:
            self.search_current = 0
            self.cursor_offset = self.search_matches[0]
        return len(self.search_matches)

    def search_next(self):
        """Go to next search match."""
        if not self.search_matches:
            return
        self.search_current = (self.search_current + 1) % len(self.search_matches)
        self.cursor_offset = self.search_matches[self.search_current]

    def search_prev(self):
        """Go to previous search match."""
        if not self.search_matches:
            return
        self.search_current = (self.search_current - 1) % len(self.search_matches)
        self.cursor_offset = self.search_matches[self.search_current]

    def get_search_match_offsets(self):
        """Return set of match offsets for highlighting."""
        return set(self.search_matches)

    # ---- Replace ----

    def start_replace(self, find_str, replace_str):
        """Initialize replace mode."""
        self.replace_find = find_str
        self.replace_with = replace_str
        self.replace_matches = []
        self.replace_current = -1
        if not find_str:
            return 0
        idx = 0
        while True:
            idx = self.doc.find(find_str, idx)
            if idx == -1:
                break
            self.replace_matches.append(idx)
            idx += 1
        if self.replace_matches:
            self.replace_current = 0
            self.cursor_offset = self.replace_matches[0]
        return len(self.replace_matches)

    def replace_current(self):
        """Replace the current match. Returns the op list for this replacement."""
        if self.replace_current < 0 or self.replace_current >= len(self.replace_matches):
            return None
        pos = self.replace_matches[self.replace_current]
        find_len = len(self.replace_find)

        # Delete old text
        ops = []
        for i in range(find_len):
            ops.append({
                "op": OP_DELETE,
                "pos": pos,
                "char": self.doc[pos] if pos < len(self.doc) else "",
            })

        # Insert new text
        for i, ch in enumerate(self.replace_with):
            ops.append({
                "op": OP_INSERT,
                "pos": pos + i,
                "char": ch,
            })

        # Apply all ops locally
        for op in ops:
            self._apply_local(op)

        # Remove this match and update remaining match positions
        del self.replace_matches[self.replace_current]
        shift = len(self.replace_with) - find_len
        for i in range(len(self.replace_matches)):
            if self.replace_matches[i] > pos:
                self.replace_matches[i] += shift

        if self.replace_matches:
            self.replace_current = min(self.replace_current, len(self.replace_matches) - 1)
            if self.replace_current >= 0:
                self.cursor_offset = self.replace_matches[self.replace_current]
        else:
            self.replace_current = -1

        return ops

    def skip_replace(self):
        """Skip current match and move to next."""
        if not self.replace_matches:
            self.replace_current = -1
            return
        self.replace_current = (self.replace_current + 1) % len(self.replace_matches)
        self.cursor_offset = self.replace_matches[self.replace_current]

    # ---- Undo ----

    def pop_undo_op(self):
        """Get the inverse of the last operation for sending to server."""
        if not self.undo_stack:
            return None
        op = self.undo_stack.pop()
        return inverse_operation(op)

    # ---- Full state reset (on reconnect) ----

    def reset_state(self, document, revision):
        """Reset editor state with fresh document from server."""
        self.doc = document
        self.revision = revision
        self.pending_ops = []
        self.undo_stack = []
        self.sent_ids = set()
        self.remote_cursors = {}
        self.search_matches = []
        self.search_current = -1
        # Keep cursor within bounds
        if self.cursor_offset > len(self.doc):
            self.cursor_offset = len(self.doc)
