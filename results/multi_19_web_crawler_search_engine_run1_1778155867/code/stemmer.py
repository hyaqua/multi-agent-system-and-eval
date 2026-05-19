"""Simple suffix-stripping stemmer for English.

A lightweight stemmer that removes common suffixes to improve
search recall. Not as sophisticated as Porter, but sufficient.
"""

# Suffix rules: (suffix, replacement, min_length_after_stem)
# Rules applied in order; first match wins for each step.
STEP1_SUFFIXES = [
    # Plural / third-person singular
    ('sses', 'ss', 2),     # caresses -> caress
    ('ies', 'i', 2),       # ponies -> poni
    ('ss', 'ss', 1),       # caress -> caress (keep)
    ('s', '', 3),          # cats -> cat (but not "us" or "ss")
]

STEP2_SUFFIXES = [
    # Past tense / participle
    ('eed', 'ee', 1),      # agreed -> agree (if stem > 1)
    ('ed', '', 3),         # jumped -> jump
    ('ing', '', 3),        # jumping -> jump
]

STEP3_SUFFIXES = [
    ('ational', 'ate', 1),
    ('tional', 'tion', 1),
    ('enci', 'ence', 1),
    ('anci', 'ance', 1),
    ('izer', 'ize', 1),
    ('abli', 'able', 1),
    ('alli', 'al', 1),
    ('entli', 'ent', 1),
    ('eli', 'e', 1),
    ('ousli', 'ous', 1),
    ('ization', 'ize', 1),
    ('ation', 'ate', 1),
    ('ator', 'ate', 1),
    ('alism', 'al', 1),
    ('iveness', 'ive', 1),
    ('fulness', 'ful', 1),
    ('ousness', 'ous', 1),
    ('aliti', 'al', 1),
    ('iviti', 'ive', 1),
    ('biliti', 'ble', 1),
    ('ment', '', 2),
    ('ness', '', 3),
    ('ful', '', 3),
    ('able', '', 3),
    ('ible', '', 3),
    ('ant', '', 3),
    ('ent', '', 3),
    ('ism', '', 3),
    ('ate', '', 3),
    ('iti', '', 3),
    ('ous', '', 3),
    ('ive', '', 3),
    ('ize', '', 3),
    ('ly', '', 3),
    ('ity', '', 3),
    ('al', '', 3),
    ('er', '', 3),
    ('or', '', 3),
    ('ic', '', 3),
]


def stem(word: str) -> str:
    """Return the stem of a word using simple suffix stripping."""
    if len(word) <= 2:
        return word

    # Step 1: Plurals and simple -s
    word = _apply_rule_list(word, STEP1_SUFFIXES)

    # Step 2: -ed, -ing, -eed
    word = _apply_rule_list(word, STEP2_SUFFIXES)

    # Step 3: More complex suffixes
    word = _apply_rule_list(word, STEP3_SUFFIXES)

    # Remove trailing 'e' if word is long enough
    if word.endswith('e') and len(word) > 3:
        # Check if removing 'e' leaves a valid stem
        word = word[:-1]

    # Remove double consonants at end
    if len(word) > 2 and word[-1] == word[-2] and word[-1] not in 'aeiou':
        if word[-1] not in ('l', 's', 'z'):
            word = word[:-1]

    return word


def _apply_rule_list(word: str, rules: list[tuple[str, str, int]]) -> str:
    """Apply the first matching rule from the list."""
    for suffix, replacement, min_stem in rules:
        if word.endswith(suffix):
            stem_part = word[:-len(suffix)]
            if len(stem_part) >= min_stem:
                return stem_part + replacement
    return word
