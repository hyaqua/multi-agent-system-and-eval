#!/usr/bin/env python3
"""Text Statistics Analyzer - Reads a text file and prints a formatted statistical report."""

import sys
import os
import re
import string
from collections import Counter


class TextAnalyzer:
    """Analyzes text content and computes various statistics."""

    def __init__(self, text: str):
        self.raw_text = text                       # untouched original content
        self.lines = self.raw_text.splitlines()    # all lines preserved
        self._words = None
        self._sentences = None

    @property
    def words(self) -> list:
        """Return list of cleaned words (lowercased, punctuation stripped)."""
        if self._words is None:
            self._words = self._extract_words()
        return self._words

    @property
    def sentences(self) -> list:
        """Return list of sentence strings."""
        if self._sentences is None:
            self._sentences = self._extract_sentences()
        return self._sentences

    def _extract_words(self) -> list:
        """Extract cleaned words from text: split on whitespace, strip outer punctuation."""
        # Split on whitespace (split() handles leading/trailing whitespace implicitly)
        raw_words = self.raw_text.split()
        # Strip punctuation from each word (but keep internal apostrophes/hyphens)
        cleaned = []
        for w in raw_words:
            # Strip leading/trailing punctuation
            stripped = w.strip(string.punctuation)
            if stripped:
                cleaned.append(stripped.lower())
        return cleaned

    def _extract_sentences(self) -> list:
        """Split text into sentences using punctuation delimiters . ! ?"""
        # Use regex to split on sentence-ending punctuation; strip only for this purpose
        txt = self.raw_text.strip()

        # Split on one or more sentence-ending punctuation marks followed by optional whitespace
        parts = re.split(r'(?<=[.!?]+)\s*', txt)

        # Filter out empty/whitespace-only parts
        result = [s.strip() for s in parts if s.strip()]
        if not result:
            result = [""]   # fallback for edge cases (no sentences found)
        return result

    def compute_basic_counts(self) -> dict:
        """Return basic counts: chars (with/without spaces), words, lines, sentences."""
        char_with_spaces = len(self.raw_text)
        char_without_spaces = sum(1 for ch in self.raw_text if not ch.isspace())
        return {
            'characters_with_spaces': char_with_spaces,
            'characters_without_spaces': char_without_spaces,
            'words': len(self.words),
            'lines': len(self.lines),
            'sentences': max(len(self.sentences), 1),  # at least 1 to avoid division by zero
        }

    def avg_word_length(self) -> float:
        """Return average word length (characters per word)."""
        words = self.words
        if not words:
            return 0.0
        total_len = sum(len(w) for w in words)
        return round(total_len / len(words), 2)

    def avg_words_per_sentence(self) -> float:
        """Return average words per sentence."""
        sentence_count = max(len(self.sentences), 1)
        return round(len(self.words) / sentence_count, 2)

    def top_frequent_words(self, n: int = 10) -> list:
        """Return list of (word, count) tuples for the n most frequent words."""
        word_counts = Counter(self.words)
        return word_counts.most_common(n)

    def character_frequency(self) -> dict:
        """Return Counter of alphabetic characters (case-insensitive)."""
        char_counter = Counter()
        for ch in self.raw_text:
            if ch.isalpha():
                char_counter[ch.lower()] += 1
        return dict(char_counter.most_common())

    def longest_and_shortest(self) -> tuple:
        """Return (longest_word, shortest_word) from cleaned words.
        
        If multiple words have the same length, the first encountered is returned.
        """
        words = self.words
        if not words:
            return ("", "")
        longest = max(words, key=lambda w: len(w))
        shortest = min(words, key=lambda w: len(w))
        return (longest, shortest)

    def readability_ari(self) -> dict:
        """Compute Automated Readability Index.
        
        ARI = 4.71 * (chars_without_spaces / words) + 0.5 * (words / sentences) - 21.43
        """
        counts = self.compute_basic_counts()
        words = counts['words']
        sentences = counts['sentences']
        chars_no_spaces = counts['characters_without_spaces']

        if words == 0:
            return {'score': 0.0, 'grade_level': 'Unknown'}

        ari = 4.71 * (chars_no_spaces / words) + 0.5 * (words / sentences) - 21.43
        ari = round(ari, 2)

        # Map score to grade level (clamp to reasonable range)
        grade = self._ari_to_grade(ari)

        return {'score': ari, 'grade_level': grade}

    @staticmethod
    def _ari_to_grade(score: float) -> str:
        """Map ARI score to a grade level label."""
        if score < 0:
            return "Kindergarten or below"
        grade_map = {
            1: "1st Grade",
            2: "2nd Grade",
            3: "3rd Grade",
            4: "4th Grade",
            5: "5th Grade",
            6: "6th Grade",
            7: "7th Grade",
            8: "8th Grade",
            9: "9th Grade",
            10: "10th Grade",
            11: "11th Grade",
            12: "12th Grade",
            13: "College Freshman",
            14: "College Sophomore",
            15: "College Junior",
            16: "College Senior",
            17: "Graduate",
        }
        grade_num = int(round(score))
        if grade_num > 17:
            return "Post-Graduate"
        elif grade_num < 1:
            return "Kindergarten or below"
        return grade_map.get(grade_num, f"Grade ~{grade_num}")


