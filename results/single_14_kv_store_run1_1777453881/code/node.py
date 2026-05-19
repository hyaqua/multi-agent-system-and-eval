"""
Storage node process for the distributed key-value store.

Each node listens for TCP connections from the router, stores key-value
pairs with optional TTL, and handles CRUD operations.
"""
import socket
import threading
import time
import sys
import signal
import logging
import argparse

from protocol import (
    DEFAULT_NODE_START_PORT, DEFAULT_NODE_PORT,
    LINE_TERM,
    CMD_PUT, CMD_GET, CMD_DELETE, CMD_KEYS, CMD_PING, CMD_REGISTER,
    RESP_OK, RESP_VALUE, RESP_NOT_FOUND, RESP_DELETED,
    RESP_KEYS, RESP_PONG, RESP_ERROR,
)

logger = logging.getLogger("node")


class StorageNode:
    """A storage node that holds key-value pairs with TTL support."""

    def __init__(self, host: str, port: int, router_host: str, router_port: int,
                 cleanup_interval: float = 5.0):
        self.host = host
        self.port = port
        self.router_host = router_host
        self.router_port = router_port
        self.cleanup_interval = cleanup_interval
        self.store: dict[str, tuple[str, float | None]] = {}  # key -> (value, expiry_time)
        self.lock = threading.RLock()
        self.running = True
        self.server_socket: socket.socket | None = None
        self.node_id = f"{host}:{port}"

    def _cleanup_expired(self) -> None:
        """Remove expired keys from the store."""
        while self.running:
            time.sleep(self.cleanup_interval)
            if not self.running:
                break
            with self.lock:
                now = time.time()
                expired_keys = [
                    key for key, (_, expiry) in self.store.items()
                    if expiry is not None and now >= expiry
                ]
                for key in expired_keys:
                    del self.store[key]
                if expired_keys:
                    logger.debug("Cleaned up %d expired keys", len(expired_keys))

    def _is_expired(self, key: str) -> bool:
        """Check if a key is expired. Must hold lock."""
        if key not in self.store:
            return False
        _, expiry = self.store[key]
        if expiry is not None and time.time() >= expiry:
            del self.store[key]
            return True
        return False

    def _handle_command(self, command: str) -> str:
        """Process a single command and return the response."""
        parts = command.strip().split(' ', 2)
        if not parts:
            return f"{RESP_ERROR} empty command"

        cmd = parts[0].upper()

        if cmd == CMD_PING:
            return RESP_PONG

        elif cmd == CMD_PUT:
            # PUT key value [ttl]
            if len(parts) < 3:
                return f"{RESP_ERROR} PUT requires key and value"
            key = parts[1]
            rest = parts[2]
            # Parse value and optional TTL
            rest_parts = rest.rsplit(' ', 1)
            ttl = None
            if len(rest_parts) == 2 and rest_parts[1].isdigit():
                value = rest_parts[0]
                ttl = int(rest_parts[1])
            else:
                value = rest

            expiry = (time.time() + ttl) if ttl is not None else None

            with self.lock:
                self.store[key] = (value, expiry)
            logger.debug("PUT key=%s ttl=%s", key, ttl)
            return RESP_OK

        elif cmd == CMD_GET:
            if len(parts) < 2:
                return f"{RESP_ERROR} GET requires key"
            key = parts[1]
            with self.lock:
                if self._is_expired(key):
                    return RESP_NOT_FOUND
                if key in self.store:
                    value, _ = self.store[key]
                    return f"{RESP_VALUE} {value}"
                return RESP_NOT_FOUND

        elif cmd == CMD_DELETE:
            if len(parts) < 2:
                return f"{RESP_ERROR} DELETE requires key"
            key = parts[1]
            with self.lock:
                if key in self.store:
                    del self.store[key]
                    return RESP_DELETED
                return RESP_NOT_FOUND

        elif cmd == CMD_KEYS:
            # KEYS [prefix]
            prefix = parts[1] if len(parts) > 1 else ""
            with self.lock:
                now = time.time()
                # Clean expired while gathering keys
                keys = []
                expired = []
                for k, (_, expiry) in self.store.items():
                    if expiry is not None and now >= expiry:
                        expired.append(k)
                    elif not prefix or k.startswith(prefix):
                        keys.append(k)
                for k in expired:
                    del self.store[k]
                return f"{RESP_KEYS} {len(keys)} " + " ".join(keys)

        else:
            return f"{RESP_ERROR} unknown command: {cmd}"

    def _handle_client(self, client_sock: socket.socket) -> None:
        """Handle a single connection from the router."""
        try:
            client_sock.settimeout(30)
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

            if data:
                command = data.decode('utf-8', errors='replace').strip()
                if command:
                    response = self._handle_command(command)
                    client_sock.sendall((response + LINE_TERM).encode('utf-8'))
        except Exception as e:
            logger.error("Error handling connection: %s", e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _register_with_router(self) -> bool:
        """Register this node with the router."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.router_host, self.router_port))
            # Send registration
            msg = f"{CMD_REGISTER} {self.port}{LINE_TERM}"
            sock.sendall(msg.encode('utf-8'))
            # Read response
            data = sock.recv(1024)
            response = data.decode('utf-8', errors='replace').strip()
            sock.close()
            if response == RESP_OK:
                logger.info("Registered with router at %s:%d", self.router_host, self.router_port)
                return True
            else:
                logger.error("Router rejected registration: %s", response)
                return False
        except Exception as e:
            logger.error("Failed to register with router: %s", e)
            return False

    def start(self) -> None:
        """Start the storage node."""
        # Start listening for router connections FIRST
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(1.0)  # Allow checking self.running
        logger.info("Storage node listening on %s:%d", self.host, self.port)

        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        cleanup_thread.start()

        # Now register with router
        if not self._register_with_router():
            logger.error("Could not register with router. Exiting.")
            self.server_socket.close()
            sys.exit(1)

        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error("Accept error: %s", e)

        self.server_socket.close()
        logger.info("Storage node shut down.")

    def stop(self) -> None:
        """Signal the node to stop."""
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Storage Node for distributed KV store")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=None,
                        help="Port to listen on (default: auto-assign starting from 6000)")
    parser.add_argument("--router-host", default="127.0.0.1", help="Router host")
    parser.add_argument("--router-port", type=int, default=DEFAULT_NODE_PORT,
                        help="Router node-registration port")
    parser.add_argument("--cleanup-interval", type=float, default=5.0,
                        help="TTL cleanup interval in seconds")
    args = parser.parse_args()

    # Auto-assign port if not specified
    if args.port is None:
        # Try ports starting from DEFAULT_NODE_START_PORT
        port = DEFAULT_NODE_START_PORT
        while True:
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.bind((args.host, port))
                test_sock.close()
                args.port = port
                break
            except OSError:
                port += 1
                if port > DEFAULT_NODE_START_PORT + 1000:
                    print("No available port found", file=sys.stderr)
                    sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format=f"[NODE {args.port}] %(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    node = StorageNode(
        host=args.host,
        port=args.port,
        router_host=args.router_host,
        router_port=args.router_port,
        cleanup_interval=args.cleanup_interval,
    )

    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        node.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    node.start()


if __name__ == "__main__":
    main()
