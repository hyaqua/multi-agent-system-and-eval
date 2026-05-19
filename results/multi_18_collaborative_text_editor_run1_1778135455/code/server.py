#!/usr/bin/env python3
"""
Collaborative Real-Time Text Editor – Server

Usage:
    python server.py [--port PORT] [--config CONFIG_PATH]

The server accepts client connections, manages rooms and documents,
and coordinates Operational Transformation.
"""

import argparse
import logging
import os
import socket
import sys
import threading
from datetime import datetime

import config as cfg
from server_connection import ClientHandler


def setup_logging(port: int):
    """Configure logging to file and console with safe fallback.

    Tries writable locations from safest to least safe. If all file
    paths fail, logs exclusively to stderr so the server always starts.
    """
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Candidates ordered from safest to least safe
    candidates = [
        os.path.join("/tmp", f"collab_edit_server_{port}_{date_str}.log"),
        os.path.join(os.path.expanduser("~"), "collab_editor_logs",
                     f"server_{port}_{date_str}.log"),
    ]

    logger = logging.getLogger("server")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = None
    for candidate in candidates:
        try:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            fh = logging.FileHandler(candidate, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            logger.addHandler(fh)
            file_handler = fh
            print(f"Logging to {candidate}", file=sys.stderr)
            break
        except (PermissionError, OSError) as exc:
            print(f"Could not log to {candidate}: {exc}", file=sys.stderr)

    # Console handler (stderr so it survives restricted environments)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    logger.addHandler(ch)

    # If no file handler was created, warn but continue
    if file_handler is None:
        print("All file paths failed; logging to stderr only.", file=sys.stderr)

    # Also set up child loggers
    for name in ("server.connection", "server.room"):
        child = logging.getLogger(name)
        child.setLevel(logging.DEBUG)
        if file_handler is not None:
            child.addHandler(file_handler)

    return logger


def main():
    parser = argparse.ArgumentParser(
        description="Collaborative Text Editor Server"
    )
    parser.add_argument(
        "--port", type=int, default=9090,
        help="TCP port to listen on (default: 9090)"
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to JSON config file (default: config.json)"
    )
    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.port)

    # Load configuration
    server_config = cfg.load_config(args.config)
    logger.info("Loaded configuration with %d rooms", len(server_config.get("rooms", {})))

    # Room registry
    rooms: dict = {}  # room_name -> Room

    # Create server socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind(("0.0.0.0", args.port))
        server_sock.listen(20)
        logger.info("Server listening on port %d", args.port)
    except OSError as e:
        logger.error("Failed to bind to port %d: %s", args.port, e)
        sys.exit(1)

    try:
        while True:
            client_sock, addr = server_sock.accept()
            logger.info("New connection from %s:%d", *addr)
            handler = ClientHandler(client_sock, addr, rooms, server_config)
            handler.start()
    except KeyboardInterrupt:
        logger.info("Server shutting down (KeyboardInterrupt)")
    finally:
        # Save all rooms
        for room in rooms.values():
            room.save_to_disk()
        server_sock.close()
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
