"""
calendar_export.py — MkDocs hook: build the site-wide future-events calendar.

Merges two sources of *future* events into one list at build time (no
network calls here — see util/sync_events.py for the fetch step that
populates the cache this reads):

  1. Manually curated `events:` entries in org frontmatter (date >= today) —
     this is also how DOD's own events reach the calendar: DOD is itself a
     tracked org (designing-open-democracy.md) with its own `events:` list,
     the same as any other org, so there's no separate "DOD's events" path.
  2. Cached iCal-synced events in docs/data/events/<slug>.json, written by
     util/sync_events.py for orgs with `ics_feed:` set (date >= today)

A third source — an optional `event_date:` field on blog posts — existed
briefly but was removed: every blog post that set it was DOD *covering*
another org's event, not hosting its own, so the same event ended up on
the calendar twice (once from the org's own `events:` entry, once from
the post). Confirmed on both posts that had used it — the dates matched
their subject org's `events:` entry exactly. If DOD ever hosts a genuine
event of its own, it belongs in designing-open-democracy.md's `events:`,
same as any org.

Output:
  - docs/calendar.ics       — combined VCALENDAR, downloadable/subscribable
  - docs/calendar-<CC>.ics  — same, filtered to one ISO 3166-1 country code;
    one per country actually present, since most calendar apps (Google
    Calendar included) offer no way to filter a subscribed feed after the
    fact — CATEGORIES is ignored on import
  - docs/data/events.json   — same data as JSON, for reference/download
  - `calendar_events` Jinja2 global — consumed by docs/overrides/calendar.html

Org-page history/upcoming timelines (rendered from `events:` alone, past and
future both) are handled separately in organisation.html — this hook only
cares about the future-facing, cross-org aggregate.
"""

import glob
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta

try:
    import frontmatter
except ImportError:
    frontmatter = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SYNCED_EVENTS_DIR = os.path.join(DOCS_DIR, "data", "events")
SKIP_FILES = {"index.md"}

# Known recurring CJK event patterns → English translation (for calendar readability)
_CJK_PATTERNS = [
    (re.compile(r'公民科技跑咖松_(.+)'), lambda m: f'Civic Tech Hackathon — {m.group(1)}'),
    (re.compile(r'第(.+?)次(.+?)松'), lambda m: f'{m.group(1)}th {m.group(2)} Hackathon'),
    (re.compile(r'公民科技(.+)活動'), lambda m: f'Civic Tech {m.group(1)} Activity'),
]


def _has_cjk(s):
    """True if string is predominantly CJK characters (Chinese/Japanese/Korean)."""
    if not s:
        return False
    total = len(s)
    cjk = sum(1 for c in s
              if '\u4e00' <= c <= '\u9fff'
              or '\u3400' <= c <= '\u4dbf'
              or '\uf900' <= c <= '\ufaff')
    return cjk / total > 0.3


def _eng_title(title, org_title):
    """Return an English title for a CJK event, or None if no translation available."""
    for pattern, fn in _CJK_PATTERNS:
        m = pattern.match(title)
        if m:
            return fn(m)
    return f'{org_title} event'


def _maybe_add_translation(event_dict, title, org_title):
    """If the title is predominantly CJK, add title_en to the event dict."""
    if _has_cjk(title):
        event_dict["title_en"] = _eng_title(title, org_title)
    return event_dict


def _org_logo(slug):
    """Return logo path for an org slug, or None if no logo in frontmatter."""
    path = os.path.join(ORGS_DIR, f"{slug}.md")
    if not os.path.exists(path):
        return None
    try:
        return frontmatter.load(path).metadata.get("logo")
    except Exception:
        return None


def _org_logo_bg(slug):
    """Return logo_bg ('dark'/'light') for an org slug, or None. Needed
    alongside _org_logo() so calendar.html can apply the same
    org-logo-needs-dark/-light backing-card treatment org pages and the
    home page map already use for transparent-background logos — see
    CLAUDE.md's logo_bg: convention."""
    path = os.path.join(ORGS_DIR, f"{slug}.md")
    if not os.path.exists(path):
        return None
    try:
        return frontmatter.load(path).metadata.get("logo_bg")
    except Exception:
        return None


