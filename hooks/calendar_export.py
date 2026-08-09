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
import uuid
from datetime import date, datetime

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
                out.append({
                    "date": d,
                    "title": entry.get("title", "Untitled event"),
                    "url": entry.get("url", ""),
                    "org_slug": slug,
                    "org_title": m.get("title", slug),
                    "source": "manual",
                })
    return out


def _load_synced_events(today):
    """Future events cached from ics_feed syncs (util/sync_events.py)."""
    if frontmatter is None:
        return []
    # Map slug -> org title so entries can carry a display name.
    titles = {}
    for path in glob.glob(os.path.join(ORGS_DIR, "*.md")):
        if os.path.basename(path) in SKIP_FILES:
            continue
        slug = os.path.basename(path)[:-3]
        titles[slug] = frontmatter.load(path).metadata.get("title", slug)

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
                out.append({
                    "date": d,
                    "title": entry.get("title", "Untitled event"),
                    "url": entry.get("url", ""),
                    "org_slug": slug,
                    "org_title": titles.get(slug, slug),
                    "source": "ical",
                })
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
            "title": m.get("title", "Untitled post"),
            "url": f"/blog/{post_d:%Y/%m/%d}/{slug}/",
            "org_slug": "",
            "org_title": DOD_TITLE,
            "source": "blog",
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
            [{**e, "date": e["date"].isoformat()} for e in events],
            f, ensure_ascii=False, indent=2,
        )


def on_env(env, config, files):
    env.globals["calendar_events"] = _events
