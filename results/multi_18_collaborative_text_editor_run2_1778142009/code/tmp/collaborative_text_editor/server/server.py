"""
Collaborative Text Editor - Server Entry Point

Usage: python -m server.server --port PORT [--config config.json]
"""

import argparse
import json
import logging
import os
import socket
import sys
import threading
from datetime import datetime

from collaborative_text_editor.server.room import Room
from collaborative_text_editor.server.client_handler import ClientHandler


class Server:
    """Main server that accepts connections and manages rooms."""

    def __init__(self, port, config_path=None):
        self.port = port
        self.config_path = config_path
        self.rooms = {}  # room_name -> Room
        self.rooms_lock = threading.Lock()
        self.running = True

        # Setup logging
        log_dir = os.environ.get("LOG_DIR", "/tmp")
        log_filename = os.path.join(
            log_dir,
            f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger("server")

        # Load config
        self.config = {}
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                self.logger.info("Loaded config from %s", config_path)
            except Exception as e:
                self.logger.error("Failed to load config: %s", e)

    def get_or_create_room(self, name):
        """Get or create a room by name."""
        with self.rooms_lock:
            if name not in self.rooms:
                room_config = self.config.get("rooms", {}).get(name, {})
                password = room_config.get("password")
                persist_file = room_config.get("persist_file", f"{name}.txt")
                self.rooms[name] = Room(
                    name=name,
                    password=password,
                    persist_file=persist_file,
                )
                self.logger.info("Created room '%s' (persist: %s, has_password: %s)",
                                 name, persist_file, bool(password))
            return self.rooms[name]

    def start(self):
        """Start listening for connections."""
        self.logger.info("Starting server on port %d", self.port)

        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", self.port))
            listener.listen(50)
            listener.settimeout(1.0)  # Allow checking self.running periodically
        except Exception as e:
            self.logger.error("Failed to bind to port %d: %s", self.port, e)
            return

        self.logger.info("Server listening on 0.0.0.0:%d", self.port)

        try:
            while self.running:
                try:
                    sock, addr = listener.accept()
                    sock.settimeout(30.0)  # 30 second timeout
                    self.logger.info("New connection from %s:%d", *addr)
                    handler = ClientHandler(sock, addr, self)
                    t = threading.Thread(target=handler.run, daemon=True)
                    t.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error("Accept error: %s", e)
        finally:
            listener.close()
            self.logger.info("Server stopped")

    def stop(self):
        """Stop the server."""
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Server")
    parser.add_argument("--port", type=int, required=True,
                        help="TCP port to listen on")
    parser.add_argument("--config", type=str, default="config.json",
                        help="Path to JSON config file (default: config.json)")
    args = parser.parse_args()

    server = Server(port=args.port, config_path=args.config)

    try:
        server.start()
    except KeyboardInterrupt:
        server.logger.info("Server shutting down...")
        server.stop()


if __name__ == "__main__":
    main()
