"""Template engine with {{variable}} placeholder replacement.

Supports:
- {{variable}} - replaced with the value of variable
- {{content}} - special placeholder for the converted Markdown body
- Conditional blocks: {{#if variable}}...{{/if}}
- Loop blocks: {{#each items}}...{{/each}} (basic support)
"""

import re


class Template:
    """A template loaded from a file."""

    def __init__(self, template_text: str):
        self.template_text = template_text

    def render(self, variables: dict, content_html: str = '') -> str:
        """Render the template with variables and content."""
        result = self.template_text

        # Replace {{content}} first
        result = result.replace('{{content}}', content_html)

        # Handle simple conditionals {{#if variable}}...{{/if}}
        result = self._process_conditionals(result, variables)

        # Handle loops {{#each items}}...{{/each}}
        result = self._process_loops(result, variables)

        # Replace remaining {{variable}} placeholders
        def replace_var(match):
            var_name = match.group(1).strip()
            value = variables.get(var_name, '')
            if isinstance(value, list):
                return ', '.join(str(v) for v in value)
            return str(value)

        result = re.sub(r'\{\{([^#/].*?)\}\}', replace_var, result)

        return result

    def _process_conditionals(self, text: str, variables: dict) -> str:
        """Process {{#if var}}...{{/if}} blocks."""
        pattern = re.compile(r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}', re.DOTALL)
        def replacer(match):
            var_name = match.group(1)
            content = match.group(2)
            if variables.get(var_name):
                return content
            return ''
        return pattern.sub(replacer, text)

    def _process_loops(self, text: str, variables: dict) -> str:
        """Process {{#each items}}...{{/each}} blocks."""
        pattern = re.compile(r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}', re.DOTALL)
        def replacer(match):
            list_name = match.group(1)
            item_template = match.group(2)
            items = variables.get(list_name, [])
            if not isinstance(items, list):
                items = []
            result_parts = []
            for item in items:
                part = item_template
                if isinstance(item, dict):
                    for k, v in item.items():
                        part = part.replace('{{' + k + '}}', str(v))
                else:
                    part = part.replace('{{this}}', str(item))
                result_parts.append(part)
            return ''.join(result_parts)
        return pattern.sub(replacer, text)


def load_template(path: str) -> Template:
    """Load a template from a file path."""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    return Template(text)
