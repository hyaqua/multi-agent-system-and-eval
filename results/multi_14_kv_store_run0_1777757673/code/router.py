"""
Router process.

Listens for client connections on one TCP port and storage node connections
on another. Routes key-value operations using consistent hashing and performs
health checks on registered nodes.

Usage:
    python router.py --client-port 5555 --node-port 5556 [--health-interval 2] [--health-timeout 1]
"""

import argparse
import logging
import socket
import threading
import time
import sys

from protocol import (
    parse_command,
    encode_command,
    encode_ok,
    encode_value,
    encode_notfound,
    encode_deleted,
    encode_end,
    encode_error,
    encode_ping,
    encode_pong,
    encode_register,
    CMD_SET,
    CMD_GET,
    CMD_DELETE,
    CMD_LIST,
    CMD_PING,
    CMD_REGISTER,
    RESP_OK,
    RESP_PONG,
    RESP_END,
    RESP_VALUE,
    RESP_NOTFOUND,
    RESP_DELETED,
    RESP_ERROR,
)
from consistent_hash import ConsistentHashRing


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("router")


class NodeInfo:
    """Information about a connected storage node."""

    def __init__(self, node_id: str, sock: socket.socket, addr: tuple):
        self.node_id = node_id
        self.sock = sock
        self.addr = addr
        self.lock = threading.Lock()  # serialises requests to this node
        self.vcount = 100
        self.last_seen = time.time()


