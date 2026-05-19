"""CLI client for the distributed key-value store.

Usage: python client.py [host] [port]
"""

import socket
import sys

from common import BufferedSocket


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)

    try:
        sock.connect((host, port))
    except Exception as e:
        print(f"Could not connect to {host}:{port} – {e}")
        sys.exit(1)

    bsock = BufferedSocket(sock)

    print("Distributed KV Store  |  Commands:")
    print("  SET <key> <value> [<ttl_secs>]")
    print("  GET <key>")
    print("  DELETE <key>")
    print("  LIST [<prefix>]")
    print("  QUIT")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        bsock.send_line(line)

        cmd = line.split()[0].upper() if line else ""
        if cmd == "QUIT":
            print("Bye.")
            break

        # Read first line of response
        try:
            first = bsock.read_line()
        except Exception as e:
            print(f"Error reading response: {e}")
            break

        if first.startswith("LIST_BEGIN"):
            count = int(first.split(" ")[1])
            keys = []
            for _ in range(count):
                try:
                    keys.append(bsock.read_line())
                except Exception:
                    break
            try:
                bsock.read_line()  # LIST_END
            except Exception:
                pass
            print(f"{count} key(s):")
            for k in keys:
                print(f"  {k}")
        else:
            print(first)

    sock.close()


if __name__ == "__main__":
    main()
