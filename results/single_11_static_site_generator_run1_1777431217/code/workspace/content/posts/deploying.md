---
title: Deploying Your Static Site
date: 2024-04-20
tags: deployment, hosting, tutorial
template: post.html
---

# Deploying Your Static Site

You've built your site. Now let's **ship it**!

## Deployment Options

Here are some popular platforms for static site hosting:

- **GitHub Pages**: Free, automatic deploys from Git
- **Netlify**: Great CI/CD, form handling included
- **Vercel**: Optimized for frontend frameworks
- **S3 + CloudFront**: AWS-based, highly scalable

## Build Process

The typical build process looks like this:

1. Write content in Markdown
2. Run the generator: `python ssg.py --clean`
3. Upload the `output/` directory
4. *(Optional)* Set up a custom domain

## Performance Tips

Make your site lightning fast:

- Minify your CSS and HTML
- Optimize images before uploading
- Enable compression on your server
- Use a CDN for global delivery

---

That's it for this series! Check the [blog index](/posts/) for all posts.
