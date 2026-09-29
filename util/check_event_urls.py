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

A URL that's dead (404/410/5xx) or unreachable is backed off rather than
made sticky: the failure is recorded in the same cache's `failing` field
(util/backoff.py, shared with check_fragments.py) and the URL isn't asked
again for 7, 14, 28, 56, then 90 days, so a dead link costs a handful of
requests a year rather than two (a HEAD, then a GET to double-check) every
week. It's still reported as DEAD on every run, and still fails the run,
until someone fixes the citation or records the decision with
check_fragments.py --set-url-status <url> dead. Once a URL is marked dead
it no longer fails the run, and is only rechecked quarterly, to notice if
it comes back; an `unfit` URL (answers, but with the wrong content) isn't
requested at all, since liveness can't say anything about it.

Usage:
    python util/check_event_urls.py                  # check all event URLs
    python util/check_event_urls.py --slug mosaiclab  # single org
    python util/check_event_urls.py --timeout 8       # per-request timeout
    python util/check_event_urls.py --no-cache        # recheck blocked and backing-off URLs now
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import date, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

import backoff  # noqa: E402 — retry schedule for failing URLs
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
MARKED_STATUS = "MARKED"  # sentinel: url_status set by hand, not checked this run


def _failure_code(status, error):
    return f"HTTP_{status}" if status is not None else "NETWORK_ERROR"


def _from_failure_code(code):
    """(status, error) as check_url() would have returned them, rebuilt from
    a stored failure record for a URL skipped while backing off."""
    if code and code.startswith("HTTP_") and code[5:].isdigit():
        return int(code[5:]), None
    return None, code or "NETWORK_ERROR"


def check_url_cached(url, session, timeout, cache, use_cache=True, today=None):
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
    call this run.

    A URL that failed on an earlier run (see the module docstring) is
    answered from its failure record while backing off, and one a human
    marked with url_status returns the MARKED_STATUS sentinel: always for
    `unfit`, and for `dead` except for a quarterly revival check."""
    today = today or date.today()
    stored = cache.get(url, {})
    entry = stored if use_cache else {}
    blocked = entry.get("blocked")
    if blocked == ROBOTS_STATUS:
        return ROBOTS_STATUS, None, None, True
    if blocked:
        return int(blocked.rsplit("_", 1)[-1]), None, None, True

    url_status = stored.get("url_status")
    failing = entry.get("failing")
    if url_status == "unfit":
        return MARKED_STATUS, None, None, True
    if url_status == "dead":
        last = backoff.as_date((failing or {}).get("last"))
        if last and today < last + timedelta(days=backoff.MAX_RETRY_DAYS):
            return MARKED_STATUS, None, None, True
    elif failing and backoff.backing_off(failing, today):
        status, error = _from_failure_code(failing.get("error"))
        return status, None, error, True

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
    elif error or status >= 400:
        prior = cache.get(url, {})
        cache[url] = {**prior, "failing": backoff.record_failure(
            prior.get("failing"), _failure_code(status, error), today)}
    elif url in cache:
        # A real, working answer — clear a stale blocked flag (the site
        # un-blocked itself, our UA/IP situation changed, or its robots.txt
        # no longer disallows us) and any failure record.
        cache[url] = {k: v for k, v in cache[url].items()
                      if k not in ("blocked", "blocked_since", "failing")}
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
    marked = []
    revived = []
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
            url_status = cache.get(url, {}).get("url_status")
            failing = cache.get(url, {}).get("failing") or {}
            backing_off_note = (f"  (failing since {failing.get('since')}, "
                                f"{failing.get('count')} attempt(s); next check "
                                f"{backoff.next_try(failing)} — skipped, no request made; "
                                f"pass --no-cache to recheck now)")

            not_answering = bool(error) or (isinstance(status, int) and status >= 400)
            if status == MARKED_STATUS or (url_status in ("dead", "unfit") and not_answering):
                # A human already decided this citation is dead/unfit (see
                # --set-url-status), so it's not a finding to act on and
                # doesn't fail the run.
                marked.append((title, event_date, event_title, url, url_status))
                print(f"  MARKED {str(url_status).upper()}  {title}  [{event_date}]  {event_title}")
                print(f"           {url}  (url_status set by hand"
                      + (" — not checked this run)" if status == MARKED_STATUS else "; still not answering)"))
            elif error:
                errored.append((title, event_date, event_title, url, error))
                print(f"  {'STILL ERRORING' if skipped else 'ERROR'}    {title}  [{event_date}]  {event_title}")
                print(f"           {url}")
                print(f"           {error}" + (backing_off_note if skipped else ""))
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
                print(f"  {'STILL DEAD' if skipped else 'DEAD'} ({status})  {title}  [{event_date}]  {event_title}")
                print(f"           {url}" + (backing_off_note if skipped else ""))
                if cache.get(url, {}).get("url_status") != "dead":
                    # Never auto-set — a human decides, same as
                    # proof_level_locked elsewhere in this repo. This is a
                    # suggestion, not a verdict: url_status also covers
                    # "unfit" (a parked domain, still 200s) which this
                    # liveness check can't distinguish from healthy.
                    print(f"           suggest: python util/check_fragments.py "
                          f"--set-url-status \"{url}\" dead")
            elif url_status == "dead":
                # Marked dead by hand, but it answers now: worth a look.
                revived.append((title, event_date, event_title, url, status))
                print(f"  ANSWERING AGAIN ({status})  {title}  [{event_date}]  {event_title}")
                print(f"           {url}  (marked url_status: dead; if the content is back, "
                      f"clear it: python util/check_fragments.py --set-url-status \"{url}\" live)")
            elif final_url and strip_fragment(url).rstrip("/") != final_url.rstrip("/"):
                redirected.append((title, event_date, event_title, url, final_url))
                print(f"  REDIRECT {title}  [{event_date}]  {event_title}")
                print(f"           {url}  ->  {final_url}")

    cf.save_state(cache)

    print()
    print(f"Unique URLs checked: {checked}"
          + (f" ({skipped_blocked} answered from cache with no request: blocked, backing "
             f"off after failures, or marked by hand — pass --no-cache to recheck)"
             if skipped_blocked else ""))
    print(f"Dead: {len(dead)}  Blocked (403/429, likely not actually dead): {len(blocked)}  "
          f"Robots-disallowed (not requested): {len(robots_blocked)}  "
          f"Redirected: {len(redirected)}  Errored: {len(errored)}  "
          f"Marked dead/unfit by hand: {len(marked)}  Answering again: {len(revived)}")

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
                           "redirected": len(redirected), "errored": len(errored),
                           "marked": len(marked), "answering_again": len(revived)},
                "dead": _rows(dead, "status"),
                "blocked": _rows(blocked, "status"),
                "robots_blocked": _rows(robots_blocked),
                "redirected": _rows(redirected, "final_url"),
                "errored": _rows(errored, "error"),
                "marked": _rows(marked, "url_status"),
                "answering_again": _rows(revived, "status"),
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
