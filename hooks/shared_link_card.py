def on_page_markdown(markdown, *, page, config, files):
    """Auto-inject a prominent shared-link card on blog posts that set
    shared_link: frontmatter — the specific external resource (article,
    paper, video) the post exists to point at. Without this, that link was
    just one more bullet in "Sources & further reading" at the bottom,
    indistinguishable from secondary citations.
    """
    src = page.file.src_path
    if not src.startswith('blog/posts/'):
        return markdown

    link = page.meta.get('shared_link')
    if not link or not link.get('url'):
        return markdown

    url = link['url']
    title = link.get('title', '')
    source = link.get('source', '')
    note = link.get('note', '')
    paywalled = link.get('paywalled', False)

    eyebrow = 'Shared link' + (f' · {source}' if source else '')
    parts = [f'\n<div class="shared-link-card">',
             f'<div class="shared-link-eyebrow">{eyebrow}</div>']
    if title:
        parts.append(f'<div class="shared-link-title">{title}</div>')
    if note:
        parts.append(f'<div class="shared-link-note">{note}</div>')
    parts.append('<div class="shared-link-actions">')
    parts.append(
        f'<a class="hero-cta-btn hero-cta-primary" href="{url}" '
        f'target="_blank" rel="noopener">Read the original →</a>'
    )
    if paywalled:
        parts.append('<span class="shared-link-badge">Paywalled</span>')
    parts.append('</div>')
    parts.append('</div>\n')
    card = '\n'.join(parts)

    lines = markdown.split('\n')
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('#') and not line.startswith('<'):
            lines.insert(i, card)
            break
    else:
        lines.append(card)

    return '\n'.join(lines)
