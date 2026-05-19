#!/usr/bin/env python3
"""
Text Statistics Analyzer
========================
A command-line tool that reads a text file and produces a detailed
statistical report about its contents. Analyzes characters, words,
sentences, and provides frequency distributions.

Usage:
    python text_stats.py <filepath>
"""

import sys
import os
import re
from collections import Counter
from typing import List, Tuple


# ──────────────────────────────────────────────────────────────────────
#  Core Analysis Functions
# ──────────────────────────────────────────────────────────────────────

def read_file(filepath: str) -> str:
    """Read and return the contents of a text file."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        sys.exit(1)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error: Cannot read file '{filepath}': {e}")
        sys.exit(1)

    if not text.strip():
        print("Error: The file is empty (contains no meaningful content).")
        sys.exit(1)

    return text


def count_chars(text: str) -> Tuple[int, int]:
    """Return (total_chars, chars_without_whitespace)."""
    total = len(text)
    no_ws = sum(1 for ch in text if not ch.isspace())
    return total, no_ws


def count_words(text: str) -> List[str]:
    """Return list of words (alphabetic sequences, case-normalized for analysis)."""
    # Extract words: sequences of letters (including common accented chars)
    # with optional hyphens and apostrophes embedded inside
    # (e.g., contractions like "don't", compounds like "Flesch-Kincaid").
    # Pattern: one or more letters, optionally followed by (hyphen/apostrophe + letters)*
    LETTER = r"[a-zA-ZàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿœÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞŸŒ]"
    words = re.findall(rf"{LETTER}+(?:[-']{LETTER}+)*", text)
    return words


def count_lines(text: str) -> int:
    """Return number of lines (including empty lines)."""
    return text.count('\n') + (1 if text and not text.endswith('\n') else 0)


def count_sentences(text: str) -> int:
    """
    Count sentences by detecting sentence-ending punctuation: . ! ?
    Handles abbreviations and ellipses with heuristics.
    """
    # Normalize multiple punctuation (e.g., "..." or "!!")
    normalized = re.sub(r'[.!?]{2,}', '.', text)
    # Split on sentence boundaries
    # Sentence-ending punctuation followed by space or end-of-string
    sentences = re.split(r'(?<=[.!?])\s+', normalized.strip())
    # Filter out empty segments
    sentences = [s.strip() for s in sentences if s.strip()]
    return len(sentences) if sentences else 0


def average_word_length(words: List[str]) -> float:
    """Return average length of words."""
    if not words:
        return 0.0
    total_len = sum(len(w) for w in words)
    return round(total_len / len(words), 2)


def average_words_per_sentence(words: List[str], sentence_count: int) -> float:
    """Return average words per sentence."""
    if sentence_count == 0:
        return 0.0
    return round(len(words) / sentence_count, 2)


def top_n_words(words: List[str], n: int = 10) -> List[Tuple[str, int]]:
    """Return top N most frequent words with counts (case-insensitive)."""
    lower_words = [w.lower() for w in words]
    counter = Counter(lower_words)
    return counter.most_common(n)


def character_frequency(words: List[str]) -> List[Tuple[str, int]]:
    """
    Return frequency distribution of alphabetic characters across all words,
    sorted by frequency descending.
    """
    all_chars = []
    for w in words:
        for ch in w.lower():
            if ch.isalpha():
                all_chars.append(ch)
    counter = Counter(all_chars)
    # Sort by frequency descending, then alphabetically for ties
    return sorted(counter.items(), key=lambda x: (-x[1], x[0]))


def longest_words(words: List[str]) -> List[str]:
    """Return the longest word(s) — handles ties."""
    if not words:
        return []
    max_len = max(len(w) for w in words)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for w in words:
        if len(w) == max_len and w.lower() not in seen:
            result.append(w)
            seen.add(w.lower())
    return result


def shortest_words(words: List[str]) -> List[str]:
    """Return the shortest word(s) — handles ties."""
    if not words:
        return []
    min_len = min(len(w) for w in words)
    seen = set()
    result = []
    for w in words:
        if len(w) == min_len and w.lower() not in seen:
            result.append(w)
            seen.add(w.lower())
    return result


def count_syllables(word: str) -> int:
    """
    Estimate syllable count in an English word.
    Heuristic: count vowel groups; every word has at least one syllable.
    """
    word = word.lower()
    # Remove trailing silent 'e' (with exceptions)
    if word.endswith('e') and len(word) > 3:
        # Don't strip if ending in 'le' preceded by a consonant
        if not (len(word) >= 3 and word[-3] not in 'aeiouy' and word.endswith('le')):
            word = word[:-1]

    # Count vowel groups
    vowels = 'aeiouy'
    count = 0
    prev_vowel = False
    for ch in word:
        if ch in vowels:
            if not prev_vowel:
                count += 1
                prev_vowel = True
        else:
            prev_vowel = False

    return max(count, 1)


def flesch_reading_ease(words: List[str], sentence_count: int) -> Tuple[float, str]:
    """
    Calculate Flesch Reading Ease score.
    Score interpretation:
        90-100: Very Easy
        80-89:  Easy
        70-79:  Fairly Easy
        60-69:  Standard
        50-59:  Fairly Difficult
        30-49:  Difficult
        0-29:   Very Confusing
    """
    if not words or sentence_count == 0:
        return 0.0, "N/A"

    total_syllables = sum(count_syllables(w) for w in words)
    total_words = len(words)

    score = 206.835 - 1.015 * (total_words / sentence_count) - 84.6 * (total_syllables / total_words)
    score = round(score, 2)

    if score >= 90:
        grade = "Very Easy"
    elif score >= 80:
        grade = "Easy"
    elif score >= 70:
        grade = "Fairly Easy"
    elif score >= 60:
        grade = "Standard"
    elif score >= 50:
        grade = "Fairly Difficult"
    elif score >= 30:
        grade = "Difficult"
    else:
        grade = "Very Confusing"

    return score, grade


# ──────────────────────────────────────────────────────────────────────
#  Display / Formatting
# ──────────────────────────────────────────────────────────────────────

def print_header(title: str, width: int = 60) -> None:
    """Print a formatted section header."""
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_bar_chart(data: List[Tuple[str, int]], max_bar_len: int = 35) -> None:
    """Print a horizontal bar chart for frequency data."""
    if not data:
        print("  (no data)")
        return
    max_count = data[0][1] if data else 1
    for label, count in data:
        bar_len = int((count / max_count) * max_bar_len) if max_count > 0 else 0
        bar = '█' * bar_len
        print(f"  {label:6s} | {bar} {count}")


def analyze_and_report(filepath: str) -> None:
    """Main analysis and reporting function."""
    text = read_file(filepath)

    # ── Basic Counts ──────────────────────────────────────────────
    total_chars, chars_no_ws = count_chars(text)
    words = count_words(text)
    lines = count_lines(text)
    sentences = count_sentences(text)

    # ── Derived Statistics ────────────────────────────────────────
    avg_wl = average_word_length(words)
    avg_wps = average_words_per_sentence(words, sentences)
    top10 = top_n_words(words, 10)
    char_freq = character_frequency(words)
    longest = longest_words(words)
    shortest = shortest_words(words)
    readability_score, readability_label = flesch_reading_ease(words, sentences)

    # ── Output ────────────────────────────────────────────────────
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║         TEXT STATISTICS ANALYZER — Analysis Report        ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print(f"  File: {filepath}")

    # --- Section 1: Basic Counts ---
    print_header("BASIC COUNTS")
    print(f"  Total characters (incl. whitespace):  {total_chars:>8,}")
    print(f"  Total characters (excl. whitespace):  {chars_no_ws:>8,}")
    print(f"  Total words:                          {len(words):>8,}")
    print(f"  Total lines:                          {lines:>8,}")
    print(f"  Total sentences:                      {sentences:>8,}")

    # --- Section 2: Averages ---
    print_header("AVERAGES")
    print(f"  Average word length:                  {avg_wl:>8} characters")
    print(f"  Average words per sentence:           {avg_wps:>8}")

    # --- Section 3: Extremes ---
    print_header("WORD EXTREMES")
    if longest:
        label_long = "Longest word(s)"
        if len(longest) > 1:
            label_long += f" ({len(longest)} ties, {len(longest[0])} chars)"
        else:
            label_long += f" ({len(longest[0])} chars)"
        print(f"  {label_long}:")
        for w in longest:
            print(f"    • {w}")
    else:
        print(f"  Longest word(s):  (none)")

    if shortest:
        label_short = "Shortest word(s)"
        if len(shortest) > 1:
            label_short += f" ({len(shortest)} ties, {len(shortest[0])} chars)"
        else:
            label_short += f" ({len(shortest[0])} chars)"
        print(f"  {label_short}:")
        for w in shortest:
            print(f"    • {w}")
    else:
        print(f"  Shortest word(s): (none)")

    # --- Section 4: Top 10 Most Frequent Words ---
    print_header("TOP 10 MOST FREQUENT WORDS")
    if top10:
        print_bar_chart(top10)
        print()
        for rank, (word, count) in enumerate(top10, 1):
            print(f"  {rank:2d}. {word:<20s} — {count} occurrence(s)")
    else:
        print("  (no words found)")

    # --- Section 5: Character Frequency ---
    print_header("ALPHABETIC CHARACTER FREQUENCY")
    if char_freq:
        # Show all alphabetic chars present
        print_bar_chart(char_freq)
        print()
        # Also print a compact table
        total_alpha = sum(c for _, c in char_freq)
        for ch, count in char_freq:
            pct = (count / total_alpha * 100) if total_alpha > 0 else 0.0
            print(f"  '{ch}': {count:>6,}  ({pct:5.1f}%)")
    else:
        print("  (no alphabetic characters found)")

    # --- Section 6: Readability ---
    print_header("READABILITY")
    print(f"  Flesch Reading Ease score:            {readability_score:>8}")
    print(f"  Interpretation:                       {readability_label}")
    print()
    print("  Scale reference:")
    print("    90–100 : Very Easy")
    print("    80–89  : Easy")
    print("    70–79  : Fairly Easy")
    print("    60–69  : Standard")
    print("    50–59  : Fairly Difficult")
    print("    30–49  : Difficult")
    print("    0–29   : Very Confusing")

    print()
    print("═" * 60)
    print("  End of report.")
    print("═" * 60)
    print()


# ──────────────────────────────────────────────────────────────────────
#  Entry Point
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python text_stats.py <filepath>")
        print("Example: python text_stats.py sample.txt")
        sys.exit(1)

    filepath = sys.argv[1]
    analyze_and_report(filepath)


if __name__ == "__main__":
    main()
