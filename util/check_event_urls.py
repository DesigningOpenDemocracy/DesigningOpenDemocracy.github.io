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

A URL that comes back 403/429 (bot protection, not a transient failure)
has that recorded against it and is skipped entirely on every subsequent
run — no request at all, HEAD or GET — until --no-cache forces a recheck
or the site starts answering normally again. This shares the same cache
file and "blocked"/"blocked_since" fields check_fragments.py uses for the
same reason: retrying a server that's already told us no, every week,
forever, produces no new information and is just unwanted traffic to a
site that's explicitly signalled it doesn't want scripted requests.

Usage:
    python util/check_event_urls.py                  # check all event URLs
    python util/check_event_urls.py --slug mosaiclab  # single org
    python util/check_event_urls.py --timeout 8       # per-request timeout
    python util/check_event_urls.py --no-cache        # recheck URLs already confirmed BLOCKED
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import date
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

import check_fragments as cf  # noqa: E402 — shared "blocked" URL cache
from robots_check import robots_allowed  # noqa: E402

ORGS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
SKIP_FILES = {"index.md"}
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
        # (see probe_feeds in check_rss.py). Deliberately NOT done for
        # 403/429: those are bot protection giving a real answer to HEAD,
        # not "method not supported" — a GET immediately after would almost
        # certainly hit the exact same block, doubling the request for no
        # new information. Other 4xx/5xx (404, 500, ...) still get the GET
        # double-check, since those aren't a bot-protection signal and a
        # server occasionally answers HEAD and GET differently for them.
        if r.status_code in (405, 501) or (r.status_code >= 400 and r.status_code not in (403, 429)):
            r = session.get(target, timeout=timeout, allow_redirects=True, stream=True)
            r.close()
        return r.status_code, r.url, None
    except requests.RequestException as e:
        return None, None, str(e)


ROBOTS_STATUS = "ROBOTS_DISALLOWED"  # sentinel status value, not a real HTTP code


def check_url_cached(url, session, timeout, cache, use_cache=True):
    """Wraps check_url() with the same shared "blocked" cache
    check_fragments.py writes to (docs/data/citation-state.json,
    keyed the same way — cache[url]["blocked"] is either the "HTTP_403"/
    "HTTP_429" string format that script already uses, or "ROBOTS_DISALLOWED"
    when the site's own robots.txt says no — so a write by either script
    is visible to the other, and either kind of block is skipped entirely
    here — no request at all — until use_cache=False forces a recheck.
    Returns (status, final_url, error, skipped), where status is an int
    HTTP code, None on a network error, or the ROBOTS_STATUS sentinel;
    skipped=True means this was answered from cache without any network
    call this run."""
    entry = cache.get(url, {}) if use_cache else {}
    blocked = entry.get("blocked")
    if blocked == ROBOTS_STATUS:
        return ROBOTS_STATUS, None, None, True
    if blocked:
        return int(blocked.rsplit("_", 1)[-1]), None, None, True

    if not robots_allowed(url, DOD_USER_AGENT, timeout=timeout, session=session):
        prior = cache.get(url, {})
        cache[url] = {**prior, "blocked": ROBOTS_STATUS,
                      "blocked_since": prior.get("blocked_since", date.today().isoformat())}
        return ROBOTS_STATUS, None, None, False

    status, final_url, error = check_url(url, session, timeout)

    if status in (403, 429):
        prior = cache.get(url, {})
        cache[url] = {**prior, "blocked": f"HTTP_{status}",
                      "blocked_since": prior.get("blocked_since", date.today().isoformat())}
    elif not error and url in cache:
        # A real, non-blocked answer — clear a stale blocked flag (the
        # site un-blocked itself, our UA/IP situation changed, or its
        # robots.txt no longer disallows us).
        cache[url] = {k: v for k, v in cache[url].items()
                      if k not in ("blocked", "blocked_since")}
        if not cache[url]:
            del cache[url]

    return status, final_url, error, False


