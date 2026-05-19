---
title: Getting Started with Static Sites
date: 2025-01-15
tags: static, web, tutorial
template: post
---

## Why Static Sites?

Static sites are **fast**, **secure**, and **easy to deploy**. Unlike dynamic sites that generate HTML on every request, static sites are pre-built and served as-is.

### Benefits

- **Performance**: No database queries, no server-side processing
- **Security**: No backend to exploit
- **Simplicity**: Just HTML, CSS, and JavaScript
- **Version Control**: Track everything with Git

### Getting Started

Here's a simple workflow:

1. Write content in Markdown
2. Run the static site generator
3. Deploy the `output/` folder to any web server

```python
# Example: building the site
from ssg.builder import build
build('content', 'templates', 'static', 'output')
```

> Static sites are the future of the web. They combine the best of both worlds: the power of dynamic generation with the simplicity of static files.

Stay tuned for more posts about advanced SSG features!
