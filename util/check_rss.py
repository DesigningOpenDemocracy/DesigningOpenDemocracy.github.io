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
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

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
    "/sitemap.xml",   # fallback: at least shows site is alive
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


def probe_feeds(base_url, timeout=8, session=None):
    """Return the first feed URL found, or None."""
    if session is None:
        session = requests.Session()
    session.headers.update({"User-Agent": "DOD-RSS-Probe/1.0 (democracy wiki feed discovery)"})

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    for path in FEED_PATHS:
        url = urljoin(root, path)
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and looks_like_feed(r):
                return url
        except RequestException:
            pass

    return None


def latest_sitemap_lastmod(sitemap_url, timeout=10, session=None):
    """Return the most recent <lastmod> date from a sitemap, or None."""
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "DOD-RSS-Reader/1.0 (democracy wiki)"
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
    """Parse RSS (RFC 2822) or Atom (ISO 8601) date strings robustly."""
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
    return None


def latest_from_feed(url, timeout=10, session=None):
    """Fetch url and return (date, title, link) of the most recent item, or (None, None, None)."""
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "DOD-RSS-Reader/1.0 (democracy wiki)"
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except RequestException:
        return None, None, None
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None, None, None

    local = re.sub(r"\{[^}]*\}", "", root.tag).lower()
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    entries = []

    if local == "rss":
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            pubdate = (item.findtext("pubDate")
                       or item.findtext("{http://purl.org/dc/elements/1.1/}date"))
            link = item.findtext("link") or ""
            d = parse_date(pubdate)
            if d:
                entries.append((d, title, link))
    elif local == "feed":
        for entry in root.findall(f"{ns}entry"):
            title_el = entry.find(f"{ns}title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            updated = (entry.findtext(f"{ns}updated")
                       or entry.findtext(f"{ns}published"))
            link_el = entry.find(f"{ns}link")
            link = link_el.get("href", "") if link_el is not None else ""
            if not link:
                link = entry.findtext(f"{ns}id") or ""
            d = parse_date(updated)
            if d:
                entries.append((d, title, link))

    if not entries:
        return None, None, None
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries[0]


def update_last_activity(path, date_str, note, feed_url, post_url=None, method="rss"):
    """Replace or append last_activity block in org frontmatter.

    Skips the update if an existing last_activity date is already newer or
    equal — so a manual or dod entry is never downgraded by an older RSS date.
    """
    with open(path) as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]

    # Guard: don't overwrite a newer (or equal) existing date
    import yaml as _yaml
    existing = (_yaml.safe_load(yaml_block) or {}).get("last_activity") or {}
    existing_date = parse_date(str(existing.get("date", "") or ""))
    new_date = parse_date(date_str)
    if existing_date and new_date and new_date <= existing_date:
        return False  # existing entry is same age or newer — leave it alone

    # Remove existing last_activity block if present
    lines = yaml_block.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if re.match(r"^last_activity\s*:", line):
            skip = True
            continue
        if skip:
            if line.startswith("  "):
                continue
            skip = False
        new_lines.append(line)
    yaml_block = "\n".join(new_lines)

    url_field = post_url or feed_url
    new_block = [
        "last_activity:",
        f"  date: {date_str}",
        f"  note: {json.dumps(note, ensure_ascii=False)}",
        f"  url: {url_field}",
        f"  method: {method}",
    ]
    yaml_block = yaml_block.rstrip("\n") + "\n" + "\n".join(new_block) + "\n"
    with open(path, "w") as f:
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
            "path": path,
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
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages found matching criteria.")
        sys.exit(0)

    session = requests.Session()
    session.headers.update({"User-Agent": "DOD-RSS-Probe/1.0 (democracy wiki feed discovery)"})

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

        # Use existing rss_feed if present, otherwise probe
        feed_url = org["rss_feed"] or probe_feeds(org["website"], timeout=args.timeout, session=session)

        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)
        result = {**org, "feed_url": feed_url}

        if feed_url:
            if args.update_activity:
                if feed_url.endswith("sitemap.xml"):
                    d = latest_sitemap_lastmod(feed_url, timeout=args.timeout, session=session)
                    if d:
                        update_last_activity(org["path"], d.isoformat(),
                                             "Page last modified (from sitemap)", feed_url,
                                             method="sitemap")
                        print(f"SITEMAP  {d}")
                        result["latest_date"] = d.isoformat()
                    else:
                        print(f"SITEMAP (no lastmod)  {feed_url}")
                else:
                    d, title, link = latest_from_feed(feed_url, timeout=args.timeout, session=session)
                    if d:
                        note = f"Latest post: {title[:80]}" if title else "RSS feed active"
                        update_last_activity(org["path"], d.isoformat(), note, feed_url, link or None)
                        print(f"UPDATED  {d}  {title[:50]}")
                        result["latest_date"] = d.isoformat()
                        result["latest_title"] = title
                    else:
                        print(f"FOUND (no parseable posts)  {feed_url}")
            else:
                print(f"FOUND  {feed_url}")
            found.append(result)
        else:
            print("not found")
            not_found.append(result)

        results.append(result)
        time.sleep(0.3)

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
