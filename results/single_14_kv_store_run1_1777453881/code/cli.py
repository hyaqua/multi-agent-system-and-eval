"""
Simple CLI client for interacting with the distributed key-value store.

Connects to the router via TCP and sends text-based commands.
"""
import socket
import sys
import argparse

from protocol import (
    DEFAULT_CLIENT_PORT,
    LINE_TERM,
    CMD_CLI_SET, CMD_CLI_GET, CMD_CLI_DELETE, CMD_CLI_LIST,
    CMD_CLI_QUIT, CMD_CLI_EXIT,
    RESP_OK, RESP_VALUE, RESP_NOT_FOUND, RESP_DELETED,
    RESP_KEYS, RESP_ERROR, RESP_PONG,
)


class KVClient:
    """CLI client for the distributed KV store."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def send_command(self, command: str) -> str:
        """Send a command to the router and return the response."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
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
            return data.decode('utf-8', errors='replace').strip()
        except ConnectionRefusedError:
            return f"{RESP_ERROR} connection refused - is the router running?"
        except socket.timeout:
            return f"{RESP_ERROR} connection timed out"
        except Exception as e:
            return f"{RESP_ERROR} {e}"

    def set(self, key: str, value: str, ttl: int | None = None) -> str:
        """Set a key-value pair, optionally with TTL."""
        cmd = f"{CMD_CLI_SET} {key} {value}"
        if ttl is not None:
            cmd += f" {ttl}"
        return self.send_command(cmd)

    def get(self, key: str) -> str:
        """Get a value by key."""
        cmd = f"{CMD_CLI_GET} {key}"
        return self.send_command(cmd)

    def delete(self, key: str) -> str:
        """Delete a key."""
        cmd = f"{CMD_CLI_DELETE} {key}"
        return self.send_command(cmd)

    def list_keys(self, prefix: str | None = None) -> str:
        """List keys, optionally filtered by prefix."""
        cmd = CMD_CLI_LIST
        if prefix:
            cmd += f" {prefix}"
        return self.send_command(cmd)

    def interactive(self) -> None:
        """Run an interactive CLI session."""
        print(f"Connected to KV store at {self.host}:{self.port}")
        print("Commands: SET <key> <value> [TTL], GET <key>, DELETE <key>, LIST [prefix], QUIT")
        print()

        while True:
            try:
                line = input("kv> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            parts = line.split(' ', 2)
            cmd = parts[0].upper()

            if cmd in (CMD_CLI_QUIT, CMD_CLI_EXIT):
                print("Bye!")
                break
            elif cmd == CMD_CLI_SET:
                if len(parts) < 3:
                    print("Usage: SET <key> <value> [TTL]")
                    continue
                key = parts[1]
                rest = parts[2]
                rest_parts = rest.rsplit(' ', 1)
                ttl = None
                if len(rest_parts) == 2 and rest_parts[1].isdigit():
                    value = rest_parts[0]
                    ttl = int(rest_parts[1])
                else:
                    value = rest
                response = self.set(key, value, ttl)
                print(response)
            elif cmd == CMD_CLI_GET:
                if len(parts) < 2:
                    print("Usage: GET <key>")
                    continue
                response = self.get(parts[1])
                print(response)
            elif cmd == CMD_CLI_DELETE:
                if len(parts) < 2:
                    print("Usage: DELETE <key>")
                    continue
                response = self.delete(parts[1])
                print(response)
            elif cmd == CMD_CLI_LIST:
                prefix = parts[1] if len(parts) > 1 else None
                response = self.list_keys(prefix)
                self._print_list_response(response)
            else:
                print(f"Unknown command: {cmd}")
                print("Available: SET, GET, DELETE, LIST, QUIT")

    def _print_list_response(self, response: str) -> None:
        """Pretty-print a LIST/KEYS response."""
        if response.startswith(RESP_ERROR):
            print(response)
        elif response.startswith(RESP_KEYS):
            parts = response.split(' ', 2)
            try:
                count = int(parts[1])
                if count == 0:
                    print("(empty)")
                else:
                    keys = parts[2].split(' ') if len(parts) > 2 else []
                    for k in keys:
                        print(k)
            except (ValueError, IndexError):
                print(response)
        else:
            print(response)


def main():
    parser = argparse.ArgumentParser(description="CLI client for distributed KV store")
    parser.add_argument("--host", default="127.0.0.1", help="Router host")
    parser.add_argument("--port", type=int, default=DEFAULT_CLIENT_PORT, help="Router client port")
    parser.add_argument("command", nargs="*", help="Command to execute (non-interactive mode)")
    args = parser.parse_args()

    client = KVClient(args.host, args.port)

    if args.command:
        # Non-interactive mode
        cmd = " ".join(args.command)
        if cmd.upper() in (CMD_CLI_QUIT, CMD_CLI_EXIT):
            return
        response = client.send_command(cmd)
        if response.startswith(RESP_KEYS):
            # Pretty-print list
            client._print_list_response(response)
        else:
            print(response)
    else:
        # Interactive mode
        client.interactive()


if __name__ == "__main__":
    main()
