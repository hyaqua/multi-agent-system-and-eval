"""Command-line interface for the static site generator."""

import argparse
import http.server
import os
import socketserver
import sys

from . import builder


def main():
    """Parse arguments and run the site builder."""
    parser = argparse.ArgumentParser(
        description='Static Site Generator - Build a static site from Markdown.'
    )
    parser.add_argument(
        '--content-dir', '-c',
        default='content',
        help='Path to content directory (default: content/)'
    )
    parser.add_argument(
        '--templates-dir', '-t',
        default='templates',
        help='Path to templates directory (default: templates/)'
    )
    parser.add_argument(
        '--static-dir', '-s',
        default='static',
        help='Path to static assets directory (default: static/)'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='output',
        help='Path to output directory (default: output/)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Remove output directory before building'
    )
    parser.add_argument(
        '--serve',
        action='store_true',
        help='Start a local HTTP server on port 8000 after building'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port for the HTTP server (default: 8000)'
    )

    args = parser.parse_args()

    # Build the site
    try:
        builder.build(
            content_dir=args.content_dir,
            templates_dir=args.templates_dir,
            static_dir=args.static_dir,
            output_dir=args.output_dir,
            clean=args.clean,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error building site: {e}", file=sys.stderr)
        sys.exit(1)

    # Start HTTP server if --serve
    if args.serve:
        output_dir = os.path.abspath(args.output_dir)
        os.chdir(output_dir)

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress log messages for cleaner output
                pass

        handler = QuietHandler
        port = args.port

        print(f"\nServing site at http://localhost:{port}/")
        print("Press Ctrl+C to stop.\n")

        with socketserver.TCPServer(("", port), handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
                httpd.shutdown()


if __name__ == '__main__':
    main()
