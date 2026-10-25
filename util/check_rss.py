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
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
import backoff  # noqa: E402
import news_signals  # noqa: E402
from frontmatter_io import split_frontmatter, write_rss_feed  # noqa: E402
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

# How often each kind of org is read. The unit is days since the source was
# last read (activity.<method>.checked), and an org is skipped while that's
# under the interval; --force overrides all of it.
#
# FEED_RECHECK_DAYS: an org with a live feed, by default. Most orgs in the
# landscape post a few times a month at most: of the 22 feeds with posts in
# the six months to 2026-09-28, 20 listed more than a month of posts at
# once, so a monthly read misses nothing.
FEED_RECHECK_DAYS = 28
# RECHECK_DAYS: a feed that turns over faster than that, whose listed posts
# (at least BUSY_MIN_POSTS of them) span under BUSY_SPAN_DAYS, is read
# weekly, or posts would drop off it between reads: Afrobarometer listed 10
# posts in 10 days, Kongra Star 10 in 14. Judged from the feed's own last
# read (`span_days` in its state file), so it adjusts as an org gets busier
# or quieter. Also the interval for ics_feed: activity reads.
#
# Strictly less-than on purpose: the weekly cron fires exactly 7 days after
# the run that stamped `checked:`, and a `<= 7` here skipped every org on
# alternate weeks, so feeds were really read fortnightly (the 2026-09-18 run
# touched 4 org pages; the runs either side, 139). A scheduled run can start
# late but never early, so the next one sees an age of at least 7 unless
# this one was delayed past midnight UTC (it's scheduled for 03:00). The
# same holds for 28: a monthly read lands on every fourth weekly run.
RECHECK_DAYS = 7
BUSY_SPAN_DAYS = 35
BUSY_MIN_POSTS = 5
# A feed whose newest post is older than DORMANT_FEED_DAYS, or that lists no
# posts at all, is read quarterly: monthly reads of a feed that last changed
# in 2019 are just traffic, and a quarter is soon enough to notice it's back.
DORMANT_FEED_DAYS = 180
DORMANT_RECHECK_DAYS = 90
# An org with no feed: the 23-path discovery probe (plus robots.txt and
# sitemap guesses) runs at most this often, spread per org by
# backoff.spread_days() so a batch probed on one day doesn't all fall due
# on one day again. In between, only its known sitemap (if any) is read,
# every SITEMAP_RECHECK_DAYS. Until 2026-09-28 the probe ran on every run
# for every org without `rss_feed:` (108 of them, about 2,200 requests a
# run, mostly 404s), and a feed it found was never saved, so it was
# rediscovered each time.
FEED_REPROBE_DAYS = 90
SITEMAP_RECHECK_DAYS = 28
# A feed body larger than this is abandoned mid-download and counts as a
# failure (TOO_LARGE). The largest real feed in the landscape was a 22 MB
# malformed one, downloaded in full every week and never parsed.
FEED_MAX_BYTES = 5 * 1024 * 1024

# What the probe knows about each org's feed, one file per org:
# docs/data/feeds/<slug>.json. Recent posts for util/news_checkup.py, the
# validators for conditional GET, a failure record for backoff, and for an
# org with no feed, when discovery last ran and which sitemap it found. See
# save_feed_items() for the layout. Posts are kept for half a year, which is
# longer than anyone should leave a checkup, and capped so one prolific
# feed can't grow its file without bound.
FEEDS_DIR = os.path.join(DOCS_DIR, "data", "feeds")
FEED_ITEMS_KEEP_DAYS = 180
FEED_ITEMS_MAX = 50

