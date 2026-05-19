#!/usr/bin/env python3
"""
client.py — Curses TUI client for the collaborative text editor.

Usage:
    python client.py --host localhost --port 9000 --user Alice --room general
                     [--password letmein] [--file display_name.py]
"""

import argparse
import copy
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import traceback
from typing import Optional, Dict, List, Tuple, Set

import protocol as proto
import ot


# ── Syntax Highlighting ────────────────────────────────────────────────────

# Python keywords
PY_KEYWORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield', 'self',
}

# Curses color pair IDs (these will be initialized later)
# We use 1-based indexing; 0 is default
COLOR_DEFAULT = 0
COLOR_KEYWORD = 1
COLOR_STRING = 2
COLOR_COMMENT = 3
COLOR_NUMBER = 4
COLOR_CURSOR = 5
COLOR_CURSOR_REMOTE_BASE = 6  # 6..15 for remote users
COLOR_STATUS = 16
COLOR_SIDEBAR = 17
COLOR_SEARCH_HIGHLIGHT = 18
COLOR_LINE_NUMBER = 19
COLOR_MATCH_HIGHLIGHT = 20

MAX_REMOTE_USERS = 10
REMOTE_COLORS = [COLOR_CURSOR_REMOTE_BASE + i for i in range(MAX_REMOTE_USERS)]


def tokenize_line(line: str, in_string: int = 0) -> Tuple[List[Tuple[int, int, int]], int]:
    """
    Tokenize a single line for syntax highlighting.
    Returns (tokens, new_in_string_state).
    in_string: 0=none, 1=single-quoted, 2=double-quoted, 3=triple-single, 4=triple-double
    tokens: list of (start, end, color_pair_id)
    """
    tokens = []
    pos = 0
    n = len(line)

    if in_string in (1, 2, 3, 4):
        # We're inside a string; look for the end
        if in_string == 1:
            end_match = re.search(r"(?<!\\)'", line)
            if end_match:
                end_pos = end_match.end()
                tokens.append((0, end_pos, COLOR_STRING))
                pos = end_pos
                in_string = 0
            else:
                tokens.append((0, n, COLOR_STRING))
                return tokens, in_string
        elif in_string == 2:
            end_match = re.search(r'(?<!\\)"', line)
            if end_match:
                end_pos = end_match.end()
                tokens.append((0, end_pos, COLOR_STRING))
                pos = end_pos
                in_string = 0
            else:
                tokens.append((0, n, COLOR_STRING))
                return tokens, in_string
        elif in_string == 3:
            end_match = re.search(r"'''", line)
            if end_match:
                end_pos = end_match.end()
                tokens.append((0, end_pos, COLOR_STRING))
                pos = end_pos
                in_string = 0
            else:
                tokens.append((0, n, COLOR_STRING))
                return tokens, in_string
        elif in_string == 4:
            end_match = re.search(r'"""', line)
            if end_match:
                end_pos = end_match.end()
                tokens.append((0, end_pos, COLOR_STRING))
                pos = end_pos
                in_string = 0
            else:
                tokens.append((0, n, COLOR_STRING))
                return tokens, in_string

    while pos < n:
        # Check for comments
        if line[pos] == '#':
            tokens.append((pos, n, COLOR_COMMENT))
            break

        # Check for triple-quoted strings
        if pos + 2 < n and line[pos:pos+3] == '"""':
            end_match = re.search(r'"""', line[pos+3:])
            if end_match:
                end_pos = pos + 3 + end_match.end()
                tokens.append((pos, end_pos, COLOR_STRING))
                pos = end_pos
                continue
            else:
                tokens.append((pos, n, COLOR_STRING))
                return tokens, 4
        if pos + 2 < n and line[pos:pos+3] == "'''":
            end_match = re.search(r"'''", line[pos+3:])
            if end_match:
                end_pos = pos + 3 + end_match.end()
                tokens.append((pos, end_pos, COLOR_STRING))
                pos = end_pos
                continue
            else:
                tokens.append((pos, n, COLOR_STRING))
                return tokens, 3

        # Check for single/double quoted strings
        if line[pos] in '"\'':
            quote = line[pos]
            # Find matching quote
            pattern = re.compile(r"(?<!\\)" + re.escape(quote))
            m = pattern.search(line, pos + 1)
            if m:
                end_pos = m.end()
                tokens.append((pos, end_pos, COLOR_STRING))
                pos = end_pos
                continue
            else:
                # String continues to next line
                tokens.append((pos, n, COLOR_STRING))
                return tokens, 1 if quote == "'" else 2

        # Check for numbers
        num_match = re.match(r'\b\d+\.?\d*\b', line[pos:])
        if num_match:
            end_pos = pos + num_match.end()
            tokens.append((pos, end_pos, COLOR_NUMBER))
            pos = end_pos
            continue

        # Check for keywords / identifiers
        word_match = re.match(r'\b[a-zA-Z_]\w*\b', line[pos:])
        if word_match:
            word = word_match.group()
            end_pos = pos + word_match.end()
            if word in PY_KEYWORDS:
                tokens.append((pos, end_pos, COLOR_KEYWORD))
            pos = end_pos
            continue

        # Skip other characters (operators, etc.)
        pos += 1

    return tokens, in_string


# ── Client Model ───────────────────────────────────────────────────────────

class PendingOp:
    """Tracks a locally submitted operation that hasn't been acked yet."""
    __slots__ = ('original', 'seq_no', 'base_version')
    def __init__(self, original_op: ot.OTMessage, seq_no: int, base_version: int):
        self.original = original_op
        self.seq_no = seq_no
        self.base_version = base_version


