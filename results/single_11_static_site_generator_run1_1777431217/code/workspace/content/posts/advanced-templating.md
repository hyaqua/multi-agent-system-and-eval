---
title: Advanced Templating Techniques
date: 2024-04-02
tags: templates, advanced, python
template: post.html
---

# Advanced Templating Techniques

Now that we have the **basics** down, let's explore more advanced template features.

## Custom Variables

You can define *any* variable in your front matter:

```
---
title: My Page
author: Jane Doe
custom_field: some value
---
```

## Conditional Logic

While this simple generator uses basic `{{variable}}` substitution, you can still achieve a lot:

1. Use different templates for different content types
2. Pass metadata to templates for conditional rendering
3. Leverage CSS classes based on tags

## Template Structure

A well-organized template looks like this:

- Header with navigation
- Main content area
- Sidebar (optional)
- Footer

> Pro tip: Keep your templates DRY by using consistent naming conventions.

## Code Highlighting

```css
.post {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
}
```

Happy building!
