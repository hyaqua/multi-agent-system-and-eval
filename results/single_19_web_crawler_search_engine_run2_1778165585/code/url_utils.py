"""URL normalization, resolution, and deduplication utilities."""

import urllib.parse


def normalize_url(url: str, base_url: str = "") -> str:
    """Normalize a URL: resolve relative URLs, strip fragments, lowercase scheme/host.

    Returns the canonical URL string, or empty string if invalid.
    """
    if not url or not url.strip():
        return ""

    url = url.strip()

    # Resolve relative URLs against base
    if base_url:
        try:
            url = urllib.parse.urljoin(base_url, url)
        except Exception:
            return ""

    # Parse the URL
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return ""

    # Must have scheme and netloc
    if not parsed.scheme or not parsed.netloc:
        return ""

    # Only http and https
    if parsed.scheme not in ("http", "https"):
        return ""

    # Normalize scheme and host to lowercase
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Normalize path: resolve /../ and /./, remove trailing slash for non-root
    path = urllib.parse.unquote(parsed.path)
    # Collapse multiple slashes
    while "//" in path:
        path = path.replace("//", "/")
    # Resolve . and ..
    segments = []
    for seg in path.split("/"):
        if seg == "." or seg == "":
            continue
        if seg == "..":
            if segments:
                segments.pop()
        else:
            segments.append(seg)
    path = "/" + "/".join(segments)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    # Rebuild URL without fragment
    normalized = urllib.parse.urlunparse(
        (scheme, netloc, path, parsed.params, parsed.query, "")
    )

    return normalized


def get_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs belong to the same domain."""
    return get_domain(url1) == get_domain(url2)


def is_in_scope(url: str, seed_domains: set) -> bool:
    """Check if a URL's domain is in the set of seed domains."""
    domain = get_domain(url)
    return domain in seed_domains
