"""
Collaborative Text Editor Server.

Handles client connections, room management, Operational Transformation,
lock management, persistence, and logging.

Usage: python server.py --config server_config.json
"""

import socket
import threading
import json
import time
import os
import sys
import argparse
import traceback
from datetime import datetime
from protocol import *
from ot import *


class ClientInfo:
    """Information about a connected client."""
    def __init__(self, client_id, username, sock):
        self.client_id = client_id
        self.username = username
        self.sock = sock
        self.cursor_row = 0
        self.cursor_col = 0
        self.last_version = 0
        self.connected = True


class Room:
    """A collaborative editing room with a shared document."""
    def __init__(self, name, password, filepath):
        self.name = name
        self.password = password
        self.filepath = filepath
        self.document = ""
        self.version = 0
        self.clients = {}  # client_id -> ClientInfo
        self.lock_queue = []  # list of client_ids waiting for lock
        self.lock_holder = None  # client_id that holds the lock
        self.operation_history = {}  # client_id -> list of (ops, inverse_ops, doc_before)
        self.version_history = []  # list of ops at each version (index = version)
        self.lock = threading.Lock()

        # Load existing document from disk
        self._load_document()

    def _load_document(self):
        """Load document from disk if it exists."""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.document = f.read()
        except Exception as e:
            print(f"Warning: Could not load document for room '{self.name}': {e}")

    def _save_document(self):
        """Persist document to disk."""
        try:
            os.makedirs(os.path.dirname(self.filepath) if os.path.dirname(self.filepath) else '.', exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(self.document)
        except Exception as e:
            print(f"Error saving document for room '{self.name}': {e}")

    def add_client(self, client_info):
        """Add a client to the room."""
        with self.lock:
            self.clients[client_info.client_id] = client_info
            client_info.last_version = self.version

    def remove_client(self, client_id):
        """Remove a client from the room."""
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
            # Release lock if held by this client
            if self.lock_holder == client_id:
                self.lock_holder = None
                self._process_lock_queue()
            # Clean up operation history
            if client_id in self.operation_history:
                del self.operation_history[client_id]
            # Remove from lock queue
            if client_id in self.lock_queue:
                self.lock_queue.remove(client_id)

    def get_clients_list(self):
        """Get a list of client info dicts for sending to clients."""
        with self.lock:
            return [
                {
                    'client_id': cid,
                    'username': info.username,
                    'cursor_row': info.cursor_row,
                    'cursor_col': info.cursor_col
                }
                for cid, info in self.clients.items()
                if info.connected
            ]

    def process_operation(self, client_id, ops, base_version):
        """Process an operation from a client.

        Returns (transformed_ops, new_version, error_msg) where error_msg is None on success.
        """
        with self.lock:
            # Check lock
            if self.lock_holder is not None and self.lock_holder != client_id:
                return None, self.version, "Document is locked by another user"

            if client_id not in self.clients:
                return None, self.version, "Client not in room"

            client = self.clients[client_id]

            # Transform incoming ops against any ops between base_version and current version
            ops_to_apply = [op.copy() for op in ops]
            if base_version < self.version and self.version_history:
                # Get ops that happened after base_version
                against_ops = []
                for v in range(base_version, self.version):
                    if v < len(self.version_history):
                        against_ops.extend(self.version_history[v])
                if against_ops:
                    ops_to_apply = transform_batch(ops_to_apply, against_ops)

            if not ops_to_apply:
                return [], self.version, None

            # Validate positions
            for op in ops_to_apply:
                if op['op'] == 'insert':
                    if op['pos'] < 0 or op['pos'] > len(self.document):
                        return None, self.version, f"Invalid insert position: {op['pos']}"
                elif op['op'] == 'delete':
                    if op['pos'] < 0 or op['pos'] >= len(self.document):
                        return None, self.version, f"Invalid delete position: {op['pos']}"

            # Compute inverses for undo (before applying)
            inverses = []
            doc_before = self.document
            for op in ops_to_apply:
                inv = invert_op(doc_before, op)
                if inv:
                    inverses.append(inv)
                doc_before = apply_op(doc_before, op)

            # Store in operation history for undo
            if client_id not in self.operation_history:
                self.operation_history[client_id] = []
            self.operation_history[client_id].append((ops_to_apply, inverses, self.document))

            # Apply operations
            for op in ops_to_apply:
                self.document = apply_op(self.document, op)

            # Update version
            self.version += 1
            self.version_history.append(ops_to_apply)

            # Update client version
            client.last_version = self.version

            # Persist to disk
            self._save_document()

            return ops_to_apply, self.version, None

    def process_undo(self, client_id):
        """Process an undo request from a client.

        Returns (ops_to_broadcast, error_msg).
        """
        with self.lock:
            # Check lock
            if self.lock_holder is not None and self.lock_holder != client_id:
                return None, "Document is locked by another user"

            if client_id not in self.clients:
                return None, "Client not in room"

            if client_id not in self.operation_history or not self.operation_history[client_id]:
                return None, "No operations to undo"

            # Pop the last operation from this client
            original_ops, inverse_ops, _ = self.operation_history[client_id].pop()

            # Apply inverse operations
            for op in inverse_ops:
                self.document = apply_op(self.document, op)

            # Update version
            self.version += 1
            self.version_history.append(inverse_ops)

            # Update all clients' last_version? No, just the version moves forward.

            # Persist
            self._save_document()

            return inverse_ops, None

    def request_lock(self, client_id):
        """Request the edit lock. Returns (granted, queue_position)."""
        with self.lock:
            if client_id not in self.clients:
                return False, -1

            if self.lock_holder == client_id:
                return True, 0  # Already holds lock

            if client_id in self.lock_queue:
                return False, self.lock_queue.index(client_id) + 1

            self.lock_queue.append(client_id)

            if self.lock_holder is None:
                self._process_lock_queue()
                if self.lock_holder == client_id:
                    return True, 0

            return False, self.lock_queue.index(client_id) + 1 if client_id in self.lock_queue else -1

    def release_lock(self, client_id):
        """Release the edit lock."""
        with self.lock:
            if self.lock_holder == client_id:
                self.lock_holder = None
                # Remove from queue if present
                if client_id in self.lock_queue:
                    self.lock_queue.remove(client_id)
                self._process_lock_queue()
                return True
            # Remove from queue even if not holder
            if client_id in self.lock_queue:
                self.lock_queue.remove(client_id)
            return False

    def _process_lock_queue(self):
        """Grant lock to the next client in the queue."""
        if self.lock_holder is not None:
            return
        # Clean up disconnected clients from queue
        self.lock_queue = [cid for cid in self.lock_queue if cid in self.clients]
        if self.lock_queue:
            next_client_id = self.lock_queue.pop(0)
            if next_client_id in self.clients:
                self.lock_holder = next_client_id

    def update_cursor(self, client_id, row, col):
        """Update a client's cursor position."""
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id].cursor_row = row
                self.clients[client_id].cursor_col = col


