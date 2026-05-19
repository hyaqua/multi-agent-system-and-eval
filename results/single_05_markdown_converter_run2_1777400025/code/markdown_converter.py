#!/usr/bin/env python3
"""
Markdown to HTML converter.
Converts .md files to .html using only the standard library.

Handles:
- Headings (h1-h6 via # syntax)
- Bold (**text** or __text__)
- Italic (*text* or _text_)
- Links [text](url)
- Unordered lists (- or *)
- Ordered lists (1. 2. etc.)
- Fenced code blocks (```)
- Paragraphs separated by blank lines
"""

import sys
import re
import os


def escape_html(text):
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def convert_inline(text):
    """
    Convert inline markdown elements to HTML using a delimiter-stack
    parser.  Handles nested **bold**, *italic*, and [links](url).
    """
    # ── Helper: find matching closer for a given marker ───────
    def find_closer(s, start, marker):
        """Find the matching closing marker, respecting nesting."""
        # For double-char markers like **, look for the exact string.
        # For single-char markers like *, look for * not followed by *.
        i = start
        while i < len(s):
            if marker == '**' or marker == '__':
                if s[i:i+2] == marker:
                    # Check this isn't part of a longer run like ***
                    # If preceded by the same char, it might belong to italic.
                    # We resolve ambiguity: *** at end -> * (italic) + ** (bold)
                    # by checking whether there's an unmatched single * before.
                    # For simplicity, accept ** that is not followed by a third *
                    # (this handles *** correctly when italic is inside bold).
                    after = i + 2
                    if after >= len(s) or s[after] != marker[0]:
                        return i
                i += 1
            else:  # single-char marker * or _
                if s[i] == marker:
                    # Ensure not part of a double marker
                    if i + 1 >= len(s) or s[i+1] != marker:
                        return i
                i += 1
        return -1

    # ── Recursive tokenizer ───────────────────────────────────
    def tokenize(s):
        result = []
        i = 0
        n = len(s)

        while i < n:
            # Bold: **text** or __text__
            if i + 1 < n and s[i:i+2] in ('**', '__'):
                marker = s[i:i+2]
                j = find_closer(s, i + 2, marker)
                if j != -1:
                    inner = tokenize(s[i+2:j])
                    result.append(f'<strong>{inner}</strong>')
                    i = j + 2
                    continue

            # Italic: *text* or _text_
            if s[i] in ('*', '_'):
                marker = s[i]
                # Must not be part of a double marker
                if i + 1 < n and s[i+1] == marker:
                    # This is ** or __ — handled above, skip here
                    # (We can also get here for *** which is ambiguous;
                    #  skip and let bold handler deal with it.)
                    i += 1
                    continue
                j = find_closer(s, i + 1, marker)
                if j != -1:
                    inner = tokenize(s[i+1:j])
                    result.append(f'<em>{inner}</em>')
                    i = j + 1
                    continue

            # Link: [text](url)
            if s[i] == '[':
                close_bracket = s.find('](', i)
                if close_bracket != -1:
                    close_paren = s.find(')', close_bracket + 2)
                    if close_paren != -1:
                        link_text = tokenize(s[i+1:close_bracket])
                        url = s[close_bracket+2:close_paren]
                        result.append(f'<a href="{url}">{link_text}</a>')
                        i = close_paren + 1
                        continue

            # Plain character
            result.append(s[i])
            i += 1

        return ''.join(result)

    return tokenize(text)


