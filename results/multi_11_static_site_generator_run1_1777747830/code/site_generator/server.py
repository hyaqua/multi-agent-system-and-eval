"""Simple HTTP server for serving the generated site."""

import os
import http.server
import socketserver


def serve(directory: str, port: int = 8000) -> None:
    """Start an HTTP server to serve files from the given directory.

    Args:
        directory: Path to the output directory to serve.
        port: Port number to listen on.
    """
    os.chdir(directory)

    print(f"\nServing site at http://localhost:{port}/")
    print("Press Ctrl+C to stop.\n")

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            # Quiet logging
            pass

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
