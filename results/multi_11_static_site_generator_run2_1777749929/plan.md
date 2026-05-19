# Implementation Plan: Static Site Generator

## Architecture Overview

A single Python package (`ssg/`) with distinct modules for parsing, conversion, and site building. The entry point is `ssg.py` (a script or `__main__.py`) that exposes a command-line interface. All processing uses only the Python standard library.

### Modules
- **`ssg/` package**:
  - `__init__.py` — empty.
  - `frontmatter.py` — parse YAML-like front matter.
  - `markdown.py` — convert limited Markdown to HTML.
  - `builder.py` — orchestrate reading content, applying templates, generating output, creating blog/navigation.
  - `cli.py` — argparse-based CLI with `--clean` and `--serve` flags (calls builder, then optionally starts HTTP server).
- **`ssg.py`** — top‑level entry point (invokes `ssg.cli.main()`).
- **Sample project folder** (provided alongside): `sample_site/` with `content/`, `templates/`, `static/`.

No external dependencies beyond stdlib.

## File List and Purposes

```
ssg/
├── __init__.py
├── frontmatter.py
├── markdown.py
├── builder.py
└── cli.py
ssg.py
sample_site/
├── content/
│   ├── pages/
│   │   ├── about.md
│   │   └── contact.md
│   └── posts/
│       ├── post1.md
│       ├── post2.md
│       └── post3.md
├── templates/
│   ├── post.html
│   ├── page.html
│   └── blog.html
└── static/
    └── css/
        └── style.css
```

- **`frontmatter.py`**: `parse(text) -> dict` — extracts YAML-like front matter between `---` delimiters.
- **`markdown.py`**: `convert(md_text) -> str` — transforms basic Markdown to HTML.
- **`builder.py`**: Functions to:
  - scan content directories,
  - load templates,
  - replace `{{variable}}` placeholders,
  - write output with clean URLs (`slug/index.html`),
  - generate blog index HTML,
  - generate navigation menu HTML,
  - copy static assets.
- **`cli.py`**: Parses arguments, calls builder, starts HTTP server if `--serve`.
- **`ssg.py`**: Simple wrapper: `from ssg.cli import main; main()`.
- **`sample_site/`**: Pre‑built sample demonstrating all features.

## Implementation Order

1. **Package housekeeping**: Create directory structure, `__init__.py`.
2. **`frontmatter.py`**: Robust parser that splits on `---`, reads lines with `key: value`.
3. **`markdown.py`**: Start with basic inline (bold, italic, code, links), then headings, paragraphs, lists, code blocks. Process block-level first, then inline.
4. **`builder.py`**:
   - Placeholder substitution engine.
   - Read templates.
   - Scan content, apply front matter and Markdown, produce output pages.
   - Generate blog index (collect posts, sort by date, inject into `{{posts}}`).
   - Generate navigation menu (collect pages, produce HTML list, inject into `{{navigation}}` everywhere).
   - Copy `static/` to `output/`.
5. **`cli.py`**: Argparse (`--clean`, `--serve`, optional `--output-dir`), call builder, conditional server start.
6. **`ssg.py`**: Entry point.
7. **Sample site**: Populate `sample_site/` as described, run the generator against it to verify.

## Feature Implementation Details

### 1. Reading content and front matter
- Walk `content/` recursively for `.md` files.
- Use `file.read().split('---', 2)`; the middle part is front matter, the last is body.
- In `frontmatter.parse()`: iterate lines, split on `:`, trim, store in dict. Treat `date` as string (the blog index will sort by it as ISO date). Tags can be comma-separated; keep as string.

