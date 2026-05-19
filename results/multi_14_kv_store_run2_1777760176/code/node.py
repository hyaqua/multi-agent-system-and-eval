"""
node.py – Storage node process.

Starts a TCP server, registers with the router, and handles key-value
operations with optional TTL-based expiration.
"""

import socket
import threading
import time
import sys
import logging
import argparse

import protocol

logger = logging.getLogger("node")


class StorageNode:
    """Single storage node that stores key-value pairs with optional TTL."""

    def __init__(self, router_host: str, router_port: int):
        self.router_host = router_host
        self.router_port = router_port

        # In-memory store: key -> (value, expiry_time_or_None)
        self._store: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.Lock()

        # Create TCP server on a random port
        self._server_socket = socket.create_server(
            ("127.0.0.1", 0),
            reuse_port=True,
        )
        self.host, self.port = self._server_socket.getsockname()[:2]

        self._running = True

    def register_with_router(self):
        """Connect to the router and send REGISTER <port>."""
        try:
            with socket.create_connection((self.router_host, self.router_port), timeout=5) as sock:
                msg = protocol.encode_message(protocol.CMD_REGISTER, self.port)
                sock.sendall(msg)
                response_data = sock.recv(4096)
                response = protocol.decode_message(response_data)
                if response == protocol.OK:
                    logger.info(f"Registered with router at {self.router_host}:{self.router_port}")
                    return True
                else:
                    logger.error(f"Unexpected registration response: {response}")
                    return False
        except Exception as e:
            logger.error(f"Failed to register with router: {e}")
            return False

    def start(self):
        """Start the node: register, then enter the accept loop."""
        if not self.register_with_router():
            logger.error("Could not register. Exiting.")
            sys.exit(1)

        logger.info(f"Node listening on {self.host}:{self.port}")

        while self._running:
            try:
                self._server_socket.settimeout(1.0)
                client_sock, addr = self._server_socket.accept()
                t = threading.Thread(target=self._handle_connection, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")

        self._server_socket.close()

    def _handle_connection(self, sock: socket.socket):
        """Handle a single incoming TCP connection from the router."""
        try:
            sock.settimeout(5)
            data = sock.recv(4096)
            if not data:
                return
            line = protocol.decode_message(data)
            command, args = protocol.parse_command(line)
            response = self._process_command(command, args)
            sock.sendall(response.encode(protocol.ENCODING) + protocol.LINE_TERMINATOR)
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _process_command(self, command: str, args: list[str]) -> str:
        """Process a single command and return the response string."""
        if command == protocol.CMD_SET:
            return self._handle_set(args)
        elif command == protocol.CMD_GET:
            return self._handle_get(args)
        elif command == protocol.CMD_DELETE:
            return self._handle_delete(args)
        elif command == protocol.CMD_LIST:
            return self._handle_list(args)
        elif command == protocol.CMD_PING:
            return protocol.PONG
        else:
            return f"{protocol.ERROR} Unknown command: {command}"

    def _handle_set(self, args: list[str]) -> str:
        if len(args) < 2:
            return f"{protocol.ERROR} SET requires key and value"
        key = args[0]
        value = args[1]
        ttl = None
        if len(args) >= 3:
            try:
                ttl = float(args[2])
            except ValueError:
                return f"{protocol.ERROR} Invalid TTL value"
            if ttl <= 0:
                return f"{protocol.ERROR} TTL must be positive"

        expiry = (time.time() + ttl) if ttl is not None else None
        with self._lock:
            self._store[key] = (value, expiry)
        logger.debug(f"SET {key} = {value}" + (f" (TTL={ttl}s)" if ttl else ""))
        return protocol.OK

    def _handle_get(self, args: list[str]) -> str:
        if len(args) < 1:
            return f"{protocol.ERROR} GET requires key"
        key = args[0]
        with self._lock:
            if key not in self._store:
                return protocol.NOT_FOUND
            value, expiry = self._store[key]
            if expiry is not None and time.time() > expiry:
                # Expired
                del self._store[key]
                return protocol.NOT_FOUND
        return f"{protocol.VALUE} {value}"

    def _handle_delete(self, args: list[str]) -> str:
        if len(args) < 1:
            return f"{protocol.ERROR} DELETE requires key"
        key = args[0]
        with self._lock:
            if key in self._store:
                del self._store[key]
                return protocol.OK
            else:
                return protocol.NOT_FOUND

    def _handle_list(self, args: list[str]) -> str:
        prefix = args[0] if len(args) >= 1 else ""
        keys = []
        now = time.time()
        with self._lock:
            # Collect matching keys, also clean expired ones
            expired = []
            for key, (value, expiry) in self._store.items():
                if expiry is not None and now > expiry:
                    expired.append(key)
                elif key.startswith(prefix):
                    keys.append(key)
            # Clean expired
            for key in expired:
                del self._store[key]

        if not keys:
            return protocol.LIST  # header only, no keys
        return protocol.LIST + "\n" + "\n".join(sorted(keys))

    def shutdown(self):
        self._running = False
        try:
            self._server_socket.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Storage Node")
    parser.add_argument("router_host", nargs="?", default="127.0.0.1",
                        help="Router host (default: 127.0.0.1)")
    parser.add_argument("router_port", type=int, help="Router port")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [NODE] %(levelname)s: %(message)s",
    )

    node = StorageNode(args.router_host, args.router_port)
    try:
        node.start()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        node.shutdown()


if __name__ == "__main__":
    main()
