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

Requirements: requests (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import sys
import time
from urllib.parse import urljoin, urlparse

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
            "has_rss": bool(meta.get("rss_feed")),
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
        if args.skip_existing and org["has_rss"]:
            skipped.append(org)
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has rss_feed)")
            continue

        print(f"  [{i:3d}/{len(orgs)}] {slug} ({org['website']}) … ", end="", flush=True)
        feed_url = probe_feeds(org["website"], timeout=args.timeout, session=session)

        result = {**org, "feed_url": feed_url}
        results.append(result)

        if feed_url:
            print(f"FOUND  {feed_url}")
            found.append(result)
        else:
            print("not found")
            not_found.append(result)

        # Polite crawling: 0.3s between sites
        time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"Found feeds for {len(found)} / {len(orgs) - len(skipped)} orgs checked")
    if skipped:
        print(f"Skipped {len(skipped)} orgs (already have rss_feed:)")
    print()

    if found:
        print("=== Orgs with feeds ===")
        for r in found:
            print(f"  {r['slug']}")
            print(f"    feed:    {r['feed_url']}")
            print(f"    website: {r['website']}")
            print()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results written to {args.output}")

    return 0 if found else 0


if __name__ == "__main__":
    sys.exit(main())
