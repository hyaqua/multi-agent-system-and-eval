"""URL normalization, deduplication, and resolution utilities."""

import urllib.parse


class URLUtils:
    """Handles URL normalization, deduplication, and relative resolution."""

    def __init__(self):
        self._visited: set[str] = set()
        self._lock = __import__('threading').Lock()

    def normalize(self, url: str, base_url: str | None = None) -> str | None:
        """
        Normalize a URL by resolving relatives, stripping fragments,
        removing trailing slashes, and lowercasing scheme/host.
        Returns None if the URL is invalid or not http/https.
        """
        # Resolve relative URLs
        if base_url:
            full_url = urllib.parse.urljoin(base_url, url)
        else:
            full_url = url

        # Strip fragment
        full_url, _ = urllib.parse.urldefrag(full_url)

        # Parse
        parsed = urllib.parse.urlparse(full_url)

        # Only accept http and https
        if parsed.scheme not in ('http', 'https'):
            return None

        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove default ports
        if ':' in netloc:
            host, port = netloc.rsplit(':', 1)
            if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
                netloc = host

        # Normalize path: remove trailing slash unless it's just "/"
        path = parsed.path
        if len(path) > 1 and path.endswith('/'):
            path = path.rstrip('/')

        # Remove dot segments
        path = _remove_dot_segments(path)

        # Rebuild URL
        normalized = urllib.parse.urlunparse(
            (scheme, netloc, path, parsed.params, parsed.query, '')
        )

        return normalized

    def is_visited(self, url: str) -> bool:
        """Check if URL has already been visited (thread-safe)."""
        with self._lock:
            return url in self._visited

    def mark_visited(self, url: str) -> bool:
        """
        Mark a URL as visited. Returns True if it was newly added,
        False if it was already visited (thread-safe).
        """
        with self._lock:
            if url in self._visited:
                return False
            self._visited.add(url)
            return True

    @property
    def visited_count(self) -> int:
        with self._lock:
            return len(self._visited)

    def extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()

    def extract_domains_from_links(self, links: list[str], base_url: str) -> set[str]:
        """Extract and normalize all unique domains from a list of links."""
        domains: set[str] = set()
        for link in links:
            normalized = self.normalize(link, base_url)
            if normalized:
                domains.add(self.extract_domain(normalized))
        return domains


def _remove_dot_segments(path: str) -> str:
    """Remove . and .. segments from a URL path."""
    segments = path.split('/')
    result: list[str] = []
    for seg in segments:
        if seg == '.' or seg == '':
            continue
        elif seg == '..':
            if result:
                result.pop()
        else:
            result.append(seg)
    return '/' + '/'.join(result) if result else '/'
