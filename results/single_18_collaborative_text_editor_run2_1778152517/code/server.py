#!/usr/bin/env python3
"""Collaborative text editor server.

Accepts client connections, manages rooms, persists documents,
and performs Operational Transformation for concurrent edits.
"""

import argparse
import json
import logging
import os
import selectors
import socket
import sys
import time
from pathlib import Path

from ot import (
    apply_operation,
    flat_to_line_col,
    line_col_to_flat,
    transform,
    transform_against_list,
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
)


class Room:
    """A collaborative editing room containing a document and connected users."""

    def __init__(self, name, password, doc_dir):
        self.name = name
        self.password = password
        self.doc_path = Path(doc_dir) / f"{name}.txt"
        self.document = ""
        self.version = 0
        # history: list of {op, username, char, version}
        self.history = []
        # per-client history indices for undo
        self.client_ops = {}  # username -> [history_index, ...]
        self.users = {}  # username -> {cursor_row, cursor_col, sock}
        self.lock_holder = None
        self.lock_queue = []
        self._load()

    def _load(self):
        if self.doc_path.exists():
            self.document = self.doc_path.read_text()

    def save(self):
        self.doc_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc_path.write_text(self.document)

    def add_user(self, username, sock):
        self.users[username] = {
            'cursor_row': 0,
            'cursor_col': 0,
            'sock': sock,
        }
        if username not in self.client_ops:
            self.client_ops[username] = []

    def remove_user(self, username):
        self.users.pop(username, None)
        if self.lock_holder == username:
            self.lock_holder = None
            self._grant_next_lock()
        if username in self.lock_queue:
            self.lock_queue.remove(username)

    def process_operation(self, op, username, client_version):
        """Process an incoming operation with OT.

        Transforms the operation against concurrent operations,
        applies it, and stores history for undo.

        Returns the transformed operation or None if voided.
        """
        # Get concurrent operations since client's version
        concurrent = []
        for i in range(client_version, len(self.history)):
            concurrent.append(self.history[i]['op'])

        # Transform the operation
        transformed = transform_against_list(op, concurrent)
        if transformed is None:
            return None

        # Capture deleted character before applying
        deleted_char = ''
        if transformed['type'] == 'delete':
            pos = transformed['position']
            if 0 <= pos < len(self.document):
                deleted_char = self.document[pos]

        # Apply
        self.document = apply_operation(self.document, transformed)

        # Store in history
        entry = {
            'op': transformed,
            'username': username,
            'char': deleted_char,
            'version': self.version,
        }
        self.history.append(entry)
        if username in self.client_ops:
            self.client_ops[username].append(len(self.history) - 1)
        self.version += 1

        self.save()
        return transformed

    def get_undo_operation(self, username):
        """Return (inverse_op, base_version) or (None, None)."""
        if username not in self.client_ops or not self.client_ops[username]:
            return None, None
        idx = self.client_ops[username].pop()
        if idx >= len(self.history):
            return None, None
        entry = self.history[idx]
        op = entry['op']
        base_version = entry['version'] + 1  # state *after* original op

        if op['type'] == 'insert':
            return {'type': 'delete', 'position': op['position']}, base_version
        else:
            return {
                'type': 'insert',
                'position': op['position'],
                'char': entry.get('char', ''),
            }, base_version

    def request_lock(self, username):
        """Request the edit lock. Returns (granted, status)."""
        if self.lock_holder == username:
            return True, 'already_held'
        if self.lock_holder is None:
            self.lock_holder = username
            return True, 'granted'
        if username not in self.lock_queue:
            self.lock_queue.append(username)
        return False, 'queued'

    def release_lock(self, username):
        """Release the lock held by username."""
        released = False
        if self.lock_holder == username:
            self.lock_holder = None
            released = True
        if username in self.lock_queue:
            self.lock_queue.remove(username)
        if released:
            self._grant_next_lock()
        return released

    def _grant_next_lock(self):
        """Grant the lock to the next user in the queue."""
        while self.lock_queue:
            next_user = self.lock_queue.pop(0)
            if next_user in self.users:
                self.lock_holder = next_user
                return next_user
        return None

    def get_user_list(self):
        return [
            {
                'username': u,
                'cursor_row': info['cursor_row'],
                'cursor_col': info['cursor_col'],
            }
            for u, info in self.users.items()
        ]

    @property
    def user_count(self):
        return len(self.users)


