#!/usr/bin/env python3
"""
Text Statistics Analyzer

Analyzes a text file and displays various statistics:
- Character counts (total and without whitespace)
- Word count
- Line count
- Sentence count
- Average word length
- Average words per sentence
- Top 10 most frequent words
- Character frequency distribution
- Longest and shortest words
- Readability score (Automated Readability Index)

Usage:
    python text_stats.py <file_path>
"""

import sys
import os
import re
from collections import Counter
import string


def get_words(text: str) -> list[str]:
    """Extract alphabetic word tokens from text (lowercase)."""
    return re.findall(r'[a-zA-Z]+', text.lower())


def get_char_count(text: str) -> int:
    """Total character count."""
    return len(text)


def get_char_count_no_whitespace(text: str) -> int:
    """Character count excluding whitespace."""
    return sum(1 for c in text if not c.isspace())


def get_word_count(words: list[str]) -> int:
    """Number of word tokens."""
    return len(words)


def get_line_count(text: str) -> int:
    """Number of lines in the text."""
    return len(text.splitlines())


def get_sentence_count(text: str) -> int:
    """Number of sentences (split by . ! ?)."""
    sentences = re.split(r'[.!?]+', text)
    return len([s for s in sentences if s.strip()])


def get_avg_word_length(words: list[str]) -> float:
    """Average word length. Returns 0.0 if no words."""
    if not words:
        return 0.0
    return sum(len(w) for w in words) / len(words)


def get_avg_words_per_sentence(word_count: int, sentence_count: int) -> float:
    """Average words per sentence. Returns 0.0 if no sentences."""
    if sentence_count == 0:
        return 0.0
    return word_count / sentence_count


def get_top_words(words: list[str], n: int = 10) -> list[tuple[str, int]]:
    """Top N most frequent words."""
    return Counter(words).most_common(n)


def get_char_frequency(words: list[str]) -> dict[str, int]:
    """Character frequency distribution for alphabetic characters a-z."""
    freq: dict[str, int] = {}
    for word in words:
        for ch in word:
            if ch.isalpha() and ch.isascii():
                freq[ch] = freq.get(ch, 0) + 1
    return freq


def get_longest_words(words: list[str]) -> list[str]:
    """All words tied for longest length."""
    if not words:
        return []
    max_len = max(len(w) for w in words)
    return sorted({w for w in words if len(w) == max_len})


def get_shortest_words(words: list[str]) -> list[str]:
    """All words tied for shortest length."""
    if not words:
        return []
    min_len = min(len(w) for w in words)
    return sorted({w for w in words if len(w) == min_len})


def get_readability_score(char_no_spaces: int, word_count: int,
                          sentence_count: int) -> float | None:
    """
    Automated Readability Index (ARI):
        ARI = 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43

    Returns None if word_count or sentence_count is 0.
    """
    if word_count == 0 or sentence_count == 0:
        return None
    ari = 4.71 * (char_no_spaces / word_count) + \
          0.5 * (word_count / sentence_count) - 21.43
    return round(ari, 1)


def format_section_header(title: str) -> str:
    """Return a formatted section header."""
    return f"\n{'=' * 50}\n== {title} ==\n{'=' * 50}"


def print_report(text: str) -> None:
    """Compute all statistics and print the formatted report."""
    # Pre-compute all values
    words = get_words(text)
    total_chars = get_char_count(text)
    chars_no_ws = get_char_count_no_whitespace(text)
    word_count = get_word_count(words)
    line_count = get_line_count(text)
    sentence_count = get_sentence_count(text)
    avg_wl = get_avg_word_length(words)
    avg_wps = get_avg_words_per_sentence(word_count, sentence_count)
    top_words = get_top_words(words)
    char_freq = get_char_frequency(words)
    longest = get_longest_words(words)
    shortest = get_shortest_words(words)
    readability = get_readability_score(chars_no_ws, word_count, sentence_count)

    # Basic Counts
    print(format_section_header("Basic Counts"))
    print(f"{'Total characters (incl. whitespace):':<38}{total_chars}")
    print(f"{'Total characters (no whitespace):':<38}{chars_no_ws}")
    print(f"{'Total words:':<38}{word_count}")
    print(f"{'Total lines:':<38}{line_count}")
    print(f"{'Total sentences:':<38}{sentence_count}")

    # Averages
    print(format_section_header("Averages"))
    print(f"{'Average word length:':<38}{avg_wl:.2f}")
    print(f"{'Average words per sentence:':<38}{avg_wps:.2f}")

    # Word Frequency
    print(format_section_header("Top 10 Most Frequent Words"))
    for i, (word, count) in enumerate(top_words, 1):
        print(f"  {i:>2}. {word:<20}{count}")

    # Character Frequency
    print(format_section_header("Character Frequency (a-z)"))
    if char_freq:
        sorted_freq = sorted(char_freq.items(), key=lambda x: (-x[1], x[0]))
        max_count = max(char_freq.values())
        for ch, count in sorted_freq:
            bar_len = int(40 * count / max_count)
            bar = '█' * bar_len
            print(f"  {ch}: {bar} {count}")
    else:
        print("  (no alphabetic characters found)")

    # Longest / Shortest Words
    print(format_section_header("Longest & Shortest Words"))
    if longest:
        if len(longest) == 1:
            print(f"{'Longest word:':<38}{longest[0]} ({len(longest[0])} chars)")
        else:
            print(f"Longest words ({len(longest[0])} chars):")
            for w in longest:
                print(f"  - {w}")
    else:
        print(f"{'Longest word:':<38}(none)")

    if shortest:
        if len(shortest) == 1:
            print(f"{'Shortest word:':<38}{shortest[0]} ({len(shortest[0])} chars)")
        else:
            print(f"Shortest words ({len(shortest[0])} chars):")
            for w in shortest:
                print(f"  - {w}")
    else:
        print(f"{'Shortest word:':<38}(none)")

    # Readability
    print(format_section_header("Readability Score"))
    if readability is not None:
        print(f"{'Automated Readability Index (ARI):':<38}{readability}")
        # Approximate grade level based on ARI
        grade = min(max(round(readability), 1), 14)
        print(f"{'Estimated grade level:':<38}{grade}")
    else:
        print(f"{'Automated Readability Index (ARI):':<38}N/A")
        print("  (cannot compute — need at least one word and one sentence)")

    print()


def main() -> None:
    """Entry point: parse arguments, validate, and run analysis."""
    if len(sys.argv) != 2:
        print("Usage: python text_stats.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Error: file not found — '{file_path}'")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"Error: could not read file — {e}")
        sys.exit(1)

    if not text.strip():
        print("Error: file is empty (no non-whitespace content).")
        sys.exit(1)

    print_report(text)


if __name__ == '__main__':
    main()
