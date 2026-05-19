#!/usr/bin/env python3
"""
Markdown to HTML Converter

Converts a Markdown (.md) file to an HTML (.html) file using only the
Python standard library. Handles common Markdown syntax including
headings, bold, italic, links, lists, code blocks, and paragraphs.
"""

import sys
import os
import re


def _format_spans(text: str) -> str:
    """
    Apply triple-delimiter, bold, and italic formatting to text.
    Does NOT process links — use parse_inline() for the full pipeline.
    """
    # Triple delimiters: ***text*** or ___text___
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', text)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Italic: *text* (remaining single * pairs)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Italic: _text_ (remaining single _ pairs, require word boundaries)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)

    return text


def parse_inline(text: str) -> str:
    """
    Parse inline Markdown within a single line of text:
    - [text](url)  -> <a href="url">text</a>
    - ***text*** or ___text___ -> <strong><em>text</em></strong>
    - **text** or __text__ -> <strong>text</strong>
    - *text* or _text_     -> <em>text</em>

    Uses a placeholder strategy: links are temporarily extracted so
    that *, _ inside URLs are not accidentally formatted.  After the
    rest of the text is processed the links are restored, with their
    *link text* also run through bold / italic formatting.
    """
    # ---- Step 1: extract links into placeholders ----
    links = []  # list of (link_text, url)

    def save_link(m: re.Match) -> str:
        links.append((m.group(1), m.group(2)))
        return f'\x00L{len(links) - 1}\x00'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', save_link, text)

    # ---- Step 2: format spans on the whole text ----
    text = _format_spans(text)

    # ---- Step 3: restore links (formatting link text as well) ----
    def restore_link(m: re.Match) -> str:
        idx = int(m.group(1))
        link_text, url = links[idx]
        # Process bold / italic inside link text
        formatted_text = _format_spans(link_text)
        return f'<a href="{url}">{formatted_text}</a>'

    text = re.sub(r'\x00L(\d+)\x00', restore_link, text)

    return text


