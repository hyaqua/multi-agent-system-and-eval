"""CLI client for interacting with the distributed KV store."""

import sys
import socket
import argparse
import readline  # noqa: for better input handling

from protocol import MessageProtocol


class KVClient:
    """A simple client for the distributed key-value store."""

    def __init__(self, host: str = "localhost", port: int = 7000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.proto: MessageProtocol | None = None

    def connect(self) -> None:
        """Connect to the router."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(10)
            self.proto = MessageProtocol(self.sock)
        except ConnectionRefusedError:
            print(f"Error: Cannot connect to router at {self.host}:{self.port}")
            sys.exit(1)

    def close(self) -> None:
        """Close the connection."""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def send_command(self, cmd: dict) -> dict:
        """Send a command and return the response."""
        if self.proto is None:
            return {"status": "ERROR", "message": "Not connected"}
        try:
            self.proto.send(cmd)
            response = self.proto.recv(timeout=10)
            if response is None:
                return {"status": "ERROR", "message": "No response from router"}
            return response
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            return {"status": "ERROR", "message": f"Connection error: {e}"}

    def set(self, key: str, value: str, ttl: int | None = None) -> dict:
        """Set a key-value pair, optionally with TTL."""
        cmd = {"cmd": "SET", "key": key, "value": value}
        if ttl is not None:
            cmd["ttl"] = ttl
        return self.send_command(cmd)

    def get(self, key: str) -> dict:
        """Get a value by key."""
        return self.send_command({"cmd": "GET", "key": key})

    def delete(self, key: str) -> dict:
        """Delete a key."""
        return self.send_command({"cmd": "DELETE", "key": key})

    def list_keys(self, prefix: str = "") -> dict:
        """List all keys, optionally filtered by prefix."""
        return self.send_command({"cmd": "LIST", "prefix": prefix})


def print_response(response: dict) -> None:
    """Pretty-print a response from the router."""
    status = response.get("status", "UNKNOWN")
    if status == "OK":
        if "value" in response:
            print(f"Value: {response['value']}")
        elif "keys" in response:
            keys = response["keys"]
            if keys:
                print("Keys:")
                for k in keys:
                    print(f"  {k}")
                print(f"Total: {len(keys)} key(s)")
            else:
                print("(no keys found)")
        else:
            print("OK")
    elif status == "NOT_FOUND":
        print("(not found)")
    elif status == "ERROR":
        print(f"Error: {response.get('message', 'Unknown error')}")
    else:
        print(f"Response: {response}")


def interactive_mode(client: KVClient) -> None:
    """Run an interactive CLI session."""
    print("Distributed KV Store CLI")
    print("Commands: SET <key> <value> [TTL <seconds>], GET <key>, DELETE <key>, LIST [<prefix>], HELP, QUIT")
    print()

    while True:
        try:
            line = input("kv> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].upper() if parts else ""

        if cmd == "QUIT" or cmd == "EXIT":
            break
        elif cmd == "HELP":
            print("Commands:")
            print("  SET <key> <value> [TTL <seconds>]  - Store a key-value pair")
            print("  GET <key>                           - Retrieve a value by key")
            print("  DELETE <key>                        - Remove a key")
            print("  LIST [<prefix>]                     - List keys, optionally filtered")
            print("  HELP                                - Show this help")
            print("  QUIT                                - Exit the client")
        elif cmd == "SET":
            if len(parts) < 3:
                print("Usage: SET <key> <value> [TTL <seconds>]")
                continue
            key = parts[1]
            # Everything after key until TTL or end is the value
            rest = line.split(None, 2)[2] if len(parts) > 2 else ""
            ttl = None
            # Check if rest ends with "TTL <number>"
            upper_rest = rest.upper()
            if " TTL " in upper_rest:
                ttl_idx = upper_rest.rfind(" TTL ")
                value = rest[:ttl_idx]
                ttl_str = rest[ttl_idx + 5:].strip()
                try:
                    ttl = int(ttl_str)
                except ValueError:
                    print(f"Invalid TTL value: {ttl_str}")
                    continue
            else:
                # Check if last part is TTL followed by number
                if len(parts) >= 4 and parts[-2].upper() == "TTL":
                    try:
                        ttl = int(parts[-1])
                        value = " ".join(parts[2:-2])
                    except ValueError:
                        print(f"Invalid TTL value: {parts[-1]}")
                        continue
                else:
                    value = " ".join(parts[2:])

            response = client.set(key, value, ttl)
            print_response(response)
        elif cmd == "GET":
            if len(parts) < 2:
                print("Usage: GET <key>")
                continue
            response = client.get(parts[1])
            print_response(response)
        elif cmd == "DELETE":
            if len(parts) < 2:
                print("Usage: DELETE <key>")
                continue
            response = client.delete(parts[1])
            print_response(response)
        elif cmd == "LIST":
            prefix = parts[1] if len(parts) > 1 else ""
            response = client.list_keys(prefix)
            print_response(response)
        else:
            print(f"Unknown command: {cmd}. Type HELP for available commands.")


def main():
    parser = argparse.ArgumentParser(description="CLI Client for Distributed KV Store")
    parser.add_argument("--host", default="localhost", help="Router host")
    parser.add_argument("--port", type=int, default=7000, help="Router port")
    parser.add_argument("command", nargs="*", help="Command to execute (non-interactive mode)")
    args = parser.parse_args()

    client = KVClient(host=args.host, port=args.port)
    client.connect()

    try:
        if args.command:
            # Non-interactive mode
            line = " ".join(args.command)
            parts = line.split()
            cmd = parts[0].upper() if parts else ""

            if cmd == "SET":
                if len(parts) < 3:
                    print("Usage: SET <key> <value> [TTL <seconds>]")
                else:
                    key = parts[1]
                    rest = line.split(None, 2)[2] if len(parts) > 2 else ""
                    ttl = None
                    upper_rest = rest.upper()
                    if " TTL " in upper_rest:
                        ttl_idx = upper_rest.rfind(" TTL ")
                        value = rest[:ttl_idx]
                        ttl_str = rest[ttl_idx + 5:].strip()
                        try:
                            ttl = int(ttl_str)
                        except ValueError:
                            print(f"Invalid TTL value: {ttl_str}")
                            client.close()
                            sys.exit(1)
                    elif len(parts) >= 4 and parts[-2].upper() == "TTL":
                        try:
                            ttl = int(parts[-1])
                            value = " ".join(parts[2:-2])
                        except ValueError:
                            print(f"Invalid TTL value: {parts[-1]}")
                            client.close()
                            sys.exit(1)
                    else:
                        value = " ".join(parts[2:])
                    response = client.set(key, value, ttl)
                    print_response(response)
            elif cmd == "GET":
                if len(parts) < 2:
                    print("Usage: GET <key>")
                else:
                    response = client.get(parts[1])
                    print_response(response)
            elif cmd == "DELETE":
                if len(parts) < 2:
                    print("Usage: DELETE <key>")
                else:
                    response = client.delete(parts[1])
                    print_response(response)
            elif cmd == "LIST":
                prefix = parts[1] if len(parts) > 1 else ""
                response = client.list_keys(prefix)
                print_response(response)
            else:
                print(f"Unknown command: {cmd}")
        else:
            interactive_mode(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
