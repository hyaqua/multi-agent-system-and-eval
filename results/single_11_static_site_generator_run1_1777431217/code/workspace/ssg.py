#!/usr/bin/env python3
"""
Static Site Generator - Converts Markdown-like content + HTML templates into a full static website.

Usage:
    python ssg.py              # Build the site
    python ssg.py --clean      # Clean output then build
    python ssg.py --serve      # Build and serve on localhost
    python ssg.py --clean --serve
"""

import os
import sys
import shutil
import re
import http.server
import socketserver
import functools
from datetime import datetime
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "content"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"

SERVE_HOST = "0.0.0.0"
SERVE_PORT = 8765


# ── Front Matter Parser ───────────────────────────────────────────────────────

def parse_front_matter(text: str):
    """
    Parse YAML-style front matter delimited by --- lines at the start of text.
    Returns (metadata_dict, body_text).
    Handles: title, date, tags, template
    Also supports lists (tags as comma-separated or YAML list with - items).
    """
    text = text.strip()
    metadata = {}
    body = text

    # Check for front matter delimited by ---
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            metadata = _parse_front_matter_lines(fm_text)

    return metadata, body


def _parse_front_matter_lines(fm_text: str) -> dict:
    """Parse individual front matter lines."""
    metadata = {}
    current_key = None
    current_list = []

    for line in fm_text.split("\n"):
        # Check for list item continuation
        if line.strip().startswith("- ") and current_key:
            current_list.append(line.strip()[2:].strip())
            continue

        # Flush previous list if any
        if current_key and current_list:
            metadata[current_key] = current_list
            current_list = []
            current_key = None

        # Key: value line
        match = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()

            # Remove surrounding quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            # Check if this is a list indicator (value is empty, next lines might be - items)
            if value == "":
                current_key = key
                current_list = []
            else:
                metadata[key] = value
                current_key = None

    # Flush remaining list
    if current_key and current_list:
        metadata[current_key] = current_list

    # Parse tags: if it's a comma-separated string, split it
    if "tags" in metadata and isinstance(metadata["tags"], str):
        metadata["tags"] = [t.strip() for t in metadata["tags"].split(",") if t.strip()]

    return metadata


# ── Markdown to HTML Converter ────────────────────────────────────────────────