class Server:
    """Main server managing rooms and client connections."""

    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.port = self.config.get('port', 9999)
        self.rooms_config = self.config.get('rooms', {})
        self.log_file_path = self.config.get('log_file', 'server.log')
        self.persist_dir = self.config.get('persist_dir', './documents')

        # Initialize rooms
        self.rooms = {}  # room_name -> Room
        for room_name, room_cfg in self.rooms_config.items():
            password = room_cfg.get('password', '')
            filename = room_cfg.get('file', f'{room_name}.txt')
            filepath = os.path.join(self.persist_dir, filename)
            self.rooms[room_name] = Room(room_name, password, filepath)

        # Ensure there's always a default room
        if 'default' not in self.rooms:
            filepath = os.path.join(self.persist_dir, 'default.txt')
            self.rooms['default'] = Room('default', '', filepath)

        self.next_client_id = 0
        self.client_id_lock = threading.Lock()
        self.running = True

        # Open log file
        try:
            self.log_file = open(self.log_file_path, 'a', encoding='utf-8')
        except (PermissionError, FileNotFoundError):
            import tempfile
            self.log_file_path = os.path.join(tempfile.gettempdir(), 'collab_editor_server.log')
            self.log_file = open(self.log_file_path, 'a', encoding='utf-8')
        self.log("Server initialized")

    def log(self, message):
        """Write a timestamped log entry."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        entry = f"[{timestamp}] {message}\n"
        try:
            self.log_file.write(entry)
            self.log_file.flush()
        except Exception:
            pass
        print(entry, end='')

    def get_next_client_id(self):
        """Generate a unique client ID."""
        with self.client_id_lock:
            cid = f"client_{self.next_client_id}"
            self.next_client_id += 1
            return cid

    def start(self):
        """Start the server and listen for connections."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', self.port))
        server_sock.listen(20)
        server_sock.settimeout(1.0)

        self.log(f"Server listening on port {self.port}")

        try:
            while self.running:
                try:
                    client_sock, addr = server_sock.accept()
                    self.log(f"New connection from {addr[0]}:{addr[1]}")
                    thread = threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True)
                    thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log(f"Error accepting connection: {e}")
        except KeyboardInterrupt:
            self.log("Server shutting down...")
        finally:
            self.running = False
            server_sock.close()
            self.log_file.close()

    def handle_client(self, sock, addr):
        """Handle a connected client."""
        client_id = None
        room = None
        buffer = b""

        try:
            # First message must be connect
            while b'\n' not in buffer:
                data = sock.recv(4096)
                if not data:
                    return
                buffer += data

            line, buffer = buffer.split(b'\n', 1)
            msg = decode_message(line.decode('utf-8'))

            if msg.get('type') != MSG_CONNECT:
                sock.send(encode_message(make_error("First message must be 'connect'")).encode('utf-8'))
                sock.close()
                return

            username = msg.get('username', 'anonymous')
            room_name = msg.get('room', 'default')
            password = msg.get('password', '')

            # Validate room
            if room_name not in self.rooms:
                sock.send(encode_message(make_error(f"Room '{room_name}' does not exist")).encode('utf-8'))
                sock.close()
                return

            room = self.rooms[room_name]

            # Validate password
            if room.password and room.password != password:
                sock.send(encode_message(make_error("Invalid password")).encode('utf-8'))
                sock.close()
                self.log(f"Failed login attempt: user='{username}' room='{room_name}' from {addr}")
                return

            # Create client
            client_id = self.get_next_client_id()
            client_info = ClientInfo(client_id, username, sock)
            room.add_client(client_info)

            self.log(f"Client connected: id={client_id}, username='{username}', room='{room_name}' from {addr}")

            # Send ack with full document state
            clients_list = room.get_clients_list()
            ack_msg = make_ack(client_id, room.document, room.version, clients_list, room.lock_holder)
            sock.send(encode_message(ack_msg).encode('utf-8'))

            # Notify other clients about the new user
            join_msg = make_user_join(client_id, username, 0, 0)
            self.broadcast_to_room(room, join_msg, exclude_client=client_id)

            # Main message loop
            while self.running:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    buffer += data

                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        msg = decode_message(line.decode('utf-8'))
                        self.handle_message(room, client_id, msg, sock)

                except socket.timeout:
                    continue
                except Exception as e:
                    self.log(f"Error handling message from {client_id}: {e}")
                    traceback.print_exc()
                    break

        except Exception as e:
            self.log(f"Client handler error for {addr}: {e}")
            traceback.print_exc()

        finally:
            # Cleanup
            if client_id and room:
                self.log(f"Client disconnected: id={client_id}, username='{client_info.username if 'client_info' in dir() else 'unknown'}'")
                room.remove_client(client_id)

                # Notify others
                leave_msg = make_user_leave(client_id, client_info.username if 'client_info' in dir() else 'unknown')
                self.broadcast_to_room(room, leave_msg, exclude_client=client_id)

                # Broadcast lock status change if needed
                status_msg = make_lock_status(room.lock_holder, list(room.lock_queue))
                self.broadcast_to_room(room, status_msg)

            try:
                sock.close()
            except Exception:
                pass

    def handle_message(self, room, client_id, msg, sock):
        """Process a message from a client."""
        msg_type = msg.get('type')

        if msg_type == MSG_OPERATION:
            ops = msg.get('ops', [])
            base_version = msg.get('base_version', 0)

            self.log(f"Operation from {client_id}: {ops}, base_version={base_version}")

            transformed_ops, new_version, error = room.process_operation(client_id, ops, base_version)

            if error:
                sock.send(encode_message(make_error(error)).encode('utf-8'))
                return

            # Always broadcast the confirmed operation to ALL clients (including sender)
            # Even if ops are empty (no-op), the sender needs to know their op was processed
            op_msg = {
                'type': MSG_OPERATION,
                'ops': transformed_ops,
                'version': new_version,
                'client_id': client_id
            }
            self.broadcast_to_room(room, op_msg)

        elif msg_type == MSG_CURSOR_UPDATE:
            row = msg.get('row', 0)
            col = msg.get('col', 0)
            room.update_cursor(client_id, row, col)

            # Broadcast to all other clients
            username = room.clients[client_id].username if client_id in room.clients else 'unknown'
            cursor_msg = make_cursor_update(client_id, username, row, col)
            self.broadcast_to_room(room, cursor_msg, exclude_client=client_id)

        elif msg_type == MSG_LOCK_REQUEST:
            self.log(f"Lock request from {client_id}")
            granted, queue_pos = room.request_lock(client_id)

            if granted:
                lock_msg = make_lock_grant(client_id, room.lock_holder)
                self.log(f"Lock granted to {client_id}")
            else:
                lock_msg = make_lock_status(room.lock_holder, list(room.lock_queue))

            # Send response to requester
            sock.send(encode_message(lock_msg).encode('utf-8'))

            # Broadcast lock status to all
            status_msg = make_lock_status(room.lock_holder, list(room.lock_queue))
            self.broadcast_to_room(room, status_msg)

        elif msg_type == MSG_LOCK_RELEASE:
            self.log(f"Lock release from {client_id}")
            room.release_lock(client_id)

            # Broadcast new lock status
            status_msg = make_lock_status(room.lock_holder, list(room.lock_queue))
            self.broadcast_to_room(room, status_msg)

        elif msg_type == MSG_SAVE_REQUEST:
            self.log(f"Save request from {client_id}")
            room._save_document()
            sock.send(encode_message(make_save_ack()).encode('utf-8'))

        elif msg_type == MSG_UNDO:
            self.log(f"Undo request from {client_id}")
            inverse_ops, error = room.process_undo(client_id)

            if error:
                sock.send(encode_message(make_error(error)).encode('utf-8'))
            elif inverse_ops:
                # Broadcast the inverse operations
                op_msg = {
                    'type': MSG_OPERATION,
                    'ops': inverse_ops,
                    'version': room.version,
                    'client_id': client_id,
                    'is_undo': True
                }
                self.broadcast_to_room(room, op_msg)

        elif msg_type == MSG_DISCONNECT:
            self.log(f"Disconnect request from {client_id}")
            # Will be handled by finally block in handle_client
            raise ConnectionError("Client requested disconnect")

        else:
            self.log(f"Unknown message type from {client_id}: {msg_type}")
            sock.send(encode_message(make_error(f"Unknown message type: {msg_type}")).encode('utf-8'))

    def broadcast_to_room(self, room, msg, exclude_client=None):
        """Send a message to all clients in a room, optionally excluding one."""
        data = encode_message(msg).encode('utf-8')
        with room.lock:
            for cid, client in list(room.clients.items()):
                if cid == exclude_client:
                    continue
                try:
                    client.sock.send(data)
                except Exception as e:
                    self.log(f"Error sending to {cid}: {e}")
                    # Will be cleaned up when their handler thread exits


def main():
    parser = argparse.ArgumentParser(description='Collaborative Text Editor Server')
    parser.add_argument('--config', default='server_config.json', help='Path to server config JSON file')
    parser.add_argument('--port', type=int, default=None, help='Override port from config file')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Config file '{args.config}' not found. Creating default config.")
        default_config = {
            "port": 9999,
            "rooms": {
                "default": {
                    "password": "",
                    "file": "default.txt"
                },
                "python": {
                    "password": "py123",
                    "file": "code.py"
                }
            },
            "log_file": "server.log",
            "persist_dir": "./documents"
        }
        os.makedirs(os.path.dirname(args.config) if os.path.dirname(args.config) else '.', exist_ok=True)
        with open(args.config, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        print(f"Default config written to '{args.config}'")

    server = Server(args.config)
    if args.port:
        server.port = args.port

    server.start()


if __name__ == '__main__':
    main()
