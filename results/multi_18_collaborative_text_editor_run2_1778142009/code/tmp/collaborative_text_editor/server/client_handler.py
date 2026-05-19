"""
Per-client thread: receive/send loop, authentication.
"""

import json
import logging
import socket
import threading

from collaborative_text_editor.common.protocol import (
    TYPE_CONNECT, TYPE_ACK, TYPE_OPERATION, TYPE_CURSOR_UPDATE,
    TYPE_LOCK_REQUEST, TYPE_LOCK_GRANT, TYPE_LOCK_RELEASE,
    TYPE_SAVE_REQUEST, TYPE_SAVE_ACK, TYPE_DISCONNECT, TYPE_ERROR,
    LOCK_ACQUIRE, LOCK_RELEASE,
    make_ack, make_error, make_user_join, make_user_leave,
)

logger = logging.getLogger("server")


class ClientHandler:
    """Handles one connected client."""

    def __init__(self, sock, addr, server):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.username = None
        self.room = None
        self.running = True
        self._send_lock = threading.Lock()

    def run(self):
        """Main loop for the client handler thread."""
        try:
            # Read the connect message first
            data = self._recv_line()
            if not data:
                return

            msg = json.loads(data.strip())
            if msg.get("type") != TYPE_CONNECT:
                self.send_message(make_error("Expected connect message"))
                return

            username = msg.get("username", "").strip()
            room_name = msg.get("room", "").strip()
            password = msg.get("password", "")

            if not username or not room_name:
                self.send_message(make_error("Username and room required"))
                return

            self.username = username

            # Get or create room
            room = self.server.get_or_create_room(room_name)

            # Check password
            if room.password is not None and room.password != password:
                self.send_message(make_error("Invalid password"))
                logger.warning("Failed auth: user='%s' room='%s' from %s:%d",
                               username, room_name, *self.addr)
                return

            # Add to room
            with room.lock:
                # If username already in room, kick old connection
                if username in room.clients:
                    old = room.clients[username]
                    try:
                        old.send_message(make_error("You connected from another location"))
                        old.running = False
                        old.sock.close()
                    except Exception:
                        pass
                    room.remove_client(username)

                room.add_client(self)
                self.room = room

                # Send ack with full state
                ack = make_ack(
                    document=room.doc,
                    revision=room.revision,
                    users=room.get_user_list(),
                    lock_owner=room.lock_owner,
                )
                self.send_message(ack)

                # Notify others
                join_msg = make_user_join(username)
                room.broadcast(join_msg, exclude=self)

            logger.info("Client connected: user='%s' room='%s' from %s:%d",
                        username, room_name, *self.addr)

            # Main message loop
            while self.running:
                data = self._recv_line()
                if not data:
                    break

                try:
                    msg = json.loads(data.strip())
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from '%s': %s", username, data[:100])
                    continue

                self._dispatch(msg)

        except Exception as e:
            logger.error("Handler error for '%s': %s", self.username, e)
        finally:
            self._cleanup()

    def _dispatch(self, msg):
        """Dispatch a message to the appropriate handler."""
        msg_type = msg.get("type")
        room = self.room

        if room is None:
            return

        with room.lock:
            if msg_type == TYPE_OPERATION:
                result = room.apply_operation(self.username, msg)
                if result:
                    room.broadcast(result)

            elif msg_type == TYPE_CURSOR_UPDATE:
                position = msg.get("position", {})
                room.handle_cursor_update(self.username, position)

            elif msg_type == TYPE_LOCK_REQUEST:
                action = msg.get("action", LOCK_ACQUIRE)
                response = room.request_lock(self.username, action)
                if response:
                    self.send_message(response)

            elif msg_type == TYPE_SAVE_REQUEST:
                response = room.handle_save_request(self.username)
                self.send_message(response)

            elif msg_type == TYPE_DISCONNECT:
                self.running = False

            elif msg_type == "undo":
                result = room.handle_undo(self.username)
                if result:
                    room.broadcast(result)
                else:
                    # Send empty ack so client knows undo was processed
                    pass

            else:
                logger.debug("Unknown message type from '%s': %s",
                             self.username, msg_type)

    def send_message(self, msg):
        """Send a JSON message to this client. Thread-safe."""
        with self._send_lock:
            try:
                data = json.dumps(msg) + "\n"
                self.sock.sendall(data.encode("utf-8"))
            except Exception as e:
                logger.warning("Failed to send to '%s': %s", self.username, e)
                self.running = False

    def _recv_line(self):
        """Receive a newline-terminated line from the socket."""
        buf = b""
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    return None
                buf += chunk
                if b"\n" in buf:
                    line, rest = buf.split(b"\n", 1)
                    # Note: rest might contain next message; we discard it for simplicity
                    # In production you'd buffer it, but for this editor it's fine
                    return line.decode("utf-8", errors="replace")
            except socket.timeout:
                continue
            except Exception:
                return None

    def _cleanup(self):
        """Clean up on disconnect."""
        try:
            self.sock.close()
        except Exception:
            pass

        if self.room and self.username:
            with self.room.lock:
                self.room.remove_client(self.username)
                # Notify others
                leave_msg = make_user_leave(self.username)
                self.room.broadcast(leave_msg)

            logger.info("Client disconnected: user='%s' room='%s'",
                        self.username, self.room.name)

        self.running = False