def markdown_to_html(text: str) -> str:
    """
    Convert basic Markdown to HTML. Supports:
      - Headings (# through ######)
      - Bold (**text**) and italic (*text*)
      - Inline code (`code`)
      - Links [text](url)
      - Images ![alt](url)
      - Unordered lists (- or *)
      - Ordered lists (1. 2. ...)
      - Fenced code blocks (```)
      - Paragraphs
      - Horizontal rules (---, ***, ___)
    """
    lines = text.split("\n")
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            fence = line.strip()[:3]
            lang = line.strip()[3:].strip()
            i += 1
            code_lines = []
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    break
                code_lines.append(lines[i])
                i += 1
            code_html = _escape_html("\n".join(code_lines))
            cls = f' class="language-{lang}"' if lang else ""
            html_parts.append(f"<pre><code{cls}>{code_html}</code></pre>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line.strip()):
            html_parts.append("<hr>")
            i += 1
            continue

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            html_parts.append(f"<h{level}>{_inline_markdown(content)}</h{level}>")
            i += 1
            continue

        # Empty line
        if line.strip() == "":
            i += 1
            continue

        # Check for list items (unordered or ordered)
        # We gather consecutive list items
        if re.match(r'^(\s*[-*]\s+|\s*\d+\.\s+)', line):
            list_items = []
            list_type = None  # 'ul' or 'ol'

            while i < len(lines):
                ul_match = re.match(r'^(\s*)[-*]\s+(.+)', lines[i])
                ol_match = re.match(r'^(\s*)\d+\.\s+(.+)', lines[i])

                if ul_match:
                    if list_type is None:
                        list_type = "ul"
                    if list_type == "ul":
                        list_items.append(ul_match.group(2))
                        i += 1
                        continue
                    else:
                        break
                elif ol_match:
                    if list_type is None:
                        list_type = "ol"
                    if list_type == "ol":
                        list_items.append(ol_match.group(2))
                        i += 1
                        continue
                    else:
                        break
                elif lines[i].strip() == "":
                    # Check if next non-empty line is a list item
                    peek = i + 1
                    while peek < len(lines) and lines[peek].strip() == "":
                        peek += 1
                    if peek < len(lines) and re.match(r'^(\s*[-*]\s+|\s*\d+\.\s+)', lines[peek]):
                        i = peek
                        continue
                    else:
                        break
                else:
                    break

            if list_items:
                tag = list_type or "ul"
                items_html = "".join(f"<li>{_inline_markdown(item)}</li>" for item in list_items)
                html_parts.append(f"<{tag}>{items_html}</{tag}>")
            continue

        # Paragraph: collect lines until blank line, heading, list, code fence, or HR
        para_lines = []
        while i < len(lines) and lines[i].strip() != "":
            if re.match(r'^(#{1,6}\s+|```|[-*_]{3,}\s*$)', lines[i].strip()):
                break
            if re.match(r'^(\s*[-*]\s+|\s*\d+\.\s+)', lines[i]):
                break
            para_lines.append(lines[i].strip())
            i += 1

        if para_lines:
            para_text = " ".join(para_lines)
            html_parts.append(f"<p>{_inline_markdown(para_text)}</p>")

    return "\n".join(html_parts)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _inline_markdown(text: str) -> str:
    """Process inline Markdown: bold, italic, code, links, images."""
    # Store code spans to protect them
    code_spans = {}

    def _save_code(m):
        placeholder = f"__CODE_{len(code_spans)}__"
        code_spans[placeholder] = f"<code>{_escape_html(m.group(1))}</code>"
        return placeholder

    text = re.sub(r'`([^`]+)`', _save_code, text)

    # Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', text)

    # Links: [text](url)
    text = re.sub(r'\[([^\]]*)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)

    # Restore code spans
    for placeholder, code_html in code_spans.items():
        text = text.replace(placeholder, code_html)

    return text


# ── Template Engine ───────────────────────────────────────────────────────────

def load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_template(template_str: str, variables: dict) -> str:
    """Replace {{variable}} placeholders with values from the dict."""
    result = template_str

    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        # Convert lists to HTML strings
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif value is None:
            value = ""
        else:
            value = str(value)
        result = result.replace(placeholder, value)

    # Remove any remaining unmatched placeholders (optional: leave as-is or remove)
    # We'll leave them so user can see if something is missing
    return result


# ── Content Loading ───────────────────────────────────────────────────────────

def load_content_files(subdir: str = "") -> list:
    """
    Load all .md files from content/ (or content/subdir).
    Returns list of dicts with keys: metadata, body, source_path, slug
    """
    search_dir = CONTENT_DIR / subdir if subdir else CONTENT_DIR
    if not search_dir.exists():
        return []

    items = []
    for md_file in sorted(search_dir.rglob("*.md")):
        rel = md_file.relative_to(CONTENT_DIR)
        # Determine slug from relative path
        slug = str(rel.with_suffix(""))
        if slug.endswith("/index"):
            slug = slug[:-6]
        if slug == "index":
            slug = ""
        # For pages, strip the "pages/" prefix so they appear at root level
        if subdir == "pages" and slug.startswith("pages/"):
            slug = slug[6:]

        raw = md_file.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(raw)
        html_body = markdown_to_html(body)

        items.append({
            "metadata": metadata,
            "body": body,
            "html_body": html_body,
            "source_path": md_file,
            "slug": slug,
            "type": subdir if subdir else _guess_type(rel),
        })

    return items


def _guess_type(rel_path) -> str:
    """Guess content type from path."""
    p = str(rel_path)
    if p.startswith("posts") or p.startswith("post"):
        return "posts"
    return "pages"


# ── Site Generation ───────────────────────────────────────────────────────────

def generate_site():
    """Main generation function."""
    print("Building site...")

    # Clean output if needed
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load all content
    posts = load_content_files("posts")
    pages = load_content_files("pages")

    # Also load any .md files directly in content/ that aren't in posts/ or pages/
    root_items = load_content_files("")
    # Filter out items already in posts/pages
    root_items = [item for item in root_items
                  if not str(item["source_path"].relative_to(CONTENT_DIR)).startswith(("posts/", "pages/"))]
    pages.extend(root_items)

    # Sort posts by date (newest first)
    for post in posts:
        date_str = post["metadata"].get("date", "")
        try:
            post["_date_obj"] = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, KeyError):
            post["_date_obj"] = datetime(1900, 1, 1)

    posts.sort(key=lambda p: p["_date_obj"], reverse=True)

    # Build navigation from pages
    nav_items = []
    for page in pages:
        title = page["metadata"].get("title", page["slug"] or "Home")
        slug = page["slug"]
        url = f"/{slug}/" if slug else "/"
        nav_items.append({"title": title, "url": url})

    # Also add blog to nav
    nav_items.append({"title": "Blog", "url": "/posts/"})

    # Sort nav: home first, then alphabetically
    nav_html = _build_nav_html(nav_items)

    # Collect all dates/categories for blog index
    all_posts_data = []
    for post in posts:
        title = post["metadata"].get("title", post["slug"])
        date_str = post["metadata"].get("date", "")
        slug = post["slug"]
        url = f"/{slug}/" if slug else "/"
        tags = post["metadata"].get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        all_posts_data.append({
            "title": title,
            "date": date_str,
            "url": url,
            "tags": tags,
        })

    # Generate individual post pages
    for post in posts:
        _generate_content_page(post, nav_html, "post")

    # Generate individual pages
    for page in pages:
        _generate_content_page(page, nav_html, "page")

    # Generate blog index
    _generate_blog_index(posts, nav_html, all_posts_data)

    # Generate home page (index)
    _generate_home_page(posts, pages, nav_html)

    # Copy static assets
    _copy_static()

    print(f"Site generated in {OUTPUT_DIR}")


def _build_nav_html(nav_items: list) -> str:
    """Build HTML navigation from nav items."""
    parts = ["<nav><ul>"]
    for item in nav_items:
        parts.append(f'<li><a href="{item["url"]}">{item["title"]}</a></li>')
    parts.append("</ul></nav>")
    return "\n".join(parts)


def _generate_content_page(item: dict, nav_html: str, content_type: str):
    """Generate a single content page (post or page)."""
    metadata = item["metadata"]
    template_name = metadata.get("template", "default.html")
    title = metadata.get("title", item["slug"] or "Untitled")
    date_str = metadata.get("date", "")
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        template_str = load_template(template_name)
    except FileNotFoundError:
        template_str = load_template("default.html")

    # Format date nicely
    formatted_date = ""
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = dt.strftime("%B %d, %Y")
        except ValueError:
            formatted_date = date_str

    tags_html = ""
    if tags:
        tag_spans = [f'<span class="tag">{t}</span>' for t in tags]
        tags_html = '<div class="tags">' + " ".join(tag_spans) + "</div>"

    variables = {
        "title": title,
        "date": date_str,
        "formatted_date": formatted_date,
        "tags": ", ".join(tags) if tags else "",
        "tags_html": tags_html,
        "content": item["html_body"],
        "nav": nav_html,
        "type": content_type,
    }

    html = render_template(template_str, variables)

    # Write output
    slug = item["slug"]
    if slug:
        out_dir = OUTPUT_DIR / slug
    else:
        out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"  → {out_file.relative_to(OUTPUT_DIR)}")


