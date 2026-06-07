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
    """Fetch url and return (date, title, link, http_ok) of the most recent item.

    http_ok is True when the server returned 200 (feed is reachable), False on
    network errors or non-200 responses.  date/title/link are None when no
    parseable items were found even though the feed was reachable.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = "DOD-RSS-Reader/1.0 (democracy wiki)"
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except RequestException:
        return None, None, None, False
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None, None, None, True

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
        return None, None, None, True
    entries.sort(key=lambda x: x[0], reverse=True)
    return (*entries[0], True)


def update_activity_source(path, date_str, note, feed_url, post_url=None, method="rss"):
    """Write or update a single source entry under activity.<method> in org frontmatter.

    Only updates if the new date is strictly newer than the existing entry for
    that source — so a stale RSS scan never clobbers a fresher manual entry.
    """
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]

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
        # activity: block already exists — replace just this source's sub-block
        lines = yaml_block.split("\n")
        new_lines = []
        in_activity = False
        in_this_source = False
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
                    if in_this_source:
                        # Insert the new source block before this top-level key
                        new_lines.extend(source_lines)
                    in_activity = False
                    in_this_source = False
                    new_lines.append(line)
                    i += 1
                    continue
                # Detect this source's sub-block
                if re.match(rf"^  {method}\s*:", line):
                    in_this_source = True
                    # Skip old sub-block lines
                    i += 1
                    while i < len(lines) and lines[i].startswith("    "):
                        i += 1
                    new_lines.extend(source_lines)
                    continue
                # Detect a different source (end of this source's sub-block)
                if in_this_source and re.match(r"^  \w", line):
                    in_this_source = False
                new_lines.append(line)
                i += 1
                continue
            new_lines.append(line)
            i += 1

        # If we never found this source, append it inside the activity block
        if in_activity and method not in (meta.get("activity") or {}):
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
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
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

        # Skip orgs checked recently unless --force
        if not args.force and args.update_activity:
            activity = org.get("activity", {})
            recent_age = None
            for chk_method in ("rss", "sitemap"):
                entry = activity.get(chk_method) or {}
                chk_date = parse_date(str(entry.get("checked", "") or ""))
                if chk_date:
                    age = (datetime.today().date() - chk_date).days
                    if age <= 7:
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
        result = {**org, "feed_url": feed_url}

        if feed_url:
            if args.update_activity:
                if feed_url.endswith("sitemap.xml"):
                    d = latest_sitemap_lastmod(feed_url, timeout=args.timeout, session=session)
                    if d:
                        update_activity_source(org["path"], d.isoformat(),
                                             "Page last modified (from sitemap)", feed_url,
                                             method="sitemap")
                        print(f"SITEMAP  {d}")
                        result["latest_date"] = d.isoformat()
                    else:
                        write_checked_only(org["path"], "sitemap", "Sitemap found, no lastmod")
                        print(f"SITEMAP (no lastmod)  {feed_url}")
                else:
                    d, title, link, http_ok = latest_from_feed(feed_url, timeout=args.timeout, session=session)
                    if d:
                        note = f"Latest post: {title[:80]}" if title else "RSS feed active"
                        update_activity_source(org["path"], d.isoformat(), note, feed_url, link or None)
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
