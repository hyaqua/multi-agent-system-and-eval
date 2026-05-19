"""
Collaborative Text Editor - Client Entry Point

Usage: python -m client.client --user USERNAME --room ROOM [--host HOST] [--port PORT] [--password PASSWORD]
"""

import argparse
import curses
import json
import socket
import sys
import threading
import time

from collaborative_text_editor.common.protocol import (
    TYPE_ACK, TYPE_OPERATION, TYPE_CURSOR_UPDATE,
    TYPE_LOCK_GRANT, TYPE_LOCK_RELEASE, TYPE_SAVE_ACK,
    TYPE_USER_JOIN, TYPE_USER_LEAVE, TYPE_ERROR,
    make_connect, make_operation, make_cursor_update,
    make_lock_request, make_save_request, make_disconnect,
    LOCK_ACQUIRE, LOCK_RELEASE,
)
from collaborative_text_editor.client.editor import Editor
from collaborative_text_editor.client.tui import TUI


class NetworkThread(threading.Thread):
    """Handles network communication with the server."""

    def __init__(self, sock, editor, tui, username, room_name):
        super().__init__(daemon=True)
        self.sock = sock
        self.editor = editor
        self.tui = tui
        self.username = username
        self.room_name = room_name
        self.running = True
        self._send_lock = threading.Lock()

        # Queues for communication with main thread
        self.incoming = []  # list of messages to process
        self.incoming_lock = threading.Lock()

    def run(self):
        """Main network loop."""
        buf = b""
        while self.running:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.tui.set_connected(False)
                    self.tui.show_status("Disconnected from server")
                    break

                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8", errors="replace"))
                        with self.incoming_lock:
                            self.incoming.append(msg)
                    except json.JSONDecodeError:
                        pass
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.tui.set_connected(False)
                    self.tui.show_status(f"Connection error: {e}")
                break

        self.running = False

    def send_message(self, msg):
        """Send a message to the server."""
        with self._send_lock:
            try:
                data = json.dumps(msg) + "\n"
                self.sock.sendall(data.encode("utf-8"))
            except Exception as e:
                self.tui.show_status(f"Send error: {e}")
                self.running = False

    def poll_messages(self):
        """Get all pending incoming messages."""
        with self.incoming_lock:
            msgs = self.incoming
            self.incoming = []
            return msgs

    def stop(self):
        """Stop the network thread."""
        self.running = False
        try:
            self.send_message(make_disconnect(self.username))
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class Client:
    """Main client application."""

    def __init__(self, host, port, username, room_name, password=""):
        self.host = host
        self.port = port
        self.username = username
        self.room_name = room_name
        self.password = password
        self.sock = None
        self.network = None
        self.editor = None
        self.tui = None
        self.last_cursor_send = 0

    def connect(self):
        """Connect to server and authenticate."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(30.0)

        try:
            self.sock.connect((self.host, self.port))
        except Exception as e:
            print(f"Failed to connect to {self.host}:{self.port}: {e}")
            return False

        # Send connect message
        connect_msg = make_connect(self.username, self.room_name, self.password)
        try:
            data = json.dumps(connect_msg) + "\n"
            self.sock.sendall(data.encode("utf-8"))
        except Exception as e:
            print(f"Failed to send connect message: {e}")
            return False

        # Wait for ack or error
        buf = b""
        try:
            while b"\n" not in buf:
                chunk = self.sock.recv(4096)
                if not chunk:
                    print("Server closed connection")
                    return False
                buf += chunk
        except Exception as e:
            print(f"Failed to receive response: {e}")
            return False

        line, rest = buf.split(b"\n", 1)
        try:
            response = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            print("Invalid response from server")
            return False

        if response.get("type") == TYPE_ERROR:
            print(f"Error: {response.get('message', 'Unknown error')}")
            return False

        if response.get("type") != TYPE_ACK:
            print(f"Unexpected response: {response.get('type')}")
            return False

        # Initialize editor with received state
        document = response.get("document", "")
        revision = response.get("revision", 0)
        users = response.get("users", [])
        lock_owner = response.get("lock_owner")

        self.editor = Editor(document=document, revision=revision,
                             username=self.username)

        # Any leftover data
        if rest:
            # Put back for the network thread
            pass

        return True

    def run(self):
        """Main client loop with curses."""
        if not self.sock:
            return

        # Set socket to non-blocking for the network thread
        self.sock.settimeout(0.5)

        def curses_main(stdscr):
            # Initialize TUI
            self.tui = TUI(stdscr, self.editor, self.username,
                           self.room_name, filename=f"{self.room_name}.txt")

            # Initialize network thread
            self.network = NetworkThread(
                self.sock, self.editor, self.tui,
                self.username, self.room_name
            )
            self.network.start()

            # Send initial cursor position
            self._send_cursor_update()

            # Main loop
            while self.tui.running and self.network.running:
                # Process incoming messages
                msgs = self.network.poll_messages()
                for msg in msgs:
                    self._handle_message(msg)

                # Handle keyboard input (TUI does this internally)
                # The TUI.run() method would loop, but we handle input here
                action = self.tui._handle_input()

                if action:
                    action_type, data = action
                    if action_type == "edit":
                        ops = data
                        msg_id = None
                        if self.editor.pending_ops:
                            msg_id = self.editor.pending_ops[-1][0]
                            self.editor.sent_ids.add(msg_id)

                        op_msg = make_operation(
                            msg_id=msg_id or "",
                            base_revision=self.editor.revision,
                            ops=ops,
                        )
                        self.network.send_message(op_msg)
                        self._send_cursor_update()

                    elif action_type == "save":
                        self.network.send_message(
                            make_save_request(self.username))

                    elif action_type == "lock_acquire":
                        self.network.send_message(
                            make_lock_request(self.username, LOCK_ACQUIRE))

                    elif action_type == "lock_release":
                        self.network.send_message(
                            make_lock_request(self.username, LOCK_RELEASE))

                    elif action_type == "undo":
                        inv_op = data
                        import uuid
                        msg_id = str(uuid.uuid4())
                        op_msg = make_operation(
                            msg_id=msg_id,
                            base_revision=self.editor.revision,
                            ops=[inv_op],
                        )
                        self.editor.sent_ids.add(msg_id)
                        self.network.send_message(op_msg)
                        self._send_cursor_update()

                # Send cursor position periodically
                now = time.time()
                if now - self.last_cursor_send > 0.5:
                    self._send_cursor_update()

                # Small sleep to prevent busy-waiting
                time.sleep(0.01)

            # Cleanup
            if self.network:
                self.network.stop()

        curses.wrapper(curses_main)

    def _handle_message(self, msg):
        """Process an incoming message from the server."""
        msg_type = msg.get("type")

        if msg_type == TYPE_OPERATION:
            self.editor.apply_remote(msg)

        elif msg_type == TYPE_CURSOR_UPDATE:
            username = msg.get("username", "")
            position = msg.get("position", {})
            revision = msg.get("revision", 0)
            self.editor.update_remote_cursor(username, position, revision)

        elif msg_type == TYPE_LOCK_GRANT:
            owner = msg.get("username", "")
            self.tui.set_lock_owner(owner)
            if owner == self.username:
                self.tui.show_status("Lock acquired!")
            else:
                self.tui.show_status(f"Lock owned by {owner}")

        elif msg_type == TYPE_LOCK_RELEASE:
            self.tui.set_lock_owner(None)
            self.tui.show_status("Lock released")

        elif msg_type == TYPE_SAVE_ACK:
            self.tui.show_status("Document saved!")

        elif msg_type == TYPE_USER_JOIN:
            username = msg.get("username", "")
            self.tui.show_status(f"{username} joined")
            # Update user list
            if username not in self.tui.user_list:
                self.tui.user_list.append(username)

        elif msg_type == TYPE_USER_LEAVE:
            username = msg.get("username", "")
            self.tui.show_status(f"{username} left")
            if username in self.tui.user_list:
                self.tui.user_list.remove(username)
            if username in self.editor.remote_cursors:
                del self.editor.remote_cursors[username]

        elif msg_type == TYPE_ACK:
            # Full state reset (reconnect scenario)
            document = msg.get("document", "")
            revision = msg.get("revision", 0)
            users = msg.get("users", [])
            lock_owner = msg.get("lock_owner")
            self.editor.reset_state(document, revision)
            self.tui.set_user_list(users)
            self.tui.set_lock_owner(lock_owner)
            self.tui.set_connected(True)
            self.tui.show_status("Reconnected!")

        elif msg_type == TYPE_ERROR:
            message = msg.get("message", "Unknown error")
            self.tui.show_status(f"Error: {message}")

    def _send_cursor_update(self):
        """Send current cursor position to server."""
        if not self.network or not self.editor:
            return
        position = {
            "row": self.editor.cursor_row,
            "col": self.editor.cursor_col,
        }
        msg = make_cursor_update(self.username, self.editor.revision, position)
        self.network.send_message(msg)
        self.last_cursor_send = time.time()


def main():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Client")
    parser.add_argument("--user", type=str, required=True,
                        help="Username for the session")
    parser.add_argument("--room", type=str, required=True,
                        help="Room name to join")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9999,
                        help="Server port (default: 9999)")
    parser.add_argument("--password", type=str, default="",
                        help="Room password")
    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port} as '{args.user}' to room '{args.room}'...")

    client = Client(
        host=args.host,
        port=args.port,
        username=args.user,
        room_name=args.room,
        password=args.password,
    )

    if not client.connect():
        print("Failed to connect. Exiting.")
        sys.exit(1)

    print("Connected! Starting editor...")
    client.run()


if __name__ == "__main__":
    main()
