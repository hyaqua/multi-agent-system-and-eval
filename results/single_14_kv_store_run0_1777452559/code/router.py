"""Router process for the distributed key-value store.

Usage: python router.py <host> <port>
"""

import socket
import threading
import time
import bisect
import sys
import signal

from common import hash_key, BufferedSocket, send_line


class Router:
    """Distributes keys across storage nodes via consistent hashing.

    Listens on *host:port* for both storage-node registrations and
    client commands.  Performs periodic health-checks and redistributes
    the hash ring when a node fails.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        # node_id -> {host, port, last_health, alive}
        self._nodes: dict[str, dict] = {}
        # sorted list of (hash_value, node_id)
        self._ring: list[tuple[int, str]] = []
        self._lock = threading.Lock()
        self.running = True
        # per-request extra lines for multi-line responses
        self._dispatch_extra: list[str] = []

    # ------------------------------------------------------------------
    # Ring management
    # ------------------------------------------------------------------
    def _rebuild_ring(self) -> None:
        """Re-sort the ring from current alive nodes (caller must hold lock)."""
        self._ring.clear()
        for nid, info in self._nodes.items():
            if info["alive"]:
                self._ring.append((hash_key(nid), nid))
        self._ring.sort()

    def add_node(self, node_id: str, host: str, port: int) -> None:
        with self._lock:
            self._nodes[node_id] = {
                "host": host,
                "port": port,
                "last_health": time.time(),
                "alive": True,
            }
            self._rebuild_ring()
        print(f"[LOG] Node {node_id} registered @ {host}:{port}")

    def get_node_for_key(self, key: str) -> str | None:
        """Return the node_id responsible for *key*, or None."""
        with self._lock:
            if not self._ring:
                return None
            h = hash_key(key)
            idx = bisect.bisect_left(self._ring, (h, ""))
            if idx >= len(self._ring):
                idx = 0
            return self._ring[idx][1]

    def _alive_nodes_snapshot(self) -> list[tuple[str, dict]]:
        """Return a consistent snapshot of alive nodes."""
        with self._lock:
            return [(nid, dict(info)) for nid, info in self._nodes.items()
                    if info["alive"]]

    # ------------------------------------------------------------------
    # Communication with storage nodes
    # ------------------------------------------------------------------
    def send_to_node(self, node_id: str, message: str,
                     timeout: float = 3.0):
        """Send *message* to a storage node.

        Returns (ok: bool, first_line: str, bsock: BufferedSocket | None).
        On success *bsock* is open and the caller must close it after
        reading any extra lines.  On failure *bsock* is None.
        """
        with self._lock:
            info = self._nodes.get(node_id)
        if info is None:
            return (False, "ERROR Node not found", None)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((info["host"], info["port"]))
            bsock = BufferedSocket(sock)
            bsock.send_line(message)
            first_line = bsock.read_line()
            # Update health timestamp on success
            with self._lock:
                if node_id in self._nodes:
                    self._nodes[node_id]["last_health"] = time.time()
            return (True, first_line, bsock)
        except (socket.timeout, ConnectionError, OSError) as e:
            sock.close()
            return (False, f"ERROR {e}", None)

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------
    def _health_check_loop(self) -> None:
        """Periodically ping every registered node."""
        while self.running:
            time.sleep(5)
            # Snapshot node ids
            with self._lock:
                node_ids = list(self._nodes.keys())
            for nid in node_ids:
                self._check_one_node(nid)

    def _check_one_node(self, node_id: str) -> None:
        with self._lock:
            info = self._nodes.get(node_id)
            if info is None:
                return
            host, port = info["host"], info["port"]

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            bsock = BufferedSocket(sock)
            bsock.send_line("PING")
            resp = bsock.read_line()
            sock.close()
            if resp == "PONG":
                with self._lock:
                    if node_id in self._nodes:
                        was_alive = self._nodes[node_id]["alive"]
                        self._nodes[node_id]["last_health"] = time.time()
                        if not was_alive:
                            self._nodes[node_id]["alive"] = True
                            self._rebuild_ring()
                            print(f"[LOG] Node {node_id} is back online")
            else:
                raise ConnectionError("bad ping response")
        except Exception:
            with self._lock:
                if node_id in self._nodes and self._nodes[node_id]["alive"]:
                    self._nodes[node_id]["alive"] = False
                    self._rebuild_ring()
                    print(f"[LOG] Node {node_id} is UNRESPONSIVE "
                          f"– key range redistributed")

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Bind the server socket and start the health-check thread."""
        hc = threading.Thread(target=self._health_check_loop, daemon=True)
        hc.start()

        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(50)
        self._server.settimeout(1.0)   # so we can check self.running
        print(f"[LOG] Router listening on {self.host}:{self.port}")

        while self.running:
            try:
                client, addr = self._server.accept()
                t = threading.Thread(target=self._handle_conn,
                                     args=(client, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[LOG] Accept error: {e}")

        self._server.close()
        print("[LOG] Router shut down.")

    def shutdown(self) -> None:
        self.running = False

    def _handle_conn(self, sock, addr) -> None:
        """Handle one TCP connection (node registration or client)."""
        bsock = BufferedSocket(sock)
        try:
            first_line = bsock.read_line()
            if not first_line:
                sock.close()
                return

            if first_line.upper().startswith("REGISTER"):
                self._handle_registration(first_line, bsock)
                sock.close()
                return

            # Regular client – feed first line as first command
            self._handle_client(bsock, first_line, addr)
        except (ConnectionError, OSError):
            pass
        finally:
            sock.close()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _handle_registration(self, msg: str, bsock: BufferedSocket) -> None:
        parts = msg.split()
        if len(parts) != 4:
            bsock.send_line("ERROR Bad REGISTER format")
            return
        _, node_id, host, port_str = parts
        try:
            port = int(port_str)
        except ValueError:
            bsock.send_line("ERROR Invalid port")
            return
        self.add_node(node_id, host, port)
        bsock.send_line("REGISTERED")

    # ------------------------------------------------------------------
    # Client commands
    # ------------------------------------------------------------------
    def _handle_client(self, bsock: BufferedSocket, first_line: str,
                       addr) -> None:
        current = first_line
        while current:
            resp, extras = self._dispatch(current)
            if resp is None:           # QUIT
                return
            bsock.send_line(resp)
            for line in extras:
                bsock.send_line(line)
            try:
                current = bsock.read_line()
            except (ConnectionError, OSError):
                return

    def _dispatch(self, msg: str) -> tuple[str | None, list[str]]:
        """Route a client command. Returns (first_line, extra_lines)."""
        parts = msg.split(" ", 1)
        cmd = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd == "QUIT":
            return (None, [])

        elif cmd == "SET":
            return self._route_set(rest)

        elif cmd == "GET":
            return self._route_get(rest)

        elif cmd == "DELETE":
            return self._route_delete(rest)

        elif cmd == "LIST":
            return self._route_list(rest)

        else:
            return ("ERROR Unknown command", [])

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_key(rest: str) -> str:
        return rest.split(" ", 1)[0] if rest else ""

    def _route_set(self, rest: str) -> tuple[str, list[str]]:
        key = self._extract_key(rest)
        node = self.get_node_for_key(key)
        if node is None:
            return ("ERROR No nodes available", [])
        ok, result, bsock = self.send_to_node(node, f"SET {rest}")
        if not ok:
            return (result, [])
        bsock.sock.close()
        print(f"[LOG] SET {key} → node {node}  ({result})")
        return (result, [])

    def _route_get(self, rest: str) -> tuple[str, list[str]]:
        key = rest.strip()
        node = self.get_node_for_key(key)
        if node is None:
            return ("ERROR No nodes available", [])
        ok, result, bsock = self.send_to_node(node, f"GET {key}")
        if not ok:
            return (result, [])
        bsock.sock.close()
        print(f"[LOG] GET {key} → node {node}  ({result})")
        return (result, [])

    def _route_delete(self, rest: str) -> tuple[str, list[str]]:
        key = rest.strip()
        node = self.get_node_for_key(key)
        if node is None:
            return ("ERROR No nodes available", [])
        ok, result, bsock = self.send_to_node(node, f"DELETE {key}")
        if not ok:
            return (result, [])
        bsock.sock.close()
        print(f"[LOG] DELETE {key} → node {node}  ({result})")
        return (result, [])

    def _route_list(self, rest: str) -> tuple[str, list[str]]:
        prefix = rest.strip()
        all_keys: list[str] = []
        nodes = self._alive_nodes_snapshot()

        for nid, info in nodes:
            ok, first_line, bsock = self.send_to_node(nid, f"LIST {prefix}")
            if not ok:
                print(f"[LOG] LIST prefix='{prefix}' → node {nid}: "
                      f"{first_line}")
                continue
            if first_line.startswith("LIST_BEGIN"):
                count = int(first_line.split(" ")[1])
                keys: list[str] = []
                for _ in range(count):
                    try:
                        keys.append(bsock.read_line())
                    except Exception:
                        break
                try:
                    bsock.read_line()  # LIST_END
                except Exception:
                    pass
                all_keys.extend(keys)
                print(f"[LOG] LIST prefix='{prefix}' → node {nid}: "
                      f"{len(keys)} keys")
            bsock.sock.close()

        all_keys.sort()
        return (f"LIST_BEGIN {len(all_keys)}", all_keys + ["LIST_END"])


# ======================================================================
# Entry point
# ======================================================================
def main():
    if len(sys.argv) != 3:
        print("Usage: python router.py <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    router = Router(host, port)

    def _sig_handler(signum, frame):
        print("\n[LOG] Shutting down router...")
        router.shutdown()

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    router.start()


if __name__ == "__main__":
    main()
