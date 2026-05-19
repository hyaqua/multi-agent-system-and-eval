"""
Curses-based TUI for the collaborative text editor.

Handles:
- Document rendering with line numbers
- Cursor movement (arrows, Home, End, Page Up/Down, Ctrl+Arrows)
- Editing (insert, Backspace, Delete, Enter)
- Status bar and sidebar
- Remote cursor markers
- Search and replace modals
- Syntax highlighting integration
"""

import curses
import curses.ascii
import logging
import time
from typing import List, Dict

import client_edit
import syntax as syn

logger = logging.getLogger("client.ui")

# ── Colour pair constants (must match syntax.py) ────────────────────────────
PAIR_DEFAULT = 0
PAIR_KEYWORD = 1
PAIR_STRING = 2
PAIR_COMMENT = 3
PAIR_NUMBER = 4
PAIR_DECORATOR = 5
PAIR_BUILTIN = 6
PAIR_STATUS = 8
PAIR_SIDEBAR = 9
PAIR_CURSOR_MARK = 10
PAIR_SEARCH_HL = 11
PAIR_LINE_NUM = 12
PAIR_USER_COLORS_START = 20  # 20..27 for 8 users

# ── User colour mapping ─────────────────────────────────────────────────────
USER_COLORS = {
    1: curses.COLOR_RED,
    2: curses.COLOR_GREEN,
    3: curses.COLOR_YELLOW,
    4: curses.COLOR_BLUE,
    5: curses.COLOR_MAGENTA,
    6: curses.COLOR_CYAN,
    7: curses.COLOR_WHITE,
    8: curses.COLOR_RED,  # fallback, use bright variant if possible
}


