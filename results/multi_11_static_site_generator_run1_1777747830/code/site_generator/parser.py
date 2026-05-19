"""Parser for Markdown files with YAML-like front matter."""

from typing import Dict, List, Tuple


def parse_file(path: str) -> Tuple[Dict, str]:
    """Parse a content file into front matter variables and Markdown body.

    Args:
        path: Path to the .md file.

    Returns:
        Tuple of (front_matter dict, body string).
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()

    # Must start with ---
    if not lines or lines[0].strip() != "---":
        return {}, content

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    front_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])

    front_matter = {}
    for line in front_lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Parse lists: [item1, item2]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                items = [item.strip().strip("'\"") for item in inner.split(",")]
            else:
                items = []
            front_matter[key] = items
        else:
            # Strip quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            front_matter[key] = value

    return front_matter, body


def validate_front_matter(
    front_matter: Dict, path: str
) -> List[str]:
    """Validate required keys in front matter.

    Args:
        front_matter: Parsed front matter dict.
        path: Source file path for error messages.

    Returns:
        List of error strings (empty if valid).
    """
    errors = []
    required = ["title", "type", "template"]
    for key in required:
        if key not in front_matter:
            errors.append(f"Missing required key '{key}' in {path}")
    return errors
