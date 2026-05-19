#!/usr/bin/env python3
"""Markdown to HTML Converter.

Converts a Markdown file to a valid HTML file with embedded CSS.
Uses only the Python standard library.
"""

import argparse
import html
import re
import sys
from pathlib import Path


def convert_inline(text: str) -> str:
    """Convert inline Markdown formatting to HTML.

    Applies bold, italic, and link conversions in order to avoid conflicts.
    Handles combined bold+italic (***text***) before individual patterns.
    """
    # Combined bold+italic: ***text*** and ___text___
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', text)

    # Bold: **text** and __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Italic: *text* and _text_  (but not inside <strong> tags added above)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)

    # Inline links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)

    return text


def parse_markdown(text: str) -> str:
    """Parse Markdown text and return HTML body content.

    Handles fenced code blocks, headings, unordered lists, ordered lists,
    and paragraphs. Applies inline formatting where appropriate.
    """
    lines = text.split('\n')
    html_blocks: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Blank line: skip
        if line.strip() == '':
            i += 1
            continue

        # Fenced code block: ```
        if line.startswith('```'):
            # Collect code lines until closing ```
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            # Skip closing ```
            i += 1
            # Escape and wrap
            escaped = html.escape('\n'.join(code_lines))
            html_blocks.append(f'<pre><code>{escaped}</code></pre>')
            continue

        # Heading: # to ######
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = convert_inline(heading_match.group(2))
            html_blocks.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Unordered list: line starting with '- ' or '* '
        ul_match = re.match(r'^[\-\*]\s+(.*)', line)
        if ul_match:
            list_items: list[str] = []
            while i < n and re.match(r'^[\-\*]\s+(.*)', lines[i]):
                item_match = re.match(r'^[\-\*]\s+(.*)', lines[i])
                if item_match:
                    item_content = convert_inline(item_match.group(1))
                    list_items.append(f'<li>{item_content}</li>')
                i += 1
            html_blocks.append('<ul>' + ''.join(list_items) + '</ul>')
            continue

        # Ordered list: line starting with '1. ' etc.
        ol_match = re.match(r'^\d+\.\s+(.*)', line)
        if ol_match:
            list_items: list[str] = []
            while i < n and re.match(r'^\d+\.\s+(.*)', lines[i]):
                item_match = re.match(r'^\d+\.\s+(.*)', lines[i])
                if item_match:
                    item_content = convert_inline(item_match.group(1))
                    list_items.append(f'<li>{item_content}</li>')
                i += 1
            html_blocks.append('<ol>' + ''.join(list_items) + '</ol>')
            continue

        # Paragraph: accumulate consecutive non-blank, non-special lines
        para_lines: list[str] = [line]
        i += 1
        while i < n and lines[i].strip() != '':
            # Stop accumulating if next line is a special block
            if (lines[i].startswith('```')
                    or re.match(r'^#{1,6}\s+', lines[i])
                    or re.match(r'^[\-\*]\s+', lines[i])
                    or re.match(r'^\d+\.\s+', lines[i])):
                break
            para_lines.append(lines[i])
            i += 1
        content = convert_inline(' '.join(para_lines))
        html_blocks.append(f'<p>{content}</p>')

    return '\n'.join(html_blocks)


def build_html(body: str) -> str:
    """Wrap body content in a full HTML document with CSS styling."""
    css = """
    body {
        max-width: 800px;
        margin: 2em auto;
        font-family: system-ui, -apple-system, sans-serif;
        line-height: 1.6;
        padding: 0 1em;
        color: #333;
        background: #fff;
    }
    h1, h2, h3, h4, h5, h6 {
        margin-top: 1.5em;
        margin-bottom: 0.5em;
        line-height: 1.3;
        color: #1a1a1a;
    }
    h1 { border-bottom: 2px solid #eee; padding-bottom: 0.3em; }
    h2 { border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
    pre {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 1em;
        overflow-x: auto;
    }
    code {
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.9em;
    }
    pre code {
        background: none;
        padding: 0;
    }
    a {
        color: #0366d6;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
    ul, ol {
        padding-left: 2em;
    }
    li {
        margin: 0.25em 0;
    }
    p {
        margin: 0.75em 0;
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Converted Markdown</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def main() -> None:
    """Entry point: parse arguments, convert, and write output."""
    parser = argparse.ArgumentParser(
        description='Convert a Markdown file to HTML with embedded CSS.'
    )
    parser.add_argument(
        'input',
        metavar='INPUT_FILE',
        help='Path to the Markdown (.md) file to convert',
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f'Error: file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    # Read input file
    raw_text = input_path.read_text(encoding='utf-8')

    # Determine output path: same name but .html extension
    output_path = input_path.with_suffix('.html')

    # Convert
    body = parse_markdown(raw_text)
    html_output = build_html(body)

    # Write output
    output_path.write_text(html_output, encoding='utf-8')
    print(f'Converted: {input_path} -> {output_path}')


if __name__ == '__main__':
    main()