class ClientModel:
    def __init__(self):
        self.document: str = ""
        self.local_version: int = 0
        self.pending_ops: List[PendingOp] = []
        self.remote_cursors: Dict[str, Tuple[int, int, int]] = {}  # username -> (line, col, offset)
        self.lock_holder: Optional[str] = None
        self.lock_queue: List[str] = []
        self.connected_users: List[str] = []
        self.client_id: str = ""
        self.username: str = ""
        self._seq_counter: int = 0

        # Cursor
        self.cursor_offset: int = 0  # offset in flat document

    def next_seq(self) -> int:
        self._seq_counter += 1
        return self._seq_counter

    def apply_local_op(self, op: ot.OTMessage) -> PendingOp:
        """Apply op locally and track as pending."""
        self.document = ot.apply_operation(self.document, op)
        seq = self.next_seq()
        base_ver = self.local_version
        po = PendingOp(original=copy.deepcopy(op), seq_no=seq, base_version=base_ver)
        self.pending_ops.append(po)
        # Adjust cursor if needed
        return po

    def apply_remote_op(self, op: ot.OTMessage):
        """Transform remote op against pending ops, then apply."""
        transformed = copy.deepcopy(op)
        for po in self.pending_ops:
            transformed = ot.transform(transformed, po.original)
        self.document = ot.apply_operation(self.document, transformed)
        return transformed

    def handle_ack(self, ack: proto.OperationAck):
        """
        Process server acknowledgement for a local operation.
        The ack contains the transformed operation as applied by server.
        We need to:
        1. Find the matching pending op by seq_no
        2. Compute the difference between original and acked op
        3. Transform all subsequent pending ops by that difference
        4. Remove the acked pending op
        5. Update local_version
        """
        seq_no = ack.seq_no
        if seq_no < 0:  # undo ack, just update version
            self.local_version = ack.new_version
            return

        # Find the pending op
        idx = None
        for i, po in enumerate(self.pending_ops):
            if po.seq_no == seq_no:
                idx = i
                break

        if idx is None:
            # Might have been already removed; just update version
            self.local_version = max(self.local_version, ack.new_version)
            return

        po = self.pending_ops[idx]
        acked_op = ot.OTMessage(
            op_type=ack.op_type,
            position=ack.position,
            text=ack.text,
            length=ack.length,
            client_id=self.client_id,
            seq_no=seq_no,
        )

        # Compute the "delta" — the difference between original and acked.
        # Since OT transform is what maps original to acked (original 
        # transformed against concurrent ops = acked), we apply the inverse
        # of original and then apply acked to align subsequent pending ops.

        # For subsequent pending ops, transform them against the difference:
        # We can do: transform(pending_op, inverse(original)) then transform(result, acked)
        # Or simpler: remove original's effect and apply acked's effect.
        # But we can't easily invert on the current document state.
        # 
        # Alternative approach: transform the remaining pending ops
        # against the "correction" - the combined effect of removing original
        # and applying acked.
        #
        # Since we already applied the original op to the document optimistically,
        # and the server applied acked instead, we need to update the document.
        # The document currently has original applied.
        # We need to remove original and apply acked.
        
        # Remove original from document
        inv_original = ot.inverse(po.original, self._doc_before_pending(idx))
        self.document = ot.apply_operation(self.document, inv_original)
        # Apply acked
        self.document = ot.apply_operation(self.document, acked_op)

        # Transform subsequent pending ops
        for j in range(idx + 1, len(self.pending_ops)):
            later_po = self.pending_ops[j]
            # Transform later_po.original against inv_original then acked
            t1 = ot.transform(later_po.original, inv_original)
            t2 = ot.transform(t1, acked_op)
            # Also need to update the document? No, pending ops are already on document.
            # But we changed document by swapping original→acked. So we need to also
            # re-apply subsequent pending ops? This gets messy.
            
            # Actually, let's just keep it simpler: transform the pending op's original
            # against the combined correction.
            # The correction is: first inverse(original), then acked.
            # For a subsequent pending op p, we compute:
            #   p' = transform(transform(p, inv_original), acked)
            later_po.original = t2

        # Remove the acked pending op
        self.pending_ops.pop(idx)
        self.local_version = max(self.local_version, ack.new_version)

    def _doc_before_pending(self, idx: int) -> str:
        """Reconstruct document state before the idx-th pending op was applied."""
        doc = self.document
        # Remove effects of pending ops from idx backwards
        for i in range(len(self.pending_ops) - 1, idx - 1, -1):
            po = self.pending_ops[i]
            inv = ot.inverse(po.original, doc)
            doc = ot.apply_operation(doc, inv)
        return doc

    def get_cursor_line_col(self) -> Tuple[int, int]:
        return ot.offset_to_line_col(self.document, self.cursor_offset)

    def set_cursor_line_col(self, line: int, col: int):
        self.cursor_offset = ot.line_col_to_offset(self.document, line, col)

    def get_lock_status(self) -> str:
        """Return 'held', 'queued', or 'none'."""
        if self.lock_holder == self.username:
            return 'held'
        if self.username in self.lock_queue:
            return 'queued'
        if self.lock_holder:
            return 'locked_by_other'
        return 'none'


# ── Network Thread ─────────────────────────────────────────────────────────

