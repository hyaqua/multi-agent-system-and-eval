#!/usr/bin/env python3
"""
Text Statistics Analyzer
Reads a text file and produces a detailed statistical report.
"""

import sys
import os
import re
from collections import Counter


def count_syllables(word: str) -> int:
    """Estimate syllable count in a word using vowel-group counting."""
    word = word.lower().rstrip(".!?,;:;\"'")
    if not word:
        return 0

    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Silent 'e' at end
    if word.endswith("e") and count > 1:
        # Check if it's a silent e (not part of "le" where the 'e' is needed)
        if len(word) >= 2 and word[-2] not in vowels and word[-2] != 'l':
            count -= 1
        elif len(word) >= 2 and word[-2] == 'l' and count > 1:
            # "le" at end often counts as a syllable
            pass

    # Ensure at least 1 syllable per word
    return max(count, 1)


def flesch_reading_ease(total_words: int, total_sentences: int,
                        total_syllables: int) -> float:
    """Calculate Flesch Reading Ease score."""
    if total_words == 0 or total_sentences == 0:
        return 0.0
    score = (206.835
             - 1.015 * (total_words / total_sentences)
             - 84.6 * (total_syllables / total_words))
    return score


def interpret_readability(score: float) -> str:
    """Interpret the Flesch Reading Ease score."""
    if score >= 90:
        return "Very Easy (5th grade)"
    elif score >= 80:
        return "Easy (6th grade)"
    elif score >= 70:
        return "Fairly Easy (7th grade)"
    elif score >= 60:
        return "Standard (8th-9th grade)"
    elif score >= 50:
        return "Fairly Difficult (10th-12th grade)"
    elif score >= 30:
        return "Difficult (College)"
    else:
        return "Very Difficult (College Graduate)"


def print_header(title: str, width: int = 60):
    """Print a formatted section header."""
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_subheader(title: str):
    """Print a formatted sub-header."""
    print(f"\n  --- {title} ---")


def main():
    # Parse command-line arguments
    if len(sys.argv) != 2:
        print("Usage: python text_stats.py <file_path>")
        print("Example: python text_stats.py sample.txt")
        sys.exit(1)

    filepath = sys.argv[1]

    # Check if file exists
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        sys.exit(1)

    # Check if path is a file
    if not os.path.isfile(filepath):
        print(f"Error: '{filepath}' is not a valid file.")
        sys.exit(1)

    # Read file content
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Error: Could not read file '{filepath}': {e}")
        sys.exit(1)

    # Check if file is empty
    if not text.strip():
        print(f"Error: File '{filepath}' is empty.")
        sys.exit(1)

    # ================================================================
    # Compute statistics
    # ================================================================

    # Character counts
    total_chars = len(text)
    chars_no_whitespace = len(re.sub(r"\s+", "", text))

    # Line count
    lines = text.splitlines()
    total_lines = len(lines)

    # Extract words: sequences of alphabetic characters, hyphens, apostrophes
    # Also keep contractions and hyphenated words together
    words = re.findall(r"[a-zA-Z]+(?:[-'][a-zA-Z]+)*", text.lower())
    total_words = len(words)

    # Sentence detection: split on .!? followed by space or end
    # Handle edge cases like "Mr.", "Dr.", "U.S.A." etc. simply by requiring
    # that sentence-ending punctuation is followed by space+capital or end.
    sentences_raw = re.split(r'(?<=[.!?])\s+', text)
    # Filter out empty strings
    sentences = [s.strip() for s in sentences_raw if s.strip()]
    total_sentences = len(sentences)

    # Average word length
    if total_words > 0:
        total_word_chars = sum(len(w) for w in words)
        avg_word_length = total_word_chars / total_words
    else:
        avg_word_length = 0.0

    # Average words per sentence
    if total_sentences > 0:
        avg_words_per_sentence = total_words / total_sentences
    else:
        avg_words_per_sentence = 0.0

    # Top 10 most frequent words
    word_freq = Counter(words)
    top_10_words = word_freq.most_common(10)

    # Character frequency distribution (alphabetic only)
    alpha_chars = [ch.lower() for ch in text if ch.isalpha()]
    char_freq = Counter(alpha_chars)
    sorted_char_freq = sorted(char_freq.items())

    # Longest and shortest words (by character length)
    # Remove duplicates to get unique words
    unique_words = list(set(words))
    if unique_words:
        longest_word = max(unique_words, key=len)
        shortest_word = min(unique_words, key=len)
        longest_len = len(longest_word)
        shortest_len = len(shortest_word)
        # Collect all words tied for longest/shortest
        all_longest = sorted(set(w for w in unique_words if len(w) == longest_len))
        all_shortest = sorted(set(w for w in unique_words if len(w) == shortest_len))
    else:
        longest_word = shortest_word = ""
        longest_len = shortest_len = 0
        all_longest = all_shortest = []

    # Readability score (Flesch Reading Ease)
    total_syllables = sum(count_syllables(w) for w in words)
    readability_score = flesch_reading_ease(
        total_words, total_sentences, total_syllables
    )
    readability_interpretation = interpret_readability(readability_score)

    # ================================================================
    # Print report
    # ================================================================

    print_header("TEXT STATISTICS REPORT")
    print(f"  File: {os.path.abspath(filepath)}")

    # --- Basic Counts ---
    print_subheader("Basic Counts")
    print(f"  Total characters (including whitespace): {total_chars:>8,}")
    print(f"  Total characters (excluding whitespace): {chars_no_whitespace:>8,}")
    print(f"  Total words:                             {total_words:>8,}")
    print(f"  Total lines:                             {total_lines:>8,}")
    print(f"  Total sentences:                         {total_sentences:>8,}")

    # --- Averages ---
    print_subheader("Averages")
    print(f"  Average word length:          {avg_word_length:>8.2f} characters")
    print(f"  Average words per sentence:   {avg_words_per_sentence:>8.2f}")

    # --- Word Extremes ---
    print_subheader("Word Extremes")
    print(f"  Longest word(s) ({longest_len} chars): {', '.join(all_longest)}")
    print(f"  Shortest word(s) ({shortest_len} chars): {', '.join(all_shortest)}")

    # --- Top 10 Most Frequent Words ---
    print_subheader("Top 10 Most Frequent Words")
    print(f"  {'Rank':<6} {'Word':<20} {'Count':>8}  {'Bar'}")
    print(f"  {'-'*6} {'-'*20} {'-'*8}  {'-'*20}")
    max_count = top_10_words[0][1] if top_10_words else 1
    for rank, (word, count) in enumerate(top_10_words, 1):
        bar_len = int((count / max_count) * 20)
        bar = "█" * bar_len
        print(f"  {rank:<6} {word:<20} {count:>8}  {bar}")

    # --- Character Frequency Distribution ---
    print_subheader("Character Frequency Distribution (Alphabetic)")
    if sorted_char_freq:
        max_cfreq = max(c for _, c in sorted_char_freq)
        for char, count in sorted_char_freq:
            bar_len = int((count / max_cfreq) * 30)
            bar = "█" * bar_len
            print(f"  '{char}': {count:>6,}  {bar}")
    else:
        print("  (No alphabetic characters found)")

    # --- Readability ---
    print_subheader("Readability")
    print(f"  Flesch Reading Ease Score:  {readability_score:.2f}")
    print(f"  Interpretation:             {readability_interpretation}")
    print(f"  (Based on {total_words} words, {total_sentences} sentences, "
          f"{total_syllables} syllables)")

    print_header("END OF REPORT")


if __name__ == "__main__":
    main()