def format_report(analyzer: TextAnalyzer) -> str:
    """Generate a formatted statistical report from the analyzer."""
    sep_eq = "=" * 60
    sep_dash = "-" * 60
    lines = []

    # Header
    lines.append(sep_eq)
    lines.append("TEXT STATISTICS REPORT")
    lines.append(sep_eq)

    # --- BASIC COUNTS ---
    lines.append("")
    lines.append("BASIC COUNTS")
    lines.append(sep_dash)
    counts = analyzer.compute_basic_counts()
    lines.append(f"  Characters (including whitespace): {counts['characters_with_spaces']}")
    lines.append(f"  Characters (excluding whitespace): {counts['characters_without_spaces']}")
    lines.append(f"  Words:                            {counts['words']}")
    lines.append(f"  Lines:                            {counts['lines']}")
    lines.append(f"  Sentences:                        {counts['sentences']}")

    # --- AVERAGES ---
    lines.append("")
    lines.append("AVERAGES")
    lines.append(sep_dash)
    lines.append(f"  Average word length:        {analyzer.avg_word_length()}")
    lines.append(f"  Average words per sentence: {analyzer.avg_words_per_sentence()}")

    # --- WORD FREQUENCY ---
    lines.append("")
    lines.append("WORD FREQUENCY (Top 10)")
    lines.append(sep_dash)
    top_words = analyzer.top_frequent_words(10)
    for i, (word, count) in enumerate(top_words, 1):
        lines.append(f"  {i:>2}. {word:<20} {count}")

    # --- CHARACTER FREQUENCY ---
    lines.append("")
    lines.append("CHARACTER FREQUENCY (Alphabetic)")
    lines.append(sep_dash)
    char_freq = analyzer.character_frequency()
    # Display in a compact multi-column format
    if char_freq:
        chars_sorted = sorted(char_freq.items(), key=lambda x: x[1], reverse=True)
        # Print 5 per line
        chunk_size = 5
        for i in range(0, len(chars_sorted), chunk_size):
            chunk = chars_sorted[i:i + chunk_size]
            parts = []
            for ch, cnt in chunk:
                parts.append(f"'{ch}': {cnt}")
            lines.append("  " + " | ".join(parts))
    else:
        lines.append("  (No alphabetic characters found)")

    # --- EXTREMES ---
    lines.append("")
    lines.append("EXTREMES")
    lines.append(sep_dash)
    longest, shortest = analyzer.longest_and_shortest()
    lines.append(f"  Longest word:  '{longest}' ({len(longest)} characters)")
    lines.append(f"  Shortest word: '{shortest}' ({len(shortest)} characters)")

    # --- READABILITY ---
    lines.append("")
    lines.append("READABILITY")
    lines.append(sep_dash)
    ari = analyzer.readability_ari()
    lines.append(f"  Automated Readability Index (ARI): {ari['score']}")
    lines.append(f"  Estimated grade level:             {ari['grade_level']}")

    lines.append("")
    lines.append(sep_eq)
    lines.append("END OF REPORT")
    lines.append(sep_eq)

    return "\n".join(lines)


def main():
    """Main entry point: parse arguments, read file, analyze, and print report."""
    if len(sys.argv) != 2:
        print("Usage: python text_stats.py <file_path>")
        sys.exit(1)

    filepath = sys.argv[1]

    # Check if file exists
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        sys.exit(1)

    # Read file
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (IOError, PermissionError) as e:
        print(f"Error: Could not read file '{filepath}': {e}")
        sys.exit(1)

    # Check if file is empty
    if not text.strip():
        print("Error: File is empty.")
        sys.exit(1)

    # Analyze and print report
    analyzer = TextAnalyzer(text)
    report = format_report(analyzer)
    print(report)


if __name__ == '__main__':
    main()