def convert_markdown_to_html(md_content):
    """
    Convert markdown string to HTML body content.
    Uses a line-by-line stateful parser.
    """
    lines = md_content.split('\n')
    html_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── Fenced code block ──────────────────────────────────
        if line.strip().startswith('```'):
            # Optional language specifier after opening ```
            language = line.strip()[3:].strip()
            if language:
                html_lines.append(f'<pre><code class="language-{escape_html(language)}">')
            else:
                html_lines.append('<pre><code>')
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('```'):
                    break
                html_lines.append(escape_html(lines[i]))
                i += 1
            html_lines.append('</code></pre>')
            i += 1  # skip closing ```
            continue

        # ── Blank line: skip ───────────────────────────────────
        if line.strip() == '':
            i += 1
            continue

        # ── Heading ────────────────────────────────────────────
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = convert_inline(heading_match.group(2).strip())
            html_lines.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # ── Unordered list ─────────────────────────────────────
        if re.match(r'^[\s]*[-*]\s+', line):
            html_lines.append('<ul>')
            while i < len(lines):
                li_match = re.match(r'^[\s]*[-*]\s+(.+)$', lines[i])
                if not li_match:
                    break
                content = convert_inline(li_match.group(1).strip())
                html_lines.append(f'<li>{content}</li>')
                i += 1
            html_lines.append('</ul>')
            continue

        # ── Ordered list ───────────────────────────────────────
        if re.match(r'^[\s]*\d+\.\s+', line):
            html_lines.append('<ol>')
            while i < len(lines):
                li_match = re.match(r'^[\s]*\d+\.\s+(.+)$', lines[i])
                if not li_match:
                    break
                content = convert_inline(li_match.group(1).strip())
                html_lines.append(f'<li>{content}</li>')
                i += 1
            html_lines.append('</ol>')
            continue

        # ── Paragraph ──────────────────────────────────────────
        para_lines = []
        while i < len(lines) and lines[i].strip() != '':
            # Stop if we encounter a structural element
            if re.match(r'^(#{1,6})\s+', lines[i]):
                break
            if re.match(r'^[\s]*[-*]\s+', lines[i]):
                break
            if re.match(r'^[\s]*\d+\.\s+', lines[i]):
                break
            if lines[i].strip().startswith('```'):
                break
            para_lines.append(lines[i].strip())
            i += 1

        if para_lines:
            para_text = ' '.join(para_lines)
            para_text = convert_inline(para_text)
            html_lines.append(f'<p>{para_text}</p>')

    return '\n'.join(html_lines)


def generate_full_html(body_content, title="Converted Markdown"):
    """Wrap body content in a full HTML document with an embedded stylesheet."""
    css = """
    * {
        box-sizing: border-box;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                     'Helvetica Neue', Arial, sans-serif;
        max-width: 820px;
        margin: 0 auto;
        padding: 2rem 1.5rem;
        background-color: #fcfcfc;
        color: #333;
        line-height: 1.7;
    }
    h1, h2, h3, h4, h5, h6 {
        margin-top: 1.8em;
        margin-bottom: 0.6em;
        font-weight: 600;
        color: #1a1a1a;
        line-height: 1.3;
    }
    h1 { font-size: 2.2em; border-bottom: 2px solid #ddd; padding-bottom: 0.35em; }
    h2 { font-size: 1.65em; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.3em; }
    h3 { font-size: 1.35em; }
    h4 { font-size: 1.15em; }
    h5 { font-size: 1.05em; }
    h6 { font-size: 0.95em; color: #555; }
    p { margin: 0.9em 0; }
    ul, ol { margin: 0.6em 0; padding-left: 2.2em; }
    li { margin: 0.3em 0; }
    pre {
        background-color: #2d2d2d;
        color: #f0f0f0;
        padding: 1.2em 1.4em;
        border-radius: 8px;
        overflow-x: auto;
        font-family: 'SF Mono', 'Fira Code', 'Courier New', Courier, monospace;
        font-size: 0.9em;
        line-height: 1.5;
        margin: 1em 0;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
        font-size: inherit;
        color: inherit;
    }
    code {
        background-color: #f0f0f0;
        padding: 0.2em 0.45em;
        border-radius: 4px;
        font-family: 'SF Mono', 'Fira Code', 'Courier New', Courier, monospace;
        font-size: 0.9em;
    }
    a {
        color: #0366d6;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
    strong { font-weight: 700; }
    em { font-style: italic; }
    """
    # Dedent the CSS for clean output
    css_lines = [line[4:] if line.startswith('    ') else line
                 for line in css.strip().split('\n')]
    css_clean = '\n'.join(css_lines).strip()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(title)}</title>
    <style>
{css_clean}
    </style>
</head>
<body>
{body_content}
</body>
</html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python markdown_converter.py <input.md>", file=sys.stderr)
        print("Converts a Markdown file to an HTML file with the same base name.",
              file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Determine output path: same name with .html extension
    base, _ = os.path.splitext(input_path)
    output_path = base + '.html'

    # Read the markdown input
    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert markdown → HTML body
    body = convert_markdown_to_html(md_content)

    # Use the input filename (without extension) as the page title
    title = os.path.splitext(os.path.basename(input_path))[0]
    html = generate_full_html(body, title)

    # Write the output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Converted '{input_path}' → '{output_path}'")


if __name__ == '__main__':
    main()
