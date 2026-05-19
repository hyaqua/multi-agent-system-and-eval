"""
Storage node process.

Connects to the router's node port, registers, and services key-value
operations. Maintains an in-memory dictionary with TTL-based expiry.

Usage:
    python storage_node.py --id node-0 --router-host localhost --router-port 5556 [--vcount 100]
"""

import argparse
import socket
import sys
import time
import threading
import select

from protocol import (
    parse_command,
    parse_set,
    encode_register,
    encode_ok,
    encode_value,
    encode_notfound,
    encode_deleted,
    encode_pong,
    encode_error,
    encode_list_response,
    CMD_SET,
    CMD_GET,
    CMD_DELETE,
    CMD_LIST,
    CMD_PING,
)


class StorageNode:
    """In-memory key-value store with TTL support."""

    def __init__(self, node_id: str, router_host: str, router_port: int,
                 vcount: int = 100, cleanup_interval: float = 1.5):
        self.node_id = node_id
        self.router_host = router_host
        self.router_port = router_port
        self.vcount = vcount
        self.cleanup_interval = cleanup_interval

        # Data store: {key: (value, expiry_ts)}  expiry_ts=0 means no TTL
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._running = True
        self._sock: socket.socket | None = None

    def _cleanup_expired(self) -> None:
        """Remove all expired keys."""
        now = time.time()
        with self._lock:
            expired = [
                k for k, (v, exp) in self._data.items()
                if exp > 0 and now >= exp
            ]
            for k in expired:
                del self._data[k]

    def _cleanup_loop(self) -> None:
        """Periodically remove expired keys."""
        while self._running:
            time.sleep(self.cleanup_interval)
            if self._running:
                self._cleanup_expired()

    def _get(self, key: str) -> str | None:
        """Get value for key, checking expiry. Returns None if expired/missing."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if expiry > 0 and time.time() >= expiry:
                del self._data[key]
                return None
            return value

    def _set(self, key: str, value: str, ttl: int = 0) -> None:
        """Set key with optional TTL in seconds."""
        expiry = time.time() + ttl if ttl > 0 else 0
        with self._lock:
            self._data[key] = (value, expiry)

    def _delete(self, key: str) -> bool:
        """Delete key, return True if it existed (and wasn't expired)."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False
            value, expiry = entry
            if expiry > 0 and time.time() >= expiry:
                del self._data[key]
                return False
            del self._data[key]
            return True

    def _list_keys(self, prefix: str = "") -> list[str]:
        """Return non-expired keys, optionally filtered by prefix."""
        now = time.time()
        with self._lock:
            keys = []
            expired = []
            for k, (v, exp) in self._data.items():
                if exp > 0 and now >= exp:
                    expired.append(k)
                elif k.startswith(prefix):
                    keys.append(k)
            for k in expired:
                del self._data[k]
            return sorted(keys)

    def handle_command(self, cmd: str, args: list[str], raw_line: str = "") -> str:
        """Process a single command and return the response string.
        raw_line is the full original line, used for SET parsing with quotes."""
        if cmd == CMD_PING:
            return encode_pong()

        elif cmd == CMD_SET:
            try:
                key, value, ttl = parse_set(raw_line)
            except ValueError as e:
                return encode_error(str(e))
            self._set(key, value, ttl)
            return encode_ok()

        elif cmd == CMD_GET:
            if len(args) < 1:
                return encode_error("GET requires key")
            key = args[0]
            val = self._get(key)
            if val is None:
                return encode_notfound()
            return encode_value(val)

        elif cmd == CMD_DELETE:
            if len(args) < 1:
                return encode_error("DELETE requires key")
            key = args[0]
            existed = self._delete(key)
            if existed:
                return encode_deleted()
            return encode_notfound()

        elif cmd == CMD_LIST:
            prefix = args[0] if len(args) >= 1 else ""
            keys = self._list_keys(prefix)
            return encode_list_response(keys)

        else:
            return encode_error(f"Unknown command: {cmd}")

    def run(self) -> None:
        """Connect to router, register, and service commands."""
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        while self._running:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.connect((self.router_host, self.router_port))
                # Send registration
                reg_msg = encode_register(self.node_id, self.vcount)
                self._sock.sendall(reg_msg.encode())
                print(f"[{self.node_id}] Registered with router at {self.router_host}:{self.router_port}")

                # Service loop
                buffer = b""
                while self._running:
                    try:
                        data = self._sock.recv(4096)
                    except (ConnectionResetError, ConnectionAbortedError, OSError):
                        break
                    if not data:
                        break
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line_str = line.decode().strip()
                        if not line_str:
                            continue
                        cmd, args = parse_command(line_str)
                        if cmd is None:
                            continue
                        response = self.handle_command(cmd, args)
                        try:
                            self._sock.sendall(response.encode())
                        except (BrokenPipeError, OSError):
                            break

            except (ConnectionRefusedError, OSError) as e:
                print(f"[{self.node_id}] Connection error: {e}")

            # Reconnect after a delay
            if self._running:
                print(f"[{self.node_id}] Reconnecting in 2 seconds...")
                time.sleep(2)

    def stop(self) -> None:
        """Signal the node to stop."""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Storage Node")
    parser.add_argument("--id", required=True, help="Unique node identifier")
    parser.add_argument("--router-host", default="localhost", help="Router host")
    parser.add_argument("--router-port", type=int, default=5556, help="Router node port")
    parser.add_argument("--vcount", type=int, default=100, help="Virtual node count")
    args = parser.parse_args()

    node = StorageNode(
        node_id=args.id,
        router_host=args.router_host,
        router_port=args.router_port,
        vcount=args.vcount,
    )

    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()


if __name__ == "__main__":
    main()
