import html
from urllib.parse import urlparse

# Known video-hosting domains get a "Watch" button by default instead of
# "Read the original" — "read" doesn't make sense for a video link.
# Deterministic on the URL's own host, not a content-sniffing guess, so it
# stays in keeping with this field's manual/no-heuristics philosophy
# elsewhere (title:/source:/note:/description: are all hand-entered, never
# fetched). cta: still overrides this for any case the host list misses.
_VIDEO_HOSTS = {
    'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com',
    'vimeo.com', 'www.vimeo.com',
}


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

    is_video = urlparse(link['url']).netloc.lower() in _VIDEO_HOSTS
    default_cta = 'Watch →' if is_video else 'Read the original →'
    cta = html.escape(link.get('cta') or default_cta)

    # Escaped once, up front — an unescaped '&' in a URL breaks HTML
    # attribute validity, and title:/source:/note:/description: are free
    # text that could contain '<'/'>'/quotes. Display-only: the raw,
    # unescaped description: in frontmatter is still what
    # util/check_fragments.py verifies against the live page.
    url = html.escape(link['url'])
    title = html.escape(link.get('title', ''))
    source = html.escape(link.get('source', ''))
    note = html.escape(link.get('note', ''))
    paywalled = link.get('paywalled', False)
    image = link.get('image', '')
    description = html.escape(link.get('description', ''))

    eyebrow = 'Shared link' + (f' · {source}' if source else '')
    parts = ['\n<div class="shared-link-card">']
    if image:
        # A remote thumbnail URL is used as-is; a local path (under
        # docs/assets/, no leading slash) needs one added — see the "URL
        # gotcha" note in CLAUDE.md about file.page.url being root-relative
        # without a leading '/'.
        img_src = html.escape(image if image.startswith('http') else f'/{image}')
        parts.append(
            f'<a class="shared-link-image-wrap" href="{url}" target="_blank" '
            f'rel="noopener"><img class="shared-link-image" src="{img_src}" '
            f'alt="{title or eyebrow}"></a>'
        )
    parts.append(f'<div class="shared-link-eyebrow">{eyebrow}</div>')
    if title:
        parts.append(f'<div class="shared-link-title">{title}</div>')
    if note:
        parts.append(f'<div class="shared-link-note">{note}</div>')
    if description:
        parts.append(f'<blockquote class="shared-link-description">{description}</blockquote>')
    parts.append('<div class="shared-link-actions">')
    parts.append(
        f'<a class="hero-cta-btn hero-cta-primary" href="{url}" '
        f'target="_blank" rel="noopener">{cta}</a>'
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
