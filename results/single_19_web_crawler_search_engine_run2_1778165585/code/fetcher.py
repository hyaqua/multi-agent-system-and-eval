"""URL fetcher using urllib with configurable timeout and error handling."""

import urllib.request
import urllib.error
import socket
import ssl
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Common content types that are HTML
HTML_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
}


class FetchResult:
    """Result of a URL fetch."""

    def __init__(
        self,
        url: str,
        content: str = "",
        content_type: str = "",
        status: int = 0,
        error: str = "",
        final_url: str = "",
    ):
        self.url = url
        self.content = content
        self.content_type = content_type
        self.status = status
        self.error = error
        self.final_url = final_url

    @property
    def is_html(self) -> bool:
        """Check if the content is HTML."""
        if not self.content_type:
            return True  # Assume HTML if no content type
        main_type = self.content_type.split(";")[0].strip().lower()
        return main_type in HTML_CONTENT_TYPES

    @property
    def success(self) -> bool:
        return self.status > 0 and not self.error


def fetch_url(
    url: str,
    timeout: float = 10.0,
    user_agent: str = "SimpleCrawler/1.0",
    max_size: int = 10 * 1024 * 1024,  # 10 MB max
) -> FetchResult:
    """Fetch a URL and return the result."""
    result = FetchResult(url=url)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        # Create SSL context that doesn't verify (for broader compatibility)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(
            req, timeout=timeout, context=ctx
        ) as resp:
            result.status = resp.status
            result.final_url = resp.geturl()
            result.content_type = resp.headers.get("Content-Type", "")

            # Check content type
            if not result.is_html:
                result.error = f"Skipped non-HTML content: {result.content_type}"
                return result

            # Read with size limit
            content_bytes = resp.read(max_size)
            # Detect encoding
            encoding = "utf-8"
            # Try to get charset from content-type
            ct = result.content_type.lower()
            if "charset=" in ct:
                charset_part = ct.split("charset=")[-1].split(";")[0].strip()
                if charset_part:
                    encoding = charset_part

            try:
                result.content = content_bytes.decode(encoding, errors="replace")
            except (UnicodeDecodeError, LookupError):
                result.content = content_bytes.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as e:
        result.status = e.code
        result.error = f"HTTP {e.code}: {e.reason}"
        logger.error(f"Error fetching {url}: HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        result.error = f"URL Error: {e.reason}"
        logger.error(f"Error fetching {url}: {e.reason}")
    except socket.timeout:
        result.error = "Connection timeout"
        logger.error(f"Error fetching {url}: Connection timeout")
    except ssl.SSLError as e:
        result.error = f"SSL Error: {e}"
        logger.error(f"Error fetching {url}: SSL error")
    except Exception as e:
        result.error = f"Error: {e}"
        logger.error(f"Error fetching {url}: {e}")

    return result
