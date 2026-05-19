#!/usr/bin/env python3
"""Static Site Generator - A simple static site generator in pure Python.

Usage:
    python ssite.py [--content CONTENT_DIR] [--templates TEMPLATES_DIR]
                    [--static STATIC_DIR] [--output OUTPUT_DIR]
                    [--serve] [--clean] [--port PORT]

Options:
    --content DIR      Content directory (default: content/)
    --templates DIR    Templates directory (default: templates/)
    --static DIR       Static assets directory (default: static/)
    --output DIR       Output directory (default: output/)
    --serve            Start a local HTTP server after building
    --clean            Remove output directory before building
    --port PORT        Port for the HTTP server (default: 8000)
"""

import sys
import os
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='Static Site Generator - Build a static website from Markdown content files.'
    )
    parser.add_argument('--content', default='content', help='Content directory (default: content/)')
    parser.add_argument('--templates', default='templates', help='Templates directory (default: templates/)')
    parser.add_argument('--static', default='static', help='Static assets directory (default: static/)')
    parser.add_argument('--output', default='output', help='Output directory (default: output/)')
    parser.add_argument('--serve', action='store_true', help='Start a local HTTP server after building')
    parser.add_argument('--clean', action='store_true', help='Remove output directory before building')
    parser.add_argument('--port', type=int, default=8000, help='Port for HTTP server (default: 8000)')

    args = parser.parse_args()

    # Resolve paths relative to current working directory
    content_dir = os.path.abspath(args.content)
    templates_dir = os.path.abspath(args.templates)
    static_dir = os.path.abspath(args.static)
    output_dir = os.path.abspath(args.output)

    # Validate directories
    if not os.path.isdir(content_dir):
        print(f"Error: Content directory not found: {content_dir}")
        sys.exit(1)
    if not os.path.isdir(templates_dir):
        print(f"Error: Templates directory not found: {templates_dir}")
        sys.exit(1)

    from generator.builder import SiteBuilder
    from generator.server import serve

    builder = SiteBuilder(content_dir, templates_dir, static_dir, output_dir)

    # Clean if requested
    if args.clean:
        builder.clean()

    # Build
    print(f"\n🔨 Building site...")
    print(f"   Content:   {content_dir}")
    print(f"   Templates: {templates_dir}")
    print(f"   Static:    {static_dir}")
    print(f"   Output:    {output_dir}\n")

    try:
        builder.build()
        print(f"\n✅ Site built successfully in: {output_dir}")
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Serve if requested
    if args.serve:
        serve(output_dir, args.port)


if __name__ == '__main__':
    main()
