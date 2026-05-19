"""Simple template engine with {{variable}} substitution."""

import re
from typing import Dict


def render(template_string: str, variables: Dict) -> str:
    """Replace {{variable}} placeholders with values from the dictionary.

    Args:
        template_string: The template with {{key}} placeholders.
        variables: Dictionary mapping key names to replacement strings.

    Returns:
        Rendered string with placeholders replaced.
    """

    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        if key in variables:
            value = variables[key]
            # If value is a list, join with ', '
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)
        # Leave unknown placeholders as-is
        return match.group(0)

    pattern = r"\{\{\s*(\w+)\s*\}\}"
    return re.sub(pattern, replacer, template_string)