def _org_country(slug):
    """Return country ISO code for an org slug, or None."""
    path = os.path.join(ORGS_DIR, f"{slug}.md")
    if not os.path.exists(path):
        return None
    try:
        return frontmatter.load(path).metadata.get("country")
    except Exception:
        return None

_events: list = []


def _notable_tier(entry):
    """Normalize an events: entry's notable: field to True (major),
    "medium", or False. Any other value (a typo, a stray truthy string)
    reads as False rather than silently getting the major-event
    highlight — see CLAUDE.md's notable: docs for the true/"medium"/
    absent distinction and why it isn't just about frequency (an AGM is
    just as annual as a flagship conference, but isn't major)."""
    v = entry.get("notable")
    return v if v is True or v == "medium" else False


def _parse_date(val):
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def _load_manual_events(today):
    """Future events from each org's `events:` frontmatter list."""
    if frontmatter is None:
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        slug = os.path.basename(path)[:-3]
        post = frontmatter.load(path)
        m = post.metadata
        for entry in m.get("events") or []:
            d = _parse_date(entry.get("date"))
            if d and d >= today:
                evt = {
                    "date": d,
                    "end_date": _parse_date(entry.get("end_date")),
                    "title": entry.get("title", "Untitled event"),
                    "short_title": entry.get("short_title"),
                    "url": entry.get("url", ""),
                    "org_slug": slug,
                    "org_title": m.get("title", slug),
                    "source": "manual",
                    "notable": _notable_tier(entry),
                    "logo": _org_logo(slug),
                    "logo_bg": _org_logo_bg(slug),
                    "country": entry.get("country") or m.get("country"),
                    "type": entry.get("type"),
                    "location": entry.get("location"),
                    "time": entry.get("time"),
                    "end_time": entry.get("end_time"),
                    "coverage_url": entry.get("coverage_url"),
                }
                _maybe_add_translation(evt, evt["title"], evt["org_title"])
                out.append(evt)
    return out


def _load_synced_events(today):
    """Future events cached from ics_feed syncs (util/sync_events.py)."""
    if frontmatter is None:
        return []
    # Map slug -> org title and country so entries can carry a display name.
    titles = {}
    for path in glob.glob(os.path.join(ORGS_DIR, "*.md")):
        if os.path.basename(path) in SKIP_FILES:
            continue
        slug = os.path.basename(path)[:-3]
        m = frontmatter.load(path).metadata
        titles[slug] = m.get("title", slug)

    out = []
    for path in sorted(glob.glob(os.path.join(SYNCED_EVENTS_DIR, "*.json"))):
        slug = os.path.basename(path)[:-5]
        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for entry in cached:
            d = _parse_date(entry.get("date"))
            if d and d >= today:
                evt = {
                    "date": d,
                    "end_date": _parse_date(entry.get("end_date")),
                    "title": entry.get("title", "Untitled event"),
                    "url": entry.get("url", ""),
                    "org_slug": slug,
                    "org_title": titles.get(slug, slug),
                    "source": "ical",
                    "notable": False,
                    "logo": _org_logo(slug),
                    "logo_bg": _org_logo_bg(slug),
                    "country": _org_country(slug),
                }
                _maybe_add_translation(evt, evt["title"], evt["org_title"])
                out.append(evt)
    return out


def _ics_escape(s):
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _fold_line(line, limit=75):
    """RFC 5545 §3.1 line folding: a content line MUST NOT exceed 75 octets
    (excluding the line break); longer lines are split across multiple
    physical lines, each continuation prefixed with a single leading space.
    Google Calendar's importer is strict about this — several event
    SUMMARY/URL lines here run past 75 octets unfolded (confirmed up to 220),
    and multi-byte UTF-8 titles (e.g. g0v's Chinese-language event names)
    make a naive octet split even more likely to corrupt a character, so
    splits are only made on whole-character boundaries."""
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    segments = []
    start = 0
    seg_limit = limit
    while start < len(encoded):
        end = min(start + seg_limit, len(encoded))
        while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
            end -= 1
        segments.append(encoded[start:end].decode("utf-8"))
        start = end
        seg_limit = limit - 1  # continuation lines carry a leading space
    return "\r\n ".join(segments)


