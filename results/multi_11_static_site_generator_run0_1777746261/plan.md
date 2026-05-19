# Revised Implementation Plan: Static Site Generator

## 1. Overview
Build a command‑line tool that converts Markdown‑like content with YAML front matter into a static HTML website, using only the Python standard library. The generator reads from `content/`, applies templates from `templates/`, copies assets from `static/`, and outputs the site to `output/`. It provides a built‑in HTTP server (`--serve`) and a cleanup flag (`--clean`). The project includes a ready‑to‑use sample site with multiple templates, blog posts, and pages.

## 2. Project File Structure
```
project_root/
├── ssg/                      # Python package
│   ├── __init__.py           # (empty)
│   ├── __main__.py           # package entry point: calls cli.main()
│   ├── cli.py                # argument parsing, orchestration
│   ├── parser.py             # front matter + body parsing
│   ├── converter.py          # Markdown to HTML
│   ├── template_engine.py    # {{variable}} substitution
│   ├── builder.py            # site generation logic
│   └── server.py             # HTTP server for preview
├── content/                  # sample site content
│   ├── about.md              # page (no date)
│   ├── contact.md            # page (no date)
│   ├── first-post.md         # blog post
│   ├── second-post.md        # blog post
│   └── third-post.md         # blog post
├── templates/                # sample site templates
│   ├── base.html             # main template ({{navigation}}, {{content}})
│   ├── post.html             # template for individual blog posts
│   └── blog.html             # template for blog index
├── static/                   # sample site static assets
│   └── css/
│       └── style.css
└── README.md
```
All paths are resolved relative to the current working directory (the project root). The tool is invoked with `python -m ssg [--clean] [--serve]`.

## 3. Architecture & Data Flow
```
[CLI] → [Builder]
         ├→ [Parser] → list of Content objects
         ├→ [Converter] → raw HTML from body
         ├→ [Template Engine] → filled template strings
         ├→ Static asset copy (shutil)
         └→ [Server] (optional)
```

## 4. Implementation Order (revised with emphasis on file presence and sample site)

### Step 0: Establish the full project directory and sample site **BEFORE writing any application logic.**
This ensures the package and its sample content are immediately usable for testing.

1. **Create the `ssg/` package directory** and inside it place empty (or minimal) Python files:
   * `ssg/__init__.py` – empty file.
   * `ssg/__main__.py` – contains only:
     ```python
     from ssg.cli import main
     main()
     ```
   * `ssg/cli.py` – initially define a stub `main()` that just prints “CLI placeholder”. We will replace it later.
   * `ssg/parser.py`, `ssg/converter.py`, `ssg/template_engine.py`, `ssg/builder.py`, `ssg/server.py` – all stubs (e.g., define empty functions or classes so the package is importable).

2. **Create the sample content files** inside `content/`:
   * `about.md`:
     ```markdown
     ---
     title: About
     template: base.html
     ---
     # About This Site

     This is a sample page.
     ```
   * `contact.md`:
     ```markdown
     ---
     title: Contact
     template: base.html
     ---
     # Contact Us

     Reach out via email.
     ```
   * `first-post.md`:
     ```markdown
     ---
     title: First Post
     date: 2025-01-15
     tags: [python, ssg]
     template: post.html
     ---
     # First Post

     This is the first blog post. **Exciting!**
     ```
   * `second-post.md`:
     ```markdown
     ---
     title: Second Post
     date: 2025-02-20
     tags: [update]
     template: post.html
     ---
     ## Second Post

     Another update with [a link](https://example.com).
     ```
   * `third-post.md`:
     ```markdown
     ---
     title: Third Post
     date: 2025-03-10
     tags: [python, tips]
     template: post.html
     ---
     ### Code Block

     ```
     print("Hello, world!")
     ```
     ```

3. **Create the template files** inside `templates/`:
   * `base.html`:
     ```html
     <!DOCTYPE html>
     <html>
     <head><title>{{title}}</title></head>
     <body>
       <nav>{{navigation}}</nav>
       <main>{{content}}</main>
     </body>
     </html>
     ```
   * `post.html`:
     ```html
     <!DOCTYPE html>
     <html>
     <head><title>{{title}}</title></head>
     <body>
       <nav>{{navigation}}</nav>
       <article>
         <h1>{{title}}</h1>
         <p><small>{{date}}</small></p>
         <p>Tags: {{tags}}</p>
         <div>{{content}}</div>
       </article>
     </body>
     </html>
     ```
   * `blog.html`:
     ```html
     <!DOCTYPE html>
     <html>
     <head><title>{{title}}</title></head>
     <body>
       <nav>{{navigation}}</nav>
       <h1>{{title}}</h1>
       <ul>{{content}}</ul>
     </body>
     </html>
     ```

