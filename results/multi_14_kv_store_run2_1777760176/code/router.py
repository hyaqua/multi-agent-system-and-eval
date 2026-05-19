"""
router.py – Main router process.

Accepts client connections, maintains a consistent hash ring of storage nodes,
forwards CRUD commands to the appropriate node, handles LIST aggregation,
and periodically health-checks nodes.
"""

import socket
import threading
import time
import logging
import sys
import argparse

import protocol
from hash_ring import HashRing

logger = logging.getLogger("router")


class Router:
    """Central router that manages the consistent hash ring and forwards commands."""

    def __init__(self, port: int, virtual_nodes_per_node: int = 128,
                 health_interval: float = 2.0, health_timeout: float = 1.0):
        self.port = port
        self.health_interval = health_interval
        self.health_timeout = health_timeout

        # Consistent hash ring
        self.ring = HashRing(virtual_nodes_per_node=virtual_nodes_per_node)

        # Node registry: node_id -> (host, port) – also accessible via ring
        self._node_lock = threading.Lock()

        # Server socket for clients
        self._server_socket = socket.create_server(
            ("127.0.0.1", port),
            reuse_port=True,
        )
        self._running = True

        # Health check thread
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)

        # Counter for generating node IDs
        self._next_node_id = 0

    def start(self):
        """Start the router: begin accepting client connections and health checks."""
        self._health_thread.start()
        logger.info(f"Router listening for clients on port {self.port}")

        while self._running:
            try:
                self._server_socket.settimeout(1.0)
                client_sock, addr = self._server_socket.accept()
                logger.info(f"Accepted connection from {addr}")
                t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")

        self._server_socket.close()

    def _handle_client(self, sock: socket.socket, addr: tuple):
        """Handle a TCP connection from a client or a registering node."""
        try:
            sock.settimeout(10)
            data = sock.recv(4096)
            if not data:
                return

            line = protocol.decode_message(data)
            command, args = protocol.parse_command(line)

            if command == protocol.CMD_REGISTER:
                # Node registration
                self._handle_register(sock, args, addr)
            else:
                # Client command
                response = self._handle_client_command(command, args)
                sock.sendall(response.encode(protocol.ENCODING) + protocol.LINE_TERMINATOR)
        except Exception as e:
            logger.error(f"Error handling connection from {addr}: {e}")
            try:
                sock.sendall(f"{protocol.ERROR} {e}".encode() + protocol.LINE_TERMINATOR)
            except Exception:
                pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_register(self, sock: socket.socket, args: list[str], addr: tuple):
        """Handle a REGISTER command from a storage node."""
        if len(args) < 1:
            sock.sendall(
                f"{protocol.ERROR} REGISTER requires port".encode() + protocol.LINE_TERMINATOR
            )
            return

        try:
            node_port = int(args[0])
        except ValueError:
            sock.sendall(
                f"{protocol.ERROR} Invalid port".encode() + protocol.LINE_TERMINATOR
            )
            return

        # Use the host from the connecting address
        node_host = addr[0]
        node_id = f"node-{self._next_node_id}"
        self._next_node_id += 1

        self.ring.add_node(node_id, node_host, node_port)
        logger.info(f"Node {node_id} registered: {node_host}:{node_port}")

        sock.sendall(protocol.encode_message(protocol.OK))

    def _handle_client_command(self, command: str, args: list[str]) -> str:
        """Handle a client command: route to appropriate node(s)."""
        logger.info(f"Client command: {command} {' '.join(args)}")

        if command == protocol.CMD_SET:
            return self._route_set(args)
        elif command == protocol.CMD_GET:
            return self._route_get(args)
        elif command == protocol.CMD_DELETE:
            return self._route_delete(args)
        elif command == protocol.CMD_LIST:
            return self._route_list(args)
        elif command == protocol.CMD_PING:
            return protocol.PONG
        elif command == protocol.CMD_QUIT:
            return protocol.OK
        else:
            return f"{protocol.ERROR} Unknown command: {command}"

    def _send_to_node(self, host: str, port: int, message: str, timeout: float = 5.0) -> str | None:
        """Send a message to a storage node and return its response, or None on failure."""
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                sock.sendall(message.encode(protocol.ENCODING) + protocol.LINE_TERMINATOR)
                response_data = sock.recv(65536)
                return protocol.decode_message(response_data)
        except Exception as e:
            logger.error(f"Failed to communicate with node {host}:{port}: {e}")
            return None

    def _route_set(self, args: list[str]) -> str:
        if len(args) < 2:
            return f"{protocol.ERROR} SET requires key and value"
        key = args[0]
        value = args[1]
        ttl_str = args[2] if len(args) >= 3 else None

        node = self.ring.get_node(key)
        if node is None:
            return f"{protocol.ERROR} No nodes available"

        node_id, host, port = node
        # Build command for node
        if ttl_str:
            node_cmd = f"{protocol.CMD_SET} {key} {value} {ttl_str}"
        else:
            node_cmd = f"{protocol.CMD_SET} {key} {value}"

        response = self._send_to_node(host, port, node_cmd)
        if response is None:
            return f"{protocol.ERROR} Node {node_id} is unreachable"
        return response

    def _route_get(self, args: list[str]) -> str:
        if len(args) < 1:
            return f"{protocol.ERROR} GET requires key"
        key = args[0]

        node = self.ring.get_node(key)
        if node is None:
            return f"{protocol.ERROR} No nodes available"

        node_id, host, port = node
        node_cmd = f"{protocol.CMD_GET} {key}"
        response = self._send_to_node(host, port, node_cmd)
        if response is None:
            return f"{protocol.ERROR} Node {node_id} is unreachable"
        return response

    def _route_delete(self, args: list[str]) -> str:
        if len(args) < 1:
            return f"{protocol.ERROR} DELETE requires key"
        key = args[0]

        node = self.ring.get_node(key)
        if node is None:
            return f"{protocol.ERROR} No nodes available"

        node_id, host, port = node
        node_cmd = f"{protocol.CMD_DELETE} {key}"
        response = self._send_to_node(host, port, node_cmd)
        if response is None:
            return f"{protocol.ERROR} Node {node_id} is unreachable"
        return response

    def _route_list(self, args: list[str]) -> str:
        prefix = args[0] if len(args) >= 1 else ""
        all_nodes = self.ring.get_all_nodes()

        if not all_nodes:
            return f"{protocol.ERROR} No nodes available"

        node_cmd = protocol.build_list_command(prefix)
        all_keys: set[str] = set()

        for node_id, host, port in all_nodes:
            response = self._send_to_node(host, port, node_cmd)
            if response is not None:
                # Parse the LIST response
                lines = response.split("\n")
                # First line should be "LIST"
                if lines and lines[0] == protocol.LIST:
                    for line in lines[1:]:
                        line = line.strip()
                        if line:
                            all_keys.add(line)

        if not all_keys:
            return protocol.LIST  # header only, no keys
        return protocol.LIST + "\n" + "\n".join(sorted(all_keys))

    def _health_check_loop(self):
        """Periodically check all registered nodes via PING."""
        while self._running:
            time.sleep(self.health_interval)
            if not self._running:
                break

            nodes = self.ring.get_all_nodes()
            for node_id, host, port in nodes:
                if not self._running:
                    break
                self._check_node(node_id, host, port)

    def _check_node(self, node_id: str, host: str, port: int):
        """Ping a single node and remove it if unresponsive."""
        response = self._send_to_node(host, port, protocol.CMD_PING, timeout=self.health_timeout)
        if response is None or response.strip() != protocol.PONG:
            logger.warning(f"Node {node_id} ({host}:{port}) failed health check. Removing from ring.")
            self.ring.remove_node(node_id)
            logger.info(f"Node {node_id} removed. Keys redistributed among remaining nodes.")

    def shutdown(self):
        """Shut down the router."""
        self._running = False
        try:
            self._server_socket.close()
        except Exception:
            pass
        logger.info("Router shut down.")


def main():
    parser = argparse.ArgumentParser(description="Distributed KV Store Router")
    parser.add_argument("--port", type=int, default=7000, help="Port for client connections (default: 7000)")
    parser.add_argument("--virtual-nodes", type=int, default=128,
                        help="Virtual nodes per physical node (default: 128)")
    parser.add_argument("--health-interval", type=float, default=2.0,
                        help="Health check interval in seconds (default: 2.0)")
    parser.add_argument("--health-timeout", type=float, default=1.0,
                        help="Health check timeout in seconds (default: 1.0)")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [ROUTER] %(levelname)s: %(message)s",
    )

    router = Router(
        port=args.port,
        virtual_nodes_per_node=args.virtual_nodes,
        health_interval=args.health_interval,
        health_timeout=args.health_timeout,
    )
    try:
        router.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        router.shutdown()


if __name__ == "__main__":
    main()
