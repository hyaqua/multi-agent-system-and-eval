#!/usr/bin/env python3
"""Text Statistics Analyzer - A command-line tool for analyzing text files.

Reads a text file and produces a detailed statistical report including
character counts, word counts, sentence analysis, frequency distributions,
and a readability score.
"""

import argparse
import collections
import math
import os
import re
import string
import sys
from typing import List, Tuple, Dict


# ──────────────────────────────────────────────────────────────────────
# Core Analysis Functions
# ──────────────────────────────────────────────────────────────────────

def read_file(filepath: str) -> str:
    """Read the contents of a file and return as a string.

    Args:
        filepath: Path to the text file.

    Returns:
        The file contents as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: '{filepath}'")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.strip():
        raise ValueError(f"File is empty: '{filepath}'")

    return content


def count_characters(text: str) -> Tuple[int, int]:
    """Count characters in text, with and without whitespace.

    Args:
        text: The text to analyze.

    Returns:
        Tuple of (total_chars, chars_without_whitespace).
    """
    total = len(text)
    without_ws = sum(1 for c in text if not c.isspace())
    return total, without_ws


def count_words(text: str) -> List[str]:
    """Extract words from text.

    A word is defined as a sequence of alphabetic characters or
    apostrophe-containing contractions.

    Args:
        text: The text to analyze.

    Returns:
        List of words in order of appearance.
    """
    # Match sequences of alphabetic characters, including contractions like "don't"
    words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", text)
    return words


def count_lines(text: str) -> int:
    """Count the number of lines in the text.

    Args:
        text: The text to analyze.

    Returns:
        Number of lines.
    """
    if not text:
        return 0
    # Count newlines; if the text doesn't end with a newline, we still count
    # the last line.
    lines = text.split('\n')
    return len(lines)


def count_sentences(text: str) -> int:
    """Count sentences by detecting sentence-ending punctuation.

    A sentence boundary is detected at '.', '!', '?' followed by
    whitespace or end-of-string. Handles abbreviations with a simple
    heuristic (single-letter followed by period is not a boundary).

    Args:
        text: The text to analyze.

    Returns:
        Number of sentences.
    """
    # Replace common abbreviations to avoid false positives
    # This is a simplified approach
    # Match sentence-ending punctuation: . ! ? followed by space/end/quote+space
    sentence_ends = re.findall(r'[.!?](?:\s+|$)', text)

    # Filter out some false positives: e.g., "Mr.", "Mrs.", "Dr.", "i.e.", "e.g.", "etc."
    # Also filter out decimal numbers like "3.14"
    # A more robust approach: check context
    true_sentence_count = 0
    for match in re.finditer(r'[.!?](?:\s+|$)', text):
        pos = match.start()
        punct = match.group()[0]

        # Get context before the punctuation
        before = text[max(0, pos-10):pos]

        # Skip if it looks like an abbreviation (e.g. Mr., Mrs., Dr.)
        # Check if the preceding word is a common abbreviation
        abbr_pattern = re.search(
            r'\b(?:Mr|Mrs|Ms|Dr|Prof|Rev|Hon|St|Sr|Jr|Capt|Col|Gen|Lt|Maj|Sgt|Gov|Rep|Sen|Mt|Ave|Blvd|Rd|Inc|Ltd|Co|Corp|etc|vs|viz|i\.e|e\.g|al|et|dept|est|approx|apt|dept|vol|ed)\.?$',
            before, re.IGNORECASE
        )

        # Skip if it looks like a number with decimal
        decimal_pattern = re.search(r'\d\.\d?$', before)

        if abbr_pattern or decimal_pattern:
            continue

        true_sentence_count += 1

    return max(true_sentence_count, 1)  # At least 1 sentence


def average_word_length(words: List[str]) -> float:
    """Calculate average word length in characters.

    Args:
        words: List of words.

    Returns:
        Average word length.
    """
    if not words:
        return 0.0
    total_length = sum(len(w) for w in words)
    return total_length / len(words)


def average_words_per_sentence(words: List[str], sentence_count: int) -> float:
    """Calculate average words per sentence.

    Args:
        words: List of words.
        sentence_count: Number of sentences.

    Returns:
        Average words per sentence.
    """
    if sentence_count == 0:
        return 0.0
    return len(words) / sentence_count


def top_frequent_words(words: List[str], n: int = 10) -> List[Tuple[str, int]]:
    """Find the top N most frequent words.

    Args:
        words: List of words (case-insensitive comparison).
        n: Number of top words to return.

    Returns:
        List of (word, count) tuples sorted by frequency descending.
    """
    # Normalize to lowercase for counting
    lower_words = [w.lower() for w in words]
    counter = collections.Counter(lower_words)
    return counter.most_common(n)


def char_frequency(text: str) -> Dict[str, int]:
    """Calculate frequency distribution for alphabetic characters.

    Case-insensitive; only counts a-z.

    Args:
        text: The text to analyze.

    Returns:
        Dictionary mapping character to count.
    """
    freq: Dict[str, int] = collections.defaultdict(int)
    for ch in text.lower():
        if ch.isalpha():
            freq[ch] += 1
    return dict(sorted(freq.items()))


def longest_word(words: List[str]) -> List[str]:
    """Find the longest word(s) in the text.

    Args:
        words: List of words.

    Returns:
        List of the longest word(s). Multiple if tied.
    """
    if not words:
        return []
    max_len = max(len(w) for w in words)
    # Use original case, but deduplicate
    seen = set()
    result = []
    for w in words:
        if len(w) == max_len and w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
    return result


def shortest_word(words: List[str]) -> List[str]:
    """Find the shortest word(s) in the text.

    Args:
        words: List of words.

    Returns:
        List of the shortest word(s). Multiple if tied.
    """
    if not words:
        return []
    min_len = min(len(w) for w in words)
    seen = set()
    result = []
    for w in words:
        if len(w) == min_len and w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
    return result


def flesch_kincaid_grade(words: List[str], sentence_count: int, syllables: int) -> float:
    """Calculate the Flesch-Kincaid Grade Level.

    Formula: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59

    Args:
        words: List of words.
        sentence_count: Number of sentences.
        syllables: Total syllable count.

    Returns:
        Grade level score.
    """
    if sentence_count == 0 or len(words) == 0:
        return 0.0

    avg_words_per_sent = len(words) / sentence_count
    avg_syllables_per_word = syllables / len(words)

    grade = 0.39 * avg_words_per_sent + 11.8 * avg_syllables_per_word - 15.59
    return round(grade, 2)


def count_syllables(word: str) -> int:
    """Estimate the number of syllables in a word.

    Uses a simplified rule-based approach:
    - Count vowel groups (a, e, i, o, u, y as vowel)
    - Subtract silent 'e' at end
    - Minimum of 1 syllable per word

    Args:
        word: The word to analyze.

    Returns:
        Estimated syllable count.
    """
    word = word.lower().strip()
    if not word:
        return 0

    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False

    for i, ch in enumerate(word):
        is_vowel = ch in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Handle silent 'e' at the end
    if word.endswith('e') and count > 1:
        # Check it's not part of a vowel group like "ee"
        if len(word) >= 2 and word[-2] not in vowels:
            count -= 1

    # Handle words ending in 'le' that add a syllable
    if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
        count += 1

    # Handle words ending in 'es' — usually an extra syllable isn't added
    # But for simplicity, leave as is

    return max(count, 1)


def total_syllables(words: List[str]) -> int:
    """Calculate total syllables for all words.

    Args:
        words: List of words.

    Returns:
        Total syllable count.
    """
    return sum(count_syllables(w) for w in words)


def flesch_reading_ease(words: List[str], sentence_count: int, syllables: int) -> float:
    """Calculate Flesch Reading Ease score.

    Formula: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)

    Args:
        words: List of words.
        sentence_count: Number of sentences.
        syllables: Total syllable count.

    Returns:
        Reading ease score (0-100, higher = easier).
    """
    if sentence_count == 0 or len(words) == 0:
        return 0.0

    avg_words_per_sent = len(words) / sentence_count
    avg_syllables_per_word = syllables / len(words)

    score = 206.835 - 1.015 * avg_words_per_sent - 84.6 * avg_syllables_per_word
    return round(score, 2)


# ──────────────────────────────────────────────────────────────────────
# Output Formatting
# ──────────────────────────────────────────────────────────────────────

def print_header(title: str, width: int = 60) -> None:
    """Print a formatted section header.

    Args:
        title: The section title.
        width: Total width of the header.
    """
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_bar_chart(data: Dict[str, int], max_bar_width: int = 40, top_n: int = 26) -> None:
    """Print a horizontal bar chart for character frequency.

    Args:
        data: Dictionary of character to count.
        max_bar_width: Maximum bar width in characters.
        top_n: Max characters to display.
    """
    if not data:
        print("  (no alphabetic characters found)")
        return

    max_count = max(data.values())
    if max_count == 0:
        return

    for char, count in data.items():
        bar_len = int((count / max_count) * max_bar_width)
        bar = '█' * bar_len + '░' * (max_bar_width - bar_len)
        print(f"  {char}: {bar} {count:>6}")


def print_report(filepath: str, text: str) -> None:
    """Print the complete statistical report.

    Args:
        filepath: Path to the analyzed file.
        text: The text content.
    """
    # ── Compute all statistics ──────────────────────────────────────
    total_chars, chars_no_ws = count_characters(text)
    words = count_words(text)
    lines = count_lines(text)
    sentences = count_sentences(text)
    avg_word_len = average_word_length(words)
    avg_wps = average_words_per_sentence(words, sentences)
    top10 = top_frequent_words(words, 10)
    char_freq = char_frequency(text)
    longest = longest_word(words)
    shortest = shortest_word(words)
    syllables = total_syllables(words)
    fk_grade = flesch_kincaid_grade(words, sentences, syllables)
    fk_ease = flesch_reading_ease(words, sentences, syllables)

    # ── Output Report ───────────────────────────────────────────────
    width = 64

    print()
    print("╔" + "═" * (width - 2) + "╗")
    print("║" + " TEXT STATISTICS REPORT ".center(width - 2) + "║")
    print("╠" + "═" * (width - 2) + "╣")
    print("║" + f" File: {os.path.basename(filepath)}".ljust(width - 2) + "║")
    print("║" + f" Path: {filepath}".ljust(width - 2) + "║")
    print("╚" + "═" * (width - 2) + "╝")

    # ── Section 1: General Counts ───────────────────────────────────
    print_header("GENERAL COUNTS")
    print(f"  Total characters (incl. whitespace):  {total_chars:>8,}")
    print(f"  Total characters (excl. whitespace):  {chars_no_ws:>8,}")
    print(f"  Total words:                          {len(words):>8,}")
    print(f"  Total lines:                          {lines:>8,}")
    print(f"  Total sentences:                      {sentences:>8,}")

    # ── Section 2: Averages ─────────────────────────────────────────
    print_header("AVERAGES")
    print(f"  Average word length:          {avg_word_len:>10.2f} characters")
    print(f"  Average words per sentence:   {avg_wps:>10.2f} words")
    print(f"  Average syllables per word:   {syllables/len(words) if words else 0:>10.2f}")

    # ── Section 3: Word Extremes ────────────────────────────────────
    print_header("WORD EXTREMES")
    if longest:
        print(f"  Longest word(s)  ({len(longest[0])} chars): {', '.join(longest)}")
    else:
        print(f"  Longest word(s):  N/A")
    if shortest:
        print(f"  Shortest word(s) ({len(shortest[0])} chars): {', '.join(shortest)}")
    else:
        print(f"  Shortest word(s): N/A")

    # ── Section 4: Top 10 Most Frequent Words ───────────────────────
    print_header("TOP 10 MOST FREQUENT WORDS")
    if top10:
        # Find the max count for proportional bar
        max_freq = top10[0][1] if top10 else 1
        rank_width = 3
        for rank, (word, count) in enumerate(top10, 1):
            bar_len = int((count / max_freq) * 16)
            bar = '█' * bar_len
            print(f"  {rank:>{rank_width}}. {word:<20} {count:>6}  {bar}")
    else:
        print("  (no words found)")

    # ── Section 5: Character Frequency Distribution ─────────────────
    print_header("CHARACTER FREQUENCY DISTRIBUTION (A-Z)")
    if char_freq:
        # Print in rows of 6 for compactness
        max_freq = max(char_freq.values())
        for i, (char, count) in enumerate(char_freq.items()):
            bar_len = int((count / max_freq) * 20)
            bar = '█' * bar_len
            end = '\n' if (i + 1) % 3 == 0 else '    '
            print(f"  {char}: {bar:<20} {count:>6}", end=end)
        if len(char_freq) % 3 != 0:
            print()
    else:
        print("  (no alphabetic characters found)")

    # ── Section 6: Readability Scores ───────────────────────────────
    print_header("READABILITY SCORES")
    print(f"  Flesch Reading Ease:        {fk_ease:>10.2f}")
    print(f"  Flesch-Kincaid Grade Level: {fk_grade:>10.2f}")
    print()
    # Interpretation
    if fk_ease >= 90:
        ease_label = "Very Easy (5th grade)"
    elif fk_ease >= 80:
        ease_label = "Easy (6th grade)"
    elif fk_ease >= 70:
        ease_label = "Fairly Easy (7th grade)"
    elif fk_ease >= 60:
        ease_label = "Standard (8th-9th grade)"
    elif fk_ease >= 50:
        ease_label = "Fairly Difficult (10th-12th grade)"
    elif fk_ease >= 30:
        ease_label = "Difficult (College)"
    else:
        ease_label = "Very Difficult (College Graduate)"
    print(f"  Interpretation: {ease_label}")
    print()

    if fk_grade <= 1:
        grade_label = "Kindergarten - 1st Grade"
    elif fk_grade <= 3:
        grade_label = "2nd - 3rd Grade"
    elif fk_grade <= 6:
        grade_label = "4th - 6th Grade"
    elif fk_grade <= 9:
        grade_label = "7th - 9th Grade (Junior High)"
    elif fk_grade <= 12:
        grade_label = "10th - 12th Grade (High School)"
    elif fk_grade <= 16:
        grade_label = "College Undergraduate"
    else:
        grade_label = "College Graduate / Professional"
    print(f"  Grade equivalent: {grade_label}")
    print()

    # ── Footer ──────────────────────────────────────────────────────
    print("─" * width)
    print("  Analysis complete.")
    print("─" * width)
    print()


# ──────────────────────────────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────────────────────────────

def main():
    """Main entry point for the text statistics analyzer."""
    parser = argparse.ArgumentParser(
        description="Text Statistics Analyzer - Analyze text files and produce "
                    "a detailed statistical report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python text_stats.py myfile.txt
  python text_stats.py /path/to/document.txt
        """
    )
    parser.add_argument(
        "filepath",
        help="Path to the text file to analyze."
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Text Statistics Analyzer v1.0.0"
    )

    args = parser.parse_args()

    try:
        text = read_file(args.filepath)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}", file=sys.stderr)
        print(f"  Please check that the file path is correct.\n", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n  ERROR: {e}", file=sys.stderr)
        print(f"  Please provide a non-empty text file.\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n  ERROR: Unexpected error reading file: {e}\n", file=sys.stderr)
        sys.exit(1)

    print_report(args.filepath, text)


if __name__ == "__main__":
    main()
