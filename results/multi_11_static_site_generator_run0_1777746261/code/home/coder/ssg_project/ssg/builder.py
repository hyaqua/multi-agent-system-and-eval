"""Site builder: core generation logic.

Reads content/, applies templates, converts Markdown, copies static assets,
and writes the complete site to output/.
"""

import shutil
from datetime import datetime
from pathlib import Path

from ssg.converter import markdown_to_html
from ssg.parser import parse_content_file
from ssg.template_engine import TemplateEngine


def build_site(work_dir: Path, clean: bool = False) -> None:
    """Main build function.

    Args:
        work_dir: Root working directory containing content/, templates/,
                  static/, and output/.
        clean: If True, remove output/ before building.
    """
    content_dir = work_dir / "content"
    templates_dir = work_dir / "templates"
    static_dir = work_dir / "static"
    output_dir = work_dir / "output"

    # Validate required directories
    if not content_dir.exists():
        raise FileNotFoundError(f"Content directory not found: {content_dir}")
    if not templates_dir.exists():
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

    # Clean output if requested
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    engine = TemplateEngine(templates_dir)

    # Parse all content files
    all_content: list[dict] = []
    for md_file in sorted(content_dir.glob("*.md")):
        content = parse_content_file(md_file)
        all_content.append(content)

    # Separate pages (no date) and posts (with date)
    pages: list[dict] = []
    posts: list[dict] = []
    for c in all_content:
        if "date" in c.get("metadata", {}) and c["metadata"]["date"]:
            posts.append(c)
        else:
            pages.append(c)

    # Sort posts by date descending
    posts.sort(
        key=lambda p: _parse_date(p["metadata"].get("date", "")),
        reverse=True,
    )

    # Generate navigation HTML from pages
    navigation_html = _build_navigation(pages)

    # Build blog index
    blog_index_html = _build_blog_index(posts, engine, navigation_html)
    blog_index_dir = output_dir / "blog"
    blog_index_dir.mkdir(parents=True, exist_ok=True)
    (blog_index_dir / "index.html").write_text(blog_index_html, encoding="utf-8")

    # Build each page
    for page in pages:
        _build_content(
            content=page,
            output_dir=output_dir,
            engine=engine,
            navigation_html=navigation_html,
            is_post=False,
        )

    # Build each post
    for post in posts:
        _build_content(
            content=post,
            output_dir=output_dir,
            engine=engine,
            navigation_html=navigation_html,
            is_post=True,
        )

    # Copy static assets
    if static_dir.exists():
        _copy_static(static_dir, output_dir)

    print(f"Site built successfully at: {output_dir.resolve()}")
    print(f"  Pages: {len(pages)}")
    print(f"  Posts: {len(posts)}")


def _parse_date(date_str: str) -> datetime:
    """Parse a date string, returning datetime.min on failure."""
    if not date_str:
        return datetime.min
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return datetime.min


def _build_navigation(pages: list[dict]) -> str:
    """Build navigation HTML from the page list.

    Includes links to all pages plus the blog index.
    """
    links: list[str] = []
    # Always add a link to the blog index
    links.append('<a href="/blog/">Blog</a>')

    for page in pages:
        slug = page["slug"]
        title = page["metadata"].get("title", slug.replace("-", " ").title())
        links.append(f'<a href="/{slug}/">{title}</a>')

    return "\n".join(links)


def _build_blog_index(posts: list[dict], engine: TemplateEngine, navigation_html: str) -> str:
    """Build the blog index page (output/blog/index.html)."""
    if not posts:
        post_items = "<li>No posts yet.</li>"
    else:
        post_items = ""
        for post in posts:
            slug = post["slug"]
            title = post["metadata"].get("title", slug)
            date_str = post["metadata"].get("date", "")
            post_items += (
                f'<li><a href="/blog/{slug}/">{title}</a>'
                f" – {date_str}</li>\n"
            )

    data = {
        "title": "Blog",
        "navigation": navigation_html,
        "content": f"<ul>{post_items}</ul>",
    }
    return engine.render("blog.html", data)


def _build_content(
    content: dict,
    output_dir: Path,
    engine: TemplateEngine,
    navigation_html: str,
    is_post: bool,
) -> None:
    """Build a single page or post and write it to the output directory.

    Pages go to: output/<slug>/index.html
    Posts go to: output/blog/<slug>/index.html
    """
    slug = content["slug"]
    metadata = content["metadata"]
    body_html = markdown_to_html(content["body"])

    template_name = metadata.get("template", "base.html")

    data: dict[str, str] = {
        "title": metadata.get("title", slug.replace("-", " ").title()),
        "navigation": navigation_html,
        "content": body_html,
    }

    # Add optional metadata
    if "date" in metadata and metadata["date"]:
        data["date"] = metadata["date"]
    if "tags" in metadata and metadata["tags"]:
        tags_val = metadata["tags"]
        if isinstance(tags_val, list):
            data["tags"] = ", ".join(tags_val)
        else:
            data["tags"] = str(tags_val)

    rendered = engine.render(template_name, data)

    # Determine output path
    if is_post:
        out_path = output_dir / "blog" / slug / "index.html"
    else:
        out_path = output_dir / slug / "index.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


def _copy_static(static_dir: Path, output_dir: Path) -> None:
    """Copy static assets from static/ to output/, preserving directory structure."""
    for item in static_dir.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(static_dir)
            dest = output_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
