#!/usr/bin/env python3
"""
client.py - Collaborative text editor TUI client.

Usage:
    python client.py --host localhost --port 9999 --user alice --room myroom [--password pass] [--file document.py]
"""

import argparse
import curses
import json
import os
import re
import socket
import sys
import threading
import time
from collections import OrderedDict
from typing import Optional

from shared import (
    Document,
    transform,
    transform_against_list,
    make_message,
    parse_message,
    MSG_CONNECT,
    MSG_ACK,
    MSG_OPERATION,
    MSG_CURSOR_UPDATE,
    MSG_LOCK_REQUEST,
    MSG_LOCK_GRANT,
    MSG_LOCK_RELEASE,
    MSG_SAVE_REQUEST,
    MSG_SAVE_ACK,
    MSG_DISCONNECT,
    MSG_ERROR,
    MSG_DOCUMENT_SYNC,
    MSG_USER_LIST,
)


# ---------------------------------------------------------------------------
# Python syntax highlighting
# ---------------------------------------------------------------------------

PYTHON_KEYWORDS = frozenset({
    'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
    'import', 'from', 'as', 'try', 'except', 'finally', 'with',
    'yield', 'lambda', 'pass', 'break', 'continue', 'and', 'or',
    'not', 'in', 'is', 'True', 'False', 'None', 'raise', 'assert',
    'del', 'global', 'nonlocal',
    'self', 'super', '__init__', '__name__', '__main__',
})

TOK_NORMAL = 0
TOK_KEYWORD = 1
TOK_STRING = 2
TOK_COMMENT = 3
TOK_NUMBER = 4

CP_NORMAL = 1
CP_KEYWORD = 2
CP_STRING = 3
CP_COMMENT = 4
CP_NUMBER = 5
CP_STATUS = 6
CP_CURSOR_OTHER = 7
CP_SEARCH_HIGHLIGHT = 8
CP_SIDEBAR = 9
CP_USER_CURSOR_BASE = 10

USER_COLORS = [
    curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
    curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN,
    curses.COLOR_WHITE,
]


def init_colors():
    """Initialize all curses color pairs."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(CP_NORMAL, -1, -1)
    curses.init_pair(CP_KEYWORD, curses.COLOR_BLUE, -1)
    curses.init_pair(CP_STRING, curses.COLOR_GREEN, -1)
    curses.init_pair(CP_COMMENT, curses.COLOR_CYAN, -1)
    curses.init_pair(CP_NUMBER, curses.COLOR_MAGENTA, -1)
    curses.init_pair(CP_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CP_CURSOR_OTHER, curses.COLOR_YELLOW, curses.COLOR_RED)
    curses.init_pair(CP_SEARCH_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    for i, color in enumerate(USER_COLORS):
        curses.init_pair(CP_USER_CURSOR_BASE + i, color, -1)


def tokenize_line(line: str):
    """Tokenize a line into (start_col, end_col, token_type) tuples."""
    tokens = []
    col = 0
    n = len(line)

    while col < n:
        if line[col] == '#':
            tokens.append((col, n, TOK_COMMENT))
            break

        if line[col] in ('"', "'"):
            quote = line[col]
            if col + 2 < n and line[col:col+3] == quote * 3:
                end = line.find(quote * 3, col + 3)
                if end == -1:
                    end = n
                else:
                    end += 3
                tokens.append((col, end, TOK_STRING))
                col = end
                continue
            end = col + 1
            while end < n:
                if line[end] == '\\':
                    end += 2
                    continue
                if line[end] == quote:
                    end += 1
                    break
                end += 1
            tokens.append((col, end, TOK_STRING))
            col = end
            continue

        num_match = re.match(r'\b\d+\.?\d*(?:[eE][+-]?\d+)?\b', line[col:])
        if num_match:
            end = col + num_match.end()
            tokens.append((col, end, TOK_NUMBER))
            col = end
            continue

        ident_match = re.match(r'[a-zA-Z_]\w*', line[col:])
        if ident_match:
            end = col + ident_match.end()
            word = line[col:end]
            if word in PYTHON_KEYWORDS:
                tokens.append((col, end, TOK_KEYWORD))
            else:
                tokens.append((col, end, TOK_NORMAL))
            col = end
            continue

        tokens.append((col, col + 1, TOK_NORMAL))
        col += 1

    return tokens


# ---------------------------------------------------------------------------
# Network client
# ---------------------------------------------------------------------------

class NetworkClient:
    """Handles TCP communication with the server."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.connected = False
        self.recv_buffer = b""
        self.message_queue: list[dict] = []
        self.queue_lock = threading.Lock()
        self.error_message: Optional[str] = None

    def connect(self, username: str, room: str, password: str, filename: str) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(0.1)
            self.running = True
            self.connected = True
            msg = make_message(
                MSG_CONNECT,
                username=username,
                room=room,
                password=password,
                filename=filename,
            )
            self.sock.sendall(msg)
            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def send(self, msg_type: str, **kwargs):
        if not self.sock or not self.connected:
            return
        try:
            data = make_message(msg_type, **kwargs)
            self.sock.sendall(data)
        except Exception:
            self.connected = False

    def poll(self):
        if not self.sock or not self.connected:
            return
        try:
            self.sock.setblocking(False)
            try:
                data = self.sock.recv(65536)
            except (BlockingIOError, socket.timeout):
                return
            if not data:
                self.connected = False
                return
            self.recv_buffer += data
            while b'\n' in self.recv_buffer:
                line, self.recv_buffer = self.recv_buffer.split(b'\n', 1)
                msg = parse_message(line)
                if msg:
                    with self.queue_lock:
                        self.message_queue.append(msg)
        except Exception:
            self.connected = False

    def get_messages(self) -> list[dict]:
        with self.queue_lock:
            msgs = self.message_queue
            self.message_queue = []
            return msgs

    def disconnect(self):
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.send(MSG_DISCONNECT)
                self.sock.close()
            except Exception:
                pass
            self.sock = None


