"""Basic Markdown to HTML converter.

Supports:
- Headings (# through ######)
- Bold (**text**) and italic (*text*)
- Inline code (`code`)
- Links [text](url) and images ![alt](url)
- Unordered lists (*, -, +)
- Ordered lists (1. 2. etc.)
- Fenced code blocks (``` ... ```)
- Blockquotes (> text)
- Paragraphs (blank-line separated)
"""

import re


def markdown_to_html(text: str) -> str:
    """Convert Markdown text to HTML."""

    # Helper to escape HTML special chars
    def _escape_html(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Helper to process inline elements
    def _process_inline(s: str) -> str:
        # Images first (before links)
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', s)
        # Links
        s = re.sub(r"\[([^\]]*)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        # Bold
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        # Italic
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        # Inline code
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    # First extract fenced code blocks so we don't process their contents
    code_blocks: list[str] = []

    def _extract_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"%%CODEBLOCK_{len(code_blocks) - 1}%%"

    text = re.sub(r"```(?:\w*)\n(.*?)```", _extract_code_block, text, flags=re.DOTALL)

    # Now process the rest
    html_lines: list[str] = []
    lines = text.splitlines()
    i = 0
    in_list = False
    list_tag: str = ""
    in_paragraph = False

    while i < len(lines):
        line = lines[i]

        # Check for code block placeholders
        if line.strip().startswith("%%CODEBLOCK_"):
            if in_list:
                html_lines.append(f"</{list_tag}>")
                in_list = False
                list_tag = ""
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            idx_str = line.strip()[len("%%CODEBLOCK_"):]
            idx_str = idx_str[:idx_str.index("%%")]
            idx = int(idx_str)
            html_lines.append(f"<pre><code>{_escape_html(code_blocks[idx])}</code></pre>")
            i += 1
            continue

        # Check for heading (# at start of line)
        heading_match = re.match(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", line)
        if heading_match:
            if in_list:
                html_lines.append(f"</{list_tag}>")
                in_list = False
                list_tag = ""
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            level = len(heading_match.group(1))
            heading_text = _process_inline(heading_match.group(2))
            html_lines.append(f"<h{level}>{heading_text}</h{level}>")
            i += 1
            continue

        # Check for blockquote
        bq_match = re.match(r"^>\s*(.*)$", line)
        if bq_match:
            if in_list:
                html_lines.append(f"</{list_tag}>")
                in_list = False
                list_tag = ""
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            bq_lines: list[str] = []
            while i < len(lines) and re.match(r"^>\s*(.*)$", lines[i]):
                bq_content = re.match(r"^>\s*(.*)$", lines[i]).group(1)
                bq_lines.append(_process_inline(bq_content))
                i += 1
            bq_html = "<br>".join(bq_lines) if len(bq_lines) > 1 else bq_lines[0] if bq_lines else ""
            html_lines.append(f"<blockquote>{bq_html}</blockquote>")
            continue

        # Check for horizontal rule
        if re.match(r"^(\*{3,}|-{3,}|_{3,})$", line.strip()):
            if in_list:
                html_lines.append(f"</{list_tag}>")
                in_list = False
                list_tag = ""
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append("<hr>")
            i += 1
            continue

        # Check for unordered list items
        ul_match = re.match(r"^(\s*)([*\-+])\s+(.+)$", line)
        if ul_match:
            if not in_list:
                in_list = True
                list_tag = "ul"
                html_lines.append("<ul>")
            elif list_tag != "ul":
                html_lines.append(f"</{list_tag}>")
                list_tag = "ul"
                html_lines.append("<ul>")
            html_lines.append(f"<li>{_process_inline(ul_match.group(3))}</li>")
            i += 1
            continue

        # Check for ordered list items
        ol_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if ol_match:
            if not in_list:
                in_list = True
                list_tag = "ol"
                html_lines.append("<ol>")
            elif list_tag != "ol":
                html_lines.append(f"</{list_tag}>")
                list_tag = "ol"
                html_lines.append("<ol>")
            html_lines.append(f"<li>{_process_inline(ol_match.group(3))}</li>")
            i += 1
            continue

        # If we were in a list and now we're not, close it
        if in_list:
            html_lines.append(f"</{list_tag}>")
            in_list = False
            list_tag = ""

        # Empty line = paragraph break
        if not line.strip():
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            i += 1
            continue

        # Regular text - start or continue a paragraph
        if not in_paragraph:
            html_lines.append("<p>")
            in_paragraph = True
            html_lines.append(_process_inline(line))
        else:
            html_lines.append("<br>" + _process_inline(line))

        i += 1

    # Close any open list
    if in_list:
        html_lines.append(f"</{list_tag}>")

    # Close any open paragraph
    if in_paragraph:
        html_lines.append("</p>")

    return "\n".join(html_lines)
