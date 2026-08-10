#!/usr/bin/env python3
"""
check_fragments.py — mechanically re-verify event evidence against live pages.

An event's "mechanical proof" is one piece of exact text that must appear on
the cited page — supplied either as a `quote:` field, or as a `#:~:text=`
fragment embedded in the `url:` itself. These are NOT two different proof
mechanisms with separate verification logic: whichever one an event has,
the "evidence text" gets checked the same way, against the same fetched
page, through one code path. The only thing fragments add on top of `quote:`
is that a browser highlights the text on click when a reader follows the
link — worth keeping for that reason, not worth a second verification
implementation.

Caching: results are kept in .event_evidence_cache.json (committed, so state
survives across weekly cron runs on fresh checkouts) keyed by URL. Non-
Wikipedia fetches use conditional GET (If-None-Match / If-Modified-Since) so
an unchanged page costs a 304 instead of a full download. Wikipedia's
extracts API has no meaningful conditional-GET support, so it's always
fetched fresh, but the extract is still hashed and compared to the cached
hash — this doesn't save the request, but it does tell you whether the
article actually changed since your last check, which is the signal that
matters for "has this citation drifted."

Usage:
    python util/check_fragments.py        # verify all events
    python util/check_fragments.py --slug mosaiclab  # single org
    python util/check_fragments.py --no-cache        # ignore cache, re-fetch everything

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import unquote, urlparse

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

ORG_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
CACHE_PATH = os.path.join(os.path.dirname(__file__), ".event_evidence_cache.json")
USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
FETCH_DELAY = 0.5  # seconds between requests — same rate limit as before


def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write("\n")


def sha256(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_ws(text):
    """Collapse whitespace for forgiving substring matching."""
    return " ".join(text.split())


def text_contains(text, needle):
    if not text or not needle:
        return False
    return normalize_ws(needle) in normalize_ws(text)


def extract_fragment(url):
    parsed = urlparse(url)
    if parsed.fragment and parsed.fragment.startswith(":~:text="):
        return unquote(parsed.fragment[len(":~:text="):])
    return None


def wikipedia_title(url):
    parsed = urlparse(url)
    if "wikipedia.org" not in parsed.netloc:
        return None
    m = re.search(r"/wiki/([^#]+)", parsed.path)
    return unquote(m.group(1)) if m else None


def _fetch_page_text(url, headers):
    """One unconditional or conditional GET. Returns (text_or_None, resp_or_None, error_or_None).
    text is None with resp set when the server returned 304 (unchanged, no body)."""
    title = wikipedia_title(url)
    try:
        if title:
            api_url = (
                "https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
                f"&explaintext=1&titles={title}&format=json"
            )
            r = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            return next(iter(pages.values())).get("extract", ""), r, None
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 304:
            return None, r, None
        r.raise_for_status()
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:100000]
        return text, r, None
    except requests.HTTPError as e:
        return None, None, f"HTTP_{e.response.status_code if e.response is not None else '?'}"
    except requests.RequestException:
        return None, None, "NETWORK_ERROR"
    except Exception:
        return None, None, "FETCH_ERROR"


def check_evidence(url, evidence, cache, use_cache=True):
    """Verify one piece of evidence text against a URL, using the cache to
    avoid redundant fetches. The cache stores ETag/Last-Modified/content
    hash plus a small per-evidence-string good/bad map — deliberately NOT
    the fetched page text itself (that made the committed cache file grow
    to multiple megabytes when it was tried; hashes and booleans are all
    that's actually needed to skip redundant work).

    Returns (result, unchanged, error) where result is "good"/"bad"/None
    and unchanged is True if this was answered from cache without a fetch
    that could reveal new content (i.e. a real 304, not just "first look").
    """
    entry = cache.get(url, {}) if use_cache else {}
    ev_key = sha256(normalize_ws(evidence))
    title = wikipedia_title(url)

    headers = {"User-Agent": USER_AGENT}
    if not title:
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("last_modified"):
            headers["If-Modified-Since"] = entry["last_modified"]

    time.sleep(FETCH_DELAY)
    text, resp, error = _fetch_page_text(url, headers)
    if error:
        return None, False, error

    if text is None:
        # 304 — server confirms unchanged. If we've already verified this
        # exact evidence string against this URL before, trust that result
        # without needing the body at all. Otherwise (a new event pointing
        # at an already-cached, unchanged URL) fall through to a fresh
        # unconditional fetch — correctness for the rare case beats trying
        # to be clever with a body we don't have.
        cached_result = entry.get("verified", {}).get(ev_key)
        if cached_result is not None:
            cache[url] = {**entry, "checked": date.today().isoformat()}
            return ("good" if cached_result else "bad"), True, None
        time.sleep(FETCH_DELAY)
        text, resp, error = _fetch_page_text(url, {"User-Agent": USER_AGENT})
        if error:
            return None, False, error

    new_hash = sha256(text)
    verified = dict(entry.get("verified", {}))
    result = text_contains(text, evidence)
    verified[ev_key] = result
    cache[url] = {
        "etag": resp.headers.get("ETag") if resp is not None and not title else entry.get("etag"),
        "last_modified": resp.headers.get("Last-Modified") if resp is not None and not title else entry.get("last_modified"),
        "content_hash": new_hash,
        "verified": verified,
        "checked": date.today().isoformat(),
    }
    return ("good" if result else "bad"), False, None


def main():
    parser = argparse.ArgumentParser(description="Verify event evidence against live pages")
    parser.add_argument("--slug", type=str, help="Check a single org")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the evidence cache — re-fetch and re-verify everything")
    args = parser.parse_args()

    cache = {} if args.no_cache else load_cache()

    good = 0
    bad = 0
    errors = 0
    unchanged = 0
    skipped_no_evidence = 0
    skipped_warning = 0

    for path in sorted(glob.glob(os.path.join(ORG_DIR, "*.md"))):
        slug = os.path.basename(path)[:-3]
        if slug in ("organisations", "concepts"):
            continue
        if args.slug and slug != args.slug:
            continue

        post = frontmatter.load(path)
        for e in post.metadata.get("events") or []:
            url = str(e.get("url", ""))
            if not url:
                continue  # source:-only events have nothing to fetch

            if "proof_warning" in e:
                skipped_warning += 1
                continue

            evidence = e.get("quote") or extract_fragment(url)
            if not evidence:
                skipped_no_evidence += 1
                continue

            title = e.get("title", "")[:50]
            event_date = e.get("date", "?")

            result, unchanged_hit, error = check_evidence(url, evidence, cache, use_cache=not args.no_cache)

            if error:
                errors += 1
                print(f"  FETCH ERROR  {slug}  [{event_date}]  {title}")
                print(f"               {url}  ({error})")
                continue

            if unchanged_hit:
                unchanged += 1

            if result == "good":
                good += 1
            else:
                bad += 1
                print(f"  MISMATCH  {slug}  [{event_date}]  {title}")
                print(f"            evidence: {evidence[:80]}")
                print(f"            url: {url}")

    save_cache(cache)

    print()
    print(f"Evidence checked: {good} good, {bad} mismatch, {errors} fetch errors")
    print(f"  ({unchanged} of those confirmed unchanged since last check — skipped re-download)")
    print(f"Skipped: {skipped_warning} have proof_warning (explicitly unverified), "
          f"{skipped_no_evidence} have neither quote: nor a fragment (note-only or source-only)")

    if bad:
        print(f"\n{bad} piece(s) of evidence no longer match their live source.")
        print("Fetch errors are NOT counted as mismatches (could be rate-limiting or a transient outage).")
        sys.exit(1)
    else:
        print("All checkable evidence matches live pages.")
        if errors:
            print(f"({errors} fetch errors — re-run later; a repeated failure on the same URL is worth investigating)")
        sys.exit(0)


if __name__ == "__main__":
    main()
