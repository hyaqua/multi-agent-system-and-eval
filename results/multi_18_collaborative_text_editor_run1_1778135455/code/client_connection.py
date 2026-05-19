"""
Client network module – handles socket connection, send queue,
background receive loop, and reconnection.
"""

import socket
import threading
import logging
import time
import queue

import protocol

logger = logging.getLogger("client.network")


class NetworkClient:
    """Manages the TCP connection to the server in a background thread."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.running = False
        self.connected = False
        self._recv_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()

        # Message queues
        self.incoming: queue.Queue = queue.Queue()  # received messages
        self._send_queue: queue.Queue = queue.Queue()

        # Reconnection
        self._reconnect_event = threading.Event()

    def connect(self, timeout: float = 5.0) -> bool:
        """Establish TCP connection. Returns True on success."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Blocking mode for recv
            self.connected = True
            self.running = True
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()
            # Start sender thread
            self._sender_thread = threading.Thread(target=self._send_loop, daemon=True)
            self._sender_thread.start()
            logger.info("Connected to %s:%d", self.host, self.port)
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.error("Connection failed: %s", e)
            self.connected = False
            return False

    def disconnect(self):
        """Close the connection."""
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def send(self, msg: dict):
        """Queue a message for sending."""
        self._send_queue.put(msg)

    def send_now(self, msg: dict) -> bool:
        """Send a message immediately (blocking). Returns True on success."""
        with self._send_lock:
            if not self.sock or not self.connected:
                return False
            try:
                data = protocol.encode_message(msg)
                self.sock.sendall(data)
                return True
            except OSError as e:
                logger.error("Send error: %s", e)
                self.connected = False
                return False

    def _send_loop(self):
        """Background thread that sends queued messages."""
        while self.running:
            try:
                msg = self._send_queue.get(timeout=0.1)
                if msg is None:
                    break
                self.send_now(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Send loop error: %s", e)

    def _recv_loop(self):
        """Background thread that reads messages from the socket."""
        buffer = b""
        while self.running:
            try:
                if not self.sock:
                    break
                data = self.sock.recv(4096)
                if not data:
                    logger.info("Server closed connection")
                    self.connected = False
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        msg = protocol.decode_message(line)
                        if msg:
                            self.incoming.put(msg)
            except (ConnectionResetError, BrokenPipeError):
                logger.info("Connection lost")
                self.connected = False
                break
            except OSError as e:
                if self.running:
                    logger.error("Recv error: %s", e)
                self.connected = False
                break

        self.connected = False

    def poll(self) -> list[dict]:
        """Get all pending incoming messages (non-blocking)."""
        messages = []
        while True:
            try:
                msg = self.incoming.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break
        return messages
