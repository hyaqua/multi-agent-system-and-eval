"""URL normalization, HTML parsing, text processing, stemming, and stopwords."""

import re
import urllib.parse
from html.parser import HTMLParser
from typing import Optional


# ── Stopwords ──────────────────────────────────────────────────────────────

STOPWORDS: set[str] = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'shall', 'can', 'need', 'dare',
    'ought', 'used', 'about', 'against', 'between', 'through', 'during',
    'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off',
    'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
    'when', 'where', 'why', 'how', 'all', 'both', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
    'own', 'same', 'so', 'than', 'too', 'very', 'just', 'because',
    'as', 'until', 'while', 'if', 'this', 'that', 'these', 'those',
    'it', 'its', 'he', 'she', 'they', 'them', 'their', 'his', 'her',
    'my', 'your', 'our', 'we', 'you', 'i', 'me', 'us', 'who', 'whom',
    'which', 'what', 'whose', 'am', 'also', 'into', 'one', 'two',
    'first', 'second', 'get', 'go', 'went', 'come', 'came',
    'know', 'knew', 'take', 'took', 'see', 'saw', 'think', 'thought',
    'say', 'said', 'make', 'made', 'use', 'find', 'found',
    'give', 'gave', 'tell', 'told', 'work', 'still', 'last', 'long',
    'great', 'little', 'right', 'left', 'high', 'low', 'old',
    'young', 'big', 'small', 'large', 'different',
    'part', 'place', 'year', 'group', 'world', 'thing', 'life',
    'hand', 'child', 'man', 'woman', 'case', 'point', 'government',
    'company', 'number', 'problem', 'fact', 'lot', 'others',
    'much', 'many', 'any', 'each', 'every', 'both', 'few',
    'something', 'anything', 'nothing', 'everything', 'someone',
    'anyone', 'everyone', 'like', 'just', 'also', 'way',
    'even', 'well', 'back', 'good', 'bad', 'new', 'old',
    'really', 'very', 'still', 'already', 'yet', 'quite',
    'almost', 'always', 'never', 'often', 'sometimes',
}


# ── URL Utilities ──────────────────────────────────────────────────────────

def normalize_url(base_url: str, href: str) -> Optional[str]:
    """Resolve relative URL, strip fragments, return absolute URL or None."""
    if href is None:
        return None
    href = href.strip()
    if not href:
        return None

    # Skip non-http schemes
    skip_prefixes = ('javascript:', 'mailto:', 'tel:', 'data:', 'ftp:',
                     'file:', 'android:', 'ios:', 'whatsapp:', 'skype:')
    lowered = href.lower()
    if any(lowered.startswith(p) for p in skip_prefixes):
        return None
    if href.startswith('#'):
        return None

    try:
        absolute = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(absolute)

        if parsed.scheme not in ('http', 'https'):
            return None

        # Normalize: lowercase netloc, strip default port, remove fragment
        netloc = parsed.netloc.lower()
        if (parsed.scheme == 'http' and netloc.endswith(':80')):
            netloc = netloc[:-3]
        elif (parsed.scheme == 'https' and netloc.endswith(':443')):
            netloc = netloc[:-4]

        path = parsed.path.rstrip('/') or '/'

        clean = urllib.parse.urlunparse((
            parsed.scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ''  # fragment removed
        ))
        return clean
    except (ValueError, TypeError, UnicodeError):
        return None


def get_domain(url: str) -> str:
    """Extract domain (netloc) from a URL."""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ''


# ── HTML Parsers ───────────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping script/style/noscript/head."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._skip_tags = {'script', 'style', 'noscript', 'meta', 'link',
                           'head', 'title', 'svg', 'canvas', 'iframe',
                           'object', 'embed', 'applet'}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1
        # Add a space for block-level element breaks
        if tag.lower() in {'p', 'br', 'div', 'li', 'h1', 'h2', 'h3', 'h4',
                           'h5', 'h6', 'tr', 'td', 'th', 'section', 'article',
                           'header', 'footer', 'blockquote', 'pre', 'hr'}:
            self.text_parts.append(' ')

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.text_parts.append(data)

    def get_text(self) -> str:
        raw = ''.join(self.text_parts)
        # collapse whitespace
        raw = re.sub(r'\s+', ' ', raw)
        return raw.strip()


