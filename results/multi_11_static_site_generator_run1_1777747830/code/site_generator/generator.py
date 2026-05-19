"""Site generator: orchestrates parsing, conversion, and output."""

import os
import shutil
import datetime
import sys
from typing import Dict, List

from .parser import parse_file, validate_front_matter
from .markdown import to_html
from .template import render


def build_site(
    content_dir: str,
    templates_dir: str,
    static_dir: str,
    output_dir: str,
    verbose: bool = False,
) -> None:
    """Build the complete static site.

    Args:
        content_dir: Path to content/ directory.
        templates_dir: Path to templates/ directory.
        static_dir: Path to static/ directory.
        output_dir: Path to output/ directory.
        verbose: Print progress messages.
    """
    # Ensure output directory exists
    try:
        os.makedirs(output_dir, exist_ok=True)
    except PermissionError:
        print(
            f"Error: Cannot create/write to output directory: {output_dir}\n"
            "Check permissions or use --clean to remove it first."
        )
        sys.exit(1)

    # 1. Scan content directory for .md files
    content_files = []
    for root, dirs, files in os.walk(content_dir):
        for fname in files:
            if fname.endswith(".md"):
                content_files.append(os.path.join(root, fname))

    if verbose:
        print(f"Found {len(content_files)} content files.")

    # 2. Parse all content files
    pages = []  # type: page
    posts = []  # type: post

    for filepath in content_files:
        front_matter, body = parse_file(filepath)

        # Validate
        errors = validate_front_matter(front_matter, filepath)
        if errors:
            for err in errors:
                print(f"WARNING: {err}")
            continue

        # Compute relative path info
        rel_path = os.path.relpath(filepath, content_dir)
        # Derive slug: remove .md extension, handle root index.md
        slug = _get_slug(rel_path)

        item = {
            "filepath": filepath,
            "front_matter": front_matter,
            "body": body,
            "slug": slug,
        }

        content_type = front_matter.get("type", "page")
        if content_type == "post":
            posts.append(item)
        else:
            pages.append(item)

    if verbose:
        print(f"  Pages: {len(pages)}, Posts: {len(posts)}")

    # 3. Build navigation HTML
    nav_html = _build_navigation(pages)

    # 4. Convert all content and write output files
    # Process pages
    for item in pages:
        _write_content_item(
            item, templates_dir, output_dir, nav_html, verbose
        )

    # Process posts
    for item in posts:
        _write_content_item(
            item, templates_dir, output_dir, nav_html, verbose
        )

    # 5. Build blog index
    _build_blog_index(posts, templates_dir, output_dir, nav_html, verbose)

    # 6. Copy static assets
    if os.path.isdir(static_dir):
        if verbose:
            print(f"Copying static assets from {static_dir} to {output_dir}...")
        shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)

    if verbose:
        print("Site build complete!")


def _get_slug(rel_path: str) -> str:
    """Derive URL slug from relative file path.

    E.g., 'index.md' -> '' (root)
          'about.md' -> 'about'
          'posts/post1.md' -> 'posts/post1'
    """
    # Remove .md extension
    slug = rel_path
    if slug.endswith(".md"):
        slug = slug[:-3]

    # On Windows, fix backslashes
    slug = slug.replace("\\", "/")

    # Special case: index at root becomes empty string
    if slug == "index":
        slug = ""

    return slug


def _build_navigation(pages: List[Dict]) -> str:
    """Build navigation HTML from pages list."""
    if not pages:
        return "<nav><ul></ul></nav>"

    items = []
    for page in pages:
        title = page["front_matter"].get("title", page["slug"] or "Home")
        slug = page["slug"]
        # Determine URL
        if slug == "":
            url = "/"
        else:
            url = f"/{slug}/"
        items.append(f'<li><a href="{url}">{title}</a></li>')

    return "<nav>\n<ul>\n" + "\n".join(items) + "\n</ul>\n</nav>"


def _write_content_item(
    item: Dict,
    templates_dir: str,
    output_dir: str,
    nav_html: str,
    verbose: bool = False,
) -> None:
    """Convert a single content item and write to output."""
    front_matter = item["front_matter"]
    body = item["body"]
    slug = item["slug"]

    # Convert Markdown to HTML
    content_html = to_html(body)

    # Load template
    template_name = front_matter.get("template", "page.html")
    template_path = os.path.join(templates_dir, template_name)

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()
    except FileNotFoundError:
        print(f"WARNING: Template '{template_name}' not found, using fallback.")
        template_str = (
            "<html><body>"
            "{{navigation}}"
            "<h1>{{title}}</h1>"
            "{{content}}"
            "</body></html>"
        )

    # Prepare variables
    variables = dict(front_matter)
    variables["content"] = content_html
    variables["navigation"] = nav_html

    # Handle tags: join list to string if needed
    if "tags" in variables and isinstance(variables["tags"], list):
        variables["tags"] = ", ".join(variables["tags"])

    # Render
    rendered = render(template_str, variables)

    # Determine output path
    if slug == "":
        out_path = os.path.join(output_dir, "index.html")
    else:
        out_dir = os.path.join(output_dir, slug)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "index.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    if verbose:
        print(f"  Wrote: {out_path}")


def _build_blog_index(
    posts: List[Dict],
    templates_dir: str,
    output_dir: str,
    nav_html: str,
    verbose: bool = False,
) -> None:
    """Build the blog index page."""
    if not posts:
        if verbose:
            print("No posts found, skipping blog index.")
        return

    # Sort posts by date descending
    def _parse_date(post: Dict) -> datetime.date:
        date_str = post["front_matter"].get("date", "1970-01-01")
        try:
            return datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return datetime.date(1970, 1, 1)

    sorted_posts = sorted(posts, key=_parse_date, reverse=True)

    # Build post list HTML
    post_items = []
    for post in sorted_posts:
        title = post["front_matter"].get("title", "Untitled")
        date_str = post["front_matter"].get("date", "")
        slug = post["slug"]
        url = f"/{slug}/"

        post_items.append(
            f'<li><a href="{url}">{title}</a>'
            f'{" — " + date_str if date_str else ""}</li>'
        )

    posts_html = "<ul>\n" + "\n".join(post_items) + "\n</ul>"

    # Load blog index template
    template_path = os.path.join(templates_dir, "blog_index.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()
    except FileNotFoundError:
        print("WARNING: blog_index.html template not found, using fallback.")
        template_str = (
            "<html><body>"
            "{{navigation}}"
            "<h1>Blog</h1>"
            "{{posts}}"
            "</body></html>"
        )

    variables = {
        "posts": posts_html,
        "navigation": nav_html,
        "title": "Blog",
    }

    rendered = render(template_str, variables)

    out_dir = os.path.join(output_dir, "blog")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    if verbose:
        print(f"  Wrote blog index: {out_path}")
