"""Template engine: substitutes {{variable}} placeholders with data values."""

import re
from pathlib import Path


class TemplateEngine:
    """Simple template engine that replaces {{variable}} with values from a data dict."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def render(self, template_name: str, data: dict[str, str]) -> str:
        """Load a template file and substitute all {{variable}} placeholders.

        Args:
            template_name: Filename of the template (e.g. 'base.html').
            data: Dict mapping variable names to their string values.

        Returns:
            The rendered template string.
        """
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        template = template_path.read_text(encoding="utf-8")

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1).strip()
            return data.get(var_name, "")

        return re.sub(r"\{\{(.*?)\}\}", replace_var, template)
