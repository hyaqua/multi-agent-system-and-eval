"""Common utilities for the distributed key-value store."""

import hashlib


def hash_key(key: str) -> int:
    """Hash a key to an integer in range [0, 2**128)."""
    return int(hashlib.md5(key.encode()).hexdigest(), 16)


class BufferedSocket:
    """Wraps a socket for line-oriented, buffered reads."""

    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""

    def read_line(self) -> str:
        """Read one newline-terminated line (without the newline)."""
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode("utf-8").strip()

    def send_line(self, msg: str) -> None:
        """Send a line with trailing newline."""
        self.sock.sendall((msg + "\n").encode("utf-8"))


def send_line(sock, msg: str) -> None:
    """Convenience: send a newline-terminated message on a raw socket."""
    sock.sendall((msg + "\n").encode("utf-8"))


def recv_line(sock) -> str:
    """Convenience: read one newline-terminated line from a raw socket."""
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    line, _ = data.split(b"\n", 1)
    return line.decode("utf-8").strip()
