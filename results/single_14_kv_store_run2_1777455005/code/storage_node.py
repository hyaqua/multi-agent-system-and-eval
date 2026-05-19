"""Storage node process: stores key-value pairs and handles commands from the router."""

import sys
import time
import threading
import socket
import argparse

from protocol import MessageProtocol


class StorageNode:
    """A storage node that connects to the router and handles CRUD operations."""

    def __init__(self, router_host: str = "localhost", router_port: int = 7000):
        self.router_host = router_host
        self.router_port = router_port
        self.node_id: str | None = None
        self.store: dict[str, tuple[str, float | None]] = {}  # key -> (value, expiry_time)
        self.store_lock = threading.Lock()
        self.running = True
        self.proto: MessageProtocol | None = None
        self.sock: socket.socket | None = None

    def start(self) -> None:
        """Connect to the router and begin processing commands."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.router_host, self.router_port))
        except ConnectionRefusedError:
            print(f"[node] Cannot connect to router at {self.router_host}:{self.router_port}")
            sys.exit(1)

        self.proto = MessageProtocol(self.sock)
        self._register()
        print(f"[node {self.node_id}] Registered with router. Starting command loop.")

        # Start TTL cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        # Main command loop
        self._command_loop()

    def _register(self) -> None:
        """Send REGISTER message to router and get node_id."""
        self.proto.send({"cmd": "REGISTER"})
        response = self.proto.recv(timeout=10)
        if response is None or response.get("status") != "REGISTERED":
            print(f"[node] Registration failed: {response}")
            sys.exit(1)
        self.node_id = response["node_id"]

    def _command_loop(self) -> None:
        """Main loop: read commands from router and process them."""
        while self.running:
            msg = self.proto.recv(timeout=None)
            if msg is None:
                print(f"[node {self.node_id}] Connection to router lost. Exiting.")
                self.running = False
                break

            cmd = msg.get("cmd", "")
            try:
                if cmd == "SET":
                    self._handle_set(msg)
                elif cmd == "GET":
                    self._handle_get(msg)
                elif cmd == "DELETE":
                    self._handle_delete(msg)
                elif cmd == "LIST":
                    self._handle_list(msg)
                elif cmd == "PING":
                    self._handle_ping()
                else:
                    self.proto.send({"status": "ERROR", "message": f"Unknown command: {cmd}"})
            except Exception as e:
                try:
                    self.proto.send({"status": "ERROR", "message": str(e)})
                except Exception:
                    self.running = False
                    break

    def _handle_set(self, msg: dict) -> None:
        """Process a SET command."""
        key = msg.get("key", "")
        value = msg.get("value", "")
        ttl = msg.get("ttl")
        if not key:
            self.proto.send({"status": "ERROR", "message": "Key required"})
            return

        expiry = time.time() + ttl if ttl else None
        with self.store_lock:
            self.store[key] = (value, expiry)
        self.proto.send({"status": "OK"})

    def _handle_get(self, msg: dict) -> None:
        """Process a GET command."""
        key = msg.get("key", "")
        if not key:
            self.proto.send({"status": "ERROR", "message": "Key required"})
            return

        with self.store_lock:
            if key not in self.store:
                self.proto.send({"status": "NOT_FOUND"})
                return
            value, expiry = self.store[key]
            if expiry and time.time() > expiry:
                del self.store[key]
                self.proto.send({"status": "NOT_FOUND"})
                return

        self.proto.send({"status": "OK", "value": value})

    def _handle_delete(self, msg: dict) -> None:
        """Process a DELETE command."""
        key = msg.get("key", "")
        if not key:
            self.proto.send({"status": "ERROR", "message": "Key required"})
            return

        with self.store_lock:
            if key in self.store:
                del self.store[key]
                self.proto.send({"status": "OK"})
            else:
                self.proto.send({"status": "NOT_FOUND"})

    def _handle_list(self, msg: dict) -> None:
        """Process a LIST command, optionally filtered by prefix."""
        prefix = msg.get("prefix", "")
        keys = []
        now = time.time()
        with self.store_lock:
            for k in list(self.store.keys()):
                v, expiry = self.store[k]
                if expiry and now > expiry:
                    del self.store[k]
                    continue
                if k.startswith(prefix):
                    keys.append(k)
        self.proto.send({"status": "OK", "keys": keys})

    def _handle_ping(self) -> None:
        """Respond to a PING health check."""
        self.proto.send({"status": "PONG"})

    def _cleanup_loop(self) -> None:
        """Periodically clean up expired keys."""
        while self.running:
            time.sleep(2)
            now = time.time()
            with self.store_lock:
                expired = [
                    k for k, (v, exp) in self.store.items()
                    if exp and now > exp
                ]
                for k in expired:
                    del self.store[k]


def main():
    parser = argparse.ArgumentParser(description="Storage Node for Distributed KV Store")
    parser.add_argument("--router-host", default="localhost", help="Router host")
    parser.add_argument("--router-port", type=int, default=7000, help="Router port")
    args = parser.parse_args()

    node = StorageNode(router_host=args.router_host, router_port=args.router_port)
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\n[node {node.node_id}] Shutting down.")
        node.running = False
        if node.sock:
            node.sock.close()


if __name__ == "__main__":
    main()
