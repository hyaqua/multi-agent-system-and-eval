"""Simple Markdown to HTML converter.

Converts basic Markdown:
- Headings (#, ##, ###, etc.)
- Bold (**text**)
- Italic (*text*)
- Links ([text](url))
- Images (![alt](url))
- Unordered lists (-, *, +)
- Ordered lists (1., 2.)
- Code blocks (```)
- Inline code (`code`)
- Paragraphs (blank-line separated blocks)
- Horizontal rules (---, ***, ___)
"""

import re


def markdown_to_html(text: str) -> str:
    """Convert Markdown text to HTML."""
    lines = text.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code blocks (```)
        if line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing ```
            code_content = '\n'.join(code_lines)
            # Escape HTML in code
            code_content = _escape_html(code_content)
            result.append(f'<pre><code>{code_content}</code></pre>')
            continue

        # Horizontal rules
        if re.match(r'^[ ]{0,3}([-*_])[ ]*\1[ ]*\1[ ]*$', line.strip()):
            result.append('<hr>')
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            content = _inline_formatting(content)
            result.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Unordered list items
        ul_match = re.match(r'^[ ]{0,3}[-*+]\s+(.*)', line)
        if ul_match:
            ul_items = []
            while i < len(lines):
                m = re.match(r'^[ ]{0,3}[-*+]\s+(.*)', lines[i])
                if not m:
                    break
                ul_items.append(_inline_formatting(m.group(1)))
                i += 1
            items_html = ''.join(f'<li>{item}</li>' for item in ul_items)
            result.append(f'<ul>{items_html}</ul>')
            continue

        # Ordered list items
        ol_match = re.match(r'^[ ]{0,3}\d+\.\s+(.*)', line)
        if ol_match:
            ol_items = []
            while i < len(lines):
                m = re.match(r'^[ ]{0,3}\d+\.\s+(.*)', lines[i])
                if not m:
                    break
                ol_items.append(_inline_formatting(m.group(1)))
                i += 1
            items_html = ''.join(f'<li>{item}</li>' for item in ol_items)
            result.append(f'<ol>{items_html}</ol>')
            continue

        # Blank line
        if line.strip() == '':
            i += 1
            continue

        # Paragraph - collect lines until blank line or special element
        para_lines = []
        while i < len(lines) and lines[i].strip() != '' and \
                not re.match(r'^(#{1,6}\s|```|[-*+]\s|\d+\.\s)', lines[i]) and \
                not re.match(r'^[ ]{0,3}([-*_])[ ]*\1[ ]*\1[ ]*$', lines[i].strip()):
            para_lines.append(lines[i])
            i += 1

        if para_lines:
            para_text = ' '.join(para_lines)
            para_text = _inline_formatting(para_text)
            result.append(f'<p>{para_text}</p>')

    return '\n'.join(result)


def _inline_formatting(text: str) -> str:
    """Apply inline formatting: bold, italic, links, images, code."""
    # The order matters: code first (to protect it), then images, links, bold, italic

    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', text)

    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)

    # Italic: *text* or _text_
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)

    return text


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text