# An org with no feed often still publishes a sitemap, and a page that wasn't
# in it last time is usually something new: a campaign, an event, a report.
# Australian Democracy Network's site is a JavaScript app with no feed, so
# nothing it published reached the news checkup, though its sitemap listed
# its new Declaration campaign page and two event pages within days of them
# going up (2026-10-25). So when the probe reads a sitemap it also keeps the
# list of page URLs (`seen`) and records any URL not seen on the last read
# as a new page (`pages`), titled from its URL, for news_checkup.py. The
# first read is a baseline and lists nothing. A sitemap listing more than
# SITEMAP_SEEN_MAX pages isn't tracked (a large CMS or a platform's own
# sitemap, like YouTube's, would bloat the state file and say little), and
# archive-style paths (tags, categories, authors, pagination) are ignored,
# since a CMS adds those as a side effect of a post rather than as news.
# A sitemap index is followed to one child sitemap: the one with the newest
# <lastmod>, or the first post/page/news/event one when none carry a date,
# skipping author/tag/category children (Democracy Technologies' newest was
# its author sitemap, every URL of which the archive-path filter drops).
# `seen` holds a 12-hex-digit hash of each URL rather than the URL: it only
# has to answer "was this here last time?", and the URLs themselves made the
# baseline ~11,000 lines across 40 orgs (Memorial's alone 125 KB).
SITEMAP_SEEN_MAX = 2000
SITEMAP_PAGES_KEEP_DAYS = FEED_ITEMS_KEEP_DAYS
SITEMAP_PAGES_MAX = FEED_ITEMS_MAX
_SITEMAP_ARCHIVE_PATH = re.compile(
    r"/(tag|tags|category|categories|author|authors|page|feed|wp-content|search|"
    r"login|account|cart|checkout)(/|$)", re.IGNORECASE)
_SITEMAP_CHILD_HINT = re.compile(r"post|page|news|event|article|blog", re.IGNORECASE)
_SITEMAP_ARCHIVE_CHILD = re.compile(r"author|tag|categor|attachment", re.IGNORECASE)

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


def _lists_posts(body):
    """Whether a discovery candidate is a feed worth recording: an XML body
    has to list at least one dated post. Without this, join.gov.tw's
    homepage (HTML that opens with an XML declaration) and WordPress feeds
    that list nothing because the site's news is a custom post type were
    recorded as `rss_feed:`, and the org was then never given the sitemap
    tracking that would have seen its new pages. JSON bodies pass, since
    this parser doesn't read JSON Feed."""
    head = (body or b"")[:64].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith((b"{", b"[")):
        return True
    return bool(parse_feed_entries(body))


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
            if r.status_code == 200 and looks_like_feed(r) and _lists_posts(r.content):
                return url
        except RequestException:
            pass

    # Fallback: sitemap (at least proves the site is alive)
    return probe_sitemap(root, timeout=timeout, session=session)


def _get_xml(url, timeout, session):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return ET.fromstring(r.content)
    except Exception:
        return None


def _sitemap_entries(root, tag):
    """[(loc, lastmod date or None)] for each <tag> (url or sitemap) in a
    parsed sitemap."""
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    out = []
    for el in root.findall(f"{ns}{tag}"):
        loc = (el.findtext(f"{ns}loc") or "").strip()
        lm = (el.findtext(f"{ns}lastmod") or "").strip()
        if loc:
            out.append((loc, parse_date(lm) if lm else None))
    return out


def _pick_child_sitemap(children):
    """The one child of a sitemap index most likely to hold new pages (see
    SITEMAP_SEEN_MAX's comment), or None."""
    children = [c for c in children if not _SITEMAP_ARCHIVE_CHILD.search(urlparse(c[0]).path)]
    dated = [c for c in children if c[1]]
    if dated:
        return max(dated, key=lambda c: c[1])[0]
    hinted = [c for c in children if _SITEMAP_CHILD_HINT.search(urlparse(c[0]).path)]
    return (hinted or children or [(None, None)])[0][0]


