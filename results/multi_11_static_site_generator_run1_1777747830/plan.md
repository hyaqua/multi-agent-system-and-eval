```markdown
## Revised Implementation Plan: Static Site Generator

### 1. Files to Create and Purposes
- `parser.py` – front matter and content splitting
- `markdown.py` – basic Markdown → HTML conversion
- `template.py` – `{{variable}}` substitution
- `generator.py` – main site‑building logic (includes output‑directory handling)
- `server.py` – local preview server
- `main.py` – CLI entry point (orchestration only)
- `sample_site/` – complete demonstration content (`content/`, `templates/`, `static/`) **used as input source**

---

### 2. Architecture

#### `parser.py`
- `parse_file(path)`: returns dict of front matter and raw Markdown body.
- YAML‑like parsing: split on `---`, read `key: value` lines; handle simple lists.
- Required keys: `title`, `type`, `template`; optional: `date`, `tags`.

#### `markdown.py`
- `to_html(text)`: converts Markdown to HTML.
- Supports headings, bold, italic, links, images, unordered/ordered lists, code blocks, paragraphs.
- Uses `re` internally for inline formatting patterns.

#### `template.py`
- `render(template_string, variables)`: replaces `{{variable}}` using `re`.

#### `generator.py`
- **Output‑directory preparation (revised to work with new default)**
  0. If the `--clean` flag is set:
     - If the output directory exists, wrap `shutil.rmtree(output_dir)` in a `try/except OSError`.
       - On success → continue.
       - On failure → print `"Error: Could not remove output directory due to permission/access issues. Please remove it manually."` and exit with code 1.
     - If the directory does **not** exist, do nothing (no error).
  1. If the output directory does **not** exist:
     - Attempt `os.makedirs(output_dir, exist_ok=True)` inside a `try/except OSError`.
     - On `OSError`, print `"Error: Cannot create output directory. Check parent folder permissions."` and exit with code 1.
  2. If the output directory **exists** and `--clean` was **not** used:
     - **Check writability** with `os.access(output_dir, os.W_OK)`.
     - If not writable → print `"Output directory exists but is not writable. Please remove it manually or use --clean."` and exit with code 1.
     - If writable → proceed normally.
  3. All subsequent file operations (e.g., copying static assets) are performed **only** after this preparation succeeds.

- **Build flow** (unchanged except for using the passed output directory):
  1. Scan `content/` (inside input content directory) for `.md` files.
  2. Parse each; separate by `type` into posts and pages.
  3. Convert Markdown → HTML, load template, render with variables + navigation, write to clean URLs under the output directory.
  4. Build blog index → `output/blog/index.html`.
  5. Navigation menu passed as `{{navigation}}` to every template.
  6. Copy `static/` recursively to `output/` using `shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)`.

- **Input directory and output directory** are configurable. The generator’s `__init__` accepts `content_dir`, `template_dir`, `static_dir`, `output_dir`.
- Missing template → fallback minimal HTML; missing required front matter → log and skip.

#### `main.py`
- CLI using `argparse`: `--serve`, `--clean`, `--output` (optional), `--content` (optional), `--templates` (optional), `--static` (optional).
- **Output directory default**: If `--output` is not provided, **default to `output/` in the current working directory**.
  - Implementation: `output_dir = args.output if args.output else os.path.join(os.getcwd(), 'output')`.
- **Only orchestrates**: parses arguments, instantiates `Generator` with resolved paths, and calls `generator.build(clean=args.clean)`.
- **No direct file‑system manipulation** (no `shutil.rmtree`, no `os.makedirs`). All output‑directory logic resides in `generator.py`.
- **Remove unused import `shutil`** – `main.py` imports only what it uses (e.g., `argparse`, `os`, `generator`, `server`).
- After building, if `--serve` is present, call `server.start(output_dir)`.

#### `server.py`
- Simple HTTP server from the generated output directory.
- Uses `http.server.HTTPServer` and `SimpleHTTPRequestHandler`, changing directory with `os.chdir(output_dir)` **only** before starting the server (no redundant `directory` argument).
- No unused imports.

---

### 3. Implementation Order
1. `parser.py`
2. `markdown.py`
3. `template.py`
4. `generator.py` (with robust output‑directory handling)
5. `main.py` (default output to cwd, clean imports)
6. `server.py`
7. Sample site creation (demonstration content under `sample_site/`)
8. Integration testing

---

### 4. Libraries Required
- Python standard library: `os`, `sys`, `shutil`, `re`, `argparse`, `http.server`, `datetime`
- No `pathlib`, `typing`, or other unused modules.

---

### 5. Feature Implementation Details

#### a–d, f, h, j (unchanged)
- Markdown conversion, variable substitution, blog index generation, navigation, clean URLs, static asset copying.

#### e. Navigation menu
- Built from all pages (non‑blog content) automatically; injected as `{{navigation}}`.

#### g. Static asset copying
- Uses `shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)` only after output directory is successfully prepared.

#### i. --clean flag
- Wrapped in `try/except OSError` in `generator.py` with descriptive error messages; exit code 1 on failure.

#### k. Additional improvements (from feedback)
- **Default output directory changed** from `sample_site/output/` to `output/` in the project’s current working directory. This avoids permission errors when `sample_site/` is read‑only.
- **Unused import `shutil` removed** from `main.py`.
- Generator’s output‑directory creation logic will now create the new default path with the same error handling, ensuring a smooth build in writable locations.
- Sample site files are kept inside `sample_site/` for demonstration, but the generated output is kept separate (in cwd/output/ by default).

---

### 6. Sample Site Structure
```
sample_site/
├── content/
│   ├── post1.md
│   ├── post2.md
│   ├── post3.md
│   ├── about.md
│   └── contact.md
├── templates/
│   ├── base.html
│   ├── post.html
│   ├── page.html
│   └── blog_index.html
└── static/
    └── style.css
```

The generator is run from the project root. Using default arguments, it reads content from `sample_site/content/`, templates from `sample_site/templates/`, static from `sample_site/static/`, and writes output to `./output/` (created if necessary).

---

These revisions ensure the default behaviour is safe, writable directories are used, and the code remains clean with no unused imports. The output directory handling in the generator is already prepared for this new default, so no structural changes are needed beyond the path resolution in `main.py`.