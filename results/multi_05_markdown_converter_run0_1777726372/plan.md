# Revised Implementation Plan: Markdown to HTML Converter

## 1. Project Files and Their Purposes

- **`md2html.py`**  
  Entry point script. Parses command-line arguments, checks input file existence, calls the converter, and writes the output HTML file.

- **`md_converter.py`**  
  Core conversion module. Contains:
  - `markdown_to_html(text: str) -> str` – Converts a raw Markdown string to an HTML body string.
  - `_wrap_html(body: str, title: str) -> str` – Wraps the body content into a full HTML document with a basic inline stylesheet.
  - Helper functions for block and inline parsing.

- **`tests/test_converter.py`** *(optional)*  
  Unit tests using `unittest` or `pytest` to verify conversion of each feature. Not required for the plan, but recommended.

All libraries are from the Python standard library: `argparse`, `re`, `pathlib`.

---

## 2. Architecture and Data Flow

```text
User runs: python md2html.py input.md
                │
                ▼
          md2html.py
        - Parse arguments
        - Check file exists
        - Read file content
                │
                ▼
          md_converter.py
        - Split input into blocks (headings, lists, code, paragraphs)
        - For each block, apply inline formatting with safe ordering (links first via placeholders, then bold, then italic)
        - Assemble HTML body with appropriate tags
        - Wrap in full HTML template with stylesheet
                │
                ▼
          md2html.py
        - Write HTML to input_stem.html
```

**State machine approach** for block parsing:  
Iterate over lines with a state variable (`normal`, `code_fence`, `unordered_list`, `ordered_list`). Accumulate lines until a block terminator (blank line, closing fence, or next non-list line) is encountered, then emit the HTML.

---

## 3. Implementation Order

1. **Set up CLI and file I/O** (`md2html.py`)  
   - Use `argparse` to accept exactly one positional argument: the input file path.  
   - Use `pathlib.Path` to check existence (`file.is_file()`) and derive output path (`file.with_suffix('.html')`).  
   - Read the entire file as UTF-8 text; if the file does not exist, print `"Error: Input file not found."` to stderr and exit with code 1.

2. **Block-level parsing** (`md_converter.py`)  
   - Implement detection and collection for:  
     - **Fenced code blocks**: triggered by a line starting with ` ``` `; collect everything until the next ` ``` ` line.  
     - **Unordered lists**: lines starting with `- ` or `* ` (space required) are items. Collect consecutive such lines.  
     - **Ordered lists**: lines starting with a number followed by `. ` (e.g., `1. `) are items. Collect consecutive such lines.  
     - **Headings**: lines beginning with 1–6 `#` characters followed by a space. Process immediately.  
     - **Paragraphs**: any run of non-blank lines not matching the above; separated by blank lines.  
   - Use blank lines as block separators for paragraphs and lists.  
   - Transform each collected block into its corresponding HTML wrapper (`<pre><code>`, `<ul><li>`, `<ol><li>`, `<hn>`, `<p>`).

3. **Inline formatting** (revised order)  
   - Apply inline transformations only inside block content that allows Markdown – **not** inside fenced code blocks.  
   - To prevent italic/bold from corrupting link URLs (e.g., when a URL contains underscores), **links must be processed before any other formatting**. The robust approach uses a placeholder technique:  
     1. Scan the text for all Markdown links `[text](url)`.  
     2. Replace each occurrence with a unique placeholder token (e.g., `@@LINK_{i}@@`) that contains no characters susceptible to other patterns.  
     3. Store the corresponding HTML anchor `<a href="{url}">{text}</a>` in a dictionary keyed by the placeholder.  
     4. Apply **bold** and then **italic** formatting to the entire text (which now contains placeholders instead of raw URLs).  
     5. Finally, substitute all placeholder tokens with their stored anchor tags.  
   - This guarantees that underscores inside links are never touched by the italic regex.  
   - Order of inline processing within a block:  
     - **Links** (placeholder extraction)  
     - **Bold**  
     - **Italic**

4. **Code block escaping**  
   - Inside fenced code blocks, replace `&` with `&amp;`, `<` with `&lt;`, `>` with `&gt;` to prevent HTML injection. Do not apply inline formatting.

5. **HTML document assembly**  
   - Generate a complete HTML5 page with:  
     - `<!DOCTYPE html>`  
     - `<html lang="en">`  
     - `<head>` containing `<meta charset="utf-8">`, `<title>` (derived from input filename), and a `<style>` block with basic CSS for readability (see section 7).  
     - `<body>` filled with the converted HTML body.

6. **Write output**  
   - Save the assembled HTML document to the output path (same stem, `.html` extension).

---

## 4. Libraries

- **argparse** – command-line argument parsing.  
- **pathlib** – file path handling (check existence, change extension).  
- **re** – regular expressions for inline and block detection.  
- **sys** – for stderr output and exit codes.  
- No external libraries; 100% standard library.

