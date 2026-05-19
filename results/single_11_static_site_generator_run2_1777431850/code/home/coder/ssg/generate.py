#!/usr/bin/env python3
"""
Static Site Generator
Reads Markdown-like content files with YAML-style front matter,
applies HTML templates, and outputs a complete static website.
"""

import os
import sys
import re
import shutil
import argparse
import http.server
import socketserver
from datetime import datetime


# ─────────────────────────────────────────────
#  FRONT MATTER PARSER
# ─────────────────────────────────────────────

def parse_front_matter(text):
    """
    Parse YAML-style front matter delimited by --- lines.
    Returns (metadata_dict, body_text).
    """
    text = text.strip()
    if not text.startswith('---'):
        return {}, text

    # Find the closing ---
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text

    front = parts[1].strip()
    body = parts[2].strip()

    metadata = {}
    for line in front.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Match key: value
        m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+)$', line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            # Remove surrounding quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            metadata[key] = value

    return metadata, body


# ─────────────────────────────────────────────
#  MARKDOWN TO HTML CONVERTER
# ─────────────────────────────────────────────

def markdown_to_html(text):
    """
    Convert basic Markdown to HTML.
    Supports: headings, bold, italic, links, unordered lists,
    ordered lists, code blocks (fenced), inline code, paragraphs.
    """
    lines = text.split('\n')
    output = []
    i = 0
    in_code_block = False
    code_block_lang = ''
    code_block_content = []
    in_list = None  # 'ul' or 'ol'
    list_buffer = []

    def flush_list():
        nonlocal in_list, list_buffer
        if in_list and list_buffer:
            tag = in_list
            output.append(f'<{tag}>')
            for item in list_buffer:
                output.append(f'  <li>{item}</li>')
            output.append(f'</{tag}>')
            list_buffer = []
            in_list = None

    def flush_paragraph(para_lines):
        if not para_lines:
            return
        para = ' '.join(para_lines).strip()
        if para:
            para = _inline_format(para)
            output.append(f'<p>{para}</p>')

    para_buffer = []

    def flush_para():
        nonlocal para_buffer
        flush_paragraph(para_buffer)
        para_buffer = []

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith('```'):
            flush_list()
            flush_para()
            if not in_code_block:
                in_code_block = True
                code_block_lang = line.strip()[3:].strip()
                code_block_content = []
            else:
                # end code block
                code_html = '\n'.join(code_block_content)
                code_html = _escape_html(code_html)
                if code_block_lang:
                    output.append(f'<pre><code class="language-{code_block_lang}">')
                else:
                    output.append('<pre><code>')
                output.append(code_html)
                output.append('</code></pre>')
                in_code_block = False
            i += 1
            continue

        if in_code_block:
            code_block_content.append(line)
            i += 1
            continue

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            flush_list()
            flush_para()
            level = len(heading_match.group(1))
            content = _inline_format(heading_match.group(2))
            output.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Unordered list
        ul_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if ul_match:
            flush_para()
            if in_list != 'ul':
                flush_list()
                in_list = 'ul'
            content = _inline_format(ul_match.group(2))
            list_buffer.append(content)
            i += 1
            continue

        # Ordered list
        ol_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ol_match:
            flush_para()
            if in_list != 'ol':
                flush_list()
                in_list = 'ol'
            content = _inline_format(ol_match.group(2))
            list_buffer.append(content)
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^[-*_]{3,}\s*$', line):
            flush_list()
            flush_para()
            output.append('<hr>')
            i += 1
            continue

        # Empty line
        if line.strip() == '':
            flush_list()
            flush_para()
            i += 1
            continue

        # Regular paragraph line
        flush_list()
        para_buffer.append(line)
        i += 1

    # Flush remaining
    flush_list()
    flush_para()

    return '\n'.join(output)


def _inline_format(text):
    """Convert inline markdown formatting to HTML."""
    # Bold + Italic (***)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    # Bold (**)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic (*)  – but not inside <strong> etc
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
    # Inline code (`)
    text = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', text)
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'<a href="\2">\1</a>', text)
    # Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*?)\]\(([^)]+?)\)', r'<img src="\2" alt="\1">', text)
    return text


def _escape_html(text):
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


# ─────────────────────────────────────────────
#  TEMPLATE ENGINE
# ─────────────────────────────────────────────

