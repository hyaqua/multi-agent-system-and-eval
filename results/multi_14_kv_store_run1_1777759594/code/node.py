"""
node.py — Storage node process.

Maintains an in-memory key-value store with TTL support.
Connects to the router's control port to register, then listens for
a single persistent data connection from the router to handle commands.
"""
import argparse
import logging
import socket
import sys
import time
import uuid

import protocol as proto

log = logging.getLogger("node")


class StorageNode:
    """In-memory key-value store with TTL."""

    def __init__(self):
        # store: key -> (value, expiry_timestamp | None)
        self._store: dict[str, tuple[str, float | None]] = {}

    def _now(self) -> float:
        return time.time()

    def _expired(self, key: str) -> bool:
        """Check if key has expired.  If so, delete it and return True."""
        entry = self._store.get(key)
        if entry is None:
            return True
        _, expiry = entry
        if expiry is not None and self._now() >= expiry:
            del self._store[key]
            return True
        return False

    def set(self, key: str, value: str, ttl: int | None = None) -> str:
        """Store a key-value pair, optionally with TTL in seconds."""
        expiry = (self._now() + ttl) if ttl is not None else None
        self._store[key] = (value, expiry)
        return proto.ok_resp()

    def get(self, key: str) -> str:
        """Retrieve a value by key.  Returns OK value or ERROR."""
        if self._expired(key):
            return proto.error_resp(f"not found: {key}")
        entry = self._store.get(key)
        if entry is None:
            return proto.error_resp(f"not found: {key}")
        return proto.ok_resp(entry[0])

    def delete(self, key: str) -> str:
        """Delete a key.  Returns OK or ERROR."""
        if self._expired(key):
            return proto.error_resp(f"not found: {key}")
        if key in self._store:
            del self._store[key]
            return proto.ok_resp()
        return proto.error_resp(f"not found: {key}")

    def list_keys(self, prefix: str | None = None) -> str:
        """
        Return comma-separated list of keys, optionally filtered by prefix.
        Expired keys are silently removed.
        """
        keys = []
        for k in list(self._store.keys()):
            if self._expired(k):
                continue
            if prefix is None or k.startswith(prefix):
                keys.append(k)
        return proto.ok_resp(",".join(keys))


def handle_connection(conn: socket.socket, store: StorageNode) -> None:
    """Serve a single persistent connection from the router."""
    buf = b""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode(proto.ENCODING).strip()
                if not line:
                    continue
                resp = process_command(line, store)
                conn.sendall(resp.encode(proto.ENCODING) + b"\n")
    except (ConnectionError, OSError) as e:
        log.debug("Connection closed: %s", e)
    finally:
        conn.close()


def process_command(line: str, store: StorageNode) -> str:
    """Parse and execute a single command line; return response string."""
    try:
        upper = line.upper()
        if upper.startswith(proto.CMD_SET):
            key, value, ttl = proto.parse_set(line)
            return store.set(key, value, ttl)

        elif upper.startswith(proto.CMD_GET):
            key = proto.parse_get(line)
            return store.get(key)

        elif upper.startswith(proto.CMD_DELETE):
            key = proto.parse_delete(line)
            return store.delete(key)

        elif upper.startswith(proto.CMD_LIST):
            prefix = proto.parse_list(line)
            return store.list_keys(prefix)

        elif upper.startswith(proto.CMD_PING):
            return proto.CMD_PONG

        else:
            return proto.error_resp(f"unknown command: {line}")
    except Exception as e:
        log.error("Error processing command '%s': %s", line, e)
        return proto.error_resp(str(e))


def main() -> None:
    parser = argparse.ArgumentParser(description="Storage Node")
    parser.add_argument("--router-host", default="127.0.0.1", help="Router control host")
    parser.add_argument("--router-port", type=int, default=5000, help="Router control port")
    parser.add_argument("--data-port", type=int, default=0, help="Data port (0=auto)")
    parser.add_argument("--node-id", default=None, help="Unique node ID (auto-generated if omitted)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind/advertise")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[node %(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    node_id = args.node_id or str(uuid.uuid4())[:8]
    store = StorageNode()

    # Bind data socket
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    data_sock.bind((args.host, args.data_port))
    actual_data_port = data_sock.getsockname()[1]
    data_sock.listen(1)
    log.info("Node %s listening on data port %s", node_id, actual_data_port)

    # Connect to router control port and register
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        ctrl_sock.connect((args.router_host, args.router_port))
    except ConnectionRefusedError:
        log.error("Cannot connect to router at %s:%s", args.router_host, args.router_port)
        sys.exit(1)

    # Send REGISTER
    reg_msg = proto.encode_msg(proto.CMD_REGISTER, node_id, args.host, str(actual_data_port))
    ctrl_sock.sendall(reg_msg)

    # Read response
    resp_data = ctrl_sock.recv(1024)
    resp = proto.decode_msg(resp_data)
    log.info("Router response: %s", resp)
    ctrl_sock.close()

    if not resp.startswith(proto.CMD_OK):
        log.error("Registration failed: %s", resp)
        sys.exit(1)

    # Accept the router's persistent data connection
    log.info("Waiting for router data connection...")
    router_conn, addr = data_sock.accept()
    log.info("Router connected from %s", addr)

    handle_connection(router_conn, store)
    log.info("Node %s shutting down.", node_id)


if __name__ == "__main__":
    main()
