"""Simple text-based (JSON line) protocol over TCP sockets."""

import json
import socket


class MessageProtocol:
    """Handles sending and receiving JSON messages over a socket with buffering."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buffer = b""

    def send(self, msg: dict) -> None:
        """Send a JSON message followed by a newline."""
        data = json.dumps(msg).encode("utf-8") + b"\n"
        self.sock.sendall(data)

    def recv(self, timeout: float | None = None) -> dict | None:
        """
        Receive a JSON message. Returns the parsed dict, or None on error/timeout/EOF.

        If timeout is given, sets the socket timeout for this receive operation only.
        """
        old_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while b"\n" not in self._buffer:
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    return None
                if not chunk:
                    # Connection closed
                    if self._buffer:
                        # Return whatever we have (shouldn't happen in proper protocol)
                        line = self._buffer
                        self._buffer = b""
                        try:
                            return json.loads(line.decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            return None
                    return None
                self._buffer += chunk
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                return json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        finally:
            if timeout is not None:
                self.sock.settimeout(old_timeout)

    def close(self) -> None:
        """Close the underlying socket."""
        try:
            self.sock.close()
        except OSError:
            pass