def render_template(template_text, variables):
    """Replace {{variable}} placeholders with values from the dict."""
    def replacer(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, ''))

    return re.sub(r'\{\{(\s*[\w]+\s*)\}\}', replacer, template_text)


# ─────────────────────────────────────────────
#  CONTENT LOADING
# ─────────────────────────────────────────────

def load_content_file(filepath):
    """Load a content file, parse front matter, convert markdown."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()

    metadata, body = parse_front_matter(raw)
    html_body = markdown_to_html(body)

    # Derive slug from filename
    filename = os.path.basename(filepath)
    slug = os.path.splitext(filename)[0]

    return {
        'slug': slug,
        'metadata': metadata,
        'html_body': html_body,
        'source_path': filepath,
    }


def load_all_content(content_dir):
    """Load all content files from content/posts/ and content/pages/."""
    posts = []
    pages = []

    posts_dir = os.path.join(content_dir, 'posts')
    pages_dir = os.path.join(content_dir, 'pages')

    if os.path.isdir(posts_dir):
        for fname in sorted(os.listdir(posts_dir)):
            if fname.endswith('.md'):
                item = load_content_file(os.path.join(posts_dir, fname))
                posts.append(item)

    if os.path.isdir(pages_dir):
        for fname in sorted(os.listdir(pages_dir)):
            if fname.endswith('.md'):
                item = load_content_file(os.path.join(pages_dir, fname))
                pages.append(item)

    # Also support content/*.md as pages (flat structure)
    for fname in sorted(os.listdir(content_dir)):
        fpath = os.path.join(content_dir, fname)
        if os.path.isfile(fpath) and fname.endswith('.md'):
            item = load_content_file(fpath)
            # If has a date, treat as post; else page
            if 'date' in item['metadata']:
                posts.append(item)
            else:
                pages.append(item)

    # Sort posts by date (newest first)
    posts.sort(key=lambda p: p['metadata'].get('date', '0000-00-00'), reverse=True)

    return posts, pages


# ─────────────────────────────────────────────
#  SITE BUILDER
# ─────────────────────────────────────────────

def load_template(template_dir, template_name):
    """Load a template file."""
    filepath = os.path.join(template_dir, template_name)
    if not os.path.exists(filepath):
        # Fall back to base template
        filepath = os.path.join(template_dir, 'base.html')
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def build_nav_html(pages, blog_index_url='/'):
    """Build navigation menu HTML from pages list."""
    nav_items = []
    # Link to blog index
    nav_items.append(f'<a href="{blog_index_url}">Blog</a>')
    for page in pages:
        title = page['metadata'].get('title', page['slug'])
        url = f"/{page['slug']}/"
        nav_items.append(f'<a href="{url}">{title}</a>')
    return '\n'.join(nav_items)


def build_site(content_dir, template_dir, output_dir, static_dir):
    """Build the complete static site."""
    # Clean output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Load content
    posts, pages = load_all_content(content_dir)

    # Build nav HTML
    nav_html = build_nav_html(pages)

    # Collect all pages for site-wide nav
    all_pages_info = []
    for p in pages:
        all_pages_info.append({
            'title': p['metadata'].get('title', p['slug']),
            'slug': p['slug'],
        })

    # ── Generate blog posts ──
    for post in posts:
        template_name = post['metadata'].get('template', 'post.html')
        template_text = load_template(template_dir, template_name)

        # Format date
        date_str = post['metadata'].get('date', '')
        formatted_date = ''
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                formatted_date = dt.strftime('%B %d, %Y')
            except ValueError:
                formatted_date = date_str

        variables = {
            'title': post['metadata'].get('title', post['slug']),
            'date': formatted_date,
            'tags': post['metadata'].get('tags', ''),
            'content': post['html_body'],
            'navigation': nav_html,
            'slug': post['slug'],
        }
        rendered = render_template(template_text, variables)

        # Write to output/posts/slug/index.html
        out_dir = os.path.join(output_dir, post['slug'])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'index.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(rendered)
        print(f'  Generated: /{post["slug"]}/')

    # ── Generate pages ──
    for page in pages:
        template_name = page['metadata'].get('template', 'page.html')
        template_text = load_template(template_dir, template_name)

        variables = {
            'title': page['metadata'].get('title', page['slug']),
            'date': '',
            'tags': '',
            'content': page['html_body'],
            'navigation': nav_html,
            'slug': page['slug'],
        }
        rendered = render_template(template_text, variables)

        out_dir = os.path.join(output_dir, page['slug'])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'index.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(rendered)
        print(f'  Generated: /{page["slug"]}/')

    # ── Generate blog index page ──
    index_template = load_template(template_dir, 'index.html')
    # Build blog post list HTML
    post_list_items = []
    for post in posts:
        title = post['metadata'].get('title', post['slug'])
        date_str = post['metadata'].get('date', '')
        formatted_date = ''
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                formatted_date = dt.strftime('%B %d, %Y')
            except ValueError:
                formatted_date = date_str
        url = f"/{post['slug']}/"
        tags = post['metadata'].get('tags', '')
        post_list_items.append({
            'title': title,
            'date': formatted_date,
            'url': url,
            'tags': tags,
        })

    # Build post list HTML
    post_list_html = '<ul class="post-list">\n'
    for p in post_list_items:
        post_list_html += f'  <li>\n'
        post_list_html += f'    <span class="post-date">{p["date"]}</span>\n'
        post_list_html += f'    <a href="{p["url"]}">{p["title"]}</a>\n'
        if p['tags']:
            tags_html = ' '.join(f'<span class="tag">{t.strip()}</span>' for t in p['tags'].split(','))
            post_list_html += f'    <span class="post-tags">{tags_html}</span>\n'
        post_list_html += f'  </li>\n'
    post_list_html += '</ul>'

    variables = {
        'title': 'Blog',
        'content': post_list_html,
        'navigation': nav_html,
        'date': '',
        'tags': '',
        'slug': 'index',
    }
    rendered = render_template(index_template, variables)

    # Write index at root
    out_path = os.path.join(output_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f'  Generated: / (blog index)')

    # ── Copy static assets ──
    if os.path.isdir(static_dir):
        _copy_static(static_dir, output_dir)

    print(f'\nSite built successfully in: {output_dir}')


def _copy_static(static_dir, output_dir):
    """Copy static assets to output directory."""
    for root, dirs, files in os.walk(static_dir):
        rel_path = os.path.relpath(root, static_dir)
        dest_dir = os.path.join(output_dir, rel_path) if rel_path != '.' else output_dir
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(dest_dir, fname)
            shutil.copy2(src, dst)
            print(f'  Copied: {os.path.relpath(dst, output_dir)}')


# ─────────────────────────────────────────────
#  HTTP SERVER FOR PREVIEW
# ─────────────────────────────────────────────

def serve_site(output_dir, port=8000):
    """Start a local HTTP server to preview the generated site."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            kwargs['directory'] = output_dir
            super().__init__(*args, **kwargs)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.allow_reuse_address = True
        print(f'\n  Serving at http://localhost:{port}/')
        print('  Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  Server stopped.')


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Static Site Generator - Build a static website from Markdown content.'
    )
    parser.add_argument(
        '--content', default='content',
        help='Content directory (default: content/)'
    )
    parser.add_argument(
        '--templates', default='templates',
        help='Templates directory (default: templates/)'
    )
    parser.add_argument(
        '--output', default='output',
        help='Output directory (default: output/)'
    )
    parser.add_argument(
        '--static', default='static',
        help='Static assets directory (default: static/)'
    )
    parser.add_argument(
        '--serve', action='store_true',
        help='Start a local HTTP server after building'
    )
    parser.add_argument(
        '--port', type=int, default=8000,
        help='Port for the HTTP server (default: 8000)'
    )
    parser.add_argument(
        '--clean', action='store_true',
        help='Remove the output directory before building'
    )

    args = parser.parse_args()

    # Resolve paths relative to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    content_dir = os.path.abspath(args.content)
    template_dir = os.path.abspath(args.templates)
    output_dir = os.path.abspath(args.output)
    static_dir = os.path.abspath(args.static)

    # Handle --clean
    if args.clean:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            print(f'Cleaned output directory: {output_dir}')
        os.makedirs(output_dir, exist_ok=True)

    print(f'Building site...')
    print(f'  Content:   {content_dir}')
    print(f'  Templates: {template_dir}')
    print(f'  Static:    {static_dir}')
    print(f'  Output:    {output_dir}')
    print()

    build_site(content_dir, template_dir, output_dir, static_dir)

    if args.serve:
        serve_site(output_dir, args.port)


if __name__ == '__main__':
    main()