_TIME_RE = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')


def _parse_time(t):
    """Parse a strict 24-hour "HH:MM" time string into (hour, minute), or
    None if t is missing or doesn't match that exact shape. Deliberately
    strict — no natural-language parsing ("6pm", "2:00 PM AEST", "14:00 -
    15:00 AEST") is attempted. Real event pages checked while sourcing
    citations this session used wildly inconsistent formats for the same
    piece of information (CAPaD: "14:00 - 15:00 AEST" in a widget vs plain
    prose elsewhere; the World Forum for Democracy's own People Powered
    listing stated "2–3 November" in one place and "2–4 November" in the
    surrounding paragraph) — a fuzzy parser here would produce confident,
    wrong output rather than a value worth automating. See CLAUDE.md's
    events: time:/end_time: docs for the expected input shape."""
    if not t:
        return None
    m = _TIME_RE.match(str(t).strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _write_ics(events, path, calname="Designing Open Democracy — Democracy Landscape Calendar"):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Designing Open Democracy//Democracy Landscape Calendar//EN",
        f"X-WR-CALNAME:{_ics_escape(calname)}",
        "CALSCALE:GREGORIAN",
    ]
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        dt = e["date"].strftime("%Y%m%d")
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"dod-calendar:{e['org_slug']}:{dt}:{e['title']}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@designingopendemocracy.com",
            f"DTSTAMP:{now_stamp}",
        ]
        # A parseable time: gives a real (floating-local-time) DTSTART/DTEND
        # instead of an all-day marker — floating because no event carries a
        # structured timezone today (time: is a bare "HH:MM"), so this is
        # honest about the precision actually on hand: closer than all-day,
        # not a claim to have the IANA tz right. See _parse_time().
        start_time = _parse_time(e.get("time"))
        if start_time:
            h, m = start_time
            lines.append(f"DTSTART:{dt}T{h:02d}{m:02d}00")
            end_time = _parse_time(e.get("end_time"))
            if end_time:
                eh, em = end_time
                lines.append(f"DTEND:{dt}T{eh:02d}{em:02d}00")
            elif e.get("end_date"):
                # end_date without a matching end_time: falls back to a
                # date-only DTEND (exclusive, +1 day per RFC 5545 §3.6.1) —
                # still better than losing the end_date entirely.
                lines.append(f"DTEND;VALUE=DATE:{(e['end_date'] + timedelta(days=1)).strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{dt}")
            if e.get("end_date"):
                # DTEND is exclusive for all-day VEVENTs per RFC 5545 §3.6.1.
                lines.append(f"DTEND;VALUE=DATE:{(e['end_date'] + timedelta(days=1)).strftime('%Y%m%d')}")
        lines += [
            f"SUMMARY:{_ics_escape(e['org_title'] + ': ' + e['title'])}",
            f"CATEGORIES:{_ics_escape(e['org_title'])}",
        ]
        if e.get("url"):
            lines.append(f"URL:{_ics_escape(e['url'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(_fold_line(l) for l in lines) + "\r\n")


def on_pre_build(config):
    if frontmatter is None:
        return
    today = date.today()
    events = _load_manual_events(today) + _load_synced_events(today)
    events.sort(key=lambda e: e["date"])

    _events.clear()
    _events.extend(events)

    _write_ics(events, os.path.join(DOCS_DIR, "calendar.ics"))

    # Per-country subscribe feeds. Google Calendar (and most other clients)
    # offer no way to filter a subscribed .ics URL after the fact — CATEGORIES
    # is ignored on import — so the combined feed is all-or-nothing once
    # someone's subscribed. Splitting by country at build time is the only
    # lever available for cutting that noise; every country actually present
    # gets a file, matching exactly what docs/overrides/calendar.html's
    # country dropdown offers (same underlying `country` field), so the
    # per-country "Subscribe" link it builds can never point at a 404.
    by_country = {}
    for e in events:
        c = e.get("country")
        if c:
            by_country.setdefault(c, []).append(e)
    for country, country_events in by_country.items():
        country_name = _COUNTRY_NAMES.get(country, country)
        _write_ics(
            country_events, os.path.join(DOCS_DIR, f"calendar-{country}.ics"),
            calname=f"Designing Open Democracy — {country_name} Events",
        )

    os.makedirs(os.path.join(DOCS_DIR, "data"), exist_ok=True)
    with open(os.path.join(DOCS_DIR, "data", "events.json"), "w", encoding="utf-8") as f:
        json.dump(
            [{**e, "date": e["date"].isoformat(),
              "end_date": e["end_date"].isoformat() if e.get("end_date") else None}
             for e in events],
            f, ensure_ascii=False, indent=2,
        )


def _next_notable_event(org_slug):
    """First upcoming *major* (notable: true, not "medium") event for a
    given org slug, or None.

    Powers home.html's "Next DOD event" banner: restricted to the major
    tier specifically — see CLAUDE.md's notable: docs — so a merely
    "medium" borderline event doesn't get promoted to the homepage
    banner, which is reserved for genuinely major (rare, flagship-scale)
    occasions. Reads the same _events list calendar_events is bound to,
    already sorted ascending by date at on_pre_build, so the first match
    is the soonest one."""
    for e in _events:
        if e.get("org_slug") == org_slug and e.get("notable") is True:
            return e
    return None


def _format_event_date(d):
    """'2026-09-15' (a date object) -> 'Tuesday, 15 September 2026'.
    Built without strftime's %-d (a GNU/BSD extension, not portable to
    every platform strftime might run on) — same approach as
    hooks/event_card.py's _format_date, duplicated rather than imported
    since mkdocs hooks are registered/loaded as standalone files, not a
    package other hooks import from."""
    if not isinstance(d, date):
        return str(d)
    return d.strftime("%A, ") + str(d.day) + d.strftime(" %B %Y")


def _format_event_time(t):
    """'18:00' -> '6:00 PM'. Same strict HH:MM shape as event_card.py's
    _format_time; falls back to the raw string if it doesn't match."""
    try:
        parsed = datetime.strptime(str(t), "%H:%M")
    except ValueError:
        return str(t)
    hour12 = parsed.strftime("%I").lstrip("0") or "12"
    return hour12 + parsed.strftime(":%M %p")


def on_env(env, config, files):
    env.globals["calendar_events"] = _events
    env.globals["next_notable_event"] = _next_notable_event
    env.filters["country_name"] = lambda c: _COUNTRY_NAMES.get(str(c).upper(), str(c)) if c else ""
    env.filters["country_flag"] = lambda c: _flag_emoji(str(c)) if c else ""
    env.filters["format_event_date"] = _format_event_date
    env.filters["format_event_time"] = _format_event_time


def _flag_emoji(code):
    """Convert ISO 3166-1 alpha-2 to a flag emoji (regional indicator pair)."""
    code = code.upper()
    if len(code) != 2:
        return ""
    return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)


