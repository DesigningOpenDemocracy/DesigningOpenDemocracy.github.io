#!/usr/bin/env python3
"""
scrape_news.py — Scrape org news/blog pages for latest activity dates.

For each org with a `news_page:` frontmatter field, fetches that URL and
extracts the most recent article date from machine-readable signals only:
  1. JSON-LD datePublished / dateModified
  2. OpenGraph article:published_time / article:modified_time
  3. <time datetime="..."> elements

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

Requirements: requests (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

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


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

class _NewsParser(HTMLParser):
    """Extract structured date signals from a fetched HTML page."""

    def __init__(self):
        super().__init__()
        self.time_datetimes = []   # values from <time datetime="...">
        self.meta_dates = []       # values from <meta property/name> date fields
        self.jsonld_blocks = []    # raw text of <script type="application/ld+json">
        self._in_jsonld = False
        self._jsonld_buf = ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "time":
            dt = d.get("datetime", "").strip()
            if dt:
                self.time_datetimes.append(dt)
        elif tag == "meta":
            prop = (d.get("property") or d.get("name") or "").lower()
            content = d.get("content", "").strip()
            if prop in {
                "article:published_time",
                "article:modified_time",
                "og:updated_time",
                "date",
                "last-modified",
                "dc.date",
                "dc.date.issued",
            } and content:
                self.meta_dates.append(content)
        elif tag == "script" and d.get("type") == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_buf = ""

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            if self._jsonld_buf.strip():
                self.jsonld_blocks.append(self._jsonld_buf)

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf += data


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
            # Recurse into @graph
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


def extract_best(parser):
    """Return (date, title) for the most recent signal, or (None, None)."""
    candidates = []

    for d, title in _dates_from_jsonld(parser.jsonld_blocks):
        candidates.append((d, title))

    for s in parser.meta_dates:
        d = parse_date(s)
        if d:
            candidates.append((d, ""))

    for s in parser.time_datetimes:
        d = parse_date(s)
        if d:
            candidates.append((d, ""))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]


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

def scrape_news_page(url, timeout=10, session=None):
    """Fetch url and return (date, title, http_ok)."""
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except RequestException:
        return None, None, False

    parser = _NewsParser()
    try:
        parser.feed(r.text)
    except Exception:
        pass  # partial parse is fine; we take what we got

    d, title = extract_best(parser)
    return d, title, True


# ---------------------------------------------------------------------------
# Frontmatter writer (mirrors check_rss.py update_activity_source)
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
            new_lines.extend(source_lines)
        yaml_block = "\n".join(new_lines)
    else:
        new_block = ["activity:"] + source_lines
        yaml_block = yaml_block.rstrip("\n") + "\n" + "\n".join(new_block) + "\n"

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
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages with news_page: found matching criteria.")
        sys.exit(0)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    updated = 0
    print(f"\nScraping {len(orgs)} org news page(s) (timeout={args.timeout}s)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        url = org["news_page"]
        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)

        if not robots_allowed(url, timeout=args.timeout, session=session):
            print(f"ROBOTS_DISALLOWED  {url}")
            time.sleep(1.0)
            continue

        d, title, ok = scrape_news_page(url, timeout=args.timeout, session=session)

        if not ok:
            print(f"UNREACHABLE  {url}")
        elif d is None:
            print(f"NO_DATE_FOUND  {url}")
        else:
            note = f"Latest post: {title[:80]}" if title else "Latest news page scraped"
            print(f"SCRAPED  {d}  {title[:50] if title else '(no title)'}")
            if not args.dry_run:
                if update_activity_source(org["path"], d.isoformat(), note, url):
                    updated += 1

        time.sleep(1.5)

    print(f"\n{'='*60}")
    if args.dry_run:
        print("Dry run — no files written")
    else:
        print(f"Updated {updated} / {len(orgs)} org page(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
