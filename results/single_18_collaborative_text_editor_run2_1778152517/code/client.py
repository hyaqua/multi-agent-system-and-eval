#!/usr/bin/env python3
"""Collaborative text editor TUI client.

Connects to a collaborative editing server and provides a full-screen
curses interface with syntax highlighting, remote cursor display,
search, find-replace, and edit locking.
"""

import argparse
import curses
import json
import os
import re
import selectors
import socket
import sys
import textwrap
import time
from collections import OrderedDict

from ot import (
    apply_operation,
    flat_to_line_col,
    line_col_to_flat,
    transform,
    transform_cursor,
)
from protocol import (
    MSG_ACK,
    MSG_CONNECT,
    MSG_CURSOR_UPDATE,
    MSG_ERROR,
    MSG_LOCK_GRANT,
    MSG_LOCK_RELEASE,
    MSG_LOCK_REQUEST,
    MSG_LOCK_STATUS,
    MSG_OPERATION,
    MSG_OPERATION_BROADCAST,
    MSG_SAVE_ACK,
    MSG_SAVE_REQUEST,
    MSG_UNDO,
    MSG_USER_JOINED,
    MSG_USER_LEFT,
    encode,
    make_connect,
    make_cursor_update,
    make_lock_release,
    make_lock_request,
    make_operation,
    make_save_request,
    make_undo,
)

# ── color constants ─────────────────────────────────────────────
COLOR_DEFAULT = 1
COLOR_KEYWORD = 2
COLOR_STRING = 3
COLOR_COMMENT = 4
COLOR_NUMBER = 5
COLOR_LINE_NUM = 6
COLOR_STATUS = 7
COLOR_CURSOR_MARK = 8
COLOR_SEARCH_HL = 9
COLOR_SIDEBAR = 10
COLOR_USER_CURSOR_BASE = 20  # 20..29 for up to 10 users
COLOR_USER_NAME_BASE = 30  # 30..39 for usernames

# Python keywords for syntax highlighting
PYTHON_KEYWORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
    'try', 'while', 'with', 'yield',
}

# Built-in functions and types that we also highlight
PYTHON_BUILTINS = {
    'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
    'set', 'tuple', 'bool', 'type', 'isinstance', 'hasattr', 'getattr',
    'super', 'object', 'zip', 'enumerate', 'map', 'filter', 'sorted',
    'reversed', 'any', 'all', 'min', 'max', 'sum', 'abs', 'round',
    'open', 'input', 'Exception', 'ValueError', 'TypeError', 'KeyError',
}


def highlight_line(line):
    """Return a list of (char, color_pair) for a line of Python code."""
    result = []
    i = 0
    n = len(line)

    while i < n:
        # Comments
        if line[i] == '#':
            for ch in line[i:]:
                result.append((ch, COLOR_COMMENT))
            break

        # Strings (single and double quoted)
        if line[i] in ('"', "'"):
            quote = line[i]
            # Check for triple quote
            if i + 2 < n and line[i:i + 3] == quote * 3:
                result.append((quote, COLOR_STRING))
                result.append((quote, COLOR_STRING))
                result.append((quote, COLOR_STRING))
                i += 3
                # Go until closing triple quote or end
                while i < n:
                    if i + 2 < n and line[i:i + 3] == quote * 3:
                        result.append((quote, COLOR_STRING))
                        result.append((quote, COLOR_STRING))
                        result.append((quote, COLOR_STRING))
                        i += 3
                        break
                    result.append((line[i], COLOR_STRING))
                    i += 1
                continue
            else:
                result.append((quote, COLOR_STRING))
                i += 1
                while i < n:
                    if line[i] == '\\' and i + 1 < n:
                        result.append((line[i], COLOR_STRING))
                        result.append((line[i + 1], COLOR_STRING))
                        i += 2
                    elif line[i] == quote:
                        result.append((line[i], COLOR_STRING))
                        i += 1
                        break
                    else:
                        result.append((line[i], COLOR_STRING))
                        i += 1
                continue

        # Numbers
        if line[i].isdigit() and (i == 0 or not line[i - 1].isalnum()):
            j = i
            while j < n and (line[j].isdigit() or line[j] == '.'):
                j += 1
            for ch in line[i:j]:
                result.append((ch, COLOR_NUMBER))
            i = j
            continue

        # Identifiers (keywords)
        if line[i].isalpha() or line[i] == '_':
            j = i
            while j < n and (line[j].isalnum() or line[j] == '_'):
                j += 1
            word = line[i:j]
            color = COLOR_KEYWORD if word in PYTHON_KEYWORDS else COLOR_DEFAULT
            if word in PYTHON_BUILTINS:
                color = COLOR_KEYWORD
            for ch in word:
                result.append((ch, color))
            i = j
            continue

        # Default
        result.append((line[i], COLOR_DEFAULT))
        i += 1

    return result