_COUNTRY_NAMES = {
    "AR": "Argentina", "AT": "Austria", "AU": "Australia", "BE": "Belgium",
    "BG": "Bulgaria", "BO": "Bolivia", "BR": "Brazil", "BW": "Botswana",
    "CA": "Canada", "CH": "Switzerland", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "CU": "Cuba", "DE": "Germany", "DK": "Denmark",
    "EC": "Ecuador", "EE": "Estonia", "ES": "Spain", "EU": "European Union",
    "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GH": "Ghana",
    "GR": "Greece", "ID": "Indonesia", "IL": "Israel", "IN": "India",
    "IS": "Iceland", "IT": "Italy", "JP": "Japan", "KE": "Kenya",
    "KR": "South Korea", "LB": "Lebanon", "MX": "Mexico", "MY": "Malaysia",
    "NG": "Nigeria", "NO": "Norway", "NZ": "New Zealand", "PH": "Philippines",
    "PL": "Poland", "PS": "Palestine", "RO": "Romania", "RU": "Russia",
    "RW": "Rwanda", "SE": "Sweden", "SK": "Slovakia", "SN": "Senegal",
    "SY": "Syria", "TW": "Taiwan", "UA": "Ukraine", "US": "United States",
    "VE": "Venezuela", "VN": "Vietnam", "ZA": "South Africa",
}
