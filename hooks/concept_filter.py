def on_page_markdown(markdown, *, page, config, files):
    """Auto-inject Democracy Landscape filter bubble on concept pages."""
    src = page.file.src_path
    if not src.startswith('concepts/') or src == 'concepts/index.md':
        return markdown

    slug = src.split('/')[-1].replace('.md', '')
    slug_title = slug.replace('-', ' ').title()
    bubble = f'\n<div class="concept-org-bubble">\n<span class="twemoji">\n  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/><path d="M18 12H6v-2h12z"/></svg>\n</span>\n<a href="/organisations/?concept={slug}">Search organisations working on <strong>{slug_title}</strong> in the Democracy Landscape →</a>\n</div>'

    lines = markdown.split('\n')
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('#') and not line.startswith('<'):
            lines.insert(i, bubble)
            break
    else:
        lines.append(bubble)

    return '\n'.join(lines)
