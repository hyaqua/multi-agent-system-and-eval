#!/usr/bin/env python3
"""REST API server entry point."""

import argparse
from http.server import HTTPServer
from socketserver import ThreadingMixIn

from api_handler import APIHandler
from data_store import DataStore
import logger as logger_mod


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a separate thread."""
    daemon_threads = True  # allow clean shutdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple REST API server")
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--data-file", type=str, default="items.json",
        help="JSON file for persistent storage (default: items.json)",
    )
    args = parser.parse_args()

    # Setup logging
    log = logger_mod.setup_logger()

    # Initialise data store (loads existing data or creates empty)
    store = DataStore(args.data_file)
    APIHandler.store = store

    server = ThreadedHTTPServer(("", args.port), APIHandler)
    log.info("Starting REST API server on port %d", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down server.")
        server.shutdown()


if __name__ == "__main__":
    main()
