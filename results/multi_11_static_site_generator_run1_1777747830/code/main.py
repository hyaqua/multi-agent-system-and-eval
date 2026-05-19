#!/usr/bin/env python3
"""Static Site Generator - CLI entry point.

Generates a static website from Markdown content files, HTML templates,
and static assets.

Usage:
    python main.py                  # Build site into output/
    python main.py --clean          # Clean output/ then build
    python main.py --serve          # Build then serve on localhost:8000
    python main.py --clean --serve  # Clean, build, and serve
"""

import argparse
import os
import sys

from site_generator.generator import build_site
from site_generator.server import serve


def main():
    parser = argparse.ArgumentParser(
        description="Static Site Generator - Build a website from Markdown files."
    )
    parser.add_argument(
        "--content",
        default="content",
        help="Path to content directory (default: content/)",
    )
    parser.add_argument(
        "--templates",
        default="templates",
        help="Path to templates directory (default: templates/)",
    )
    parser.add_argument(
        "--static",
        default="static",
        help="Path to static assets directory (default: static/)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to output directory (default: output/ in current directory)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove output directory before building",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start HTTP server after building",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP server (default: 8000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress information",
    )

    args = parser.parse_args()

    # Determine paths
    # If using sample_site, prepend sample_site/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sample_site_dir = os.path.join(script_dir, "sample_site")

    # Resolve content, templates, static dirs
    content_dir = args.content
    templates_dir = args.templates
    static_dir = args.static
    # Default output to ./output in the current working directory
    output_dir = args.output if args.output else os.path.join(os.getcwd(), 'output')

    # If default paths don't exist but sample_site has them, use sample_site
    if not os.path.isdir(content_dir) and os.path.isdir(
        os.path.join(sample_site_dir, "content")
    ):
        content_dir = os.path.join(sample_site_dir, "content")
        templates_dir = os.path.join(sample_site_dir, "templates")
        static_dir = os.path.join(sample_site_dir, "static")

    # Validate required directories
    if not os.path.isdir(content_dir):
        print(f"Error: Content directory not found: {content_dir}")
        print("Create a 'content/' directory with .md files, or use sample_site/")
        sys.exit(1)

    if not os.path.isdir(templates_dir):
        print(f"Error: Templates directory not found: {templates_dir}")
        print("Create a 'templates/' directory with .html files, or use sample_site/")
        sys.exit(1)

    # Build the site
    print("Building site...")
    build_site(
        content_dir=content_dir,
        templates_dir=templates_dir,
        static_dir=static_dir,
        output_dir=output_dir,
        verbose=args.verbose,
        clean=args.clean,
    )
    print("Done.")

    # Serve if requested
    if args.serve:
        serve(output_dir, port=args.port)


if __name__ == "__main__":
    main()
