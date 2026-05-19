"""HTTP server for previewing the generated site."""

import http.server
import os
import socketserver
from pathlib import Path


def serve_site(output_dir: Path, port: int = 8000) -> None:
    """Start a local HTTP server serving the output directory.

    Args:
        output_dir: Path to the built site directory.
        port: Port number to bind to (default 8000).
    """
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    # Change to the output directory so the server serves from it
    original_dir = os.getcwd()
    os.chdir(output_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        """Custom handler that suppresses log output."""

        def log_message(self, format, *args):
            pass  # Suppress access log

    handler = QuietHandler

    # Use TCPServer
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n🌐 Server running at http://localhost:{port}/")
        print(f"   Serving from: {output_dir.resolve()}")
        print(f"   Press Ctrl+C to stop.\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        finally:
            os.chdir(original_dir)
