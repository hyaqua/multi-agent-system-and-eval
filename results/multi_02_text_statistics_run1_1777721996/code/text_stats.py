#!/usr/bin/env python3
"""Text Statistics Analyzer.

Analyzes a text file and prints a comprehensive statistical report including
word counts, character frequencies, readability scores, and more.

Usage:
    python text_stats.py <file_path>
"""

import sys
import os
import re
import string
from collections import Counter


def parse_args():
    """Parse and return the file path from command-line arguments.

    Returns:
        str: The file path argument.

    Exits with code 1 if no argument is provided.
    """
    if len(sys.argv) < 2:
        print("Error: No file path provided.")
        print("Usage: python text_stats.py <file_path>")
        sys.exit(1)
    return sys.argv[1]


def read_file(path):
    """Read and return the contents of a file.

    Args:
        path: Path to the text file.

    Returns:
        str: File contents.

    Exits with code 1 if the file does not exist or is empty.
    """
    if not os.path.isfile(path):
        print(f"Error: File not found: '{path}'")
        sys.exit(1)

    if os.path.getsize(path) == 0:
        print(f"Error: File is empty: '{path}'")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tokenize_words(text):
    """Extract words from text.

    A word is defined as a sequence of alphanumeric characters (including
    underscores). The text is lowercased before extraction.

    Args:
        text: The full text string.

    Returns:
        list[str]: List of words in order of appearance.
    """
    return re.findall(r"\b\w+\b", text.lower())


def tokenize_sentences(text):
    """Split text into sentences.

    Sentences are delimited by periods, exclamation marks, or question marks
    followed by whitespace. A trailing sentence without punctuation is also
    captured.

    Args:
        text: The full text string.

    Returns:
        list[str]: List of non-empty sentence strings.
    """
    # Split on sentence-ending punctuation followed by whitespace
    raw = re.split(r"(?<=[.!?])\s+", text)
    # Strip and filter out empty strings
    return [s.strip() for s in raw if s.strip()]


def compute_stats(text):
    """Compute all statistics for the given text.

    Args:
        text: The full text string.

    Returns:
        dict: A dictionary containing all computed statistics.
    """
    stats = {}

    # --- Basic counts ---
    words = tokenize_words(text)
    sentences = tokenize_sentences(text)
    lines = text.splitlines()

    stats["char_count_total"] = len(text)
    stats["char_count_no_spaces"] = len(re.sub(r"\s", "", text))
    stats["word_count"] = len(words)
    stats["line_count"] = len(lines)
    stats["sentence_count"] = len(sentences)

    # --- Derived statistics ---
    if stats["word_count"] > 0:
        stats["avg_word_length"] = sum(len(w) for w in words) / stats["word_count"]
    else:
        stats["avg_word_length"] = 0.0

    if stats["sentence_count"] > 0:
        stats["avg_words_per_sentence"] = stats["word_count"] / stats["sentence_count"]
    else:
        stats["avg_words_per_sentence"] = 0.0

    # --- Top 10 most frequent words ---
    word_counter = Counter(words)
    stats["top_words"] = word_counter.most_common(10)

    # --- Character frequency (alphabetic only) ---
    lower_text = text.lower()
    char_freq = {}
    for c in string.ascii_lowercase:
        count = lower_text.count(c)
        if count > 0:
            char_freq[c] = count
    stats["char_freq"] = char_freq

    # --- Longest and shortest words ---
    if words:
        stats["longest_word"] = max(words, key=len)
        stats["shortest_word"] = min(words, key=len)
    else:
        stats["longest_word"] = ""
        stats["shortest_word"] = ""

    # --- Readability score (Automated Readability Index) ---
    if stats["word_count"] > 0 and stats["sentence_count"] > 0:
        ari = (
            4.71 * (stats["char_count_no_spaces"] / stats["word_count"])
            + 0.5 * (stats["word_count"] / stats["sentence_count"])
            - 21.43
        )
        stats["readability_score"] = max(0.0, round(ari, 1))
    else:
        stats["readability_score"] = 0.0

    return stats


def display_report(stats):
    """Print a formatted statistical report.

    Args:
        stats: Dictionary of statistics from compute_stats().
    """
    print("=" * 52)
    print("  TEXT STATISTICS REPORT")
    print("=" * 52)

    # --- Basic Counts ---
    print()
    print("--- BASIC COUNTS ---")
    print(f"  Characters (total):               {stats['char_count_total']:>8}")
    print(f"  Characters (no spaces):            {stats['char_count_no_spaces']:>8}")
    print(f"  Words:                             {stats['word_count']:>8}")
    print(f"  Lines:                             {stats['line_count']:>8}")
    print(f"  Sentences:                         {stats['sentence_count']:>8}")

    # --- Word Statistics ---
    print()
    print("--- WORD STATISTICS ---")
    print(f"  Average word length:               {stats['avg_word_length']:>8.2f}")
    print(f"  Average words per sentence:        {stats['avg_words_per_sentence']:>8.2f}")
    print(f"  Longest word:                      {stats['longest_word']:>8}")
    print(f"  Shortest word:                     {stats['shortest_word']:>8}")

    # --- Top 10 Most Frequent Words ---
    print()
    print("--- TOP 10 MOST FREQUENT WORDS ---")
    if stats["top_words"]:
        # Find max word length for alignment
        max_word_len = max(len(w) for w, _ in stats["top_words"])
        for rank, (word, count) in enumerate(stats["top_words"], 1):
            print(f"  {rank:>2}. {word:<{max_word_len + 2}} {count:>6}")
    else:
        print("  (no words found)")

    # --- Character Frequency Distribution ---
    print()
    print("--- CHARACTER FREQUENCY (alphabetic) ---")
    char_freq = stats["char_freq"]
    if char_freq:
        # Sort by frequency descending, then alphabetically
        sorted_chars = sorted(char_freq.items(), key=lambda x: (-x[1], x[0]))
        # Build a simple horizontal bar chart
        max_count = max(char_freq.values())
        max_bar_width = 30
        for c, count in sorted_chars:
            bar_len = int(count / max_count * max_bar_width) if max_count > 0 else 0
            bar = "#" * bar_len
            print(f"  {c}: {bar:<{max_bar_width}} {count:>6}")
    else:
        print("  (no alphabetic characters found)")

    # --- Readability ---
    print()
    print("--- READABILITY ---")
    print(f"  Automated Readability Index (ARI):  {stats['readability_score']:>8.1f}")
    print()
    print("=" * 52)


def main():
    """Main entry point: parse args, read file, compute stats, display report."""
    filepath = parse_args()
    text = read_file(filepath)
    stats = compute_stats(text)
    display_report(stats)


if __name__ == "__main__":
    main()
