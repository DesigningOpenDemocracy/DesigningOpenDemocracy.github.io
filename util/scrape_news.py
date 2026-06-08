#!/usr/bin/env python3
"""
scrape_news.py — Scrape org news/blog pages for latest activity dates.

For each org with a `news_page:` frontmatter field, fetches that URL and
extracts the most recent article date from machine-readable signals:
  1. JSON-LD datePublished / dateModified
  2. OpenGraph / Dublin Core / schema.org <meta> date fields
  3. Schema.org microdata via itemprop="datePublished/dateModified"
  4. <time datetime="..."> elements (or <time> with parseable text content)
  5. <a href> URL path patterns (e.g. /2026/01/15/) with anchor text as title
  6. Human-readable text date patterns ("January 15, 2026", "15 Jan 2026" etc.)

Also discovers RSS/Atom feed links in <link rel="alternate"> and can write
them to rss_feed: frontmatter with --update-rss.

Also discovers iCal/ICS calendar links (<link rel="alternate" type="text/calendar">,
webcal:// hrefs, and .ics file links) and can write them to ics_feed: frontmatter
with --update-ics.

Writes to activity.scrape in org frontmatter. Respects robots.txt.
Never writes if no machine-readable date is found.

Add `news_page: <url>` to an org page to opt it in (auto-discovery is
intentionally not done — bulk probing generates unnecessary traffic).

Usage:
    python util/scrape_news.py              # all active orgs with news_page:
    python util/scrape_news.py --all        # include inactive orgs
    python util/scrape_news.py --slug loomio
    python util/scrape_news.py --timeout 10
    python util/scrape_news.py --dry-run    # print results without writing
    python util/scrape_news.py --update-rss # write discovered RSS feeds to rss_feed:
    python util/scrape_news.py --update-ics # write discovered iCal feeds to ics_feed:
    python util/scrape_news.py --debug      # show date signals found per page

Requirements: requests (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

# Matches /YYYY/MM/DD/ path segments — used as a low-priority date fallback
_URL_DATE_YMD = re.compile(r'/(\d{4})/(\d{1,2})/(\d{1,2})(?:[/?#]|$)')
_URL_DATE_YM  = re.compile(r'/(\d{4})/(\d{1,2})(?:[/?#]|$)')

# Text date patterns for human-readable dates in article listings.
# Applied as a final fallback when no structured signals are present.
_MONTHS_PAT = (
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?'
)
_YEAR_PAT = r'(20[0-3]\d)'
_MONTH_MAP = {m[:3].lower(): i + 1 for i, m in enumerate([
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
])}
# "January 15, 2026" or "Jan 15 2026"
# (?<![a-zA-Z]) rather than \b: \b fails when the month name directly follows a
# letter with no whitespace, e.g. "ArticleFebruary 10, 2026" in concatenated text.
_TEXT_DATE_MDY = re.compile(
    rf'(?<![a-zA-Z])({_MONTHS_PAT})\s+(\d{{1,2}}),?\s+{_YEAR_PAT}(?!\d)', re.IGNORECASE
)
# "15 January 2026" or "15 Jan, 2026"
_TEXT_DATE_DMY = re.compile(
    rf'(?<!\d)(\d{{1,2}})\s+({_MONTHS_PAT}),?\s+{_YEAR_PAT}(?!\d)', re.IGNORECASE
)
# "January 2026" (month + year only, treated as 1st of month)
_TEXT_DATE_MY = re.compile(
    rf'(?<![a-zA-Z])({_MONTHS_PAT})\s+{_YEAR_PAT}(?!\d)', re.IGNORECASE
)

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

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = datetime.today().strftime("%Y-%m-%d")
USER_AGENT = "DOD-NewsScraper/1.0 (DesigningOpenDemocracy activity monitor)"

# Pages with fewer raw links than this are almost certainly JavaScript SPAs
_SPA_LINK_THRESHOLD = 5


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

class _NewsParser(HTMLParser):
    """Extract structured date signals from a fetched HTML page."""

    def __init__(self):
        super().__init__()
        self.time_datetimes = []   # values from <time datetime="...">
        self.time_text_dates = []  # text content of <time> without datetime attr
        self.meta_dates = []       # values from <meta property/name/itemprop> date fields
        self.jsonld_blocks = []    # raw text of <script type="application/ld+json">
        self.links = []            # hrefs from <a> tags (used for SPA detection / link count)
        self.link_texts = []       # (href, text) pairs — text = visible anchor label
        self.feed_urls = []        # href values from <link rel="alternate"> feed links
        self.ical_urls = []        # iCal links: <link rel=alternate type=text/calendar>, webcal://, *.ics
        self._in_jsonld = False
        self._jsonld_buf = ""
        self._in_link = False
        self._link_href = ""
        self._link_buf = ""
        self._in_time_text = False
        self._time_text_buf = ""
        self._in_inert = False     # True inside <script>/<style> (non-JSON-LD)
        self._text_buf = ""        # visible text content for pattern matching

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a":
            href = d.get("href", "").strip()
            if href:
                self.links.append(href)
                href_lower = href.lower()
                if href_lower.startswith("webcal://") or href_lower.split("?")[0].endswith(".ics"):
                    self.ical_urls.append(href)
            self._in_link = bool(href)
            self._link_href = href
            self._link_buf = ""
        elif tag == "link":
            rel = (d.get("rel") or "").lower().split()
            type_ = (d.get("type") or "").lower()
            href = (d.get("href") or "").strip()
            if "alternate" in rel and href:
                if type_ in ("application/rss+xml", "application/atom+xml"):
                    self.feed_urls.append(href)
                elif type_ in ("text/calendar", "text/x-vcalendar"):
                    self.ical_urls.append(href)
        elif tag == "time":
            dt = d.get("datetime", "").strip()
            if dt:
                self.time_datetimes.append(dt)
                self._in_time_text = False
            else:
                self._in_time_text = True
                self._time_text_buf = ""
        elif tag == "meta":
            prop = (d.get("property") or d.get("name") or d.get("itemprop") or "").lower()
            content = d.get("content", "").strip()
            if prop in {
                "article:published_time",
                "article:modified_time",
                "og:updated_time",
                "date",
                "last-modified",
                "dc.date",
                "dc.date.issued",
                "datepublished",    # itemprop="datePublished" on <meta>
                "datemodified",     # itemprop="dateModified" on <meta>
                "datecreated",      # itemprop="dateCreated" on <meta>
            } and content:
                self.meta_dates.append(content)
        elif tag == "script":
            if d.get("type") == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buf = ""
            else:
                self._in_inert = True
        elif tag == "style":
            self._in_inert = True

    def handle_endtag(self, tag):
        if tag == "script":
            if self._in_jsonld:
                self._in_jsonld = False
                if self._jsonld_buf.strip():
                    self.jsonld_blocks.append(self._jsonld_buf)
            elif self._in_inert:
                self._in_inert = False
        elif tag == "style" and self._in_inert:
            self._in_inert = False
        elif tag == "a" and self._in_link:
            text = self._link_buf.strip()
            if self._link_href:
                self.link_texts.append((self._link_href, text))
            self._in_link = False
        elif tag == "time" and self._in_time_text:
            self._in_time_text = False
            t = self._time_text_buf.strip()
            if t:
                self.time_text_dates.append(t)

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf += data
            return
        if self._in_inert:
            return
        if self._in_link:
            self._link_buf += data
        if self._in_time_text:
            self._time_text_buf += data
        self._text_buf += data


def _dates_from_jsonld(blocks):
    """Yield (date, title_or_empty) from a list of raw JSON-LD strings."""
    for block in blocks:
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if graph:
                yield from _dates_from_jsonld([json.dumps(graph)])
            date_val = item.get("datePublished") or item.get("dateModified")
            if not date_val:
                continue
            d = parse_date(str(date_val))
            if d:
                title = str(item.get("headline") or item.get("name") or "").strip()
                yield d, title


def _dates_from_links(link_texts):
    """Yield (date, title) from URL path patterns like /2026/01/15/ in anchor hrefs.

    Low-priority fallback for sites that don't use structured date markup
    but embed dates in article URLs (common in WordPress/CMS).  Anchor text
    is returned as the title when non-empty.
    """
    today = date.today()
    seen = set()
    for href, text in link_texts:
        m = _URL_DATE_YMD.search(href)
        if m:
            try:
                y, mo, day_n = int(m.group(1)), int(m.group(2)), int(m.group(3))
                dt = date(y, mo, day_n)
                if 2000 <= y and dt <= today and dt not in seen:
                    seen.add(dt)
                    yield dt, text[:80]
                continue
            except ValueError:
                pass
        m = _URL_DATE_YM.search(href)
        if m:
            try:
                y, mo = int(m.group(1)), int(m.group(2))
                dt = date(y, mo, 1)
                if 2000 <= y and dt <= today and dt not in seen:
                    seen.add(dt)
                    yield dt, text[:80]
            except ValueError:
                pass


def _dates_from_text(text):
    """Yield (date, '') from human-readable date strings in page text.

    Matches English date formats: "15 January 2026", "January 15, 2026",
    "Jan 2026".  Lowest-confidence fallback for sites with no structured
    markup.  Always filtered to past dates.
    """
    if not text:
        return
    today = date.today()
    seen = set()

    def _emit(year_s, month_s, day_n):
        mo = _MONTH_MAP.get(month_s.lower()[:3])
        if not mo:
            return
        try:
            dt = date(int(year_s), mo, day_n)
            if 2000 <= dt.year and dt <= today and dt not in seen:
                seen.add(dt)
                return dt
        except ValueError:
            pass

    for m in _TEXT_DATE_MDY.finditer(text):
        mo_s, day_s, year_s = m.group(1), m.group(2), m.group(3)
        dt = _emit(year_s, mo_s, int(day_s))
        if dt:
            yield dt, ""

    for m in _TEXT_DATE_DMY.finditer(text):
        day_s, mo_s, year_s = m.group(1), m.group(2), m.group(3)
        dt = _emit(year_s, mo_s, int(day_s))
        if dt:
            yield dt, ""

    for m in _TEXT_DATE_MY.finditer(text):
        mo_s, year_s = m.group(1), m.group(2)
        dt = _emit(year_s, mo_s, 1)
        if dt:
            yield dt, ""


def extract_best(parser):
    """Return (date, title) for the most recent signal, or (None, None).

    Priority (highest to lowest):
      JSON-LD → <meta>/microdata → <time datetime> → <time> text
      → URL path patterns → human-readable text patterns
    Future dates are excluded so upcoming-event pages don't inflate activity.
    """
    today = date.today()
    candidates = []

    for d, title in _dates_from_jsonld(parser.jsonld_blocks):
        if d <= today:
            candidates.append((d, title))

    for s in parser.meta_dates:
        d = parse_date(s)
        if d and d <= today:
            candidates.append((d, ""))

    for s in parser.time_datetimes:
        d = parse_date(s)
        if d and d <= today:
            candidates.append((d, ""))

    for s in parser.time_text_dates:
        d = parse_date(s)
        if d and d <= today:
            candidates.append((d, ""))

    for d, title in _dates_from_links(parser.link_texts):
        candidates.append((d, title))

    for d, title in _dates_from_text(parser._text_buf):
        candidates.append((d, title))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]


def _print_debug(parser):
    """Print a summary of what date signals the parser found on the page."""
    url_dates = sorted(
        {d.isoformat() for d, _ in _dates_from_links(parser.link_texts)},
        reverse=True,
    )[:8]
    text_dates = sorted(
        {d.isoformat() for d, _ in _dates_from_text(parser._text_buf)},
        reverse=True,
    )[:5]
    print(f"    ┌─ signals found ───────────────────────────────")
    print(f"    │ <time datetime>  : {parser.time_datetimes[:8] or '(none)'}")
    print(f"    │ <time> text      : {parser.time_text_dates[:5] or '(none)'}")
    print(f"    │ <meta> dates     : {parser.meta_dates[:5] or '(none)'}")
    print(f"    │ JSON-LD blocks   : {len(parser.jsonld_blocks)}")
    print(f"    │ URL date patterns: {url_dates or '(none)'}")
    print(f"    │ text date matches: {text_dates or '(none)'}")
    print(f"    │ feed links found : {parser.feed_urls[:3] or '(none)'}")
    print(f"    │ ical links found : {parser.ical_urls[:3] or '(none)'}")
    print(f"    │ total <a> links  : {len(parser.links)}")
    print(f"    └───────────────────────────────────────────────")


# ---------------------------------------------------------------------------
# Date parsing (mirrors check_rss.py)
# ---------------------------------------------------------------------------

def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        return parsedate_to_datetime(s).date()
    except Exception:
        pass
    try:
        clean = re.sub(r"\.\d+", "", s)
        return datetime.fromisoformat(clean).date()
    except Exception:
        pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# Robots.txt check
# ---------------------------------------------------------------------------

def robots_allowed(url, timeout=5, session=None):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, timeout=timeout)
        rp.parse(resp.text.splitlines())
    except Exception:
        return True  # unreachable robots.txt → assume allowed
    return rp.can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def _classify_hint(ok, http_status, parser):
    """Return a short hint string classifying a scraping failure.

    spa         — raw HTML is nearly empty (JS SPA); headless browser needed
    no_markup   — page loaded with content but has no machine-readable date
                  signals; consider requesting an RSS feed from the org
    bot_blocked — server returned 403/429; consider reaching out for a feed
    unreachable — network error or unexpected HTTP error
    """
    if not ok:
        if http_status in (403, 429):
            return "bot_blocked"
        return "unreachable"
    if len(parser.links) < _SPA_LINK_THRESHOLD:
        return "spa"
    return "no_markup"


def scrape_news_page(url, timeout=10, session=None):
    """Fetch url and return (date, title, http_ok, parser, http_status).

    parser is always returned so callers can inspect signals for --debug output
    or to write custom extraction logic.  http_status is the integer response
    code on HTTP errors, None on network/timeout failures.
    """
    empty = _NewsParser()
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        return None, None, False, empty, status
    except RequestException:
        return None, None, False, empty, None

    parser = _NewsParser()
    try:
        parser.feed(r.text)
    except Exception:
        pass  # partial parse is fine; we take what we got

    d, title = extract_best(parser)
    return d, title, True, parser, r.status_code


# ---------------------------------------------------------------------------
# Frontmatter writers
# ---------------------------------------------------------------------------

def update_activity_source(path, date_str, note, url, method="scrape"):
    """Write activity.<method>; skip if existing entry is the same age or newer."""
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]

    meta = _yaml.safe_load(yaml_block) or {}
    existing = (meta.get("activity") or {}).get(method) or {}
    existing_date = parse_date(str(existing.get("date", "") or ""))
    new_date = parse_date(date_str)
    if existing_date and new_date and new_date <= existing_date:
        return False

    source_lines = [
        f"  {method}:",
        f"    date: {date_str}",
        f"    note: {json.dumps(note, ensure_ascii=False)}",
        f"    url: {url}",
        f"    checked: {TODAY}",
    ]

    if meta.get("activity"):
        lines = yaml_block.split("\n")
        new_lines = []
        in_activity = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^activity\s*:", line):
                in_activity = True
                new_lines.append(line)
                i += 1
                continue
            if in_activity:
                if line and not line.startswith(" "):
                    if method not in (meta.get("activity") or {}):
                        new_lines.extend(source_lines)
                    in_activity = False
                    new_lines.append(line)
                    i += 1
                    continue
                if re.match(rf"^  {method}\s*:", line):
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
        if in_activity and method not in (meta.get("activity") or {}):
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            new_lines.extend(source_lines)
        yaml_block = "\n".join(new_lines)
        if not yaml_block.endswith("\n"):
            yaml_block += "\n"
    else:
        new_block = ["activity:"] + source_lines
        yaml_block = yaml_block.rstrip("\n") + "\n" + "\n".join(new_block) + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def write_checked_only(path, method, note=None, hint=None):
    """Add/update checked: (and optionally hint:) on an activity source entry.

    hint  — short classification string written to activity.<method>.hint so
            future runs and humans know why scraping failed (spa, no_markup,
            bot_blocked, unreachable).  Pass None to leave any existing hint
            unchanged.
    """
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
    meta = _yaml.safe_load(yaml_block) or {}
    activity = meta.get("activity") or {}

    minimal = [f"  {method}:"]
    if note:
        minimal.append(f"    note: {json.dumps(note, ensure_ascii=False)}")
    if hint:
        minimal.append(f"    hint: {hint}")
    minimal.append(f"    checked: {TODAY}")

    if not activity:
        yaml_block = yaml_block.rstrip("\n") + "\nactivity:\n" + "\n".join(minimal) + "\n"
    elif method not in activity:
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
        lines = yaml_block.split("\n")
        new_lines = []
        in_this_source = False
        checked_written = False
        hint_written = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(rf"^  {method}\s*:", line):
                in_this_source = True
                new_lines.append(line)
                i += 1
                continue
            if in_this_source:
                if re.match(r"^  \w", line) or (line and not line.startswith("    ")):
                    if hint and not hint_written:
                        new_lines.append(f"    hint: {hint}")
                        hint_written = True
                    if not checked_written:
                        new_lines.append(f"    checked: {TODAY}")
                        checked_written = True
                    in_this_source = False
                elif re.match(r"^    hint\s*:", line):
                    if hint:
                        new_lines.append(f"    hint: {hint}")
                        hint_written = True
                    else:
                        new_lines.append(line)  # keep existing hint unchanged
                    i += 1
                    continue
                elif re.match(r"^    checked\s*:", line):
                    if hint and not hint_written:
                        new_lines.append(f"    hint: {hint}")
                        hint_written = True
                    new_lines.append(f"    checked: {TODAY}")
                    checked_written = True
                    i += 1
                    continue
            new_lines.append(line)
            i += 1
        if in_this_source:
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            if hint and not hint_written:
                new_lines.append(f"    hint: {hint}")
            if not checked_written:
                new_lines.append(f"    checked: {TODAY}")
        yaml_block = "\n".join(new_lines)

    if not yaml_block.endswith("\n"):
        yaml_block += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def write_rss_feed(path, feed_url):
    """Write rss_feed: to org frontmatter if not already present.

    Inserts after the website: line when present, otherwise before news_page:.
    Returns False (no write) if rss_feed: already exists in the file.
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
    if re.search(r'^rss_feed\s*:', yaml_block, re.MULTILINE):
        return False
    for pattern in (r'^(website\s*:.*\n)', r'^(news_page\s*:.*\n)'):
        m = re.search(pattern, yaml_block, re.MULTILINE)
        if m:
            yaml_block = yaml_block[:m.end()] + f"rss_feed: {feed_url}\n" + yaml_block[m.end():]
            break
    else:
        yaml_block = yaml_block.rstrip("\n") + f"\nrss_feed: {feed_url}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def write_ics_feed(path, feed_url):
    """Write ics_feed: to org frontmatter if not already present.

    webcal:// URIs are normalised to https:// so the URL is directly fetchable
    by check_rss.py.  Inserts after rss_feed: when present, otherwise after
    website:, otherwise at end of frontmatter.
    Returns False (no write) if ics_feed: already exists in the file.
    """
    # Normalise webcal:// → https:// so check_rss.py can fetch it directly
    if feed_url.lower().startswith("webcal://"):
        feed_url = "https://" + feed_url[9:]

    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
    if re.search(r'^ics_feed\s*:', yaml_block, re.MULTILINE):
        return False
    for pattern in (r'^(rss_feed\s*:.*\n)', r'^(website\s*:.*\n)'):
        m = re.search(pattern, yaml_block, re.MULTILINE)
        if m:
            yaml_block = yaml_block[:m.end()] + f"ics_feed: {feed_url}\n" + yaml_block[m.end():]
            break
    else:
        yaml_block = yaml_block.rstrip("\n") + f"\nics_feed: {feed_url}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


