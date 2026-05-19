"""URL fetcher using urllib with error handling and content-type checking."""

import urllib.request
import urllib.error
import socket
import ssl


DEFAULT_TIMEOUT = 10
USER_AGENT = 'SimpleCrawler/1.0'


class Fetcher:
    """Fetches URLs and returns their content, handling various errors."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._error_callback = None

    def set_error_callback(self, callback):
        """Set a callback for logging errors: callback(url, error_message)."""
        self._error_callback = callback

    def fetch(self, url: str) -> tuple[str | None, str | None]:
        """
        Fetch a URL and return (html_content, content_type).

        Returns (None, None) on failure.
        Only returns content if Content-Type indicates text/html.
        """
        req = urllib.request.Request(
            url,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,*/*'},
        )

        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            self._log_error(url, f'HTTP {e.code}: {e.reason}')
            return None, None
        except urllib.error.URLError as e:
            self._log_error(url, f'URL Error: {e.reason}')
            return None, None
        except socket.timeout:
            self._log_error(url, 'Timeout')
            return None, None
        except ssl.SSLError as e:
            self._log_error(url, f'SSL Error: {e}')
            return None, None
        except ConnectionError as e:
            self._log_error(url, f'Connection Error: {e}')
            return None, None
        except Exception as e:
            self._log_error(url, f'Unexpected Error: {e}')
            return None, None

        try:
            content_type = response.headers.get('Content-Type', '')
            # Check if it's HTML
            if 'text/html' not in content_type.lower():
                response.close()
                return None, None

            raw = response.read()
            response.close()

            # Try to decode
            html = self._decode(raw, response.headers)

            return html, content_type

        except Exception as e:
            self._log_error(url, f'Read Error: {e}')
            try:
                response.close()
            except Exception:
                pass
            return None, None

    def _decode(self, raw: bytes, headers) -> str:
        """Decode bytes to string using charset from headers or default."""
        charset = 'utf-8'
        content_type = headers.get('Content-Type', '')
        if 'charset=' in content_type.lower():
            parts = content_type.lower().split('charset=')
            if len(parts) > 1:
                charset = parts[1].split(';')[0].strip()

        # Try to decode with detected charset
        try:
            return raw.decode(charset)
        except (UnicodeDecodeError, LookupError):
            # Fall back to utf-8 with replacement
            return raw.decode('utf-8', errors='replace')

    def _log_error(self, url: str, message: str):
        """Log an error through the callback or print."""
        if self._error_callback:
            self._error_callback(url, message)
        else:
            print(f'[ERR] Failed to fetch {url}: {message}')
