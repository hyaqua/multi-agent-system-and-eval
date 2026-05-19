"""Markdown to HTML Converter - CLI Entry Point."""

import argparse
import sys
from pathlib import Path

from md_converter import markdown_to_html, _wrap_html


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Markdown file to an HTML file."
    )
    parser.add_argument(
        "input_file",
        help="Path to the input Markdown file.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)

    if not input_path.is_file():
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        sys.exit(1)

    # Read the markdown content
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
    except Exception as e:
        print(f"Error: Could not read file '{args.input_file}': {e}", file=sys.stderr)
        sys.exit(1)

    # Convert markdown to HTML body
    html_body = markdown_to_html(markdown_text)

    # Derive title from filename stem
    title = input_path.stem

    # Wrap in full HTML document
    full_html = _wrap_html(html_body, title)

    # Write output
    output_path = input_path.with_suffix(".html")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_html)
    except Exception as e:
        print(f"Error: Could not write output file '{output_path}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Converted: {input_path} -> {output_path}")


if __name__ == "__main__":
    main()