def main():
    parser = argparse.ArgumentParser(description="Check liveness of event citation URLs")
    parser.add_argument("--slug", type=str, help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=10, help="Per-request timeout in seconds")
    parser.add_argument("--no-cache", action="store_true",
                        help="Recheck URLs already confirmed BLOCKED on a prior run instead "
                             "of skipping them")
    parser.add_argument("--report", type=str, default=None,
                        help="Write a JSON summary of findings to this path "
                             "(dead/blocked/redirected/errored, with counts) "
                             "for ad hoc/manual review. Purely additive: never "
                             "changes stdout or the exit code.")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})
    cache = cf.load_state()

    checked = 0
    skipped_blocked = 0
    dead = []
    blocked = []
    robots_blocked = []
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
                status, final_url, error, skipped = check_url_cached(
                    url, session, args.timeout, cache, use_cache=not args.no_cache)
                seen_urls[url] = (status, final_url, error, skipped)
                checked += 1
                if skipped:
                    skipped_blocked += 1
            status, final_url, error, skipped = seen_urls[url]

            event_date = e.get("date", "?")
            event_title = e.get("title", "?")

            if error:
                errored.append((title, event_date, event_title, url, error))
                print(f"  ERROR    {title}  [{event_date}]  {event_title}")
                print(f"           {url}")
                print(f"           {error}")
            elif status == ROBOTS_STATUS:
                # The site's own robots.txt disallows us — we didn't even
                # try HEAD/GET. Not a dead or broken citation, just one we
                # deliberately didn't check; see docs/bot.md.
                robots_blocked.append((title, event_date, event_title, url))
                label = "STILL ROBOTS-BLOCKED" if skipped else "ROBOTS.TXT DISALLOWED"
                print(f"  {label}  {title}  [{event_date}]  {event_title}")
                if skipped:
                    since = cache.get(url, {}).get("blocked_since", "?")
                    print(f"           {url}  (confirmed disallowed since {since} — skipped, "
                          f"no request made; pass --no-cache to recheck)")
                else:
                    print(f"           {url}  (robots.txt disallows DOD-Bot — not requested)")
            elif status in (403, 429):
                # Near-certainly bot/scraper blocking (Cloudflare etc.), not a
                # dead resource — several sites in this landscape are known to
                # 403 automated requests while being perfectly live in a real
                # browser (sortitionfoundation.org, humanitix.com,
                # unimelb.edu.au among them, confirmed during manual research).
                # Reported separately from DEAD so nobody "fixes" a citation
                # that was never actually broken.
                blocked.append((title, event_date, event_title, url, status))
                label = "STILL BLOCKED" if skipped else "BLOCKED"
                print(f"  {label} ({status})  {title}  [{event_date}]  {event_title}")
                if skipped:
                    since = cache.get(url, {}).get("blocked_since", "?")
                    print(f"           {url}  (confirmed blocked since {since} — skipped, "
                          f"no request made; pass --no-cache to recheck)")
                else:
                    print(f"           {url}  (likely bot-blocking — verify manually in a browser before touching)")
            elif status is None or status >= 400:
                dead.append((title, event_date, event_title, url, status))
                print(f"  DEAD ({status})  {title}  [{event_date}]  {event_title}")
                print(f"           {url}")
                if cache.get(url, {}).get("url_status") != "dead":
                    # Never auto-set — a human decides, same as
                    # proof_level_locked elsewhere in this repo. This is a
                    # suggestion, not a verdict: url_status also covers
                    # "unfit" (a parked domain, still 200s) which this
                    # liveness check can't distinguish from healthy.
                    print(f"           suggest: python util/check_fragments.py "
                          f"--set-url-status \"{url}\" dead")
            elif final_url and strip_fragment(url).rstrip("/") != final_url.rstrip("/"):
                redirected.append((title, event_date, event_title, url, final_url))
                print(f"  REDIRECT {title}  [{event_date}]  {event_title}")
                print(f"           {url}  ->  {final_url}")

    cf.save_state(cache)

    print()
    print(f"Unique URLs checked: {checked}"
          + (f" ({skipped_blocked} answered from cache, already confirmed BLOCKED — "
             f"pass --no-cache to recheck)" if skipped_blocked else ""))
    print(f"Dead: {len(dead)}  Blocked (403/429, likely not actually dead): {len(blocked)}  "
          f"Robots-disallowed (not requested): {len(robots_blocked)}  "
          f"Redirected: {len(redirected)}  Errored: {len(errored)}")

    if args.report:
        def _rows(items, extra_key=None):
            if extra_key is None:
                return [{"org": t, "date": d, "event": et, "url": u}
                        for (t, d, et, u) in items]
            return [
                {"org": t, "date": d, "event": et, "url": u, extra_key: x}
                for (t, d, et, u, x) in items
            ]
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "generated": date.today().isoformat(),
                "counts": {"checked": checked, "dead": len(dead), "blocked": len(blocked),
                           "robots_blocked": len(robots_blocked),
                           "redirected": len(redirected), "errored": len(errored)},
                "dead": _rows(dead, "status"),
                "blocked": _rows(blocked, "status"),
                "robots_blocked": _rows(robots_blocked),
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
    if robots_blocked:
        print(f"\n{len(robots_blocked)} URL(s) weren't requested at all because the site's "
              "own robots.txt disallows DOD-Bot — this is us honoring their opt-out, not "
              "a citation problem.")
    print("No confirmed-dead event citation URLs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
