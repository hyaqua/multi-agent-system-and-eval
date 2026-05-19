"""Convert a limited subset of Markdown to HTML."""

import re


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def _process_inline(text: str) -> str:
    """Process inline Markdown elements within a line or block of text.

    Order matters: code first (protect from other rules), then links,
    then bold, then italic.
    """
    # Protect inline code
    code_placeholders = {}

    def _save_code(match):
        code = match.group(1)
        placeholder = f'\x00CODE{len(code_placeholders)}\x00'
        code_placeholders[placeholder] = f'<code>{_escape_html(code)}</code>'
        return placeholder

    text = re.sub(r'`([^`]+)`', _save_code, text)

    # Images: ![alt](url)
    def _img_repl(match):
        alt = match.group(1)
        url = match.group(2)
        return f'<img src="{url}" alt="{alt}">'

    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _img_repl, text)

    # Links: [text](url)
    def _link_repl(match):
        link_text = match.group(1)
        url = match.group(2)
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r'\[([^\]]*)\]\(([^)]+)\)', _link_repl, text)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)

    # Italic: *text* or _text_
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)

    # Restore code placeholders
    for placeholder, code_html in code_placeholders.items():
        text = text.replace(placeholder, code_html)

    return text


def convert(md_text: str) -> str:
    """Convert Markdown text to HTML.

    Supports:
    - Headings (# through ######)
    - Paragraphs
    - Unordered lists (- or *)
    - Ordered lists (1. 2. etc.)
    - Fenced code blocks (```)
    - Inline: bold, italic, inline code, links, images

    Args:
        md_text: Raw Markdown text.

    Returns:
        HTML string.
    """
    # First, extract and protect fenced code blocks
    code_blocks = {}

    def _save_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        placeholder = f'\x01BLOCK{len(code_blocks)}\x01'
        code_blocks[placeholder] = (
            f'<pre><code>{_escape_html(code)}</code></pre>'
        )
        return placeholder

    # Handle ```language\ncode\n```  and  ```code```
    text = re.sub(
        r'```(\w*)\n(.*?)```',
        _save_block,
        md_text,
        flags=re.DOTALL
    )

    lines = text.split('\n')
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if line.strip() == '':
            i += 1
            continue

        # Check for heading
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            content = _process_inline(content)
            output.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Check for unordered list
        ul_match = re.match(r'^[\-\*]\s+(.*)', line)
        if ul_match:
            list_items = []
            while i < len(lines) and re.match(r'^[\-\*]\s+(.*)', lines[i]):
                item_match = re.match(r'^[\-\*]\s+(.*)', lines[i])
                item_content = item_match.group(1)
                list_items.append(
                    f'<li>{_process_inline(item_content)}</li>'
                )
                i += 1
            output.append('<ul>' + ''.join(list_items) + '</ul>')
            continue

        # Check for ordered list
        ol_match = re.match(r'^\d+\.\s+(.*)', line)
        if ol_match:
            list_items = []
            while i < len(lines) and re.match(r'^\d+\.\s+(.*)', lines[i]):
                item_match = re.match(r'^\d+\.\s+(.*)', lines[i])
                item_content = item_match.group(1)
                list_items.append(
                    f'<li>{_process_inline(item_content)}</li>'
                )
                i += 1
            output.append('<ol>' + ''.join(list_items) + '</ol>')
            continue

        # Check for horizontal rule
        if re.match(r'^(\-{3,}|\*{3,}|_{3,})\s*$', line):
            output.append('<hr>')
            i += 1
            continue

        # Otherwise, it's a paragraph - collect contiguous non-empty lines
        para_lines = []
        while i < len(lines) and lines[i].strip() != '':
            # Stop if we hit a special line
            current = lines[i]
            if re.match(r'^(#{1,6})\s+', current):
                break
            if re.match(r'^[\-\*]\s+', current):
                break
            if re.match(r'^\d+\.\s+', current):
                break
            if re.match(r'^(\-{3,}|\*{3,}|_{3,})\s*$', current):
                break
            para_lines.append(current.strip())
            i += 1

        if para_lines:
            para_text = ' '.join(para_lines)
            para_text = _process_inline(para_text)
            output.append(f'<p>{para_text}</p>')

    result = '\n'.join(output)

    # Restore code blocks
    for placeholder, block_html in code_blocks.items():
        result = result.replace(placeholder, block_html)

    return result
