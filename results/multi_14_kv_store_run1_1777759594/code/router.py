"""
router.py — Main router process.

Responsibilities:
- Listen for client connections on a configurable TCP port.
- Listen for node registrations on the same or a separate control port.
  (Control and client share the same port for simplicity; registration
   is distinguished by the REGISTER command.)
- Maintain a consistent hash ring of registered nodes.
- Forward client commands to the responsible node(s).
- Perform periodic health checks on all nodes.
- Log all operations.
"""
import argparse
import logging
import socket
import threading
import time

import consistent_hash
import protocol as proto

log = logging.getLogger("router")


class NodeConnection:
    """Represents a registered storage node and its persistent data connection."""

    def __init__(self, node_id: str, host: str, port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.lock = threading.Lock()
        self.alive = True

    def connect(self) -> bool:
        """Establish persistent data connection to the node."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.host, self.port))
            s.settimeout(None)  # switch back to blocking for regular use
            self.sock = s
            log.info("Connected to node %s at %s:%s", self.node_id, self.host, self.port)
            return True
        except (ConnectionRefusedError, OSError) as e:
            log.error("Failed to connect to node %s: %s", self.node_id, e)
            return False

    def send_cmd(self, cmd: str) -> str:
        """Send a command and read the response line (thread-safe)."""
        with self.lock:
            if self.sock is None:
                raise ConnectionError(f"Node {self.node_id} is not connected")
            try:
                self.sock.sendall(cmd.encode(proto.ENCODING) + b"\n")
                # Read response line
                buf = b""
                while b"\n" not in buf:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("Connection closed by node")
                    buf += chunk
                line_bytes, _ = buf.split(b"\n", 1)
                return line_bytes.decode(proto.ENCODING).strip()
            except (ConnectionError, OSError) as e:
                self.alive = False
                raise ConnectionError(f"Node {self.node_id} communication error: {e}") from e

    def ping(self) -> bool:
        """Send PING and expect PONG.  Returns True on success."""
        try:
            if self.sock is None:
                return False
            self.sock.settimeout(1)
            resp = self.send_cmd(proto.CMD_PING)
            self.sock.settimeout(None)
            return resp == proto.CMD_PONG
        except Exception:
            self.alive = False
            return False

    def close(self):
        """Close the data connection."""
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None
        self.alive = False


class Router:
    """Distributed key-value store router."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port
        self.ring = consistent_hash.ConsistentHashRing(virtual_nodes=128)
        # node_id -> NodeConnection
        self.nodes: dict[str, NodeConnection] = {}
        self.nodes_lock = threading.Lock()
        self.running = True

    def start(self) -> None:
        """Start the router: listener + health-check thread."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(50)
        log.info("Router listening on %s:%s", self.host, self.port)

        # Start health-check thread
        hc = threading.Thread(target=self._health_check_loop, daemon=True)
        hc.start()

        # Accept loop
        while self.running:
            try:
                conn, addr = self.sock.accept()
                t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                t.start()
            except OSError:
                if self.running:
                    log.exception("Accept error")
                break

    def stop(self) -> None:
        """Shut down the router."""
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        with self.nodes_lock:
            for nc in self.nodes.values():
                nc.close()
            self.nodes.clear()
            self.ring = consistent_hash.ConsistentHashRing()

    # ---- health checks ----------------------------------------------------
    def _health_check_loop(self) -> None:
        """Periodically ping every node and remove failed ones."""
        while self.running:
            time.sleep(2)
            dead_nodes: list[str] = []
            with self.nodes_lock:
                for nid, nc in list(self.nodes.items()):
                    if not nc.ping():
                        dead_nodes.append(nid)
                        log.warning("Node %s is unresponsive, marking dead", nid)
            for nid in dead_nodes:
                self._remove_node(nid)

    def _remove_node(self, node_id: str) -> None:
        """Remove a node from the ring and close its connection."""
        with self.nodes_lock:
            nc = self.nodes.pop(node_id, None)
            if nc:
                nc.close()
                self.ring.remove_node(node_id)
                log.info(
                    "Node %s removed.  Ring now has %d node(s).",
                    node_id,
                    len(self.ring.get_nodes()),
                )

    # ---- client handling ---------------------------------------------------
    def _handle_client(self, conn: socket.socket, addr) -> None:
        """Handle a single client connection."""
        log.info("Client connected from %s", addr)
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
                    resp = self._process_client_command(line)
                    if resp is not None:
                        conn.sendall(resp.encode(proto.ENCODING) + b"\n")
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()
            log.info("Client disconnected from %s", addr)

    def _process_client_command(self, line: str) -> str | None:
        """Route a client command to the appropriate node(s)."""
        upper = line.upper()

        # Registration from a node
        if upper.startswith(proto.CMD_REGISTER):
            return self._handle_register(line)

        # PING — silently handled, but could respond
        if upper.startswith(proto.CMD_PING):
            return proto.CMD_PONG

        if upper.startswith(proto.CMD_SET):
            return self._route_set(line)

        if upper.startswith(proto.CMD_GET):
            return self._route_get(line)

        if upper.startswith(proto.CMD_DELETE):
            return self._route_delete(line)

        if upper.startswith(proto.CMD_LIST):
            return self._route_list(line)

        if upper.startswith(proto.CMD_QUIT):
            return None  # client disconnecting

        return proto.error_resp(f"Unknown command: {line}")

    # ---- registration -----------------------------------------------------
    def _handle_register(self, line: str) -> str:
        """Register a new storage node."""
        try:
            node_id, host, port = proto.parse_register(line)
        except ValueError as e:
            return proto.error_resp(str(e))

        with self.nodes_lock:
            if node_id in self.nodes:
                return proto.error_resp(f"node {node_id} already registered")

            nc = NodeConnection(node_id, host, port)
            if not nc.connect():
                return proto.error_resp("cannot connect to data port")

            self.nodes[node_id] = nc
            self.ring.add_node(node_id)
            log.info(
                "Node %s registered at %s:%s.  Ring size: %d",
                node_id,
                host,
                port,
                len(self.ring.get_nodes()),
            )
        return proto.ok_resp()

    # ---- routing helpers --------------------------------------------------
    def _get_node_for_key(self, key: str) -> NodeConnection:
        """Find the responsible node for a key."""
        with self.nodes_lock:
            if self.ring.empty():
                raise RuntimeError("No nodes available")
            node_id = self.ring.get_node(key)
            nc = self.nodes.get(node_id)
            if nc is None or not nc.alive:
                raise RuntimeError(f"Node {node_id} is not available")
            return nc

    def _get_all_nodes(self) -> list[NodeConnection]:
        """Return all alive nodes (snapshot)."""
        with self.nodes_lock:
            return [nc for nc in self.nodes.values() if nc.alive]

    def _route_set(self, line: str) -> str:
        log.info("SET request: %s", line)
        try:
            key, _, _ = proto.parse_set(line)
            nc = self._get_node_for_key(key)
            resp = nc.send_cmd(line)
            log.info("SET %s -> node %s: %s", key, nc.node_id, resp)
            return resp
        except Exception as e:
            log.error("SET failed: %s", e)
            return proto.error_resp(str(e))

    def _route_get(self, line: str) -> str:
        log.info("GET request: %s", line)
        try:
            key = proto.parse_get(line)
            nc = self._get_node_for_key(key)
            resp = nc.send_cmd(line)
            log.info("GET %s -> node %s: %s", key, nc.node_id, resp)
            return resp
        except Exception as e:
            log.error("GET failed: %s", e)
            return proto.error_resp(str(e))

    def _route_delete(self, line: str) -> str:
        log.info("DELETE request: %s", line)
        try:
            key = proto.parse_delete(line)
            nc = self._get_node_for_key(key)
            resp = nc.send_cmd(line)
            log.info("DELETE %s -> node %s: %s", key, nc.node_id, resp)
            return resp
        except Exception as e:
            log.error("DELETE failed: %s", e)
            return proto.error_resp(str(e))

    def _route_list(self, line: str) -> str:
        log.info("LIST request: %s", line)
        try:
            nodes = self._get_all_nodes()
            if not nodes:
                return proto.error_resp("No nodes available")
            all_keys: list[str] = []
            for nc in nodes:
                try:
                    resp = nc.send_cmd(line)
                    if resp.startswith(proto.CMD_OK):
                        data = resp[3:]  # skip "OK "
                        if data:
                            all_keys.extend(data.split(","))
                except Exception as e:
                    log.warning("LIST error from node %s: %s", nc.node_id, e)
            return proto.ok_resp(",".join(all_keys))
        except Exception as e:
            log.error("LIST failed: %s", e)
            return proto.error_resp(str(e))


def main() -> None:
    parser = argparse.ArgumentParser(description="KV Store Router")
    parser.add_argument("--host", default="127.0.0.1", help="Listen host")
    parser.add_argument("--port", type=int, default=5000, help="Listen port")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[router %(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    router = Router(args.host, args.port)
    try:
        router.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        router.stop()


if __name__ == "__main__":
    main()
