"""Storage node process for the distributed key-value store.

Usage: python node.py <node_id> <host> <port> <router_host> <router_port>
"""

import socket
import threading
import time
import sys
import signal

from common import BufferedSocket, send_line, recv_line


class StorageNode:
    """In-memory key-value store with TTL support."""

    def __init__(self, node_id: str, host: str, port: int,
                 router_host: str, router_port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.router_host = router_host
        self.router_port = router_port
        # store: key -> (value, expiry_timestamp or None)
        self.store: dict[str, tuple[str, float | None]] = {}
        self.lock = threading.Lock()
        self.running = True

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_with_router(self) -> bool:
        """Tell the router our host:port so it can route to us."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.router_host, self.router_port))
            send_line(sock, f"REGISTER {self.node_id} {self.host} {self.port}")
            resp = recv_line(sock)
            sock.close()
            print(f"[node {self.node_id}] Registration response: {resp}")
            return resp == "REGISTERED"
        except Exception as e:
            print(f"[node {self.node_id}] Registration failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Bind and serve until stopped."""
        if not self.register_with_router():
            print(f"[node {self.node_id}] Aborting – could not register.")
            return

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(10)
        self.server_sock.settimeout(1.0)
        print(f"[node {self.node_id}] Listening on {self.host}:{self.port}")

        while self.running:
            try:
                client, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle, args=(client,),
                                     daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[node {self.node_id}] Accept error: {e}")

        self.server_sock.close()
        print(f"[node {self.node_id}] Shut down.")

    def shutdown(self) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------
    def _handle(self, sock) -> None:
        """Handle one connection from the router."""
        bsock = BufferedSocket(sock)
        try:
            while True:
                line = bsock.read_line()
                if not line:
                    break
                first_line, extra_lines = self._process(line)
                bsock.send_line(first_line)
                for el in extra_lines:
                    bsock.send_line(el)
        except (ConnectionError, OSError):
            pass
        finally:
            sock.close()

    def _process(self, msg: str) -> tuple[str, list[str]]:
        """Dispatch a single command. Returns (first_line, extra_lines)."""
        parts = msg.split(" ", 1)
        cmd = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd == "PING":
            return ("PONG", [])

        elif cmd == "SET":
            return (self._cmd_set(rest), [])

        elif cmd == "GET":
            return (self._cmd_get(rest), [])

        elif cmd == "DELETE":
            return (self._cmd_delete(rest), [])

        elif cmd == "LIST":
            first, extras = self._cmd_list(rest)
            return (first, extras)

        else:
            return ("ERROR Unknown command", [])

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------
    def _cmd_set(self, rest: str) -> str:
        # Syntax: <key> <value> [<ttl>]
        tokens = rest.split(" ", 1)
        key = tokens[0]
        value_and_ttl = tokens[1] if len(tokens) > 1 else ""

        ttl: int | None = None
        if value_and_ttl:
            tail = value_and_ttl.rsplit(" ", 1)
            if len(tail) == 2:
                try:
                    ttl = int(tail[1])
                    value = tail[0]
                except ValueError:
                    value = value_and_ttl
            else:
                value = value_and_ttl
        else:
            value = ""

        expiry = time.time() + ttl if ttl is not None else None
        with self.lock:
            self.store[key] = (value, expiry)
        return "OK"

    def _cmd_get(self, rest: str) -> str:
        key = rest.strip()
        with self.lock:
            if key not in self.store:
                return "NOT_FOUND"
            value, expiry = self.store[key]
        if expiry is not None and time.time() > expiry:
            with self.lock:
                self.store.pop(key, None)
            return "NOT_FOUND"
        return f"VALUE {value}"

    def _cmd_delete(self, rest: str) -> str:
        key = rest.strip()
        with self.lock:
            if key in self.store:
                del self.store[key]
                return "DELETED"
        return "NOT_FOUND"

    def _cmd_list(self, rest: str) -> tuple[str, list[str]]:
        prefix = rest.strip()
        now = time.time()
        with self.lock:
            # Purge expired keys
            expired = [k for k, (_, exp) in self.store.items()
                       if exp is not None and now > exp]
            for k in expired:
                del self.store[k]

            matching = sorted(k for k in self.store if k.startswith(prefix))

        extras = matching + ["LIST_END"]
        return (f"LIST_BEGIN {len(matching)}", extras)


# ======================================================================
# Entry point
# ======================================================================
def main():
    if len(sys.argv) != 6:
        print("Usage: python node.py <node_id> <host> <port> "
              "<router_host> <router_port>")
        sys.exit(1)

    node_id = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    router_host = sys.argv[4]
    router_port = int(sys.argv[5])

    node = StorageNode(node_id, host, port, router_host, router_port)

    def _sig_handler(signum, frame):
        print(f"\n[node {node_id}] Shutting down...")
        node.shutdown()

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    node.start()


if __name__ == "__main__":
    main()
