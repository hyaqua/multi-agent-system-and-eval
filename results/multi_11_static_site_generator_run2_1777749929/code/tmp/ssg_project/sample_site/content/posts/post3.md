---
title: Deploying Your Static Site
date: 2025-03-10
tags: deployment, hosting, tutorial
template: post
---

## Deployment Options

Once you've built your static site, you need to put it online. Here are some popular options:

### Free Hosting

- **GitHub Pages**: Free for public repos, supports custom domains
- **Netlify**: Generous free tier with continuous deployment
- **Vercel**: Great for Next.js but works with any static site

### Deployment Steps

1. Build your site with `python ssg.py`
2. Navigate to the `output/` directory
3. Upload to your hosting provider

### Pro Tips

- Always run with `--clean` before deploying to avoid stale files
- Use `--serve` locally to preview before pushing live
- Minify your CSS and HTML for better performance
- Set up a CDN for global delivery

```bash
# Typical deployment workflow
python ssg.py --clean
cd output/
# Then upload via your provider's CLI or Git
```

That's it! Your site is live for the world to see.
