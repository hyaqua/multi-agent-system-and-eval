"""
CLI client for the distributed key-value store.

Connects to the router's client port and sends text commands.
Can be used interactively or in one-shot mode.

Usage:
    # Interactive mode
    python client.py --host localhost --port 5555

    # One-shot mode
    python client.py -c "SET foo bar 3600"
    python client.py -c "GET foo"
    python client.py -c "LIST"
    python client.py -c "LIST prefix"
    python client.py -c "DELETE foo"
"""

import argparse
import socket
import sys


class KVClient:
    """Simple CLI client for the distributed KV store."""

    def __init__(self, host: str = "localhost", port: int = 5555):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        """Connect to the router."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))

    def close(self) -> None:
        """Close the connection."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def send_command(self, command: str) -> str:
        """
        Send a command and return the response.
        The command should NOT include a trailing newline (it's added here).
        """
        if not self._sock:
            raise ConnectionError("Not connected")
        msg = command.strip() + "\n"
        self._sock.sendall(msg.encode())

        # Read response
        buffer = b""
        while True:
            data = self._sock.recv(4096)
            if not data:
                break
            buffer += data
            # Check if we have a complete response
            text = buffer.decode()
            if text.endswith("END\n"):
                break
            # Single-line responses: OK, NOTFOUND, DELETED, ERROR, VALUE
            if "\n" in text and not text.startswith("END"):
                # For single-line responses, one newline is enough
                lines = text.strip().split("\n")
                # If it doesn't look like a LIST response (multi-line)
                if len(lines) == 1 and "END" not in text:
                    break
                # Also break if we got END
        return buffer.decode()

    def interactive(self) -> None:
        """Run interactive mode."""
        print(f"Connected to {self.host}:{self.port}")
        print("Commands: SET key value [TTL] | GET key | DELETE key | LIST [prefix]")
        print("Type 'quit' or Ctrl+C to exit.\n")

        try:
            while True:
                try:
                    line = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not line:
                    continue
                if line.lower() in ("quit", "exit", "q"):
                    break

                try:
                    response = self.send_command(line)
                    # Print response without the trailing newline
                    sys.stdout.write(response)
                    sys.stdout.flush()
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    print(f"Connection error: {e}")
                    break
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="KV Store CLI Client")
    parser.add_argument("--host", default="localhost", help="Router host")
    parser.add_argument("--port", type=int, default=5555, help="Router client port")
    parser.add_argument("-c", "--command", default=None,
                        help="Execute a single command and exit")
    args = parser.parse_args()

    client = KVClient(host=args.host, port=args.port)

    if args.command:
        # One-shot mode
        try:
            client.connect()
            response = client.send_command(args.command)
            sys.stdout.write(response)
            sys.stdout.flush()
        except (ConnectionRefusedError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            client.close()
    else:
        # Interactive mode
        try:
            client.connect()
            client.interactive()
        except (ConnectionRefusedError, OSError) as e:
            print(f"Error: Could not connect to {args.host}:{args.port}: {e}",
                  file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            pass
        finally:
            client.close()


if __name__ == "__main__":
    main()
