"""Site builder: orchestrates reading content, applying templates,
generating output, building blog index and navigation."""

import os
import re
import shutil
from pathlib import Path

from . import frontmatter as fm
from . import markdown as md


def _slugify(title: str) -> str:
    """Create a URL-safe slug from a title string."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    if not slug:
        slug = 'untitled'
    return slug


def _replace_placeholders(template: str, variables: dict) -> str:
    """Replace {{variable}} placeholders in template with values.

    Args:
        template: The template string containing placeholders.
        variables: Dict mapping placeholder names to replacement strings.

    Returns:
        Template string with placeholders replaced.
    """
    def replacer(match):
        key = match.group(1)
        return variables.get(key, '')

    return re.sub(r'\{\{(\w+)\}\}', replacer, template)


def _load_template(templates_dir: str, template_name: str) -> str:
    """Load a template file by name.

    Args:
        templates_dir: Path to the templates directory.
        template_name: Name of the template file (e.g. 'post.html').

    Returns:
        The template contents as a string.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = os.path.join(templates_dir, template_name)
    if not os.path.isfile(template_path):
        raise FileNotFoundError(
            f"Template '{template_name}' not found in {templates_dir}"
        )
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def _scan_content(content_dir: str) -> list:
    """Recursively scan content directory for .md files.

    Args:
        content_dir: Path to the content directory.

    Returns:
        List of dicts with keys: path, filename, frontmatter, body.
    """
    results = []
    for root, dirs, files in os.walk(content_dir):
        for fname in files:
            if fname.endswith('.md'):
                full_path = os.path.join(root, fname)
                with open(full_path, 'r', encoding='utf-8') as f:
                    raw = f.read()

                frontmatter_dict, body = fm.split_frontmatter(raw)

                # Set defaults
                if 'title' not in frontmatter_dict:
                    frontmatter_dict['title'] = fname[:-3].replace('-', ' ').title()
                if 'template' not in frontmatter_dict:
                    frontmatter_dict['template'] = 'page'

                results.append({
                    'path': full_path,
                    'filename': fname,
                    'frontmatter': frontmatter_dict,
                    'body': body,
                })
    return results


def _build_navigation(pages: list) -> str:
    """Build navigation HTML from pages and blog link.

    Args:
        pages: List of content items with template != 'post'.

    Returns:
        HTML string for the navigation menu.
    """
    items = []
    for page in pages:
        title = page['frontmatter'].get('title', 'Untitled')
        slug = _slugify(title)
        items.append(f'<li><a href="/{slug}/index.html">{title}</a></li>')

    # Add blog link
    items.append('<li><a href="/blog/index.html">Blog</a></li>')

    return '<nav><ul>' + ''.join(items) + '</ul></nav>'


def _build_blog_index(posts: list, templates_dir: str, navigation_html: str,
                      output_dir: str):
    """Generate the blog index page.

    Args:
        posts: List of post content items sorted by date descending.
        templates_dir: Path to templates directory.
        navigation_html: Navigation menu HTML string.
        output_dir: Path to output directory.
    """
    # Build posts list HTML
    post_items = []
    for post in posts:
        fm_dict = post['frontmatter']
        title = fm_dict.get('title', 'Untitled')
        date = fm_dict.get('date', '')
        slug = _slugify(title)
        post_items.append(
            f'<li><a href="/blog/{slug}/index.html">{title}</a>'
            + (f' - {date}' if date else '')
            + '</li>'
        )

    posts_html = '<ul>' + ''.join(post_items) + '</ul>'

    # Load blog template
    blog_template = _load_template(templates_dir, 'blog.html')

    variables = {
        'title': 'Blog',
        'posts': posts_html,
        'navigation': navigation_html,
        'content': '',
    }

    html = _replace_placeholders(blog_template, variables)

    # Write blog index
    blog_dir = os.path.join(output_dir, 'blog')
    os.makedirs(blog_dir, exist_ok=True)
    index_path = os.path.join(blog_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)


def build(content_dir: str, templates_dir: str, static_dir: str,
          output_dir: str, clean: bool = False):
    """Build the static site.

    Args:
        content_dir: Path to content/ directory.
        templates_dir: Path to templates/ directory.
        static_dir: Path to static/ directory.
        output_dir: Path to output/ directory.
        clean: If True, remove output directory before building.
    """
    # Clean output if requested
    if clean and os.path.isdir(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Scan all content
    all_content = _scan_content(content_dir)

    # Separate posts and pages
    posts = [
        c for c in all_content
        if c['frontmatter'].get('template') == 'post'
    ]
    pages = [
        c for c in all_content
        if c['frontmatter'].get('template') != 'post'
    ]

    # Sort posts by date descending
    posts.sort(
        key=lambda p: p['frontmatter'].get('date', ''),
        reverse=True
    )

    # Build navigation (from pages, plus blog link)
    navigation_html = _build_navigation(pages)

    # Generate each page/post
    for item in all_content:
        fm_dict = item['frontmatter']
        body = item['body']
        template_name = fm_dict.get('template', 'page') + '.html'

        # Convert body Markdown to HTML
        content_html = md.convert(body)

        # Load template
        template = _load_template(templates_dir, template_name)

        # Determine slug and output path
        title = fm_dict.get('title', 'Untitled')
        slug = _slugify(title)

        if fm_dict.get('template') == 'post':
            out_subdir = os.path.join(output_dir, 'blog', slug)
        else:
            out_subdir = os.path.join(output_dir, slug)

        os.makedirs(out_subdir, exist_ok=True)

        # Prepare variables for template
        variables = dict(fm_dict)
        variables['content'] = content_html
        variables['navigation'] = navigation_html

        html = _replace_placeholders(template, variables)

        # Write index.html
        out_path = os.path.join(out_subdir, 'index.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)

    # Generate blog index
    _build_blog_index(posts, templates_dir, navigation_html, output_dir)

    # Copy static assets
    if os.path.isdir(static_dir):
        dest_static = os.path.join(output_dir, 'static')
        if os.path.exists(dest_static):
            shutil.rmtree(dest_static, ignore_errors=True)
        shutil.copytree(static_dir, dest_static)

    print(f"Site built successfully in '{output_dir}'")
