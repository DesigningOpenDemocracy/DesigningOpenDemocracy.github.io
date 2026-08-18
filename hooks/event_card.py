import html
from datetime import date as _date
from datetime import datetime as _datetime


def _format_date(value):
    """Render an event date as e.g. 'Thursday, 27 August 2026'. Accepts a
    datetime.date (YAML auto-parses an unquoted ISO date into one) or a
    'YYYY-MM-DD' string (if an author quoted it) — falls back to the raw
    value unchanged for anything else rather than guessing."""
    if isinstance(value, (_date, _datetime)):
        d = value
    else:
        try:
            d = _datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return str(value)
    return d.strftime("%A, ") + str(d.day) + d.strftime(" %B %Y")


def _format_time(value):
    """'18:00' -> '6:00 PM'. Same strict HH:MM shape hooks/calendar_export.py
    requires for time:/end_time: — deliberately not attempting to parse
    anything looser. Falls back to the raw string unchanged if it doesn't
    match, rather than guessing."""
    try:
        t = _datetime.strptime(str(value), "%H:%M")
    except ValueError:
        return str(value)
    hour12 = t.strftime("%I").lstrip("0") or "12"
    return hour12 + t.strftime(":%M %p")


def on_page_markdown(markdown, *, page, config, files):
    """Auto-inject a prominent event card on blog posts that set event:
    frontmatter — a ticketed/RSVP'd event DOD is pointing readers at,
    someone else's event in the common case (per CLAUDE.md's blog-posts
    convention: the actual calendar-worthy entry belongs on the *host
    org's own* events: field, not here — this card is presentational
    only and is never read by hooks/calendar_export.py, which is exactly
    why the earlier event_date: field was removed: it fed the site-wide
    calendar and duplicated the org's own entry for the same date).

    Reuses the page's own top-level location: frontmatter (already set on
    posts like this for other reasons) for an embedded map, rather than
    duplicating lat/lon inside event: too.
    """
    src = page.file.src_path
    if not src.startswith('blog/posts/'):
        return markdown

    event = page.meta.get('event')
    if not event or not event.get('url'):
        return markdown

    # Escaped once, up front — an unescaped '&' in a URL (a real case:
    # actionnetwork.org query strings) breaks HTML attribute validity, and
    # note:/title: are free text that could contain '<'/'>'/quotes.
    url = html.escape(event['url'])
    title = html.escape(event.get('title', ''))
    host = html.escape(event.get('host', ''))
    note = html.escape(event.get('note', ''))
    cta = html.escape(event.get('cta') or 'RSVP →')
    image = event.get('image', '')

    when_parts = []
    if event.get('date'):
        when_parts.append(_format_date(event['date']))
    if event.get('time'):
        start = _format_time(event['time'])
        if event.get('end_time'):
            end = _format_time(event['end_time'])
            # Drop the redundant AM/PM off the start time when both share
            # the same period ("6:00 PM" + "8:00 PM" -> "6:00-8:00 PM",
            # not "6:00 PM-8:00 PM") — matches how these times actually
            # read in prose (radicalxchange-melbourne.md's own "6-8pm").
            start_period = start[-2:]
            end_period = end[-2:]
            if start_period == end_period and start_period in ('AM', 'PM'):
                start = start[:-3]
            when_parts.append(f'{start}–{end}')
        else:
            when_parts.append(start)
    when = ', '.join(when_parts)

    location = page.meta.get('location') or {}
    loc_name = html.escape(location.get('name', ''))
    lat = location.get('latitude')
    lon = location.get('longitude')

    eyebrow = 'Event' + (f' · {host}' if host else '')
    parts = ['\n<div class="event-card">']
    if image:
        # A remote URL is used as-is; a local path (under docs/assets/, no
        # leading slash) needs one added — see the "URL gotcha" note in
        # CLAUDE.md about file.page.url being root-relative without a
        # leading '/'. Same convention as shared_link.image.
        img_src = html.escape(image if image.startswith('http') else f'/{image}')
        parts.append(
            f'<a class="event-card-image-wrap" href="{url}" target="_blank" '
            f'rel="noopener"><img class="event-card-image" src="{img_src}" '
            f'alt="{title or eyebrow}"></a>'
        )
    parts.append(f'<div class="event-card-eyebrow">{eyebrow}</div>')
    if title:
        parts.append(f'<div class="event-card-title">{title}</div>')
    if when:
        parts.append(f'<div class="event-card-when">{when}</div>')
    if loc_name:
        parts.append(f'<div class="event-card-location">{loc_name}</div>')
    if note:
        parts.append(f'<div class="event-card-note">{note}</div>')
    parts.append('<div class="event-card-actions">')
    parts.append(
        f'<a class="hero-cta-btn hero-cta-primary" href="{url}" '
        f'target="_blank" rel="noopener">{cta}</a>'
    )
    parts.append('</div>')
    if lat is not None and lon is not None:
        delta = 0.008
        bbox = f'{lon - delta}%2C{lat - delta}%2C{lon + delta}%2C{lat + delta}'
        parts.append(
            '<iframe class="event-card-map" width="100%" height="250" frameborder="0" '
            'scrolling="no" src="https://www.openstreetmap.org/export/embed.html?'
            f'bbox={bbox}&amp;layer=mapnik&amp;marker={lat}%2C{lon}"></iframe>'
        )
        parts.append(
            '<div class="event-card-map-link"><a href="https://www.openstreetmap.org/'
            f'?mlat={lat}&amp;mlon={lon}#map=17/{lat}/{lon}" target="_blank" '
            'rel="noopener">View larger map / directions →</a></div>'
        )
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
