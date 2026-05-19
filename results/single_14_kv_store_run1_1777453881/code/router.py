"""
Router process for the distributed key-value store.

The router accepts client connections on one port and node registrations
on another. It uses consistent hashing to distribute keys across storage
nodes, performs health checks, and handles node failures.
"""
import socket
import threading
import time
import sys
import signal
import logging
import argparse

from protocol import (
    DEFAULT_CLIENT_PORT, DEFAULT_NODE_PORT,
    LINE_TERM,
    CMD_PUT, CMD_GET, CMD_DELETE, CMD_KEYS, CMD_PING, CMD_REGISTER,
    RESP_OK, RESP_VALUE, RESP_NOT_FOUND, RESP_DELETED,
    RESP_KEYS, RESP_PONG, RESP_ERROR,
    CMD_CLI_SET, CMD_CLI_GET, CMD_CLI_DELETE, CMD_CLI_LIST,
    CMD_CLI_QUIT, CMD_CLI_EXIT,
    ConsistentHash,
)

logger = logging.getLogger("router")


class Router:
    """Router that distributes key-value operations across storage nodes."""

    def __init__(self, client_host: str, client_port: int,
                 node_host: str, node_port: int,
                 health_check_interval: float = 5.0,
                 health_timeout: float = 2.0,
                 virtual_nodes: int = 100):
        self.client_host = client_host
        self.client_port = client_port
        self.node_host = node_host
        self.node_port = node_port
        self.health_check_interval = health_check_interval
        self.health_timeout = health_timeout
        self.virtual_nodes = virtual_nodes

        # Consistent hash ring
        self.ring = ConsistentHash(virtual_nodes=virtual_nodes)

        # Node address registry: node_id -> (host, port)
        self.node_addrs: dict[str, tuple[str, int]] = {}
        self.node_lock = threading.RLock()

        # Running flag
        self.running = True

        # Server sockets
        self.client_server: socket.socket | None = None
        self.node_server: socket.socket | None = None

    def _send_to_node(self, node_id: str, command: str) -> str:
        """Send a command to a storage node and return the response."""
        with self.node_lock:
            if node_id not in self.node_addrs:
                return f"{RESP_ERROR} node not found: {node_id}"
            host, port = self.node_addrs[node_id]

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, port))
            sock.sendall((command + LINE_TERM).encode('utf-8'))
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if LINE_TERM.encode() in data:
                    break
            sock.close()
            response = data.decode('utf-8', errors='replace').strip()
            return response
        except Exception as e:
            logger.warning("Failed to communicate with node %s: %s", node_id, e)
            return f"{RESP_ERROR} node unreachable: {node_id}"

    def _handle_node_registration(self, client_sock: socket.socket) -> None:
        """Handle a node registration connection."""
        try:
            client_sock.settimeout(10)
            data = client_sock.recv(1024)
            if data:
                msg = data.decode('utf-8', errors='replace').strip()
                parts = msg.split(' ', 1)
                if len(parts) >= 2 and parts[0].upper() == CMD_REGISTER:
                    try:
                        node_port = int(parts[1])
                    except ValueError:
                        client_sock.sendall(f"{RESP_ERROR} invalid port{LINE_TERM}".encode('utf-8'))
                        client_sock.close()
                        return

                    # Get the node's address from the connection
                    node_host, _ = client_sock.getpeername()
                    node_id = f"{node_host}:{node_port}"

                    with self.node_lock:
                        if node_id in self.node_addrs:
                            logger.info("Node %s re-registering", node_id)
                        else:
                            logger.info("Node %s registered", node_id)
                        self.node_addrs[node_id] = (node_host, node_port)

                    # Add to consistent hash ring
                    self.ring.add_node(node_id)

                    client_sock.sendall(f"{RESP_OK}{LINE_TERM}".encode('utf-8'))
                    logger.info("Node %s added to ring (total nodes: %d)",
                                node_id, self.ring.node_count())
                else:
                    client_sock.sendall(f"{RESP_ERROR} expected REGISTER{LINE_TERM}".encode('utf-8'))
        except Exception as e:
            logger.error("Error handling node registration: %s", e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _handle_client(self, client_sock: socket.socket, addr: tuple) -> None:
        """Handle a client connection."""
        logger.info("Client connected from %s:%d", addr[0], addr[1])
        try:
            client_sock.settimeout(60)
            data = b""
            while True:
                try:
                    chunk = client_sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if LINE_TERM.encode() in data:
                        break
                except socket.timeout:
                    break

            if not data:
                return

            command = data.decode('utf-8', errors='replace').strip()
            if not command:
                response = f"{RESP_ERROR} empty command"
            else:
                response = self._process_client_command(command)

            client_sock.sendall((response + LINE_TERM).encode('utf-8'))
            logger.info("Client %s:%d command=%s -> %s", addr[0], addr[1],
                        command.split()[0] if command else "EMPTY",
                        response.split()[0] if response else "EMPTY")
        except Exception as e:
            logger.error("Error handling client %s:%d: %s", addr[0], addr[1], e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _process_client_command(self, command: str) -> str:
        """Process a client command and return the response."""
        parts = command.strip().split(' ', 2)
        if not parts:
            return f"{RESP_ERROR} empty command"

        cmd = parts[0].upper()

        if cmd == CMD_CLI_SET:
            # SET key value [TTL]
            if len(parts) < 3:
                return f"{RESP_ERROR} SET requires key and value"
            key = parts[1]
            rest = parts[2]
            # Parse value and optional TTL
            rest_parts = rest.rsplit(' ', 1)
            ttl_str = None
            if len(rest_parts) == 2 and rest_parts[1].isdigit():
                value = rest_parts[0]
                ttl_str = rest_parts[1]
            else:
                value = rest

            node_id = self.ring.get_node(key)
            if node_id is None:
                return f"{RESP_ERROR} no nodes available"

            node_cmd = f"{CMD_PUT} {key} {value}"
            if ttl_str:
                node_cmd += f" {ttl_str}"

            logger.info("Routing SET key=%s to node %s", key, node_id)
            return self._send_to_node(node_id, node_cmd)

        elif cmd == CMD_CLI_GET:
            if len(parts) < 2:
                return f"{RESP_ERROR} GET requires key"
            key = parts[1]

            node_id = self.ring.get_node(key)
            if node_id is None:
                return f"{RESP_ERROR} no nodes available"

            logger.info("Routing GET key=%s to node %s", key, node_id)
            return self._send_to_node(node_id, f"{CMD_GET} {key}")

        elif cmd == CMD_CLI_DELETE:
            if len(parts) < 2:
                return f"{RESP_ERROR} DELETE requires key"
            key = parts[1]

            node_id = self.ring.get_node(key)
            if node_id is None:
                return f"{RESP_ERROR} no nodes available"

            logger.info("Routing DELETE key=%s to node %s", key, node_id)
            return self._send_to_node(node_id, f"{CMD_DELETE} {key}")

        elif cmd == CMD_CLI_LIST:
            prefix = parts[1] if len(parts) > 1 else ""

            all_nodes = self.ring.all_nodes()
            if not all_nodes:
                return f"{RESP_ERROR} no nodes available"

            all_keys = []
            for node_id in all_nodes:
                node_cmd = f"{CMD_KEYS} {prefix}"
                response = self._send_to_node(node_id, node_cmd)
                if response.startswith(RESP_KEYS):
                    try:
                        resp_parts = response.split(' ', 2)
                        count = int(resp_parts[1])
                        if count > 0 and len(resp_parts) > 2:
                            keys = resp_parts[2].split(' ')
                            all_keys.extend(keys)
                    except (ValueError, IndexError):
                        logger.warning("Malformed KEYS response from node %s: %s", node_id, response)
                elif response.startswith(RESP_ERROR):
                    logger.warning("Node %s error on KEYS: %s", node_id, response)

            all_keys.sort()
            return f"{RESP_KEYS} {len(all_keys)} " + " ".join(all_keys)

        elif cmd in (CMD_CLI_QUIT, CMD_CLI_EXIT):
            return RESP_OK

        else:
            return f"{RESP_ERROR} unknown command: {cmd}"

    def _health_check_loop(self) -> None:
        """Periodically check health of all registered nodes."""
        while self.running:
            time.sleep(self.health_check_interval)
            if not self.running:
                break

            with self.node_lock:
                nodes_to_check = list(self.node_addrs.items())

            for node_id, (host, port) in nodes_to_check:
                if not self.running:
                    break
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.health_timeout)
                    sock.connect((host, port))
                    sock.sendall(f"{CMD_PING}{LINE_TERM}".encode('utf-8'))
                    data = sock.recv(1024)
                    sock.close()
                    response = data.decode('utf-8', errors='replace').strip()
                    if response == RESP_PONG:
                        logger.debug("Health check OK for node %s", node_id)
                    else:
                        logger.warning("Health check unexpected response from %s: %s", node_id, response)
                        self._mark_node_failed(node_id)
                except Exception as e:
                    logger.warning("Health check failed for node %s: %s", node_id, e)
                    self._mark_node_failed(node_id)

    def _mark_node_failed(self, node_id: str) -> None:
        """Mark a node as failed and remove it from the ring."""
        with self.node_lock:
            if node_id in self.node_addrs:
                logger.info("Removing failed node %s", node_id)
                del self.node_addrs[node_id]
        self.ring.remove_node(node_id)
        logger.info("Node %s removed from ring (remaining nodes: %d)",
                    node_id, self.ring.node_count())

    def start(self) -> None:
        """Start the router."""
        # Start client listener
        self.client_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_server.bind((self.client_host, self.client_port))
        self.client_server.listen(50)
        self.client_server.settimeout(1.0)
        logger.info("Router client listener on %s:%d", self.client_host, self.client_port)

        # Start node registration listener
        self.node_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.node_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.node_server.bind((self.node_host, self.node_port))
        self.node_server.listen(50)
        self.node_server.settimeout(1.0)
        logger.info("Router node registration listener on %s:%d", self.node_host, self.node_port)

        # Start health check thread
        health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        health_thread.start()

        logger.info("Router running. Waiting for nodes and clients...")

        while self.running:
            # Accept client connections
            try:
                client_sock, addr = self.client_server.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                t.start()
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    logger.error("Client accept error: %s", e)

            # Accept node registrations
            try:
                node_sock, addr = self.node_server.accept()
                t = threading.Thread(target=self._handle_node_registration, args=(node_sock,), daemon=True)
                t.start()
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    logger.error("Node accept error: %s", e)

        # Cleanup
        if self.client_server:
            self.client_server.close()
        if self.node_server:
            self.node_server.close()
        logger.info("Router shut down.")

    def stop(self) -> None:
        """Signal the router to stop."""
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Router for distributed KV store")
    parser.add_argument("--client-host", default="127.0.0.1", help="Host for client connections")
    parser.add_argument("--client-port", type=int, default=DEFAULT_CLIENT_PORT,
                        help="Port for client connections")
    parser.add_argument("--node-host", default="127.0.0.1", help="Host for node registrations")
    parser.add_argument("--node-port", type=int, default=DEFAULT_NODE_PORT,
                        help="Port for node registrations")
    parser.add_argument("--health-interval", type=float, default=5.0,
                        help="Health check interval in seconds")
    parser.add_argument("--health-timeout", type=float, default=2.0,
                        help="Health check timeout in seconds")
    parser.add_argument("--virtual-nodes", type=int, default=100,
                        help="Number of virtual nodes per physical node")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[ROUTER] %(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    router = Router(
        client_host=args.client_host,
        client_port=args.client_port,
        node_host=args.node_host,
        node_port=args.node_port,
        health_check_interval=args.health_interval,
        health_timeout=args.health_timeout,
        virtual_nodes=args.virtual_nodes,
    )

    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        router.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    router.start()


if __name__ == "__main__":
    main()
