# Implementation Plan: Markdown to HTML Converter

## 1. File Structure

- **`markdown_converter.py`** — single Python script containing all logic:
  - command-line argument parsing
  - input file validation
  - HTML template with embedded CSS
  - Markdown-to-HTML conversion engine
  - output file writing

No external libraries are used; only standard library modules `sys`, `re`, and `pathlib`.

## 2. Architecture

The converter follows a straightforward pipeline:

1. **Argument Parsing** – read the input file path from `sys.argv`.
2. **Validation** – check if the file exists; exit with error if not.
3. **File Reading** – read all lines into memory.
4. **Block Parsing** – scan lines to identify block-level elements:
   - Fenced code blocks
   - Headings (`#` syntax)
   - Unordered/ordered lists
   - Paragraphs (separated by blank lines)
5. **Inline Parsing** – within text blocks (paragraphs, list items, headings), apply inline transformations:
   - Bold (`**` or `__`)
   - Italic (`*` or `_`)
   - Links (`[text](url)`)
6. **HTML Generation** – assemble the parsed blocks into an HTML document with a basic stylesheet.
7. **Output** – write the HTML to a file with the same base name but `.html` extension.

State is managed with a simple loop that groups consecutive lines of the same block type.

## 3. Implementation Order

1. **CLI skeleton** – handle `sys.argv`, check file existence, define `main()`.
2. **HTML template** – function that returns the full HTML structure with a `<style>` block containing readable CSS (font, max-width, code background, list margins, etc.).
3. **Block parsing** – function `parse_blocks(lines)` that yields a list of block dictionaries:
   - `{"type": "heading", "level": int, "content": str}`
   - `{"type": "code", "content": str}`
   - `{"type": "list", "ordered": bool, "items": [str]}`
   - `{"type": "paragraph", "content": str}`
4. **Inline parsing** – function `parse_inline(text)` that applies bold, then italic, then links (in that order to avoid conflicts). Uses `re.sub` with safe placeholder patterns.
5. **Rendering** – function that converts the list of blocks to HTML strings, calling `parse_inline` on relevant content.
6. **Assembly & write** – combine rendered blocks into the template and write the output file.

## 4. Required Features Implementation

### File input & output
- Use `sys.argv[1]` for input; print usage if missing.
- Use `pathlib.Path` to validate existence, derive output path (`with_suffix('.html')`).

### Headings
- Match lines with `r'^(#{1,6})\s+(.*)'`.
- Emit `<hN>content</hN>` with inline parsing applied.

### Bold and italic
- Process bold first: `**text**` → `<strong>text</strong>`; same for `__`.
- Process italic: `*text*` → `<em>text</em>`; `_text_`. Use non-greedy patterns to avoid crossing boundaries.
- Apply after block grouping so that `*` used for list markers doesn’t interfere.

### Inline links
- Match `[text](url)` with regex `r'\[([^\]]+)\]\(([^\)]+)\)'`.
- Replace with `<a href="url">text</a>`.

### Unordered lists
- Group consecutive lines starting with `- ` or `* ` (after stripping marker/whitespace).
- Each group becomes `<ul><li>...</li></ul>` with inline parsing applied to item content.

### Ordered lists
- Group consecutive lines starting with `d+. ` (number + dot + space).
- Similar output as unordered but use `<ol>`.

### Fenced code blocks
- Detect start and end lines that are exactly ` ``` ` (may allow optional language, but spec just fences). Collect lines between as raw content.
- Emit `<pre><code>content</code></pre>`. Escape HTML entities (`&`, `<`, `>`) in the code content.

### Paragraphs
- Any block of non-blank lines that doesn’t match another pattern becomes a paragraph.
- Join lines with a space, wrap in `<p>...</p>` with inline parsing.

### CSS stylesheet
- Embed in `<style>`: set font-family to system fonts, max-width 800px, margin auto, line-height 1.6. Code blocks get a light grey background and monospace font. Headings, links, lists styled for readability.

### Error handling
- Check `input_path.exists()`. If not, print `Error: file not found` to stderr and exit(1).

## 5. Example HTML Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; line-height: 1.6; color: #333; }
    pre { background: #f4f4f4; padding: 1rem; border-radius: 4px; }
    code { font-family: monospace; font-size: 0.9em; }
    img { max-width: 100%; }
    a { color: #1a0dab; }
  </style>
</head>
<body>
  {content}
</body>
</html>
```

## 6. Edge Cases & Notes

- **Mixed bold/italic**: Process bold first so `***text***` becomes strong+em if desired, but simple handling may not support triple markers; spec doesn't require it.
- **Escaping**: The spec does not mention backslash escapes, so ignore for now.
- **Nested lists**: Not required; all list items are flat inside one `<ul>`/`<ol>`.
- **Code inside inline**: If fenced code block is processed first, inline code (backticks) not required. Spec only mentions fenced blocks.
- **Indentation**: We assume well-formed Markdown without indentation issues.

This plan yields a single-file, dependency-free converter that fulfills all required features.