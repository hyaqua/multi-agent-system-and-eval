"""Router process: listens for client and node connections, distributes keys via consistent hashing."""

import sys
import time
import threading
import socket
import argparse
from datetime import datetime

from protocol import MessageProtocol
from hash_ring import ConsistentHashRing


class Router:
    """The router distributes keys across storage nodes using consistent hashing."""

    def __init__(self, host: str = "localhost", port: int = 7000, vnodes_per_node: int = 100,
                 health_check_interval: float = 5.0, health_check_timeout: float = 3.0):
        self.host = host
        self.port = port
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout

        self.hash_ring = ConsistentHashRing(vnodes_per_node=vnodes_per_node)
        # node_id -> {"proto": MessageProtocol, "lock": threading.Lock, "sock": socket.socket}
        self.node_connections: dict[str, dict] = {}
        self.node_counter = 0
        self.node_lock = threading.Lock()

        self.running = True
        self.server_sock: socket.socket | None = None

    def log(self, message: str) -> None:
        """Log a message with timestamp."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[router {ts}] {message}")

    def start(self) -> None:
        """Start the router: listen for connections and run health checks."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(50)
        self.server_sock.settimeout(1.0)  # Allow periodic check of self.running

        self.log(f"Router listening on {self.host}:{self.port}")

        # Start health check thread
        health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        health_thread.start()

        # Accept connections
        try:
            self._accept_loop()
        except KeyboardInterrupt:
            self.log("Router shutting down.")
        finally:
            self.running = False
            self._cleanup()

    def _accept_loop(self) -> None:
        """Accept incoming connections from nodes and clients."""
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if not self.running:
                    break
                continue

            self.log(f"New connection from {addr}")
            # Handle each connection in its own thread
            t = threading.Thread(target=self._handle_connection, args=(client_sock, addr), daemon=True)
            t.start()

    def _handle_connection(self, sock: socket.socket, addr: tuple) -> None:
        """Handle a new connection. Determine if it's a node or client."""
        proto = MessageProtocol(sock)

        # Read first message to determine connection type
        msg = proto.recv(timeout=10)
        if msg is None:
            self.log(f"Connection from {addr} closed without sending data")
            try:
                sock.close()
            except OSError:
                pass
            return

        cmd = msg.get("cmd", "")
        if cmd == "REGISTER":
            self._handle_node_registration(sock, proto, addr)
        else:
            # It's a client connection; handle the first command and continue
            self._handle_client(sock, proto, addr, msg)

    def _handle_node_registration(self, sock: socket.socket, proto: MessageProtocol, addr: tuple) -> None:
        """Register a new storage node."""
        with self.node_lock:
            self.node_counter += 1
            node_id = f"node_{self.node_counter}"

        # Add to hash ring
        self.hash_ring.add_node(node_id)

        # Store connection info
        with self.node_lock:
            self.node_connections[node_id] = {
                "proto": proto,
                "lock": threading.Lock(),
                "sock": sock,
            }

        # Send registration confirmation
        try:
            proto.send({"status": "REGISTERED", "node_id": node_id})
        except OSError:
            self.log(f"Failed to send REGISTERED to node from {addr}")
            self._remove_node(node_id)
            return

        self.log(f"Node {node_id} registered from {addr}. Total nodes: {len(self.node_connections)}")

    def _handle_client(self, sock: socket.socket, proto: MessageProtocol, addr: tuple, first_msg: dict) -> None:
        """Handle a client connection. Process commands until disconnect."""
        msg = first_msg
        while msg is not None:
            response = self._process_client_command(msg)
            try:
                proto.send(response)
            except OSError:
                self.log(f"Client {addr} disconnected during send")
                break

            # Read next command
            msg = proto.recv(timeout=300)  # 5 minute idle timeout
            if msg is None:
                break

        self.log(f"Client {addr} disconnected")
        try:
            sock.close()
        except OSError:
            pass

    def _process_client_command(self, msg: dict) -> dict:
        """Process a single client command and return the response."""
        cmd = msg.get("cmd", "")
        self.log(f"Processing client command: {cmd} {msg.get('key', '')}")

        if cmd == "SET":
            return self._route_set(msg)
        elif cmd == "GET":
            return self._route_get(msg)
        elif cmd == "DELETE":
            return self._route_delete(msg)
        elif cmd == "LIST":
            return self._route_list(msg)
        else:
            return {"status": "ERROR", "message": f"Unknown command: {cmd}"}

    def _route_set(self, msg: dict) -> dict:
        """Route a SET command to the appropriate node."""
        key = msg.get("key", "")
        if not key:
            return {"status": "ERROR", "message": "Key required"}

        node_id = self.hash_ring.get_node(key)
        if node_id is None:
            return {"status": "ERROR", "message": "No nodes available"}

        forward_msg = {
            "cmd": "SET",
            "key": key,
            "value": msg.get("value", ""),
            "ttl": msg.get("ttl"),
        }
        return self._forward_to_node(node_id, forward_msg)

    def _route_get(self, msg: dict) -> dict:
        """Route a GET command to the appropriate node."""
        key = msg.get("key", "")
        if not key:
            return {"status": "ERROR", "message": "Key required"}

        node_id = self.hash_ring.get_node(key)
        if node_id is None:
            return {"status": "ERROR", "message": "No nodes available"}

        forward_msg = {"cmd": "GET", "key": key}
        return self._forward_to_node(node_id, forward_msg)

    def _route_delete(self, msg: dict) -> dict:
        """Route a DELETE command to the appropriate node."""
        key = msg.get("key", "")
        if not key:
            return {"status": "ERROR", "message": "Key required"}

        node_id = self.hash_ring.get_node(key)
        if node_id is None:
            return {"status": "ERROR", "message": "No nodes available"}

        forward_msg = {"cmd": "DELETE", "key": key}
        return self._forward_to_node(node_id, forward_msg)

    def _route_list(self, msg: dict) -> dict:
        """Broadcast a LIST command to all nodes and aggregate results."""
        prefix = msg.get("prefix", "")
        forward_msg = {"cmd": "LIST", "prefix": prefix}

        all_keys: list[str] = []
        with self.node_lock:
            node_ids = list(self.node_connections.keys())

        if not node_ids:
            return {"status": "OK", "keys": []}

        for node_id in node_ids:
            response = self._forward_to_node(node_id, forward_msg)
            if response and response.get("status") == "OK":
                all_keys.extend(response.get("keys", []))

        return {"status": "OK", "keys": sorted(all_keys)}

    def _forward_to_node(self, node_id: str, cmd: dict) -> dict | None:
        """
        Forward a command to a specific node and return the response.
        Returns None if the node is unreachable.
        """
        with self.node_lock:
            conn_info = self.node_connections.get(node_id)

        if conn_info is None:
            return {"status": "ERROR", "message": f"Node {node_id} not found"}

        lock = conn_info["lock"]
        proto = conn_info["proto"]

        with lock:
            try:
                proto.send(cmd)
                response = proto.recv(timeout=5)
                if response is None:
                    self.log(f"Node {node_id} timed out or disconnected during command {cmd.get('cmd')}")
                    self._remove_node(node_id)
                    return {"status": "ERROR", "message": f"Node {node_id} is unreachable"}
                return response
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                self.log(f"Node {node_id} communication error: {e}")
                self._remove_node(node_id)
                return {"status": "ERROR", "message": f"Node {node_id} is unreachable"}

    def _health_check_loop(self) -> None:
        """Periodically ping all nodes to check their health."""
        while self.running:
            time.sleep(self.health_check_interval)

            with self.node_lock:
                node_ids = list(self.node_connections.keys())

            for node_id in node_ids:
                if not self.running:
                    break

                with self.node_lock:
                    conn_info = self.node_connections.get(node_id)
                if conn_info is None:
                    continue

                lock = conn_info["lock"]
                proto = conn_info["proto"]

                acquired = lock.acquire(timeout=self.health_check_timeout)
                if not acquired:
                    self.log(f"Health check: Could not acquire lock for {node_id}, skipping")
                    continue

                try:
                    proto.send({"cmd": "PING"})
                    response = proto.recv(timeout=self.health_check_timeout)
                    if response is None or response.get("status") != "PONG":
                        self.log(f"Health check failed for {node_id}: no PONG response")
                        lock.release()
                        self._remove_node(node_id)
                    else:
                        lock.release()
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    self.log(f"Health check failed for {node_id}: {e}")
                    try:
                        lock.release()
                    except RuntimeError:
                        pass
                    self._remove_node(node_id)

    def _remove_node(self, node_id: str) -> None:
        """Remove a failed node from the ring and clean up its connection."""
        with self.node_lock:
            if node_id not in self.node_connections:
                return
            conn_info = self.node_connections.pop(node_id, None)

        if conn_info:
            try:
                conn_info["proto"].close()
            except OSError:
                pass

        self.hash_ring.remove_node(node_id)
        self.log(f"Node {node_id} removed from ring. Remaining nodes: {len(self.node_connections)}")
        self.log(f"Key range for {node_id} redistributed to remaining nodes")

    def _cleanup(self) -> None:
        """Clean up all resources."""
        self.running = False
        with self.node_lock:
            for conn_info in self.node_connections.values():
                try:
                    conn_info["proto"].close()
                except OSError:
                    pass
            self.node_connections.clear()
        if self.server_sock:
            try:
                self.server_sock.close()
            except OSError:
                pass
        self.log("Router stopped")


def main():
    parser = argparse.ArgumentParser(description="Router for Distributed KV Store")
    parser.add_argument("--host", default="localhost", help="Listen host")
    parser.add_argument("--port", type=int, default=7000, help="Listen port")
    parser.add_argument("--vnodes", type=int, default=100, help="Virtual nodes per storage node")
    parser.add_argument("--health-interval", type=float, default=5.0, help="Health check interval in seconds")
    parser.add_argument("--health-timeout", type=float, default=3.0, help="Health check timeout in seconds")
    args = parser.parse_args()

    router = Router(
        host=args.host,
        port=args.port,
        vnodes_per_node=args.vnodes,
        health_check_interval=args.health_interval,
        health_check_timeout=args.health_timeout,
    )
    try:
        router.start()
    except KeyboardInterrupt:
        router.log("Router interrupted. Shutting down.")


if __name__ == "__main__":
    main()