def escape_html(text: str) -> str:
    """Escape HTML special characters for code blocks."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def convert_markdown_to_html(md_text: str) -> str:
    """
    Convert raw Markdown text to HTML body content (without
    the surrounding <html>, <head>, <body> tags).
    """
    lines = md_text.split('\n')
    html_parts = []
    n = len(lines)

    # Parser state
    in_code_block = False
    code_block_lines = []

    in_list = None          # 'ul' or 'ol' or None
    list_items = []

    paragraph_lines = []

    def flush_paragraph():
        """Output accumulated paragraph lines as a <p> block."""
        nonlocal paragraph_lines
        if paragraph_lines:
            content = ' '.join(paragraph_lines)
            content = parse_inline(content)
            html_parts.append(f'<p>{content}</p>')
            paragraph_lines = []

    def flush_list():
        """Output accumulated list items as a <ul> or <ol> block."""
        nonlocal in_list, list_items
        if in_list and list_items:
            tag = in_list
            html_parts.append(f'<{tag}>')
            for item in list_items:
                html_parts.append(f'  <li>{parse_inline(item)}</li>')
            html_parts.append(f'</{tag}>')
            list_items = []
            in_list = None

    i = 0
    while i < n:
        line = lines[i]

        # Handle fenced code blocks (```)
        if line.strip().startswith('```'):
            if not in_code_block:
                flush_paragraph()
                flush_list()
                in_code_block = True
                code_block_lines = []
            else:
                # End of code block
                html_parts.append('<pre><code>')
                for cl in code_block_lines:
                    html_parts.append(escape_html(cl))
                html_parts.append('</code></pre>')
                in_code_block = False
                code_block_lines = []
            i += 1
            continue

        # Inside a code block, accumulate lines verbatim
        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # Blank line: separates blocks
        if line.strip() == '':
            flush_paragraph()
            flush_list()
            i += 1
            continue

        # Heading: # through ######
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            html_parts.append(f'<h{level}>{parse_inline(content)}</h{level}>')
            i += 1
            continue

        # Unordered list item: lines starting with - or *
        ul_match = re.match(r'^(\s*)([-*])\s+(.+)$', line)
        if ul_match:
            if in_list != 'ul':
                flush_paragraph()
                flush_list()
                in_list = 'ul'
            else:
                flush_paragraph()  # no-op if empty
            list_items.append(ul_match.group(3))
            i += 1
            continue

        # Ordered list item: lines starting with digits followed by dot
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)
        if ol_match:
            if in_list != 'ol':
                flush_paragraph()
                flush_list()
                in_list = 'ol'
            else:
                flush_paragraph()
            list_items.append(ol_match.group(3))
            i += 1
            continue

        # Anything else is a paragraph line
        flush_list()
        paragraph_lines.append(line.strip())
        i += 1

    # Flush any remaining open blocks
    flush_paragraph()
    flush_list()

    # Handle unclosed code block (treat as closed at EOF)
    if in_code_block and code_block_lines:
        html_parts.append('<pre><code>')
        for cl in code_block_lines:
            html_parts.append(escape_html(cl))
        html_parts.append('</code></pre>')

    return '\n'.join(html_parts)


def build_html_document(body_html: str, title: str = "Converted Markdown") -> str:
    """Wrap the body HTML in a full HTML5 document with an inline stylesheet."""
    css = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                     Oxygen, Ubuntu, Cantarell, sans-serif;
        line-height: 1.7;
        max-width: 820px;
        margin: 0 auto;
        padding: 2em 1.5em;
        color: #333333;
        background-color: #ffffff;
    }
    h1, h2, h3, h4, h5, h6 {
        margin-top: 1.6em;
        margin-bottom: 0.6em;
        font-weight: 600;
        color: #1a1a1a;
    }
    h1 { font-size: 2.2em; border-bottom: 2px solid #eaeaea; padding-bottom: 0.3em; }
    h2 { font-size: 1.7em; border-bottom: 1px solid #eaeaea; padding-bottom: 0.25em; }
    h3 { font-size: 1.35em; }
    h4 { font-size: 1.15em; }
    h5 { font-size: 1.05em; }
    h6 { font-size: 1em; color: #666; }
    p {
        margin: 1em 0;
    }
    a {
        color: #0366d6;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
    strong {
        font-weight: 600;
    }
    em {
        font-style: italic;
    }
    pre {
        background-color: #f6f8fa;
        border: 1px solid #d1d5da;
        border-radius: 6px;
        padding: 1em;
        overflow-x: auto;
        line-height: 1.45;
    }
    code {
        font-family: 'SF Mono', 'Courier New', Courier, monospace;
        font-size: 0.92em;
    }
    pre code {
        background: none;
        padding: 0;
        font-size: 0.9em;
    }
    ul, ol {
        padding-left: 2.2em;
        margin: 1em 0;
    }
    li {
        margin: 0.35em 0;
    }
    hr {
        border: 0;
        border-top: 1px solid #ddd;
        margin: 2em 0;
    }
    blockquote {
        border-left: 4px solid #ddd;
        margin: 1em 0;
        padding-left: 1em;
        color: #666;
    }
    @media (prefers-color-scheme: dark) {
        body {
            color: #c9d1d9;
            background-color: #0d1117;
        }
        h1, h2, h3, h4, h5, h6 { color: #f0f6fc; }
        a { color: #58a6ff; }
        pre {
            background-color: #161b22;
            border-color: #30363d;
        }
        h1 { border-bottom-color: #21262d; }
        h2 { border-bottom-color: #21262d; }
        hr { border-top-color: #21262d; }
        blockquote {
            border-left-color: #30363d;
            color: #8b949e;
        }
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(title)}</title>
    <style>
{css.strip()}
    </style>
</head>
<body>
{body_html}
</body>
</html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python markdown_converter.py <input.md>")
        print()
        print("Converts a Markdown file to an HTML file with the same base name.")
        print("Example: python markdown_converter.py README.md  →  README.html")
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' does not exist.")
        sys.exit(1)

    if not os.path.isfile(input_path):
        print(f"Error: '{input_path}' is not a file.")
        sys.exit(1)

    # Read the Markdown source
    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Convert Markdown → HTML body
    body_html = convert_markdown_to_html(md_text)

    # Derive a title from the filename
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    title = base_name.replace('_', ' ').replace('-', ' ').title()

    # Build the full HTML document
    full_html = build_html_document(body_html, title=title)

    # Determine the output path (same name, .html extension)
    output_path = os.path.splitext(input_path)[0] + '.html'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"✓ Converted '{input_path}' → '{output_path}'")


if __name__ == '__main__':
    main()