def read_sitemap(sitemap_url, timeout=10, session=None):
    """{"lastmod": newest <lastmod> date or None, "pages": [page URLs] or
    None} for a sitemap, or None if it can't be read. `pages` is None for a
    sitemap index whose chosen child can't be read, so a failed read never
    looks like every page vanishing."""
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = DOD_USER_AGENT
    root = _get_xml(sitemap_url, timeout, session)
    if root is None:
        return None
    local = re.sub(r"\{[^}]*\}", "", root.tag).lower()
    if local == "sitemapindex":
        children = _sitemap_entries(root, "sitemap")
        dates = [d for _, d in children[:5] if d]
        result = {"lastmod": max(dates) if dates else None, "pages": None}
        child = _pick_child_sitemap(children)
        child_root = _get_xml(child, timeout, session) if child else None
        if child_root is not None:
            urls = _sitemap_entries(child_root, "url")
            result["pages"] = [u for u, _ in urls]
            child_dates = [d for _, d in urls if d]
            if child_dates and (result["lastmod"] is None or max(child_dates) > result["lastmod"]):
                result["lastmod"] = max(child_dates)
        return result
    if local == "urlset":
        urls = _sitemap_entries(root, "url")
        dates = [d for _, d in urls if d]
        return {"lastmod": max(dates) if dates else None, "pages": [u for u, _ in urls]}
    return {"lastmod": None, "pages": None}


def latest_sitemap_lastmod(sitemap_url, timeout=10, session=None):
    """Return the most recent <lastmod> date from a sitemap, or None."""
    res = read_sitemap(sitemap_url, timeout=timeout, session=session)
    return res["lastmod"] if res else None


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
    # "Oct 23, 2026" / "October 23, 2026", as Eurasianet's <pubDate> has it
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
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


def _read_feed_body(r):
    """(body, truncated) for a streamed response, or (None, False) when a
    declared Content-Length is over FEED_MAX_BYTES, which skips the download
    outright. Without a declared length, reading stops at the cap and
    `truncated` says it did; the caller keeps whatever complete posts the
    part read so far holds (see _parse_partial_feed), since the newest posts
    come first in a feed."""
    declared = r.headers.get("Content-Length")
    if declared is not None:
        try:
            if int(declared) > FEED_MAX_BYTES:
                return None, False
        except ValueError:
            pass
    body = bytearray()
    for chunk in r.iter_content(chunk_size=65536):
        body.extend(chunk)
        if len(body) > FEED_MAX_BYTES:
            return bytes(body[:FEED_MAX_BYTES]), True
    return bytes(body), False


def _parse_partial_feed(content):
    """The complete posts in the opening of a feed cut off mid-document, or
    None if not even one parses. Internet Freedom Foundation's feed carries
    every post's full text and runs past FEED_MAX_BYTES, so until 2026-10-25
    it was abandoned as TOO_LARGE on every read and none of its posts
    reached the checkup."""
    parser = ET.XMLPullParser(events=("start", "end"))
    root, closed = None, set()
    try:
        parser.feed(_strip_xml_preamble(content))
        for event, el in parser.read_events():
            if event == "start" and root is None:
                root = el
            elif event == "end":
                closed.add(el)
    except ET.ParseError:
        pass  # the cut-off tail; whatever closed before it is usable
    if root is None:
        return None
    entries = _entries_from_root(root, closed)  # the post cut off mid-way is left out
    return entries or None


