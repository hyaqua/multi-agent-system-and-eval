# Revised Implementation Plan: Text Statistics Analyzer

## Overview
A single Python script (`text_stats.py`) that reads a text file and prints a formatted statistical report. It uses only the Python standard library. The analyzer extracts metrics via a series of easily testable functions and a `TextAnalyzer` class. The raw file content is preserved without stripping to ensure accurate character counts, line counts, and readability calculations.

**Changes from previous plan:**  
- Removed all references to the non-existent `self.clean_text` attribute; all methods now use `self.raw_text`, `self.words`, `self.sentences`, and `self.lines`.  
- Character counting now uses `c.isspace()` to correctly exclude all Unicode whitespace characters (spaces, tabs, newlines, carriage returns, etc.).  
- Character frequency distribution iterates directly over `self.raw_text`.  
- No new attributes are introduced; the `__init__` method sets only `raw_text`, `lines`, `words`, and `sentences`.

## Files and Modules
- **`text_stats.py`** — Main script containing:
  - Argument handling (`sys.argv`)
  - File I/O and error checking
  - `TextAnalyzer` class to compute all metrics
  - Output formatting logic (no additional modules)

## Architecture and Data Flow
1. Parse command-line argument to get file path.
2. Open and read the file content as a single string.
   - If file missing or empty → print error and exit.
3. Instantiate `TextAnalyzer(file_content)`. Do **no** global stripping or cleaning of the text.
4. Call the analyzer’s public methods to compute statistics.
   - Character counts and line count use the raw text directly.
   - Word and sentence extraction use the raw text but handle punctuation and whitespace appropriately.
5. Format and print the report with labeled sections.

### Internal Structure of `TextAnalyzer`
- **Attributes (set in `__init__`):**
  - `raw_text` — the exact file content, with all whitespace preserved.
  - `lines` — list of lines from `raw_text.splitlines()` (preserving all lines, including leading/trailing empty ones).
  - `words` — list of words obtained by splitting on whitespace and removing leading/trailing punctuation (but preserving apostrophes inside words). Empty strings resulting from purely punctuation tokens are filtered out.
  - `sentences` — list of sentence strings obtained by splitting on sentence-ending punctuation.
- **Methods:**
  - `compute_basic_counts()` → character counts (total and without whitespace), word count, line count, sentence count. All computed from `raw_text` or the pre‑computed collections.
  - `avg_word_length()` → total word length / word count.
  - `avg_words_per_sentence()` → word count / sentence count (with a minimum of 1 sentence to avoid division by zero).
  - `top_frequent_words(n=10)` → `collections.Counter` of lowercased words, excluding empty strings.
  - `character_frequency()` → `Counter` of alphabetic characters (case‑insensitive) iterating over `raw_text`.
  - `longest_and_shortest()` → return tuple (longest_word, shortest_word) from the word list, with ties broken by first occurrence.
  - `readability_ari()` → Automated Readability Index using character count without whitespace from `raw_text`, word count, and sentence count.

## Implementation Order
1. **Setup and argument parsing** (system exit on missing argument).
2. **File handling** — open, read, exit with error if file not found or empty (even if only whitespace).
3. **`TextAnalyzer` class skeleton** — store raw text, split into lines and words, and detect sentences (using `re` for robust splitting). **No `clean_text` attribute is created.**
4. **Basic counts** — implement `compute_basic_counts()` using `raw_text` and `isspace()` for whitespace exclusion.
5. **Derived averages** — word length, words per sentence.
6. **Frequency analyses** — top words (using `collections.Counter`), alphabetic character distribution (iterating over `raw_text`).
7. **Longest/shortest words** — using `max` and `min` by length.
8. **Readability score (ARI)** — using corrected character count without whitespace.
9. **Output formatting** — print sections with headers using separators.
10. **Testing** — run with sample files, edge cases (empty, single word, no punctuation, leading/trailing whitespace, all-whitespace file).

## Libraries Required
- **`sys`** — command-line arguments, exit.
- **`os.path`** — file existence check.
- **`collections.Counter`** — word and character frequency.
- **`re`** — for sentence splitting.
- **`string`** — `string.punctuation` for stripping word boundaries (but not apostrophes, which are kept inside words).

## Detailed Feature Implementation

### File Input and Error Handling
```python
import sys
import os

def main():
    if len(sys.argv) != 2:
        print("Usage: python text_stats.py <file_path>")
        sys.exit(1)
    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        sys.exit(1)
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    if not text.strip():                     # file with only whitespace → treated as empty
        print("Error: File is empty.")
        sys.exit(1)
    analyzer = TextAnalyzer(text)
    report = generate_report(analyzer)
    print(report)
```

