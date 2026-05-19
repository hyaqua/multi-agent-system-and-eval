# Implementation Plan: Text Statistics Analyzer

## 1. Files
- **`text_stats.py`** – Single Python script containing all logic.

## 2. Architecture
Follow a simple procedural flow:
- Parse command-line argument (file path) using `sys.argv`.
- Validate file existence and non‑emptiness.
- Read file content as a single string.
- Compute all statistics using dedicated functions.
- Format and print the report.
No external dependencies.

## 3. Implementation Order
1. **Argument & file handling** – `main()` checks `sys.argv[1]`, verifies file with `os.path.exists`, reads content with `open().read()`, exits with an error message if invalid or empty.
2. **Basic counts** – 
   - Characters (total = `len(text)`; without whitespace = total minus count of `string.whitespace` characters).
   - Lines = `len(text.splitlines())`.
   - Word tokens: use `re.findall(r'[a-zA-Z]+', text.lower())` to get a list of alphabetic words. Word count = length of that list.
3. **Sentence detection** – Use `re.split(r'[.!?]+', text)` and count non‑empty strings (strip before checking).
4. **Averages** 
   - Average word length = sum of lengths of word tokens / word count.
   - Average words per sentence = word count / sentence count.
5. **Frequency analysis**
   - Most frequent words: `collections.Counter(word_tokens).most_common(10)`.
   - Character frequency: iterate over alphabetic tokens, count letters a‑z, store in a dict, sort by descending frequency (or just print all).
6. **Longest / shortest words** – Find `max` / `min` from word tokens by length (handle ties by showing first one or all).
7. **Readability score** – Use **Automated Readability Index**:  
   `ARI = 4.71 * (characters_no_spaces / word_count) + 0.5 * (word_count / sentence_count) - 21.43`.  
   Round to one decimal.
8. **Report formatting** – Print section headers (`== Basic Counts ==` etc.) and aligned key‑value pairs.

## 4. Libraries
- `sys` – command-line arguments.
- `os` – file existence check.
- `re` – word extraction, sentence splitting.
- `collections.Counter` – frequency counting.
- `string` – whitespace definition (optional, `str.isspace()` could also be used).

## 5. Feature Implementation Details

| Feature | Implementation |
|---------|---------------|
| **Command-line file argument** | `if len(sys.argv) != 2: print('Usage...'); sys.exit(1)` |
| **Character count (total)** | `len(text)` |
| **Character count (no whitespace)** | `len([c for c in text if not c.isspace()])` or `len(text) - sum(1 for c in text if c.isspace())` |
| **Word count** | `len(re.findall(r'[a-zA-Z]+', text))` |
| **Line count** | `len(text.splitlines())` |
| **Sentence count** | `len([s for s in re.split(r'[.!?]+', text) if s.strip()])` |
| **Average word length** | `sum(len(w) for w in words) / word_count` (guard against zero) |
| **Average words per sentence** | `word_count / sentence_count` if sentences>0 else 0 |
| **Top 10 frequent words** | `Counter(words).most_common(10)`, display each as `word: count` |
| **Character frequency (a‑z)** | Loop over all `words`, count each character with `c.isalpha()`, store in `Counter`, output sorted by letter or frequency. |
| **Longest/shortest word** | `max(words, key=len)` / `min(words, key=len)`; handle if multiple with same length by listing all. |
| **Readability score** | Compute ARI as described; if sentence count = 0, treat as 1 to avoid division by zero (or just note N/A). |
| **Error handling** | Before reading: `if not os.path.exists(path): print('Error: file not found.'); sys.exit(1)`; after reading: `if not text.strip(): print('Error: file is empty.'); sys.exit(1)` |
| **Output formatting** | Use `print("...")` with fixed-width headers and aligned columns, e.g., `print(f"{'Total characters:':<25}{total_chars}")`. |

## 6. Additional Notes
- Word tokenization via `[a-zA-Z]+` ignores numbers, apostrophes, and hyphens – this meets typical plain‑text analysis expectations.
- Sentence splitting is simple and may miscount abbreviations (e.g., “Mr.”), but is acceptable for this tool.
- All statistics may safely use integer formats except readability, which is a float rounded to one decimal.
- Output will be directly printed; no file writing needed.