"""Site builder: orchestrates reading content, applying templates, and generating output."""

import os
import shutil
import re
from datetime import datetime

from .front_matter import parse_front_matter
from .markdown import markdown_to_html
from .template import load_template


class SiteBuilder:
    """Builds a static site from content, templates, and static assets."""

    def __init__(self, content_dir: str, templates_dir: str, static_dir: str, output_dir: str):
        self.content_dir = content_dir
        self.templates_dir = templates_dir
        self.static_dir = static_dir
        self.output_dir = output_dir
        self.pages = []   # Non-blog pages
        self.posts = []   # Blog posts
        self._content_cache = {}  # slug -> content_html

    def build(self) -> None:
        """Run the full site build."""
        self.pages = []
        self.posts = []
        self._content_cache = {}

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Discover and process all content files - first pass collects metadata
        self._discover_content()

        # Sort posts by date (newest first)
        self.posts.sort(key=lambda p: p.get('date', ''), reverse=True)

        # Now render all pages with nav
        self._render_all_pages()

        # Generate blog index if there are posts
        if self.posts:
            self._generate_blog_index()

        # Copy static assets
        self._copy_static()

    def _discover_content(self) -> None:
        """Walk through content directory, parse all .md files, cache content."""
        for root, dirs, files in os.walk(self.content_dir):
            for filename in files:
                if not filename.endswith('.md'):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.content_dir)

                name_no_ext = os.path.splitext(filename)[0]
                rel_dir = os.path.dirname(rel_path)

                # Build slug and output path
                if name_no_ext == 'index':
                    slug = rel_dir.replace(os.sep, '/') if rel_dir else ''
                    out_dir = os.path.join(self.output_dir, rel_dir) if rel_dir else self.output_dir
                else:
                    subdir = rel_dir.replace(os.sep, '/')
                    slug = f'{subdir}/{name_no_ext}' if subdir else name_no_ext
                    out_dir = os.path.join(self.output_dir, rel_dir, name_no_ext)

                out_file = os.path.join(out_dir, 'index.html')

                # Read and parse content
                with open(filepath, 'r', encoding='utf-8') as f:
                    raw_text = f.read()

                metadata, body = parse_front_matter(raw_text)
                content_html = markdown_to_html(body)

                # Determine template
                template_name = metadata.get('template', 'base')

                # Store page info
                is_post = 'date' in metadata

                page_info = {
                    'title': metadata.get('title', name_no_ext.replace('-', ' ').title()),
                    'date': metadata.get('date', ''),
                    'tags': metadata.get('tags', []),
                    'slug': slug,
                    'template': template_name,
                    'out_file': out_file,
                    'is_post': is_post,
                }

                # Cache content HTML
                self._content_cache[slug] = content_html

                if is_post:
                    self.posts.append(page_info)
                else:
                    self.pages.append(page_info)

    def _render_all_pages(self) -> None:
        """Render all pages and posts with navigation."""
        nav_html = self._build_nav_html()

        all_items = self.posts + self.pages
        for info in all_items:
            slug = info['slug']
            content_html = self._content_cache.get(slug, '')
            template_name = info.get('template', 'base')

            template = self._load_template(template_name)

            variables = {
                'title': info['title'],
                'date': info.get('date', ''),
                'tags': info.get('tags', []),
                'template': template_name,
                'slug': slug,
                'navigation': nav_html,
                'pages': self.pages,
                'posts': self.posts,
            }

            rendered = template.render(variables, content_html)

            out_file = info['out_file']
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(rendered)

            print(f"  Generated: {slug or '(root)'}/ -> {out_file}")

    def _load_template(self, template_name: str):
        """Load a template, falling back to base.html if not found."""
        template_path = os.path.join(self.templates_dir, f'{template_name}.html')
        if not os.path.exists(template_path):
            print(f"Warning: Template '{template_name}.html' not found, falling back to base.html")
            template_path = os.path.join(self.templates_dir, 'base.html')
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"No template found: {template_path}")
        return load_template(template_path)

    def _build_nav_html(self) -> str:
        """Build navigation HTML from pages."""
        links = []

        # Blog link if there are posts
        if self.posts:
            links.append('<li><a href="/blog/">Blog</a></li>')

        for page in self.pages:
            title = page.get('title', 'Untitled')
            slug = page.get('slug', '')
            links.append(f'<li><a href="/{slug}/">{title}</a></li>')

        if not links:
            return ''

        return '<nav><ul>' + ''.join(links) + '</ul></nav>'

    def _generate_blog_index(self) -> None:
        """Generate a blog index page listing all posts sorted by date."""
        template = self._load_template('base')

        # Build posts list HTML
        posts_html = '<h1>Blog</h1>\n<ul class="post-list">\n'
        for post in self.posts:
            title = post.get('title', 'Untitled')
            date = post.get('date', '')
            slug = post.get('slug', '')
            posts_html += f'  <li><span class="post-date">{date}</span> <a href="/{slug}/">{title}</a></li>\n'
        posts_html += '</ul>'

        nav_html = self._build_nav_html()

        variables = {
            'title': 'Blog',
            'navigation': nav_html,
            'pages': self.pages,
            'posts': self.posts,
        }

        rendered = template.render(variables, posts_html)

        out_dir = os.path.join(self.output_dir, 'blog')
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, 'index.html')
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(rendered)

        print(f"  Generated: blog/ -> {out_file}")

    def _copy_static(self) -> None:
        """Copy static assets from static/ to output/."""
        if not os.path.isdir(self.static_dir):
            return

        for root, dirs, files in os.walk(self.static_dir):
            for filename in files:
                src = os.path.join(root, filename)
                rel = os.path.relpath(src, self.static_dir)
                dst = os.path.join(self.output_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  Copied: {rel}")

    def clean(self) -> None:
        """Remove the output directory."""
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)
            print(f"Cleaned: {self.output_dir}")
