"""CLI entry point: argument parsing and orchestration."""

import argparse
import sys
from pathlib import Path

from ssg.builder import build_site
from ssg.server import serve_site


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static Site Generator – convert Markdown to HTML site."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove output directory before building.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local HTTP server after building.",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Working directory containing content/, templates/, static/, and output/. "
        "Defaults to the current working directory.",
    )

    args = parser.parse_args()

    work_dir = Path(args.dir) if args.dir else Path.cwd()

    try:
        build_site(work_dir, clean=args.clean)
    except Exception as e:
        print(f"Build error: {e}", file=sys.stderr)
        return 1

    if args.serve:
        output_dir = work_dir / "output"
        serve_site(output_dir)

    return 0
