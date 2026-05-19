"""
Simple Porter-style stemmer for English text.
Implements steps 1a, 1b, 1c, 2, 3, 4, 5a, 5b of the Porter algorithm.
"""

import re

VOWELS = set('aeiou')

def is_vowel(ch):
    return ch.lower() in VOWELS

def measure(stem):
    """Count VC sequences (measure m)."""
    count = 0
    # Find pattern V C
    i = 0
    while i < len(stem):
        if is_vowel(stem[i]):
            # Found vowel, look for consonant sequence after
            i += 1
            while i < len(stem) and is_vowel(stem[i]):
                i += 1
            if i < len(stem):
                count += 1
                # Skip consonant sequence
                while i < len(stem) and not is_vowel(stem[i]) and stem[i] != 'y':
                    i += 1
            else:
                break
        else:
            i += 1
    return count

def contains_vowel(stem):
    for ch in stem:
        if is_vowel(ch):
            return True
    return False

def ends_with_double_consonant(stem):
    if len(stem) >= 2:
        ch = stem[-1]
        if not is_vowel(ch) and ch not in 'wxy' and ch == stem[-2]:
            return True
    return False

def ends_with_cvc(stem):
    """Check if stem ends with CVC where last C is not w, x, or y."""
    if len(stem) >= 3:
        c3 = stem[-1]
        c2 = stem[-2]
        c1 = stem[-3]
        if (not is_vowel(c3) and c3 not in 'wxy' and
            is_vowel(c2) and
            not is_vowel(c1) and c1 not in 'wxy' and c1 != c2):
            return True
    return False


def step1a(word):
    """Step 1a: Handle plurals and past participles."""
    if word.endswith('sses'):
        word = word[:-2]  # sses -> ss
    elif word.endswith('ies'):
        word = word[:-2]  # ies -> i
    elif word.endswith('ss'):
        pass  # ss -> ss
    elif word.endswith('s'):
        word = word[:-1]  # s -> ''
    return word


def step1b(word):
    """Step 1b: Handle -ed and -ing."""
    changed = False
    if word.endswith('eed'):
        # If measure > 0, replace with ee
        stem = word[:-3]
        if measure(stem) > 0:
            word = stem + 'ee'
    elif word.endswith('ed'):
        stem = word[:-2]
        if contains_vowel(stem):
            word = stem
            changed = True
    elif word.endswith('ing'):
        stem = word[:-3]
        if contains_vowel(stem):
            word = stem
            changed = True
    
    if changed:
        # Handle doubling and special cases
        if word.endswith('at') or word.endswith('bl') or word.endswith('iz'):
            word += 'e'
        elif ends_with_double_consonant(word) and not word.endswith(('l', 's', 'z')):
            word = word[:-1]
        elif measure(word) == 1 and ends_with_cvc(word):
            word += 'e'
    
    return word


def step1c(word):
    """Step 1c: Handle y -> i when preceded by consonant."""
    if word.endswith('y') and len(word) > 1:
        if not is_vowel(word[-2]):
            word = word[:-1] + 'i'
    return word


def step2(word):
    """Step 2: Handle various suffixes."""
    suffixes = [
        ('ational', 'ate'), ('tional', 'tion'), ('enci', 'ence'),
        ('anci', 'ance'), ('izer', 'ize'), ('abli', 'able'),
        ('alli', 'al'), ('entli', 'ent'), ('eli', 'e'),
        ('ousli', 'ous'), ('ization', 'ize'), ('ation', 'ate'),
        ('ator', 'ate'), ('alism', 'al'), ('iveness', 'ive'),
        ('fulness', 'ful'), ('ousness', 'ous'), ('aliti', 'al'),
        ('iviti', 'ive'), ('biliti', 'ble'),
    ]
    for suffix, replacement in suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if measure(stem) > 0:
                word = stem + replacement
            break
    return word


def step3(word):
    """Step 3: Handle -ic-, -full, -ness etc."""
    suffixes = [
        ('icate', 'ic'), ('ative', ''), ('alize', 'al'),
        ('iciti', 'ic'), ('ical', 'ic'), ('ful', ''),
        ('ness', ''),
    ]
    for suffix, replacement in suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if measure(stem) > 0:
                word = stem + replacement
            break
    return word


def step4(word):
    """Step 4: Remove -ance, -ence, -able, -ible, etc."""
    suffixes = [
        'ance', 'ence', 'able', 'ible', 'ment', 'ment',
        'ent', 'ant', 'ism', 'ate', 'iti', 'ous',
        'ive', 'ize', 'ion', 'al', 'er', 'ic',
    ]
    # Remove duplicates
    suffixes = sorted(set(suffixes), key=len, reverse=True)
    for suffix in suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if measure(stem) > 1:
                word = stem
            break
    return word


def step5a(word):
    """Step 5a: Remove final e."""
    if word.endswith('e'):
        stem = word[:-1]
        m = measure(stem)
        if m > 1:
            word = stem
        elif m == 1 and not ends_with_cvc(stem):
            word = stem
    return word


def step5b(word):
    """Step 5b: Remove double l at end if measure > 1."""
    if word.endswith('ll') and measure(word) > 1:
        word = word[:-1]
    return word


def stem(word):
    """Apply the Porter stemming algorithm to a word."""
    if len(word) <= 2:
        return word.lower()
    
    word = word.lower()
    
    # Skip if word contains digits
    if any(ch.isdigit() for ch in word):
        return word
    
    word = step1a(word)
    word = step1b(word)
    word = step1c(word)
    word = step2(word)
    word = step3(word)
    word = step4(word)
    word = step5a(word)
    word = step5b(word)
    
    return word