def fetch_feed(url, timeout=10, session=None, validators=None):
    """Read a feed once. Returns a dict with `status`:

      "ok"            — `entries` (see parse_feed_entries) and `validators`,
                        the ETag/Last-Modified the server sent, if any
      "not_modified"  — a 304: unchanged since the validators passed in
      "error"         — `error` is HTTP_<code>, NETWORK_ERROR, TOO_LARGE
                        (over FEED_MAX_BYTES) or UNPARSEABLE (not XML)

    `validators` from the previous read go out as If-None-Match /
    If-Modified-Since, so a feed that hasn't changed costs a 304 and no
    body. An empty but valid feed is "ok" with no entries, not an error.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = DOD_USER_AGENT
    headers = {}
    validators = validators or {}
    if validators.get("etag"):
        headers["If-None-Match"] = validators["etag"]
    if validators.get("last_modified"):
        headers["If-Modified-Since"] = validators["last_modified"]
    try:
        r = session.get(url, timeout=timeout, headers=headers, stream=True)
        try:
            if r.status_code == 304:
                return {"status": "not_modified"}
            if r.status_code >= 400:
                return {"status": "error", "error": f"HTTP_{r.status_code}"}
            body, truncated = _read_feed_body(r)
        finally:
            r.close()
    except RequestException:
        return {"status": "error", "error": "NETWORK_ERROR"}
    if body is None:
        return {"status": "error", "error": "TOO_LARGE"}
    if truncated:
        entries = _parse_partial_feed(body)
        if entries is None:
            return {"status": "error", "error": "TOO_LARGE"}
    else:
        entries = _parse_feed(body)
    if entries is None:
        return {"status": "error", "error": "UNPARSEABLE"}
    sent = {key: r.headers.get(header)
            for key, header in (("etag", "ETag"), ("last_modified", "Last-Modified"))
            if r.headers.get(header)}
    return {"status": "ok", "entries": entries, "validators": sent}


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

    An entry's triage labels (`signals`, `routine`, `mentions`, set by
    news_signals.annotate()) are kept when non-empty; its text never is.
    """
    keep_days = FEED_ITEMS_KEEP_DAYS if keep_days is None else keep_days
    max_items = FEED_ITEMS_MAX if max_items is None else max_items
    fresh = []
    for e in entries:
        item = {"date": e["published"].isoformat(), "title": e["title"], "url": strip_tracking(e["link"])}
        for key in ("signals", "routine", "mentions"):
            if e.get(key):
                item[key] = list(e[key])
        fresh.append(item)
    merged = {}
    for item in list(existing or []) + fresh:
        merged[_feed_item_key(item)] = item
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    kept = [i for i in merged.values() if str(i.get("date", "")) >= cutoff]
    kept.sort(key=lambda i: (str(i["date"]), i.get("title", ""), i.get("url", "")), reverse=True)
    return kept[:max_items]


# --- Per-org feed state: docs/data/feeds/<slug>.json ------------------------
#
#   feed     the feed URL last read (mirrors rss_feed:)
#   latest   newest post the feed listed on its last successful read, even
#            one old enough to be pruned from `items`; null when it listed
#            nothing. How the checkup tells a dormant feed from an empty one.
#   span_days  days between the oldest and newest post the feed listed on
#            that read, when it listed at least BUSY_MIN_POSTS. How
#            feed_due() tells a feed that turns over within a month (read
#            weekly) from the usual kind (read monthly).
#   items    recent posts, [{date, title, url}] (see merge_feed_items)
#   fetch    {etag, last_modified} from the last successful read, sent back
#            as a conditional GET
#   failing  a backoff.py failure record while reads are failing
#   probed   (org with no feed) the date discovery last ran
#   sitemap  (org with no feed) the sitemap discovery found, read monthly
#   seen     (org with no feed) the page URLs that sitemap listed on its
#            last read, as sorted short hashes (see _seen_key)
#   pages    (org with no feed) pages that first appeared in the sitemap,
#            [{date, title, url}] like `items`, `date` being the read that
#            first saw them (see record_sitemap_pages)
#
# Dates, titles and links only: no summaries or post text, the same reason
# citation-state.json holds hashes rather than page bodies. There's no
# "checked" date, so a file only changes when something in it does; when a
# feed was last read is the org's activity.rss.checked, written in the same
# pass. One file per org rather than one shared file, so a local run and the
# cron rarely touch the same file.

_STATE_KEYS = ("feed", "latest", "span_days", "items", "fetch", "failing", "probed", "sitemap",
               "seen", "pages")


def _as_date(value):
    return parse_date(str(value)) if value else None