# ---------------------------------------------------------------------------
# Client state
# ---------------------------------------------------------------------------

class ClientState:
    """Holds all client-side state with proper OT handling."""

    def __init__(self, username: str, room: str, filename: str):
        self.username = username
        self.room = room
        self.filename = filename

        # Server-confirmed document
        self.server_doc = Document()
        # Our pending (optimistic) operations
        self.pending_ops: list[dict] = []
        # Local view = server_doc + pending_ops
        self.document = Document()

        self.server_version = 0

        # Cursor
        self.cursor_line = 0
        self.cursor_col = 0

        # Viewport scroll offsets
        self.scroll_row = 0
        self.scroll_col = 0

        # Other users
        self.users: dict[str, dict] = {}
        self.lock_owner: Optional[str] = None
        self.user_count = 1

        # Connection status
        self.connected = False
        self.status_message = "Connecting..."

        # Search state
        self.search_mode = False
        self.search_query = ""
        self.search_matches: list[tuple[int, int]] = []
        self.search_current = -1

        # Find & replace state
        self.replace_mode = False
        self.replace_query = ""
        self.replace_with = ""
        self.replace_step = 0

        # Lock state
        self.has_lock = False
        self.lock_pending = False

        # Screen
        self.screen_rows = 24
        self.screen_cols = 80

    def rebuild_local_doc(self):
        """Rebuild local document from server_doc + pending_ops."""
        self.document = self.server_doc.clone()
        for op in self.pending_ops:
            self.document.apply_op(op)

    def apply_local_op(self, op: dict):
        """Apply operation locally (optimistic)."""
        self.document.apply_op(op)
        self.pending_ops.append(op)

    def handle_server_op(self, msg: dict):
        """
        Handle an operation message from the server.
        Updates server_doc, adjusts pending ops, rebuilds local doc.
        """
        op = {
            'op_type': msg['op_type'],
            'flat_pos': msg['flat_pos'],
        }
        if op['op_type'] == 'insert':
            op['char'] = msg.get('char', '')

        client_id = msg.get('client_id', '')
        is_mine = (client_id == self.username)
        is_undo = msg.get('undo', False)

        # Apply to server document
        self.server_doc.apply_op(op)

        if is_mine and not is_undo:
            # Remove matching pending op (only for non-undo operations)
            self._remove_pending(op)
        else:
            # Transform pending ops against this server op
            new_pending = []
            for pop in self.pending_ops:
                transformed = transform(pop, op)
                if transformed is not None:
                    new_pending.append(transformed)
            self.pending_ops = new_pending

        # Rebuild local document
        self.rebuild_local_doc()
        self.server_version = msg.get('version', self.server_version)

    def _remove_pending(self, server_op: dict):
        """Remove the matching pending operation."""
        for i, pop in enumerate(self.pending_ops):
            if (pop['op_type'] == server_op['op_type'] and
                pop.get('char') == server_op.get('char')):
                # Check if positions are close
                if abs(pop['flat_pos'] - server_op['flat_pos']) <= 2:
                    del self.pending_ops[i]
                    return
        # Fallback: remove first matching by type
        for i, pop in enumerate(self.pending_ops):
            if pop['op_type'] == server_op['op_type']:
                del self.pending_ops[i]
                return


