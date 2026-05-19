"""
HTML parser that extracts visible text and anchor href links.
Uses html.parser from the standard library.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re


class LinkTextExtractor(HTMLParser):
    """Extracts visible text, title, and links from HTML."""
    
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.text_parts = []
        self.links = []
        
        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._skip_tags = {'script', 'style', 'noscript', 'iframe', 'svg', 'canvas', 'code', 'pre'}
        self._current_skip = None
    
    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attrs_dict = dict(attrs)
        
        if tag_lower == 'title':
            self._in_title = True
        elif tag_lower in self._skip_tags:
            self._current_skip = tag_lower
        elif tag_lower == 'a':
            href = attrs_dict.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                absolute_url = urljoin(self.base_url, href)
                self.links.append(absolute_url)
        elif tag_lower == 'br':
            self.text_parts.append(' ')
        elif tag_lower in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'td', 'th', 'section', 'article', 'header', 'footer'):
            self.text_parts.append(' ')
    
    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == 'title':
            self._in_title = False
        elif tag_lower == self._current_skip:
            self._current_skip = None
        elif tag_lower in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'td', 'th', 'section', 'article', 'header', 'footer', 'br'):
            self.text_parts.append(' ')
    
    def handle_data(self, data):
        if self._current_skip:
            return
        if self._in_title:
            self.title += data
        else:
            self.text_parts.append(data)
    
    def get_text(self):
        """Get the visible text content."""
        text = ''.join(self.text_parts)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def get_title(self):
        """Get the page title."""
        return self.title.strip()
    
    def get_links(self):
        """Get extracted and normalized links."""
        # Normalize: remove fragments, strip trailing slashes in some cases
        normalized = []
        for link in self.links:
            parsed = urlparse(link)
            # Strip fragment
            clean = parsed._replace(fragment='').geturl()
            normalized.append(clean)
        return normalized


def parse_html(html_content, base_url):
    """Parse HTML content and return (text, title, links)."""
    parser = LinkTextExtractor(base_url)
    try:
        parser.feed(html_content)
    except Exception:
        pass
    
    return parser.get_text(), parser.get_title(), parser.get_links()
