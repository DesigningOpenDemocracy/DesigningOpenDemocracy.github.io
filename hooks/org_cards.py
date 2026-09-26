"""Inline Democracy Landscape cards for blog posts.

Put a marker on its own line where the card should appear, e.g. under a
panellist's bio:

    <!-- org-card: mosaiclab -->

It's replaced at build time with a compact card built from that org page's
frontmatter: logo, name, type/country, a trimmed summary, a link to the
org's Democracy Landscape profile, and a link to its own website. The
marker is an HTML comment, so if the hook ever stops running the post still
reads cleanly with no card rather than showing stray syntax.

Nothing is stored in the post but the slug, so a card always reflects the
org page as it is now. An unknown slug fails the build rather than quietly
dropping the card.
"""
import html
import os
import re

import yaml

MARKER_RE = re.compile(r'^[ \t]*<!--\s*org-card:\s*([a-z0-9-]+)\s*-->[ \t]*$', re.M)
SUMMARY_CHARS = 220

_cache = {}


def _load_org(docs_dir, slug):
    key = (docs_dir, slug)
    if key not in _cache:
        path = os.path.join(docs_dir, 'organisations', f'{slug}.md')
        meta = None
        try:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            if text.startswith('---'):
                end = text.find('\n---', 3)
                if end != -1:
                    meta = yaml.safe_load(text[3:end]) or {}
        except OSError:
            meta = None
        _cache[key] = meta
    return _cache[key]


def _trim(text, limit=SUMMARY_CHARS):
    text = ' '.join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0].rstrip(',;:—-')
    return cut + '…'


def render_card(slug, meta):
    title = html.escape(str(meta.get('title') or slug))
    profile = f'/organisations/{slug}/'
    parts = ['<div class="org-card">']

    logo = meta.get('logo')
    if logo:
        src = html.escape(logo if str(logo).startswith(('http', '/')) else f'/{logo}')
        bg = meta.get('logo_bg')
        cls = 'org-card-logo' + (f' org-logo-needs-{bg}' if bg in ('dark', 'light') else '')
        parts.append(f'<a class="org-card-logo-link" href="{profile}"><img class="{cls}" src="{src}" alt="" loading="lazy"></a>')

    parts.append('<div class="org-card-body">')
    parts.append('<div class="org-card-eyebrow">Democracy Landscape</div>')
    parts.append(f'<div class="org-card-title"><a href="{profile}">{title}</a></div>')
    facts = [str(meta[k]) for k in ('type', 'country') if meta.get(k)]
    status = meta.get('status')
    if status and status != 'active':
        facts.append(str(status))
    if facts:
        parts.append(f'<div class="org-card-facts">{html.escape(" · ".join(facts))}</div>')
    if meta.get('summary'):
        parts.append(f'<div class="org-card-summary">{html.escape(_trim(meta["summary"]))}</div>')

    parts.append('<div class="org-card-links">')
    parts.append(f'<a href="{profile}">Landscape profile →</a>')
    website = meta.get('website')
    if website:
        label = 'Website (archived) ↗' if 'web.archive.org' in str(website) else 'Website ↗'
        parts.append(
            f'<a href="{html.escape(str(website))}" target="_blank" rel="noopener">{label}</a>'
        )
    parts.append('</div></div></div>')
    return ''.join(parts)


def expand_markers(markdown, docs_dir, where='page'):
    def repl(m):
        slug = m.group(1)
        meta = _load_org(docs_dir, slug)
        if not meta:
            raise ValueError(f'{where}: org-card marker names unknown org "{slug}" '
                             f'(no docs/organisations/{slug}.md with frontmatter)')
        # Blank lines around the block so Markdown treats it as raw HTML.
        return '\n' + render_card(slug, meta) + '\n'
    return MARKER_RE.sub(repl, markdown)


def on_page_markdown(markdown, *, page, config, files):
    if not page.file.src_path.startswith('blog/posts/') or 'org-card:' not in markdown:
        return markdown
    return expand_markers(markdown, config['docs_dir'], page.file.src_path)
