#!/usr/bin/env python3
"""
server.py - Collaborative text editor server.

Usage:
    python server.py --port 9999 [--config config.json]
"""

import argparse
import json
import os
import socket
import sys
import threading
import time
import logging
from collections import defaultdict
from typing import Optional

from shared import (
    Document,
    transform_against_list,
    make_message,
    parse_message,
    timestamp,
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
# Room
# ---------------------------------------------------------------------------

class Room:
    """A collaborative editing room with one document."""

    def __init__(self, name: str, password: str, data_dir: str):
        self.name = name
        self.password = password
        self.filepath = os.path.join(data_dir, f"{name}.txt")
        self.document = Document(self._load_document())
        self.operation_history: list[dict] = []  # all applied operations
        self.version = 0  # monotonically increasing version counter
        self.clients: dict[str, 'ClientHandler'] = {}  # username -> handler
        self.lock_owner: Optional[str] = None
        self.lock_queue: list[str] = []  # FIFO queue of usernames waiting for lock

    def _load_document(self) -> str:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    def save_document(self):
        """Persist document to disk."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(self.document.get_text())
        except Exception as e:
            logging.error(f"[{timestamp()}] Failed to save room '{self.name}': {e}")

    def add_client(self, username: str, handler: 'ClientHandler'):
        self.clients[username] = handler

    def remove_client(self, username: str):
        self.clients.pop(username, None)
        # Release lock if held by this user
        if self.lock_owner == username:
            self.lock_owner = None
            self._grant_next_lock()
        # Remove from lock queue
        if username in self.lock_queue:
            self.lock_queue.remove(username)

    def get_user_list(self) -> list[dict]:
        """Return list of {username, cursor_line, cursor_col} for all clients."""
        users = []
        for uname, handler in self.clients.items():
            users.append({
                "username": uname,
                "cursor_line": handler.cursor_line,
                "cursor_col": handler.cursor_col,
            })
        return users

    def broadcast(self, message: bytes, exclude: Optional[str] = None):
        """Send a message to all clients in the room."""
        for uname, handler in list(self.clients.items()):
            if uname != exclude:
                try:
                    handler.send_raw(message)
                except Exception:
                    pass

    def broadcast_user_list(self):
        """Send updated user list to all clients."""
        users = self.get_user_list()
        msg = make_message(MSG_USER_LIST, users=users, lock_owner=self.lock_owner)
        self.broadcast(msg)

    def request_lock(self, username: str):
        """Handle a lock request from a user."""
        if self.lock_owner == username:
            # Already owns the lock
            handler = self.clients.get(username)
            if handler:
                handler.send_raw(make_message(MSG_LOCK_GRANT, username=username))
            return

        if self.lock_owner is None:
            # Grant immediately
            self.lock_owner = username
            handler = self.clients.get(username)
            if handler:
                handler.send_raw(make_message(MSG_LOCK_GRANT, username=username))
            self.broadcast_user_list()
            logging.info(f"[{timestamp()}] Lock granted to '{username}' in room '{self.name}'")
        else:
            # Queue the request
            if username not in self.lock_queue:
                self.lock_queue.append(username)
                logging.info(f"[{timestamp()}] Lock queued for '{username}' in room '{self.name}' (owner: {self.lock_owner})")

    def release_lock(self, username: str):
        """Release the lock held by a user."""
        if self.lock_owner == username:
            self.lock_owner = None
            logging.info(f"[{timestamp()}] Lock released by '{username}' in room '{self.name}'")
            self.broadcast(make_message(MSG_LOCK_RELEASE, username=username))
            self._grant_next_lock()
            self.broadcast_user_list()

    def _grant_next_lock(self):
        """Grant lock to the next user in the queue."""
        while self.lock_queue:
            next_user = self.lock_queue.pop(0)
            if next_user in self.clients:
                self.lock_owner = next_user
                handler = self.clients[next_user]
                try:
                    handler.send_raw(make_message(MSG_LOCK_GRANT, username=next_user))
                except Exception:
                    self.lock_owner = None
                    continue
                logging.info(f"[{timestamp()}] Lock granted to '{next_user}' in room '{self.name}'")
                return

    def apply_operation(self, op: dict, client_version: int, username: str) -> Optional[dict]:
        """
        Apply an operation from a client.
        Transforms against concurrent operations, applies to document,
        returns the transformed operation for broadcast, or None if rejected.
        """
        # Get concurrent operations (those after client_version from other users)
        concurrent_ops = [
            h for h in self.operation_history[client_version:]
            if h.get('client_id') != username
        ]

        # Transform the incoming operation against concurrent ops
        transformed = transform_against_list(op, concurrent_ops)
        if transformed is None:
            return None  # became no-op

        # Apply to document and capture deleted char
        deleted_char = self.document.apply_op(transformed)
        if transformed['op_type'] == 'delete' and deleted_char is not None:
            transformed['char'] = deleted_char

        # Bump version and record
        self.version += 1
        record = dict(transformed)
        record['version'] = self.version
        record['client_id'] = username
        self.operation_history.append(record)

        # Persist
        self.save_document()

        return record

    def undo_operation(self, username: str) -> Optional[dict]:
        """
        Undo the last operation from the given user.
        Transforms the inverse against concurrent operations.
        Returns the inverse operation to broadcast, or None.
        """
        # Find the last operation from this user
        target_idx = None
        for i in range(len(self.operation_history) - 1, -1, -1):
            op = self.operation_history[i]
            if op.get('client_id') == username:
                target_idx = i
                break

        if target_idx is None:
            return None

        original = self.operation_history[target_idx]

        # Create inverse operation
        inverse = None
        if original['op_type'] == 'insert':
            inverse = {
                'op_type': 'delete',
                'flat_pos': original['flat_pos'],
                'char': original.get('char', ''),
            }
        elif original['op_type'] == 'delete':
            inverse = {
                'op_type': 'insert',
                'flat_pos': original['flat_pos'],
                'char': original.get('char', ''),
            }

        if inverse is None:
            return None

        # Get concurrent operations that happened after the original
        concurrent = self.operation_history[target_idx + 1:]

        # Transform the inverse against all concurrent ops
        transformed = transform_against_list(inverse, concurrent)

        if transformed is None:
            return None  # became no-op

        # Apply to document
        self.document.apply_op(transformed)

        # Record
        self.version += 1
        record = dict(transformed)
        record['version'] = self.version
        record['client_id'] = username
        record['undo'] = True
        self.operation_history.append(record)
        self.save_document()

        return record


# ---------------------------------------------------------------------------
# Client Handler
# ---------------------------------------------------------------------------

class ClientHandler:
    """Handles one connected client."""

    def __init__(self, sock: socket.socket, addr: tuple, server: 'Server'):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.username: Optional[str] = None
        self.room: Optional[Room] = None
        self.cursor_line = 0
        self.cursor_col = 0
        self.running = True
        self.send_lock = threading.Lock()

    def send_raw(self, data: bytes):
        """Thread-safe send."""
        with self.send_lock:
            try:
                self.sock.sendall(data)
            except Exception:
                self.running = False

    def handle(self):
        """Main client handling loop."""
        try:
            self.sock.settimeout(1.0)
            buffer = b""
            while self.running:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        break
                    buffer += data
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        self._process_message(line)
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            self._disconnect()

    def _process_message(self, data: bytes):
        msg = parse_message(data)
        if msg is None:
            return

        msg_type = msg.get('type')

        if msg_type == MSG_CONNECT:
            self._handle_connect(msg)
        elif msg_type == MSG_OPERATION:
            self._handle_operation(msg)
        elif msg_type == MSG_CURSOR_UPDATE:
            self._handle_cursor(msg)
        elif msg_type == MSG_LOCK_REQUEST:
            self._handle_lock_request(msg)
        elif msg_type == MSG_LOCK_RELEASE:
            self._handle_lock_release(msg)
        elif msg_type == MSG_SAVE_REQUEST:
            self._handle_save_request(msg)
        elif msg_type == MSG_DISCONNECT:
            self.running = False

    def _handle_connect(self, msg: dict):
        username = msg.get('username', '').strip()
        room_name = msg.get('room', '').strip()
        password = msg.get('password', '')

        if not username or not room_name:
            self.send_raw(make_message(MSG_ERROR, message="Username and room are required."))
            self.running = False
            return

        # Validate room password
        room = self.server.get_room(room_name)
        if room is None:
            self.send_raw(make_message(MSG_ERROR, message=f"Room '{room_name}' not configured."))
            self.running = False
            return

        if room.password and room.password != password:
            self.send_raw(make_message(MSG_ERROR, message="Invalid password."))
            self.running = False
            return

        # Check for duplicate username in room
        if username in room.clients:
            # Allow reconnection – kick old client
            old = room.clients[username]
            old.running = False
            try:
                old.send_raw(make_message(MSG_ERROR, message="You were disconnected because you reconnected from another client."))
                old.sock.close()
            except Exception:
                pass

        self.username = username
        self.room = room
        room.add_client(username, self)

        logging.info(f"[{timestamp()}] {username} connected to room '{room_name}' from {self.addr}")

        # Send full document sync
        doc_text = room.document.get_text()
        self.send_raw(make_message(
            MSG_ACK,
            message="Connected.",
            username=username,
            room=room_name,
            document=doc_text,
            version=room.version,
            lock_owner=room.lock_owner,
        ))

        # Broadcast user list update
        room.broadcast_user_list()

        # Notify others
        room.broadcast(
            make_message(MSG_CONNECT, username=username, message=f"{username} joined."),
            exclude=username
        )

    def _handle_operation(self, msg: dict):
        if not self.room or not self.username:
            return

        op_type = msg.get('op_type')
        flat_pos = msg.get('flat_pos')
        char = msg.get('char')
        client_version = msg.get('version', 0)
        undo_requested = msg.get('undo', False)

        if undo_requested:
            # Undo bypasses lock - you can always undo your own operations
            result = self.room.undo_operation(self.username)
            if result:
                self.room.broadcast(make_message(
                    MSG_OPERATION,
                    op_type=result['op_type'],
                    flat_pos=result['flat_pos'],
                    char=result.get('char', ''),
                    version=self.room.version,
                    client_id=self.username,
                    undo=True,
                ))
                logging.info(
                    f"[{timestamp()}] Undo by '{self.username}' in '{self.room.name}': "
                    f"{result['op_type']} at {result['flat_pos']}"
                )
            return

        # Check lock for normal operations
        if self.room.lock_owner and self.room.lock_owner != self.username:
            self.send_raw(make_message(MSG_ERROR, message="Document is locked by another user."))
            return

        if op_type not in ('insert', 'delete'):
            return

        if op_type == 'delete' and flat_pos is None:
            return
        if op_type == 'insert' and (flat_pos is None or char is None):
            return

        operation = {
            'op_type': op_type,
            'flat_pos': flat_pos,
        }
        if op_type == 'insert':
            operation['char'] = char

        result = self.room.apply_operation(operation, client_version, self.username)
        if result is None:
            return  # became no-op

        # Broadcast to all clients including sender
        broadcast_msg = make_message(
            MSG_OPERATION,
            op_type=result['op_type'],
            flat_pos=result['flat_pos'],
            char=result.get('char', ''),
            version=self.room.version,
            client_id=self.username,
            undo=result.get('undo', False),
        )
        self.room.broadcast(broadcast_msg)

        logging.info(
            f"[{timestamp()}] Op by '{self.username}' in '{self.room.name}': "
            f"{result['op_type']} at {result['flat_pos']} v{self.room.version}"
        )

    def _handle_cursor(self, msg: dict):
        if not self.room or not self.username:
            return
        self.cursor_line = msg.get('line', 0)
        self.cursor_col = msg.get('col', 0)
        # Broadcast cursor update to others
        self.room.broadcast(
            make_message(
                MSG_CURSOR_UPDATE,
                username=self.username,
                line=self.cursor_line,
                col=self.cursor_col,
            ),
            exclude=self.username
        )

    def _handle_lock_request(self, msg: dict):
        if not self.room or not self.username:
            return
        self.room.request_lock(self.username)

    def _handle_lock_release(self, msg: dict):
        if not self.room or not self.username:
            return
        self.room.release_lock(self.username)

    def _handle_save_request(self, msg: dict):
        if not self.room or not self.username:
            return
        self.room.save_document()
        self.send_raw(make_message(MSG_SAVE_ACK, message="Document saved."))
        logging.info(f"[{timestamp()}] Save requested by '{self.username}' in '{self.room.name}'")

    def _disconnect(self):
        self.running = False
        if self.room and self.username:
            logging.info(f"[{timestamp()}] {self.username} disconnected from room '{self.room.name}'")
            self.room.remove_client(self.username)
            self.room.broadcast(
                make_message(MSG_DISCONNECT, username=self.username, message=f"{self.username} left."),
            )
            self.room.broadcast_user_list()
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class Server:
    """Main server accepting client connections."""

    def __init__(self, port: int, config_path: str = "config.json", data_dir: str = "data"):
        self.port = port
        self.data_dir = data_dir
        self.rooms: dict[str, Room] = {}
        self.running = True
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load room configuration from JSON file."""
        if not os.path.exists(config_path):
            logging.warning(f"[{timestamp()}] Config file '{config_path}' not found. No rooms configured.")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logging.error(f"[{timestamp()}] Failed to load config: {e}")
            return

        rooms_cfg = config.get('rooms', {})
        for room_name, room_cfg in rooms_cfg.items():
            if isinstance(room_cfg, str):
                password = room_cfg
            elif isinstance(room_cfg, dict):
                password = room_cfg.get('password', '')
            else:
                password = ''
            self.rooms[room_name] = Room(room_name, password, self.data_dir)

        logging.info(f"[{timestamp()}] Loaded {len(self.rooms)} rooms from config.")

    def get_room(self, name: str) -> Optional[Room]:
        """Get or create a room. Rooms not in config can be created without password."""
        if name not in self.rooms:
            # Auto-create room with empty password
            self.rooms[name] = Room(name, '', self.data_dir)
        return self.rooms[name]

    def start(self):
        """Start listening for connections."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.listen(50)
        self.sock.settimeout(1.0)
        logging.info(f"[{timestamp()}] Server listening on port {self.port}")

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # Load any existing documents for configured rooms
        for room in self.rooms.values():
            room.save_document()  # Creates empty file if doesn't exist

        try:
            while self.running:
                try:
                    client_sock, addr = self.sock.accept()
                    logging.info(f"[{timestamp()}] Connection from {addr}")
                    handler = ClientHandler(client_sock, addr, self)
                    t = threading.Thread(target=handler.handle, daemon=True)
                    t.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logging.error(f"[{timestamp()}] Accept error: {e}")
        finally:
            self.sock.close()

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Server")
    parser.add_argument('--port', type=int, default=9999, help="TCP port to listen on")
    parser.add_argument('--config', type=str, default='config.json', help="Server config JSON file")
    parser.add_argument('--data-dir', type=str, default='data', help="Directory for persisted documents")
    parser.add_argument('--log-file', type=str, default='server.log', help="Log file path")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(args.log_file),
            logging.StreamHandler(sys.stdout),
        ]
    )

    server = Server(port=args.port, config_path=args.config, data_dir=args.data_dir)
    logging.info(f"[{timestamp()}] Server starting on port {args.port}")

    try:
        server.start()
    except KeyboardInterrupt:
        logging.info(f"[{timestamp()}] Server shutting down.")
    finally:
        server.stop()


if __name__ == '__main__':
    main()
