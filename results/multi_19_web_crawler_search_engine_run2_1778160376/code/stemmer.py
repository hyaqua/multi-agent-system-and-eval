"""
Simple suffix-stripping stemmer for English words.
"""


def stem(word: str) -> str:
    """Apply iterative suffix-stripping to reduce a word to its stem."""
    original = word
    if len(word) <= 3:
        return word

    # Ordered list of (suffix, replacement) pairs – more specific first
    suffixes = [
        ("ational", "ate"),
        ("tional", "tion"),
        ("enci", "ence"),
        ("anci", "ance"),
        ("izer", "ize"),
        ("abli", "able"),
        ("alli", "al"),
        ("entli", "ent"),
        ("eli", "e"),
        ("ousli", "ous"),
        ("ization", "ize"),
        ("ation", "ate"),
        ("ator", "ate"),
        ("alism", "al"),
        ("iveness", "ive"),
        ("fulness", "ful"),
        ("ousness", "ous"),
        ("aliti", "al"),
        ("iviti", "ive"),
        ("biliti", "ble"),
        ("logi", "log"),
        ("ing", ""),
        ("edly", "ed"),
        ("edly", "e"),
        ("ness", ""),
        ("ment", ""),
        ("ship", ""),
        ("able", ""),
        ("ible", ""),
        ("ful", ""),
        ("ous", ""),
        ("ive", ""),
        ("ize", ""),
        ("ise", ""),
        ("ly", ""),
        ("ed", ""),
        ("en", ""),
        ("er", ""),
        ("est", ""),
        ("es", ""),
        ("s", ""),
        ("'s", ""),
    ]

    changed = True
    while changed:
        changed = False
        if len(word) <= 3:
            break
        for suffix, replacement in suffixes:
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                word = word[: -len(suffix)] + replacement
                changed = True
                break

    return word if word else original
