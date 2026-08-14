#!/usr/bin/env python3
"""
check_event_urls.py — liveness check for event citation URLs.

The event-sourcing system (check_event_sourcing.py) verifies that every
event carries a url: or source:, and check_fragments.py verifies that a
Wikipedia #:~:text= fragment still matches live article text. Neither one
catches the far more common failure mode: a cited URL quietly starts
404ing, redirects to an unrelated page, or the host disappears. Nothing
else in this repo checks that.

This is a network script (like check_rss.py / scrape_news.py), so it is
NOT part of the offline `make build` / CI pipeline — run it periodically
as a maintenance step (see HEARTBEAT.md) rather than on every commit.

Usage:
    python util/check_event_urls.py                  # check all event URLs
    python util/check_event_urls.py --slug mosaiclab  # single org
    python util/check_event_urls.py --timeout 8       # per-request timeout
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import date
from urllib.parse import urlparse

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

ORGS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
SKIP_FILES = {"organisations.md", "concepts.md"}
DOD_USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
REQUEST_DELAY = 0.5  # be polite between requests to the same run, different hosts


def strip_fragment(url):
    """Drop a #:~:text= fragment before requesting — servers don't see it
    anyway (it's a browser-side text-fragment directive), and leaving it on
    doesn't change the request but is confusing in output."""
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def check_url(url, session, timeout):
    """Return (status, final_url_or_None, error_or_None)."""
    target = strip_fragment(url)
    try:
        r = session.head(target, timeout=timeout, allow_redirects=True)
        # Some servers don't implement HEAD properly (405/501) or lie about
        # it — fall back to GET, same pattern used elsewhere in this repo
        # (see probe_feeds in check_rss.py).
        if r.status_code in (405, 501) or r.status_code >= 400:
            r = session.get(target, timeout=timeout, allow_redirects=True, stream=True)
            r.close()
        return r.status_code, r.url, None
    except requests.RequestException as e:
        return None, None, str(e)


def main():
    parser = argparse.ArgumentParser(description="Check liveness of event citation URLs")
    parser.add_argument("--slug", type=str, help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=10, help="Per-request timeout in seconds")
    parser.add_argument("--report", type=str, default=None,
                        help="Write a JSON summary of findings to this path "
                             "(dead/blocked/redirected/errored, with counts) "
                             "for ad hoc/manual review. Purely additive: never "
                             "changes stdout or the exit code.")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})

    checked = 0
    dead = []
    blocked = []
    redirected = []
    errored = []
    seen_urls = {}  # url -> result, so a citation reused across orgs is only fetched once

    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        filename = os.path.basename(path)
        if filename in SKIP_FILES:
            continue
        slug = filename[:-3]
        if args.slug and slug != args.slug:
            continue

        post = frontmatter.load(path)
        title = post.metadata.get("title", slug)
        for e in post.metadata.get("events") or []:
            url = e.get("url")
            if not url:
                continue
            url = str(url).strip()

            if url not in seen_urls:
                time.sleep(REQUEST_DELAY)
                status, final_url, error = check_url(url, session, args.timeout)
                seen_urls[url] = (status, final_url, error)
                checked += 1
            status, final_url, error = seen_urls[url]

            event_date = e.get("date", "?")
            event_title = e.get("title", "?")

            if error:
                errored.append((title, event_date, event_title, url, error))
                print(f"  ERROR    {title}  [{event_date}]  {event_title}")
                print(f"           {url}")
                print(f"           {error}")
            elif status in (403, 429):
                # Near-certainly bot/scraper blocking (Cloudflare etc.), not a
                # dead resource — several sites in this landscape are known to
                # 403 automated requests while being perfectly live in a real
                # browser (sortitionfoundation.org, humanitix.com,
                # unimelb.edu.au among them, confirmed during manual research).
                # Reported separately from DEAD so nobody "fixes" a citation
                # that was never actually broken.
                blocked.append((title, event_date, event_title, url, status))
                print(f"  BLOCKED ({status})  {title}  [{event_date}]  {event_title}")
                print(f"           {url}  (likely bot-blocking — verify manually in a browser before touching)")
            elif status is None or status >= 400:
                dead.append((title, event_date, event_title, url, status))
                print(f"  DEAD ({status})  {title}  [{event_date}]  {event_title}")
                print(f"           {url}")
            elif final_url and strip_fragment(url).rstrip("/") != final_url.rstrip("/"):
                redirected.append((title, event_date, event_title, url, final_url))
                print(f"  REDIRECT {title}  [{event_date}]  {event_title}")
                print(f"           {url}  ->  {final_url}")

    print()
    print(f"Unique URLs checked: {checked}")
    print(f"Dead: {len(dead)}  Blocked (403/429, likely not actually dead): {len(blocked)}  "
          f"Redirected: {len(redirected)}  Errored: {len(errored)}")

    if args.report:
        def _rows(items, extra_key):
            return [
                {"org": t, "date": d, "event": et, "url": u, extra_key: x}
                for (t, d, et, u, x) in items
            ]
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "generated": date.today().isoformat(),
                "counts": {"checked": checked, "dead": len(dead), "blocked": len(blocked),
                           "redirected": len(redirected), "errored": len(errored)},
                "dead": _rows(dead, "status"),
                "blocked": _rows(blocked, "status"),
                "redirected": _rows(redirected, "final_url"),
                "errored": _rows(errored, "error"),
            }, f, indent=2)
            f.write("\n")

    if dead or errored:
        print("\nDead/errored URLs need a replacement citation, an updated url_checked "
              "if the content moved, or (if the source is genuinely gone) removal of the "
              "event unless a Wayback Machine snapshot can stand in as the url:.")
        sys.exit(1)
    if blocked:
        print("\nAll remaining issues are BLOCKED (403/429) — spot-check a few manually "
              "in a real browser before assuming anything is actually broken.")
    print("No confirmed-dead event citation URLs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
