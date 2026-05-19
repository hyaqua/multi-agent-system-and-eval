#!/usr/bin/env python3
"""Markdown to HTML Converter.

Converts a Markdown file to HTML with embedded CSS styling.
Usage: python markdown_converter.py <input_file.md>
Output: <input_file>.html
"""

import re
import sys
from pathlib import Path


def html_template(title: str, content: str) -> str:
    """Wrap the rendered content in a full HTML document with CSS."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      max-width: 800px;
      margin: 2rem auto;
      line-height: 1.6;
      color: #333;
    }}
    pre {{
      background: #f4f4f4;
      padding: 1rem;
      border-radius: 4px;
      overflow-x: auto;
    }}
    code {{
      font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
      font-size: 0.9em;
    }}
    pre code {{
      font-size: 0.85em;
    }}
    img {{
      max-width: 100%;
    }}
    a {{
      color: #1a0dab;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    h1, h2, h3, h4, h5, h6 {{
      margin-top: 1.5em;
      margin-bottom: 0.5em;
      font-weight: 600;
      color: #1a1a1a;
    }}
    h1 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
    h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.25em; }}
    h3 {{ font-size: 1.25em; }}
    p {{
      margin: 0.8em 0;
    }}
    ul, ol {{
      margin: 0.5em 0;
      padding-left: 2em;
    }}
    li {{
      margin: 0.25em 0;
    }}
    blockquote {{
      border-left: 4px solid #ddd;
      margin: 0.8em 0;
      padding-left: 1em;
      color: #555;
    }}
  </style>
</head>
<body>
{content}
</body>
</html>"""


def escape_html(text: str) -> str:
    """Escape HTML entities for code blocks."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def parse_inline(text: str) -> str:
    """Apply inline transformations: bold, italic, links.

    Uses placeholder tokens to avoid interference between patterns.
    Bold is processed first (wrapping bold content), then italic within the result,
    then links.
    """
    # Process bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Process italic: *text* or _text_
    # To avoid matching inside HTML tags, we match text that does NOT contain '<' or '>'
    text = re.sub(r'\*([^<>\*]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'(?<![a-zA-Z0-9>])_([^<>_]+?)_(?![a-zA-Z0-9<])', r'<em>\1</em>', text)

    # Process links [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)

    return text


def parse_blocks(lines: list[str]) -> list[dict]:
    """Parse raw lines into a list of block-level element dicts.

    Each dict has:
      - "type": "heading" | "code" | "list" | "paragraph"
      - Additional keys depending on type.
    """
    blocks: list[dict] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Blank line → skip
        if line.strip() == "":
            i += 1
            continue

        # Fenced code block
        if line.strip().startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < n:
                if lines[i].strip() == "```":
                    i += 1  # consume closing fence
                    break
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                "type": "code",
                "content": "\n".join(code_lines),
            })
            continue

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            blocks.append({
                "type": "heading",
                "level": level,
                "content": content,
            })
            i += 1
            continue

        # Unordered list: group consecutive lines starting with - or *
        if re.match(r'^[\-\*]\s+', line):
            items: list[str] = []
            while i < n and re.match(r'^[\-\*]\s+', lines[i]):
                item_content = re.sub(r'^[\-\*]\s+', '', lines[i]).strip()
                items.append(item_content)
                i += 1
            blocks.append({
                "type": "list",
                "ordered": False,
                "items": items,
            })
            continue

        # Ordered list: group consecutive lines starting with number. )
        if re.match(r'^\d+\.\s+', line):
            items = []
            while i < n and re.match(r'^\d+\.\s+', lines[i]):
                item_content = re.sub(r'^\d+\.\s+', '', lines[i]).strip()
                items.append(item_content)
                i += 1
            blocks.append({
                "type": "list",
                "ordered": True,
                "items": items,
            })
            continue

        # Paragraph: collect until blank line or another block-level element
        para_lines: list[str] = []
        while i < n and lines[i].strip() != "":
            # Stop if we hit a heading, list, or code fence
            stripped = lines[i].strip()
            if re.match(r'^(#{1,6})\s+', stripped):
                break
            if re.match(r'^[\-\*]\s+', stripped):
                break
            if re.match(r'^\d+\.\s+', stripped):
                break
            if stripped == "```":
                break
            para_lines.append(stripped)
            i += 1
        if para_lines:
            blocks.append({
                "type": "paragraph",
                "content": " ".join(para_lines),
            })

    return blocks


def render_blocks(blocks: list[dict]) -> str:
    """Convert a list of block dicts into HTML strings."""
    html_parts: list[str] = []

    for block in blocks:
        bt = block["type"]

        if bt == "heading":
            level = block["level"]
            content = parse_inline(block["content"])
            html_parts.append(f"<h{level}>{content}</h{level}>")

        elif bt == "code":
            escaped = escape_html(block["content"])
            html_parts.append(f"<pre><code>{escaped}</code></pre>")

        elif bt == "list":
            tag = "ol" if block["ordered"] else "ul"
            items_html = "".join(
                f"<li>{parse_inline(item)}</li>" for item in block["items"]
            )
            html_parts.append(f"<{tag}>{items_html}</{tag}>")

        elif bt == "paragraph":
            content = parse_inline(block["content"])
            html_parts.append(f"<p>{content}</p>")

    return "\n".join(html_parts)


def convert_markdown(input_path: Path) -> str:
    """Read a markdown file, convert to HTML, return the result string."""
    lines = input_path.read_text(encoding="utf-8").splitlines()
    blocks = parse_blocks(lines)
    rendered = render_blocks(blocks)
    title = input_path.stem
    return html_template(title, rendered)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python markdown_converter.py <input_file.md>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(f"Error: not a file: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_html = convert_markdown(input_path)

    output_path = input_path.with_suffix(".html")

    try:
        output_path.write_text(output_html, encoding="utf-8")
        print(f"Converted: {input_path} → {output_path}")
    except PermissionError:
        # Fallback: write to a temp location
        import tempfile
        fallback = Path(tempfile.gettempdir()) / output_path.name
        fallback.write_text(output_html, encoding="utf-8")
        print(f"Converted: {input_path} → {fallback} (fallback due to permission)", file=sys.stderr)


if __name__ == "__main__":
    main()
