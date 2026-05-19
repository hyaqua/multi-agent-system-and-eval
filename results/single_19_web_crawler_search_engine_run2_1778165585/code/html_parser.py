"""HTML parser using html.parser from the standard library.

Extracts visible text content and anchor href links.
"""

from html.parser import HTMLParser
from typing import List, Tuple


class LinkTextParser(HTMLParser):
    """Parse HTML to extract visible text and anchor links."""

    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self.title: str = ""

        # Tags to skip entirely (scripts, styles, etc.)
        self._skip_tags = {"script", "style", "noscript", "iframe", "svg", "canvas"}
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        tag_lower = tag.lower()

        if self._skip_depth > 0:
            self._skip_depth += 1
            return

        if tag_lower in self._skip_tags:
            self._skip_depth = 1
            return

        if tag_lower == "title":
            self._in_title = True

        # Extract href from anchors
        if tag_lower == "a":
            for attr_name, attr_value in attrs:
                if attr_name.lower() == "href" and attr_value:
                    self.links.append(attr_value)
                    break

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if self._skip_depth > 0:
            self._skip_depth -= 1
            return

        if tag_lower == "title":
            self._in_title = False

    def handle_data(self, data: str):
        if self._skip_depth > 0:
            return

        if self._in_title:
            self.title += data

        self.text_parts.append(data)

    def get_text(self) -> str:
        """Get all visible text joined by spaces."""
        return " ".join(p.strip() for p in self.text_parts if p.strip())

    def get_links(self) -> List[str]:
        """Get all extracted href links."""
        return self.links


def parse_html(html_content: str) -> Tuple[str, str, List[str]]:
    """Parse HTML content and return (title, visible_text, links).

    Args:
        html_content: Raw HTML string.

    Returns:
        Tuple of (title, visible_text, links)
    """
    parser = LinkTextParser()
    try:
        parser.feed(html_content)
    except Exception:
        # If parsing fails, return what we have
        pass

    title = parser.title.strip()
    text = parser.get_text()
    links = parser.get_links()

    return title, text, links
