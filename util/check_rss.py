#!/usr/bin/env python3
"""
check_rss.py — Probe org websites for common RSS/Atom feed paths.

For each org page with a live website (non-Wayback), tries a list of
common feed URL patterns. Reports which URLs return a valid feed
(Content-Type: xml or rss, or body starts with <rss / <feed / <?xml).

Usage:
    python util/check_rss.py              # check all active orgs
    python util/check_rss.py --all        # include inactive orgs
    python util/check_rss.py --slug loomio  # check one org by slug
    python util/check_rss.py --timeout 8    # per-request timeout in seconds
    python util/check_rss.py --output results.json  # write JSON output
    python util/check_rss.py --update-activity      # fetch feeds and update last_activity

Requirements: requests (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from frontmatter_io import split_frontmatter  # noqa: E402
from robots_check import load_robots, robots_allowed  # noqa: E402

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

DOD_USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"index.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = datetime.today().strftime("%Y-%m-%d")

# An org read this many days ago or more is read again; anything more recent
# is skipped (--force overrides). Strictly less-than on purpose: the weekly
# cron fires exactly 7 days after the run that stamped `checked:`, and a
# `<= 7` here skipped every org on alternate weeks, so feeds were really read
# fortnightly (the 2026-09-18 run touched 4 org pages; the runs either side,
# 139). A scheduled run can start late but never early, so the next one sees
# an age of at least 7 unless this one was delayed past midnight UTC (it's
# scheduled for 03:00).
RECHECK_DAYS = 7

# Recent posts from each org's feed, saved on every --update-activity read for
# util/news_checkup.py (see save_feed_items). Kept for half a year, which is
# longer than anyone should leave a checkup, and capped so one prolific feed
# can't grow its file without bound.
FEED_ITEMS_DIR = os.path.join(DOCS_DIR, "data", "feed-items")
FEED_ITEMS_KEEP_DAYS = 180
FEED_ITEMS_MAX = 50

# Common feed URL paths to probe (tried in order, stop at first hit)
FEED_PATHS = [
    "/feed",
    "/feed.xml",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/rss/",
    "/atom.xml",
    "/atom/",
    "/feeds/all.atom.xml",
    "/feeds/posts/default",
    "/blog/feed",
    "/blog/feed.xml",
    "/blog/rss.xml",
    "/blog/rss",
    "/news/feed",
    "/news/rss",
    "/news/feed.xml",
    "/wp-json/wp/v2/posts?_embed",  # WordPress REST (JSON)
    "/wp-rss2.php",
    "/?feed=rss2",
    "/?feed=rss",
    "/?feed=atom",
    "/index.xml",
]

# Sitemap paths tried in order when no RSS/Atom feed is found.
# robots.txt Sitemap: declarations are checked first (see probe_sitemap()).
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemaps.xml",
]

# Content-type fragments that indicate a feed
FEED_CONTENT_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
    "application/xml",
    "text/xml",
    "text/rss+xml",
    "text/atom+xml",
}

# Body prefixes for feed detection (case-insensitive start)
FEED_BODY_PREFIXES = (
    b"<?xml",
    b"<rss",
    b"<feed",
    b'{"version":"https://jsonfeed.org',
    b'{"version": "https://jsonfeed.org',
)


def looks_like_feed(response):
    ct = response.headers.get("Content-Type", "").lower()
    if any(f in ct for f in FEED_CONTENT_TYPES):
        return True
    body = response.content[:512].lstrip()
    return body.startswith(FEED_BODY_PREFIXES)


def is_sitemap_url(url):
    """True if url looks like a sitemap rather than an RSS/Atom feed."""
    return "sitemap" in urlparse(url).path.lower()


def probe_sitemap(base_url, timeout=8, session=None):
    """Return a sitemap URL for base_url, or None.

    Checks robots.txt for Sitemap: declarations first, then falls back to
    SITEMAP_PATHS. Handles both /sitemap.xml and /sitemap_index.xml. Any
    candidate path robots.txt disallows for DOD-Bot is skipped — same
    fetch also builds the RobotFileParser used for that gate, so this
    doesn't cost a second robots.txt request beyond the Sitemap: lookup
    it was already doing.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = DOD_USER_AGENT

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    rp = RobotFileParser()
    robots_url = urljoin(root, "/robots.txt")
    rp.set_url(robots_url)

    # 1. robots.txt Sitemap: declarations are the canonical source
    try:
        r = session.get(robots_url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            rp.parse(r.text.splitlines())
            for line in r.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    candidate = line.split(":", 1)[1].strip()
                    if not candidate.startswith("http"):
                        candidate = urljoin(root, candidate)
                    if not rp.can_fetch(DOD_USER_AGENT, candidate):
                        continue
                    try:
                        chk = session.get(candidate, timeout=timeout, allow_redirects=True)
                        if chk.status_code == 200:
                            return candidate
                    except RequestException:
                        pass
    except RequestException:
        pass  # unreachable robots.txt → rp has no rules → allows everything below

    # 2. Standard paths
    for path in SITEMAP_PATHS:
        url = urljoin(root, path)
        if not rp.can_fetch(DOD_USER_AGENT, url):
            continue
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and r.content:
                return url
        except RequestException:
            pass

    return None


def probe_feeds(base_url, timeout=8, session=None):
    """Return the first feed URL found (RSS/Atom/sitemap), or None. Skips
    any candidate feed path robots.txt disallows for DOD-Bot."""
    if session is None:
        session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    rp = load_robots(root, timeout=timeout, session=session)

    for path in FEED_PATHS:
        url = urljoin(root, path)
        if not rp.can_fetch(DOD_USER_AGENT, url):
            continue
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and looks_like_feed(r):
                return url
        except RequestException:
            pass

    # Fallback: sitemap (at least proves the site is alive)
    return probe_sitemap(root, timeout=timeout, session=session)


def latest_sitemap_lastmod(sitemap_url, timeout=10, session=None):
    """Return the most recent <lastmod> date from a sitemap, or None."""
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = DOD_USER_AGENT
    try:
        r = session.get(sitemap_url, timeout=timeout)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return None

    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    local = re.sub(r"\{[^}]*\}", "", root.tag).lower()
    dates = []

    if local == "sitemapindex":
        for sitemap in root.findall(f"{ns}sitemap")[:5]:
            lm = sitemap.findtext(f"{ns}lastmod")
            if lm:
                d = parse_date(lm.strip())
                if d:
                    dates.append(d)
    elif local == "urlset":
        for url in root.findall(f"{ns}url"):
            lm = url.findtext(f"{ns}lastmod")
            if lm:
                d = parse_date(lm.strip())
                if d:
                    dates.append(d)

    return max(dates) if dates else None


def parse_date(s):
    """Parse RSS (RFC 2822), Atom (ISO 8601), or iCal (YYYYMMDD) date strings robustly."""
    if not s:
        return None
    s = s.strip()
    # RFC 2822 (most RSS feeds)
    try:
        return parsedate_to_datetime(s).date()
    except Exception:
        pass
    # ISO 8601 — strip sub-seconds, use fromisoformat for tz handling
    try:
        clean = re.sub(r"\.\d+", "", s)
        return datetime.fromisoformat(clean).date()
    except Exception:
        pass
    # bare date fallback
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    # iCal compact: YYYYMMDD or YYYYMMDDThhmmss
    try:
        return datetime.strptime(s[:8], "%Y%m%d").date()
    except ValueError:
        pass
    return None


def latest_from_ical(url, timeout=10, session=None):
    """Fetch an iCal (.ics) URL and return (date, title, http_ok) of the most recent past event.

    Only considers events with DTSTART in the past so upcoming events don't
    inflate activity dates.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "DOD-ICS-Reader/1.0 (democracy wiki)"
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except RequestException:
        return None, None, False

    today = datetime.today().date()
    entries = []

    # Unfold continuation lines per RFC 5545 §3.1
    text = r.text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)

    in_vevent = False
    current_start = None
    current_summary = ""

    for line in text.split("\n"):
        if line == "BEGIN:VEVENT":
            in_vevent = True
            current_start = None
            current_summary = ""
        elif line == "END:VEVENT":
            if in_vevent and current_start:
                d = parse_date(current_start)
                if d and d <= today:
                    entries.append((d, current_summary))
            in_vevent = False
        elif in_vevent:
            if line.startswith("DTSTART"):
                # DTSTART:20260630, DTSTART;TZID=...:20260630T000000,
                # DTSTART;VALUE=DATE:20260630
                val = line.split(":", 1)[-1].strip()
                current_start = val[:8]
            elif line.startswith("SUMMARY:"):
                current_summary = line[8:].strip()

    if not entries:
        return None, None, True
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries[0][0], entries[0][1], True


def fetch_feed_entries(url, timeout=10, session=None):
    """Fetch url and return (entries, http_ok): every dated item the feed
    lists (see parse_feed_entries), and whether the server answered 200.
    entries is [] both when the fetch failed and when a reachable feed had
    nothing parseable; http_ok tells the two apart."""
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = DOD_USER_AGENT
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except RequestException:
        return [], False
    return parse_feed_entries(r.content), True


def latest_entry(entries):
    """(date, title, link) of the most recent entry, or three Nones. The sort
    is stable, so of several items on the same day the one listed first in
    the feed wins, as it always has."""
    if not entries:
        return None, None, None
    latest = sorted(entries, key=lambda e: e["date"], reverse=True)[0]
    return latest["date"], latest["title"], latest["link"]


def _feed_item_key(item):
    return item.get("url") or f"{item.get('date')}|{item.get('title')}"


def strip_tracking(url):
    """Drop utm_* parameters (WordPress's RSS plugins add them to every
    link), so a link copied from the news checkup into an event's `url:`
    is the plain citation, not a campaign-tagged one."""
    parts = urlsplit(url or "")
    if "utm_" not in parts.query:
        return url or ""
    query = "&".join(p for p in parts.query.split("&") if p and not p.lower().startswith("utm_"))
    return urlunsplit(parts._replace(query=query))


def merge_feed_items(existing, entries, today, keep_days=None, max_items=None):
    """The post list to store for one org: what was stored before plus what
    the feed lists now, deduplicated by URL, pruned to posts published within
    keep_days of today, newest first, capped at max_items.

    Merged rather than replaced because a feed only lists its latest N
    posts: an org that publishes more than that between two reads would
    otherwise lose the middle ones before anyone reviewed them. A post the
    feed still lists wins over its stored copy, so a retitled post updates.
    """
    keep_days = FEED_ITEMS_KEEP_DAYS if keep_days is None else keep_days
    max_items = FEED_ITEMS_MAX if max_items is None else max_items
    fresh = [{"date": e["published"].isoformat(), "title": e["title"], "url": strip_tracking(e["link"])}
             for e in entries]
    merged = {}
    for item in list(existing or []) + fresh:
        merged[_feed_item_key(item)] = item
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    kept = [i for i in merged.values() if str(i.get("date", "")) >= cutoff]
    kept.sort(key=lambda i: (str(i["date"]), i.get("title", ""), i.get("url", "")), reverse=True)
    return kept[:max_items]


def save_feed_items(slug, feed_url, entries, today=None, items_dir=None):
    """Merge a feed's current entries into docs/data/feed-items/<slug>.json.

    The cache util/news_checkup.py reads, so the news checkup never has to
    fetch a feed this script has already downloaded (see that script's
    docstring). Dates, titles and links only: no summaries or post text,
    the same reason citation-state.json holds hashes rather than page bodies.
    `latest` is the newest post the feed listed on this read, even one old
    enough to have been pruned from `items`, and null when the feed listed
    nothing: that's how the checkup tells a dormant feed from an empty or
    broken one. The file carries no "checked" date, so it only changes when
    the posts do; when the feed was last read is the org's
    activity.rss.checked, written in the same pass. Returns True if the file
    changed."""
    today = today or datetime.today().date()
    items_dir = items_dir or FEED_ITEMS_DIR
    path = os.path.join(items_dir, f"{slug}.json")
    existing = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f).get("items") or []
        except (OSError, ValueError, AttributeError):
            existing = []
    latest = max((e["published"] for e in entries), default=None)
    data = {"feed": feed_url, "latest": latest.isoformat() if latest else None,
            "items": merge_feed_items(existing, entries, today)}
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    os.makedirs(items_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"


def _atom_post_link(entry, ns):
    """The post's own page. Atom entries often carry several <link>s, and
    the first isn't always the post: Blogger's list rel="replies" and
    rel="edit" ahead of rel="alternate". Falls back to the first link,
    then to <id>."""
    links = entry.findall(f"{ns}link")
    for el in links:
        if el.get("rel") in (None, "alternate") and el.get("href"):
            return el.get("href")
    if links and links[0].get("href"):
        return links[0].get("href")
    return entry.findtext(f"{ns}id") or ""


def parse_feed_entries(content):
    """Every dated item in an RSS 2.0 or Atom document, in feed order, as
    dicts: date, published, title, link.

    `date` is what the activity check has always keyed on (Atom's <updated>
    before <published>). `published` is when the post first went out, where
    the feed says so separately; it's what a news checkup wants, since an
    old post edited today isn't new. Undated items are dropped.
    Returns [] for anything that doesn't parse as XML.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    local = re.sub(r"\{[^}]*\}", "", root.tag).lower()
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    entries = []

    if local == "rss":
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            d = parse_date(item.findtext("pubDate") or item.findtext(_DC_DATE))
            link = (item.findtext("link") or "").strip()
            if not link:
                guid = (item.findtext("guid") or "").strip()
                if guid.startswith(("http://", "https://")):
                    link = guid
            if d:
                entries.append({"date": d, "published": d, "title": title, "link": link})
    elif local == "feed":
        for entry in root.findall(f"{ns}entry"):
            title_el = entry.find(f"{ns}title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            published = parse_date(entry.findtext(f"{ns}published"))
            d = parse_date(entry.findtext(f"{ns}updated")) or published
            if d:
                entries.append({"date": d, "published": published or d, "title": title,
                                "link": _atom_post_link(entry, ns)})
    return entries


def update_activity_source(path, date_str, note, feed_url, post_url=None, method="rss"):
    """Write or update a single source entry under activity.<method> in org frontmatter.

    Only updates if the new date is strictly newer than the existing entry for
    that source — so a stale RSS scan never clobbers a fresher manual entry.
    """
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    yaml_block, rest = split_frontmatter(content)
    if yaml_block is None:
        return False

    meta = _yaml.safe_load(yaml_block) or {}

    # Guard: don't overwrite a newer or equal entry for this specific source.
    # Exception: placeholder notes from feed-discovery-only passes (no actual
    # post data fetched yet) are always overwritten so --update-activity can
    # replace them with real "Latest post: …" data.
    _PLACEHOLDER_NOTES = {
        "RSS feed discovered",
        "RSS feed active",
        "Server still up (sitemap detected)",
    }
    existing_source = (meta.get("activity") or {}).get(method) or {}
    existing_note = str(existing_source.get("note", "") or "")
    existing_date = parse_date(str(existing_source.get("date", "") or ""))
    new_date = parse_date(date_str)
    if existing_note not in _PLACEHOLDER_NOTES and existing_date and new_date and new_date <= existing_date:
        return False

    # Build the new source sub-block lines
    url_field = post_url or feed_url
    source_lines = [
        f"  {method}:",
        f"    date: {date_str}",
        f"    note: {json.dumps(note, ensure_ascii=False)}",
        f"    url: {url_field}",
        f"    checked: {TODAY}",
    ]

    if meta.get("activity"):
        # activity: block already exists — replace just this source's
        # sub-block, or insert it fresh if this method has no entry yet.
        #
        # `found` tracks whether source_lines have been written, so it can
        # be checked both mid-loop (when the activity: block ends at the
        # frontmatter's next top-level key, e.g. last_checked: — the common
        # case, since canonical field order always puts one there) and
        # after the loop (when activity: is the very last frontmatter key,
        # so the block ends at end-of-file instead). Two real bugs lived
        # here from conflating this with a separate in_this_source flag
        # that didn't reset after a replacement completed: an existing
        # source got its replacement inserted a second time whenever
        # followed by a top-level key (duplicate keys — the 2026-08-17
        # activity probe's designing-open-democracy.md/g0v.md corruption),
        # and a *new* source silently never got written at all in that same
        # common case, because the old "did we ever find it" check only
        # fired when the block ran to end-of-file. See
        # tests/test_frontmatter_writers.py.
        lines = yaml_block.split("\n")
        new_lines = []
        in_activity = False
        found = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^activity\s*:", line):
                in_activity = True
                new_lines.append(line)
                i += 1
                continue
            if in_activity:
                # Detect a top-level key (end of activity block)
                if line and not line.startswith(" "):
                    if not found:
                        new_lines.extend(source_lines)
                        found = True
                    in_activity = False
                    new_lines.append(line)
                    i += 1
                    continue
                # Detect this source's sub-block and replace it in place
                if re.match(rf"^  {method}\s*:", line):
                    found = True
                    i += 1
                    while i < len(lines) and lines[i].startswith("    "):
                        i += 1
                    new_lines.extend(source_lines)
                    continue
                new_lines.append(line)
                i += 1
                continue
            new_lines.append(line)
            i += 1

        # activity: was the last frontmatter key, so the loop ended without
        # ever hitting the boundary branch above.
        if in_activity and not found:
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            new_lines.extend(source_lines)

        yaml_block = "\n".join(new_lines)
        if not yaml_block.endswith("\n"):
            yaml_block += "\n"
    else:
        # No activity: block yet — append a fresh one
        new_block = ["activity:"] + source_lines
        yaml_block = yaml_block.rstrip("\n") + "\n" + "\n".join(new_block) + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def write_checked_only(path, method, note=None):
    """Add/update checked: <TODAY> on an activity source entry.

    If the source entry doesn't exist, creates a minimal entry with note and
    checked (no date/url).  If it exists, adds/updates only the checked: field
    without touching date, note, or url.
    """
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    yaml_block, rest = split_frontmatter(content)
    if yaml_block is None:
        return False
    meta = _yaml.safe_load(yaml_block) or {}
    activity = meta.get("activity") or {}

    minimal = [f"  {method}:"]
    if note:
        minimal.append(f"    note: {json.dumps(note, ensure_ascii=False)}")
    minimal.append(f"    checked: {TODAY}")

    if not activity:
        yaml_block = yaml_block.rstrip("\n") + "\nactivity:\n" + "\n".join(minimal) + "\n"

    elif method not in activity:
        # Append minimal entry into existing activity: block
        lines = yaml_block.split("\n")
        new_lines = []
        in_activity = False
        inserted = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^activity\s*:", line):
                in_activity = True
                new_lines.append(line)
                i += 1
                continue
            if in_activity and line and not line.startswith(" "):
                if not inserted:
                    new_lines.extend(minimal)
                    inserted = True
                in_activity = False
                new_lines.append(line)
                i += 1
                continue
            new_lines.append(line)
            i += 1
        if in_activity and not inserted:
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            new_lines.extend(minimal)
        yaml_block = "\n".join(new_lines)

    else:
        # Source exists — update or insert the checked: line in its sub-block
        lines = yaml_block.split("\n")
        new_lines = []
        in_this_source = False
        checked_written = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(rf"^  {method}\s*:", line):
                in_this_source = True
                new_lines.append(line)
                i += 1
                continue
            if in_this_source:
                # Another source block or top-level key ends this sub-block
                if re.match(r"^  \w", line) or (line and not line.startswith("    ")):
                    if not checked_written:
                        new_lines.append(f"    checked: {TODAY}")
                        checked_written = True
                    in_this_source = False
                elif re.match(r"^    checked\s*:", line):
                    new_lines.append(f"    checked: {TODAY}")
                    checked_written = True
                    i += 1
                    continue
            new_lines.append(line)
            i += 1
        if in_this_source and not checked_written:
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            new_lines.append(f"    checked: {TODAY}")
        yaml_block = "\n".join(new_lines)

    if not yaml_block.endswith("\n"):
        yaml_block += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def load_orgs(slug_filter=None, include_inactive=False):
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata
        slug = os.path.basename(path)[:-3]
        if slug_filter and slug != slug_filter:
            continue
        website = meta.get("website", "") or ""
        if not website or WAYBACK_PREFIX in website:
            continue
        status = meta.get("status", "")
        if not include_inactive and status not in ("active",):
            continue
        orgs.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "website": website,
            "status": status,
            "rss_feed": meta.get("rss_feed") or "",
            "ics_feed": meta.get("ics_feed") or "",
            "path": path,
            "activity": meta.get("activity") or {},
        })
    return orgs