class NetworkThread(threading.Thread):
    def __init__(self, host: str, port: int, username: str, room: str,
                 password: str, incoming_queue: queue.Queue,
                 outgoing_queue: queue.Queue, model: ClientModel):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.username = username
        self.room = room
        self.password = password
        self.incoming = incoming_queue  # messages from server → main thread
        self.outgoing = outgoing_queue  # messages from main thread → server
        self.model = model
        self._running = True
        self._connected = False
        self.sock: Optional[socket.socket] = None
        self._buffer = b""

    def run(self):
        while self._running:
            try:
                self._connect_and_loop()
            except Exception as e:
                traceback.print_exc()
                self.incoming.put(('error', f"Connection error: {e}"))
                self.incoming.put(('disconnected', None))
                self._connected = False
                # Exponential backoff
                time.sleep(2)
                if not self._running:
                    break

    def _connect_and_loop(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(None)

        # Send connect
        connect_msg = proto.Connect(
            username=self.username,
            room=self.room,
            password=self.password,
        )
        self._send_raw(proto.encode(connect_msg))
        self._connected = True

        # Read loop
        self._buffer = b""
        while self._running and self._connected:
            # Check outgoing queue
            try:
                while True:
                    msg = self.outgoing.get_nowait()
                    if msg is None:  # shutdown signal
                        self._running = False
                        return
                    self._send_raw(proto.encode(msg))
            except queue.Empty:
                pass

            # Read from socket
            try:
                self.sock.settimeout(0.1)
                data = self.sock.recv(65536)
                if not data:
                    raise ConnectionError("Server closed connection")
                self._buffer += data
                self._process_buffer()
            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                raise ConnectionError(str(e))

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _send_raw(self, data: bytes):
        if self.sock and self._connected:
            try:
                self.sock.sendall(data)
            except Exception as e:
                self._connected = False
                raise ConnectionError(str(e))

    def _process_buffer(self):
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                msg = proto.decode(line.decode('utf-8').strip())
                self.incoming.put(('message', msg))
            except Exception as e:
                self.incoming.put(('error', f"Decode error: {e}"))

    def stop(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


# ── Curses UI ──────────────────────────────────────────────────────────────

class CursesUI:
    def __init__(self, model: ClientModel, incoming_queue: queue.Queue,
                 outgoing_queue: queue.Queue, display_filename: str,
                 is_python: bool):
        self.model = model
        self.incoming = incoming_queue
        self.outgoing = outgoing_queue
        self.display_filename = display_filename
        self.is_python = is_python

        # UI state
        self.scroll_line = 0       # first visible line
        self.scroll_col = 0        # first visible column
        self.sidebar_width = 22
        self.dirty = True
        self.connected = False
        self.status_message = ""
        self.error_message = ""
        self.error_timer = 0

        # Search state
        self.search_mode = False
        self.search_query = ""
        self.search_matches: List[int] = []  # offsets of matches
        self.search_current = -1
        self.replace_mode = False
        self.replace_query = ""
        self.replace_prompt = ""
        self.replace_idx = 0

        # Curses objects
        self.stdscr = None

        # Remote user color mapping
        self.user_colors: Dict[str, int] = {}
        self._next_remote_color = 0

    def _get_user_color(self, username: str) -> int:
        if username not in self.user_colors:
            self.user_colors[username] = REMOTE_COLORS[
                self._next_remote_color % MAX_REMOTE_USERS
            ]
            self._next_remote_color += 1
        return self.user_colors[username]

    def _init_curses(self):
        import curses
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.start_color()
        curses.use_default_colors()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)

        # Initialize color pairs
        curses.init_pair(COLOR_KEYWORD, curses.COLOR_BLUE, -1)
        curses.init_pair(COLOR_STRING, curses.COLOR_GREEN, -1)
        curses.init_pair(COLOR_COMMENT, curses.COLOR_MAGENTA, -1)
        curses.init_pair(COLOR_NUMBER, curses.COLOR_CYAN, -1)
        curses.init_pair(COLOR_CURSOR, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(COLOR_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(COLOR_SIDEBAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(COLOR_SEARCH_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(COLOR_LINE_NUMBER, curses.COLOR_YELLOW, -1)
        curses.init_pair(COLOR_MATCH_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_GREEN)

        # Remote user colors
        remote_bg_colors = [
            curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_BLUE,
            curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_YELLOW,
            curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_GREEN,
            curses.COLOR_BLUE,
        ]
        for i in range(MAX_REMOTE_USERS):
            curses.init_pair(
                REMOTE_COLORS[i],
                curses.COLOR_BLACK,
                remote_bg_colors[i % len(remote_bg_colors)]
            )

        # Hide cursor
        curses.curs_set(0)

    def run(self):
        import curses
        try:
            self._init_curses()
            self._main_loop()
        finally:
            if self.stdscr:
                self.stdscr.keypad(False)
                curses.nocbreak()
                curses.echo()
                curses.endwin()

    def _main_loop(self):
        import curses
        last_redraw = time.time()
        while True:
            # Process network messages
            self._process_incoming()

            # Process keyboard
            key = self.stdscr.getch()
            if key != -1:
                if not self._handle_key(key):
                    break  # quit

            # Redraw if needed or periodically
            now = time.time()
            if self.dirty or (now - last_redraw > 0.1):
                self._redraw()
                last_redraw = now
                self.dirty = False

            # Update error timer
            if self.error_timer > 0:
                self.error_timer -= 1
                if self.error_timer == 0:
                    self.error_message = ""
                    self.dirty = True

            # Small sleep to avoid busy-wait
            time.sleep(0.02)

    def _process_incoming(self):
        try:
            while True:
                item = self.incoming.get_nowait()
                kind, data = item
                if kind == 'message':
                    self._handle_message(data)
                elif kind == 'error':
                    self.error_message = str(data)
                    self.error_timer = 50  # ~1 second at 50fps
                    self.dirty = True
                elif kind == 'disconnected':
                    self.connected = False
                    self.status_message = "Disconnected — reconnecting..."
                    self.dirty = True
        except queue.Empty:
            pass

    def _handle_message(self, msg: proto.Message):
        if isinstance(msg, proto.Ack):
            self.model.document = msg.document
            self.model.local_version = msg.version
            self.model.client_id = msg.client_id
            self.model.connected_users = msg.users
            self.model.lock_holder = msg.lock_holder
            self.model.pending_ops.clear()
            self.connected = True
            self.status_message = "Connected"
            # Reset user colors for current users
            for u in msg.users:
                self._get_user_color(u)
            self.dirty = True

        elif isinstance(msg, proto.Operation):
            # Remote operation
            op_msg = ot.OTMessage(
                op_type=msg.op_type,
                position=msg.position,
                text=msg.text,
                length=msg.length,
                client_id=msg.client_id,
                seq_no=msg.seq_no,
            )
            transformed = self.model.apply_remote_op(op_msg)
            # Adjust cursor if it's after the edit
            self._adjust_cursor_for_remote(transformed)
            self.model.local_version = max(self.model.local_version, msg.base_version)
            self.dirty = True

        elif isinstance(msg, proto.OperationAck):
            self.model.handle_ack(msg)
            self.dirty = True

        elif isinstance(msg, proto.CursorUpdate):
            if msg.line < 0:
                # User left
                self.model.remote_cursors.pop(msg.username, None)
            else:
                self.model.remote_cursors[msg.username] = (msg.line, msg.col, msg.offset)
            self.dirty = True

        elif isinstance(msg, proto.UserListUpdate):
            self.model.connected_users = msg.users
            for u in msg.users:
                self._get_user_color(u)
            self.dirty = True

        elif isinstance(msg, proto.LockUpdate):
            old_holder = self.model.lock_holder
            self.model.lock_holder = msg.holder
            self.model.lock_queue = msg.queue
            if msg.holder and msg.holder != old_holder:
                self.status_message = f"Lock held by {msg.holder}"
            elif msg.holder is None and old_holder:
                self.status_message = "Lock released"
            self.dirty = True

        elif isinstance(msg, proto.LockGrant):
            self.model.lock_holder = msg.holder
            self.status_message = "Lock acquired!"
            self.dirty = True

        elif isinstance(msg, proto.SaveAck):
            self.status_message = "Saved"
            self.error_message = ""
            self.error_timer = 30
            self.dirty = True

        elif isinstance(msg, proto.Error):
            self.error_message = msg.message
            self.error_timer = 50
            self.dirty = True

    def _adjust_cursor_for_remote(self, op_msg: ot.OTMessage):
        """Adjust local cursor position based on remote operation."""
        cur = self.model.cursor_offset
        if op_msg.op_type == "insert":
            if op_msg.position <= cur:
                self.model.cursor_offset += len(op_msg.text)
        elif op_msg.op_type == "delete":
            if op_msg.position + op_msg.length <= cur:
                self.model.cursor_offset -= op_msg.length
            elif op_msg.position < cur:
                self.model.cursor_offset = op_msg.position

    def _handle_key(self, key) -> bool:
        """Handle keypress. Return False to quit."""
        import curses

        # Search mode has its own key handling
        if self.search_mode:
            return self._handle_search_key(key)
        if self.replace_mode:
            return self._handle_replace_key(key)

        ctrl = key & 0x1f

        # Handle common Ctrl+letter combinations where key == ctrl code
        if key < 32:
            if ctrl == 19:  # Ctrl+S -> save
                self._send_save()
                return True
            elif ctrl == 6:  # Ctrl+F -> search
                self._enter_search()
                return True
            elif ctrl == 8:  # Ctrl+H -> find & replace
                self._enter_replace()
                return True
            elif ctrl == 12:  # Ctrl+L -> lock toggle
                self._toggle_lock()
                return True
            elif ctrl == 26:  # Ctrl+Z -> undo
                self._send_undo()
                return True
            elif ctrl == 17:  # Ctrl+Q -> quit
                return False
            elif ctrl == 3:  # Ctrl+C -> quit
                return False

        if 32 <= key <= 126:
            self._insert_char(chr(key))
            return True
        elif key == 10:  # Enter
            self._insert_char('\n')
            return True
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self._backspace()
            return True
        elif key == curses.KEY_DC:
            self._delete_forward()
            return True
        elif key == curses.KEY_LEFT:
            self._move_cursor(-1, 0)
            return True
        elif key == curses.KEY_RIGHT:
            self._move_cursor(1, 0)
            return True
        elif key == curses.KEY_UP:
            self._move_cursor(0, -1)
            return True
        elif key == curses.KEY_DOWN:
            self._move_cursor(0, 1)
            return True
        elif key == curses.KEY_HOME:
            self._move_home()
            return True
        elif key == curses.KEY_END:
            self._move_end()
            return True
        elif key == curses.KEY_PPAGE:
            self._page_up()
            return True
        elif key == curses.KEY_NPAGE:
            self._page_down()
            return True
        elif key == curses.KEY_RESIZE:
            self.dirty = True
            return True
        # Ctrl+Left / Ctrl+Right — these have various codes
        elif key == 545 or key == 546 or key == 547 or key == 548:  # Ctrl+Left variants
            self._word_left()
            return True
        elif key == 560 or key == 561 or key == 562 or key == 563:  # Ctrl+Right variants
            self._word_right()
            return True
        elif key == 554 or key == 555:  # More Ctrl+Left
            self._word_left()
            return True
        elif key == 569 or key == 570:  # More Ctrl+Right
            self._word_right()
            return True

        return True

    def _handle_ctrl_arrow(self, key: int):
        """Handle special key codes for Ctrl+Left/Right."""
        if key == 545:  # Ctrl+Left
            self._word_left()
        elif key == 560:  # Ctrl+Right
            self._word_right()

    # ── Cursor Movement ─────────────────────────────────────────────────

    def _move_cursor(self, dx: int, dy: int):
        doc = self.model.document
        lines = doc.split('\n')
        line, col = self.model.get_cursor_line_col()

        if dy != 0:
            new_line = max(0, min(len(lines) - 1, line + dy))
            if new_line < len(lines):
                new_col = min(col, len(lines[new_line]))
            else:
                new_col = 0
            self.model.set_cursor_line_col(new_line, new_col)
        else:
            if line < len(lines):
                new_col = max(0, min(len(lines[line]), col + dx))
                self.model.set_cursor_line_col(line, new_col)

        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _move_home(self):
        line, _ = self.model.get_cursor_line_col()
        self.model.set_cursor_line_col(line, 0)
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _move_end(self):
        doc = self.model.document
        lines = doc.split('\n')
        line, _ = self.model.get_cursor_line_col()
        if line < len(lines):
            self.model.set_cursor_line_col(line, len(lines[line]))
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _page_up(self):
        import curses
        page_size = max(1, curses.LINES - 4)  # minus status + sidebar space
        line, col = self.model.get_cursor_line_col()
        new_line = max(0, line - page_size)
        self.model.set_cursor_line_col(new_line, min(col, len(self.model.document.split('\n')[new_line]) if new_line < len(self.model.document.split('\n')) else 0))
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _page_down(self):
        import curses
        page_size = max(1, curses.LINES - 4)
        doc = self.model.document
        lines = doc.split('\n')
        line, col = self.model.get_cursor_line_col()
        new_line = min(len(lines) - 1, line + page_size)
        if new_line < len(lines):
            self.model.set_cursor_line_col(new_line, min(col, len(lines[new_line])))
        else:
            self.model.set_cursor_line_col(new_line, 0)
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _word_left(self):
        doc = self.model.document
        offset = self.model.cursor_offset
        # Find previous word boundary
        if offset == 0:
            return
        # Skip non-word chars to the left
        new_offset = offset - 1
        while new_offset > 0 and not doc[new_offset - 1].isalnum() and doc[new_offset - 1] != '_':
            new_offset -= 1
        # Skip word chars
        while new_offset > 0 and (doc[new_offset - 1].isalnum() or doc[new_offset - 1] == '_'):
            new_offset -= 1
        self.model.cursor_offset = new_offset
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _word_right(self):
        doc = self.model.document
        offset = self.model.cursor_offset
        if offset >= len(doc):
            return
        # Skip current word
        new_offset = offset
        while new_offset < len(doc) and (doc[new_offset].isalnum() or doc[new_offset] == '_'):
            new_offset += 1
        # Skip non-word chars
        while new_offset < len(doc) and not doc[new_offset].isalnum() and doc[new_offset] != '_':
            new_offset += 1
        self.model.cursor_offset = min(new_offset, len(doc))
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _scroll_to_cursor(self):
        import curses
        line, col = self.model.get_cursor_line_col()
        view_height = max(1, curses.LINES - 2)  # status bar
        view_width = max(1, curses.COLS - self.sidebar_width - 7)  # line numbers take ~6 cols

        # Vertical scroll
        if line < self.scroll_line:
            self.scroll_line = line
        elif line >= self.scroll_line + view_height:
            self.scroll_line = line - view_height + 1

        # Horizontal scroll
        if col < self.scroll_col:
            self.scroll_col = col
        elif col >= self.scroll_col + view_width:
            self.scroll_col = col - view_width + 1

    # ── Editing ─────────────────────────────────────────────────────────

    def _insert_char(self, ch: str):
        doc = self.model.document
        offset = self.model.cursor_offset

        op_msg = ot.OTMessage(
            op_type="insert",
            position=offset,
            text=ch,
            client_id=self.model.client_id,
            seq_no=0,
        )
        po = self.model.apply_local_op(op_msg)
        self.model.cursor_offset = min(len(self.model.document), offset + len(ch))

        # Send to server
        send_op = proto.Operation(
            op_type="insert",
            position=offset,
            text=ch,
            base_version=po.base_version,
            client_id=self.model.client_id,
            seq_no=po.seq_no,
        )
        self.outgoing.put(send_op)
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _backspace(self):
        doc = self.model.document
        offset = self.model.cursor_offset
        if offset == 0:
            return
        # Delete the character before cursor
        # If before cursor is a newline and cursor is at start of line,
        # delete the newline (merge lines)
        delete_pos = offset - 1
        length = 1

        op_msg = ot.OTMessage(
            op_type="delete",
            position=delete_pos,
            length=length,
            client_id=self.model.client_id,
            seq_no=0,
        )
        po = self.model.apply_local_op(op_msg)
        self.model.cursor_offset = delete_pos

        send_op = proto.Operation(
            op_type="delete",
            position=delete_pos,
            length=length,
            base_version=po.base_version,
            client_id=self.model.client_id,
            seq_no=po.seq_no,
        )
        self.outgoing.put(send_op)
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _delete_forward(self):
        doc = self.model.document
        offset = self.model.cursor_offset
        if offset >= len(doc):
            return

        op_msg = ot.OTMessage(
            op_type="delete",
            position=offset,
            length=1,
            client_id=self.model.client_id,
            seq_no=0,
        )
        po = self.model.apply_local_op(op_msg)
        # Cursor stays at same position

        send_op = proto.Operation(
            op_type="delete",
            position=offset,
            length=1,
            base_version=po.base_version,
            client_id=self.model.client_id,
            seq_no=po.seq_no,
        )
        self.outgoing.put(send_op)
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    # ── Network actions ─────────────────────────────────────────────────

    def _send_cursor_update(self):
        line, col = self.model.get_cursor_line_col()
        msg = proto.CursorUpdate(
            username=self.model.username,
            line=line,
            col=col,
            offset=self.model.cursor_offset,
        )
        self.outgoing.put(msg)

    def _send_save(self):
        msg = proto.SaveRequest(client_id=self.model.client_id)
        self.outgoing.put(msg)
        self.status_message = "Saving..."
        self.dirty = True

    def _send_undo(self):
        msg = proto.UndoRequest(client_id=self.model.client_id)
        self.outgoing.put(msg)
        self.status_message = "Undo requested..."
        self.dirty = True

    def _toggle_lock(self):
        status = self.model.get_lock_status()
        if status == 'held':
            msg = proto.LockRelease(client_id=self.model.client_id)
            self.outgoing.put(msg)
            self.status_message = "Releasing lock..."
        else:
            msg = proto.LockRequest(client_id=self.model.client_id)
            self.outgoing.put(msg)
            self.status_message = "Requesting lock..."
        self.dirty = True

    # ── Search ──────────────────────────────────────────────────────────

    def _enter_search(self):
        self.search_mode = True
        self.search_query = ""
        self.search_matches = []
        self.search_current = -1
        self.dirty = True

    def _enter_replace(self):
        self.replace_mode = True
        self.replace_prompt = "find"
        self.search_query = ""
        self.replace_query = ""
        self.replace_idx = 0
        self.dirty = True

    def _handle_search_key(self, key) -> bool:
        import curses
        if key == 27:  # Escape
            self.search_mode = False
            self.search_query = ""
            self.search_matches = []
            self.search_current = -1
            self.dirty = True
            return True
        elif key == 10:  # Enter — next match
            self._search_next()
            return True
        elif key == curses.KEY_BTAB or key == 353:  # Shift+Enter or Shift+Tab
            self._search_prev()
            return True
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if self.search_query:
                self.search_query = self.search_query[:-1]
                self._update_search_matches()
            self.dirty = True
            return True
        elif 32 <= key <= 126:
            self.search_query += chr(key)
            self._update_search_matches()
            self.dirty = True
            return True
        return True

    def _handle_replace_key(self, key) -> bool:
        import curses
        if key == 27:  # Escape
            self.replace_mode = False
            self.dirty = True
            return True
        elif key == 10:  # Enter — confirm prompt or go to next match
            if self.replace_prompt == "find":
                self._update_search_matches()
                if self.search_matches:
                    self.replace_prompt = "replace"
                    self.replace_query = ""
                    self.replace_idx = 0
                    self.model.cursor_offset = self.search_matches[0]
                else:
                    self.replace_mode = False
            elif self.replace_prompt == "replace":
                self._update_search_matches()
                if self.search_matches:
                    self.replace_prompt = "confirm"
                    self.replace_idx = 0
                    self.model.cursor_offset = self.search_matches[0]
                else:
                    self.replace_mode = False
            elif self.replace_prompt == "confirm":
                # Replace current match
                self._do_replace_current()
                self._update_search_matches()
                if not self.search_matches:
                    self.replace_mode = False
                elif self.replace_idx >= len(self.search_matches):
                    self.replace_idx = 0
                    if self.search_matches:
                        self.model.cursor_offset = self.search_matches[0]
            self._scroll_to_cursor()
            self._send_cursor_update()
            self.dirty = True
            return True
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if self.replace_prompt == "find":
                if self.search_query:
                    self.search_query = self.search_query[:-1]
                    self._update_search_matches()
            elif self.replace_prompt == "replace":
                if self.replace_query:
                    self.replace_query = self.replace_query[:-1]
            self.dirty = True
            return True
        elif key == ord('y') or key == ord('Y'):
            if self.replace_prompt == "confirm":
                self._do_replace_current()
                self._update_search_matches()
                if not self.search_matches:
                    self.replace_mode = False
                elif self.replace_idx >= len(self.search_matches):
                    self.replace_idx = len(self.search_matches) - 1
                if self.search_matches:
                    self.model.cursor_offset = self.search_matches[self.replace_idx]
                self._scroll_to_cursor()
                self._send_cursor_update()
            self.dirty = True
            return True
        elif key == ord('n') or key == ord('N'):
            if self.replace_prompt == "confirm":
                # Skip this match
                self.replace_idx += 1
                if self.replace_idx >= len(self.search_matches):
                    self.replace_mode = False
                elif self.search_matches:
                    self.model.cursor_offset = self.search_matches[self.replace_idx]
                    self._scroll_to_cursor()
                    self._send_cursor_update()
            self.dirty = True
            return True
        elif 32 <= key <= 126:
            if self.replace_prompt == "find":
                self.search_query += chr(key)
                self._update_search_matches()
            elif self.replace_prompt == "replace":
                self.replace_query += chr(key)
            self.dirty = True
            return True
        return True

    def _update_search_matches(self):
        if not self.search_query:
            self.search_matches = []
            self.search_current = -1
            return
        doc = self.model.document
        pattern = re.escape(self.search_query)
        self.search_matches = [m.start() for m in re.finditer(pattern, doc)]
        self.search_current = 0 if self.search_matches else -1

    def _search_next(self):
        if not self.search_matches:
            return
        self.search_current = (self.search_current + 1) % len(self.search_matches)
        self.model.cursor_offset = self.search_matches[self.search_current]
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _search_prev(self):
        if not self.search_matches:
            return
        self.search_current = (self.search_current - 1) % len(self.search_matches)
        self.model.cursor_offset = self.search_matches[self.search_current]
        self._scroll_to_cursor()
        self._send_cursor_update()
        self.dirty = True

    def _do_replace_current(self):
        if self.replace_idx >= len(self.search_matches):
            return
        offset = self.search_matches[self.replace_idx]
        doc = self.model.document
        # Delete old text
        old_len = len(self.search_query)
        if old_len > 0 and offset + old_len <= len(doc):
            del_op = ot.OTMessage("delete", offset, length=old_len,
                                   client_id=self.model.client_id, seq_no=0)
            po_del = self.model.apply_local_op(del_op)
            self.outgoing.put(proto.Operation(
                op_type="delete", position=offset, length=old_len,
                base_version=po_del.base_version, client_id=self.model.client_id,
                seq_no=po_del.seq_no,
            ))

        # Insert replacement
        if self.replace_query:
            ins_op = ot.OTMessage("insert", offset, text=self.replace_query,
                                   client_id=self.model.client_id, seq_no=0)
            po_ins = self.model.apply_local_op(ins_op)
            self.outgoing.put(proto.Operation(
                op_type="insert", position=offset, text=self.replace_query,
                base_version=po_ins.base_version, client_id=self.model.client_id,
                seq_no=po_ins.seq_no,
            ))

    # ── Rendering ───────────────────────────────────────────────────────

    def _redraw(self):
        if self.stdscr is None:
            return
        import curses
        self.stdscr.erase()

        max_y, max_x = self.stdscr.getmaxyx()

        # Layout
        sidebar_x = max_x - self.sidebar_width
        main_width = sidebar_x
        line_number_width = 6
        text_x = line_number_width
        text_width = main_width - text_x
        if text_width < 1:
            text_width = 1

        # Viewport
        view_height = max_y - 1  # leave bottom line for status

        # Draw document
        self._draw_document(text_x, text_width, view_height)

        # Draw sidebar separator
        if sidebar_x < max_x:
            for y in range(view_height):
                try:
                    self.stdscr.addch(y, sidebar_x - 1, '│')
                except curses.error:
                    pass

        # Draw sidebar
        self._draw_sidebar(sidebar_x, view_height, max_x - sidebar_x)

        # Draw status bar
        self._draw_status(max_y - 1, max_x)

        # Draw search/replace prompt if active
        if self.search_mode:
            self._draw_search_prompt(max_y - 2, max_x)
        elif self.replace_mode:
            self._draw_replace_prompt(max_y - 2, max_x)

        # Draw error message if any
        if self.error_message and self.error_timer > 0:
            try:
                self.stdscr.addstr(max_y - 2, 0, f"⚠ {self.error_message}"[:max_x],
                                   curses.color_pair(COLOR_SEARCH_HIGHLIGHT))
            except curses.error:
                pass

        try:
            self.stdscr.refresh()
        except curses.error:
            pass

    def _draw_document(self, text_x: int, text_width: int, view_height: int):
        import curses
        doc = self.model.document
        lines = doc.split('\n')
        cursor_line, cursor_col = self.model.get_cursor_line_col()

        for vy in range(view_height):
            doc_line_idx = self.scroll_line + vy
            if doc_line_idx >= len(lines):
                break

            screen_y = vy
            line_text = lines[doc_line_idx]

            # Line number
            line_num_str = f"{doc_line_idx + 1:5d} "
            try:
                self.stdscr.addstr(screen_y, 0, line_num_str,
                                   curses.color_pair(COLOR_LINE_NUMBER))
            except curses.error:
                pass

            # Visible portion of line
            if self.scroll_col < len(line_text):
                visible = line_text[self.scroll_col:self.scroll_col + text_width]
            else:
                visible = ""

            # If Python file, apply syntax highlighting
            if self.is_python:
                tokens, _ = tokenize_line(line_text)
                # Adjust tokens for scroll
                col_start = 0
                for tok_start, tok_end, color_id in tokens:
                    # Adjust for scroll
                    adj_start = tok_start - self.scroll_col
                    adj_end = tok_end - self.scroll_col
                    if adj_end <= 0:
                        continue
                    if adj_start >= text_width:
                        break
                    disp_start = max(0, adj_start)
                    disp_end = min(text_width, adj_end)
                    if disp_end > disp_start:
                        seg = line_text[tok_start + (disp_start - adj_start):
                                        tok_start + (disp_end - adj_start)]
                        try:
                            self.stdscr.addstr(screen_y, text_x + disp_start,
                                               seg, curses.color_pair(color_id))
                        except curses.error:
                            pass
            else:
                # Plain text
                try:
                    self.stdscr.addstr(screen_y, text_x, visible[:text_width])
                except curses.error:
                    pass

            # Draw cursor
            if doc_line_idx == cursor_line:
                cursor_screen_x = text_x + cursor_col - self.scroll_col
                if 0 <= cursor_screen_x < text_x + text_width:
                    cursor_char = ' '
                    if cursor_col < len(line_text):
                        cursor_char = line_text[cursor_col]
                    try:
                        self.stdscr.addstr(screen_y, cursor_screen_x,
                                           cursor_char,
                                           curses.color_pair(COLOR_CURSOR))
                    except curses.error:
                        pass

                # Cursor username label above
                if vy > 0 and cursor_col - self.scroll_col >= 0:
                    label = self.model.username[:1]
                    try:
                        self.stdscr.addstr(screen_y - 1, cursor_screen_x,
                                           label,
                                           curses.color_pair(COLOR_CURSOR))
                    except curses.error:
                        pass

            # Draw remote cursors
            for uname, (rline, rcol, roffset) in list(self.model.remote_cursors.items()):
                if rline == doc_line_idx:
                    rsx = text_x + rcol - self.scroll_col
                    if 0 <= rsx < text_x + text_width:
                        color = self._get_user_color(uname)
                        marker_char = ' '
                        if rcol < len(line_text):
                            marker_char = line_text[rcol]
                        try:
                            self.stdscr.addstr(screen_y, rsx, marker_char,
                                               curses.color_pair(color))
                        except curses.error:
                            pass
                        # Username label above
                        if vy > 0:
                            label = uname[:1]
                            try:
                                self.stdscr.addstr(screen_y - 1, rsx,
                                                   label,
                                                   curses.color_pair(color))
                            except curses.error:
                                pass

            # Draw search highlights
            if self.search_matches:
                for match_offset in self.search_matches:
                    ml, mc = ot.offset_to_line_col(doc, match_offset)
                    if ml == doc_line_idx:
                        msx = text_x + mc - self.scroll_col
                        match_len = len(self.search_query)
                        me = msx + match_len
                        if msx < text_x + text_width and me > text_x:
                            d_start = max(text_x, msx)
                            d_end = min(text_x + text_width, me)
                            if d_end > d_start:
                                seg = doc[match_offset + (d_start - msx):
                                          match_offset + (d_end - msx)]
                                try:
                                    self.stdscr.addstr(
                                        screen_y, d_start, seg,
                                        curses.color_pair(
                                            COLOR_MATCH_HIGHLIGHT
                                            if match_offset == (
                                                self.search_matches[self.search_current]
                                                if self.search_current >= 0
                                                   and self.search_current < len(self.search_matches)
                                                else -1)
                                            else COLOR_SEARCH_HIGHLIGHT
                                        )
                                    )
                                except curses.error:
                                    pass

    def _draw_sidebar(self, x: int, view_height: int, width: int):
        import curses
        # Header
        try:
            self.stdscr.addstr(0, x, " USERS".ljust(width),
                               curses.color_pair(COLOR_SIDEBAR) | curses.A_BOLD)
        except curses.error:
            pass

        users = self.model.connected_users
        for i, uname in enumerate(users):
            if i + 1 >= view_height:
                break
            cursor_info = self.model.remote_cursors.get(uname, (0, 0, 0))
            line_no = cursor_info[0] + 1  # 1-indexed display

            color = self._get_user_color(uname)

            # Lock indicator
            lock_str = "🔒" if uname == self.model.lock_holder else "  "

            display = f" {lock_str}{uname[:width-6]:<{width-9}}L{line_no:>4}"
            try:
                self.stdscr.addstr(i + 1, x, display[:width],
                                   curses.color_pair(color))
            except curses.error:
                pass

    def _draw_status(self, y: int, max_x: int):
        import curses
        line, col = self.model.get_cursor_line_col()
        conn_status = "Connected" if self.connected else "Disconnected"
        lock_status = self.model.get_lock_status()
        lock_str = {"held": "🔒", "queued": "🕐", "locked_by_other": "🔒✖", "none": "  "}[lock_status]

        status = (
            f" {self.display_filename} | "
            f"Users: {len(self.model.connected_users)} | "
            f"{conn_status} | "
            f"L{line+1}:C{col+1} | "
            f"Lock:{lock_str} | "
            f"{self.status_message}"
        )
        try:
            self.stdscr.addstr(y, 0, status[:max_x],
                               curses.color_pair(COLOR_STATUS) | curses.A_BOLD)
            # Pad remaining
            if len(status) < max_x:
                self.stdscr.addstr(y, len(status), " " * (max_x - len(status)),
                                   curses.color_pair(COLOR_STATUS))
        except curses.error:
            pass

    def _draw_search_prompt(self, y: int, max_x: int):
        import curses
        prompt = f"Search: {self.search_query}"
        match_info = ""
        if self.search_matches:
            match_info = f" ({self.search_current + 1}/{len(self.search_matches)} matches)"
        full = prompt + match_info + " [Enter=next Shift+Enter=prev Esc=exit]"
        try:
            self.stdscr.addstr(y, 0, full[:max_x],
                               curses.color_pair(COLOR_STATUS))
            if len(full) < max_x:
                self.stdscr.addstr(y, len(full), " " * (max_x - len(full)),
                                   curses.color_pair(COLOR_STATUS))
        except curses.error:
            pass

    def _draw_replace_prompt(self, y: int, max_x: int):
        import curses
        if self.replace_prompt == "find":
            prompt = f"Find: {self.search_query}"
        elif self.replace_prompt == "replace":
            prompt = f"Replace with: {self.replace_query}"
        else:
            prompt = f"Replace '{self.search_query}' with '{self.replace_query}'? (y/n)"
        try:
            self.stdscr.addstr(y, 0, prompt[:max_x],
                               curses.color_pair(COLOR_STATUS))
            if len(prompt) < max_x:
                self.stdscr.addstr(y, len(prompt), " " * (max_x - len(prompt)),
                                   curses.color_pair(COLOR_STATUS))
        except curses.error:
            pass


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Client")
    parser.add_argument("--host", type=str, default="localhost",
                        help="Server host")
    parser.add_argument("--port", type=int, default=9000,
                        help="Server port")
    parser.add_argument("--user", type=str, required=True,
                        help="Username")
    parser.add_argument("--room", type=str, required=True,
                        help="Room name")
    parser.add_argument("--password", type=str, default="",
                        help="Room password")
    parser.add_argument("--file", type=str, default="untitled.txt",
                        help="Display filename (for syntax highlighting)")
    args = parser.parse_args()

    # Determine if Python syntax highlighting
    is_python = args.file.endswith('.py')

    model = ClientModel()
    model.username = args.user

    incoming = queue.Queue()
    outgoing = queue.Queue()

    net_thread = NetworkThread(
        host=args.host,
        port=args.port,
        username=args.user,
        room=args.room,
        password=args.password,
        incoming_queue=incoming,
        outgoing_queue=outgoing,
        model=model,
    )
    net_thread.start()

    ui = CursesUI(
        model=model,
        incoming_queue=incoming,
        outgoing_queue=outgoing,
        display_filename=args.file,
        is_python=is_python,
    )

    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        net_thread.stop()
        # Send disconnect
        try:
            outgoing.put(proto.Disconnect(username=args.user))
        except Exception:
            pass
        net_thread.join(timeout=2)
        print(f"Goodbye, {args.user}!")


if __name__ == "__main__":
    main()
