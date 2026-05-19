"""Parse YAML-like front matter from Markdown files."""


def parse(text: str) -> dict:
    """Extract front matter from text between --- delimiters.

    Args:
        text: The full text of a Markdown file.

    Returns:
        A dict of key: value pairs extracted from the front matter.
        Returns an empty dict if no front matter is found.
    """
    # Check for opening ---
    stripped = text.lstrip()
    if not stripped.startswith('---'):
        return {}

    # Split on ---: parts[0] is empty (before first ---),
    # parts[1] is front matter, parts[2] is the body (may contain more ---)
    parts = stripped.split('---', 2)
    if len(parts) < 3:
        return {}

    fm_text = parts[1]
    result = {}

    for line in fm_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if value and len(value) >= 2:
                if (value[0] == '"' and value[-1] == '"') or \
                   (value[0] == "'" and value[-1] == "'"):
                    value = value[1:-1]
            result[key] = value

    return result


def split_frontmatter(text: str) -> tuple:
    """Split text into (frontmatter_dict, body_text).

    Args:
        text: The full text of a Markdown file.

    Returns:
        A tuple of (dict, str) where dict is the parsed front matter
        and str is the body text after the closing ---.
    """
    stripped = text.lstrip()
    if not stripped.startswith('---'):
        return {}, text

    parts = stripped.split('---', 2)
    if len(parts) < 3:
        return {}, text

    fm = parse(text)
    body = parts[2].strip()
    return fm, body
