"""
client.py – Interactive CLI client for the distributed key-value store.

Connects to the router via TCP and supports commands:
  SET key value [TTL]
  GET key
  DELETE key
  LIST [prefix]
  QUIT
"""

import socket
import sys
import argparse

import protocol


class Client:
    """CLI client for interacting with the KV store via the router."""

    def __init__(self, router_host: str, router_port: int):
        self.router_host = router_host
        self.router_port = router_port

    def send_command(self, line: str) -> str:
        """Send a single command line to the router and return the response."""
        try:
            with socket.create_connection((self.router_host, self.router_port), timeout=10) as sock:
                sock.settimeout(10)
                sock.sendall(line.strip().encode(protocol.ENCODING) + protocol.LINE_TERMINATOR)
                response_data = sock.recv(65536)
                return protocol.decode_message(response_data)
        except ConnectionRefusedError:
            return f"{protocol.ERROR} Could not connect to router at {self.router_host}:{self.router_port}"
        except socket.timeout:
            return f"{protocol.ERROR} Connection timed out"
        except Exception as e:
            return f"{protocol.ERROR} {e}"

    def run(self):
        """Interactive REPL loop."""
        print(f"Connected to router at {self.router_host}:{self.router_port}")
        print("Commands: SET key value [TTL] | GET key | DELETE key | LIST [prefix] | QUIT")
        print()

        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            command, args = protocol.parse_command(line)
            if command == protocol.CMD_QUIT:
                print("Bye.")
                break

            response = self.send_command(line)
            self._print_response(response)

    def _print_response(self, response: str):
        """Pretty-print the router's response."""
        lines = response.split("\n")
        if not lines:
            return

        header = lines[0].strip()

        if header == protocol.OK:
            print("OK")
        elif header == protocol.NOT_FOUND:
            print("(not found)")
        elif header == protocol.VALUE:
            if len(lines) >= 2:
                print(lines[1])
            else:
                parts = response.split(maxsplit=1)
                if len(parts) >= 2:
                    print(parts[1])
                else:
                    print("(empty value)")
        elif header == protocol.LIST:
            if len(lines) > 1:
                for key in lines[1:]:
                    if key.strip():
                        print(key.strip())
            else:
                print("(empty)")
        elif header == protocol.ERROR:
            error_msg = lines[0][len(protocol.ERROR):].strip()
            if error_msg:
                print(f"ERROR: {error_msg}")
            elif len(lines) > 1:
                print(f"ERROR: {lines[1]}")
            else:
                print("ERROR")
        else:
            print(response)


def main():
    parser = argparse.ArgumentParser(description="KV Store Client CLI")
    parser.add_argument("--host", default="127.0.0.1", help="Router host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7000, help="Router port (default: 7000)")
    args = parser.parse_args()

    client = Client(args.host, args.port)
    client.run()


if __name__ == "__main__":
    main()