### 2. Markdown to HTML (`markdown.convert`)
- **Code blocks**: Extract with regex ```` ```.*?``` ```` (re.DOTALL), replace with `<pre><code>…</code></pre>` using a placeholder to avoid interference with other rules.
- **Headings**: lines starting with `#`; trim hashes to get level, wrap in `<h#>`.
- **Unordered lists**: consecutive lines starting with `- ` or `* ` → wrap entire group in `<ul>`, each line as `<li>`.
- **Ordered lists**: lines starting with digits + `.` → `<ol>` with `<li>`.
- **Paragraphs**: any remaining contiguous text block → `<p>` block.
- **Inline** (apply sequentially after block processing):
  - **Bold**: `**` or `__` → `<strong>`.
  - **Italic**: `*` or `_` → `<em>`.
  - **Inline code**: backtick pairs → `<code>`.
  - **Links**: `[text](url)` → `<a href="url">text</a>`.
- Return joined HTML string. (Keep it simple, no nesting of block elements inside other blocks.)

### 3. Template substitution
- Read template file entirely.
- Replace `{{content}}` with the HTML generated from Markdown body.
- For any other `{{...}}` found via regex `\{\{(\w+)\}\}`, look up the front matter dict (title, date, tags, template name, etc.). Replace with the value or empty string if missing. The navigation placeholder `{{navigation}}` will be a special case populated globally.

### 4. Blog index page
- Collect all content files where `front_matter.get('template') == 'post'`.
- Sort descending by `date` (assume YYYY-MM-DD).
- Build HTML snippet: an unordered list with `<li><a href="/blog/{slug}/index.html">{title}</a> - {date}</li>`.
- Load `templates/blog.html` (or the blog index template specified, e.g., `blog.html`). Replace `{{posts}}` with the list HTML, `{{title}}` with a default like "Blog", and `{{navigation}}` with the global nav. Write to `output/blog/index.html`.

### 5. Navigation menu
- Gather all content where `template != 'post'` (i.e., pages). Additionally, include a hardcoded link to the blog index (`/blog/index.html`).
- Build `<ul>` list of `<li><a href="/{slug}/index.html">{title}</a></li>` for each page, plus the blog link.
- Store this HTML string. For every page generated (both posts and pages), replace `{{navigation}}` with this string before writing.

### 6. Clean URL output
- For each content file:
  - Create a slug from the title (lowercase, replace spaces with hyphens, remove non-alphanumeric except `-`). Use the filename if title missing.
  - Determine output directory:
    - If `template == 'post'` → `output/blog/{slug}/`
    - Else (page) → `output/{slug}/`
  - Ensure directory exists, write `index.html` inside.

### 7. Static asset copying
- Use `shutil.copytree('static', 'output/static', dirs_exist_ok=True)` (Python 3.8+). On earlier Python, remove and copy.

### 8. `--clean` flag
- Before building, if `args.clean`, delete `output/` tree using `shutil.rmtree('output', ignore_errors=True)`, then re‑create `output/`.

### 9. `--serve` flag
- After build, change working directory to `output/` and create `http.server.HTTPServer(('', 8000), SimpleHTTPRequestHandler)`. Run `server.serve_forever()` with `try/except KeyboardInterrupt` to allow clean shutdown.

### 10. Sample site
- Provide `sample_site/` with:
  - **templates/post.html**: `<html><head>...<title>{{title}}</title>...</head><body><header>{{navigation}}</header><article><h1>{{title}}</h1><p class="date">{{date}}</p>{{content}}</article></body></html>`
  - **templates/page.html**: similar, without date.
  - **templates/blog.html**: `<h1>{{title}}</h1>{{posts}}{{navigation}}`
  - **content/pages/about.md** and **contact.md**: front matter `title`, `template: page`.
  - **content/posts/post1.md**, **post2.md**, **post3.md**: front matter `title`, `date`, `tags`, `template: post`, with varied Markdown body.
  - **static/css/style.css**: basic styling.

## Edge Cases & Robustness
- Missing front matter fields → use defaults (title from filename, empty date, empty tags, template `page` if absent).
- Template not found → raise clear error.
- Placeholder in template not found in front matter → replace with empty string.
- Ensure `output/` directory is created if not exist.
- Slug collisions: if two pages produce same slug, append a number or skip with warning. For simplicity, rely on unique titles/folders.