class Server:
    """Main server handling connections and message routing."""

    def __init__(self, host, port, config_file, doc_dir):
        self.host = host
        self.port = port
        self.doc_dir = Path(doc_dir)
        self.rooms = {}
        self.selector = selectors.DefaultSelector()
        self.running = True

        # Load config
        with open(config_file) as f:
            self.config = json.load(f)

        # Pre-create configured rooms
        for room_name, room_cfg in self.config.get('rooms', {}).items():
            password = room_cfg.get('password', '')
            self.rooms[room_name] = Room(room_name, password, self.doc_dir)

        # Setup logging
        log_dir = Path(os.environ.get('LOG_DIR', str(self.doc_dir / 'logs')))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            log_dir = Path('/tmp/collab_editor_logs')
            log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"server_{time.strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
        )
        self.logger = logging.getLogger('server')
        self.logger.info(f"Server starting on {host}:{port}")

        # Track connections: sock -> {buffer, username, room_name}
        self.connections = {}

    def start(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(64)
        server_sock.setblocking(False)
        self.selector.register(server_sock, selectors.EVENT_READ, data=None)

        print(f"Server listening on {self.host}:{self.port}")
        self.logger.info(f"Server listening on {self.host}:{self.port}")

        try:
            while self.running:
                events = self.selector.select(timeout=1.0)
                for key, mask in events:
                    if key.data is None:
                        self._accept_connection(key.fileobj)
                    else:
                        self._handle_client(key.fileobj, mask)
        except KeyboardInterrupt:
            self.logger.info("Server shutting down (KeyboardInterrupt)")
            print("\nShutting down...")
        finally:
            self._shutdown()

    def _shutdown(self):
        self.running = False
        for sock in list(self.connections.keys()):
            self._disconnect(sock)
        self.selector.close()
        self.logger.info("Server stopped")

    def _accept_connection(self, sock):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.selector.register(
            conn, selectors.EVENT_READ, data={'buffer': b''}
        )
        self.connections[conn] = {
            'buffer': b'',
            'username': None,
            'room_name': None,
            'addr': addr,
        }
        self.logger.info(f"Connection accepted from {addr}")

    def _handle_client(self, sock, mask):
        if mask & selectors.EVENT_READ:
            try:
                data = sock.recv(65536)
                if data:
                    self.connections[sock]['buffer'] += data
                    self._process_buffer(sock)
                else:
                    self._disconnect(sock)
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                self.logger.info(f"Client disconnected: {e}")
                self._disconnect(sock)
            except Exception as e:
                self.logger.error(f"Error handling client: {e}")
                self._disconnect(sock)

    def _process_buffer(self, sock):
        conn = self.connections[sock]
        buf = conn['buffer']
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            conn['buffer'] = buf
            if line.strip():
                try:
                    msg = json.loads(line.decode('utf-8'))
                    self._handle_message(sock, msg)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON: {e}")
                    self._send_error(sock, f"Invalid JSON: {e}")
                except Exception as e:
                    self.logger.error(f"Message handling error: {e}")

    def _handle_message(self, sock, msg):
        msg_type = msg.get('type')
        conn = self.connections.get(sock)
        if conn is None:
            return

        if msg_type == MSG_CONNECT:
            self._handle_connect(sock, msg)
        elif msg_type == MSG_OPERATION:
            self._handle_operation(sock, msg)
        elif msg_type == MSG_CURSOR_UPDATE:
            self._handle_cursor_update(sock, msg)
        elif msg_type == MSG_LOCK_REQUEST:
            self._handle_lock_request(sock)
        elif msg_type == MSG_LOCK_RELEASE:
            self._handle_lock_release(sock)
        elif msg_type == MSG_SAVE_REQUEST:
            self._handle_save_request(sock)
        elif msg_type == MSG_UNDO:
            self._handle_undo(sock)
        else:
            self.logger.warning(f"Unknown message type: {msg_type}")

    # ── handlers ──────────────────────────────────────────────

    def _handle_connect(self, sock, msg):
        username = msg.get('username', '').strip()
        room_name = msg.get('room', '').strip()
        password = msg.get('password', '')

        if not username or not room_name:
            self._send_error(sock, "Username and room name are required")
            return

        if not username.isalnum() and not all(c.isalnum() or c in '_-' for c in username):
            self._send_error(sock, "Username must be alphanumeric (with _ and -)")
            return

        # Get or create room
        if room_name not in self.rooms:
            self.rooms[room_name] = Room(room_name, '', self.doc_dir)
            self.logger.info(f"Auto-created room: {room_name}")

        room = self.rooms[room_name]

        # Check password
        if room.password and room.password != password:
            self._send_error(sock, "Invalid password")
            self.logger.info(
                f"Failed auth: {username} -> room '{room_name}'"
            )
            return

        # Check duplicate username in room
        if username in room.users:
            self._send_error(sock, "Username already taken in this room")
            return

        # Register
        conn = self.connections[sock]
        conn['username'] = username
        conn['room_name'] = room_name
        room.add_user(username, sock)

        # Send ack with full document state
        self._send(
            sock,
            {
                'type': MSG_ACK,
                'document': room.document,
                'version': room.version,
                'users': room.get_user_list(),
                'lock_holder': room.lock_holder,
                'lock_queue': list(room.lock_queue),
            },
        )

        # Notify other users
        self._broadcast(
            room,
            {
                'type': MSG_USER_JOINED,
                'username': username,
                'cursor_row': 0,
                'cursor_col': 0,
            },
            exclude=sock,
        )

        self.logger.info(f"User '{username}' connected to room '{room_name}' "
                         f"({room.user_count} users)")

    def _handle_operation(self, sock, msg):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        if not username or not room_name:
            return
        room = self.rooms.get(room_name)
        if room is None:
            return

        # Check lock
        if room.lock_holder and room.lock_holder != username:
            self._send_error(sock, "Document is locked by another user")
            return

        op = msg.get('op')
        client_version = msg.get('version', 0)
        op_id = msg.get('id')

        if not op or 'type' not in op or 'position' not in op:
            self._send_error(sock, "Invalid operation")
            return

        transformed_op = room.process_operation(op, username, client_version)
        if transformed_op is None:
            # Operation was voided (e.g., double delete); still ack
            self._send(
                sock,
                {
                    'type': MSG_OPERATION_BROADCAST,
                    'op': op,
                    'username': username,
                    'version': room.version,
                    'id': op_id,
                    'voided': True,
                },
            )
            return

        # Broadcast to ALL clients in room (including sender for confirmation)
        broadcast_msg = {
            'type': MSG_OPERATION_BROADCAST,
            'op': transformed_op,
            'username': username,
            'version': room.version,
            'id': op_id,
        }
        self._broadcast(room, broadcast_msg)
        self.logger.debug(
            f"Op by {username} in '{room_name}': {transformed_op} v{room.version}"
        )

    def _handle_cursor_update(self, sock, msg):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        if not username or not room_name:
            return
        room = self.rooms.get(room_name)
        if room is None:
            return

        cursor_row = msg.get('cursor_row', 0)
        cursor_col = msg.get('cursor_col', 0)

        if username in room.users:
            room.users[username]['cursor_row'] = cursor_row
            room.users[username]['cursor_col'] = cursor_col

        self._broadcast(
            room,
            {
                'type': MSG_CURSOR_UPDATE,
                'username': username,
                'cursor_row': cursor_row,
                'cursor_col': cursor_col,
            },
            exclude=sock,
        )

    def _handle_lock_request(self, sock):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        room = self.rooms.get(room_name)
        if room is None:
            return

        granted, status = room.request_lock(username)

        self._send(
            sock,
            {
                'type': MSG_LOCK_GRANT,
                'granted': granted,
                'status': status,
                'lock_holder': room.lock_holder,
                'lock_queue': list(room.lock_queue),
            },
        )

        # Broadcast lock status to everyone
        self._broadcast(
            room,
            {
                'type': MSG_LOCK_STATUS,
                'lock_holder': room.lock_holder,
                'lock_queue': list(room.lock_queue),
            },
        )

        self.logger.info(
            f"Lock request by {username} in '{room_name}': "
            f"granted={granted}, status={status}"
        )

    def _handle_lock_release(self, sock):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        room = self.rooms.get(room_name)
        if room is None:
            return

        room.release_lock(username)

        # Notify the releaser
        self._send(
            sock,
            {
                'type': MSG_LOCK_GRANT,
                'granted': False,
                'status': 'released',
                'lock_holder': room.lock_holder,
                'lock_queue': list(room.lock_queue),
            },
        )

        # If a new lock holder was granted, notify them
        if room.lock_holder and room.lock_holder != username:
            holder_sock = room.users.get(room.lock_holder, {}).get('sock')
            if holder_sock:
                self._send(
                    holder_sock,
                    {
                        'type': MSG_LOCK_GRANT,
                        'granted': True,
                        'status': 'granted',
                        'lock_holder': room.lock_holder,
                        'lock_queue': list(room.lock_queue),
                    },
                )

        # Broadcast updated lock status
        self._broadcast(
            room,
            {
                'type': MSG_LOCK_STATUS,
                'lock_holder': room.lock_holder,
                'lock_queue': list(room.lock_queue),
            },
        )

        self.logger.info(f"Lock released by {username} in '{room_name}'")

    def _handle_save_request(self, sock):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        room = self.rooms.get(room_name)
        if room is None:
            return

        room.save()
        self._send(sock, {'type': MSG_SAVE_ACK, 'filename': str(room.doc_path)})
        self.logger.info(f"Save by {username} in '{room_name}': {room.doc_path}")

    def _handle_undo(self, sock):
        conn = self.connections[sock]
        username = conn['username']
        room_name = conn['room_name']
        if not username or not room_name:
            return
        room = self.rooms.get(room_name)
        if room is None:
            return

        # Check lock
        if room.lock_holder and room.lock_holder != username:
            self._send_error(sock, "Document is locked by another user")
            return

        inverse, base_version = room.get_undo_operation(username)
        if inverse is None:
            self._send_error(sock, "Nothing to undo")
            return

        # Process the inverse as a new operation
        # Use the version when the original op was applied as the base
        transformed = room.process_operation(inverse, username, base_version)
        if transformed is None:
            return

        broadcast_msg = {
            'type': MSG_OPERATION_BROADCAST,
            'op': transformed,
            'username': username,
            'version': room.version,
            'id': None,  # undo doesn't have a client-side id
        }
        self._broadcast(room, broadcast_msg)
        self.logger.info(f"Undo by {username} in '{room_name}': {transformed}")

    # ── helpers ───────────────────────────────────────────────

    def _broadcast(self, room, msg, exclude=None):
        """Send a message to all users in a room, optionally excluding one socket."""
        data = encode(msg).encode('utf-8')
        for user_info in list(room.users.values()):
            sock = user_info['sock']
            if sock != exclude:
                try:
                    sock.send(data)
                except Exception:
                    pass

    def _send(self, sock, msg):
        """Send a message to a specific socket."""
        try:
            sock.send(encode(msg).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Send error: {e}")

    def _send_error(self, sock, message):
        self._send(sock, {'type': MSG_ERROR, 'message': message})

    def _disconnect(self, sock):
        """Clean up a disconnected client."""
        if sock in self.connections:
            conn = self.connections[sock]
            username = conn.get('username')
            room_name = conn.get('room_name')

            if username and room_name and room_name in self.rooms:
                room = self.rooms[room_name]
                room.remove_user(username)
                self._broadcast(
                    room,
                    {'type': MSG_USER_LEFT, 'username': username},
                )
                self.logger.info(
                    f"User '{username}' left room '{room_name}' "
                    f"({room.user_count} users)"
                )

            del self.connections[sock]

        try:
            self.selector.unregister(sock)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description='Collaborative Text Editor Server')
    parser.add_argument(
        '--port', type=int, default=9000, help='TCP port to listen on (default: 9000)'
    )
    parser.add_argument(
        '--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Server config JSON file (default: config.json)',
    )
    parser.add_argument(
        '--doc-dir',
        type=str,
        default='documents',
        help='Directory for persisted documents (default: documents/)',
    )
    args = parser.parse_args()

    server = Server(args.host, args.port, args.config, args.doc_dir)
    server.start()


if __name__ == '__main__':
    main()
