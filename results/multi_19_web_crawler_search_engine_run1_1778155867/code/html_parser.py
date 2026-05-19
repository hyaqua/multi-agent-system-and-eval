"""HTML parser for extracting visible text and anchor links."""

from html.parser import HTMLParser


class TextExtractingParser(HTMLParser):
    """Extracts visible text and all <a href> links from HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._skip_tags: set[str] = {'script', 'style', 'noscript'}
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower in self._skip_tags:
            self._skip_depth += 1

        if tag_lower == 'a':
            for name, value in attrs:
                if name.lower() == 'href' and value:
                    self.links.append(value)
                    break

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text)

    def get_text(self) -> str:
        """Return all extracted visible text as a single string."""
        return ' '.join(self.text_parts)

    def get_links(self) -> list[str]:
        """Return all extracted href links."""
        return self.links


class TitleExtractingParser(HTMLParser):
    """Extracts the <title> tag content from HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title: str = ''
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() == 'title':
            self._in_title = True

    def handle_endtag(self, tag: str):
        if tag.lower() == 'title':
            self._in_title = False

    def handle_data(self, data: str):
        if self._in_title:
            self.title += data

    def get_title(self) -> str:
        """Return the page title, trimmed."""
        return self.title.strip()


def extract_text_and_links(html: str) -> tuple[str, list[str], str]:
    """
    Parse HTML and return (visible_text, links, title).

    Args:
        html: Raw HTML string.

    Returns:
        Tuple of (text content, list of href links, page title).
    """
    text_parser = TextExtractingParser()
    title_parser = TitleExtractingParser()

    try:
        text_parser.feed(html)
        title_parser.feed(html)
    except Exception as e:
        print(f'HTML parse error: {e}', file=__import__('sys').stderr)

    text_parser.close()
    title_parser.close()

    return (
        text_parser.get_text(),
        text_parser.get_links(),
        title_parser.get_title(),
    )