class EditorUI:
    """Main curses editor UI."""

    def __init__(self, stdscr, document: client_edit.Document,
                 network, user_name: str, room_name: str):
        self.stdscr = stdscr
        self.doc = document
        self.net = network
        self.user_name = user_name
        self.room_name = room_name
        self.running = True

        # Cursor position (flat index into local_doc)
        self.cursor_pos = 0

        # Viewport
        self.scroll_top = 0
        self.scroll_left = 0

        # Remote users: {user: {color, cursor_pos}}
        self.remote_users: dict = {}
        self.user_color: int = 0
        self.connected = False

        # Lock state
        self.lock_holder: str | None = None
        self.lock_queue: list = []

        # Sidebar width
        self.sidebar_width = 22
        self.line_num_width = 6

        # Search state
        self.search_mode = False
        self.search_query = ""
        self.search_matches: list[int] = []
        self.search_current = -1
        self.replace_mode = False
        self.replace_text = ""

        # Input buffer for modal prompts
        self.modal_input = ""
        self.modal_prompt = ""

        # Cursor blink
        self.cursor_visible = True
        self.last_blink = time.time()

        # Setup curses
        self._setup_curses()

        # Window dimensions
        self.rows, self.cols = self.stdscr.getmaxyx()

    def _setup_curses(self):
        """Initialise curses colours and settings."""
        curses.curs_set(0)  # Hide hardware cursor, we draw our own
        self.stdscr.nodelay(True)  # Non-blocking input
        self.stdscr.keypad(True)

        # Initialise colours
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

            # Define colour pairs
            curses.init_pair(PAIR_KEYWORD, curses.COLOR_BLUE, -1)
            curses.init_pair(PAIR_STRING, curses.COLOR_GREEN, -1)
            curses.init_pair(PAIR_COMMENT, curses.COLOR_CYAN, -1)
            curses.init_pair(PAIR_NUMBER, curses.COLOR_MAGENTA, -1)
            curses.init_pair(PAIR_DECORATOR, curses.COLOR_YELLOW, -1)
            curses.init_pair(PAIR_BUILTIN, curses.COLOR_RED, -1)
            curses.init_pair(PAIR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(PAIR_SIDEBAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(PAIR_CURSOR_MARK, curses.COLOR_YELLOW, -1)
            curses.init_pair(PAIR_SEARCH_HL, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(PAIR_LINE_NUM, curses.COLOR_WHITE, -1)

            # User colours (background for remote cursor markers)
            for i in range(1, 9):
                color = USER_COLORS.get(i, curses.COLOR_WHITE)
                try:
                    curses.init_pair(PAIR_USER_COLORS_START + i - 1, color, -1)
                except curses.error:
                    pass

    def run(self):
        """Main event loop."""
        while self.running:
            self._handle_network()
            self._handle_input()
            self._render()
            time.sleep(0.01)  # ~100 FPS cap

    # ── Network handling ────────────────────────────────────────────────────

    def _handle_network(self):
        """Process incoming messages from the server."""
        messages = self.net.poll()
        for msg in messages:
            msg_type = msg.get("type", "")

            if msg_type == "ack":
                self._handle_ack(msg)
            elif msg_type == "operation":
                # Check if this is an ack (sender gets ack=True)
                if msg.get("ack"):
                    self.doc.handle_ack(msg)
                else:
                    self.doc.apply_remote_op(msg)
                self._update_cursor_bounds()
            elif msg_type == "cursor_update":
                user = msg.get("user", "")
                pos = msg.get("pos", 0)
                if user in self.remote_users:
                    self.remote_users[user]["cursor_pos"] = pos
            elif msg_type == "user_join":
                user = msg.get("user", "")
                color = msg.get("color", 1)
                if user != self.user_name:
                    self.remote_users[user] = {"color": color, "cursor_pos": 0}
            elif msg_type == "user_leave":
                user = msg.get("user", "")
                self.remote_users.pop(user, None)
            elif msg_type == "lock_status":
                self.lock_holder = msg.get("holder")
                self.lock_queue = msg.get("queue", [])
            elif msg_type == "lock_grant":
                self.lock_holder = msg.get("user")
            elif msg_type == "save_ack":
                pass  # Could flash a message
            elif msg_type == "error":
                logger.warning("Server error: %s", msg.get("message", ""))

    def _handle_ack(self, msg: dict):
        """Handle initial connection ack."""
        if msg.get("status") == "ok":
            document_text = msg.get("document", "")
            version = msg.get("version", 0)
            self.doc.full_resync(document_text, version)
            self.user_color = msg.get("user_color", 1)

            # Populate remote users
            clients = msg.get("clients", [])
            for c in clients:
                if c["user"] != self.user_name:
                    self.remote_users[c["user"]] = {
                        "color": c["color"],
                        "cursor_pos": c.get("cursor_pos", 0),
                    }

            self.lock_holder = msg.get("lock_holder")
            self.connected = True
            self._update_cursor_bounds()
        else:
            logger.error("Connection failed: %s", msg)

    def _update_cursor_bounds(self):
        """Clamp cursor to valid range."""
        max_pos = len(self.doc.get_local_doc())
        if self.cursor_pos > max_pos:
            self.cursor_pos = max_pos
        if self.cursor_pos < 0:
            self.cursor_pos = 0

    # ── Input handling ──────────────────────────────────────────────────────

    def _handle_input(self):
        """Process keyboard input."""
        try:
            ch = self.stdscr.get_wch()
        except curses.error:
            return

        if self.search_mode or self.replace_mode:
            self._handle_modal_input(ch)
            return

        if isinstance(ch, str):
            self._handle_char(ch)
        else:
            self._handle_key(ch)

    def _handle_char(self, ch: str):
        """Handle a regular character (insertion)."""
        # Check for Ctrl+key combinations
        if len(ch) == 1:
            code = ord(ch)
            if 1 <= code <= 26:  # Ctrl+A through Ctrl+Z
                self._handle_ctrl(chr(code + 96))
                return

        # Skip control characters
        if len(ch) == 1 and ord(ch) < 32:
            return

        # Check lock
        if self._is_locked_for_us():
            curses.beep()
            return

        # Insert character
        op_msg = self.doc.insert(self.cursor_pos, ch)
        self.net.send(op_msg)
        self.cursor_pos += len(ch)
        self._send_cursor()

    def _handle_key(self, key: int):
        """Handle special keys (arrows, etc.)."""
        if key == curses.KEY_UP:
            self._move_cursor_vertical(-1)
        elif key == curses.KEY_DOWN:
            self._move_cursor_vertical(1)
        elif key == curses.KEY_LEFT:
            self._move_cursor(-1)
        elif key == curses.KEY_RIGHT:
            self._move_cursor(1)
        elif key == curses.KEY_HOME:
            self._cursor_home()
        elif key == curses.KEY_END:
            self._cursor_end()
        elif key == curses.KEY_PPAGE:  # Page Up
            self._page_up()
        elif key == curses.KEY_NPAGE:  # Page Down
            self._page_down()
        elif key == curses.KEY_BACKSPACE or key == 127:
            self._handle_backspace()
        elif key == curses.KEY_DC:  # Delete
            self._handle_delete()
        elif key == curses.KEY_ENTER or key == 10 or key == 13:
            self._handle_enter()
        elif key == curses.KEY_SLEFT:  # Shift+Left (some terminals)
            self._word_left()
        elif key == curses.KEY_SRIGHT:  # Shift+Right (some terminals)
            self._word_right()
        elif key == curses.KEY_RESIZE:
            self.rows, self.cols = self.stdscr.getmaxyx()
        # Ctrl+Left and Ctrl+Right are handled via _handle_ctrl
        # But some terminals send them as KEY_SLEFT etc.
        # Try to detect: in some curses, KEY_SLEFT is 393 etc.
        # We handle this in _handle_char via Ctrl+B/F mapping
        elif key == 546:  # Ctrl+Left on some terminals
            self._word_left()
        elif key == 561:  # Ctrl+Right on some terminals
            self._word_right()

    def _handle_ctrl(self, ch: str):
        """Handle Ctrl+key combinations."""
        if ch == 's':
            # Save request
            self.net.send({"type": "save_request"})
        elif ch == 'f':
            self._start_search()
        elif ch == 'h':
            self._start_replace()
        elif ch == 'l':
            self._toggle_lock()
        elif ch == 'z':
            self._undo()
        elif ch == 'b':
            self._word_left()
        elif ch == 'f':
            # Actually Ctrl+F is search; Ctrl+Right for word-right
            # Word right is... let me use another binding
            pass
        elif ch == 'w':
            self._word_right()

    def _handle_modal_input(self, ch):
        """Handle input when in search/replace mode."""
        if isinstance(ch, str) and len(ch) == 1:
            if ord(ch) == 27:  # Escape
                self._cancel_modal()
                return
            elif ord(ch) == 10 or ord(ch) == 13:  # Enter
                self._confirm_modal()
                return
            elif ord(ch) == 127 or ord(ch) == 8:  # Backspace
                self.modal_input = self.modal_input[:-1]
            elif ord(ch) >= 32:
                self.modal_input += ch

            if self.search_mode:
                self._update_search()
            elif self.replace_mode and not self.search_query:
                self.search_query = self.modal_input
                self._update_search()
        elif isinstance(ch, int):
            if ch == 27:  # Escape
                self._cancel_modal()
            elif ch == curses.KEY_BACKSPACE or ch == 127:
                self.modal_input = self.modal_input[:-1]
                if self.search_mode:
                    self._update_search()
            elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
                self._confirm_modal()

    # ── Cursor movement ─────────────────────────────────────────────────────

    def _move_cursor(self, delta: int):
        """Move cursor by delta positions. Clamp to document bounds."""
        new_pos = self.cursor_pos + delta
        doc_len = len(self.doc.get_local_doc())
        if 0 <= new_pos <= doc_len:
            self.cursor_pos = new_pos
        elif new_pos < 0:
            self.cursor_pos = 0
        else:
            self.cursor_pos = doc_len
        self._send_cursor()

    def _move_cursor_vertical(self, direction: int):
        """Move cursor up (-1) or down (+1), keeping column."""
        line, col = self.doc.cursor_pos_to_line_col(self.cursor_pos)
        new_line = line + direction
        if new_line < 0:
            self.cursor_pos = 0
        else:
            self.cursor_pos = self.doc.line_col_to_pos(new_line, col)
        self._send_cursor()

    def _cursor_home(self):
        """Move to start of current line."""
        line, _ = self.doc.cursor_pos_to_line_col(self.cursor_pos)
        self.cursor_pos = self.doc.line_col_to_pos(line, 0)
        self._send_cursor()

    def _cursor_end(self):
        """Move to end of current line."""
        doc = self.doc.get_local_doc()
        line, _ = self.doc.cursor_pos_to_line_col(self.cursor_pos)
        lines = doc.split("\n")
        if line < len(lines):
            self.cursor_pos = self.doc.line_col_to_pos(line, len(lines[line]))
        self._send_cursor()

    def _page_up(self):
        """Move up by one page."""
        page_lines = max(1, self.rows - 3)
        for _ in range(page_lines):
            self._move_cursor_vertical(-1)

    def _page_down(self):
        """Move down by one page."""
        page_lines = max(1, self.rows - 3)
        for _ in range(page_lines):
            self._move_cursor_vertical(1)

    def _word_left(self):
        """Move cursor to start of current/previous word."""
        doc = self.doc.get_local_doc()
        pos = self.cursor_pos
        # Skip whitespace left
        while pos > 0 and doc[pos - 1].isspace():
            pos -= 1
        # Skip word characters left
        while pos > 0 and not doc[pos - 1].isspace():
            pos -= 1
        self.cursor_pos = pos
        self._send_cursor()

    def _word_right(self):
        """Move cursor to start of next word."""
        doc = self.doc.get_local_doc()
        pos = self.cursor_pos
        # Skip current word
        while pos < len(doc) and not doc[pos].isspace():
            pos += 1
        # Skip whitespace
        while pos < len(doc) and doc[pos].isspace():
            pos += 1
        self.cursor_pos = pos
        self._send_cursor()

    # ── Editing operations ──────────────────────────────────────────────────

    def _handle_backspace(self):
        """Delete character before cursor."""
        if self._is_locked_for_us():
            curses.beep()
            return
        if self.cursor_pos <= 0:
            return
        doc = self.doc.get_local_doc()
        char = doc[self.cursor_pos - 1]
        op_msg = self.doc.delete(self.cursor_pos - 1, char)
        self.net.send(op_msg)
        self.cursor_pos -= 1
        self._send_cursor()

    def _handle_delete(self):
        """Delete character at cursor."""
        if self._is_locked_for_us():
            curses.beep()
            return
        doc = self.doc.get_local_doc()
        if self.cursor_pos >= len(doc):
            return
        char = doc[self.cursor_pos]
        op_msg = self.doc.delete(self.cursor_pos, char)
        self.net.send(op_msg)
        self._send_cursor()

    def _handle_enter(self):
        """Insert newline."""
        if self._is_locked_for_us():
            curses.beep()
            return
        op_msg = self.doc.insert(self.cursor_pos, "\n")
        self.net.send(op_msg)
        self.cursor_pos += 1
        self._send_cursor()

    def _undo(self):
        """Send undo request."""
        if self._is_locked_for_us():
            curses.beep()
            return
        self.net.send({"type": "undo_request", "user": self.user_name})

    def _toggle_lock(self):
        """Request or release edit lock."""
        if self.lock_holder == self.user_name:
            self.net.send({"type": "lock_release", "user": self.user_name})
        else:
            self.net.send({"type": "lock_request", "user": self.user_name})

    def _is_locked_for_us(self) -> bool:
        """Check if document is locked by someone else."""
        return (self.lock_holder is not None and
                self.lock_holder != self.user_name)

    # ── Search ──────────────────────────────────────────────────────────────

    def _start_search(self):
        """Enter search mode."""
        self.search_mode = True
        self.search_query = ""
        self.modal_input = ""
        self.search_matches = []
        self.search_current = -1
        self.modal_prompt = "Search: "

    def _start_replace(self):
        """Enter replace mode."""
        self.replace_mode = True
        self.search_query = ""
        self.replace_text = ""
        self.modal_input = ""
        self.search_matches = []
        self.search_current = -1
        self.modal_prompt = "Find: "

    def _cancel_modal(self):
        """Exit search/replace mode."""
        self.search_mode = False
        self.replace_mode = False
        self.search_query = ""
        self.replace_text = ""
        self.modal_input = ""
        self.search_matches = []
        self.search_current = -1

    def _confirm_modal(self):
        """Confirm search or replace input."""
        if self.search_mode:
            self._cycle_search(forward=True)
        elif self.replace_mode:
            if not self.search_query:
                self.search_query = self.modal_input
                self.modal_input = ""
                self.modal_prompt = "Replace with: "
                self._update_search()
            elif not self.replace_text:
                self.replace_text = self.modal_input
                if self.search_current >= 0:
                    self._do_replace()
                self.modal_prompt = "Replace? (y/n): "
                self.modal_input = ""
            else:
                # Check confirmation
                if self.modal_input.lower() == 'y':
                    self._do_replace()
                self._cycle_search(forward=True)
                self.modal_prompt = "Replace? (y/n): "
                self.modal_input = ""

    def _update_search(self):
        """Update search matches based on current query."""
        query = self.modal_input if self.search_mode or not self.search_query else self.search_query
        if self.replace_mode and self.search_query and not self.replace_text:
            query = self.modal_input  # we're typing replace text
        if not query:
            self.search_matches = []
            self.search_current = -1
            return

        doc = self.doc.get_local_doc()
        self.search_matches = []
        start = 0
        while True:
            idx = doc.find(query, start)
            if idx == -1:
                break
            self.search_matches.append(idx)
            start = idx + 1

        if self.search_matches and self.search_current < 0:
            self.search_current = 0
            # Move cursor to first match
            self.cursor_pos = self.search_matches[0]

    def _cycle_search(self, forward: bool = True):
        """Cycle through search matches."""
        if not self.search_matches:
            return
        if forward:
            self.search_current = (self.search_current + 1) % len(self.search_matches)
        else:
            self.search_current = (self.search_current - 1) % len(self.search_matches)
        self.cursor_pos = self.search_matches[self.search_current]
        self._send_cursor()

    def _do_replace(self):
        """Replace current match with replacement text."""
        if self.search_current < 0 or not self.search_matches:
            return
        pos = self.search_matches[self.search_current]
        old_text = self.search_query.replace("\n", "")  # should be single line

        # Delete old text
        op_msg = self.doc.delete(pos, old_text)
        self.net.send(op_msg)
        # Insert new text
        op_msg = self.doc.insert(pos, self.replace_text)
        self.net.send(op_msg)

        # Adjust cursor
        self.cursor_pos = pos + len(self.replace_text)
        self._send_cursor()

        # Recompute matches
        self._update_search()

    # ── Network helper ─────────────────────────────────────────────────────

    def _send_cursor(self):
        """Send cursor update to server."""
        msg = {
            "type": "cursor_update",
            "user": self.user_name,
            "pos": self.cursor_pos,
        }
        self.net.send(msg)

    # ── Rendering ───────────────────────────────────────────────────────────

    def _render(self):
        """Render the entire UI."""
        self.stdscr.erase()
        self.rows, self.cols = self.stdscr.getmaxyx()

        if self.rows < 5 or self.cols < 20:
            self.stdscr.addstr(0, 0, "Terminal too small")
            self.stdscr.refresh()
            return

        # Layout:
        # - Left: document area (cols - sidebar_width)
        # - Right: sidebar (sidebar_width)
        # - Bottom: status bar (1 line)

        doc_width = self.cols - self.sidebar_width
        doc_height = self.rows - 1  # minus status bar

        self._render_document(doc_width, doc_height)
        self._render_sidebar(doc_width, doc_height)
        self._render_status_bar()
        self._render_modal()

        self.stdscr.refresh()

    def _render_document(self, width: int, height: int):
        """Render the document content with line numbers."""
        doc = self.doc.get_local_doc()
        lines = doc.split("\n")
        total_lines = len(lines)

        # Compute visible line range
        cursor_line, cursor_col = self.doc.cursor_pos_to_line_col(self.cursor_pos)

        # Adjust scroll to keep cursor visible
        self._adjust_scroll(cursor_line, cursor_col, width, height)

        # Render each visible line
        for screen_row in range(height):
            doc_line_idx = self.scroll_top + screen_row
            if doc_line_idx >= total_lines:
                break

            line_text = lines[doc_line_idx]

            # Line number
            ln_str = f"{doc_line_idx + 1:>{self.line_num_width - 1}} "
            try:
                self.stdscr.addstr(screen_row, 0, ln_str,
                                   curses.color_pair(PAIR_LINE_NUM) | curses.A_DIM)
            except curses.error:
                pass

            # Visible portion of the line
            text_x = self.line_num_width
            available_width = width - text_x

            if self.scroll_left < len(line_text):
                visible_text = line_text[self.scroll_left:self.scroll_left + available_width]
            else:
                visible_text = ""

            # Render with syntax highlighting if it's a .py file
            if self.room_name.endswith(".py"):
                self._render_highlighted_line(
                    screen_row, text_x, line_text, visible_text,
                    doc_line_idx, available_width
                )
            else:
                try:
                    self.stdscr.addstr(screen_row, text_x, visible_text)
                except curses.error:
                    pass

        # Render remote cursors
        self._render_remote_cursors(width, height, lines)

        # Render local cursor
        self._render_local_cursor(cursor_line, cursor_col, width, height, lines)

    def _render_highlighted_line(self, screen_row: int, text_x: int,
                                  full_line: str, visible_text: str,
                                  doc_line_idx: int, available_width: int):
        """Render a line with Python syntax highlighting."""
        try:
            segments = syn.highlight_line(full_line)
        except Exception:
            segments = [(full_line, syn.COLOR_DEFAULT)]

        col = text_x
        scroll_end = self.scroll_left + available_width

        for seg_text, color_idx in segments:
            # Determine visible part of this segment
            seg_start_in_line = sum(len(s[0]) for s in segments[:segments.index((seg_text, color_idx))])
            # Simpler: track cumulative position
            pass

        # Actually render segment by segment
        pos_in_line = 0
        for seg_text, color_idx in segments:
            seg_len = len(seg_text)
            # Check if segment overlaps visible region
            seg_end = pos_in_line + seg_len
            if seg_end <= self.scroll_left:
                pos_in_line = seg_end
                continue
            if pos_in_line >= scroll_end:
                break

            # Clip to visible region
            start_clip = max(0, self.scroll_left - pos_in_line)
            end_clip = min(seg_len, scroll_end - pos_in_line)
            visible_part = seg_text[start_clip:end_clip]

            if visible_part:
                screen_x = text_x + max(0, pos_in_line - self.scroll_left)
                try:
                    attr = curses.color_pair(color_idx)
                    self.stdscr.addstr(screen_row, screen_x, visible_part, attr)
                except curses.error:
                    pass

            pos_in_line = seg_end

    def _render_remote_cursors(self, width: int, height: int, lines: list):
        """Draw remote user cursor markers."""
        for user, info in self.remote_users.items():
            pos = info.get("cursor_pos", 0)
            color = info.get("color", 1)
            if pos < 0:
                continue

            rline, rcol = self.doc.cursor_pos_to_line_col(pos)

            # Check if this line is visible
            screen_row = rline - self.scroll_top
            if 0 <= screen_row < height:
                screen_col = self.line_num_width + rcol - self.scroll_left
                if self.line_num_width <= screen_col < width:
                    try:
                        pair_idx = PAIR_USER_COLORS_START + color - 1
                        attr = curses.color_pair(pair_idx) | curses.A_BOLD
                        self.stdscr.addstr(screen_row, screen_col, " ", attr)
                    except curses.error:
                        pass

                # Show username above cursor on previous line
                if screen_row > 0:
                    label_col = screen_col - len(user) // 2
                    label_col = max(self.line_num_width, min(label_col, width - len(user) - 1))
                    try:
                        attr = curses.color_pair(PAIR_USER_COLORS_START + color - 1) | curses.A_BOLD
                        self.stdscr.addstr(screen_row - 1, label_col, user, attr)
                    except curses.error:
                        pass

    def _render_local_cursor(self, cursor_line: int, cursor_col: int,
                              width: int, height: int, lines: list):
        """Draw the local cursor."""
        screen_row = cursor_line - self.scroll_top
        screen_col = self.line_num_width + cursor_col - self.scroll_left

        if 0 <= screen_row < height and self.line_num_width <= screen_col < width:
            # Blink
            now = time.time()
            if now - self.last_blink > 0.5:
                self.cursor_visible = not self.cursor_visible
                self.last_blink = now

            if self.cursor_visible:
                try:
                    # Get character under cursor
                    line_text = lines[cursor_line] if cursor_line < len(lines) else ""
                    if cursor_col < len(line_text):
                        ch = line_text[cursor_col]
                    else:
                        ch = " "
                    attr = curses.A_REVERSE
                    self.stdscr.addstr(screen_row, screen_col, ch, attr)
                except curses.error:
                    pass

    def _render_sidebar(self, doc_width: int, height: int):
        """Render the sidebar with connected users."""
        x = doc_width
        w = self.sidebar_width

        # Draw vertical separator
        for row in range(height):
            try:
                self.stdscr.addstr(row, x, "│", curses.color_pair(PAIR_SIDEBAR))
            except curses.error:
                pass

        # Title
        try:
            self.stdscr.addstr(0, x + 1, " USERS ", curses.color_pair(PAIR_SIDEBAR) | curses.A_BOLD)
        except curses.error:
            pass

        # List users
        row = 2
        # Local user first
        lock_mark = " 🔒" if self.lock_holder == self.user_name else ""
        try:
            entry = f" ● {self.user_name}{lock_mark}"
            attr = curses.color_pair(PAIR_USER_COLORS_START + self.user_color - 1)
            self.stdscr.addstr(row, x + 1, entry[:w-2], attr)
        except curses.error:
            pass
        row += 1

        for user, info in self.remote_users.items():
            if row >= height - 1:
                break
            color = info.get("color", 1)
            pos = info.get("cursor_pos", 0)
            rline, _ = self.doc.cursor_pos_to_line_col(pos)
            lock_mark = " 🔒" if self.lock_holder == user else ""
            entry = f"   {user}{lock_mark} L:{rline+1}"
            try:
                attr = curses.color_pair(PAIR_USER_COLORS_START + color - 1)
                self.stdscr.addstr(row, x + 1, entry[:w-2], attr)
            except curses.error:
                pass
            row += 1

        # Lock queue
        if self.lock_queue:
            row += 1
            try:
                self.stdscr.addstr(row, x + 1, " Lock queue:", curses.A_BOLD)
            except curses.error:
                pass
            row += 1
            for q_user in self.lock_queue[:5]:
                if row >= height - 1:
                    break
                try:
                    self.stdscr.addstr(row, x + 1, f"   {q_user}"[:w-2])
                except curses.error:
                    pass
                row += 1

    def _render_status_bar(self):
        """Render the bottom status bar."""
        y = self.rows - 1
        cursor_line, cursor_col = self.doc.cursor_pos_to_line_col(self.cursor_pos)
        total_lines = len(self.doc.get_local_doc().split("\n"))

        # Build status components
        file_part = f" {self.room_name} "
        users_part = f" {len(self.remote_users) + 1} users "
        conn_part = " CONNECTED " if self.connected else " RECONNECTING "
        pos_part = f" Ln {cursor_line + 1}/{total_lines} Col {cursor_col + 1} "
        lock_part = ""
        if self.lock_holder:
            lock_part = f" LOCKED by {self.lock_holder} "

        # Fill with spaces
        status = ""
        status += file_part
        status += lock_part if lock_part else ""
        # Right-align position
        right_part = users_part + conn_part + pos_part
        padding = self.cols - len(status) - len(right_part)
        if padding > 0:
            status += " " * padding
        status += right_part

        try:
            self.stdscr.addstr(y, 0, status[:self.cols],
                               curses.color_pair(PAIR_STATUS) | curses.A_BOLD)
        except curses.error:
            pass

    def _render_modal(self):
        """Render search/replace overlay bar."""
        if not self.search_mode and not self.replace_mode:
            return

        y = self.rows - 2
        width = min(60, self.cols - 4)
        x = (self.cols - width) // 2

        # Background
        for i in range(width):
            try:
                self.stdscr.addstr(y, x + i, " ", curses.A_REVERSE)
            except curses.error:
                pass

        # Prompt and input
        display = self.modal_prompt + self.modal_input
        if self.search_mode:
            match_info = ""
            if self.search_matches:
                match_info = f" [{self.search_current + 1}/{len(self.search_matches)}]"
            display += match_info

        display = display[:width - 2]
        try:
            self.stdscr.addstr(y, x + 1, display, curses.A_REVERSE)
        except curses.error:
            pass

        # Show cursor position
        cursor_x = x + 1 + len(self.modal_prompt) + len(self.modal_input)
        try:
            self.stdscr.addstr(y, min(cursor_x, x + width - 2), " ", curses.A_REVERSE | curses.A_BLINK)
        except curses.error:
            pass

    def _adjust_scroll(self, cursor_line: int, cursor_col: int,
                       width: int, height: int):
        """Adjust scroll_top and scroll_left to keep cursor visible."""
        text_width = width - self.line_num_width

        # Vertical
        if cursor_line < self.scroll_top:
            self.scroll_top = cursor_line
        elif cursor_line >= self.scroll_top + height:
            self.scroll_top = cursor_line - height + 1

        if self.scroll_top < 0:
            self.scroll_top = 0

        # Horizontal
        if cursor_col < self.scroll_left:
            self.scroll_left = cursor_col
        elif cursor_col >= self.scroll_left + text_width:
            self.scroll_left = cursor_col - text_width + 1

        if self.scroll_left < 0:
            self.scroll_left = 0
