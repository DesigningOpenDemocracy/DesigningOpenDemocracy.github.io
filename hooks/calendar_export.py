"""
calendar_export.py — MkDocs hook: build the site-wide future-events calendar.

Merges three sources of *future* events into one list at build time (no
network calls here — see util/sync_events.py for the fetch step that
populates the cache this reads):

  1. Manually curated `events:` entries in org frontmatter (date >= today)
  2. Cached iCal-synced events in docs/data/events/<slug>.json, written by
     util/sync_events.py for orgs with `ics_feed:` set (date >= today)
  3. DOD's own events, announced via an optional `event_date:` field on any
     (non-draft) blog post — distinct from `date:` (the post's publish date),
     since a post is usually written before or after the event it announces,
     not on the day itself.

Output:
  - docs/calendar.ics       — combined VCALENDAR, downloadable/subscribable
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

try:
    from pymdownx.slugs import slugify as _pymdownx_slugify
    _slugify = _pymdownx_slugify(case="lower")
except ImportError:
    _slugify = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
BLOG_POSTS_DIR = os.path.join(DOCS_DIR, "blog", "posts")
SYNCED_EVENTS_DIR = os.path.join(DOCS_DIR, "data", "events")
SKIP_FILES = {"organisations.md"}
DOD_TITLE = "Designing Open Democracy"

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
                    "url": entry.get("url", ""),
                    "org_slug": slug,
                    "org_title": m.get("title", slug),
                    "source": "manual",
                    "notable": bool(entry.get("notable")),
                    "logo": _org_logo(slug),
                    "country": m.get("country"),
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
                    "country": _org_country(slug),
                }
                _maybe_add_translation(evt, evt["title"], evt["org_title"])
                out.append(evt)
    return out


def _load_blog_events(today):
    """DOD's own future events, from `event_date:` on non-draft blog posts.

    The post's URL is computed with the same {date}/{slug} scheme and
    pymdownx slugify function mkdocs-material's blog plugin uses by default
    (verified against a real built post) — this hook runs at on_pre_build,
    before pages have real page.url values to read instead.
    """
    if frontmatter is None or _slugify is None:
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(BLOG_POSTS_DIR, "*.md"))):
        post = frontmatter.load(path)
        m = post.metadata
        if m.get("draft"):
            continue
        event_d = _parse_date(m.get("event_date"))
        if not event_d or event_d < today:
            continue
        post_d = _parse_date(m.get("date"))
        if not post_d:
            continue
        slug = _slugify(m.get("title", ""), "-")
        out.append({
            "date": event_d,
            "end_date": _parse_date(m.get("event_end_date")),
            "title": m.get("title", "Untitled post"),
            "url": f"/blog/{post_d:%Y/%m/%d}/{slug}/",
            "org_slug": "",
            "org_title": DOD_TITLE,
            "source": "blog",
            "notable": bool(m.get("event_notable")),
            "logo": "/assets/dodlogo_transparent.png",
            "country": "AU",
        })
    return out


def _ics_escape(s):
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _write_ics(events, path):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Designing Open Democracy//Democracy Landscape Calendar//EN",
        "X-WR-CALNAME:Designing Open Democracy — Democracy Landscape Calendar",
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
            f"DTSTART;VALUE=DATE:{dt}",
        ]
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
        f.write("\r\n".join(lines) + "\r\n")


def on_pre_build(config):
    if frontmatter is None:
        return
    today = date.today()
    events = _load_manual_events(today) + _load_synced_events(today) + _load_blog_events(today)
    events.sort(key=lambda e: e["date"])

    _events.clear()
    _events.extend(events)

    _write_ics(events, os.path.join(DOCS_DIR, "calendar.ics"))

    os.makedirs(os.path.join(DOCS_DIR, "data"), exist_ok=True)
    with open(os.path.join(DOCS_DIR, "data", "events.json"), "w", encoding="utf-8") as f:
        json.dump(
            [{**e, "date": e["date"].isoformat(),
              "end_date": e["end_date"].isoformat() if e.get("end_date") else None}
             for e in events],
            f, ensure_ascii=False, indent=2,
        )


def on_env(env, config, files):
    env.globals["calendar_events"] = _events
    env.filters["country_name"] = lambda c: _COUNTRY_NAMES.get(str(c).upper(), str(c)) if c else ""
    env.filters["country_flag"] = lambda c: _flag_emoji(str(c)) if c else ""


def _flag_emoji(code):
    """Convert ISO 3166-1 alpha-2 to a flag emoji (regional indicator pair)."""
    code = code.upper()
    if len(code) != 2:
        return ""
    return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)


_COUNTRY_NAMES = {
    "AR": "Argentina", "AT": "Austria", "AU": "Australia", "BE": "Belgium",
    "BO": "Bolivia", "BR": "Brazil", "CA": "Canada", "CH": "Switzerland",
    "CL": "Chile", "CN": "China", "CO": "Colombia", "CU": "Cuba",
    "DE": "Germany", "DK": "Denmark", "EC": "Ecuador", "EE": "Estonia",
    "ES": "Spain", "EU": "European Union", "FI": "Finland", "FR": "France",
    "GB": "United Kingdom", "GH": "Ghana", "ID": "Indonesia", "IL": "Israel",
    "IN": "India", "IS": "Iceland", "IT": "Italy", "JP": "Japan",
    "KE": "Kenya", "KR": "South Korea", "LB": "Lebanon", "MX": "Mexico",
    "MY": "Malaysia", "NG": "Nigeria", "NO": "Norway", "NZ": "New Zealand",
    "PH": "Philippines", "PL": "Poland", "PS": "Palestine", "RO": "Romania",
    "RU": "Russia", "RW": "Rwanda", "SE": "Sweden", "SK": "Slovakia",
    "SN": "Senegal", "SY": "Syria", "TW": "Taiwan", "UA": "Ukraine",
    "US": "United States", "VE": "Venezuela", "VN": "Vietnam", "ZA": "South Africa",
}