class Router:
    """Central coordinator for the distributed key-value store."""

    def __init__(self, client_port: int = 5555, node_port: int = 5556,
                 health_interval: float = 2.0, health_timeout: float = 1.0):
        self.client_port = client_port
        self.node_port = node_port
        self.health_interval = health_interval
        self.health_timeout = health_timeout

        self._ring = ConsistentHashRing()
        self._ring_lock = threading.RLock()  # protects ring modifications

        # node_id -> NodeInfo
        self._nodes: dict[str, NodeInfo] = {}
        self._nodes_lock = threading.Lock()

        self._running = True
        self._client_sock: socket.socket | None = None
        self._node_sock: socket.socket | None = None

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def _handle_node_connection(self, conn: socket.socket, addr: tuple) -> None:
        """Handle a new storage node connection - reads registration then
        hands off the socket to the shared node dict. The health checker
        and client handlers will use the socket via per-node locks."""
        node_id = None
        try:
            conn.settimeout(5.0)
            # Read registration line
            buffer = b""
            while b"\n" not in buffer:
                data = conn.recv(1024)
                if not data:
                    conn.close()
                    return
                buffer += data
            line, _ = buffer.split(b"\n", 1)
            line_str = line.decode().strip()
            cmd, args = parse_command(line_str)

            if cmd != CMD_REGISTER or len(args) < 1:
                logger.warning(f"Invalid registration from {addr}: {line_str}")
                conn.sendall(encode_error("Expected REGISTER <id> [vcount]").encode())
                conn.close()
                return

            node_id = args[0]
            vcount = 100
            if len(args) >= 2:
                try:
                    vcount = int(args[1])
                except ValueError:
                    vcount = 100

            # Check for duplicate node_id
            with self._nodes_lock:
                if node_id in self._nodes:
                    old = self._nodes[node_id]
                    logger.warning(f"Duplicate node_id {node_id}, closing old connection")
                    try:
                        old.sock.close()
                    except OSError:
                        pass
                    with self._ring_lock:
                        self._ring.remove_node(node_id)

            # Create NodeInfo
            node_info = NodeInfo(node_id, conn, addr)
            node_info.vcount = vcount

            with self._nodes_lock:
                self._nodes[node_id] = node_info

            with self._ring_lock:
                self._ring.add_node(node_id, vcount)

            # Send OK
            conn.sendall(encode_ok().encode())
            logger.info(f"NODE_JOIN {node_id} from {addr} vcount={vcount} "
                        f"(total nodes: {self._ring.node_count})")

            # We do NOT read from the socket in this thread anymore.
            # All further socket I/O goes through per-node locks
            # (health checks and client request forwarding).
            # To detect unexpected disconnection, the health checker
            # will notice when PING fails, or a client request will fail.

        except Exception as e:
            logger.error(f"Error during node registration from {addr}: {e}")
            if node_id:
                self._remove_node(node_id)
            try:
                conn.close()
            except OSError:
                pass

    def _remove_node(self, node_id: str) -> None:
        """Remove a node from the ring and internal structures."""
        if node_id is None:
            return
        with self._nodes_lock:
            node_info = self._nodes.pop(node_id, None)
        if node_info:
            try:
                node_info.sock.close()
            except OSError:
                pass
        with self._ring_lock:
            self._ring.remove_node(node_id)
        logger.info(f"NODE_FAIL {node_id} removed from ring "
                    f"(remaining nodes: {self._ring.node_count})")

    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------

    def _health_check_loop(self) -> None:
        """Periodically ping all nodes to detect failures."""
        while self._running:
            time.sleep(self.health_interval)
            if not self._running:
                break

            with self._nodes_lock:
                node_ids = list(self._nodes.keys())

            for node_id in node_ids:
                with self._nodes_lock:
                    node_info = self._nodes.get(node_id)
                if node_info is None:
                    continue

                try:
                    with node_info.lock:
                        node_info.sock.settimeout(self.health_timeout)
                        node_info.sock.sendall(encode_ping().encode())

                        # Read response (just PONG)
                        buffer = b""
                        while b"\n" not in buffer:
                            data = node_info.sock.recv(4096)
                            if not data:
                                raise ConnectionError("No data (connection closed)")
                            buffer += data
                        line = buffer.split(b"\n", 1)[0].decode().strip()
                        if line != RESP_PONG:
                            raise ConnectionError(f"Unexpected response: {line}")
                        node_info.last_seen = time.time()
                except Exception as e:
                    logger.warning(f"Health check failed for {node_id}: {e}")
                    self._remove_node(node_id)

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------

    def _get_node_for_key(self, key: str) -> NodeInfo | None:
        """Get the NodeInfo responsible for a key."""
        with self._ring_lock:
            node_id = self._ring.get_node(key)
        if node_id is None:
            return None
        with self._nodes_lock:
            return self._nodes.get(node_id)

    def _get_all_nodes(self) -> list[NodeInfo]:
        """Get all current node infos."""
        with self._nodes_lock:
            return list(self._nodes.values())

    def _send_to_node(self, node_info: NodeInfo, command: str) -> str:
        """
        Send a command to a specific node and read its response.
        Acquires the per-node lock to serialise communication.
        Returns the full response string (including trailing newline).
        On failure, removes the node and returns an ERROR response.
        """
        with node_info.lock:
            try:
                node_info.sock.settimeout(5.0)
                node_info.sock.sendall(command.encode())

                # Read the first line
                buffer = b""
                while b"\n" not in buffer:
                    data = node_info.sock.recv(4096)
                    if not data:
                        raise ConnectionError("Node disconnected")
                    buffer += data
                first_line_bytes, rest = buffer.split(b"\n", 1)
                first_line = first_line_bytes.decode().strip()

                # Single-line responses
                if first_line in (RESP_OK, RESP_NOTFOUND, RESP_DELETED):
                    return first_line + "\n"
                if first_line.startswith(RESP_VALUE + " "):
                    return first_line + "\n"
                if first_line.startswith(RESP_ERROR + " "):
                    return first_line + "\n"

                # LIST response: first_line could be a key or "END"
                if first_line == RESP_END:
                    return RESP_END + "\n"

                # Multi-line: collect until END
                lines = [first_line]
                remaining = rest
                while True:
                    while b"\n" not in remaining:
                        data = node_info.sock.recv(4096)
                        if not data:
                            raise ConnectionError("Node disconnected during LIST")
                        remaining += data
                    line_bytes, remaining = remaining.split(b"\n", 1)
                    line_str = line_bytes.decode().strip()
                    if line_str == RESP_END:
                        break
                    lines.append(line_str)
                return "\n".join(lines) + "\n" + RESP_END + "\n"

            except Exception as e:
                logger.error(f"Error communicating with node {node_info.node_id}: {e}")
                self._remove_node(node_info.node_id)
                return encode_error(f"Node error: {e}")

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """Handle a client connection."""
        logger.info(f"Client connected from {addr}")
        conn.settimeout(None)
        buffer = b""
        try:
            while self._running:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line_str = line_bytes.decode().strip()
                    if not line_str:
                        continue

                    cmd, args = parse_command(line_str)
                    if cmd is None:
                        conn.sendall(encode_error("Empty command").encode())
                        continue

                    logger.info(f"CLIENT {addr} {cmd} {' '.join(args) if args else ''}")

                    if cmd == CMD_SET:
                        self._handle_client_set(conn, args)
                    elif cmd == CMD_GET:
                        self._handle_client_get(conn, args)
                    elif cmd == CMD_DELETE:
                        self._handle_client_delete(conn, args)
                    elif cmd == CMD_LIST:
                        self._handle_client_list(conn, args)
                    else:
                        conn.sendall(encode_error(f"Unknown command: {cmd}").encode())
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            logger.info(f"Client disconnected from {addr}")
            try:
                conn.close()
            except OSError:
                pass

    def _handle_client_set(self, conn: socket.socket, args: list[str]) -> None:
        if len(args) < 2:
            conn.sendall(encode_error("SET requires key and value").encode())
            return
        key = args[0]
        value = args[1]
        ttl = 0
        if len(args) >= 3:
            try:
                ttl = int(args[2])
            except ValueError:
                conn.sendall(encode_error("TTL must be integer").encode())
                return

        node = self._get_node_for_key(key)
        if node is None:
            conn.sendall(encode_error("No nodes available").encode())
            return

        if ttl > 0:
            cmd_str = encode_command(CMD_SET, key, value, ttl)
        else:
            cmd_str = encode_command(CMD_SET, key, value)
        response = self._send_to_node(node, cmd_str)
        conn.sendall(response.encode())

    def _handle_client_get(self, conn: socket.socket, args: list[str]) -> None:
        if len(args) < 1:
            conn.sendall(encode_error("GET requires key").encode())
            return
        key = args[0]
        node = self._get_node_for_key(key)
        if node is None:
            conn.sendall(encode_error("No nodes available").encode())
            return

        cmd_str = encode_command(CMD_GET, key)
        response = self._send_to_node(node, cmd_str)
        conn.sendall(response.encode())

    def _handle_client_delete(self, conn: socket.socket, args: list[str]) -> None:
        if len(args) < 1:
            conn.sendall(encode_error("DELETE requires key").encode())
            return
        key = args[0]
        node = self._get_node_for_key(key)
        if node is None:
            conn.sendall(encode_error("No nodes available").encode())
            return

        cmd_str = encode_command(CMD_DELETE, key)
        response = self._send_to_node(node, cmd_str)
        conn.sendall(response.encode())

    def _handle_client_list(self, conn: socket.socket, args: list[str]) -> None:
        prefix = args[0] if len(args) >= 1 else ""
        if prefix:
            cmd_str = encode_command(CMD_LIST, prefix)
        else:
            cmd_str = encode_command(CMD_LIST)

        nodes = self._get_all_nodes()
        if not nodes:
            conn.sendall(encode_end().encode())
            return

        all_keys: list[str] = []
        for node in nodes:
            response = self._send_to_node(node, cmd_str)
            # Parse response: keys are lines; END terminates
            lines = response.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and line != RESP_END and not line.startswith(RESP_ERROR + " "):
                    all_keys.append(line)

        all_keys.sort()
        out = "\n".join(all_keys)
        if out:
            out += "\n"
        out += encode_end()
        conn.sendall(out.encode())

    # ------------------------------------------------------------------
    # Server startup
    # ------------------------------------------------------------------

    def _node_accept_loop(self) -> None:
        """Accept loop for storage node connections."""
        self._node_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._node_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._node_sock.bind(("", self.node_port))
        self._node_sock.listen(50)
        self._node_sock.settimeout(1.0)
        logger.info(f"Router listening for nodes on port {self.node_port}")

        while self._running:
            try:
                conn, addr = self._node_sock.accept()
                logger.info(f"Node connection accepted from {addr}")
                t = threading.Thread(target=self._handle_node_connection,
                                     args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("Node accept error")
                break

    def _client_accept_loop(self) -> None:
        """Accept loop for client connections."""
        self._client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._client_sock.bind(("", self.client_port))
        self._client_sock.listen(50)
        self._client_sock.settimeout(1.0)
        logger.info(f"Router listening for clients on port {self.client_port}")

        while self._running:
            try:
                conn, addr = self._client_sock.accept()
                t = threading.Thread(target=self._handle_client,
                                     args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("Client accept error")
                break

    def run(self) -> None:
        """Start the router."""
        logger.info("Router starting...")

        # Start accept threads
        node_thread = threading.Thread(target=self._node_accept_loop, daemon=True)
        client_thread = threading.Thread(target=self._client_accept_loop, daemon=True)
        health_thread = threading.Thread(target=self._health_check_loop, daemon=True)

        node_thread.start()
        client_thread.start()
        health_thread.start()

        logger.info("Router running. Press Ctrl+C to stop.")

        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Clean shutdown."""
        logger.info("Router shutting down...")
        self._running = False

        # Close server sockets
        for sock in (self._client_sock, self._node_sock):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        # Close all node connections
        with self._nodes_lock:
            for node_info in list(self._nodes.values()):
                try:
                    node_info.sock.close()
                except OSError:
                    pass
            self._nodes.clear()

        logger.info("Router stopped.")


def main():
    parser = argparse.ArgumentParser(description="Distributed KV Store Router")
    parser.add_argument("--client-port", type=int, default=5555,
                        help="Port for client connections")
    parser.add_argument("--node-port", type=int, default=5556,
                        help="Port for storage node connections")
    parser.add_argument("--health-interval", type=float, default=2.0,
                        help="Seconds between health checks")
    parser.add_argument("--health-timeout", type=float, default=1.0,
                        help="Seconds to wait for PONG")
    args = parser.parse_args()

    router = Router(
        client_port=args.client_port,
        node_port=args.node_port,
        health_interval=args.health_interval,
        health_timeout=args.health_timeout,
    )

    try:
        router.run()
    except KeyboardInterrupt:
        router.stop()


if __name__ == "__main__":
    main()
