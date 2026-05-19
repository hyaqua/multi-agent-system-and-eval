#!/usr/bin/env python3
"""Convert Markdown files to HTML with embedded CSS for readability."""

import re
import sys
import os


CSS = """\
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.7;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    color: #1a1a1a;
    background: #fefefe;
}
h1, h2, h3, h4, h5, h6 {
    color: #111;
    line-height: 1.25;
    margin-top: 1.75em;
    margin-bottom: 0.5em;
}
h1 { font-size: 2rem; border-bottom: 2px solid #e0e0e0; padding-bottom: 0.35em; }
h2 { font-size: 1.5rem; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.25em; }
h3 { font-size: 1.25rem; }
h4 { font-size: 1.1rem; }
h5, h6 { font-size: 1rem; }
p { margin: 0 0 1em; }
pre {
    background: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 1em;
    overflow-x: auto;
    font-size: 0.9rem;
    line-height: 1.5;
}
code {
    font-family: "SF Mono", "Fira Code", "Fira Mono", Menlo, Consolas, monospace;
    font-size: 0.9em;
    background: #f5f5f5;
    padding: 0.15em 0.35em;
    border-radius: 3px;
}
pre code {
    background: none;
    padding: 0;
    font-size: inherit;
}
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { padding-left: 2em; margin: 0 0 1em; }
li { margin-bottom: 0.25em; }
blockquote {
    border-left: 4px solid #ddd;
    margin: 0 0 1em;
    padding: 0.5em 1em;
    color: #555;
}
table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
th, td { border: 1px solid #ddd; padding: 0.5em 1em; text-align: left; }
th { background: #f5f5f5; }
hr { border: none; border-top: 1px solid #e0e0e0; margin: 2em 0; }
img { max-width: 100%; }
"""


def parse_inline(text: str) -> str:
    """Convert inline markdown to HTML tags using placeholder protection."""
    placeholders = []

    def save(m):
        placeholders.append(m.group(0))
        return f'\x00{len(placeholders) - 1}\x00'

    # 1. Inline code: `code`
    text = re.sub(r'(?<!`)`([^`]+)`(?!`)', save, text)

    # 2. Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', save, text)

    # 3. Links: [text](url)
    text = re.sub(r'\[([^\]]*)\]\(([^)]+)\)', save, text)

    # 4. Bold+Italic combined: ***text*** or ___text___
    text = re.sub(r'\*\*\*(.+?)\*\*\*', save, text)
    text = re.sub(r'___(.+?)___', save, text)

    # 5. Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', save, text)
    text = re.sub(r'__(.+?)__', save, text)

    # 6. Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', save, text)
    text = re.sub(r'(?<![a-zA-Z0-9])_(.+?)_(?![a-zA-Z0-9])', save, text)

    # Process saved matches
    for i, ph in enumerate(placeholders):
        if ph.startswith('`') and not ph.startswith('``'):
            replacement = f'<code>{ph[1:-1]}</code>'
        elif ph.startswith('!['):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', ph)
            replacement = f'<img src="{m.group(2)}" alt="{m.group(1)}">'
        elif ph.startswith('['):
            m = re.match(r'\[([^\]]*)\]\(([^)]+)\)', ph)
            inner = parse_inline(m.group(1))
            replacement = f'<a href="{m.group(2)}">{inner}</a>'
        elif ph.startswith('***'):
            inner = parse_inline(ph[3:-3])
            replacement = f'<strong><em>{inner}</em></strong>'
        elif ph.startswith('___'):
            inner = parse_inline(ph[3:-3])
            replacement = f'<strong><em>{inner}</em></strong>'
        elif ph.startswith('**'):
            inner = parse_inline(ph[2:-2])
            replacement = f'<strong>{inner}</strong>'
        elif ph.startswith('__'):
            inner = parse_inline(ph[2:-2])
            replacement = f'<strong>{inner}</strong>'
        elif ph.startswith('*'):
            inner = parse_inline(ph[1:-1])
            replacement = f'<em>{inner}</em>'
        elif ph.startswith('_'):
            inner = parse_inline(ph[1:-1])
            replacement = f'<em>{inner}</em>'
        else:
            replacement = ph

        text = text.replace(f'\x00{i}\x00', replacement)

    return text


def convert_markdown(md_text: str) -> str:
    """Convert markdown text to HTML body content."""
    lines = md_text.split('\n')
    output_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('```'):
                    break
                code_lines.append(lines[i])
                i += 1
            code_content = '\n'.join(code_lines)
            # Escape HTML entities in code
            code_content = code_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            output_lines.append(f'<pre><code>{code_content}</code></pre>')
            i += 1
            continue

        # Heading (must be at start of line)
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = parse_inline(heading_match.group(2).strip())
            output_lines.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Unordered list
        ul_match = re.match(r'^(\s*)[-*]\s+(.+)$', line)
        if ul_match:
            list_items = []
            while i < len(lines):
                m = re.match(r'^(\s*)[-*]\s+(.+)$', lines[i])
                if not m:
                    break
                list_items.append(parse_inline(m.group(2).strip()))
                i += 1
            items_html = ''.join(f'<li>{item}</li>' for item in list_items)
            output_lines.append(f'<ul>{items_html}</ul>')
            continue

        # Ordered list
        ol_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ol_match:
            list_items = []
            while i < len(lines):
                m = re.match(r'^(\s*)\d+\.\s+(.+)$', lines[i])
                if not m:
                    break
                list_items.append(parse_inline(m.group(2).strip()))
                i += 1
            items_html = ''.join(f'<li>{item}</li>' for item in list_items)
            output_lines.append(f'<ol>{items_html}</ol>')
            continue

        # Blank line – skip
        if line.strip() == '':
            i += 1
            continue

        # Paragraph: accumulate lines until blank line or special line
        para_lines = []
        while i < len(lines):
            if lines[i].strip() == '':
                break
            if lines[i].strip().startswith('```'):
                break
            if re.match(r'^(#{1,6})\s+', lines[i]):
                break
            if re.match(r'^(\s*)[-*]\s+', lines[i]):
                break
            if re.match(r'^(\s*)\d+\.\s+', lines[i]):
                break
            para_lines.append(lines[i].strip())
            i += 1

        if para_lines:
            content = parse_inline(' '.join(para_lines))
            output_lines.append(f'<p>{content}</p>')

    return '\n'.join(output_lines)


def build_html(body: str, title: str = "") -> str:
    """Wrap body content in a full HTML document with stylesheet."""
    safe_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
{CSS}
</style>
</head>
<body>
{body}
</body>
</html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python md2html.py <input.md>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.isfile(input_path):
        print(f"Error: file not found: '{input_path}'", file=sys.stderr)
        sys.exit(1)

    # Read markdown
    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Derive output path
    base, _ = os.path.splitext(input_path)
    output_path = base + '.html'

    # Derive title from first heading or filename
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else os.path.splitext(os.path.basename(input_path))[0]

    # Convert
    body = convert_markdown(md_text)
    html = build_html(body, title)

    # Write
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Converted: {input_path} -> {output_path}")


if __name__ == '__main__':
    main()
