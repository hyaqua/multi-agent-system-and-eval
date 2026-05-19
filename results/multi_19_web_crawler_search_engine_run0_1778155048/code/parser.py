"""HTML parser to extract visible text and hyperlinks."""

from html.parser import HTMLParser


class HTMLContentParser(HTMLParser):
    """Extract visible text, title, and hyperlinks from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ''
        self.text_parts = []
        self.links = []
        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._skip_tags = {'script', 'style', 'noscript', 'iframe', 'svg', 'canvas'}

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in self._skip_tags:
            if tag_lower == 'script':
                self._in_script = True
            elif tag_lower == 'style':
                self._in_style = True

        if tag_lower == 'title':
            self._in_title = True

        if tag_lower == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == 'title':
            self._in_title = False
        elif tag_lower == 'script':
            self._in_script = False
        elif tag_lower == 'style':
            self._in_style = False

    def handle_data(self, data):
        if self._in_script or self._in_style:
            return
        if self._in_title:
            self.title += data.strip()
        else:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self):
        """Return visible text as a single string."""
        return ' '.join(self.text_parts)

    def get_title(self):
        """Return the page title."""
        return self.title.strip() if self.title else ''

    def get_links(self):
        """Return extracted hyperlinks."""
        return self.links

    def parse_html(self, html_content):
        """Parse HTML content and extract text, title, links."""
        self.reset()
        self.title = ''
        self.text_parts = []
        self.links = []
        self._in_title = False
        self._in_script = False
        self._in_style = False

        try:
            self.feed(html_content)
        except Exception:
            # Robust parsing - just return what we have
            pass

        return {
            'title': self.get_title(),
            'text': self.get_text(),
            'links': self.get_links()
        }