def load_feed_state(slug, feeds_dir=None):
    path = os.path.join(feeds_dir or FEEDS_DIR, f"{slug}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_feed_state(slug, state, feeds_dir=None):
    """Write one org's state in a fixed key order; returns True if the file
    changed. An unchanged state leaves the file alone, so a quiet week makes
    no commit."""
    feeds_dir = feeds_dir or FEEDS_DIR
    path = os.path.join(feeds_dir, f"{slug}.json")
    ordered = {k: state[k] for k in _STATE_KEYS if k in state}
    text = json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(feeds_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def save_feed_items(slug, feed_url, entries, today=None, feeds_dir=None, validators=None):
    """Record a successful read: merge its posts in, note the newest, keep
    its validators for next time's conditional GET, and clear any failure
    record. Returns True if the file changed."""
    today = today or date.today()
    state = load_feed_state(slug, feeds_dir)
    latest = max((e["published"] for e in entries), default=None)
    state["feed"] = feed_url
    state["latest"] = latest.isoformat() if latest else None
    if len(entries) >= BUSY_MIN_POSTS:
        published = [e["published"] for e in entries]
        state["span_days"] = (max(published) - min(published)).days
    else:
        state.pop("span_days", None)
    state["items"] = merge_feed_items(state.get("items"), entries, today)
    if validators:
        state["fetch"] = dict(validators)
    else:
        state.pop("fetch", None)
    state.pop("failing", None)
    for key in ("probed", "sitemap", "seen", "pages"):  # discovery bookkeeping; it has a feed now
        state.pop(key, None)
    return write_feed_state(slug, state, feeds_dir)


def mark_feed_unchanged(slug, feeds_dir=None):
    """A 304: the server answered, so any failure record is over."""
    state = load_feed_state(slug, feeds_dir)
    if state.pop("failing", None) is not None:
        write_feed_state(slug, state, feeds_dir)


def record_feed_failure(slug, feed_url, error, today=None, feeds_dir=None):
    """Record a failed read (see backoff.py) and return the failure record.
    Posts saved by earlier reads are kept."""
    state = load_feed_state(slug, feeds_dir)
    state["feed"] = feed_url
    state["failing"] = backoff.record_failure(state.get("failing"), error, today)
    write_feed_state(slug, state, feeds_dir)
    return state["failing"]


def record_discovery(slug, sitemap_url, today=None, feeds_dir=None):
    """Record that discovery ran for an org with no feed, and the sitemap it
    found (or that it found none)."""
    state = load_feed_state(slug, feeds_dir)
    state["probed"] = (today or date.today()).isoformat()
    if sitemap_url:
        if state.get("sitemap") not in (None, sitemap_url):
            state.pop("seen", None)  # a different sitemap: start a new baseline
        state["sitemap"] = sitemap_url
    else:
        state.pop("sitemap", None)
        state.pop("seen", None)
    write_feed_state(slug, state, feeds_dir)


def _seen_key(url):
    """How a page URL is stored in `seen`: the first 12 hex digits of a
    SHA-256 of the URL, scheme, a leading www. and a trailing slash
    ignored, so the same page isn't new again when a site switches to
    https or drops a slash."""
    import hashlib
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    norm = host + parts.path.rstrip("/") + (f"?{parts.query}" if parts.query else "")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


def page_title_from_url(url):
    """A readable stand-in title for a page known only by its URL: the last
    path segment, extension dropped, hyphens and underscores as spaces
    ("/unlocking-better-politics-melbourne" -> "unlocking better politics
    melbourne"). The host when the path is empty."""
    from urllib.parse import unquote
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return parts.netloc
    last = re.sub(r"\.(html?|php|aspx?)$", "", unquote(segments[-1]), flags=re.IGNORECASE)
    return " ".join(re.sub(r"[-_+]+", " ", last).split()) or parts.netloc


def record_sitemap_pages(slug, sitemap_url, pages, today=None, feeds_dir=None):
    """Compare a sitemap's page list with the last read's and record the new
    ones (see SITEMAP_SEEN_MAX's comment). Returns the new pages, [] on a
    baseline read, or None when the sitemap isn't tracked (too large)."""
    today = today or date.today()
    state = load_feed_state(slug, feeds_dir)
    pages = [u for u in dict.fromkeys(pages or []) if not _SITEMAP_ARCHIVE_PATH.search(urlsplit(u).path)]
    if len(pages) > SITEMAP_SEEN_MAX:
        if state.pop("seen", None) is not None:
            write_feed_state(slug, state, feeds_dir)
        return None
    keys = {_seen_key(u): u for u in pages}
    previous = state.get("seen")
    new = []
    if isinstance(previous, list):
        known = set(previous)
        for key, url in keys.items():
            if key not in known:
                title = page_title_from_url(url)
                worth, routine = news_signals.signals(title)
                new.append({"date": today.isoformat(), "title": title, "url": url,
                            "signals": worth, "routine": routine})
    state["seen"] = sorted(keys)
    if new:
        merged = {i["url"]: i for i in state.get("pages") or []}
        for item in new:
            merged.setdefault(item["url"], item)
        cutoff = (today - timedelta(days=SITEMAP_PAGES_KEEP_DAYS)).isoformat()
        kept = sorted((i for i in merged.values() if str(i.get("date", "")) >= cutoff),
                      key=lambda i: (str(i["date"]), i["url"]), reverse=True)
        state["pages"] = kept[:SITEMAP_PAGES_MAX]
    write_feed_state(slug, state, feeds_dir)
    return new


def feed_due(state, rss_checked, today):
    """(due, why) for an org with a feed. A failing feed waits out its
    backoff. Otherwise a feed is read monthly; weekly if it turns over
    within BUSY_SPAN_DAYS, and quarterly once it's dormant or empty (see the
    constants at the top of this file)."""
    failing = state.get("failing")
    if failing:
        if backoff.backing_off(failing, today):
            return False, (f"failing ({failing.get('error')}) since {failing.get('since')}, "
                           f"next try {backoff.next_try(failing)}")
        return True, f"retrying, failing since {failing.get('since')}"
    interval = FEED_RECHECK_DAYS
    if "latest" in state:
        latest = _as_date(state["latest"])
        span = state.get("span_days")
        if latest is None or (today - latest).days > DORMANT_FEED_DAYS:
            interval = DORMANT_RECHECK_DAYS
        elif isinstance(span, int) and span < BUSY_SPAN_DAYS:
            interval = RECHECK_DAYS
    checked = _as_date(rss_checked)
    if checked and (today - checked).days < interval:
        return False, f"checked {(today - checked).days}d ago"
    return True, ""


def discovery_action(slug, state, sitemap_checked, today):
    """What to do this run for an org with no `rss_feed:`: ("probe", None) to
    run discovery, ("sitemap", url) to read just its known sitemap, or
    ("skip", why)."""
    window = FEED_REPROBE_DAYS - backoff.spread_days(slug, FEED_REPROBE_DAYS)
    probed = _as_date(state.get("probed"))
    if probed is None or (today - probed).days >= window:
        return "probe", None
    sitemap = state.get("sitemap")
    if sitemap:
        checked = _as_date(sitemap_checked)
        if checked is None or (today - checked).days >= SITEMAP_RECHECK_DAYS:
            return "sitemap", sitemap
        return "skip", f"no feed; sitemap read {(today - checked).days}d ago"
    return "skip", (f"no feed found {(today - probed).days}d ago, "
                    f"next look in {window - (today - probed).days}d")


_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"
_RSS1 = "{http://purl.org/rss/1.0/}"
_CONTENT_ENCODED = "{http://purl.org/rss/1.0/modules/content/}encoded"


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
    dicts: date, published, title, link, summary_html, body_html.

    `date` is what the activity check has always keyed on (Atom's <updated>
    before <published>). `published` is when the post first went out, where
    the feed says so separately; it's what a news checkup wants, since an
    old post edited today isn't new. `summary_html`/`body_html` are the
    feed's excerpt and full post (RSS <description>/<content:encoded>, Atom
    <summary>/<content>), empty when absent. They're only read in memory, by
    news_signals.annotate(), and never saved. Undated items are dropped.
    Returns [] for anything that doesn't parse as XML.
    """
    return _parse_feed(content) or []


def _strip_xml_preamble(content):
    """Drop a byte-order mark and whitespace before the XML declaration,
    which the parser rejects: Democracy Without Borders' WordPress feed
    opens with blank lines (a stray newline in a theme file), and was
    reported UNPARSEABLE on every read until 2026-10-25."""
    content = content or b""
    if isinstance(content, str):
        return content.lstrip("\ufeff \t\r\n")
    return content.lstrip(b" \t\r\n").removeprefix(b"\xef\xbb\xbf").lstrip(b" \t\r\n")


def _parse_feed(content):
    """parse_feed_entries(), but None rather than [] when the document isn't
    XML at all, so fetch_feed() can tell a broken feed from an empty one."""
    try:
        root = ET.fromstring(_strip_xml_preamble(content))
    except ET.ParseError:
        return None
    return _entries_from_root(root)


def _entries_from_root(root, closed=None):
    local = re.sub(r"\{[^}]*\}", "", root.tag).lower()
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    entries = []

    if local == "rss":
        for item in root.findall(".//item"):
            if closed is not None and item not in closed:
                continue
            title = (item.findtext("title") or "").strip()
            d = parse_date(item.findtext("pubDate") or item.findtext(_DC_DATE))
            link = (item.findtext("link") or "").strip()
            if not link:
                guid = (item.findtext("guid") or "").strip()
                if guid.startswith(("http://", "https://")):
                    link = guid
            if d:
                entries.append({"date": d, "published": d, "title": title, "link": link,
                                "summary_html": item.findtext("description") or "",
                                "body_html": item.findtext(_CONTENT_ENCODED) or ""})
    elif local == "rdf":
        # RSS 1.0 (RDF), as DW and Taipei Times publish it: items are
        # siblings of <channel> in the RSS 1.0 namespace, dated by dc:date.
        for item in root.findall(f"{_RSS1}item"):
            if closed is not None and item not in closed:
                continue
            d = parse_date(item.findtext(_DC_DATE))
            if d:
                entries.append({"date": d, "published": d,
                                "title": (item.findtext(f"{_RSS1}title") or "").strip(),
                                "link": (item.findtext(f"{_RSS1}link") or "").strip(),
                                "summary_html": item.findtext(f"{_RSS1}description") or "",
                                "body_html": item.findtext(_CONTENT_ENCODED) or ""})
    elif local == "feed":
        for entry in root.findall(f"{ns}entry"):
            if closed is not None and entry not in closed:
                continue
            title_el = entry.find(f"{ns}title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            published = parse_date(entry.findtext(f"{ns}published"))
            d = parse_date(entry.findtext(f"{ns}updated")) or published
            if d:
                entries.append({"date": d, "published": published or d, "title": title,
                                "link": _atom_post_link(entry, ns),
                                "summary_html": _element_text(entry.find(f"{ns}summary")),
                                "body_html": _element_text(entry.find(f"{ns}content"))})
    return entries


def _element_text(el):
    """An Atom text construct's content: escaped HTML for type="html", the
    text of its child elements for type="xhtml"."""
    return "".join(el.itertext()) if el is not None else ""


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

    today = date.today()
    # Every org's name, for tagging posts that mention another Landscape org
    # (news_signals.annotate), and which orgs share each feed, so a feed's own
    # orgs don't count as mentions of themselves.
    names = news_signals.landscape_names() if args.update_activity else []
    feed_orgs = {}
    for slug_, _forms, feed_ in names:
        if feed_:
            feed_orgs.setdefault(feed_, set()).add(slug_)
    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        prefix = f"  [{i:3d}/{len(orgs)}] {slug} … "
        if args.skip_existing and org["rss_feed"]:
            skipped.append(org)
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has rss_feed)")
            continue

        activity = org.get("activity") or {}
        state = load_feed_state(slug) if args.update_activity else {}
        feed_url = org["rss_feed"]
        sitemap_url = None

        # Is this org due? A feed is read monthly (weekly if it turns over
        # faster, quarterly once dormant) and a failing one waits out its
        # backoff; an org with no feed is probed at most every
        # FEED_REPROBE_DAYS and otherwise only has its known sitemap read.
        # See feed_due() / discovery_action().
        if args.update_activity and not args.force:
            if feed_url:
                due, why = feed_due(state, (activity.get("rss") or {}).get("checked"), today)
            else:
                action, detail = discovery_action(
                    slug, state, (activity.get("sitemap") or {}).get("checked"), today)
                due, why = action != "skip", detail
                if action == "sitemap":
                    sitemap_url = detail
            if not due:
                print(prefix + f"SKIPPED ({why})")
                skipped.append(org)
                results.append({**org, "feed_url": None, "skipped_checked": True})
                continue

        # Discovery. A feed it finds is saved as rss_feed:, so from the next
        # run on this org is read like any other feed rather than rediscovered.
        if not feed_url and not sitemap_url:
            found_url = probe_feeds(org["website"], timeout=args.timeout, session=session)
            if found_url and not is_sitemap_url(found_url):
                feed_url = found_url
                if args.update_activity:
                    write_rss_feed(org["path"], found_url)
            else:
                sitemap_url = found_url
                if args.update_activity:
                    record_discovery(slug, found_url, today)

        print(prefix, end="", flush=True)
        target = feed_url or sitemap_url
        result = {**org, "feed_url": target}

        if not target:
            if args.update_activity:
                write_checked_only(org["path"], "rss", "No feed found")
            print("not found")
            not_found.append(result)
            results.append(result)
            time.sleep(0.3)
            continue

        # An already-configured rss_feed: skips probe_feeds()'s own gating
        # above, so re-check here — the site's robots.txt may have changed
        # since the feed was recorded. A disallow is backed off like any
        # other failure, so robots.txt isn't re-asked every week either.
        if not robots_allowed(target, DOD_USER_AGENT, timeout=args.timeout, session=session):
            print(f"BLOCKED by robots.txt  {target}")
            if args.update_activity and feed_url:
                record_feed_failure(slug, feed_url, "ROBOTS_DISALLOWED", today)
            elif args.update_activity:
                record_discovery(slug, None, today)  # forget the sitemap until the next probe
            skipped.append(org)
            results.append({**org, "feed_url": None, "skipped_robots": True})
            continue

        if not args.update_activity:
            print(f"FOUND  {target}")
            found.append(result)
            results.append(result)
            time.sleep(0.3)
            continue

        if sitemap_url:
            sm = read_sitemap(sitemap_url, timeout=args.timeout, session=session)
            d = sm["lastmod"] if sm else None
            if sm and sm["pages"]:
                new_pages = record_sitemap_pages(slug, sitemap_url, sm["pages"], today)
                if new_pages:
                    print(f"NEW PAGES ({len(new_pages)})  ", end="")
            if d:
                if not update_activity_source(org["path"], d.isoformat(),
                                              "Page last modified (from sitemap)", sitemap_url,
                                              method="sitemap"):
                    write_checked_only(org["path"], "sitemap")
                print(f"SITEMAP  {d}")
                result["latest_date"] = d.isoformat()
            else:
                write_checked_only(org["path"], "sitemap", "Sitemap found, no lastmod")
                print(f"SITEMAP (no lastmod)  {sitemap_url}")
        else:
            res = fetch_feed(feed_url, timeout=args.timeout, session=session,
                             validators=state.get("fetch"))
            if res["status"] == "not_modified":
                # Nothing new since the last read, and the server didn't have
                # to send the feed again to say so.
                mark_feed_unchanged(slug)
                write_checked_only(org["path"], "rss")
                print("UNCHANGED (304)")
            elif res["status"] == "ok":
                entries = res["entries"]
                news_signals.annotate(entries, names, feed_orgs.get(feed_url, set()) | {slug})
                save_feed_items(slug, feed_url, entries, today, validators=res["validators"])
                d, title, link = latest_entry(entries)
                if d:
                    note = f"Latest post: {title[:80]}" if title else "RSS feed active"
                    if not update_activity_source(org["path"], d.isoformat(), note, feed_url, link or None):
                        write_checked_only(org["path"], "rss")
                    print(f"UPDATED  {d}  {title[:50]}")
                    result["latest_date"] = d.isoformat()
                    result["latest_title"] = title
                else:
                    # Feed responded but lists no dated posts; upgrade any placeholder
                    # note so the entry at least reads as "RSS feed active" rather than
                    # "RSS feed discovered" (the old probe-only placeholder).
                    update_activity_source(org["path"], TODAY, "RSS feed active",
                                           feed_url, method="rss")
                    print(f"FOUND (no parseable posts)  {feed_url}")
            else:
                failing = record_feed_failure(slug, feed_url, res["error"], today)
                print(f"FAILING ({res['error']}, {failing['count']} in a row; "
                      f"next try {backoff.next_try(failing)})  {feed_url}")
        found.append(result)
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
        print(f"Skipped {len(skipped)} orgs (not due yet, backing off, robots.txt, or --skip-existing)")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
