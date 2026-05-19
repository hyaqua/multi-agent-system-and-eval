"""Simple HTTP server for previewing the generated site."""

import http.server
import socketserver
import os


def serve(directory: str, port: int = 8000) -> None:
    """Start a local HTTP server to preview the site.

    Serves files from the given directory.
    Automatically serves index.html for directory paths (clean URLs).
    """
    os.chdir(directory)

    class CleanURLHandler(http.server.SimpleHTTPRequestHandler):
        """Handler that supports clean URLs by serving index.html for directories."""

        def do_GET(self):
            # If the path doesn't have an extension and doesn't end with /,
            # try to serve it as a directory with index.html
            path = self.path

            # Normalize: strip query string and fragment
            request_path = path.split('?')[0].split('#')[0]

            if not os.path.splitext(request_path)[1]:
                # No file extension - treat as directory
                if not request_path.endswith('/'):
                    # Redirect to trailing slash for clean URLs
                    self.send_response(301)
                    self.send_header('Location', request_path + '/')
                    self.end_headers()
                    return

                # Try to serve index.html
                index_path = request_path + 'index.html'
                if os.path.isfile('.' + index_path):
                    self.path = index_path

            super().do_GET()

        def log_message(self, format, *args):
            print(f"[server] {args[0]}")

    handler = CleanURLHandler

    print(f"\n🌐 Serving site at http://localhost:{port}/")
    print(f"   Press Ctrl+C to stop.\n")

    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
