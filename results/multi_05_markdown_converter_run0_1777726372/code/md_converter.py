"""Core Markdown to HTML conversion module."""

import re


def _escape_html(text: str) -> str:
    """Escape HTML special characters: &, <, >."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _apply_inline_formatting(text: str) -> str:
    """Apply bold, italic, and link inline formatting to text.

    Process links first via placeholders to prevent italic/bold from
    corrupting URLs (e.g. underscores in URLs being turned into <em> tags).
    Then apply bold, then italic to the remaining text.
    Finally restore link placeholders with their HTML anchors,
    applying bold/italic inside the link text as well.
    """
    # Step 1: Extract links to safe placeholders
    link_pattern = r"\[(.+?)\]\((.+?)\)"
    links = {}  # placeholder -> (link_text, link_url)
    counter = 0

    def _extract_link(match):
        nonlocal counter
        link_text = match.group(1)
        link_url = match.group(2)
        placeholder = f"@@LINK_{counter}@@"
        links[placeholder] = (link_text, link_url)
        counter += 1
        return placeholder

    text = re.sub(link_pattern, _extract_link, text)

    # Step 2: Bold – **text** and __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)

    # Step 3: Italic – *text* and _text_
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)

    # Step 4: Restore link placeholders with HTML anchors.
    # Apply bold/italic to the link text so nested formatting works.
    for placeholder, (link_text, link_url) in links.items():
        # Apply bold and italic to link text (non-recursive)
        lt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", link_text)
        lt = re.sub(r"__(.+?)__", r"<strong>\1</strong>", lt)
        lt = re.sub(r"\*(.+?)\*", r"<em>\1</em>", lt)
        lt = re.sub(r"_(.+?)_", r"<em>\1</em>", lt)
        anchor = f'<a href="{link_url}">{lt}</a>'
        text = text.replace(placeholder, anchor)

    return text


def _is_heading(line: str) -> bool:
    """Check if a line is a markdown heading."""
    return bool(re.match(r"^#{1,6}\s", line))


def _is_unordered_list_item(line: str) -> bool:
    """Check if a line is an unordered list item (- or * followed by space)."""
    return bool(re.match(r"^[\-\*]\s", line))


def _is_ordered_list_item(line: str) -> bool:
    """Check if a line is an ordered list item (number. followed by space)."""
    return bool(re.match(r"^\d+\.\s", line))


def _is_code_fence(line: str) -> bool:
    """Check if a line is a fenced code block delimiter."""
    return line.startswith("```")


def _process_heading(line: str) -> str:
    """Convert a single heading line to HTML."""
    match = re.match(r"^(#{1,6})\s+(.*)", line)
    if not match:
        return line
    level = len(match.group(1))
    content = match.group(2)
    content = _apply_inline_formatting(content)
    return f"<h{level}>{content}</h{level}>"


def _process_unordered_list(lines: list) -> str:
    """Convert a list of unordered list item lines to HTML."""
    items = []
    for line in lines:
        # Strip the leading marker: '- ' or '* '
        content = re.sub(r"^[\-\*]\s+", "", line)
        content = _apply_inline_formatting(content)
        items.append(f"<li>{content}</li>")
    return "<ul>\n" + "\n".join(items) + "\n</ul>"


def _process_ordered_list(lines: list) -> str:
    """Convert a list of ordered list item lines to HTML."""
    items = []
    for line in lines:
        # Strip the leading marker: '1. ', '2. ', etc.
        content = re.sub(r"^\d+\.\s+", "", line)
        content = _apply_inline_formatting(content)
        items.append(f"<li>{content}</li>")
    return "<ol>\n" + "\n".join(items) + "\n</ol>"


def _process_code_block(lines: list) -> str:
    """Convert a list of code block lines to HTML with escaping."""
    # Join with newlines, then escape HTML
    code = "\n".join(lines)
    code = _escape_html(code)
    return f"<pre><code>{code}</code></pre>"


def _process_paragraph(lines: list) -> str:
    """Convert paragraph lines to HTML paragraph."""
    content = " ".join(lines)
    content = _apply_inline_formatting(content)
    return f"<p>{content}</p>"


def _wrap_html(body: str, title: str) -> str:
    """Wrap body content in a full HTML5 document with inline CSS."""
    css = """body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
    color: #333;
}
h1, h2, h3, h4, h5, h6 { color: #222; margin-top: 1.5em; }
pre {
    background: #f4f4f4;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
}
code {
    font-family: monospace;
}
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { padding-left: 2em; }"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>"""


def markdown_to_html(text: str) -> str:
    """Convert raw Markdown string to an HTML body string.

    Uses a state-machine approach for block parsing.
    """
    lines = text.split("\n")
    blocks = []  # Each block: (type, [lines])
    state = "normal"  # normal, code_fence, unordered_list, ordered_list
    current_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if state == "code_fence":
            if _is_code_fence(line):
                # End of code block
                blocks.append(("code", current_lines))
                current_lines = []
                state = "normal"
            else:
                current_lines.append(line)
            i += 1
            continue

        # Check for code fence start
        if _is_code_fence(line):
            # Flush any pending paragraph
            if current_lines:
                blocks.append(("paragraph", current_lines))
                current_lines = []
            state = "code_fence"
            i += 1
            continue

        # Check for heading
        if _is_heading(line):
            if current_lines:
                blocks.append(("paragraph", current_lines))
                current_lines = []
            blocks.append(("heading", [line]))
            i += 1
            continue

        # Check for unordered list
        if _is_unordered_list_item(line):
            if state != "unordered_list":
                if current_lines:
                    blocks.append(("paragraph", current_lines))
                    current_lines = []
                state = "unordered_list"
            current_lines.append(line)
            i += 1
            continue

        # Check for ordered list
        if _is_ordered_list_item(line):
            if state != "ordered_list":
                if current_lines:
                    blocks.append(("paragraph", current_lines))
                    current_lines = []
                state = "ordered_list"
            current_lines.append(line)
            i += 1
            continue

        # Blank line: block separator
        if line.strip() == "":
            if current_lines:
                if state == "unordered_list":
                    blocks.append(("unordered_list", current_lines))
                elif state == "ordered_list":
                    blocks.append(("ordered_list", current_lines))
                else:
                    blocks.append(("paragraph", current_lines))
                current_lines = []
            state = "normal"
            i += 1
            continue

        # Normal text line
        if state == "unordered_list" or state == "ordered_list":
            # A non-list line ends the list, but this line is not blank and not a list item
            # Flush the list and restart processing this line
            if state == "unordered_list":
                blocks.append(("unordered_list", current_lines))
            else:
                blocks.append(("ordered_list", current_lines))
            current_lines = []
            state = "normal"
            # Do NOT increment i; re-process this line
            continue

        # Normal line in normal state
        current_lines.append(line)
        i += 1

    # Flush remaining
    if current_lines:
        if state == "unordered_list":
            blocks.append(("unordered_list", current_lines))
        elif state == "ordered_list":
            blocks.append(("ordered_list", current_lines))
        elif state == "code_fence":
            blocks.append(("code", current_lines))
        else:
            blocks.append(("paragraph", current_lines))

    # Convert blocks to HTML
    html_parts = []
    for block_type, block_lines in blocks:
        if block_type == "heading":
            html_parts.append(_process_heading(block_lines[0]))
        elif block_type == "code":
            html_parts.append(_process_code_block(block_lines))
        elif block_type == "unordered_list":
            html_parts.append(_process_unordered_list(block_lines))
        elif block_type == "ordered_list":
            html_parts.append(_process_ordered_list(block_lines))
        elif block_type == "paragraph":
            html_parts.append(_process_paragraph(block_lines))

    return "\n".join(html_parts)
