"""
Curses TUI: rendering, input handling, sub-windows.
"""

import curses
import time
from collaborative_text_editor.client.syntax import highlight_line, is_python_file, TOKEN_KEYWORD, TOKEN_STRING, TOKEN_COMMENT, TOKEN_NUMBER


# Color pair definitions
COL_NORMAL = 0
COL_KEYWORD = 1
COL_STRING = 2
COL_COMMENT = 3
COL_NUMBER = 4
COL_STATUS = 5
COL_SIDEBAR = 6
COL_HIGHLIGHT = 7
COL_USER_CURSOR_BASE = 10  # Base for per-user cursor colors (10, 11, 12, ...)
MAX_USER_COLORS = 8

# User display colors (cycle through these)
USER_COLORS = [
    curses.COLOR_CYAN,
    curses.COLOR_GREEN,
    curses.COLOR_MAGENTA,
    curses.COLOR_YELLOW,
    curses.COLOR_RED,
    curses.COLOR_BLUE,
    curses.COLOR_WHITE,
]


class TUI:
    """Curses-based TUI for the collaborative text editor."""

    def __init__(self, stdscr, editor, username, room_name, filename=""):
        self.stdscr = stdscr
        self.editor = editor
        self.username = username
        self.room_name = room_name
        self.filename = filename
        self.running = True

        # Viewport scroll
        self.scroll_row = 0
        self.scroll_col = 0

        # Sidebar width
        self.sidebar_width = 22

        # Status message (for transient messages)
        self.status_message = ""
        self.status_message_time = 0

        # User colors
        self.user_colors = {}  # username -> color_pair_number
        self._next_color = 0

        # Lock state
        self.lock_owner = None

        # Connection status
        self.connected = True
        self.user_list = []

        # Search mode
        self.search_mode = False
        self.search_input = ""

        # Replace mode
        self.replace_mode = False
        self.replace_stage = 0  # 0: find string, 1: replace string, 2: confirm
        self.replace_find = ""
        self.replace_with = ""

        # Input mode for overlays
        self.overlay_input = ""

        # Setup curses
        self._setup_curses()

    def _setup_curses(self):
        """Initialize curses settings."""
        curses.curs_set(1)  # Show cursor
        self.stdscr.keypad(True)
        self.stdscr.nodelay(False)

        # Use default terminal colors
        curses.use_default_colors()

        # Initialize color pairs
        if curses.has_colors():
            curses.init_pair(COL_KEYWORD, curses.COLOR_BLUE, -1)
            curses.init_pair(COL_STRING, curses.COLOR_GREEN, -1)
            curses.init_pair(COL_COMMENT, curses.COLOR_RED, -1)
            curses.init_pair(COL_NUMBER, curses.COLOR_MAGENTA, -1)
            curses.init_pair(COL_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(COL_SIDEBAR, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(COL_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_YELLOW)

            # Initialize per-user cursor colors
            for i, color in enumerate(USER_COLORS):
                curses.init_pair(COL_USER_CURSOR_BASE + i, color, -1)

        # Non-blocking input with small delay
        self.stdscr.timeout(30)

    def get_user_color(self, username):
        """Get or assign a color pair number for a user."""
        if username not in self.user_colors:
            idx = self._next_color % MAX_USER_COLORS
            self.user_colors[username] = COL_USER_CURSOR_BASE + idx
            self._next_color += 1
        return self.user_colors[username]

    def run(self):
        """Main TUI loop."""
        while self.running:
            self._render()
            self._handle_input()

    def _render(self):
        """Render the entire TUI."""
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        if max_y < 3 or max_x < 40:
            self.stdscr.addstr(0, 0, "Terminal too small")
            self.stdscr.refresh()
            return

        # Layout:
        # - main_area_width = max_x - sidebar_width - 1
        # - main_area_height = max_y - 2 (status bar) - 1 (optional search bar)
        sidebar_width = min(self.sidebar_width, max_x - 20)
        main_width = max_x - sidebar_width - 1
        main_height = max_y - 2  # status bar always

        # If in search/replace mode, reduce main_height by 1
        overlay_visible = self.search_mode or self.replace_mode
        if overlay_visible:
            main_height -= 1

        if main_height < 1:
            main_height = 1

        main_width = max(main_width, 10)

        self._draw_main_area(0, 0, main_height, main_width)
        self._draw_sidebar(0, main_width + 1, main_height, sidebar_width)
        self._draw_status_bar(max_y - 2, 0, max_x)

        if overlay_visible:
            self._draw_overlay(max_y - 1, 0, max_x)

        self.stdscr.refresh()

    def _draw_main_area(self, start_y, start_x, height, width):
        """Draw the document content with line numbers and syntax highlighting."""
        if height <= 0:
            return

        doc_lines = self.editor.get_lines()
        total_lines = len(doc_lines)

        # Ensure cursor is visible
        self._update_scroll(height, width - 6)  # -6 for line numbers

        # Determine line number width
        line_num_width = max(4, len(str(total_lines)) + 1)

        # Calculate visible range
        content_width = width - line_num_width - 1  # -1 for separator
        if content_width < 1:
            return

        for screen_row in range(height):
            doc_row = self.scroll_row + screen_row

            # Line number
            if doc_row < total_lines:
                line_num_str = str(doc_row + 1).rjust(line_num_width - 1) + " "
                try:
                    self.stdscr.addstr(start_y + screen_row, start_x,
                                       line_num_str, curses.A_DIM)
                except curses.error:
                    pass
            else:
                try:
                    self.stdscr.addstr(start_y + screen_row, start_x,
                                       " " * line_num_width, curses.A_DIM)
                except curses.error:
                    pass

            # Separator
            sep_x = start_x + line_num_width
            try:
                self.stdscr.addch(start_y + screen_row, sep_x, '│')
            except curses.error:
                pass

            # Document content
            if doc_row < total_lines:
                line = doc_lines[doc_row]
                # Handle horizontal scroll
                if self.scroll_col < len(line):
                    visible_line = line[self.scroll_col:self.scroll_col + content_width]
                else:
                    visible_line = ""

                # Syntax highlighting
                if is_python_file(self.filename):
                    tokens = highlight_line(visible_line)
                    col_offset = start_x + line_num_width + 1
                    for text, token_type in tokens:
                        color = COL_NORMAL
                        if token_type == TOKEN_KEYWORD:
                            color = COL_KEYWORD
                        elif token_type == TOKEN_STRING:
                            color = COL_STRING
                        elif token_type == TOKEN_COMMENT:
                            color = COL_COMMENT
                        elif token_type == TOKEN_NUMBER:
                            color = COL_NUMBER

                        try:
                            self.stdscr.addstr(start_y + screen_row, col_offset,
                                               text, curses.color_pair(color))
                        except curses.error:
                            pass
                        col_offset += len(text)
                else:
                    try:
                        self.stdscr.addstr(start_y + screen_row,
                                           start_x + line_num_width + 1,
                                           visible_line)
                    except curses.error:
                        pass

                # Search highlights
                search_offsets = self.editor.get_search_match_offsets()
                if search_offsets:
                    line_start_offset = sum(len(doc_lines[i]) + 1 for i in range(doc_row))
                    for match_offset in search_offsets:
                        # Check if this match is on this line
                        match_line_start = match_offset
                        # Find which line the match is on
                        ml = 0
                        mls = 0
                        for i in range(doc_row):
                            mls += len(doc_lines[i]) + 1
                        if doc_row < total_lines:
                            mle = mls + len(doc_lines[doc_row])
                            if mls <= match_offset < mle:
                                # Match is on this visible line
                                rel_pos = match_offset - mls - self.scroll_col
                                if 0 <= rel_pos < content_width:
                                    query_len = len(self.editor.search_query)
                                    if query_len > 0:
                                        try:
                                            for q in range(query_len):
                                                screen_pos = start_x + line_num_width + 1 + rel_pos + q
                                                if screen_pos < start_x + width:
                                                    self.stdscr.chgat(
                                                        start_y + screen_row,
                                                        screen_pos,
                                                        1,
                                                        curses.A_REVERSE | curses.color_pair(COL_HIGHLIGHT))
                                        except curses.error:
                                            pass

        # Draw remote user cursors on visible lines
        for remote_user, (rrow, rcol, rev) in list(self.editor.remote_cursors.items()):
            if rrow == -1:
                continue
            screen_ry = rrow - self.scroll_row
            if 0 <= screen_ry < height:
                screen_rcx = rcol - self.scroll_col
                if 0 <= screen_rcx < content_width:
                    color = self.get_user_color(remote_user)
                    try:
                        # Draw a marker at the column
                        marker_x = start_x + line_num_width + 1 + screen_rcx
                        # Draw username above if there's room
                        if screen_ry > 0:
                            name = remote_user[:content_width - 1]
                            self.stdscr.addstr(
                                start_y + screen_ry - 1,
                                marker_x,
                                name,
                                curses.color_pair(color) | curses.A_BOLD)
                        # Draw cursor indicator
                        self.stdscr.chgat(
                            start_y + screen_ry,
                            marker_x,
                            1,
                            curses.color_pair(color) | curses.A_REVERSE)
                    except curses.error:
                        pass

        # Draw our cursor
        cursor_row = self.editor.cursor_row
        cursor_col = self.editor.cursor_col
        screen_cy = cursor_row - self.scroll_row
        screen_ccx = cursor_col - self.scroll_col
        if 0 <= screen_cy < height and 0 <= screen_ccx < content_width:
            try:
                self.stdscr.move(start_y + screen_cy,
                                 start_x + line_num_width + 1 + screen_ccx)
            except curses.error:
                pass

    def _draw_sidebar(self, start_y, start_x, height, width):
        """Draw the sidebar with user list and cursor positions."""
        if width < 5:
            return

        # Vertical separator
        for i in range(height):
            try:
                self.stdscr.addch(start_y + i, start_x - 1, '│')
            except curses.error:
                pass

        # Title
        try:
            self.stdscr.addstr(start_y, start_x, " USERS", curses.A_BOLD)
        except curses.error:
            pass

        # User list
        row = start_y + 1
        users = self.editor.remote_cursors.copy()
        # Add self
        users[self.username] = (self.editor.cursor_row, self.editor.cursor_col, 0)

        # Sort by username
        for i, (uname, (urow, ucol, urev)) in enumerate(sorted(users.items())):
            if row >= start_y + height:
                break

            color = self.get_user_color(uname) if uname != self.username else COL_NORMAL
            attrs = curses.color_pair(color)
            if uname == self.username:
                attrs |= curses.A_BOLD

            # Indicator
            indicator = "▌"
            try:
                self.stdscr.addstr(row, start_x, indicator, attrs)
            except curses.error:
                pass

            # Username (truncated)
            display_name = uname[:width - 8]
            try:
                self.stdscr.addstr(row, start_x + 2, display_name, attrs)
            except curses.error:
                pass

            # Line number
            line_str = f"Ln {urow + 1}"
            try:
                ln_x = start_x + width - len(line_str) - 1
                self.stdscr.addstr(row, ln_x, line_str, attrs)
            except curses.error:
                pass

            # Lock indicator
            if uname == self.lock_owner:
                try:
                    self.stdscr.addstr(row, start_x + 2 + len(display_name) + 1, "🔒")
                except curses.error:
                    try:
                        self.stdscr.addstr(row, start_x + 2 + len(display_name) + 1, "[L]")
                    except curses.error:
                        pass

            row += 1

    def _draw_status_bar(self, y, x, width):
        """Draw the status bar."""
        if y < 0:
            return

        # Build status line
        filename = self.filename or f"room:{self.room_name}"
        user_count = len(self.user_list) if self.user_list else 1
        conn_status = "Online" if self.connected else "Disconnected"
        cursor_row = self.editor.cursor_row + 1
        cursor_col = self.editor.cursor_col + 1
        lock_info = f"LOCK: {self.lock_owner}" if self.lock_owner else ""

        # Build parts
        parts = [
            f" {filename} ",
            f" {user_count} users ",
            f" {conn_status} ",
            f" Ln {cursor_row}, Col {cursor_col} ",
        ]
        if lock_info:
            parts.append(f" {lock_info} ")

        # Show transient status message if recent
        if self.status_message and time.time() - self.status_message_time < 3:
            parts.append(f" {self.status_message} ")

        status = "│".join(parts)

        # Truncate to fit
        if len(status) > width:
            status = status[:width - 1]

        try:
            self.stdscr.addstr(y, x, status.ljust(width),
                               curses.color_pair(COL_STATUS))
        except curses.error:
            pass

    def _draw_overlay(self, y, x, width):
        """Draw the search/replace overlay bar."""
        if y < 0:
            return

        if self.search_mode:
            prompt = f"Search: {self.search_input}"
            match_info = ""
            if self.editor.search_matches:
                match_info = f" [{self.editor.search_current + 1}/{len(self.editor.search_matches)}]"
            text = prompt + match_info + " (Enter/Shift+Enter to cycle, Esc to cancel)"
        elif self.replace_mode:
            if self.replace_stage == 0:
                text = f"Find: {self.overlay_input}"
            elif self.replace_stage == 1:
                text = f"Replace with: {self.overlay_input}"
            else:
                total = len(self.editor.replace_matches)
                current = self.editor.replace_current + 1 if self.editor.replace_current >= 0 else 0
                text = f"Replace? [{current}/{total}] y=yes n=no q=quit"
        else:
            text = ""

        try:
            self.stdscr.addstr(y, x, text.ljust(width)[:width],
                               curses.A_REVERSE)
        except curses.error:
            pass

    def _update_scroll(self, height, content_width):
        """Update scroll to keep cursor visible."""
        cursor_row = self.editor.cursor_row
        cursor_col = self.editor.cursor_col

        # Vertical scroll
        if cursor_row < self.scroll_row:
            self.scroll_row = cursor_row
        elif cursor_row >= self.scroll_row + height:
            self.scroll_row = cursor_row - height + 1

        if self.scroll_row < 0:
            self.scroll_row = 0

        # Horizontal scroll
        if cursor_col < self.scroll_col:
            self.scroll_col = cursor_col
        elif cursor_col >= self.scroll_col + content_width:
            self.scroll_col = cursor_col - content_width + 1

        if self.scroll_col < 0:
            self.scroll_col = 0

    # ---- Input handling ----

    def _handle_input(self):
        """Handle keyboard input. Returns action to send to network layer."""
        try:
            key = self.stdscr.getch()
        except Exception:
            return None

        if key == -1:
            return None

        action = None

        # If in search mode
        if self.search_mode:
            action = self._handle_search_input(key)
            if action:
                return action
            return None

        # If in replace mode
        if self.replace_mode:
            action = self._handle_replace_input(key)
            if action:
                return action
            return None

        # Check if we can edit (lock check)
        can_edit = (self.lock_owner is None or self.lock_owner == self.username)

        # Normal mode input
        if key == curses.KEY_UP:
            self.editor.move_cursor_relative(-1, 0)
        elif key == curses.KEY_DOWN:
            self.editor.move_cursor_relative(1, 0)
        elif key == curses.KEY_LEFT:
            self.editor.move_cursor_relative(0, -1)
        elif key == curses.KEY_RIGHT:
            self.editor.move_cursor_relative(0, 1)
        elif key == curses.KEY_HOME:
            self.editor.move_to_line_start()
        elif key == curses.KEY_END:
            self.editor.move_to_line_end()
        elif key == curses.KEY_PPAGE:
            self.editor.page_up(max(1, curses.LINES - 4))
        elif key == curses.KEY_NPAGE:
            self.editor.page_down(max(1, curses.LINES - 4))
        elif key == curses.KEY_BACKSPACE or key == 127:
            if can_edit:
                action = self.editor.delete_char(backspace=True)
                if action:
                    return ("edit", [action])
        elif key == curses.KEY_DC:  # Delete key
            if can_edit:
                action = self.editor.delete_char(backspace=False)
                if action:
                    return ("edit", [action])
        elif key == 10 or key == 13:  # Enter
            if can_edit:
                action = self.editor.insert_char('\n')
                if action:
                    return ("edit", [action])
        elif key == 9:  # Tab
            if can_edit:
                action = self.editor.insert_char('\t')
                if action:
                    return ("edit", [action])
        elif key == 27:  # Escape
            self.search_mode = False
            self.replace_mode = False
            self.search_input = ""
            self.overlay_input = ""
        elif key == 6:  # Ctrl+F
            self.search_mode = True
            self.search_input = ""
            self.editor.search("")
        elif key == 8:  # Ctrl+H
            self.replace_mode = True
            self.replace_stage = 0
            self.overlay_input = ""
        elif key == 19:  # Ctrl+S
            return ("save", None)
        elif key == 12:  # Ctrl+L
            if self.lock_owner == self.username:
                return ("lock_release", None)
            else:
                return ("lock_acquire", None)
        elif key == 26:  # Ctrl+Z
            if can_edit:
                inv_op = self.editor.pop_undo_op()
                if inv_op:
                    return ("undo", inv_op)
        elif key == 544:  # Ctrl+Left (some terminals)
            self.editor.move_word_left()
        elif key == 559:  # Ctrl+Right (some terminals)
            self.editor.move_word_right()
        elif key == 546:  # Ctrl+Left alt
            self.editor.move_word_left()
        elif key == 561:  # Ctrl+Right alt
            self.editor.move_word_right()
        elif 1 <= key <= 26:  # Other Ctrl+letter combos
            # Ctrl+B = 2, Ctrl+Left might be sent as other codes
            if key == 2:  # Ctrl+B (alternative left word)
                self.editor.move_word_left()
            elif key == 6:  # Already handled Ctrl+F
                pass
            else:
                pass  # Ignore other Ctrl combos for now
        elif 32 <= key <= 126:  # Printable ASCII
            if can_edit:
                char = chr(key)
                action = self.editor.insert_char(char)
                if action:
                    return ("edit", [action])

        # Handle Ctrl+Left/Right via escape sequences
        # Some terminals send ESC [ 1 ; 5 D for Ctrl+Left etc.
        # This is hard to handle with simple getch; we rely on the above codes

        return None

    def _handle_search_input(self, key):
        """Handle search mode input."""
        if key == 27:  # Escape
            self.search_mode = False
            self.search_input = ""
            self.editor.search("")
            return None
        elif key == 10 or key == 13:  # Enter
            self.editor.search_next()
            return None
        elif key == curses.KEY_BTAB or key == 353:  # Shift+Tab or Shift+Enter
            self.editor.search_prev()
            return None
        elif key == curses.KEY_BACKSPACE or key == 127:
            self.search_input = self.search_input[:-1]
            self.editor.search(self.search_input)
        elif 32 <= key <= 126:
            self.search_input += chr(key)
            self.editor.search(self.search_input)
        return None

    def _handle_replace_input(self, key):
        """Handle replace mode input."""
        if key == 27:  # Escape
            self.replace_mode = False
            self.overlay_input = ""
            self.editor.replace_active = False
            return None

        if self.replace_stage == 0:  # Entering find string
            if key == 10 or key == 13:  # Enter
                self.replace_find = self.overlay_input
                self.replace_stage = 1
                self.overlay_input = ""
            elif key == curses.KEY_BACKSPACE or key == 127:
                self.overlay_input = self.overlay_input[:-1]
            elif 32 <= key <= 126:
                self.overlay_input += chr(key)

        elif self.replace_stage == 1:  # Entering replace string
            if key == 10 or key == 13:  # Enter
                self.replace_with = self.overlay_input
                count = self.editor.start_replace(self.replace_find, self.replace_with)
                if count == 0:
                    self.replace_mode = False
                    self.status_message = "No matches found"
                    self.status_message_time = time.time()
                else:
                    self.replace_stage = 2
            elif key == curses.KEY_BACKSPACE or key == 127:
                self.overlay_input = self.overlay_input[:-1]
            elif 32 <= key <= 126:
                self.overlay_input += chr(key)

        elif self.replace_stage == 2:  # Confirm each replacement
            if key == ord('y') or key == ord('Y'):
                ops = self.editor.replace_current()
                if ops:
                    # Send all ops as one operation
                    return ("edit", ops)
                if self.editor.replace_current < 0:
                    self.replace_mode = False
                    self.status_message = "Replace complete"
                    self.status_message_time = time.time()
            elif key == ord('n') or key == ord('N'):
                self.editor.skip_replace()
                if self.editor.replace_current < 0:
                    self.replace_mode = False
            elif key == ord('q') or key == ord('Q'):
                self.replace_mode = False
                self.editor.replace_active = False

        return None

    def set_lock_owner(self, owner):
        """Update lock owner display."""
        self.lock_owner = owner

    def set_user_list(self, users):
        """Update user list."""
        self.user_list = users

    def set_connected(self, status):
        """Update connection status."""
        self.connected = status

    def show_status(self, message):
        """Show a transient status message."""
        self.status_message = message
        self.status_message_time = time.time()

    def stop(self):
        """Stop the TUI."""
        self.running = False