---

## 5. Feature Implementation Details

### 5.1 Command-line Argument
- `argparse.ArgumentParser` with one positional argument `input_file`.  
- Validate `Path(input_file).is_file()`, else error.

### 5.2 Output File Name
- `input_path = Path(input_file)`  
- `output_path = input_path.with_suffix('.html')`

### 5.3 Headings
- Regex: `^(#{1,6})\s+(.*)`  
- Capture level count `len(match.group(1))` and text `match.group(2)`.  
- Apply inline formatting (with the revised order) to the heading text, then wrap with `<h{level}>...</h{level}>`.

### 5.4 Inline Links (applied first via placeholders)
- Pattern: `\[([^\]]*?)\]\(([^)]*?)\)` (non‑greedy; assumes URLs contain no nested parentheses).  
- For each match found in the raw text:  
  - Store `(text, url)` and assign a unique placeholder like `@@LINK_0@@`.  
  - Replace the entire match with the placeholder.
- After bold/italic processing, replace each `@@LINK_i@@` with `<a href="{url}">{text}</a>`.

### 5.5 Bold Text (applied after link placeholders)
- Use `re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)`  
- Then `re.sub(r'__(.+?)__', r'<strong>\1</strong>', line)`  
- These substitutions are applied only after all link placeholders are in place, so underscores inside link placeholders (nonexistent) are not an issue.

### 5.6 Italic Text (applied last)
- After bold, apply `re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)`  
- Then `re.sub(r'_(.+?)_', r'<em>\1</em>', line)`  
- Because link URLs are now safe inside placeholders (which contain no underscores), the italic regex will only affect intended italic markers outside `<a>` tags.

### 5.7 Unordered Lists
- Detect lines matching `^\- (.+)` or `^\* (.+)`.  
- Collect consecutive lines until a blank line or line not matching.  
- Each item gets its content inline-processed, then wrapped in `<li>`.  
- Whole block wrapped in `<ul>`.  
- Blank line terminates the list and triggers new block.

### 5.8 Ordered Lists
- Detect lines matching `^\d+\. (.+)`.  
- Same logic as unordered; wrapper is `<ol>`.

### 5.9 Fenced Code Blocks
- Look for line starting with ` ``` ` (optionally followed by language).  
- Enter `code_fence` state; collect lines until another ` ``` ` line.  
- Join collected lines, escape HTML special characters (`&`, `<`, `>`).  
- Output `<pre><code>escaped_text</code></pre>`.  
- Do **not** apply inline formatting inside code blocks.

### 5.10 Paragraphs
- Any block of non‑blank lines that isn’t a heading, list, or code block.  
- Join lines with a space.  
- Apply inline formatting (links first, then bold, then italic), then wrap with `<p>`.

### 5.11 Basic Inline CSS Stylesheet
Embed the following in a `<style>` tag inside `<head>`:

```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
    color: #333;
}
h1, h2, h3, h4, h5, h6 { color: #222; margin-top: 1.5em; }
pre {
    background: #f4f4f4;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
}
code {
    font-family: monospace;
}
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { padding-left: 2em; }
```

### 5.12 Error Handling
- File not found: print `"Error: Input file 'filename' not found."` to `sys.stderr`, `sys.exit(1)`.  
- For any other expected errors (e.g., permission), we can catch and display a generic error, but not strictly required by spec.

---

## 6. Edge Cases and Limitations

- **Nested lists** (indented sub‑lists) are **not supported**; the converter treats every list item flush as a single-level list.  
- **Code spans** (`inline code`) are not required and therefore not implemented.  
- **Horizontal rules** (`---`) are not required.  
- **Images** (`![alt](url)`) are not required; the converter may treat them as regular links (or ignore).  
- **Escaping** of Markdown characters (e.g., `\*literal\*`) is not implemented beyond code blocks.  
- The converter does not validate URL syntax in links; it trusts the input. Note that URLs containing closing parentheses `)` may break the basic regex; such edge cases are out of scope.  
- Blank lines inside paragraph blocks (multiple consecutive blank lines) are treated as paragraph separators.

---

## 7. Testing Strategy (Optional but Recommended)

- Write a test file for each feature.  
- Use `pytest` or `unittest` to compare expected HTML output with actual conversion.  
- Include tests for: headings, bold, italic, links, unordered/ordered lists, code blocks (with escaping), paragraphs, and the full‑document wrapper.  
- **Crucial test**: a link whose URL contains one or more underscores (e.g., `[demo](http://example.com/some_path_with_underscores)`) must produce a valid `<a href="http://example.com/some_path_with_underscores">demo</a>` without italicising any part of the URL.  
- Test error condition: missing file raises SystemExit or prints to stderr.

---

This plan now prevents the italic‑before‑link corruption bug by processing links first (via a placeholder technique that isolates URLs from the subsequent bold/italic transformations). All other features remain unchanged.