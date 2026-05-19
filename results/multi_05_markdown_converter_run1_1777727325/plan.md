# Implementation Plan: Markdown to HTML Converter

## Overview
A single-file command-line tool (`markdown_converter.py`) that reads a Markdown file, converts it to valid HTML with embedded CSS, and writes the output to a file with the same base name and `.html` extension. Uses only the Python standard library (`argparse`, `re`, `html`, `pathlib`).

## Files
| File | Purpose |
|------|---------|
| `markdown_converter.py` | Main script: argument parsing, file I/O, Markdown parsing, HTML generation |

## Architecture
The script is self-contained. It is organized into three layers:

1. **CLI Layer** (`main` function)  
   - Parses command-line arguments (input file path).  
   - Validates input file existence, prints error and exits if missing.  
   - Determines output file path by replacing the `.md` extension with `.html`.  
   - Calls conversion function and writes the result.

2. **Block Parser** (`parse_markdown` function)  
   - Splits input text into lines.  
   - Iterates line-by-line with state tracking:  
     - **In-code block** (fenced by ```````)  
     - **In-list** (unordered or ordered)  
     - **Paragraph** accumulation separated by blank lines.  
   - Recognises headings, lists, code blocks, and plain paragraphs.  
   - Applies inline conversions (`convert_inline`) to heading and paragraph/list item text.

3. **Inline Converter** (`convert_inline` function)  
   - Processes a single string for bold, italic, and inline links.  
   - Uses `re.sub` with ordered patterns to avoid nesting conflicts:  
     1. Bold: `\*\*(.*?)\*\*` → `<strong>\1</strong>`  
     2. Bold: `__(.*?)__` → `<strong>\1</strong>`  
     3. Italic: `\*(.*?)\*` → `<em>\1</em>`  
     4. Italic: `_(.*?)_` → `<em>\1</em>`  
     5. Links: `\[([^\]]+)\]\(([^\)]+)\)` → `<a href="\2">\1</a>`

The HTML document is constructed with a fixed template containing the CSS stylesheet in `<head>` and the converted body content.

## Implementation Order

1. **Setup argument parsing and file checks**  
   - Use `argparse` to accept one positional argument: the input Markdown file.  
   - Check with `pathlib.Path.exists()`; if not, print `Error: file not found` and exit.

2. **Read input and determine output path**  
   - Read all lines from the input file.  
   - Generate output path by replacing suffix `.md` with `.html` (use `pathlib.Path.with_suffix`).

3. **Implement block-level parsing**  
   - Maintain a list of HTML blocks (`<h1>`, `<ul>`, `<pre><code>`, `<p>`, etc.).  
   - Walk through lines with an index, handle:  
     - **Fenced code blocks**: when a line starts with ```` ``` ````, collect lines until closing ```` ``` ````; escape with `html.escape` and wrap in `<pre><code>`.  
     - **Headings**: if line matches `^#{1,6} (.*)`, capture level and text, add `<h{level}>text</h{level}>`.  
     - **Unordered lists**: if line starts with `- ` or `* `, collect consecutive such lines, then wrap in `<ul>` and each in `<li>`.  
     - **Ordered lists**: if line starts with `\d+\. `, same accumulation, wrap in `<ol>`.  
     - **Paragraphs**: treat any other non-blank line as paragraph text; group consecutive lines separated by blank lines into a single `<p>` (join lines with a space).  
   - Apply `convert_inline` to the text inside headings, list items, and paragraphs (code block content is left raw but escaped).

4. **Implement inline conversions**  
   - Apply the five regex substitutions in the order listed above.

5. **Assemble final HTML**  
   - Create a template string with `<!DOCTYPE html>`, `<html>`, `<head>` containing a `<style>` block with a basic readable stylesheet, then `<body>` containing all collected blocks.  
   - Recommended CSS: `max-width: 800px; margin: auto; font-family: system-ui; line-height: 1.6; padding: 1em;` with styling for `pre`, `code`, `a`, etc.

6. **Write output file**  
   - Write the complete HTML string to the output path using UTF-8 encoding.

7. **Testing**  
   - Test with a sample `.md` file covering all required features.  
   - Verify correct handling of edge cases: escaped characters, code inside lists, etc.

## Required Feature Mapping

| Feature | Implementation Detail |
|---------|------------------------|
| **Command-line argument** | `argparse` with one required argument; validated via `pathlib`. |
| **Output file naming** | Replace `.md` extension with `.html` using `Path.with_suffix`. |
| **Headings (# syntax)** | Regex `^#{1,6} `; parse level from `len` of `#` group; inline convert rest. |
| **Bold (`**text**` / `__text__`)** | Two regex passes for `**` and `__` before italic to avoid conflict. |
| **Italic (`*text*` / `_text_`)** | Two regex passes for `*` and `_`, after bold conversion. |
| **Inline links** | Regex `\[([^\]]+)\]\(([^\)]+)\)` → `<a href="...">`. |
| **Unordered lists (`- ` / `* `)** | Detect lines starting with `- ` or `* `; collect until a line no longer matches; wrap all in `<ul><li>`. Use `convert_inline` on each item. |
| **Ordered lists (`1. `)** | Detect lines starting with `\d+\. `; collect similarly; wrap in `<ol><li>`. |
| **Fenced code blocks (```````)** | Detect opening ` ``` `, collect lines until closing ` ``` `, escape with `html.escape`, wrap in `<pre><code>`. |
| **Paragraphs** | Group consecutive non-empty, non-special lines that are separated by blank lines; join with a space and wrap in `<p>`. |
| **Inline CSS** | Hardcoded `<style>` block in `<head>` with clean typography styles. |
| **Error on missing input** | `if not input_path.exists(): print("Error: ..."); sys.exit(1)` |

## Dependencies
- Python 3 standard library only: `sys`, `argparse`, `pathlib`, `re`, `html` (for `html.escape`).

This plan ensures a clear, stepwise build from simple CLI to full-featured converter.