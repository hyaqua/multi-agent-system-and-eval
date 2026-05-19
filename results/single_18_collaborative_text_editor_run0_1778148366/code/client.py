"""
Collaborative Text Editor TUI Client.

Uses curses for the terminal interface with syntax highlighting,
real-time collaboration, search/replace, and more.

Usage: python client.py --host localhost --port 9999 --user username --room roomname [--password pw] [--file filename]
"""

import socket
import select
import sys
import json
import os
import time
import argparse
import curses
import curses.ascii
import traceback
from protocol import *
from ot import *

# Python keywords for syntax highlighting
PYTHON_KEYWORDS = {
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
    'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
    'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
    'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
    'True', 'False', 'None', 'self',
}

# Color pair indices
COLOR_DEFAULT = 1
COLOR_LINE_NUM = 2
COLOR_STATUS_BAR = 3
COLOR_KEYWORD = 4
COLOR_STRING = 5
COLOR_COMMENT = 6
COLOR_NUMBER = 7
COLOR_SEARCH_HIGHLIGHT = 8
COLOR_CURSOR_OTHER = 9  # Base for other users' cursors (9..15)
COLOR_SIDEBAR = 16
COLOR_MY_CURSOR = 17
COLOR_PROMPT = 18


class EditorClient:
    """Main TUI client for the collaborative editor."""

    def __init__(self, host, port, username, room, password, filename=None):
        self.host = host
        self.port = port
        self.username = username
        self.room_name = room
        self.password = password
        self.filename = filename or f"{room}.txt"

        # Network
        self.sock = None
        self.client_id = None
        self.recv_buffer = b""

        # Document state
        self.document = ""
        self.version = 0
        self.cursor_row = 0
        self.cursor_col = 0

        # Optimistic update tracking
        self.pending_ops = []  # list of (op, inverse_op) tuples applied locally but not confirmed
        self.pending_client_version = 0  # version we had when we made pending ops

        # Viewport scrolling
        self.scroll_row = 0
        self.scroll_col = 0

        # Remote users
        self.remote_users = {}  # client_id -> {username, cursor_row, cursor_col, color_pair}

        # Lock state
        self.lock_holder = None  # client_id of lock holder (or None)
        self.lock_queue = []  # list of client_ids waiting
        self.i_hold_lock = False

        # Connected users list
        self.connected_users = []  # list of {client_id, username, cursor_row, cursor_col}

        # Search state
        self.search_mode = False
        self.search_query = ""
        self.search_matches = []
        self.search_current_match = -1

        # Replace state
        self.replace_mode = False
        self.replace_query = ""
        self.replace_with = ""
        self.replace_step = 0  # 0: enter search, 1: enter replace, 2: confirm

        # Status message
        self.status_message = ""
        self.status_message_time = 0

        # Connection status
        self.connected = False
        self.connection_error = ""

        # Curses
        self.screen = None
        self.running = False

        # User color assignment
        self.user_colors = {}  # client_id -> color_pair
        self.next_user_color = COLOR_CURSOR_OTHER

    def connect(self):
        """Establish connection and authenticate with the server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.sock.setblocking(False)

            # Send connect message
            msg = make_connect(self.username, self.room_name, self.password)
            self.sock.send(encode_message(msg).encode('utf-8'))

            # Wait for ack
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    data = self.sock.recv(4096)
                    if data:
                        self.recv_buffer += data
                        if b'\n' in self.recv_buffer:
                            line, self.recv_buffer = self.recv_buffer.split(b'\n', 1)
                            response = decode_message(line.decode('utf-8'))
                            if response.get('type') == MSG_ACK:
                                self.client_id = response.get('client_id')
                                self.document = response.get('document', '')
                                self.version = response.get('version', 0)
                                self.connected = True

                                # Initialize connected users (exclude self)
                                for cu in response.get('clients', []):
                                    uid = cu['client_id']
                                    if uid != self.client_id:
                                        self.remote_users[uid] = {
                                            'username': cu['username'],
                                            'cursor_row': cu.get('cursor_row', 0),
                                            'cursor_col': cu.get('cursor_col', 0),
                                            'color_pair': self._get_user_color(uid)
                                        }
                                self.lock_holder = response.get('lock_holder')
                                self.connected_users = response.get('clients', [])
                                return True
                            elif response.get('type') == MSG_ERROR:
                                self.connection_error = response.get('message', 'Unknown error')
                                return False
                except BlockingIOError:
                    time.sleep(0.05)
                    continue
                except Exception as e:
                    self.connection_error = str(e)
                    return False

            self.connection_error = "Connection timed out"
            return False

        except Exception as e:
            self.connection_error = str(e)
            return False

    def _get_user_color(self, client_id):
        """Assign a color pair to a user for their cursor display."""
        if client_id not in self.user_colors:
            self.user_colors[client_id] = self.next_user_color
            self.next_user_color += 1
            if self.next_user_color > 15:
                self.next_user_color = COLOR_CURSOR_OTHER
        return self.user_colors[client_id]

    def run(self):
        """Main entry point. Initializes curses and runs the main loop."""
        if not self.connected:
            print(f"Connection error: {self.connection_error}")
            return

        try:
            curses.wrapper(self._run_curses)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()

    def _run_curses(self, screen):
        """Main curses loop."""
        self.screen = screen
        self.running = True

        # Setup curses
        curses.curs_set(0)  # Hide cursor (we draw our own)
        screen.nodelay(True)
        screen.keypad(True)

        # Initialize colors
        self._init_colors()

        # Main loop
        last_cursor_send = 0
        while self.running:
            try:
                # Check network
                self._process_network()

                # Check keyboard
                ch = screen.getch()
                if ch != -1:
                    self._handle_key(ch)
                    last_cursor_send = 0  # Force cursor update

                # Send cursor update periodically
                if time.time() - last_cursor_send > 0.2:
                    self._send_cursor_update()
                    last_cursor_send = time.time()

                # Render
                self._render()

                # Small sleep
                time.sleep(0.02)

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.status_message = f"Error: {e}"
                self.status_message_time = time.time()

        # Cleanup
        self.sock.close()

    def _init_colors(self):
        """Initialize color pairs for curses."""
        curses.start_color()
        curses.use_default_colors()

        # Color pair definitions
        curses.init_pair(COLOR_DEFAULT, curses.COLOR_WHITE, -1)
        curses.init_pair(COLOR_LINE_NUM, curses.COLOR_YELLOW, -1)
        curses.init_pair(COLOR_STATUS_BAR, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(COLOR_KEYWORD, curses.COLOR_BLUE, -1)
        curses.init_pair(COLOR_STRING, curses.COLOR_GREEN, -1)
        curses.init_pair(COLOR_COMMENT, curses.COLOR_MAGENTA, -1)
        curses.init_pair(COLOR_NUMBER, curses.COLOR_RED, -1)
        curses.init_pair(COLOR_SEARCH_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(COLOR_SIDEBAR, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(COLOR_MY_CURSOR, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(COLOR_PROMPT, curses.COLOR_YELLOW, -1)

        # User cursor colors (9-15)
        user_colors = [
            (curses.COLOR_RED, -1),
            (curses.COLOR_GREEN, -1),
            (curses.COLOR_YELLOW, -1),
            (curses.COLOR_BLUE, -1),
            (curses.COLOR_MAGENTA, -1),
            (curses.COLOR_CYAN, -1),
            (curses.COLOR_WHITE, -1),
        ]
        for i, (fg, bg) in enumerate(user_colors):
            curses.init_pair(COLOR_CURSOR_OTHER + i, fg, bg)

    def _process_network(self):
        """Read and process messages from the server."""
        try:
            data = self.sock.recv(4096)
            if not data:
                self.connected = False
                self.status_message = "Disconnected from server"
                self.status_message_time = time.time()
                return
            self.recv_buffer += data

            while b'\n' in self.recv_buffer:
                line, self.recv_buffer = self.recv_buffer.split(b'\n', 1)
                msg = decode_message(line.decode('utf-8'))
                self._handle_server_message(msg)

        except BlockingIOError:
            pass
        except Exception as e:
            self.status_message = f"Network error: {e}"
            self.status_message_time = time.time()

    def _handle_server_message(self, msg):
        """Process a message from the server."""
        msg_type = msg.get('type')

        if msg_type == MSG_OPERATION:
            self._handle_remote_operation(msg)

        elif msg_type == MSG_CURSOR_UPDATE:
            cid = msg.get('client_id')
            if cid and cid != self.client_id:
                if cid not in self.remote_users:
                    self.remote_users[cid] = {
                        'username': msg.get('username', 'unknown'),
                        'cursor_row': 0,
                        'cursor_col': 0,
                        'color_pair': self._get_user_color(cid)
                    }
                self.remote_users[cid]['cursor_row'] = msg.get('row', 0)
                self.remote_users[cid]['cursor_col'] = msg.get('col', 0)

        elif msg_type == MSG_LOCK_GRANT:
            self.i_hold_lock = True
            self.status_message = "Lock acquired! You now have exclusive edit access."
            self.status_message_time = time.time()

        elif msg_type == MSG_LOCK_STATUS:
            self.lock_holder = msg.get('holder')
            self.lock_queue = msg.get('queue', [])
            self.i_hold_lock = (self.lock_holder == self.client_id)
            if self.lock_holder and not self.i_hold_lock:
                holder_name = "unknown"
                for cu in self.connected_users:
                    if cu['client_id'] == self.lock_holder:
                        holder_name = cu['username']
                        break
                self.status_message = f"Document locked by {holder_name}"
                self.status_message_time = time.time()
            elif not self.lock_holder:
                self.status_message = "Document lock released"
                self.status_message_time = time.time()

        elif msg_type == MSG_SAVE_ACK:
            self.status_message = "Document saved to server"
            self.status_message_time = time.time()

        elif msg_type == MSG_USER_JOIN:
            cid = msg.get('client_id')
            username = msg.get('username')
            if cid and cid != self.client_id:
                self.remote_users[cid] = {
                    'username': username,
                    'cursor_row': msg.get('cursor_row', 0),
                    'cursor_col': msg.get('cursor_col', 0),
                    'color_pair': self._get_user_color(cid)
                }
                self.status_message = f"{username} joined the room"
                self.status_message_time = time.time()
                self._update_connected_users()

        elif msg_type == MSG_USER_LEAVE:
            cid = msg.get('client_id')
            username = msg.get('username')
            if cid in self.remote_users:
                del self.remote_users[cid]
            self.status_message = f"{username} left the room"
            self.status_message_time = time.time()
            self._update_connected_users()

        elif msg_type == MSG_ERROR:
            self.status_message = f"Server error: {msg.get('message', '')}"
            self.status_message_time = time.time()

    def _update_connected_users(self):
        """Rebuild the connected users list from remote_users + self."""
        self.connected_users = [
            {
                'client_id': cid,
                'username': info['username'],
                'cursor_row': info['cursor_row'],
                'cursor_col': info['cursor_col']
            }
            for cid, info in self.remote_users.items()
        ]
        # Add ourselves
        self.connected_users.append({
            'client_id': self.client_id,
            'username': self.username,
            'cursor_row': self.cursor_row,
            'cursor_col': self.cursor_col
        })

    def _handle_remote_operation(self, msg):
        """Handle an operation broadcast from the server."""
        ops = msg.get('ops', [])
        cid = msg.get('client_id')
        new_version = msg.get('version', self.version)

        if cid == self.client_id:
            # This is our own operation being confirmed
            if not ops:
                # Our operation became a no-op (someone else's op had the same effect).
                # Our local change is already correct, just clear one pending entry.
                if self.pending_ops:
                    self.pending_ops.pop(0)
            else:
                for op in ops:
                    if self.pending_ops:
                        pending_op, pending_inv = self.pending_ops.pop(0)
                        # If the confirmed op differs from what we applied, reconcile
                        if pending_op != op:
                            # Apply inverse of our optimistic change
                            self.document = apply_op(self.document, pending_inv)
                            # Apply server's confirmed version
                            self.document = apply_op(self.document, op)
                            # Adjust cursor for the reconciliation
                            self._adjust_cursor_for_op(op)
                        # If they match, cursor is already correct - no adjustment needed
                    else:
                        # No pending op to match - just apply the confirmed op
                        self.document = apply_op(self.document, op)
                        self._adjust_cursor_for_op(op)
        else:
            # Remote operation - transform against pending ops and apply
            for op in ops:
                # Transform against all pending ops (in order)
                transformed_op = op.copy()
                for pending_op, _ in self.pending_ops:
                    result = transform(pending_op, transformed_op)
                    if result is None:
                        transformed_op = None
                        break
                    transformed_op = result

                if transformed_op:
                    self.document = apply_op(self.document, transformed_op)
                    self._adjust_cursor_for_remote_op(transformed_op)
                    self._adjust_remote_cursors(transformed_op)
                # If transformed_op is None, the op has no effect on our view

        self.version = new_version
        self._update_connected_users()

    def _adjust_cursor_for_op(self, op):
        """Adjust own cursor position after applying an operation."""
        # Clamp cursor first to ensure it's valid
        self._clamp_cursor()
        pos = row_col_to_position(self.document, self.cursor_row, self.cursor_col)
        # Clamp pos to valid range
        pos = max(0, min(pos, len(self.document)))
        op_pos = op['pos']

        if op['op'] == 'insert':
            if op_pos <= pos:
                pos += 1
        elif op['op'] == 'delete':
            if op_pos < pos:
                pos -= 1
            elif op_pos == pos:
                pass  # Character at or after cursor was deleted

        pos = max(0, min(pos, len(self.document)))
        self.cursor_row, self.cursor_col = position_to_row_col(self.document, pos)
        self._clamp_cursor()

    def _adjust_cursor_for_remote_op(self, op):
        """Adjust own cursor position for a remote operation."""
        self._adjust_cursor_for_op(op)

    def _adjust_remote_cursors(self, op):
        """Adjust all remote user cursors for an operation."""
        for cid, info in self.remote_users.items():
            pos = row_col_to_position(self.document, info['cursor_row'], info['cursor_col'])
            pos = max(0, min(pos, len(self.document)))
            op_pos = op['pos']

            if op['op'] == 'insert':
                if op_pos <= pos:
                    pos += 1
            elif op['op'] == 'delete':
                if op_pos < pos:
                    pos -= 1
                elif op_pos == pos:
                    pass

            pos = max(0, min(pos, len(self.document)))
            info['cursor_row'], info['cursor_col'] = position_to_row_col(self.document, pos)

    def _clamp_cursor(self):
        """Ensure cursor is within document bounds."""
        lines = self.document.split('\n') if self.document else ['']
        if self.cursor_row >= len(lines):
            self.cursor_row = max(0, len(lines) - 1)
        if self.cursor_row < 0:
            self.cursor_row = 0
        max_col = len(lines[self.cursor_row]) if self.cursor_row < len(lines) else 0
        if self.cursor_col > max_col:
            self.cursor_col = max_col
        if self.cursor_col < 0:
            self.cursor_col = 0

    def _send_cursor_update(self):
        """Send current cursor position to server."""
        if self.connected and self.sock:
            msg = make_cursor_update(self.client_id, self.username, self.cursor_row, self.cursor_col)
            try:
                self.sock.send(encode_message(msg).encode('utf-8'))
            except Exception:
                pass

    def _reverse_transform_position(self, pos):
        """Transform a position in the local document to the corresponding
        position in the confirmed document (without pending ops applied)."""
        result = pos
        for pending_op, _ in reversed(self.pending_ops):
            if pending_op['op'] == 'insert':
                if pending_op['pos'] <= result:
                    result -= 1
            elif pending_op['op'] == 'delete':
                if pending_op['pos'] < result:
                    result += 1
        return result

    def _send_operation(self, ops):
        """Send an operation to the server.
        
        The ops should already have positions adjusted to be relative
        to the confirmed document state.
        """
        if not self.connected or not self.sock:
            return

        msg = make_operation(ops, self.version, self.client_id)
        try:
            self.sock.send(encode_message(msg).encode('utf-8'))
        except Exception as e:
            self.status_message = f"Send error: {e}"
            self.status_message_time = time.time()

    def _local_insert(self, char):
        """Perform a local insert with optimistic update."""
        if not self._can_edit():
            return

        pos = row_col_to_position(self.document, self.cursor_row, self.cursor_col)
        if pos < 0 or pos > len(self.document):
            return

        op = {'op': 'insert', 'pos': pos, 'char': char}
        inverse = invert_op(self.document, op)

        # Compute server-relative position BEFORE adding to pending
        server_pos = self._reverse_transform_position(pos)

        # Apply locally
        self.document = apply_op(self.document, op)
        self.pending_ops.append((op, inverse))

        # Update cursor
        if char == '\n':
            self.cursor_row += 1
            self.cursor_col = 0
        else:
            self.cursor_col += 1

        # Send to server with adjusted position
        server_op = {'op': 'insert', 'pos': server_pos, 'char': char}
        self._send_operation([server_op])

    def _local_delete(self, backspace=False):
        """Perform a local delete with optimistic update.
        backspace=True means delete character before cursor (Backspace).
        backspace=False means delete character at cursor (Delete).
        """
        if not self._can_edit():
            return

        pos = row_col_to_position(self.document, self.cursor_row, self.cursor_col)

        if backspace:
            if pos <= 0:
                return
            pos -= 1
        else:
            if pos >= len(self.document):
                return

        if pos < 0 or pos >= len(self.document):
            return

        op = {'op': 'delete', 'pos': pos}
        inverse = invert_op(self.document, op)

        if inverse is None:
            return

        # Compute server-relative position BEFORE adding to pending
        server_pos = self._reverse_transform_position(pos)

        # Apply locally
        self.document = apply_op(self.document, op)
        self.pending_ops.append((op, inverse))

        # Update cursor
        if backspace:
            self.cursor_row, self.cursor_col = position_to_row_col(self.document, pos)
        else:
            self.cursor_row, self.cursor_col = position_to_row_col(self.document, pos)

        # Send to server with adjusted position
        server_op = {'op': 'delete', 'pos': server_pos}
        self._send_operation([server_op])

    def _local_enter(self):
        """Handle Enter key - insert newline."""
        self._local_insert('\n')

    def _can_edit(self):
        """Check if we can edit (lock check)."""
        if self.lock_holder and self.lock_holder != self.client_id:
            self.status_message = "Document is locked. Press Ctrl+L to request lock."
            self.status_message_time = time.time()
            return False
        return True

    def _handle_key(self, ch):
        """Handle a keyboard input character."""
        # If in search mode, handle search input
        if self.search_mode:
            self._handle_search_key(ch)
            return

        # If in replace mode, handle replace input
        if self.replace_mode:
            self._handle_replace_key(ch)
            return

        # Ctrl key combinations (ASCII control characters)
        if ch == 6:  # Ctrl+F
            self._start_search()
            return
        elif ch == 8:  # Ctrl+H
            self._start_replace()
            return
        elif ch == 12:  # Ctrl+L
            self._toggle_lock()
            return
        elif ch == 19:  # Ctrl+S
            self._save_request()
            return
        elif ch == 26:  # Ctrl+Z
            self._undo_request()
            return

        # Special keys
        if ch == curses.KEY_UP:
            self._move_cursor(0, -1)
        elif ch == curses.KEY_DOWN:
            self._move_cursor(0, 1)
        elif ch == curses.KEY_LEFT:
            self._move_cursor(-1, 0)
        elif ch == curses.KEY_RIGHT:
            self._move_cursor(1, 0)
        elif ch == curses.KEY_HOME:
            self._move_cursor_to_col(0)
        elif ch == curses.KEY_END:
            lines = self.document.split('\n')
            if self.cursor_row < len(lines):
                self._move_cursor_to_col(len(lines[self.cursor_row]))
        elif ch == curses.KEY_PPAGE:  # Page Up
            self._move_cursor(0, -self._visible_rows())
        elif ch == curses.KEY_NPAGE:  # Page Down
            self._move_cursor(0, self._visible_rows())
        elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
            self._local_delete(backspace=True)
        elif ch == curses.KEY_DC:  # Delete
            self._local_delete(backspace=False)
        elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
            self._local_enter()
        elif ch == 27:  # ESC
            # Could be escape sequence for Ctrl+arrows
            self._handle_escape_sequence()
        elif ch == 9:  # Tab
            self._local_insert('\t')
        elif 32 <= ch <= 126:  # Printable ASCII
            self._local_insert(chr(ch))
        elif ch == 547 or ch == 546:  # Ctrl+Left (common codes)
            self._word_left()
        elif ch == 562 or ch == 561:  # Ctrl+Right (common codes)
            self._word_right()
        elif ch == curses.KEY_SLEFT:  # Shift+Left (some terminals use for Ctrl+Left)
            self._word_left()
        elif ch == curses.KEY_SRIGHT:  # Shift+Right (some terminals use for Ctrl+Right)
            self._word_right()

    def _handle_escape_sequence(self):
        """Handle escape sequences for Ctrl+arrows etc."""
        self.screen.nodelay(True)
        try:
            ch2 = self.screen.getch()
            if ch2 == ord('['):
                ch3 = self.screen.getch()
                if ch3 == ord('1'):
                    ch4 = self.screen.getch()
                    if ch4 == ord(';'):
                        ch5 = self.screen.getch()
                        if ch5 == ord('5'):
                            ch6 = self.screen.getch()
                            if ch6 == ord('D'):
                                self._word_left()
                            elif ch6 == ord('C'):
                                self._word_right()
        except Exception:
            pass
        self.screen.nodelay(True)

    def _move_cursor(self, dcol, drow):
        """Move cursor by delta col, delta row."""
        lines = self.document.split('\n')
        new_row = self.cursor_row + drow
        new_col = self.cursor_col + dcol

        # Clamp row
        if new_row < 0:
            new_row = 0
        if new_row >= len(lines):
            new_row = max(0, len(lines) - 1)

        # Clamp col
        if new_row < len(lines):
            max_col = len(lines[new_row])
            if new_col < 0:
                new_col = 0
            if new_col > max_col:
                new_col = max_col
        else:
            new_col = 0

        self.cursor_row = new_row
        self.cursor_col = new_col
        self._update_scroll()

    def _move_cursor_to_col(self, col):
        """Move cursor to a specific column on the current line."""
        lines = self.document.split('\n')
        if self.cursor_row < len(lines):
            max_col = len(lines[self.cursor_row])
            self.cursor_col = max(0, min(col, max_col))
        else:
            self.cursor_col = 0
        self._update_scroll()

    def _word_left(self):
        """Move cursor to start of current/previous word."""
        lines = self.document.split('\n')
        if self.cursor_row >= len(lines):
            return
        line = lines[self.cursor_row]

        # If at start of line, go to end of previous line
        if self.cursor_col == 0:
            if self.cursor_row > 0:
                self.cursor_row -= 1
                self.cursor_col = len(lines[self.cursor_row])
            self._update_scroll()
            return

        # Move left past whitespace
        col = self.cursor_col - 1
        while col > 0 and line[col].isspace():
            col -= 1
        # Move left to start of word
        while col > 0 and not line[col - 1].isspace():
            col -= 1
        self.cursor_col = col
        self._update_scroll()

    def _word_right(self):
        """Move cursor to end of current/next word."""
        lines = self.document.split('\n')
        if self.cursor_row >= len(lines):
            return
        line = lines[self.cursor_row]

        # If at end of line, go to start of next line
        if self.cursor_col >= len(line):
            if self.cursor_row < len(lines) - 1:
                self.cursor_row += 1
                self.cursor_col = 0
            self._update_scroll()
            return

        # Move right past current word
        col = self.cursor_col
        while col < len(line) and not line[col].isspace():
            col += 1
        # Move past whitespace
        while col < len(line) and line[col].isspace():
            col += 1
        self.cursor_col = col
        self._update_scroll()

    def _update_scroll(self):
        """Update scroll position to keep cursor visible."""
        max_rows, max_cols = self._visible_dims()

        # Vertical scroll
        if self.cursor_row < self.scroll_row:
            self.scroll_row = self.cursor_row
        elif self.cursor_row >= self.scroll_row + max_rows:
            self.scroll_row = self.cursor_row - max_rows + 1

        # Horizontal scroll
        if self.cursor_col < self.scroll_col:
            self.scroll_col = self.cursor_col
        elif self.cursor_col >= self.scroll_col + max_cols:
            self.scroll_col = self.cursor_col - max_cols + 1

        if self.scroll_row < 0:
            self.scroll_row = 0
        if self.scroll_col < 0:
            self.scroll_col = 0

    def _visible_rows(self):
        """Return the number of visible document rows."""
        h, w = self.screen.getmaxyx()
        return max(1, h - 2)  # Subtract status bar and search bar if any

    def _visible_dims(self):
        """Return (visible_rows, visible_cols) for the document area."""
        h, w = self.screen.getmaxyx()
        sidebar_width = 20
        line_num_width = 6
        visible_rows = max(1, h - 2)  # status bar at bottom, possible search bar
        visible_cols = max(10, w - line_num_width - sidebar_width - 1)
        return visible_rows, visible_cols

    # === Search functionality ===

    def _start_search(self):
        """Enter search mode."""
        self.search_mode = True
        self.search_query = ""
        self.search_matches = []
        self.search_current_match = -1
        self.status_message = "Search: "
        self.status_message_time = time.time()

    def _handle_search_key(self, ch):
        """Handle keypress in search mode."""
        if ch == 27:  # ESC - cancel search
            self.search_mode = False
            self.search_query = ""
            self.search_matches = []
            self.search_current_match = -1
            self.status_message = ""
        elif ch == 10 or ch == 13:  # Enter - next match
            if self.search_matches:
                self.search_current_match = (self.search_current_match + 1) % len(self.search_matches)
                self._goto_match()
        elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
            if self.search_query:
                self.search_query = self.search_query[:-1]
                self._update_search_matches()
        elif ch == 6:  # Ctrl+F again - also next match
            if self.search_matches:
                self.search_current_match = (self.search_current_match + 1) % len(self.search_matches)
                self._goto_match()
        elif 32 <= ch <= 126:
            self.search_query += chr(ch)
            self._update_search_matches()
        elif ch == 353:  # Shift+Enter (some terminals)
            if self.search_matches:
                self.search_current_match = (self.search_current_match - 1) % len(self.search_matches)
                self._goto_match()

    def _update_search_matches(self):
        """Find all matches for the current search query."""
        self.search_matches = []
        self.search_current_match = -1
        if not self.search_query:
            return
        query_lower = self.search_query.lower()
        doc_lower = self.document.lower()
        start = 0
        while True:
            idx = doc_lower.find(query_lower, start)
            if idx == -1:
                break
            self.search_matches.append(idx)
            start = idx + 1
        if self.search_matches:
            self.search_current_match = 0
            self._goto_match()

    def _goto_match(self):
        """Move cursor to the current search match."""
        if 0 <= self.search_current_match < len(self.search_matches):
            pos = self.search_matches[self.search_current_match]
            self.cursor_row, self.cursor_col = position_to_row_col(self.document, pos)
            self._update_scroll()

    # === Replace functionality ===

    def _start_replace(self):
        """Enter find and replace mode."""
        self.replace_mode = True
        self.replace_step = 0
        self.replace_query = ""
        self.replace_with = ""
        self.status_message = "Find: "
        self.status_message_time = time.time()

    def _handle_replace_key(self, ch):
        """Handle keypress in replace mode."""
        if ch == 27:  # ESC - cancel
            self.replace_mode = False
            self.replace_step = 0
            self.replace_query = ""
            self.replace_with = ""
            self.status_message = "Replace cancelled"
            self.status_message_time = time.time()
            return

        if self.replace_step == 0:
            # Entering search query
            if ch == 10 or ch == 13:  # Enter
                if self.replace_query:
                    self.replace_step = 1
                    self.status_message = "Replace with: "
            elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
                if self.replace_query:
                    self.replace_query = self.replace_query[:-1]
            elif 32 <= ch <= 126:
                self.replace_query += chr(ch)

        elif self.replace_step == 1:
            # Entering replacement text
            if ch == 10 or ch == 13:  # Enter
                if self.replace_with or True:  # Allow empty replacement
                    self.replace_step = 2
                    self._find_replace_matches()
            elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
                if self.replace_with:
                    self.replace_with = self.replace_with[:-1]
            elif 32 <= ch <= 126:
                self.replace_with += chr(ch)

        elif self.replace_step == 2:
            # Confirm each replacement
            if ch == ord('y') or ch == ord('Y'):
                self._do_replace_current()
            elif ch == ord('n') or ch == ord('N'):
                self._skip_replace_current()
            elif ch == ord('a') or ch == ord('A'):
                self._replace_all()
            elif ch == ord('q') or ch == ord('Q'):
                self.replace_mode = False
                self.replace_step = 0
                self.status_message = "Replace done"
                self.status_message_time = time.time()

    def _find_replace_matches(self):
        """Find all matches for replace."""
        self.search_matches = []
        self.search_current_match = -1
        if not self.replace_query:
            self.replace_mode = False
            self.replace_step = 0
            return
        query_lower = self.replace_query.lower()
        doc_lower = self.document.lower()
        start = 0
        while True:
            idx = doc_lower.find(query_lower, start)
            if idx == -1:
                break
            self.search_matches.append(idx)
            start = idx + 1
        if self.search_matches:
            self.search_current_match = 0
            self._goto_match()
            self.status_message = f"Replace? (y/n/a/q): {self.replace_query} -> {self.replace_with}"
            self.status_message_time = time.time()
        else:
            self.replace_mode = False
            self.replace_step = 0
            self.status_message = "No matches found"
            self.status_message_time = time.time()

    def _do_replace_current(self):
        """Replace the current match."""
        if 0 <= self.search_current_match < len(self.search_matches):
            pos = self.search_matches[self.search_current_match]
            # Delete the matched text - send operations with correct server-relative positions
            for _ in range(len(self.replace_query)):
                server_pos = self._reverse_transform_position(pos)
                op = {'op': 'delete', 'pos': pos}
                inverse = invert_op(self.document, op)
                if inverse:
                    self.document = apply_op(self.document, op)
                    self.pending_ops.append((op, inverse))
                    server_op = {'op': 'delete', 'pos': server_pos}
                    self._send_operation([server_op])

            # Insert replacement text
            for i, char in enumerate(self.replace_with):
                server_pos = self._reverse_transform_position(pos + i)
                op = {'op': 'insert', 'pos': pos + i, 'char': char}
                inverse = invert_op(self.document, op)
                self.document = apply_op(self.document, op)
                self.pending_ops.append((op, inverse))
                server_op = {'op': 'insert', 'pos': server_pos, 'char': char}
                self._send_operation([server_op])

            # Update match positions
            self._update_search_matches()
            self.status_message = f"Replace? (y/n/a/q): {self.replace_query} -> {self.replace_with}"
            self.status_message_time = time.time()

    def _skip_replace_current(self):
        """Skip current match and go to next."""
        if self.search_matches:
            self.search_current_match = (self.search_current_match + 1) % len(self.search_matches)
            self._goto_match()
            self.status_message = f"Replace? (y/n/a/q): {self.replace_query} -> {self.replace_with}"
            self.status_message_time = time.time()

    def _replace_all(self):
        """Replace all remaining matches."""
        while self.search_matches:
            self._do_replace_current()
            if not self.search_matches:
                break
            self.search_current_match = 0
        self.replace_mode = False
        self.replace_step = 0
        self.status_message = "All replaced"
        self.status_message_time = time.time()

    # === Lock functionality ===

    def _toggle_lock(self):
        """Request or release edit lock."""
        if self.i_hold_lock:
            # Release lock
            msg = make_lock_release(self.client_id)
            try:
                self.sock.send(encode_message(msg).encode('utf-8'))
            except Exception:
                pass
            self.i_hold_lock = False
        else:
            # Request lock
            msg = make_lock_request(self.client_id)
            try:
                self.sock.send(encode_message(msg).encode('utf-8'))
            except Exception:
                pass
            self.status_message = "Lock requested..."
            self.status_message_time = time.time()

    # === Save functionality ===

    def _save_request(self):
        """Send save request to server."""
        msg = make_save_request(self.client_id)
        try:
            self.sock.send(encode_message(msg).encode('utf-8'))
        except Exception:
            pass
        self.status_message = "Save requested..."
        self.status_message_time = time.time()

    # === Undo functionality ===

    def _undo_request(self):
        """Send undo request to server."""
        msg = make_undo(self.client_id)
        try:
            self.sock.send(encode_message(msg).encode('utf-8'))
        except Exception:
            pass
        self.status_message = "Undo requested..."
        self.status_message_time = time.time()

    # === Rendering ===

    def _render(self):
        """Render the full TUI."""
        if not self.screen:
            return

        self.screen.erase()
        h, w = self.screen.getmaxyx()

        if h < 5 or w < 40:
            self.screen.addstr(0, 0, "Terminal too small")
            self.screen.refresh()
            return

        # Layout:
        # - Line numbers: columns 0-5 (6 chars wide)
        # - Document: columns 6 to w-21
        # - Sidebar: columns w-20 to w-1 (20 chars wide)
        # - Status bar: bottom row
        # - Search bar: second from bottom (if active)

        line_num_width = 6
        sidebar_width = 20
        doc_left = line_num_width
        doc_width = max(10, w - line_num_width - sidebar_width - 1)
        sidebar_left = w - sidebar_width

        # Render document with line numbers
        self._render_document(doc_left, doc_width, line_num_width)

        # Render other users' cursors
        self._render_remote_cursors(doc_left, doc_width, line_num_width)

        # Render sidebar
        self._render_sidebar(sidebar_left, sidebar_width, h)

        # Render status bar
        self._render_status_bar(h, w)

        # Render search bar if active
        if self.search_mode:
            self._render_search_bar(h, w)

        # Render replace prompt if active
        if self.replace_mode:
            self._render_replace_bar(h, w)

        self.screen.refresh()

    def _render_document(self, doc_left, doc_width, line_num_width):
        """Render the document text with line numbers and syntax highlighting."""
        h, w = self.screen.getmaxyx()
        max_rows = max(1, h - 2)
        if self.search_mode or self.replace_mode:
            max_rows = max(1, h - 3)

        lines = self.document.split('\n')
        is_python = self.filename.endswith('.py')

        for i in range(max_rows):
            doc_row = self.scroll_row + i
            screen_row = i

            if doc_row >= len(lines):
                # Draw empty line with line number
                line_num = str(doc_row + 1)
                attr = curses.color_pair(COLOR_LINE_NUM)
                self.screen.addstr(screen_row, 0, line_num.rjust(line_num_width - 1) + ' ', attr)
                continue

            line_text = lines[doc_row]
            # Truncate for horizontal scrolling
            if self.scroll_col > 0 and self.scroll_col < len(line_text):
                display_text = line_text[self.scroll_col:self.scroll_col + doc_width]
            elif self.scroll_col >= len(line_text):
                display_text = ""
            else:
                display_text = line_text[self.scroll_col:self.scroll_col + doc_width]

            # Draw line number
            line_num = str(doc_row + 1)
            attr = curses.color_pair(COLOR_LINE_NUM)
            try:
                self.screen.addstr(screen_row, 0, line_num.rjust(line_num_width - 1) + ' ', attr)
            except curses.error:
                pass

            # Draw line content with optional syntax highlighting
            if is_python:
                self._render_syntax_line(screen_row, doc_left, display_text, doc_width)
            else:
                try:
                    self.screen.addstr(screen_row, doc_left, display_text[:doc_width])
                except curses.error:
                    pass

            # If we're on the cursor line, highlight the cursor column
            if doc_row == self.cursor_row:
                cursor_visible_col = self.cursor_col - self.scroll_col
                if 0 <= cursor_visible_col < doc_width:
                    if cursor_visible_col < len(display_text):
                        char = display_text[cursor_visible_col]
                    else:
                        char = ' '
                    try:
                        self.screen.addstr(screen_row, doc_left + cursor_visible_col, char,
                                          curses.color_pair(COLOR_MY_CURSOR))
                    except curses.error:
                        pass

    def _render_syntax_line(self, screen_row, doc_left, text, max_width):
        """Render a line with Python syntax highlighting."""
        if not text:
            return

        i = 0
        while i < len(text) and i < max_width:
            remaining = text[i:]

            # Check for comment
            if remaining.startswith('#'):
                try:
                    self.screen.addstr(screen_row, doc_left + i, remaining[:max_width - i],
                                      curses.color_pair(COLOR_COMMENT))
                except curses.error:
                    pass
                break

            # Check for string (simple detection)
            if remaining[0] in ('"', "'"):
                quote = remaining[0]
                # Check for triple quote
                if remaining.startswith(quote * 3):
                    end_idx = text.find(quote * 3, i + 3)
                    if end_idx == -1:
                        end_idx = len(text)
                    else:
                        end_idx += 3
                    try:
                        self.screen.addstr(screen_row, doc_left + i, text[i:min(end_idx, i + max_width)],
                                          curses.color_pair(COLOR_STRING))
                    except curses.error:
                        pass
                    i = end_idx
                    continue
                else:
                    end_idx = text.find(quote, i + 1)
                    # Handle escaped quotes
                    while end_idx != -1 and end_idx > 0 and text[end_idx - 1] == '\\':
                        end_idx = text.find(quote, end_idx + 1)
                    if end_idx == -1:
                        end_idx = len(text)
                    else:
                        end_idx += 1
                    try:
                        self.screen.addstr(screen_row, doc_left + i, text[i:min(end_idx, i + max_width)],
                                          curses.color_pair(COLOR_STRING))
                    except curses.error:
                        pass
                    i = end_idx
                    continue

            # Check for number
            if remaining[0].isdigit():
                j = i
                while j < len(text) and j - i < max_width and (text[j].isdigit() or text[j] == '.'):
                    j += 1
                if j > i:
                    try:
                        self.screen.addstr(screen_row, doc_left + i, text[i:min(j, i + max_width)],
                                          curses.color_pair(COLOR_NUMBER))
                    except curses.error:
                        pass
                    i = j
                    continue

            # Check for keyword/identifier
            if remaining[0].isalpha() or remaining[0] == '_':
                j = i
                while j < len(text) and j - i < max_width and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                word = text[i:j]
                if word in PYTHON_KEYWORDS:
                    attr = curses.color_pair(COLOR_KEYWORD)
                else:
                    attr = curses.color_pair(COLOR_DEFAULT)
                try:
                    self.screen.addstr(screen_row, doc_left + i, word, attr)
                except curses.error:
                    pass
                i = j
                continue

            # Default character
            try:
                self.screen.addstr(screen_row, doc_left + i, text[i], curses.color_pair(COLOR_DEFAULT))
            except curses.error:
                pass
            i += 1

    def _render_remote_cursors(self, doc_left, doc_width, line_num_width):
        """Render other users' cursor indicators."""
        h, w = self.screen.getmaxyx()
        max_rows = max(1, h - 2)
        if self.search_mode or self.replace_mode:
            max_rows = max(1, h - 3)

        for cid, info in self.remote_users.items():
            row = info['cursor_row']
            col = info['cursor_col']
            username = info['username']
            color_pair = info['color_pair']

            # Check if cursor is visible
            screen_row = row - self.scroll_row
            screen_col = col - self.scroll_col

            if 0 <= screen_row < max_rows and 0 <= screen_col < doc_width:
                # Draw username above cursor if there's room
                if screen_row > 0:
                    name_start = doc_left + screen_col - len(username) // 2
                    name_start = max(doc_left, min(name_start, doc_left + doc_width - len(username)))
                    try:
                        self.screen.addstr(screen_row - 1, name_start, username[:doc_width],
                                          curses.color_pair(color_pair) | curses.A_BOLD)
                    except curses.error:
                        pass

                # Highlight the cursor column
                lines = self.document.split('\n')
                if row < len(lines) and col < len(lines[row]):
                    char = lines[row][col]
                else:
                    char = ' '
                try:
                    self.screen.addstr(screen_row, doc_left + screen_col, char,
                                      curses.color_pair(color_pair) | curses.A_REVERSE)
                except curses.error:
                    pass

    def _render_sidebar(self, sidebar_left, sidebar_width, h):
        """Render the connected users sidebar."""
        # Draw sidebar border
        try:
            for i in range(h - 1):
                self.screen.addstr(i, sidebar_left - 1, '│', curses.color_pair(COLOR_SIDEBAR))
        except curses.error:
            pass

        # Draw header
        try:
            self.screen.addstr(0, sidebar_left, " Users ".center(sidebar_width),
                              curses.color_pair(COLOR_STATUS_BAR) | curses.A_BOLD)
        except curses.error:
            pass

        # Draw user list
        all_users = list(self.remote_users.values())
        # Add self
        all_users.append({
            'username': self.username + ' (you)',
            'cursor_row': self.cursor_row,
            'cursor_col': self.cursor_col
        })

        for i, user in enumerate(all_users):
            screen_row = i + 1
            if screen_row >= h - 1:
                break
            username = user['username'][:sidebar_width - 8]
            row_str = f"L:{user['cursor_row'] + 1}"
            line = f" {username} {row_str}"
            try:
                self.screen.addstr(screen_row, sidebar_left, line[:sidebar_width],
                                  curses.color_pair(COLOR_SIDEBAR))
            except curses.error:
                pass

        # Draw lock status
        lock_row = min(len(all_users) + 2, h - 2)
        if self.lock_holder:
            holder_name = "unknown"
            for cu in self.connected_users:
                if cu['client_id'] == self.lock_holder:
                    holder_name = cu['username']
                    break
            lock_text = f" 🔒 {holder_name}"
            try:
                self.screen.addstr(lock_row, sidebar_left, lock_text[:sidebar_width],
                                  curses.color_pair(COLOR_SIDEBAR))
            except curses.error:
                pass
        elif self.lock_queue:
            lock_text = f" ⏳ Queue: {len(self.lock_queue)}"
            try:
                self.screen.addstr(lock_row, sidebar_left, lock_text[:sidebar_width],
                                  curses.color_pair(COLOR_SIDEBAR))
            except curses.error:
                pass

    def _render_status_bar(self, h, w):
        """Render the status bar at the bottom."""
        # Build status bar content
        connected_count = len(self.remote_users) + 1  # +1 for self
        status = "Connected" if self.connected else "Disconnected"
        lock_status = " 🔒" if self.i_hold_lock else (" 🔓" if self.lock_holder else "")
        line_info = f"Ln {self.cursor_row + 1}, Col {self.cursor_col + 1}"
        file_info = self.filename

        left = f" {file_info} | {connected_count} users | {status}{lock_status} "
        right = f" {line_info} "

        # Fill middle with spaces
        middle = " " * max(0, w - len(left) - len(right))

        status_text = left + middle + right

        try:
            self.screen.addstr(h - 1, 0, status_text[:w], curses.color_pair(COLOR_STATUS_BAR))
        except curses.error:
            pass

        # Show temporary status message if any
        if self.status_message and time.time() - self.status_message_time < 5:
            try:
                msg = self.status_message[:w - 2]
                self.screen.addstr(h - 2, 1, msg, curses.color_pair(COLOR_PROMPT))
            except curses.error:
                pass

    def _render_search_bar(self, h, w):
        """Render the search bar."""
        search_row = h - 2
        prompt = f"Search: {self.search_query}"
        if self.search_matches:
            prompt += f" ({self.search_current_match + 1}/{len(self.search_matches)} matches)"
        prompt += " [Enter=next, Shift+Enter=prev, Esc=cancel]"
        try:
            self.screen.addstr(search_row, 0, prompt[:w], curses.color_pair(COLOR_PROMPT))
        except curses.error:
            pass

        # Highlight matches in document
        if self.search_query and self.search_matches:
            query_len = len(self.search_query)
            h, w = self.screen.getmaxyx()
            max_rows = max(1, h - 3)
            line_num_width = 6
            doc_left = line_num_width

            for match_pos in self.search_matches:
                row, col = position_to_row_col(self.document, match_pos)
                screen_row = row - self.scroll_row
                screen_col = col - self.scroll_col
                if 0 <= screen_row < max_rows and 0 <= screen_col:
                    # Highlight each character of the match that's visible
                    doc_width_line = w - doc_left - 20 - 1
                    for ci in range(query_len):
                        sc = screen_col + ci
                        if 0 <= sc < doc_width_line:
                            try:
                                # We redraw over the existing character with highlight
                                pass  # The match highlighting is complex to do inline; skip for now
                            except curses.error:
                                pass

    def _render_replace_bar(self, h, w):
        """Render the replace prompt bar."""
        if self.replace_step == 0:
            prompt = f"Find: {self.replace_query}"
        elif self.replace_step == 1:
            prompt = f"Replace with: {self.replace_with}"
        else:
            prompt = f"Replace? (y/n/a/q): {self.replace_query} -> {self.replace_with}"
        try:
            self.screen.addstr(h - 2, 0, prompt[:w], curses.color_pair(COLOR_PROMPT))
        except curses.error:
            pass


def main():
    parser = argparse.ArgumentParser(description='Collaborative Text Editor Client')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=9999, help='Server port')
    parser.add_argument('--user', required=True, help='Username')
    parser.add_argument('--room', default='default', help='Room name')
    parser.add_argument('--password', default='', help='Room password')
    parser.add_argument('--file', default=None, help='Filename (for syntax highlighting)')
    args = parser.parse_args()

    client = EditorClient(
        host=args.host,
        port=args.port,
        username=args.user,
        room=args.room,
        password=args.password,
        filename=args.file
    )

    if client.connect():
        client.run()
    else:
        print(f"Failed to connect: {client.connection_error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
