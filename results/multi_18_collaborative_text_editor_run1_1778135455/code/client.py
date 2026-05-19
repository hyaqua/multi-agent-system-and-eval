#!/usr/bin/env python3
"""
Collaborative Real-Time Text Editor – Client

Usage:
    python client.py --host HOST --port PORT --user USER --room ROOM [--password PASSWORD]
"""

import argparse
import curses
import logging
import sys
import time

from client_connection import NetworkClient
from client_edit import Document
from client_ui import EditorUI
import protocol

logger = logging.getLogger("client")


def setup_logging():
    """Configure client logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename="client.log",
        filemode="w",
    )
    # Also log to stderr
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    logging.getLogger().addHandler(console)


def connect_and_auth(net: NetworkClient, user: str, room: str, password: str,
                     timeout: float = 5.0) -> tuple[Document | None, int]:
    """Connect to server and authenticate. Returns (Document, user_color) or (None, 0)."""
    if not net.connect(timeout):
        print(f"Failed to connect to {net.host}:{net.port}", file=sys.stderr)
        return None, 0

    # Send connect message
    connect_msg = protocol.make_connect(user, room, password)
    net.send(connect_msg)

    # Wait for ack
    start = time.time()
    while time.time() - start < timeout:
        messages = net.poll()
        for msg in messages:
            if msg.get("type") == protocol.TYPE_ACK:
                if msg.get("status") == "ok":
                    doc_text = msg.get("document", "")
                    version = msg.get("version", 0)
                    doc = Document(doc_text, version)
                    user_color = msg.get("user_color", 1)
                    logger.info("Connected to room '%s', doc=%d chars, v=%d",
                                room, len(doc_text), version)
                    return doc, user_color
                else:
                    logger.error("Auth failed")
                    return None, 0
            elif msg.get("type") == protocol.TYPE_ERROR:
                logger.error("Server error: %s", msg.get("message"))
                return None, 0
        time.sleep(0.1)

    logger.error("Timeout waiting for server ack")
    return None, 0


def main_ui(stdscr, net: NetworkClient, user: str, room: str, doc: Document, user_color: int):
    """Main curses UI loop."""
    ui = EditorUI(stdscr, doc, net, user, room)
    ui.user_color = user_color
    ui.connected = True
    ui.run()


def main():
    parser = argparse.ArgumentParser(
        description="Collaborative Text Editor Client"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9090,
                        help="Server port (default: 9090)")
    parser.add_argument("--user", type=str, required=True,
                        help="Username")
    parser.add_argument("--room", type=str, required=True,
                        help="Room name")
    parser.add_argument("--password", type=str, default="",
                        help="Room password")
    args = parser.parse_args()

    setup_logging()

    # Create network client
    net = NetworkClient(args.host, args.port)

    # Connect and authenticate
    doc, user_color = connect_and_auth(net, args.user, args.room, args.password)
    if doc is None:
        print("Failed to connect to server.", file=sys.stderr)
        sys.exit(1)

    # Start curses UI
    try:
        curses.wrapper(lambda stdscr: main_ui(stdscr, net, args.user, args.room, doc, user_color))
    except KeyboardInterrupt:
        pass
    finally:
        net.disconnect()
        logger.info("Client shut down")


if __name__ == "__main__":
    main()