# ---------------------------------------------------------------------------
# Curses UI
# ---------------------------------------------------------------------------

class EditorUI:
    """Curses-based TUI."""

    def __init__(self, stdscr, state: ClientState, network: NetworkClient):
        self.stdscr = stdscr
        self.state = state
        self.network = network
        self.running = True

        curses.curs_set(1)
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        init_colors()

        self.SIDEBAR_WIDTH = 20
        # Track escape sequence parsing
        self.esc_buf = []

    def run(self):
        while self.running:
            self._update_screen_size()
            self._process_network()
            self._handle_input()
            self._render()
            time.sleep(0.02)

    def _update_screen_size(self):
        rows, cols = self.stdscr.getmaxyx()
        self.state.screen_rows = rows
        self.state.screen_cols = cols

    def _process_network(self):
        self.network.poll()
        msgs = self.network.get_messages()
        for msg in msgs:
            self._handle_message(msg)

    def _handle_message(self, msg: dict):
        msg_type = msg.get('type')
        state = self.state

        if msg_type == MSG_ACK:
            doc_text = msg.get('document', '')
            state.server_doc = Document(doc_text)
            state.rebuild_local_doc()
            state.server_version = msg.get('version', 0)
            state.connected = True
            state.status_message = "Connected"
            state.lock_owner = msg.get('lock_owner')
            state.pending_ops.clear()

        elif msg_type == MSG_OPERATION:
            state.handle_server_op(msg)

        elif msg_type == MSG_CURSOR_UPDATE:
            uname = msg.get('username', '')
            if uname != state.username:
                state.users[uname] = {
                    'line': msg.get('line', 0),
                    'col': msg.get('col', 0),
                }

        elif msg_type == MSG_USER_LIST:
            users_list = msg.get('users', [])
            state.lock_owner = msg.get('lock_owner')
            new_users = {}
            for u in users_list:
                uname = u['username']
                if uname != state.username:
                    new_users[uname] = {
                        'line': u.get('cursor_line', 0),
                        'col': u.get('cursor_col', 0),
                    }
            state.users = new_users
            state.user_count = len(users_list)

        elif msg_type == MSG_LOCK_GRANT:
            if msg.get('username') == state.username:
                state.has_lock = True
                state.lock_pending = False
                state.status_message = "Lock acquired!"
            state.lock_owner = msg.get('username')

        elif msg_type == MSG_LOCK_RELEASE:
            state.lock_owner = None
            if msg.get('username') == state.username:
                state.has_lock = False
                state.status_message = "Lock released."

        elif msg_type == MSG_SAVE_ACK:
            state.status_message = "Document saved on server."

        elif msg_type == MSG_ERROR:
            state.status_message = f"Error: {msg.get('message', 'Unknown')}"
            # Revert optimistic changes on error
            state.pending_ops.clear()
            state.rebuild_local_doc()

        elif msg_type == MSG_DISCONNECT:
            uname = msg.get('username', '')
            state.users.pop(uname, None)

    def _handle_input(self):
        try:
            ch = self.stdscr.getch()
        except Exception:
            return
        if ch == -1:
            return

        state = self.state

        # Handle escape sequences (for Ctrl+Arrow keys etc.)
        if ch == 27:  # ESC
            self._try_escape_sequence()
            return

        if state.search_mode:
            self._handle_search_input(ch)
            return

        if state.replace_mode:
            self._handle_replace_input(ch)
            return

        ctrl = ch & 0x1f

        if ch == curses.KEY_RESIZE:
            return

        elif ch == curses.KEY_UP:
            self._move_cursor(-1, 0)
        elif ch == curses.KEY_DOWN:
            self._move_cursor(1, 0)
        elif ch == curses.KEY_LEFT:
            self._move_cursor(0, -1)
        elif ch == curses.KEY_RIGHT:
            self._move_cursor(0, 1)
        elif ch == curses.KEY_HOME:
            state.cursor_col = 0
        elif ch == curses.KEY_END:
            state.cursor_col = state.document.line_length(state.cursor_line)
        elif ch == curses.KEY_PPAGE:
            page_size = max(1, state.screen_rows - 4)
            self._move_cursor(-page_size, 0)
        elif ch == curses.KEY_NPAGE:
            page_size = max(1, state.screen_rows - 4)
            self._move_cursor(page_size, 0)

        # Ctrl+Left: some terminals send KEY_SLEFT or similar
        elif ch == curses.KEY_SLEFT:
            self._word_left()
        elif ch == curses.KEY_SRIGHT:
            self._word_right()

        elif ctrl == 8:  # Ctrl+H -> find & replace
            self._start_replace()

        elif ch == 12:  # Ctrl+L
            self._toggle_lock()

        elif ch == 26:  # Ctrl+Z
            self._undo()

        elif ch == 6:   # Ctrl+F
            self._start_search()

        elif ch == 19:  # Ctrl+S
            self._save()

        elif ch == 10:  # Enter
            self._insert_char('\n')

        elif ch in (curses.KEY_BACKSPACE, 127):  # Backspace (not Ctrl+H)
            self._backspace()

        elif ch == curses.KEY_DC:
            self._delete()

        elif 32 <= ch < 127:
            self._insert_char(chr(ch))

    def _try_escape_sequence(self):
        """Try to read an escape sequence (for Ctrl+Arrow etc.)."""
        self.stdscr.nodelay(True)
        try:
            ch = self.stdscr.getch()
            if ch == -1:
                # Plain Escape - cancel search/replace if active
                if self.state.search_mode:
                    self.state.search_mode = False
                    self.state.search_query = ""
                    self.state.search_matches = []
                    self.state.status_message = ""
                elif self.state.replace_mode:
                    self.state.replace_mode = False
                    self.state.replace_query = ""
                    self.state.replace_with = ""
                    self.state.search_matches = []
                    self.state.status_message = ""
                return

            if ch == ord('['):
                # CSI sequence: ESC [ ...
                ch2 = self.stdscr.getch()
                if ch2 == -1:
                    return

                if ch2 == ord('1'):
                    ch3 = self.stdscr.getch()
                    if ch3 == ord(';'):
                        ch4 = self.stdscr.getch()
                        if ch4 == ord('5'):
                            ch5 = self.stdscr.getch()
                            if ch5 == ord('D'):
                                self._word_left()
                            elif ch5 == ord('C'):
                                self._word_right()
                elif ch2 == ord('5'):
                    ch3 = self.stdscr.getch()
                    if ch3 == ord('D'):
                        self._word_left()
                    elif ch3 == ord('C'):
                        self._word_right()
                elif ch2 == ord('H'):  # ESC [ H  (Home)
                    self.state.cursor_col = 0
                elif ch2 == ord('F'):  # ESC [ F  (End)
                    self.state.cursor_col = self.state.document.line_length(self.state.cursor_line)
                elif ch2 == ord('5'):
                    ch3 = self.stdscr.getch()
                    if ch3 == ord('~'):
                        pass  # Page Up handled
                elif ch2 == ord('6'):
                    ch3 = self.stdscr.getch()
                    if ch3 == ord('~'):
                        pass  # Page Down handled
        except Exception:
            pass

    def _word_left(self):
        state = self.state
        line = state.document.get_line(state.cursor_line)
        col = state.cursor_col
        while col > 0 and line[col - 1].isspace():
            col -= 1
        while col > 0 and not line[col - 1].isspace():
            col -= 1
        state.cursor_col = col

    def _word_right(self):
        state = self.state
        line = state.document.get_line(state.cursor_line)
        col = state.cursor_col
        while col < len(line) and not line[col].isspace():
            col += 1
        while col < len(line) and line[col].isspace():
            col += 1
        state.cursor_col = col

    def _move_cursor(self, dline: int, dcol: int):
        state = self.state
        doc = state.document

        new_line = state.cursor_line + dline
        new_line = max(0, min(new_line, doc.get_line_count() - 1))
        if dline != 0:
            new_col = state.cursor_col
            new_col = max(0, min(new_col, doc.line_length(new_line)))
        else:
            new_col = state.cursor_col + dcol
            new_col = max(0, min(new_col, doc.line_length(new_line)))

        state.cursor_line = new_line
        state.cursor_col = new_col

    def _insert_char(self, char: str):
        state = self.state
        doc = state.document

        flat_pos = doc.line_col_to_flat_pos(state.cursor_line, state.cursor_col)

        op = {
            'op_type': 'insert',
            'flat_pos': flat_pos,
            'char': char,
        }

        state.apply_local_op(op)

        if char == '\n':
            state.cursor_line += 1
            state.cursor_col = 0
        else:
            state.cursor_col += 1

        self.network.send(
            MSG_OPERATION,
            op_type='insert',
            flat_pos=flat_pos,
            char=char,
            version=state.server_version,
            client_id=state.username,
        )

    def _backspace(self):
        state = self.state
        doc = state.document

        if state.cursor_line == 0 and state.cursor_col == 0:
            return

        if state.cursor_col > 0:
            delete_line = state.cursor_line
            delete_col = state.cursor_col - 1
        else:
            delete_line = state.cursor_line - 1
            delete_col = doc.line_length(delete_line)

        flat_pos = doc.line_col_to_flat_pos(delete_line, delete_col)

        op = {'op_type': 'delete', 'flat_pos': flat_pos}
        state.apply_local_op(op)

        if state.cursor_col > 0:
            state.cursor_col -= 1
        else:
            state.cursor_line -= 1
            state.cursor_col = doc.line_length(state.cursor_line)

        self.network.send(
            MSG_OPERATION,
            op_type='delete',
            flat_pos=flat_pos,
            version=state.server_version,
            client_id=state.username,
        )

    def _delete(self):
        state = self.state
        doc = state.document

        line = state.cursor_line
        if line >= doc.get_line_count():
            return
        col = state.cursor_col
        if col >= doc.line_length(line) and line + 1 >= doc.get_line_count():
            return

        flat_pos = doc.line_col_to_flat_pos(line, col)

        op = {'op_type': 'delete', 'flat_pos': flat_pos}
        state.apply_local_op(op)

        self.network.send(
            MSG_OPERATION,
            op_type='delete',
            flat_pos=flat_pos,
            version=state.server_version,
            client_id=state.username,
        )

    def _save(self):
        self.network.send(MSG_SAVE_REQUEST)
        self.state.status_message = "Save requested..."

    def _undo(self):
        self.network.send(
            MSG_OPERATION,
            undo=True,
            version=self.state.server_version,
            client_id=self.state.username,
        )
        self.state.status_message = "Undo requested..."

    def _toggle_lock(self):
        state = self.state
        if state.has_lock:
            self.network.send(MSG_LOCK_RELEASE)
            state.has_lock = False
            state.status_message = "Lock released."
        else:
            self.network.send(MSG_LOCK_REQUEST)
            state.lock_pending = True
            state.status_message = "Lock requested..."

    def _start_search(self):
        state = self.state
        state.search_mode = True
        state.search_query = ""
        state.search_matches = []
        state.search_current = -1
        state.status_message = "Search: "

    def _handle_search_input(self, ch: int):
        state = self.state

        if ch == 10:  # Enter
            self._search_next(1)
            return

        if ch in (curses.KEY_BTAB, 353):  # Shift+Tab/Enter
            self._search_next(-1)
            return

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if state.search_query:
                state.search_query = state.search_query[:-1]
                self._update_search_matches()
            state.status_message = f"Search: {state.search_query}"
            return

        if 32 <= ch < 127:
            state.search_query += chr(ch)
            self._update_search_matches()
            state.status_message = f"Search: {state.search_query}"
            return

    def _update_search_matches(self):
        state = self.state
        state.search_matches = []
        state.search_current = -1
        if not state.search_query:
            return

        query = state.search_query.lower()
        for line_idx in range(state.document.get_line_count()):
            line = state.document.get_line(line_idx).lower()
            col = 0
            while True:
                col = line.find(query, col)
                if col == -1:
                    break
                state.search_matches.append((line_idx, col))
                col += 1

        if state.search_matches:
            state.search_current = 0
            self._goto_match(0)

    def _search_next(self, direction: int):
        state = self.state
        if not state.search_matches:
            return
        state.search_current += direction
        if state.search_current >= len(state.search_matches):
            state.search_current = 0
        elif state.search_current < 0:
            state.search_current = len(state.search_matches) - 1
        self._goto_match(state.search_current)

    def _goto_match(self, idx: int):
        state = self.state
        if 0 <= idx < len(state.search_matches):
            line, col = state.search_matches[idx]
            state.cursor_line = line
            state.cursor_col = col

    def _start_replace(self):
        state = self.state
        state.replace_mode = True
        state.replace_step = 0
        state.replace_query = ""
        state.replace_with = ""
        state.search_matches = []
        state.search_current = -1
        state.status_message = "Find: "

    def _handle_replace_input(self, ch: int):
        state = self.state

        if state.replace_step == 0:
            if ch == 10:
                if state.replace_query:
                    state.replace_step = 1
                    state.status_message = "Replace with: "
                return
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if state.replace_query:
                    state.replace_query = state.replace_query[:-1]
                state.status_message = f"Find: {state.replace_query}"
                return
            if 32 <= ch < 127:
                state.replace_query += chr(ch)
                state.status_message = f"Find: {state.replace_query}"
                return

        elif state.replace_step == 1:
            if ch == 10:
                state.replace_step = 2
                self._update_search_matches()
                if state.search_matches:
                    self._goto_match(0)
                    state.status_message = "Replace? (y/n/q): "
                else:
                    state.status_message = "No matches."
                    state.replace_mode = False
                return
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if state.replace_with:
                    state.replace_with = state.replace_with[:-1]
                state.status_message = f"Replace with: {state.replace_with}"
                return
            if 32 <= ch < 127:
                state.replace_with += chr(ch)
                state.status_message = f"Replace with: {state.replace_with}"
                return

        elif state.replace_step == 2:
            if ch in (ord('y'), ord('Y')):
                self._do_replace_current()
                self._update_search_matches()
                if state.search_current < len(state.search_matches) and state.search_current >= 0:
                    self._goto_match(state.search_current)
                    state.status_message = "Replace? (y/n/q): "
                else:
                    state.status_message = "Replace complete."
                    state.replace_mode = False
                return
            elif ch in (ord('n'), ord('N')):
                state.search_current += 1
                if state.search_current < len(state.search_matches):
                    self._goto_match(state.search_current)
                    state.status_message = "Replace? (y/n/q): "
                else:
                    state.status_message = "Replace complete."
                    state.replace_mode = False
                return
            elif ch in (ord('q'), ord('Q')):
                state.status_message = "Replace stopped."
                state.replace_mode = False
                return

    def _do_replace_current(self):
        state = self.state
        if not state.replace_query or state.search_current < 0:
            return
        if state.search_current >= len(state.search_matches):
            return

        line_idx, col = state.search_matches[state.search_current]
        query_len = len(state.replace_query)

        # Delete matched text (right to left to preserve positions)
        for i in range(query_len - 1, -1, -1):
            flat_pos = state.document.line_col_to_flat_pos(line_idx, col + i)
            op = {'op_type': 'delete', 'flat_pos': flat_pos}
            state.apply_local_op(op)
            self.network.send(
                MSG_OPERATION, op_type='delete', flat_pos=flat_pos,
                version=state.server_version, client_id=state.username,
            )

        # Insert replacement
        for i, ch in enumerate(state.replace_with):
            flat_pos = state.document.line_col_to_flat_pos(line_idx, col + i)
            op = {'op_type': 'insert', 'flat_pos': flat_pos, 'char': ch}
            state.apply_local_op(op)
            self.network.send(
                MSG_OPERATION, op_type='insert', flat_pos=flat_pos, char=ch,
                version=state.server_version, client_id=state.username,
            )

    def _render(self):
        state = self.state
        self.stdscr.clear()
        rows, cols = state.screen_rows, state.screen_cols
        if rows < 5 or cols < 20:
            return

        sidebar_width = min(self.SIDEBAR_WIDTH, max(0, cols // 4))
        editor_width = cols - sidebar_width - 1
        editor_height = rows - 2

        self._update_scroll(editor_height, editor_width)
        self._render_editor(editor_height, editor_width)

        if sidebar_width > 0:
            self._render_sidebar(editor_height, editor_width, sidebar_width)

        self._render_status_bar(rows, cols)

        if state.search_mode or state.replace_mode:
            self._render_search_bar(rows, cols)

        self.stdscr.refresh()

    def _update_scroll(self, editor_height: int, editor_width: int):
        state = self.state

        # Vertical
        if state.cursor_line < state.scroll_row:
            state.scroll_row = state.cursor_line
        elif state.cursor_line >= state.scroll_row + editor_height:
            state.scroll_row = state.cursor_line - editor_height + 1
        state.scroll_row = max(0, min(state.scroll_row,
                                       max(0, state.document.get_line_count() - editor_height)))

        # Horizontal
        line_num_width = len(str(max(state.document.get_line_count(), 1))) + 2
        text_width = max(1, editor_width - line_num_width)
        if state.cursor_col < state.scroll_col:
            state.scroll_col = state.cursor_col
        elif state.cursor_col >= state.scroll_col + text_width:
            state.scroll_col = state.cursor_col - text_width + 1
        state.scroll_col = max(0, state.scroll_col)

    def _render_editor(self, height: int, width: int):
        state = self.state
        doc = state.document
        total_lines = doc.get_line_count()
        line_num_width = len(str(max(total_lines, 1))) + 1
        text_width = max(1, width - line_num_width - 1)
        do_highlight = state.filename.endswith('.py')

        for screen_row in range(height):
            doc_line = state.scroll_row + screen_row
            if doc_line >= total_lines:
                try:
                    self.stdscr.addstr(screen_row, 0, " " * width)
                except curses.error:
                    pass
                continue

            line_num_str = str(doc_line + 1).rjust(line_num_width - 1) + " "
            try:
                self.stdscr.addstr(screen_row, 0, line_num_str, curses.A_DIM)
            except curses.error:
                pass

            line_text = doc.get_line(doc_line)
            text_x = line_num_width

            if not do_highlight:
                visible = line_text[state.scroll_col:state.scroll_col + text_width]
                try:
                    self.stdscr.addstr(screen_row, text_x, visible)
                except curses.error:
                    pass
            else:
                self._render_highlighted_line(screen_row, text_x, doc_line, line_text, text_width)

            # Render other users' cursors
            for uname, info in state.users.items():
                if info['line'] == doc_line:
                    col_v = info['col'] - state.scroll_col
                    if 0 <= col_v < text_width:
                        user_idx = list(state.users.keys()).index(uname) % len(USER_COLORS)
                        cp = CP_USER_CURSOR_BASE + user_idx
                        ch = line_text[info['col']] if info['col'] < len(line_text) else ' '
                        try:
                            self.stdscr.addstr(screen_row, text_x + col_v, ch,
                                             curses.color_pair(cp) | curses.A_REVERSE)
                        except curses.error:
                            pass

            # Render own cursor
            if doc_line == state.cursor_line:
                col_v = state.cursor_col - state.scroll_col
                if 0 <= col_v < text_width:
                    ch = line_text[state.cursor_col] if state.cursor_col < len(line_text) else ' '
                    try:
                        self.stdscr.addstr(screen_row, text_x + col_v, ch, curses.A_REVERSE)
                    except curses.error:
                        pass

    def _render_highlighted_line(self, screen_row: int, text_x: int,
                                  doc_line: int, line_text: str, text_width: int):
        tokens = tokenize_line(line_text)
        scroll = self.state.scroll_col
        end_col = scroll + text_width

        for start, end, tok_type in tokens:
            if end <= scroll:
                continue
            if start >= end_col:
                break
            vs = max(start, scroll)
            ve = min(end, end_col)
            segment = line_text[vs:ve]

            if tok_type == TOK_KEYWORD:
                attr = curses.color_pair(CP_KEYWORD) | curses.A_BOLD
            elif tok_type == TOK_STRING:
                attr = curses.color_pair(CP_STRING)
            elif tok_type == TOK_COMMENT:
                attr = curses.color_pair(CP_COMMENT)
            elif tok_type == TOK_NUMBER:
                attr = curses.color_pair(CP_NUMBER)
            else:
                attr = curses.color_pair(CP_NORMAL)

            try:
                self.stdscr.addstr(screen_row, text_x + (vs - scroll), segment, attr)
            except curses.error:
                pass

    def _render_sidebar(self, height: int, editor_width: int, sidebar_width: int):
        state = self.state
        x = editor_width + 1

        for row in range(height):
            try:
                self.stdscr.addch(row, editor_width, curses.ACS_VLINE)
            except curses.error:
                pass

        try:
            self.stdscr.addstr(0, x, " USERS ", curses.A_REVERSE)
        except curses.error:
            pass

        row = 1
        self_info = f"* {state.username}"
        if state.has_lock:
            self_info += " [LOCK]"
        elif state.lock_pending:
            self_info += " [wait]"
        try:
            self.stdscr.addstr(row, x, self_info[:sidebar_width])
        except curses.error:
            pass
        row += 1

        for uname, info in state.users.items():
            if row >= height:
                break
            user_idx = list(state.users.keys()).index(uname) % len(USER_COLORS)
            cp = CP_USER_CURSOR_BASE + user_idx
            line_str = f"  {uname} :{info['line']+1}"
            if state.lock_owner == uname:
                line_str += " [LOCK]"
            try:
                self.stdscr.addstr(row, x, line_str[:sidebar_width], curses.color_pair(cp))
            except curses.error:
                pass
            row += 1

        for r in range(row, height):
            try:
                self.stdscr.addstr(r, x, " " * sidebar_width)
            except curses.error:
                pass

    def _render_status_bar(self, rows: int, cols: int):
        state = self.state
        status_row = rows - 1

        lock_str = ""
        if state.has_lock:
            lock_str = " [LOCKED]"
        elif state.lock_owner:
            lock_str = f" [LOCKED by {state.lock_owner}]"

        status_str = (
            f" {state.filename} | "
            f"Users: {state.user_count} | "
            f"{state.status_message}{lock_str} | "
            f"Ln {state.cursor_line+1}, Col {state.cursor_col+1}"
        )
        status_str = status_str[:cols]

        try:
            self.stdscr.addstr(status_row, 0, status_str.ljust(cols),
                             curses.color_pair(CP_STATUS))
        except curses.error:
            pass

    def _render_search_bar(self, rows: int, cols: int):
        state = self.state
        bar_row = rows - 2

        if state.search_mode:
            text = f"Search: {state.search_query}"
            if state.search_matches:
                text += f" ({state.search_current + 1}/{len(state.search_matches)})"
            text += " [Enter=next, Shift+Enter=prev, Esc=cancel]"
        elif state.replace_mode:
            if state.replace_step == 0:
                text = f"Find: {state.replace_query} [Enter=confirm]"
            elif state.replace_step == 1:
                text = f"Replace with: {state.replace_with} [Enter=confirm]"
            else:
                text = "Replace? (y/n/q): "
        else:
            return

        text = text[:cols]
        try:
            self.stdscr.addstr(bar_row, 0, text.ljust(cols), curses.A_REVERSE)
        except curses.error:
            pass

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(stdscr, args):
    state = ClientState(args.user, args.room, args.file)
    network = NetworkClient(args.host, args.port)

    password = args.password if args.password else ""
    if not network.connect(args.user, args.room, password, args.file):
        stdscr.clear()
        msg = f"Connection failed: {network.error_message or 'Unknown error'}"
        stdscr.addstr(0, 0, msg)
        stdscr.addstr(2, 0, "Press any key to exit...")
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
        return

    state.status_message = "Waiting for server..."
    ui = EditorUI(stdscr, state, network)

    start_time = time.time()
    while not state.connected and time.time() - start_time < 5:
        network.poll()
        msgs = network.get_messages()
        for msg in msgs:
            ui._handle_message(msg)
        time.sleep(0.1)

    if not state.connected:
        stdscr.clear()
        stdscr.addstr(0, 0, "Failed to receive acknowledgement from server.")
        stdscr.addstr(2, 0, "Press any key to exit...")
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
        network.disconnect()
        return

    # Cursor update thread
    def cursor_updater():
        last_line = -1
        last_col = -1
        while network.connected and ui.running:
            if state.cursor_line != last_line or state.cursor_col != last_col:
                last_line = state.cursor_line
                last_col = state.cursor_col
                network.send(MSG_CURSOR_UPDATE, line=state.cursor_line, col=state.cursor_col)
            time.sleep(0.3)

    cursor_thread = threading.Thread(target=cursor_updater, daemon=True)
    cursor_thread.start()

    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        network.disconnect()


def parse_args():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Client")
    parser.add_argument('--host', type=str, default='localhost', help="Server host")
    parser.add_argument('--port', type=int, default=9999, help="Server port")
    parser.add_argument('--user', type=str, required=True, help="Username")
    parser.add_argument('--room', type=str, required=True, help="Room name")
    parser.add_argument('--password', type=str, default='', help="Room password")
    parser.add_argument('--file', type=str, default='document.txt', help="Document filename")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    curses.wrapper(main, args)
