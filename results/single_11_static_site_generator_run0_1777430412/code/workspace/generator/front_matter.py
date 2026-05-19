"""YAML-style front matter parser.

Parses front matter delimited by --- lines at the start of a content file.
Supports simple YAML key: value pairs. Values can be quoted strings,
unquoted strings, or lists using [item1, item2] syntax.
"""

import re


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse front matter and body from raw text.

    Front matter is delimited by --- on its own line at the start.
    Returns (metadata_dict, body_text).

    Raises ValueError if the file does not begin with front matter.
    """
    text = text.lstrip('\ufeff')  # Strip BOM if present
    if not text.startswith('---'):
        raise ValueError("Content file must start with --- front matter delimiter")

    # Find the closing ---
    # Split on newlines, find second ---
    lines = text.split('\n')
    if lines[0].strip() != '---':
        raise ValueError("Content file must start with --- front matter delimiter")

    closing_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            closing_idx = i
            break

    if closing_idx is None:
        raise ValueError("Unclosed front matter: missing closing ---")

    front_matter_lines = lines[1:closing_idx]
    body_lines = lines[closing_idx + 1:]

    metadata = _parse_yaml_lines(front_matter_lines)
    body = '\n'.join(body_lines)

    return metadata, body


def _parse_yaml_lines(lines: list[str]) -> dict:
    """Parse simple YAML key: value pairs from lines."""
    metadata = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Match key: value
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)', stripped)
        if match:
            key = match.group(1).lower()
            value = match.group(2).strip()

            # Handle quoted strings
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            # Handle lists: [item1, item2]
            if value.startswith('[') and value.endswith(']'):
                inner = value[1:-1]
                items = [item.strip().strip('"').strip("'") for item in inner.split(',')]
                value = [item for item in items if item]

            metadata[key] = value

    return metadata
