# Static Site Generator

A simple static site generator built with Python using only the standard library.

## Features

- Reads Markdown content files with YAML-like front matter
- Converts Markdown to HTML (headings, bold, italic, links, lists, code blocks)
- Template engine with `{{variable}}` substitution
- Generates clean URLs (`/page/` → `page/index.html`)
- Blog index with date-sorted posts
- Automatic navigation menu from pages
- Copies static assets (CSS, images, etc.)
- Built-in HTTP server for preview

## Usage

### Build the site

```bash
python main.py
```

This reads content from `sample_site/content/`, templates from `sample_site/templates/`,
static files from `sample_site/static/`, and writes the output to `sample_site/output/`.

### Clean and build

```bash
python main.py --clean
```

### Build and serve

```bash
python main.py --serve
```

Then visit http://localhost:8000 in your browser.

### Clean, build, and serve

```bash
python main.py --clean --serve
```

### Verbose output

```bash
python main.py --clean --serve --verbose
```

## Project Structure

```
├── main.py                      # CLI entry point
├── site_generator/              # Core package
│   ├── __init__.py
│   ├── parser.py                # Front matter parser
│   ├── markdown.py              # Markdown to HTML
│   ├── template.py              # Template engine
│   ├── generator.py             # Site builder
│   └── server.py                # HTTP server
├── sample_site/                 # Example site
│   ├── content/                 # .md content files
│   ├── templates/               # .html templates
│   ├── static/                  # CSS, images, etc.
│   └── output/                  # Generated site
└── README.md
```

## Content File Format

Each `.md` file starts with front matter between `---` delimiters:

```markdown
---
title: My Page Title
date: 2025-01-15
tags: [tag1, tag2]
type: page
template: page.html
---

Your Markdown content here...
```

Required fields: `title`, `type` (page or post), `template`.

Optional fields: `date`, `tags`.