def _generate_blog_index(posts: list, nav_html: str, all_posts_data: list):
    """Generate the blog index page."""
    template_name = "blog.html"
    try:
        template_str = load_template(template_name)
    except FileNotFoundError:
        template_str = load_template("default.html")

    # Build posts listing HTML
    posts_html_parts = ['<div class="post-list">']
    for pd in all_posts_data:
        posts_html_parts.append(f"""
        <article class="post-item">
            <h2><a href="{pd['url']}">{pd['title']}</a></h2>
            <time datetime="{pd['date']}">{pd['date']}</time>
            <div class="tags">{" ".join(f'<span class="tag">{t}</span>' for t in pd['tags'])}</div>
        </article>""")
    posts_html_parts.append('</div>')
    posts_html = "\n".join(posts_html_parts)

    variables = {
        "title": "Blog",
        "content": posts_html,
        "nav": nav_html,
        "date": "",
        "formatted_date": "",
        "tags": "",
        "tags_html": "",
        "type": "blog_index",
    }

    html = render_template(template_str, variables)

    out_dir = OUTPUT_DIR / "posts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"  → {out_file.relative_to(OUTPUT_DIR)}")


def _generate_home_page(posts: list, pages: list, nav_html: str):
    """Generate the home page."""
    try:
        template_str = load_template("home.html")
    except FileNotFoundError:
        template_str = load_template("default.html")

    # Show recent posts
    recent_html = '<div class="recent-posts"><h2>Recent Posts</h2><ul>'
    for post in posts[:5]:
        title = post["metadata"].get("title", post["slug"])
        date_str = post["metadata"].get("date", "")
        slug = post["slug"]
        url = f"/{slug}/" if slug else "/"
        recent_html += f'<li><a href="{url}">{title}</a> <span class="date">{date_str}</span></li>'
    recent_html += '</ul></div>'

    variables = {
        "title": "Home",
        "content": f"<h1>Welcome</h1>{recent_html}",
        "nav": nav_html,
        "date": "",
        "formatted_date": "",
        "tags": "",
        "tags_html": "",
        "type": "home",
    }

    html = render_template(template_str, variables)

    out_file = OUTPUT_DIR / "index.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"  → {out_file.relative_to(OUTPUT_DIR)}")


def _copy_static():
    """Copy static assets to output directory."""
    if not STATIC_DIR.exists():
        return

    for item in STATIC_DIR.rglob("*"):
        if item.is_file():
            rel = item.relative_to(STATIC_DIR)
            dest = OUTPUT_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            print(f"  → {dest.relative_to(OUTPUT_DIR)}")


# ── HTTP Server ───────────────────────────────────────────────────────────────

def serve_site():
    """Start a local HTTP server to preview the generated site."""
    if not OUTPUT_DIR.exists() or not any(OUTPUT_DIR.iterdir()):
        print("No generated site found. Building first...")
        generate_site()

    os.chdir(str(OUTPUT_DIR))

    handler = http.server.SimpleHTTPRequestHandler

    # Quiet logging
    class QuietHandler(handler):
        def log_message(self, format, *args):
            pass  # Silent

    with socketserver.TCPServer((SERVE_HOST, SERVE_PORT), QuietHandler) as httpd:
        print(f"\n🌐 Server running at http://{SERVE_HOST}:{SERVE_PORT}/")
        print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    do_clean = "--clean" in args
    do_serve = "--serve" in args

    if do_clean and OUTPUT_DIR.exists():
        print(f"Cleaning {OUTPUT_DIR}...")
        shutil.rmtree(OUTPUT_DIR)

    generate_site()

    if do_serve:
        serve_site()


if __name__ == "__main__":
    main()
