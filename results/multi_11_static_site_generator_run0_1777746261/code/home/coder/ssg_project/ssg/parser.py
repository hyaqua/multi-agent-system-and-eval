"""Parser for Markdown files with YAML front matter.

Front matter is delimited by --- lines at the top of the file.
Keys: title, date, tags, template (and any extras).
tags can be a comma-separated string or a YAML-style list [a, b, c].
"""

from pathlib import Path
from typing import Any


def parse_content_file(filepath: Path) -> dict[str, Any]:
    """Parse a single .md file, returning a dict with keys:
    - slug: filename without extension
    - metadata: dict of front-matter key/value pairs
    - body: raw Markdown string after front matter
    """
    raw = filepath.read_text(encoding="utf-8")
    slug = filepath.stem

    lines = raw.splitlines()

    metadata: dict[str, Any] = {}
    body = raw

    # Check for front matter delimited by ---
    if lines and lines[0].strip() == "---":
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx is not None:
            fm_lines = lines[1:end_idx]
            metadata = _parse_front_matter(fm_lines)
            body = "\n".join(lines[end_idx + 1:])

    # Default template if not specified
    if "template" not in metadata:
        metadata["template"] = "base.html"

    return {
        "slug": slug,
        "metadata": metadata,
        "body": body.strip(),
    }


def _parse_front_matter(lines: list[str]) -> dict[str, Any]:
    """Parse key: value lines from front matter.

    Supports:
    - key: value
    - key: value with spaces
    - tags: tag1, tag2, tag3   (comma-separated)
    - tags: [tag1, tag2, tag3] (YAML-style list)
    """
    result: dict[str, Any] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Handle tags: support both comma-separated and YAML-style [a, b, c]
            if key == "tags":
                if value:
                    # Check for YAML-style list: [a, b, c]
                    if value.startswith("[") and value.endswith("]"):
                        inner = value[1:-1]
                        result[key] = [t.strip() for t in inner.split(",") if t.strip()]
                    else:
                        result[key] = [t.strip() for t in value.split(",") if t.strip()]
                else:
                    result[key] = []
            else:
                result[key] = value
    return result
