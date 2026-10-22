import html

# The DOD podcast's own feed and listing pages, shown under every player so a
# reader who liked one episode can subscribe without hunting for the feed.
FEED_URL = 'https://anchor.fm/s/39cd9860/podcast/rss'
APPLE_URL = 'https://podcasts.apple.com/au/podcast/designing-open-democracy/id1492656241'
ANTENNAPOD_URL = (
    'https://antennapod.org/deeplink/subscribe/'
    '?url=https%3A%2F%2Fanchor.fm%2Fs%2F39cd9860%2Fpodcast%2Frss'
    '&title=Designing+Open+Democracy'
)


def episodes(meta):
    """podcast: is one episode (a dict) or several (a list, e.g. a talk
    released as three parts). Entries without audio: are dropped."""
    value = meta.get('podcast')
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [e for e in value if isinstance(e, dict) and e.get('audio')]


def render(eps):
    multi = len(eps) > 1
    parts = ['\n<div class="podcast-card">',
             '<div class="podcast-card-eyebrow">🎧 Listen · Designing Open Democracy podcast</div>']
    for ep in eps:
        audio = html.escape(ep['audio'])
        title = html.escape(str(ep.get('title') or ''))
        duration = html.escape(str(ep.get('duration') or ''))
        page = html.escape(ep.get('url') or '')
        if multi and title:
            parts.append(f'<div class="podcast-card-title">{title}</div>')
        # preload="none": episodes run to 100 MB, and nothing should be
        # downloaded until the reader actually presses play.
        parts.append(
            f'<audio class="podcast-player" controls preload="none" src="{audio}">'
            f'<a href="{audio}">Download the MP3</a></audio>'
        )
        links = []
        if duration:
            links.append(duration)
        links.append(f'<a href="{audio}">Download MP3</a>')
        if page:
            links.append(f'<a href="{page}" target="_blank" rel="noopener">Episode page ↗</a>')
        parts.append(f'<div class="podcast-card-links">{" · ".join(links)}</div>')
    parts.append(
        '<div class="podcast-card-subscribe">Subscribe: '
        f'<a href="{APPLE_URL}" target="_blank" rel="noopener">Apple Podcasts</a> · '
        f'<a href="{ANTENNAPOD_URL}" target="_blank" rel="noopener">AntennaPod</a> · '
        f'<a href="{FEED_URL}">RSS feed</a></div>'
    )
    parts.append('</div>\n')
    return '\n'.join(parts)


def on_page_markdown(markdown, *, page, config, files):
    """Render an audio player for blog posts that set podcast: frontmatter.

    Placed straight after <!-- more --> so the player is the first thing in
    the post body but stays out of the blog index's excerpt, where a row of
    players would make the listing heavy and noisy. Posts without the
    marker get it at the top.
    """
    if not page.file.src_path.startswith('blog/posts/'):
        return markdown
    eps = episodes(page.meta)
    if not eps:
        return markdown
    card = render(eps)
    marker = '<!-- more -->'
    if marker in markdown:
        return markdown.replace(marker, marker + '\n' + card, 1)
    return card + '\n' + markdown