def main():
    parser = argparse.ArgumentParser(description="Probe org websites for RSS/Atom feeds")
    parser.add_argument("--all", action="store_true", help="Include inactive orgs (default: active only)")
    parser.add_argument("--slug", metavar="SLUG", help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=8, metavar="N", help="Per-request timeout in seconds (default: 8)")
    parser.add_argument("--output", metavar="FILE", help="Write JSON results to FILE")
    parser.add_argument("--skip-existing", action="store_true", help="Skip orgs that already have rss_feed:")
    parser.add_argument("--update-activity", action="store_true",
                        help="Fetch each discovered (or existing) feed and update last_activity with latest post date/title")
    parser.add_argument("--force", action="store_true",
                        help="Probe all orgs even if recently checked (ignores activity.*.checked)")
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages found matching criteria.")
        sys.exit(0)

    session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})

    results = []
    found = []
    not_found = []
    skipped = []

    print(f"\nProbing {len(orgs)} org websites for feeds (timeout={args.timeout}s)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        if args.skip_existing and org["rss_feed"]:
            skipped.append(org)
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has rss_feed)")
            continue

        # Skip orgs checked recently unless --force
        if not args.force and args.update_activity:
            activity = org.get("activity", {})
            recent_age = None
            for chk_method in ("rss", "sitemap"):
                entry = activity.get(chk_method) or {}
                chk_date = parse_date(str(entry.get("checked", "") or ""))
                if chk_date:
                    age = (datetime.today().date() - chk_date).days
                    if age < RECHECK_DAYS:
                        recent_age = age
                        break
            if recent_age is not None:
                print(f"  [{i:3d}/{len(orgs)}] {slug} … SKIPPED (checked {recent_age}d ago)")
                skipped.append(org)
                results.append({**org, "feed_url": None, "skipped_checked": True})
                continue

        # Use existing rss_feed if present, otherwise probe
        feed_url = org["rss_feed"] or probe_feeds(org["website"], timeout=args.timeout, session=session)

        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)

        # An already-configured rss_feed: skips probe_feeds()'s own gating
        # above, so re-check here — the site's robots.txt may have changed
        # since the feed was recorded.
        if feed_url and not robots_allowed(feed_url, DOD_USER_AGENT, timeout=args.timeout, session=session):
            print(f"BLOCKED by robots.txt  {feed_url}")
            skipped.append(org)
            results.append({**org, "feed_url": None, "skipped_robots": True})
            continue

        result = {**org, "feed_url": feed_url}

        if feed_url:
            if args.update_activity:
                if is_sitemap_url(feed_url):
                    d = latest_sitemap_lastmod(feed_url, timeout=args.timeout, session=session)
                    if d:
                        if not update_activity_source(org["path"], d.isoformat(),
                                                      "Page last modified (from sitemap)", feed_url,
                                                      method="sitemap"):
                            write_checked_only(org["path"], "sitemap")
                        print(f"SITEMAP  {d}")
                        result["latest_date"] = d.isoformat()
                    else:
                        write_checked_only(org["path"], "sitemap", "Sitemap found, no lastmod")
                        print(f"SITEMAP (no lastmod)  {feed_url}")
                else:
                    entries, http_ok = fetch_feed_entries(feed_url, timeout=args.timeout, session=session)
                    d, title, link = latest_entry(entries)
                    if http_ok:
                        # Saved even when empty, so the news checkup can tell a
                        # feed that answers with nothing apart from one never read.
                        save_feed_items(slug, feed_url, entries)
                    if d:
                        note = f"Latest post: {title[:80]}" if title else "RSS feed active"
                        if not update_activity_source(org["path"], d.isoformat(), note, feed_url, link or None):
                            write_checked_only(org["path"], "rss")
                        print(f"UPDATED  {d}  {title[:50]}")
                        result["latest_date"] = d.isoformat()
                        result["latest_title"] = title
                    elif http_ok:
                        # Feed responded 200 but no parseable posts; upgrade any placeholder
                        # note so the entry at least reads as "RSS feed active" rather than
                        # "RSS feed discovered" (the old probe-only placeholder).
                        update_activity_source(org["path"], TODAY, "RSS feed active",
                                               feed_url, method="rss")
                        print(f"FOUND (no parseable posts)  {feed_url}")
                    else:
                        print(f"UNREACHABLE (keeping existing activity)  {feed_url}")
            else:
                print(f"FOUND  {feed_url}")
            found.append(result)
        else:
            if args.update_activity:
                write_checked_only(org["path"], "rss", "No feed found")
            print("not found")
            not_found.append(result)

        results.append(result)
        time.sleep(0.3)

    # --- iCal feeds ---
    if args.update_activity:
        ical_orgs = [o for o in orgs if o.get("ics_feed")]
        if ical_orgs:
            print(f"\nChecking {len(ical_orgs)} iCal feed(s) (timeout={args.timeout}s)…\n")
            for i, org in enumerate(ical_orgs, 1):
                slug = org["slug"]
                ics_url = org["ics_feed"]
                print(f"  [{i:3d}/{len(ical_orgs)}] {slug} … ", end="", flush=True)

                if not args.force:
                    entry = (org.get("activity") or {}).get("ical") or {}
                    chk_date = parse_date(str(entry.get("checked", "") or ""))
                    if chk_date:
                        age = (datetime.today().date() - chk_date).days
                        if age < RECHECK_DAYS:
                            print(f"SKIPPED (checked {age}d ago)")
                            continue

                if not robots_allowed(ics_url, DOD_USER_AGENT, timeout=args.timeout, session=session):
                    print(f"BLOCKED by robots.txt  {ics_url}")
                    continue

                d, title, ok = latest_from_ical(ics_url, timeout=args.timeout, session=session)
                if not ok:
                    print(f"UNREACHABLE  {ics_url}")
                elif d is None:
                    write_checked_only(org["path"], "ical", "iCal feed found, no past events")
                    print(f"NO_PAST_EVENTS  {ics_url}")
                else:
                    note = f"Latest event: {title[:80]}" if title else "Latest calendar event"
                    if not update_activity_source(org["path"], d.isoformat(), note, ics_url, method="ical"):
                        write_checked_only(org["path"], "ical")
                    print(f"UPDATED  {d}  {title[:50] if title else '(no title)'}")

                time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Found feeds for {len(found)} / {len(orgs) - len(skipped)} orgs checked")
    if skipped:
        print(f"Skipped {len(skipped)} orgs (already have rss_feed:)")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