4. **Create the static assets**:
   * `static/css/style.css` (any minimal CSS, e.g., `body { font-family: sans-serif; }`).

After this step, the project directory will contain all source files and sample data, and running `python -m ssg --clean` will already be possible (though the build will be a no‑op until the logic is implemented). This eliminates the “file not found” error and lets us test incrementally.

### Step 1: Fully implement CLI (`ssg/cli.py`)
* Replace the stub `main()` with proper argument parsing using `argparse`.
* Implement `--clean`: before building, remove the `output/` directory if it exists using `shutil.rmtree`.
* Implement `--serve`: after building, call `serve_site` (from `server.py`) to start the HTTP server.
* Orchestrate the build by calling the builder’s main function (e.g., `builder.build()`).
* Ensure `ssg/__main__.py` remains correct (it already calls `main()`).

### Step 2: Parser (`ssg/parser.py`)
* Read a `.md` file and split front matter (delimited by `---`) from the body.
* Manually parse the YAML‑style front matter (simple key: value pairs, with support for lists like `tags: [a, b]`).
* Return a `Content` object (or dict) with `title`, `date` (optional), `tags` (optional), `template`, and `body`.
* Markdown body is left untouched (conversion happens later).

### Step 3: Markdown Converter (`ssg/converter.py`)
* Convert basic Markdown to HTML using regular expressions or a state machine:
  - Headings (`#` … `######`)
  - Bold (`**text**`) → `<strong>`
  - Italic (`*text*`) → `<em>`
  - Links (`[text](url)`) → `<a href="…">`
  - Unordered lists (`- ` or `* `) → `<ul><li>…</li></ul>`
  - Code blocks (fenced with ```) → `<pre><code>…</code></pre>`
  - Paragraphs (double newline)
* Returns the HTML string.

### Step 4: Template Engine (`ssg/template_engine.py`)
* Implement a function `render(template_string, context_dict)` that replaces all `{{variable}}` occurrences with the corresponding value from the context.
* No bells and whistles – simple string substitution.

### Step 5: Builder (`ssg/builder.py`)
* a. Scan `content/` directory, parse all `.md` files. Separate pages (no `date` field) and posts (have `date`).
* b. Generate navigation HTML: iterate over pages list, create `<a href="/slug/">Title</a>` for each, and possibly a link to the blog index (`/blog/`).
* c. Generate blog index:
   - Sort posts descending by `date`.
   - Render a list of `<li><a href="/blog/slug/">{{title}}</a> – {{date}}</li>` for each post.
   - Load `blog.html` template.
   - Substitute `{{title}}` = "Blog", `{{content}}` = the generated list HTML, `{{navigation}}` = navigation.
   - Write to `output/blog/index.html`.
* d. For each page and post:
   - Convert body to HTML using converter.
   - Load the template specified in the front matter.
   - Build context: `content` (the converted HTML), `navigation`, and any front matter fields (title, date, tags).
   - Render the final HTML.
   - Determine output path using clean URLs:
     * pages: `output/<slug>/index.html`
     * posts: `output/blog/<slug>/index.html`
   - Create directories and write `index.html`.
* e. Copy static assets from `static/` to `output/` preserving directory structure (using `shutil.copytree` if possible, or manual copy of files).

### Step 6: Server (`ssg/server.py`)
* Implement a function `serve_site(host='localhost', port=8000)`.
* Use `http.server.HTTPServer` with a custom handler that serves files from the `output/` directory.
* Print the URL to the console.

## 5. Feature‑by‑Feature Verification (Integration Test)
Once all modules are implemented, run the following commands from the project root:

1. `python -m ssg --clean`
   - The `output/` directory appears with:
     - `about/index.html`
     - `contact/index.html`
     - `blog/index.html`
     - `blog/first-post/index.html`
     - `blog/second-post/index.html`
     - `blog/third-post/index.html`
     - `css/style.css`
   - All HTML pages contain correct navigation, blog index lists posts sorted by date, post pages show metadata.

2. `python -m ssg --serve`
   - Server starts, navigate to `http://localhost:8000`, verify that the site works and all links are functional.

If any feature fails, fix the corresponding module. The sample site provides immediate test data.

## 6. Dependencies
Only Python standard library: `argparse`, `pathlib`, `shutil`, `re`, `http.server`, `datetime`. No external libraries.

---

This revised plan now explicitly lists the creation of every source file and sample content at the very beginning, eliminating the “file not found” error and allowing incremental development with working test fixtures. The implementation order remains logical, and all required features are addressed.