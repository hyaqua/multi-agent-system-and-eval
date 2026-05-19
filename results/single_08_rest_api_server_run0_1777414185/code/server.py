#!/usr/bin/env python3
"""
REST API server – entry point.

Usage::

    python server.py [--port 8080] [--host localhost]
                     [--data-file items.json] [--token secret-token]
"""
import argparse
import logging
import sys
from http.server import HTTPServer
from socketserver import ThreadingMixIn

from handlers import APIHandler


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in its own thread."""
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser(description="JSON-file-backed REST API server")
    parser.add_argument(
        "--port", type=int, default=8080, help="Listening port (default: 8080)"
    )
    parser.add_argument(
        "--host", type=str, default="localhost", help="Bind address (default: localhost)"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="items.json",
        help="Path to the JSON data file (default: items.json)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default="secret-token",
        help="Bearer token required for all requests (default: secret-token)",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Wire up the handler
    APIHandler.data_file = args.data_file
    APIHandler.auth_token = args.token
    APIHandler.init_store()

    server = ThreadingHTTPServer((args.host, args.port), APIHandler)
    print(f"✓ Server listening on http://{args.host}:{args.port}")
    print(f"  Data file : {args.data_file}")
    print(f"  Auth token: {args.token}")
    print("  Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down …")
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