# ---------------------------------------------------------------------------
# Org loader
# ---------------------------------------------------------------------------

def load_orgs(slug_filter=None, include_inactive=False):
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata
        news_page = (meta.get("news_page") or "").strip()
        if not news_page:
            continue
        slug = os.path.basename(path)[:-3]
        if slug_filter and slug != slug_filter:
            continue
        website = meta.get("website", "") or ""
        if WAYBACK_PREFIX in website:
            continue
        status = meta.get("status", "")
        if not include_inactive and status != "active":
            continue
        orgs.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "status": status,
            "news_page": news_page,
            "path": path,
            "activity": meta.get("activity") or {},
            "rss_feed": (meta.get("rss_feed") or "").strip(),
            "ics_feed": (meta.get("ics_feed") or "").strip(),
        })
    return orgs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape org news pages for latest activity dates")
    parser.add_argument("--all", action="store_true", help="Include inactive orgs (default: active only)")
    parser.add_argument("--slug", metavar="SLUG", help="Scrape a single org by slug")
    parser.add_argument("--timeout", type=int, default=10, metavar="N", help="Per-request timeout in seconds (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing frontmatter")
    parser.add_argument("--force", action="store_true",
                        help="Scrape all orgs even if recently checked (ignores activity.scrape.checked)")
    parser.add_argument("--debug", action="store_true",
                        help="Print what date signals were found on each page (useful for writing custom extractors)")
    parser.add_argument("--update-rss", action="store_true",
                        help="Write discovered RSS/Atom feed URLs to rss_feed: frontmatter for orgs that lack one")
    parser.add_argument("--update-ics", action="store_true",
                        help="Write discovered iCal feed URLs to ics_feed: frontmatter for orgs that lack one")
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages with news_page: found matching criteria.")
        sys.exit(0)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    updated = 0
    feeds_written = 0
    ics_written = 0
    print(f"\nScraping {len(orgs)} org news page(s) (timeout={args.timeout}s)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        url = org["news_page"]
        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)

        # Skip unless --force
        if not args.force:
            entry = (org.get("activity") or {}).get("scrape") or {}
            # Permanent-failure hints: skip until --force (no point retrying)
            existing_hint = entry.get("hint", "")
            if existing_hint in ("spa", "bot_blocked"):
                print(f"SKIP [{existing_hint}]")
                continue
            # Recency skip: checked within the last 7 days
            chk_date = parse_date(str(entry.get("checked", "") or ""))
            if chk_date:
                age = (datetime.strptime(TODAY, "%Y-%m-%d").date() - chk_date).days
                if age <= 7:
                    print(f"SKIPPED (checked {age}d ago)")
                    continue

        if not robots_allowed(url, timeout=args.timeout, session=session):
            print(f"ROBOTS_DISALLOWED  {url}")
            time.sleep(1.0)
            continue

        d, title, ok, page_parser, http_status = scrape_news_page(url, timeout=args.timeout, session=session)

        # Report / write discovered RSS feeds
        if page_parser.feed_urls:
            resolved_feeds = [urljoin(url, f) for f in page_parser.feed_urls[:2]]
            if args.update_rss and not args.dry_run and not org["rss_feed"]:
                if write_rss_feed(org["path"], resolved_feeds[0]):
                    feeds_written += 1

        # Report / write discovered iCal feeds
        if page_parser.ical_urls:
            resolved_icals = [urljoin(url, f) for f in page_parser.ical_urls[:2]]
            if args.update_ics and not args.dry_run and not org["ics_feed"]:
                if write_ics_feed(org["path"], resolved_icals[0]):
                    ics_written += 1

        if not ok:
            hint = _classify_hint(ok, http_status, page_parser)
            print(f"UNREACHABLE [{hint}]")
            if not args.dry_run:
                write_checked_only(org["path"], "scrape",
                                   "News page unreachable", hint=hint)
        elif d is None:
            hint = _classify_hint(ok, http_status, page_parser)
            print(f"NO_DATE_FOUND [{hint}]")
            if not args.dry_run:
                write_checked_only(org["path"], "scrape",
                                   "News page found, no machine-readable date", hint=hint)
        else:
            note = f"Latest post: {title[:80]}" if title else "Latest news page scraped"
            print(f"SCRAPED  {d}  {title[:50] if title else '(no title)'}")
            if not args.dry_run:
                if update_activity_source(org["path"], d.isoformat(), note, url):
                    updated += 1

        if page_parser.feed_urls:
            resolved_feeds = [urljoin(url, f) for f in page_parser.feed_urls[:2]]
            for f in resolved_feeds:
                print(f"    → feed:  {f}")

        if page_parser.ical_urls:
            resolved_icals = [urljoin(url, f) for f in page_parser.ical_urls[:2]]
            for f in resolved_icals:
                print(f"    → ical:  {f}")

        if args.debug:
            _print_debug(page_parser)

        time.sleep(1.5)

    print(f"\n{'='*60}")
    if args.dry_run:
        print("Dry run — no files written")
    else:
        print(f"Updated {updated} / {len(orgs)} org page(s)")
        if feeds_written:
            print(f"Wrote rss_feed: for {feeds_written} org(s) — run check_rss.py --update-activity to populate activity.rss")
        if ics_written:
            print(f"Wrote ics_feed: for {ics_written} org(s) — run check_rss.py --update-activity to populate activity.ical")

    return 0


if __name__ == "__main__":
    sys.exit(main())
