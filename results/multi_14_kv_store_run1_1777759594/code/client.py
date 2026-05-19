"""
client.py — Simple CLI client for the distributed key-value store.

Connect to the router and send commands interactively.
"""
import argparse
import socket
import sys

import protocol as proto


class KVClient:
    """REPL client for the KV store."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        """Connect to the router."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f"Connected to router at {self.host}:{self.port}")

    def send(self, cmd: str) -> str:
        """Send a command and return the response."""
        if self.sock is None:
            raise ConnectionError("Not connected")
        self.sock.sendall(cmd.encode(proto.ENCODING) + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by router")
            buf += chunk
        line_bytes, _ = buf.split(b"\n", 1)
        return line_bytes.decode(proto.ENCODING).strip()

    def close(self) -> None:
        """Close the connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
        print("Disconnected.")

    def run(self) -> None:
        """Interactive REPL."""
        print("Key-Value Store CLI")
        print("Commands: SET <key> <value> [TTL] | GET <key> | DELETE <key> |")
        print("          LIST [prefix] | QUIT")
        print()
        try:
            while True:
                try:
                    line = input("kv> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not line:
                    continue

                upper = line.upper()
                if upper.startswith("QUIT"):
                    break

                if (
                    upper.startswith(proto.CMD_SET)
                    or upper.startswith(proto.CMD_GET)
                    or upper.startswith(proto.CMD_DELETE)
                    or upper.startswith(proto.CMD_LIST)
                ):
                    try:
                        resp = self.send(line)
                        print(resp)
                    except ConnectionError as e:
                        print(f"ERROR: {e}")
                        break
                else:
                    print("Unknown command.  Use SET, GET, DELETE, LIST, or QUIT.")
        finally:
            self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="KV Store CLI Client")
    parser.add_argument("--host", default="127.0.0.1", help="Router host")
    parser.add_argument("--port", type=int, default=5000, help="Router port")
    args = parser.parse_args()

    client = KVClient(args.host, args.port)
    try:
        client.connect()
        client.run()
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to router at {args.host}:{args.port}")
        sys.exit(1)


if __name__ == "__main__":
    main()
