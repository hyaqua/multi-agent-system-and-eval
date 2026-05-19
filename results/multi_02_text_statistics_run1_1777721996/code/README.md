# Text Statistics Analyzer

A command-line tool that analyzes a text file and displays a comprehensive
statistical report.

## Usage

```bash
python text_stats.py <file_path>
```

## Features

- **Basic Counts**: total characters (with and without spaces), words, lines,
  sentences.
- **Word Statistics**: average word length, average words per sentence,
  longest and shortest words.
- **Top 10 Words**: most frequent words with their counts.
- **Character Frequency**: frequency distribution of alphabetic characters.
- **Readability**: Automated Readability Index (ARI) score.

## Error Handling

- Displays an error and exits with code 1 if:
  - No file path is provided.
  - The specified file does not exist.
  - The file is empty.

## Example

```bash
$ python text_stats.py sample.txt
====================================================
  TEXT STATISTICS REPORT
====================================================
...
```
