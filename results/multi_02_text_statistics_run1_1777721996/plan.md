```markdown
# Implementation Plan: Text Statistics Analyzer

## 1. Files and Purposes

- **`text_stats.py`** – The single Python script containing all logic:
  - Argument parsing
  - File reading and validation
  - Statistical computations
  - Formatted report printing
- **`README.md`** (optional, not required) – basic usage instructions.

No additional modules are needed; the tool is entirely self-contained using only the Python standard library.

## 2. Architecture

All functionality resides in one file with clear functional decomposition:

```
text_stats.py
├── main()
│   ├── parse_args()          → sys.argv[1]
│   ├── read_file(path)       → str or raises error
│   ├── compute_stats(text)
│   │   ├── tokenize(text)    → list of words, list of sentences
│   │   ├── char_count_total / char_count_no_spaces
│   │   ├── word_count
│   │   ├── line_count
│   │   ├── sentence_count
│   │   ├── average_word_length
│   │   ├── average_words_per_sentence
│   │   ├── top_words (Counter)
│   │   ├── char_freq (alphabetic only)
│   │   ├── longest_and_shortest
│   │   └── readability_score (ARI)
│   └── display_report(stats)
```

All steps are called sequentially. No state is shared outside the main flow.

## 3. Implementation Order

1. **Argument handling & file access**  
   - Check `sys.argv` length.  
   - Verify file existence & non-emptiness.  
   - Print error messages and exit with code 1 on failure.

2. **Core tokenization & basic counts**  
   - Read entire file into a string (`utf-8`).  
   - Split into lines (`text.splitlines()`) for line count.  
   - Define word tokenization: `re.findall(r"\b\w+\b", text.lower())` – gives list of words.  
   - Sentence splitting: use `re.split(r'(?<=[.!?])\s+', text)` to obtain sentences (handles simple end punctuation).  
   - Count characters with and without whitespace: `len(text)` and `len(re.sub(r'\s', '', text))`.

3. **Derived statistics**  
   - Average word length = sum(len(w) for w in words) / word_count.  
   - Average words per sentence = word_count / sentence_count.  
   - Top 10 words: `Counter(words).most_common(10)`.  
   - Longest/shortest word: `max(words, key=len)` / `min(words, key=len)`; handle ties by first occurrence.  
   - Character frequency distribution: iterate over `string.ascii_lowercase`, count occurrences in lowercased text using `text.lower().count(c)`.  
   - Readability score: Automated Readability Index (ARI) = `4.71 * (chars_no_spaces / words) + 0.5 * (words / sentences) - 21.43`. Clamp negative values to `0`.

4. **Output formatting**  
   - Print sections with headers (e.g., `=== BASIC COUNTS ===`).  
   - Align numbers neatly.  
   - For frequency distributions, list top 10 words with counts and character frequencies in a readable table-like format.

5. **Integration & testing**  
   - Tie everything together in `main()`.  
   - Manually test with known text files (e.g., a paragraph, an empty file, a missing file).

## 4. Standard Library Dependencies

- `sys` – command-line arguments, exit codes.
- `os.path` – `isfile()`, `getsize()` for file existence and emptiness check.
- `re` – regular expressions for tokenization and whitespace removal.
- `collections.Counter` – word frequencies.
- `string.ascii_lowercase` – alphabetic character set for frequency distribution.

No third-party libraries.

## 5. Feature Implementation Details

| Feature | Implementation Strategy |
|--------|--------------------------|
| **Command-line argument** | `sys.argv[1]` captured after checking length. Error message if missing. |
| **Character count total** | `len(text)` where `text` is the full file content. |
| **Character count excluding whitespace** | `len(re.sub(r'\s', '', text))`. |
| **Word count** | `len(words)` where words = `re.findall(r"\b\w+\b", text.lower())`. |
| **Line count** | `text.count('\n') + 1` or `len(text.splitlines())`. Note: `splitlines()` handles trailing newlines well. Use `len(text.splitlines())`. |
| **Sentence count** | Split by sentence-ending punctuation followed by space: `re.split(r'(?<=[.!?])\s+', text)`. Count non-empty strings. |
| **Average word length** | `sum(map(len, words)) / len(words)` if words > 0. |
| **Average words per sentence** | `word_count / sentence_count` if sentences > 0. |
| **Top 10 most frequent words** | `Counter(words).most_common(10)`. |
| **Character frequency (alphabetic)** | For each letter in `string.ascii_lowercase`, count occurrences in `text.lower()` and store. Display as a simple chart or list. |
| **Longest & shortest words** | `max(words, key=len)` and `min(words, key=len)`. If multiple, the first encountered is returned. |
| **Readability score** | Automated Readability Index: `4.71 * (characters_no_spaces / words) + 0.5 * (words / sentences) - 21.43`. Round to one decimal. |
| **Error handling (file not exist or empty)** | Before reading, `os.path.isfile(path)` and `os.path.getsize(path) > 0`. Print "Error: file not found" or "Error: file is empty" and `sys.exit(1)`. |
| **Output formatting** | Use section headers (`--- WORD STATISTICS ---`), aligned values, and simple tables. Print result to stdout. |

All computations happen in memory and will work for files that fit in RAM (reasonable for typical text files).
```