class EditorClient:
    """Curses-based collaborative text editor client."""

    def __init__(self, stdscr, host, port, username, room, password='',
                 filename='untitled.txt'):
        self.stdscr = stdscr
        self.host = host
        self.port = port
        self.username = username
        self.room_name = room
        self.password = password
        self.filename = filename

        # Document state
        self.lines = ['']  # list of lines
        self.version = 0
        self.flat_doc = ''  # cached flat document

        # Cursor
        self.cursor_row = 0
        self.cursor_col = 0
        self.scroll_row = 0
        self.scroll_col = 0

        # Network
        self.sock = None
        self.selector = selectors.DefaultSelector()
        self.connected = False
        self.recv_buffer = b''

        # Pending operations (optimistic)
        self.pending_ops = []  # list of {id, op, original_op}
        self.op_counter = 0

        # Remote users
        self.remote_users = {}  # username -> {cursor_row, cursor_col}
        self.user_colors = {}  # username -> color pair index
        self._next_user_color = 0

        # Lock state
        self.lock_holder = None
        self.lock_queue = []
        self.lock_held = False

        # Search state
        self.search_mode = False
        self.search_term = ''
        self.search_matches = []
        self.search_idx = -1
        self.replace_mode = False
        self.replace_term = ''

        # Status message
        self.status_msg = ''
        self.status_timer = 0

        # Connection status
        self.conn_status = 'Connecting...'

        # Cursor blink
        self.cursor_visible = True
        self._last_cursor_toggle = time.time()

        # Initialize colors
        self._setup_colors()

        # Screen dimensions
        self._update_screen_size()

    # ── color setup ──────────────────────────────────────────

    def _setup_colors(self):
        curses.start_color()
        curses.use_default_colors()

        # Background
        curses.init_pair(COLOR_DEFAULT, curses.COLOR_WHITE, -1)
        curses.init_pair(COLOR_KEYWORD, curses.COLOR_BLUE, -1)
        curses.init_pair(COLOR_STRING, curses.COLOR_GREEN, -1)
        curses.init_pair(COLOR_COMMENT, curses.COLOR_CYAN, -1)
        curses.init_pair(COLOR_NUMBER, curses.COLOR_YELLOW, -1)
        curses.init_pair(COLOR_LINE_NUM, 8, -1)  # gray
        curses.init_pair(COLOR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(COLOR_CURSOR_MARK, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(COLOR_SEARCH_HL, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(COLOR_SIDEBAR, curses.COLOR_WHITE, 235)  # dark gray bg

        # User cursor colors (10 distinct colors)
        user_colors = [
            (curses.COLOR_RED, -1),
            (curses.COLOR_GREEN, -1),
            (curses.COLOR_YELLOW, -1),
            (curses.COLOR_BLUE, -1),
            (curses.COLOR_MAGENTA, -1),
            (curses.COLOR_CYAN, -1),
            (209, -1),  # orange-ish
            (curses.COLOR_WHITE, 52),  # white on dark red
            (curses.COLOR_BLACK, 47),  # black on green
            (curses.COLOR_BLACK, 226),  # black on bright yellow
        ]
        for i, (fg, bg) in enumerate(user_colors):
            curses.init_pair(COLOR_USER_CURSOR_BASE + i, fg, bg)
            curses.init_pair(COLOR_USER_NAME_BASE + i, fg, -1)

    # ── screen ───────────────────────────────────────────────

    def _update_screen_size(self):
        self.max_rows, self.max_cols = self.stdscr.getmaxyx()

    def _sidebar_width(self):
        return min(20, max(12, self.max_cols // 5))

    # ── network ──────────────────────────────────────────────

    def connect(self):
        """Connect to the server and authenticate."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.sock.setblocking(False)
            self.selector.register(self.sock, selectors.EVENT_READ)

            # Send connect message
            self._send(make_connect(self.username, self.room_name, self.password))
            self.conn_status = 'Authenticating...'
            return True
        except Exception as e:
            self.status_msg = f"Connection failed: {e}"
            self.conn_status = f'Error: {e}'
            return False

    def _send(self, msg):
        """Send a message to the server."""
        if self.sock:
            try:
                self.sock.send(encode(msg).encode('utf-8'))
            except Exception:
                self.connected = False

    def _check_network(self):
        """Non-blocking check for incoming network data."""
        if not self.sock:
            return
        events = self.selector.select(timeout=0)
        for key, mask in events:
            if mask & selectors.EVENT_READ:
                try:
                    data = self.sock.recv(65536)
                    if data:
                        self.recv_buffer += data
                        self._process_buffer()
                    else:
                        self._on_disconnect()
                except (ConnectionResetError, BrokenPipeError, OSError):
                    self._on_disconnect()

    def _process_buffer(self):
        """Process complete messages in the receive buffer."""
        while b'\n' in self.recv_buffer:
            line, self.recv_buffer = self.recv_buffer.split(b'\n', 1)
            if line.strip():
                try:
                    msg = json.loads(line.decode('utf-8'))
                    self._handle_message(msg)
                except Exception:
                    pass

    def _handle_message(self, msg):
        msg_type = msg.get('type')

        if msg_type == MSG_ACK:
            self._handle_ack(msg)
        elif msg_type == MSG_OPERATION_BROADCAST:
            self._handle_operation_broadcast(msg)
        elif msg_type == MSG_CURSOR_UPDATE:
            self._handle_cursor_update(msg)
        elif msg_type == MSG_USER_JOINED:
            self._handle_user_joined(msg)
        elif msg_type == MSG_USER_LEFT:
            self._handle_user_left(msg)
        elif msg_type == MSG_LOCK_GRANT:
            self._handle_lock_grant(msg)
        elif msg_type == MSG_LOCK_STATUS:
            self._handle_lock_status(msg)
        elif msg_type == MSG_SAVE_ACK:
            self._handle_save_ack(msg)
        elif msg_type == MSG_ERROR:
            self._handle_error(msg)

    def _on_disconnect(self):
        self.connected = False
        self.conn_status = 'Disconnected'
        if self.sock:
            try:
                self.selector.unregister(self.sock)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # ── message handlers ─────────────────────────────────────

    def _handle_ack(self, msg):
        """Handle the initial connection ack with full document state."""
        document = msg.get('document', '')
        self.flat_doc = document
        self.lines = document.split('\n') if document else ['']
        self.version = msg.get('version', 0)
        self.connected = True
        self.conn_status = 'Connected'

        # Load remote users
        self.remote_users = {}
        for u in msg.get('users', []):
            uname = u['username']
            if uname != self.username:
                self.remote_users[uname] = {
                    'cursor_row': u.get('cursor_row', 0),
                    'cursor_col': u.get('cursor_col', 0),
                }
                if uname not in self.user_colors:
                    self.user_colors[uname] = self._next_user_color
                    self._next_user_color = (self._next_user_color + 1) % 10

        # Lock state
        self.lock_holder = msg.get('lock_holder')
        self.lock_queue = msg.get('lock_queue', [])
        self.lock_held = (self.lock_holder == self.username)

        self.status_msg = f"Joined room '{self.room_name}'"

        # Clamp cursor
        self._clamp_cursor()

    def _handle_operation_broadcast(self, msg):
        """Handle an operation broadcast from the server."""
        op = msg.get('op')
        op_id = msg.get('id')
        username = msg.get('username')
        server_version = msg.get('version', self.version + 1)
        voided = msg.get('voided', False)

        if voided:
            # Remove pending op with this id
            self.pending_ops = [p for p in self.pending_ops if p['id'] != op_id]
            return

        if username == self.username:
            # This is our own operation coming back
            # Find and remove from pending
            self.pending_ops = [p for p in self.pending_ops if p['id'] != op_id]
            self.version = server_version
            return

        # --- Remote operation ---
        # Build pre-op flat doc for cursor adjustments
        self._rebuild_flat()
        pre_flat = self.flat_doc

        # Adjust local cursor position (before applying op)
        cursor_flat = line_col_to_flat(pre_flat, self.cursor_row, self.cursor_col)
        new_cursor_flat = transform_cursor(cursor_flat, op)

        # Adjust remote user cursors (before applying op)
        for uname in self.remote_users:
            rpos = line_col_to_flat(
                pre_flat,
                self.remote_users[uname]['cursor_row'],
                self.remote_users[uname]['cursor_col'],
            )
            new_rpos = transform_cursor(rpos, op)
            nr, nc = flat_to_line_col(pre_flat, new_rpos)
            # After op is applied, the flat positions change, so we just store
            # the transformed flat position; we'll convert after applying
            self.remote_users[uname]['_new_flat_pos'] = new_rpos

        # Transform remote op against pending ops
        transformed_op = dict(op)
        for p in self.pending_ops:
            result = transform(transformed_op, p['op'])
            if result is None:
                return
            transformed_op = result

        # Apply to local document
        self._apply_operation(transformed_op)

        # Transform pending ops against this remote op
        for p in self.pending_ops:
            result = transform(p['op'], op)
            if result:
                p['op'] = result

        self.version = server_version

        # Set cursor to transformed position (convert using new flat doc)
        self.cursor_row, self.cursor_col = flat_to_line_col(
            self.flat_doc, new_cursor_flat
        )
        self._clamp_cursor()

        # Set remote user cursors
        for uname in self.remote_users:
            if '_new_flat_pos' in self.remote_users[uname]:
                nr, nc = flat_to_line_col(
                    self.flat_doc,
                    self.remote_users[uname]['_new_flat_pos']
                )
                self.remote_users[uname]['cursor_row'] = nr
                self.remote_users[uname]['cursor_col'] = nc
                del self.remote_users[uname]['_new_flat_pos']

    def _handle_cursor_update(self, msg):
        username = msg.get('username')
        if username == self.username:
            return
        self.remote_users[username] = {
            'cursor_row': msg.get('cursor_row', 0),
            'cursor_col': msg.get('cursor_col', 0),
        }
        if username not in self.user_colors:
            self.user_colors[username] = self._next_user_color
            self._next_user_color = (self._next_user_color + 1) % 10

    def _handle_user_joined(self, msg):
        username = msg.get('username')
        if username != self.username:
            self.remote_users[username] = {
                'cursor_row': msg.get('cursor_row', 0),
                'cursor_col': msg.get('cursor_col', 0),
            }
            if username not in self.user_colors:
                self.user_colors[username] = self._next_user_color
                self._next_user_color = (self._next_user_color + 1) % 10
            self.status_msg = f"User '{username}' joined"

    def _handle_user_left(self, msg):
        username = msg.get('username')
        self.remote_users.pop(username, None)
        self.status_msg = f"User '{username}' left"

    def _handle_lock_grant(self, msg):
        granted = msg.get('granted', False)
        status = msg.get('status', '')
        self.lock_holder = msg.get('lock_holder')
        self.lock_queue = msg.get('lock_queue', [])

        if status == 'granted':
            self.lock_held = True
            self.status_msg = "Lock acquired! You can now edit."
        elif status == 'already_held':
            self.lock_held = True
        elif status == 'released':
            self.lock_held = False
            self.status_msg = "Lock released."
        elif status == 'queued':
            self.lock_held = False
            self.status_msg = f"Lock queued. Position: {self.lock_queue.index(self.username) + 1 if self.username in self.lock_queue else '?'}"

    def _handle_lock_status(self, msg):
        self.lock_holder = msg.get('lock_holder')
        self.lock_queue = msg.get('lock_queue', [])
        self.lock_held = (self.lock_holder == self.username)

    def _handle_save_ack(self, msg):
        self.status_msg = f"Saved: {msg.get('filename', 'unknown')}"

    def _handle_error(self, msg):
        self.status_msg = f"Error: {msg.get('message', 'unknown')}"

    # ── document helpers ─────────────────────────────────────

    def _rebuild_flat(self):
        """Rebuild flat document from lines."""
        self.flat_doc = '\n'.join(self.lines)

    def _apply_operation(self, op):
        """Apply an operation to the local document."""
        if op is None:
            return
        self._rebuild_flat()
        self.flat_doc = apply_operation(self.flat_doc, op)
        self.lines = self.flat_doc.split('\n') if self.flat_doc else ['']

    def _apply_local_operation(self, op):
        """Apply operation locally (optimistic)."""
        self._apply_operation(op)
        self.version += 1  # Tentative

    def _adjust_cursor_for_op(self, op):
        """Adjust local cursor after a remote operation."""
        # Get flat cursor position before the op
        self._rebuild_flat()
        pre_flat = self.flat_doc
        # We need pre-op flat doc. Approximate by reverse-applying the op
        # Simpler: just check if cursor needs adjusting
        op_pos = op['position']
        cursor_flat = line_col_to_flat(pre_flat, self.cursor_row, self.cursor_col)
        new_cursor = transform_cursor(cursor_flat, op)
        r, c = flat_to_line_col(self.flat_doc, new_cursor)
        self.cursor_row = r
        self.cursor_col = c

    def _clamp_cursor(self):
        """Clamp cursor to valid document range."""
        if not self.lines:
            self.lines = ['']
        self.cursor_row = max(0, min(self.cursor_row, len(self.lines) - 1))
        line_len = len(self.lines[self.cursor_row]) if self.lines else 0
        self.cursor_col = max(0, min(self.cursor_col, line_len))

    # ── local edits ──────────────────────────────────────────

    def _send_operation(self, op):
        """Send an edit operation to the server and apply locally."""
        self._rebuild_flat()
        flat_pos = line_col_to_flat(self.flat_doc, self.cursor_row, self.cursor_col)

        # Create flat-position operation
        if op['type'] == 'insert':
            flat_op = {'type': 'insert', 'position': flat_pos, 'char': op['char']}
        else:  # delete
            if op.get('backspace'):
                # Backspace: delete character before cursor
                if flat_pos > 0:
                    flat_op = {'type': 'delete', 'position': flat_pos - 1}
                else:
                    return
            else:
                # Delete: delete character at cursor
                flat_op = {'type': 'delete', 'position': flat_pos}

        op_id = self.op_counter
        self.op_counter += 1

        # Apply locally (optimistic)
        self._apply_local_operation(flat_op)

        # Update cursor for insert
        if flat_op['type'] == 'insert':
            self.cursor_col += 1
            # Handle newline
            if flat_op['char'] == '\n':
                self.cursor_row += 1
                self.cursor_col = 0
        elif flat_op['type'] == 'delete':
            if op.get('backspace'):
                self.cursor_col -= 1
                if self.cursor_col < 0:
                    if self.cursor_row > 0:
                        self.cursor_row -= 1
                        self.cursor_col = len(self.lines[self.cursor_row]) if self.lines else 0

        self._clamp_cursor()

        # Add to pending
        self.pending_ops.append({
            'id': op_id,
            'op': flat_op,
        })

        # Send to server
        self._send(make_operation(flat_op, self.version - 1, op_id))

        # Send cursor update
        self._send_cursor_update()

    def _send_cursor_update(self):
        self._send(make_cursor_update(self.cursor_row, self.cursor_col))

    # ── input handling ───────────────────────────────────────

    def handle_key(self, key):
        """Handle a keypress. Returns True if the app should continue."""
        if key == -1:
            return True  # timeout

        # Search / replace modes
        if self.search_mode:
            return self._handle_search_key(key)
        if self.replace_mode:
            return self._handle_replace_key(key)

        # Ctrl key combinations
        if key == 19:  # Ctrl+S
            self._send(make_save_request())
            self.status_msg = "Saving..."
            return True

        if key == 6:  # Ctrl+F
            self._start_search()
            return True

        if key == 8:  # Ctrl+H
            self._start_replace()
            return True

        if key == 12:  # Ctrl+L
            self._toggle_lock()
            return True

        if key == 26:  # Ctrl+Z
            self._send(make_undo())
            self.status_msg = "Undo requested..."
            return True

        # Navigation
        if key == curses.KEY_UP:
            if self.cursor_row > 0:
                self.cursor_row -= 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            self._send_cursor_update()
            return True

        if key == curses.KEY_DOWN:
            if self.cursor_row < len(self.lines) - 1:
                self.cursor_row += 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            self._send_cursor_update()
            return True

        if key == curses.KEY_LEFT:
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_row > 0:
                self.cursor_row -= 1
                self.cursor_col = len(self.lines[self.cursor_row])
            self._send_cursor_update()
            return True

        if key == curses.KEY_RIGHT:
            if self.cursor_col < len(self.lines[self.cursor_row]):
                self.cursor_col += 1
            elif self.cursor_row < len(self.lines) - 1:
                self.cursor_row += 1
                self.cursor_col = 0
            self._send_cursor_update()
            return True

        if key == curses.KEY_HOME:
            # Go to start of line (first non-whitespace or column 0)
            line = self.lines[self.cursor_row]
            start = len(line) - len(line.lstrip())
            if self.cursor_col == start and start > 0:
                self.cursor_col = 0
            else:
                self.cursor_col = start
            self._send_cursor_update()
            return True

        if key == curses.KEY_END:
            self.cursor_col = len(self.lines[self.cursor_row])
            self._send_cursor_update()
            return True

        if key == curses.KEY_PPAGE:  # Page Up
            page_size = max(1, self.max_rows - 4)
            self.cursor_row = max(0, self.cursor_row - page_size)
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            self._send_cursor_update()
            return True

        if key == curses.KEY_NPAGE:  # Page Down
            page_size = max(1, self.max_rows - 4)
            self.cursor_row = min(len(self.lines) - 1, self.cursor_row + page_size)
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            self._send_cursor_update()
            return True

        # Ctrl+Left: word left
        if key == 545 or key == 546 or key == 549 or key == 554:  # Various terminals
            self._word_left()
            self._send_cursor_update()
            return True

        # Ctrl+Right: word right
        if key == 560 or key == 561 or key == 558 or key == 565:  # Various terminals
            self._word_right()
            self._send_cursor_update()
            return True

        # curses KEY_SLEFT / KEY_SRIGHT (some terminals map Ctrl+Left/Right here)
        if 'KEY_SLEFT' in dir(curses) and key == curses.KEY_SLEFT:
            self._word_left()
            self._send_cursor_update()
            return True
        if 'KEY_SRIGHT' in dir(curses) and key == curses.KEY_SRIGHT:
            self._word_right()
            self._send_cursor_update()
            return True

        # Editing keys
        if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            self._send_operation({'type': 'delete', 'backspace': True})
            return True

        if key == curses.KEY_DC:  # Delete key
            self._send_operation({'type': 'delete', 'backspace': False})
            return True

        if key == 10 or key == 13:  # Enter
            self._send_operation({'type': 'insert', 'char': '\n'})
            return True

        if key == 9:  # Tab
            self._send_operation({'type': 'insert', 'char': '\t'})
            return True

        # Printable characters
        if 32 <= key <= 126:
            char = chr(key)
            self._send_operation({'type': 'insert', 'char': char})
            return True

        # Handle escaped Ctrl+Left / Ctrl+Right from various terminals
        # (we handle these via the raw key codes above)

        return True

    def _word_left(self):
        """Move cursor left by one word."""
        text = self.flat_doc if self.flat_doc else '\n'.join(self.lines)
        pos = line_col_to_flat(self.flat_doc, self.cursor_row, self.cursor_col)
        if pos <= 0:
            return
        pos -= 1
        # Skip whitespace
        while pos > 0 and text[pos].isspace():
            pos -= 1
        # Skip word characters
        while pos > 0 and not text[pos].isspace():
            pos -= 1
        if text[pos].isspace():
            pos += 1
        self.cursor_row, self.cursor_col = flat_to_line_col(text, pos)

    def _word_right(self):
        """Move cursor right by one word."""
        text = self.flat_doc if self.flat_doc else '\n'.join(self.lines)
        pos = line_col_to_flat(self.flat_doc, self.cursor_row, self.cursor_col)
        if pos >= len(text):
            return
        # Skip word characters
        while pos < len(text) and not text[pos].isspace():
            pos += 1
        # Skip whitespace
        while pos < len(text) and text[pos].isspace():
            pos += 1
        self.cursor_row, self.cursor_col = flat_to_line_col(text, pos)

    # ── lock ────────────────────────────────────────────────

    def _toggle_lock(self):
        if self.lock_held:
            self._send(make_lock_release())
        else:
            self._send(make_lock_request())

    # ── search ──────────────────────────────────────────────

    def _start_search(self):
        self.search_mode = True
        self.search_term = ''
        self.search_matches = []
        self.search_idx = -1
        self.status_msg = 'Search: '

    def _handle_search_key(self, key):
        if key == 27:  # Escape
            self.search_mode = False
            self.search_term = ''
            self.search_matches = []
            self.search_idx = -1
            self.status_msg = 'Search cancelled'
            return True

        if key in (10, 13):  # Enter
            if self.search_matches:
                self.search_idx = (self.search_idx + 1) % len(self.search_matches)
                pos = self.search_matches[self.search_idx]
                self.cursor_row, self.cursor_col = flat_to_line_col(
                    self.flat_doc, pos
                )
                self._send_cursor_update()
                self.status_msg = f"Match {self.search_idx + 1}/{len(self.search_matches)}"
            return True

        if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            if self.search_term:
                self.search_term = self.search_term[:-1]
            self._update_search()
            return True

        # Shift+Enter for reverse cycle (we can't easily detect Shift+Enter,
        # so we use Ctrl+P or just cycle with Enter)
        if key == 353:  # Shift+Enter on some terminals
            if self.search_matches:
                self.search_idx = (self.search_idx - 1) % len(self.search_matches)
                pos = self.search_matches[self.search_idx]
                self.cursor_row, self.cursor_col = flat_to_line_col(
                    self.flat_doc, pos
                )
                self._send_cursor_update()
                self.status_msg = f"Match {self.search_idx + 1}/{len(self.search_matches)}"
            return True

        if 32 <= key <= 126:
            self.search_term += chr(key)
            self._update_search()
            return True

        return True

    def _update_search(self):
        self.search_matches = []
        self.search_idx = -1
        if not self.search_term:
            self.status_msg = 'Search: ' + self.search_term
            return
        text = self.flat_doc
        term = self.search_term
        idx = 0
        while True:
            idx = text.find(term, idx)
            if idx == -1:
                break
            self.search_matches.append(idx)
            idx += 1
        self.status_msg = f"Search: {self.search_term} ({len(self.search_matches)} matches)"

    # ── replace ─────────────────────────────────────────────

    def _start_replace(self):
        self.replace_mode = True
        self.search_term = ''
        self.replace_term = ''
        self._replace_phase = 'search'  # 'search' or 'confirm'
        self.search_matches = []
        self.search_idx = -1
        self.status_msg = 'Find: '

    def _handle_replace_key(self, key):
        if key == 27:  # Escape
            self.replace_mode = False
            self.search_term = ''
            self.replace_term = ''
            self.search_matches = []
            self.status_msg = 'Replace cancelled'
            return True

        if self._replace_phase == 'search':
            if key in (10, 13):  # Enter - finish search term, ask for replace
                if self.search_term:
                    self._replace_phase = 'replace_input'
                    self.status_msg = f"Replace '{self.search_term}' with: "
                return True
            if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                if self.search_term:
                    self.search_term = self.search_term[:-1]
                self.status_msg = 'Find: ' + self.search_term
                return True
            if 32 <= key <= 126:
                self.search_term += chr(key)
                self.status_msg = 'Find: ' + self.search_term
                return True
            return True

        elif self._replace_phase == 'replace_input':
            if key in (10, 13):  # Enter - now find matches and start confirming
                self._update_search()
                self._replace_phase = 'confirm'
                if self.search_matches:
                    self.search_idx = 0
                    pos = self.search_matches[0]
                    self.cursor_row, self.cursor_col = flat_to_line_col(
                        self.flat_doc, pos
                    )
                    self._send_cursor_update()
                    self.status_msg = (
                        f"Replace? (y/n/a/q) "
                        f"Match 1/{len(self.search_matches)}"
                    )
                else:
                    self.status_msg = 'No matches found.'
                    self.replace_mode = False
                return True
            if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                if self.replace_term:
                    self.replace_term = self.replace_term[:-1]
                self.status_msg = f"Replace '{self.search_term}' with: {self.replace_term}"
                return True
            if 32 <= key <= 126:
                self.replace_term += chr(key)
                self.status_msg = f"Replace '{self.search_term}' with: {self.replace_term}"
                return True
            return True

        elif self._replace_phase == 'confirm':
            if key in (ord('y'), ord('Y')):
                # Replace current match
                pos = self.search_matches[self.search_idx]
                # Delete the search term and insert replacement
                self._replace_at(pos, len(self.search_term), self.replace_term)
                # Recompute matches
                self._update_search()
                if self.search_matches:
                    self.search_idx = min(self.search_idx, len(self.search_matches) - 1)
                    if self.search_idx >= 0:
                        pos = self.search_matches[self.search_idx]
                        self.cursor_row, self.cursor_col = flat_to_line_col(
                            self.flat_doc, pos
                        )
                else:
                    self.status_msg = 'All matches replaced.'
                    self.replace_mode = False
                    return True
                self.status_msg = (
                    f"Replace? (y/n/a/q) "
                    f"Match {self.search_idx + 1}/{len(self.search_matches)}"
                )
                return True

            if key in (ord('n'), ord('N')):
                if self.search_matches:
                    self.search_idx = (self.search_idx + 1) % len(self.search_matches)
                    pos = self.search_matches[self.search_idx]
                    self.cursor_row, self.cursor_col = flat_to_line_col(
                        self.flat_doc, pos
                    )
                    self._send_cursor_update()
                    self.status_msg = (
                        f"Replace? (y/n/a/q) "
                        f"Match {self.search_idx + 1}/{len(self.search_matches)}"
                    )
                else:
                    self.replace_mode = False
                return True

            if key in (ord('a'), ord('A')):
                # Replace all remaining
                for pos in reversed(self.search_matches[self.search_idx:]):
                    self._replace_at(pos, len(self.search_term), self.replace_term)
                self.status_msg = 'All remaining matches replaced.'
                self.replace_mode = False
                return True

            if key in (ord('q'), ord('Q')):
                self.status_msg = 'Replace quit.'
                self.replace_mode = False
                return True

            return True

        return True

    def _replace_at(self, pos, old_len, new_text):
        """Replace old_len characters at pos with new_text, sending operations."""
        text = self.flat_doc if self.flat_doc else '\n'.join(self.lines)
        # Delete old_len characters (in reverse so positions stay valid)
        for i in range(old_len - 1, -1, -1):
            op = {'type': 'delete', 'position': pos + i}
            self._apply_local_operation(op)
            op_id = self.op_counter
            self.op_counter += 1
            self.pending_ops.append({'id': op_id, 'op': dict(op)})
            self._send(make_operation(op, self.version - 1, op_id))
            self.version += 1

        # Insert new_text
        for i, ch in enumerate(new_text):
            op = {'type': 'insert', 'position': pos + i, 'char': ch}
            self._apply_local_operation(op)
            op_id = self.op_counter
            self.op_counter += 1
            self.pending_ops.append({'id': op_id, 'op': dict(op)})
            self._send(make_operation(op, self.version - 1, op_id))
            self.version += 1

    # ── rendering ────────────────────────────────────────────

    def render(self):
        """Render the full TUI."""
        self._update_screen_size()
        self.stdscr.erase()
        self._rebuild_flat()

        sidebar_w = self._sidebar_width()
        main_w = self.max_cols - sidebar_w
        text_area_h = self.max_rows - 2  # leave room for status bar and cursor ruler

        # Update scroll
        self._update_scroll(main_w - 6, text_area_h - 1)  # -6 for line numbers

        # Draw cursor ruler (shows remote usernames above their cursors)
        ruler_row = 0
        self._draw_cursor_ruler(ruler_row, main_w)

        # Draw document with line numbers
        doc_start_row = 1
        self._draw_document(doc_start_row, main_w, text_area_h - 1)

        # Draw sidebar
        self._draw_sidebar(sidebar_w)

        # Draw status bar
        self._draw_status_bar()

        # Draw search/replace prompt if active
        if self.search_mode or self.replace_mode:
            self._draw_prompt()

        self.stdscr.refresh()

    def _update_scroll(self, visible_width, visible_height):
        """Update scroll position to keep cursor visible."""
        # Vertical scroll
        if self.cursor_row < self.scroll_row:
            self.scroll_row = self.cursor_row
        elif self.cursor_row >= self.scroll_row + visible_height:
            self.scroll_row = self.cursor_row - visible_height + 1
        self.scroll_row = max(0, self.scroll_row)

        # Horizontal scroll
        line_num_width = len(str(max(1, len(self.lines)))) + 2
        text_w = visible_width - line_num_width
        if text_w < 1:
            text_w = 1
        if self.cursor_col < self.scroll_col:
            self.scroll_col = self.cursor_col
        elif self.cursor_col >= self.scroll_col + text_w:
            self.scroll_col = self.cursor_col - text_w + 1
        self.scroll_col = max(0, self.scroll_col)

    def _draw_cursor_ruler(self, row, main_w):
        """Draw a ruler line showing remote usernames at their cursor columns."""
        if row >= self.max_rows:
            return
        line_num_w = len(str(max(1, len(self.lines)))) + 2
        text_x = line_num_w
        text_w = main_w - text_x

        # Only show cursors on visible lines
        for uname, info in self.remote_users.items():
            urow = info['cursor_row']
            ucol = info['cursor_col']
            if urow >= self.scroll_row and urow < self.scroll_row + (self.max_rows - 3):
                # Cursor is on a visible line
                display_col = ucol - self.scroll_col
                if 0 <= display_col < text_w:
                    x = text_x + display_col
                    if x < main_w:
                        color = COLOR_USER_NAME_BASE + self.user_colors.get(uname, 0)
                        try:
                            self.stdscr.addstr(
                                row, x, uname[:text_w - display_col],
                                curses.color_pair(color) | curses.A_BOLD
                            )
                        except curses.error:
                            pass

    def _draw_document(self, start_row, main_w, visible_h):
        """Draw the document text with line numbers and syntax highlighting."""
        line_num_w = len(str(max(1, len(self.lines)))) + 2
        text_x = line_num_w
        text_w = main_w - text_x
        is_python = self.filename.endswith('.py')

        for i in range(visible_h):
            screen_row = start_row + i
            if screen_row >= self.max_rows:
                break

            line_idx = self.scroll_row + i
            if line_idx >= len(self.lines):
                break

            line = self.lines[line_idx]

            # Line number
            num_str = str(line_idx + 1).rjust(line_num_w - 1) + ' '
            try:
                if line_idx == self.cursor_row:
                    self.stdscr.addstr(
                        screen_row, 0, num_str,
                        curses.color_pair(COLOR_LINE_NUM) | curses.A_BOLD
                    )
                else:
                    self.stdscr.addstr(
                        screen_row, 0, num_str,
                        curses.color_pair(COLOR_LINE_NUM)
                    )
            except curses.error:
                pass

            # Visible portion of the line
            visible_line = line[self.scroll_col:self.scroll_col + text_w]

            # Apply syntax highlighting
            if is_python:
                highlighted = highlight_line(line)
                # Extract the visible portion
                vis_highlights = highlighted[self.scroll_col:self.scroll_col + text_w]

                for j, (ch, color) in enumerate(vis_highlights):
                    x = text_x + j
                    if x >= main_w:
                        break
                    try:
                        attr = curses.color_pair(color)
                        # Highlight current cursor position
                        if line_idx == self.cursor_row and (self.scroll_col + j) == self.cursor_col:
                            attr = curses.color_pair(COLOR_CURSOR_MARK) | curses.A_BOLD

                        # Check for remote user cursors on this line
                        for uname, info in self.remote_users.items():
                            if (info['cursor_row'] == line_idx and
                                    info['cursor_col'] == self.scroll_col + j):
                                user_color = COLOR_USER_CURSOR_BASE + self.user_colors.get(uname, 0)
                                attr = curses.color_pair(user_color) | curses.A_BOLD
                                break

                        self.stdscr.addstr(screen_row, x, ch, attr)
                    except curses.error:
                        pass
            else:
                for j, ch in enumerate(visible_line):
                    x = text_x + j
                    if x >= main_w:
                        break
                    try:
                        attr = curses.color_pair(COLOR_DEFAULT)
                        if line_idx == self.cursor_row and (self.scroll_col + j) == self.cursor_col:
                            attr = curses.color_pair(COLOR_CURSOR_MARK) | curses.A_BOLD

                        for uname, info in self.remote_users.items():
                            if (info['cursor_row'] == line_idx and
                                    info['cursor_col'] == self.scroll_col + j):
                                user_color = COLOR_USER_CURSOR_BASE + self.user_colors.get(uname, 0)
                                attr = curses.color_pair(user_color) | curses.A_BOLD
                                break

                        self.stdscr.addstr(screen_row, x, ch, attr)
                    except curses.error:
                        pass

            # If cursor is at end of line (beyond text)
            if line_idx == self.cursor_row and self.cursor_col >= len(line):
                display_col = self.cursor_col - self.scroll_col
                if 0 <= display_col < text_w:
                    x = text_x + display_col
                    if x < main_w:
                        try:
                            self.stdscr.addstr(
                                screen_row, x, ' ',
                                curses.color_pair(COLOR_CURSOR_MARK) | curses.A_BOLD
                            )
                        except curses.error:
                            pass

            # If cursor is beyond all text
            if line_idx == self.cursor_row and self.cursor_col >= self.scroll_col + text_w:
                pass  # cursor is off-screen to the right

        # Search highlighting
        if self.search_mode and self.search_term:
            self._highlight_search_matches(start_row, text_x, text_w, visible_h)

    def _highlight_search_matches(self, start_row, text_x, text_w, visible_h):
        """Highlight all search matches in the visible area."""
        if not self.search_term:
            return
        term = self.search_term
        text = self.flat_doc

        for i in range(visible_h):
            screen_row = start_row + i
            if screen_row >= self.max_rows:
                break
            line_idx = self.scroll_row + i
            if line_idx >= len(self.lines):
                break
            line = self.lines[line_idx]

            # Find all occurrences in this line
            search_start = 0
            while True:
                idx = line.find(term, search_start)
                if idx == -1:
                    break
                # Check if this match is in the visible area
                if idx + len(term) > self.scroll_col and idx < self.scroll_col + text_w:
                    for k in range(len(term)):
                        col = idx + k
                        if self.scroll_col <= col < self.scroll_col + text_w:
                            x = text_x + (col - self.scroll_col)
                            if x < self.max_cols - self._sidebar_width():
                                try:
                                    # Don't overwrite cursor
                                    existing = self.stdscr.inch(screen_row, x)
                                    if existing & curses.A_COLOR != curses.color_pair(COLOR_CURSOR_MARK):
                                        self.stdscr.addstr(
                                            screen_row, x, line[col],
                                            curses.color_pair(COLOR_SEARCH_HL)
                                        )
                                except curses.error:
                                    pass
                search_start = idx + 1

    def _draw_sidebar(self, sidebar_w):
        """Draw the sidebar with connected users."""
        if sidebar_w < 5:
            return
        x = self.max_cols - sidebar_w
        h = self.max_rows - 2

        # Draw border
        try:
            for i in range(h):
                self.stdscr.addstr(i, x, '│', curses.color_pair(COLOR_SIDEBAR))
        except curses.error:
            pass

        # Title
        try:
            title = ' Users '
            self.stdscr.addstr(0, x + 1, title[:sidebar_w - 1],
                               curses.color_pair(COLOR_SIDEBAR) | curses.A_BOLD)
        except curses.error:
            pass

        # Separator
        try:
            self.stdscr.addstr(1, x + 1, '─' * (sidebar_w - 2),
                               curses.color_pair(COLOR_SIDEBAR))
        except curses.error:
            pass

        # List users
        all_users = [(self.username, {
            'cursor_row': self.cursor_row,
            'cursor_col': self.cursor_col,
        })]
        for uname, info in self.remote_users.items():
            all_users.append((uname, info))

        for i, (uname, info) in enumerate(all_users):
            y = 2 + i
            if y >= h:
                break
            line_str = f"L{info['cursor_row'] + 1}"
            display = f" {uname[:sidebar_w - len(line_str) - 3]} {line_str}"
            display = display[:sidebar_w - 1]

            if uname == self.username:
                attr = curses.color_pair(COLOR_STATUS) | curses.A_BOLD
            else:
                user_color = COLOR_USER_NAME_BASE + self.user_colors.get(uname, 0)
                attr = curses.color_pair(user_color) | curses.A_BOLD

            try:
                self.stdscr.addstr(y, x + 1, display, attr)
            except curses.error:
                pass

        # Lock indicator
        if self.lock_holder:
            lock_y = min(h - 2, 2 + len(all_users) + 1)
            if lock_y < h:
                lock_str = f" 🔒 {self.lock_holder}"
                try:
                    self.stdscr.addstr(
                        lock_y, x + 1, lock_str[:sidebar_w - 1],
                        curses.color_pair(COLOR_SIDEBAR)
                    )
                except curses.error:
                    pass

            if self.lock_queue:
                queue_y = lock_y + 1
                if queue_y < h:
                    queue_str = f" Queue: {len(self.lock_queue)}"
                    try:
                        self.stdscr.addstr(
                            queue_y, x + 1, queue_str[:sidebar_w - 1],
                            curses.color_pair(COLOR_SIDEBAR)
                        )
                    except curses.error:
                        pass

    def _draw_status_bar(self):
        """Draw the status bar at the bottom."""
        y = self.max_rows - 1
        if y < 0:
            return

        # Build status line
        user_count = len(self.remote_users) + 1
        lock_indicator = '🔒' if self.lock_held else ('🔓' if self.lock_holder else '')
        status = (
            f" {self.filename} | Users: {user_count} | {self.conn_status} "
            f"| Ln {self.cursor_row + 1}, Col {self.cursor_col + 1} {lock_indicator} "
        )

        # Fill with background
        try:
            self.stdscr.addstr(y, 0, ' ' * self.max_cols,
                               curses.color_pair(COLOR_STATUS))
        except curses.error:
            pass

        # Write status text
        try:
            self.stdscr.addstr(y, 0, status[:self.max_cols],
                               curses.color_pair(COLOR_STATUS) | curses.A_BOLD)
        except curses.error:
            pass

        # If there's a temporary status message, show it
        if self.status_msg and self.status_timer > 0:
            msg = f" {self.status_msg} "
            try:
                msg_x = max(0, self.max_cols - len(msg) - 2)
                self.stdscr.addstr(y - 1, msg_x, msg,
                                   curses.color_pair(COLOR_SEARCH_HL))
            except curses.error:
                pass

    def _draw_prompt(self):
        """Draw the search/replace prompt."""
        y = self.max_rows - 2
        if y < 1:
            y = self.max_rows - 1

        msg = self.status_msg
        try:
            self.stdscr.addstr(y, 0, ' ' * self.max_cols,
                               curses.color_pair(COLOR_SEARCH_HL))
            self.stdscr.addstr(y, 0, msg[:self.max_cols],
                               curses.color_pair(COLOR_SEARCH_HL) | curses.A_BOLD)
        except curses.error:
            pass

    # ── main loop ────────────────────────────────────────────

    def run(self):
        """Main event loop."""
        if not self.connect():
            return

        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        curses.curs_set(0)  # Hide hardware cursor, we draw our own
        curses.cbreak()
        self.stdscr.clear()

        # Initial cursor update
        self._send_cursor_update()

        while True:
            self._check_network()

            if not self.connected and self.sock is None:
                self.status_msg = "Disconnected. Press 'q' to quit."
                self.render()
                key = self.stdscr.getch()
                if key == ord('q'):
                    break
                time.sleep(0.1)
                continue

            # Handle input
            key = self.stdscr.getch()
            if key == 27:  # Escape
                # Check for escape sequences (Ctrl+Left, Ctrl+Right, etc.)
                # But simple Escape exits search or is a no-op
                if self.search_mode:
                    self.search_mode = False
                    self.search_term = ''
                    self.search_matches = []
                    self.status_msg = ''
                elif self.replace_mode:
                    self.replace_mode = False
                    self.status_msg = ''
            elif key == ord('q') and not self.search_mode and not self.replace_mode:
                # Quit (Ctrl+Q or just q when not searching)
                pass  # We'll keep going; Ctrl+C to quit
            elif not self.handle_key(key):
                break

            # Update status timer
            if self.status_timer > 0:
                self.status_timer -= 1
                if self.status_timer == 0:
                    self.status_msg = ''

            # Set status timer for new messages
            if self.status_msg and self.status_timer == 0:
                self.status_timer = 50  # ~1 second at 20fps

            # Cursor blink
            now = time.time()
            if now - self._last_cursor_toggle > 0.5:
                self.cursor_visible = not self.cursor_visible
                self._last_cursor_toggle = now

            self.render()

            # Small sleep to prevent CPU spinning
            time.sleep(0.02)

        self._cleanup()

    def _cleanup(self):
        if self.sock:
            try:
                self.selector.unregister(self.sock)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


def main():
    parser = argparse.ArgumentParser(description='Collaborative Text Editor Client')
    parser.add_argument(
        '--host', type=str, default='127.0.0.1',
        help='Server host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port', type=int, default=9000,
        help='Server port (default: 9000)'
    )
    parser.add_argument(
        '--user', type=str, required=True,
        help='Username for the session'
    )
    parser.add_argument(
        '--room', type=str, required=True,
        help='Room name to join'
    )
    parser.add_argument(
        '--password', type=str, default='',
        help='Room password (if required)'
    )
    parser.add_argument(
        '--file', type=str, default='untitled.txt',
        help='Filename for syntax highlighting (default: untitled.txt)'
    )
    args = parser.parse_args()

    def _run(stdscr):
        editor = EditorClient(
            stdscr, args.host, args.port, args.user, args.room,
            args.password, args.file
        )
        editor.run()

    curses.wrapper(_run)


if __name__ == '__main__':
    main()
