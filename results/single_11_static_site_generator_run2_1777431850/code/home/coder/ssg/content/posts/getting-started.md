---
title: Getting Started with Static Sites
date: 2024-03-15
tags: web, static, tutorial
template: post.html
---

Static sites are making a **big comeback**. They are fast, secure, and easy to deploy.

## Why Static Sites?

Here are some reasons to consider a static site:

- **Speed**: No database queries, just raw HTML
- **Security**: No server-side code to exploit
- **Simplicity**: Write content in Markdown, generate HTML
- **Version Control**: Track everything in Git

## How It Works

This site is built with a custom static site generator written in Python. It takes Markdown files with front matter, converts them to HTML, and applies them to templates.

### The Build Process

1. Read content files from the `content/` directory
2. Parse YAML-style front matter for metadata
3. Convert Markdown to HTML
4. Apply templates with `{{variable}}` placeholders
5. Output the complete site to `output/`

> Static sites are the future of the web. - Some wise developer

Here is some inline `code` for you.

```
def hello():
    print("Hello, static world!")
```

Start building your static site today!
