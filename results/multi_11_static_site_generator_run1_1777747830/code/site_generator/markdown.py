"""Basic Markdown to HTML converter.

Supports: headings, bold, italic, links, unordered/ordered lists,
fenced code blocks, and paragraphs.
"""

import re
from typing import List


def to_html(text: str) -> str:
    """Convert Markdown text to HTML.

    Args:
        text: Raw Markdown string.

    Returns:
        HTML string.
    """
    lines = text.splitlines()
    if not lines:
        return ""

    # Split into blocks (blank-line separated)
    blocks = _split_blocks(lines)

    html_blocks = []
    for block in blocks:
        block_type, html = _process_block(block)
        html_blocks.append(html)

    return "\n".join(html_blocks)


def _split_blocks(lines: List[str]) -> List[List[str]]:
    """Split lines into blocks separated by blank lines."""
    blocks = []
    current_block = []

    for line in lines:
        if line.strip() == "":
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    return blocks


def _process_block(lines: List[str]) -> tuple:
    """Determine block type and convert to HTML.

    Returns:
        Tuple of (block_type, html_string).
    """
    first = lines[0].lstrip()

    # Fenced code block: starts with ```
    if first.startswith("```"):
        return _code_block(lines)

    # Heading: starts with #
    if first.startswith("#"):
        return _heading(lines[0])

    # Unordered list: starts with - or *
    if first.startswith("- ") or first.startswith("* "):
        return _unordered_list(lines)

    # Ordered list: starts with digit followed by . and space
    if re.match(r"^\d+\.\s", first):
        return _ordered_list(lines)

    # Horizontal rule
    if re.match(r"^[-*_]{3,}$", first.strip()):
        return ("hr", "<hr>")

    # Blockquote
    if first.startswith("> "):
        return _blockquote(lines)

    # Default: paragraph
    return _paragraph(lines)


def _code_block(lines: List[str]) -> tuple:
    """Convert fenced code block."""
    # Remove opening ```
    if len(lines) > 1:
        content_lines = lines[1:]
    else:
        content_lines = []

    # Remove closing ``` if present
    if content_lines and content_lines[-1].strip() == "```":
        content_lines = content_lines[:-1]

    # Escape HTML entities
    code_text = "\n".join(content_lines)
    code_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;"
    )

    html = f"<pre><code>{code_text}</code></pre>"
    return ("code", html)


def _heading(line: str) -> tuple:
    """Convert heading line."""
    level = 0
    for ch in line:
        if ch == "#":
            level += 1
        else:
            break

    if level < 1 or level > 6:
        level = 1

    text = line[level:].strip()
    text = _inline_format(text)
    html = f"<h{level}>{text}</h{level}>"
    return (f"h{level}", html)


def _unordered_list(lines: List[str]) -> tuple:
    """Convert unordered list items."""
    items = []
    for line in lines:
        stripped = line.lstrip()
        # Remove leading - or * and space
        if stripped.startswith("- "):
            text = stripped[2:]
        elif stripped.startswith("* "):
            text = stripped[2:]
        else:
            text = stripped
        text = _inline_format(text)
        items.append(f"<li>{text}</li>")

    html = "<ul>\n" + "\n".join(items) + "\n</ul>"
    return ("ul", html)


def _ordered_list(lines: List[str]) -> tuple:
    """Convert ordered list items."""
    items = []
    for line in lines:
        stripped = line.lstrip()
        # Remove leading number. and space
        match = re.match(r"^\d+\.\s+(.*)", stripped)
        if match:
            text = match.group(1)
        else:
            text = stripped
        text = _inline_format(text)
        items.append(f"<li>{text}</li>")

    html = "<ol>\n" + "\n".join(items) + "\n</ol>"
    return ("ol", html)


def _blockquote(lines: List[str]) -> tuple:
    """Convert blockquote."""
    content_lines = []
    for line in lines:
        if line.startswith("> "):
            content_lines.append(line[2:])
        elif line.startswith(">"):
            content_lines.append(line[1:])
        else:
            content_lines.append(line)

    # Join and process inner content recursively for inline
    inner = "\n".join(content_lines)
    inner_html = _inline_format(inner)
    html = f"<blockquote>{inner_html}</blockquote>"
    return ("blockquote", html)


def _paragraph(lines: List[str]) -> tuple:
    """Convert paragraph."""
    joined = " ".join(lines)
    html = _inline_format(joined)
    return ("p", f"<p>{html}</p>")


def _inline_format(text: str) -> str:
    """Apply inline formatting: bold, italic, links, images.

    Order matters: process longer patterns first.
    """
    # Image: ![alt](url)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r'<img src="\2" alt="\1">',
        text,
    )

    # Link: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )

    # Bold: **text** or __text__
    text = re.sub(
        r"\*\*(.+?)\*\*",
        r"<strong>\1</strong>",
        text,
    )
    text = re.sub(
        r"__(.+?)__",
        r"<strong>\1</strong>",
        text,
    )

    # Italic: *text* or _text_ (but not **)
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
        r"<em>\1</em>",
        text,
    )
    text = re.sub(
        r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)",
        r"<em>\1</em>",
        text,
    )

    # Inline code: `code`
    text = re.sub(
        r"`([^`]+)`",
        r"<code>\1</code>",
        text,
    )

    return text
