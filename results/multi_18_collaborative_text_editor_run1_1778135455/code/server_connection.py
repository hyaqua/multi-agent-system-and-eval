"""
Per-connection client handler thread for the collaborative editor server.
"""

import socket
import threading
import logging
import json

import protocol
import config as cfg

logger = logging.getLogger("server.connection")


class ClientHandler(threading.Thread):
    """Handles one client connection in a dedicated thread."""

    def __init__(self, sock: socket.socket, addr: tuple, rooms: dict,
                 server_config: dict):
        super().__init__(daemon=True)
        self.sock = sock
        self.addr = addr
        self.rooms = rooms  # dict of room_name -> Room
        self.config = server_config
        self.user: str | None = None
        self.room_name: str | None = None
        self.room = None
        self.running = True
        self._send_lock = threading.Lock()

    def run(self):
        """Main loop: read lines, dispatch messages."""
        logger.info("Connection from %s:%d", *self.addr)
        buffer = b""
        try:
            while self.running:
                data = self.sock.recv(4096)
                if not data:
                    logger.info("Client %s disconnected (EOF)", self.user or self.addr)
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        self._handle_line(line)
        except ConnectionResetError:
            logger.info("Client %s connection reset", self.user or self.addr)
        except OSError as e:
            logger.error("Socket error for %s: %s", self.user or self.addr, e)
        finally:
            self._cleanup()

    def _handle_line(self, line: bytes):
        """Parse and dispatch a single message."""
        msg = protocol.decode_message(line)
        if msg is None:
            self._send_error("Invalid JSON")
            return

        msg_type = msg.get("type", "")

        if msg_type == protocol.TYPE_CONNECT:
            self._handle_connect(msg)
        elif msg_type == protocol.TYPE_OPERATION:
            self._handle_operation(msg)
        elif msg_type == protocol.TYPE_CURSOR_UPDATE:
            self._handle_cursor_update(msg)
        elif msg_type == protocol.TYPE_LOCK_REQUEST:
            self._handle_lock_request(msg)
        elif msg_type == protocol.TYPE_LOCK_RELEASE:
            self._handle_lock_release(msg)
        elif msg_type == protocol.TYPE_SAVE_REQUEST:
            self._handle_save_request()
        elif msg_type == protocol.TYPE_UNDO_REQUEST:
            self._handle_undo_request(msg)
        elif msg_type == protocol.TYPE_DISCONNECT:
            self.running = False
        else:
            self._send_error(f"Unknown message type: {msg_type}")

    def _handle_connect(self, msg: dict):
        """Authenticate and join a room."""
        user = msg.get("user", "").strip()
        room_name = msg.get("room", "").strip()
        password = msg.get("password", "")

        if not user or not room_name:
            self._send(protocol.make_error("User and room required"))
            return

        # Check room exists
        if not cfg.room_exists(self.config, room_name):
            self._send(protocol.make_error(f"Room '{room_name}' does not exist"))
            return

        # Verify password
        expected_pw = cfg.get_room_password(self.config, room_name)
        if expected_pw is None:
            self._send(protocol.make_error(f"Room '{room_name}' not configured"))
            return
        if expected_pw and password != expected_pw:
            self._send(protocol.make_error("Invalid password"))
            return

        # Get or create room
        if room_name not in self.rooms:
            from server_room import Room
            self.rooms[room_name] = Room(room_name)

        room = self.rooms[room_name]

        # Check for duplicate user (kick old connection)
        if user in room.clients:
            old_handler = room.clients[user].get("handler")
            if old_handler and old_handler is not self:
                old_handler.running = False
                try:
                    old_handler.sock.close()
                except OSError:
                    pass
                logger.info("Kicked old connection for user '%s'", user)

        self.user = user
        self.room_name = room_name
        self.room = room

        # Register client
        color = room.add_client(user)
        room.clients[user]["handler"] = self

        # Send ack
        ack = protocol.make_ack(
            status="ok",
            document=room.document,
            clients=room.get_clients_list(),
            version=room.version,
            lock_holder=room.lock_holder,
            user_color=color,
        )
        self._send(ack)

        # Broadcast join to others
        join_msg = protocol.make_user_join(user, color)
        self._broadcast(join_msg, exclude_self=True)

        logger.info("User '%s' joined room '%s' (color %d)", user, room_name, color)

    def _handle_operation(self, msg: dict):
        """Process an edit operation."""
        if not self.room or not self.user:
            self._send_error("Not connected to a room")
            return

        ack, broadcast = self.room.process_operation(msg, self.user)
        if ack is not None:
            if ack.get("type") == protocol.TYPE_ERROR:
                self._send(ack)
            else:
                self._send(ack)
        if broadcast is not None:
            self._broadcast(broadcast)

    def _handle_cursor_update(self, msg: dict):
        """Update cursor position and broadcast."""
        if not self.room or not self.user:
            return
        pos = msg.get("pos", 0)
        self.room.update_cursor(self.user, pos)
        # Broadcast to others
        cursor_msg = protocol.make_cursor_update(self.user, pos)
        self._broadcast(cursor_msg, exclude_self=True)

    def _handle_lock_request(self, msg: dict):
        if not self.room or not self.user:
            return

        grant, status = self.room.request_lock(self.user)
        if grant:
            self._send(grant)
        if status:
            self._broadcast(status)

    def _handle_lock_release(self, msg: dict):
        if not self.room or not self.user:
            return

        status = self.room.release_lock(self.user)
        if status:
            self._broadcast(status)
            # If new holder, send them a grant too
            new_holder = status.get("holder")
            if new_holder and new_holder in self.room.clients:
                new_handler = self.room.clients[new_holder].get("handler")
                if new_handler:
                    new_handler._send(protocol.make_lock_grant(new_holder))

    def _handle_save_request(self):
        if not self.room:
            return
        self.room.save_to_disk()
        self._send(protocol.make_save_ack())

    def _handle_undo_request(self, msg: dict):
        if not self.room or not self.user:
            return
        broadcast = self.room.process_undo(self.user)
        if broadcast:
            self._broadcast(broadcast)

    def _send(self, msg: dict):
        """Send a message to this client."""
        with self._send_lock:
            try:
                data = protocol.encode_message(msg)
                self.sock.sendall(data)
            except OSError as e:
                logger.error("Send error to %s: %s", self.user or self.addr, e)
                self.running = False

    def _send_error(self, message: str):
        self._send(protocol.make_error(message))

    def _broadcast(self, msg: dict, exclude_self: bool = False):
        """Send a message to all clients in the room."""
        if not self.room:
            return
        with self.room.lock:
            clients = dict(self.room.clients)
        for user, info in clients.items():
            if exclude_self and user == self.user:
                continue
            handler = info.get("handler")
            if handler and handler.running:
                handler._send(msg)

    def _cleanup(self):
        """Remove client from room and close socket."""
        self.running = False
        if self.room and self.user:
            self.room.remove_client(self.user)
            # Broadcast leave
            leave_msg = protocol.make_user_leave(self.user)
            with self.room.lock:
                clients = dict(self.room.clients)
            for user, info in clients.items():
                handler = info.get("handler")
                if handler and handler.running:
                    handler._send(leave_msg)
        try:
            self.sock.close()
        except OSError:
            pass