class LinkExtractor(HTMLParser):
    """Extract all href links from <a> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == 'a':
            for key, value in attrs:
                if key.lower() == 'href' and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        pass  # no state needed


class TitleExtractor(HTMLParser):
    """Extract the <title> content."""

    def __init__(self) -> None:
        super().__init__()
        self.title: Optional[str] = None
        self._in_title = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == 'title':
            self._in_title = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == 'title':
            self._in_title = False
            self.title = ''.join(self._parts).strip()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._parts.append(data)


# ── Stemmer ────────────────────────────────────────────────────────────────

def _m(w: str) -> int:
    """Measure: count VC sequences."""
    vowels = set('aeiou')
    count = 0
    prev_vowel = False
    for i, ch in enumerate(w):
        is_vowel = ch in vowels or (ch == 'y' and i > 0 and not prev_vowel)
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return count


def _contains_vowel(w: str) -> bool:
    vowels = set('aeiou')
    for i, ch in enumerate(w):
        if ch in vowels:
            return True
        if ch == 'y' and i > 0 and w[i - 1] not in vowels:
            return True
    return False


def _cvc(w: str) -> bool:
    """Check if word ends in CVC where last C is not w, x, y."""
    if len(w) < 3:
        return False
    vowels = set('aeiou')
    last = w[-1]
    if last in 'wxy':
        return False

    def is_vowel(ch, idx):
        if ch in vowels:
            return True
        if ch == 'y' and idx > 0:
            prev = w[idx - 1]
            return prev not in vowels
        return False

    c1 = not is_vowel(w[-3], len(w) - 3)
    v = is_vowel(w[-2], len(w) - 2)
    c2 = not is_vowel(w[-1], len(w) - 1)
    return c1 and v and c2


def stem(word: str) -> str:
    """Porter stemming algorithm (simplified but substantially complete)."""
    if len(word) <= 2:
        return word

    w = word.lower()

    # Step 1a
    if w.endswith('sses'):
        w = w[:-2]  # sses -> ss
    elif w.endswith('ies'):
        w = w[:-2]  # ies -> i
    elif w.endswith('ss'):
        pass
    elif w.endswith('s') and len(w) > 2:
        w = w[:-1]  # s -> (remove)

    # Step 1b
    changed = False
    if w.endswith('eed'):
        if _m(w[:-3]) > 0:
            w = w[:-1]  # eed -> ee
    elif w.endswith('ed'):
        stem_part = w[:-2]
        if _contains_vowel(stem_part):
            w = stem_part
            changed = True
    elif w.endswith('ing'):
        stem_part = w[:-3]
        if _contains_vowel(stem_part):
            w = stem_part
            changed = True

    if changed:
        if w.endswith(('at', 'bl', 'iz')):
            w += 'e'
        elif len(w) >= 2 and w[-1] == w[-2] and w[-1] not in 'aeiouls':
            w = w[:-1]
        elif _m(w) == 1 and _cvc(w):
            w += 'e'

    # Step 1c
    if w.endswith('y') and len(w) > 2:
        stem_part = w[:-1]
        if _contains_vowel(stem_part):
            w = w[:-1] + 'i'

    # Step 2
    step2_map = [
        ('ational', 'ate'), ('tional', 'tion'), ('enci', 'ence'),
        ('anci', 'ance'), ('izer', 'ize'), ('abli', 'able'),
        ('alli', 'al'), ('entli', 'ent'), ('eli', 'e'),
        ('ousli', 'ous'), ('ization', 'ize'), ('ation', 'ate'),
        ('ator', 'ate'), ('alism', 'al'), ('iveness', 'ive'),
        ('fulness', 'ful'), ('ousness', 'ous'), ('aliti', 'al'),
        ('iviti', 'ive'), ('biliti', 'ble'),
    ]
    for suffix, repl in step2_map:
        if w.endswith(suffix):
            stem_part = w[:-len(suffix)]
            if _m(stem_part) > 0:
                w = stem_part + repl
            break

    # Step 3
    step3_map = [
        ('icate', 'ic'), ('ative', ''), ('alize', 'al'),
        ('iciti', 'ic'), ('ical', 'ic'), ('ful', ''),
        ('ness', ''),
    ]
    for suffix, repl in step3_map:
        if w.endswith(suffix):
            stem_part = w[:-len(suffix)]
            if _m(stem_part) > 0:
                w = stem_part + repl
            break

    # Step 4
    step4_suffixes = [
        'ement', 'ance', 'ence', 'able', 'ible', 'ment',
        'ant', 'ent', 'ism', 'ate', 'iti', 'ous', 'ive', 'ize'
    ]
    for suffix in step4_suffixes:
        if w.endswith(suffix):
            stem_part = w[:-len(suffix)]
            if _m(stem_part) > 1:
                w = stem_part
            break

    if w.endswith('ion'):
        stem_part = w[:-3]
        if len(stem_part) >= 2 and stem_part[-1] in 'st' and _m(stem_part) > 1:
            w = stem_part

    # Step 5a
    if w.endswith('e'):
        stem_part = w[:-1]
        m_val = _m(stem_part)
        if m_val > 1 or (m_val == 1 and not _cvc(stem_part)):
            w = stem_part

    # Step 5b
    if w.endswith('ll') and _m(w) > 1:
        w = w[:-1]

    return w if len(w) >= 1 else word.lower()


# ── Tokenizer ──────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Full tokenization pipeline: lowercase, strip punct, stopwords, stem."""
    text = text.lower()
    # Extract alphabetic tokens only
    tokens = re.findall(r'[a-z]{2,}', text)
    # Filter stopwords
    tokens = [t for t in tokens if t not in STOPWORDS]
    # Stem
    tokens = [stem(t) for t in tokens]
    return tokens


def make_snippet(text: str, query_tokens: list[str], window: int = 30) -> str:
    """Extract a snippet around the first occurrence of any query token."""
    if not query_tokens:
        # Return beginning of text
        words = text.split()
        return ' '.join(words[:window * 2])

    text_lower = text.lower()
    words = text.split()
    best_pos = -1
    best_token = ''

    for qt in query_tokens:
        # Find approximate position
        idx = text_lower.find(qt.lower())
        if idx != -1 and (best_pos == -1 or idx < best_pos):
            # Count words before this position
            before = text[:idx]
            word_count = len(before.split())
            best_pos = word_count
            best_token = qt.lower()

    if best_pos == -1:
        return ' '.join(words[:window * 2])

    start = max(0, best_pos - window)
    end = min(len(words), best_pos + window)
    snippet_words = words[start:end]

    # Bold the query tokens
    result_parts: list[str] = []
    for w in snippet_words:
        if stem(w.lower()) in query_tokens:
            result_parts.append(f'<b>{w}</b>')
        else:
            result_parts.append(w)

    prefix = '...' if start > 0 else ''
    suffix = '...' if end < len(words) else ''
    return prefix + ' '.join(result_parts) + suffix