### TextAnalyzer Initialization (revised)
```python
import re
import string
import collections

class TextAnalyzer:
    def __init__(self, text):
        # Keep raw text untouched.
        self.raw_text = text

        # Lines – preserve all.
        self.lines = self.raw_text.splitlines()

        # Words – split on whitespace, strip surrounding punctuation,
        # filter out empty strings (e.g., from tokens of pure punctuation).
        raw_words = self.raw_text.split()
        self.words = [w.strip(string.punctuation) for w in raw_words]
        self.words = [w for w in self.words if w]

        # Sentences – split on sentence-ending punctuation (one or more ! . ?)
        # followed by optional whitespace. Use strip() only to avoid
        # leading/trailing empty sentences; remaining empty chunks are filtered.
        stripped = self.raw_text.strip()
        if stripped:
            parts = re.split(r'(?<=[.!?]+)\s*', stripped)
            self.sentences = [s for s in parts if s]
        else:
            self.sentences = [""]   # edge case: all‑whitespace file (caught earlier)
```

*Note:* This `__init__` method defines **only** `raw_text`, `lines`, `words`, and `sentences`. There is no `clean_text` attribute.

### Basic Counts (revised)
```python
def compute_basic_counts(self):
    total_chars = len(self.raw_text)
    # Use isspace() to exclude all Unicode whitespace characters
    chars_no_space = sum(1 for ch in self.raw_text if not ch.isspace())
    word_count = len(self.words)
    line_count = len(self.lines)
    sentence_count = len(self.sentences)
    return {
        'total_chars': total_chars,
        'chars_no_space': chars_no_space,
        'word_count': word_count,
        'line_count': line_count,
        'sentence_count': sentence_count
    }
```

### Derived Averages (unchanged logic, safe from the bug)
```python
def avg_word_length(self):
    words = self.words
    return sum(len(w) for w in words) / len(words) if words else 0.0

def avg_words_per_sentence(self):
    num_sentences = max(len(self.sentences), 1)
    return len(self.words) / num_sentences
```

### Top Frequent Words (unchanged)
```python
def top_frequent_words(self, n=10):
    counter = collections.Counter(w.lower() for w in self.words)
    return counter.most_common(n)
```

### Character Frequency (revised)
```python
def character_frequency(self):
    counter = collections.Counter()
    for ch in self.raw_text:
        if ch.isalpha():
            counter[ch.lower()] += 1
    return counter
```

*This now uses `self.raw_text` directly.*

### Longest and Shortest Words (unchanged)
```python
def longest_and_shortest(self):
    if not self.words:
        return ("", "")
    longest = max(self.words, key=len)
    shortest = min(self.words, key=len)
    return (longest, shortest)
```

### Readability Score (ARI) (unchanged formula, already uses raw_text)
```python
def readability_ari(self):
    chars_no_space = sum(1 for ch in self.raw_text if not ch.isspace())
    words = len(self.words)
    sentences = max(len(self.sentences), 1)
    ari = 4.71 * (chars_no_space / words) + 0.5 * (words / sentences) - 21.43
    return round(ari, 1)
```

### Output Formatting
- Sections separated by lines of `=` or `-`.
- Headers: `BASIC COUNTS`, `AVERAGES`, `WORD FREQUENCY`, `CHARACTER FREQUENCY`, `EXTREMES`, `READABILITY`.
- Each statistic printed as `Label: value`.
- For the top words, output as a numbered list; for character frequency, list all letters with counts > 0.

## Sentence Splitting Details
The regex `r'(?<=[.!?]+)\s*'` splits **after** one or more sentence-ending punctuation marks (`[.!?]+`) and consumes any following whitespace. The initial `strip()` on `raw_text` ensures the split isn’t affected by leading/trailing whitespace, and empty strings are filtered out. This correctly handles:
- Multiple punctuation: `"Hello!! How are you?"` → `["Hello!!", "How are you?"]`
- Missing spaces after punctuation: `"End.No space"` → `["End.", "No space"]`
- Lone punctuation at the end: `"Only one."` → `["Only one."]`

## Testing and Edge Cases
- **Leading/trailing whitespace**: character counts include it; line count includes blank lines; words and sentences ignore it because of `split()` and the `strip()` in sentence extraction.
- **Empty file after stripping**: error message as before.
- **Single sentence with no punctuation**: `re.split` returns the whole string, sentence count = 1.
- **Division by zero**: prevented by `max(sentences, 1)`.
- **Apostrophes inside words**: `string.punctuation` includes the apostrophe (`'`), but `strip()` only removes it when it appears at the very beginning or end of a token. A word like `"don't"` strips nothing (no leading/trailing punctuation), so the apostrophe is preserved. Edge‑cases like `"'tis"` become `"tis"` (historically acceptable), and `"end'"` becomes `"end"`, which is fine.
- **All‑whitespace file**: caught as empty earlier.
- **Performance**: reading the entire file into memory is acceptable for typical text files.

All methods now rely solely on `self.raw_text`, `self.words`, `self.sentences`, and `self.lines`. No attempt is made to access a non‑existent `clean_text` attribute. The character‑no‑whitespace count and alphabetic frequency correctly iterate over the raw text and use `isspace()` to cover all whitespace characters.