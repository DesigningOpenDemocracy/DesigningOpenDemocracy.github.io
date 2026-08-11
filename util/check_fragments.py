#!/usr/bin/env python3
"""
check_fragments.py — mechanically re-verify evidence against live pages.

Verifies two sources of evidence through the same pipeline:

1. Event quotes — from org frontmatter `events:` entries. An event's
   "mechanical proof" is the exact text in its `quote:` field — this must
   appear verbatim on the cited page. The #:~:text= fragment is derived
   from quote: at render time and is never stored in frontmatter.

2. Footnote quotes — from prose footnote citations in org pages, blog
   posts, and concept pages. A footnote that carries a verbatim quoted
   excerpt (per the CLAUDE.md "Prose footnote citations" convention) is
   checked against its cited page using the same quote_matches() logic
   (see text_fragment.py) — including its '...' elision handling, so a
   quote like "X... Y" verifies correctly instead of always mismatching
   on the literal ellipsis that never appears on a real page.

Both sources share the same cache, fetch machinery, and reporting.

Caching: results are kept in docs/data/event-evidence-cache.json (committed, so state
survives across weekly cron runs on fresh checkouts) keyed by URL. Non-
Wikipedia fetches use conditional GET (If-None-Match / If-Modified-Since) so
an unchanged page costs a 304 instead of a full download. Wikipedia's
extracts API has no meaningful conditional-GET support, so it's always
fetched fresh, but the extract is still hashed and compared to the cached
hash — this doesn't save the request, but it does tell you whether the
article actually changed since your last check, which is the signal that
matters for "has this citation drifted."

Usage:
    python util/check_fragments.py           # verify all events + footnotes
    python util/check_fragments.py --slug mosaiclab  # single org
    python util/check_fragments.py --no-cache        # ignore cache, re-fetch everything
    python util/check_fragments.py --save-to-wayback # archive each URL to Wayback Machine
    python util/check_fragments.py --footnotes-only  # only check footnotes

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import hashlib
import html
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

sys.path.insert(0, os.path.dirname(__file__))
from text_fragment import (  # noqa: E402
    count_occurrences, find_span, iter_footnote_citations, normalize_ws, quote_matches,
)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORG_DIR = os.path.join(DOCS_DIR, "organisations")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "event-evidence-cache.json")
USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
FETCH_DELAY = 0.5  # seconds between requests — same rate limit as before

BLOCK_TAGS = [
    "p", "div", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "header", "footer", "main", "aside", "nav",
    "figure", "figcaption", "br", "hr",
    "li", "ol", "ul", "dl", "dt", "dd", "table", "tr",
]
BLOCK_PATTERN = re.compile(
    r"</?(" + "|".join(BLOCK_TAGS) + r")\b[^>]*>",
    re.IGNORECASE
)
PARAGRAPH_DELIM = "\x00P\x00"


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


def paragraph_hash(text, quote):
    """Hash the paragraph containing the quote, bounded by \n\n
    paragraph delimiters. Returns the SHA256 hex digest, or None if
    the quote cannot be located in the text.

    Uses find_span() to locate the quote directly in `text`'s own
    coordinates, rather than searching a separately-normalized copy and
    reusing that offset here — mixing the two used to drift by one
    character per paragraph break preceding the quote (normalize_ws()
    shrinks each "\\n\\n" to a single space), landing this function in
    the wrong paragraph — sometimes one that doesn't even contain the
    quote — on any page with enough short paragraphs before the cited
    sentence. See internal-heartbeat/machine-verifiable-citation.md's
    "Known issues" note for the reproduction.
    """
    if not text or not quote:
        return None
    span = find_span(text, quote)
    if span is None:
        return None
    idx, end_idx = span
    before = text.rfind("\n\n", 0, idx)
    after = text.find("\n\n", end_idx)
    para_start = before + 2 if before != -1 else 0
    para_end = after if after != -1 else len(text)
    para_text = text[para_start:para_end]
    return sha256(normalize_ws(para_text))


def wikipedia_title(url):
    """Return (lang_subdomain, article_title) for any *.wikipedia.org URL, or
    None. Previously this returned just the title and the fetch always
    queried en.wikipedia.org's API regardless of which language subdomain
    the citation actually pointed to — a real bug: an fr.wikipedia.org
    citation would silently fetch the (often nonexistent) English article
    instead, always producing a MISMATCH regardless of the French text's
    accuracy (confirmed on africtivistes, which cites fr.wikipedia.org and
    was being checked against an empty English API response)."""
    parsed = urlparse(url)
    if "wikipedia.org" not in parsed.netloc:
        return None
    m = re.search(r"/wiki/([^#]+)", parsed.path)
    if not m:
        return None
    lang = parsed.netloc.split(".")[0]
    return lang, unquote(m.group(1))


def _fetch_page_text(url, headers):
    """One unconditional or conditional GET. Returns (text_or_None, resp_or_None, error_or_None).
    text is None with resp set when the server returned 304 (unchanged, no body)."""
    wp = wikipedia_title(url)
    try:
        if wp:
            lang, title = wp
            # redirects=1 matters: e.g. en.wikipedia.org/wiki/Referendum_Council
            # redirects to Uluru_Statement_from_the_Heart — without this the API
            # returns an empty extract for any redirect title, which read as a
            # MISMATCH regardless of how accurate the stored evidence was.
            api_url = (
                f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts"
                f"&explaintext=1&redirects=1&titles={title}&format=json"
            )
            r = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            return next(iter(pages.values())).get("extract", ""), r, None
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 304:
            return None, r, None
        r.raise_for_status()
        # No practical truncation here — the cache only stores a hash and
        # per-evidence booleans now (see check_evidence), not the text
        # itself, so there's no memory-bloat reason to cap it. A prior
        # 100_000-char cap silently broke matches for evidence sitting
        # later in longer pages (confirmed: civictech.africa/about-ctin is
        # ~194KB of extracted text with its founding sentence at ~171KB —
        # a real false MISMATCH, not a wrong quote). 2MB is a sanity
        # ceiling against a truly pathological response, not a real limit.
        # <script>/<style> bodies are dropped before tag-stripping — a bare
        # <[^>]+> pass only removes the tags themselves, leaving inline
        # JSON-LD/page-props payloads in place as "text". Confirmed on
        # CAPaD's events page (JSON-LD embeds the same event title that
        # also appears in the visible listing) and mckinnon.co (a
        # Next.js page-props blob duplicating the visible paragraph) —
        # both made an otherwise-unique quote look like it occurred twice
        # on the page, which is a false ambiguity signal, not a real one.
        # html.unescape() decodes entities (&#8211;, &amp;, &quot;, &nbsp;,
        # etc.) left behind by tag-stripping — confirmed CAPaD's event page
        # embeds its listing as JSON-in-HTML with an en-dash encoded as the
        # literal string "&#8211;", which a quote written with a real "–"
        # character could never match without this.
        no_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", r.text, flags=re.S | re.I)
        with_paragraphs = BLOCK_PATTERN.sub(" " + PARAGRAPH_DELIM + " ", no_scripts)
        no_tags = re.sub(r"<[^>]+>", " ", with_paragraphs)
        text = re.sub(r"\s+", " ", html.unescape(no_tags))
        text = text.replace(PARAGRAPH_DELIM, "\n\n").strip()
        text = text[:2_000_000]
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

    Returns (result, unchanged, error, ambiguous) where result is
    "good"/"bad"/None, unchanged is True if this was answered from cache
    without a fetch that could reveal new content (i.e. a real 304, not
    just "first look"), and ambiguous is True if the evidence text occurs
    more than once on a freshly-fetched page (only known when a fetch
    actually happened — a cache hit reports ambiguous=False rather than
    re-deriving it, since the cache doesn't retain page text).
    """
    entry = cache.get(url, {}) if use_cache else {}
    ev_key = sha256(normalize_ws(evidence))
    is_wikipedia = wikipedia_title(url) is not None

    headers = {"User-Agent": USER_AGENT}
    if not is_wikipedia:
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("last_modified"):
            headers["If-Modified-Since"] = entry["last_modified"]

    time.sleep(FETCH_DELAY)
    text, resp, error = _fetch_page_text(url, headers)
    if error:
        return None, False, error, False

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
            return ("good" if cached_result else "bad"), True, None, False
        time.sleep(FETCH_DELAY)
        text, resp, error = _fetch_page_text(url, {"User-Agent": USER_AGENT})
        if error:
            return None, False, error, False

    new_hash = paragraph_hash(text, evidence) or sha256(text)
    verified = dict(entry.get("verified", {}))
    result = quote_matches(text, evidence)
    verified[ev_key] = result
    cache[url] = {
        "etag": resp.headers.get("ETag") if resp is not None and not is_wikipedia else entry.get("etag"),
        "last_modified": resp.headers.get("Last-Modified") if resp is not None and not is_wikipedia else entry.get("last_modified"),
        "content_hash": new_hash,
        "verified": verified,
        "checked": date.today().isoformat(),
    }
    ambiguous = result and count_occurrences(text, evidence) > 1
    return ("good" if result else "bad"), False, None, ambiguous


def find_footnote_evidence(path):
    """Yield (url, quote_text, source_label) for footnote definitions
    that qualify for the machine-verifiable quote convention — see
    text_fragment.py's footnote_citation() for the exactly-one-citation
    eligibility rule and why it exists."""
    rel = os.path.relpath(path, os.path.join(DOCS_DIR, ".."))
    with open(path, encoding="utf-8") as f:
        source = f.read()
    for i, line in enumerate(source.split("\n"), start=1):
        for label, url, title, quote in iter_footnote_citations(line):
            source_label = "".join([rel, ":", str(i), " [^", label, "]"])
            yield url, quote, source_label


def save_to_wayback(url, timeout=30):
    """Submit a URL to the Wayback Machine's Save Page Now service.
    Returns True on success, False on failure. Does not raise."""
    try:
        spn_url = "https://web.archive.org/save/" + url
        r = requests.get(spn_url, headers={"User-Agent": USER_AGENT},
                         timeout=timeout, allow_redirects=True)
        return r.status_code == 200
    except requests.RequestException:
        return False


def collect_evidence(args):
    """Return list of (url, quote, source_label, kind) tuples from
    events and footnotes. 'kind' is 'event' or 'footnote' for reporting."""
    items = []

    event_paths = sorted(glob.glob(os.path.join(ORG_DIR, "*.md")))
    for path in event_paths:
        slug = os.path.basename(path)[:-3]
        if slug in ("organisations", "concepts"):
            continue
        if args.slug and slug != args.slug:
            continue

        post = frontmatter.load(path)
        for e in post.metadata.get("events") or []:
            url = str(e.get("url", ""))
            if not url:
                continue
            if "proof_warning" in e:
                continue
            evidence = e.get("quote")
            if not evidence:
                continue
            items.append((url, evidence,
                         "".join([slug, " [", str(e.get("date", "?")), "] ",
                                  str(e.get("title", ""))[:50]]),
                         "event"))

    if not args.events_only:
        for path in sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.md"),
                                     recursive=True)):
            for url, quote, source_label in find_footnote_evidence(path):
                items.append((url, quote, source_label, "footnote"))

    return items


def main():
    parser = argparse.ArgumentParser(
        description="Verify event and footnote evidence against live pages")
    parser.add_argument("--slug", type=str, help="Check a single org")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the evidence cache")
    parser.add_argument("--save-to-wayback", action="store_true",
                        help="Archive each URL to Wayback Machine's Save Page Now")
    parser.add_argument("--footnotes-only", action="store_true",
                        help="Only check footnote evidence (skip events)")
    parser.add_argument("--events-only", action="store_true",
                        help="Only check event evidence (skip footnotes)")
    args = parser.parse_args()

    cache = {} if args.no_cache else load_cache()

    evidence_items = collect_evidence(args)

    good = 0
    bad = 0
    errors = 0
    unchanged = 0
    ambiguous_count = 0
    wayback_saved = 0
    wayback_failed = 0
    by_kind = {"event": {"good": 0, "bad": 0, "errors": 0},
               "footnote": {"good": 0, "bad": 0, "errors": 0}}

    for url, evidence, source_label, kind in evidence_items:
        result, unchanged_hit, error, ambiguous = check_evidence(
            url, evidence, cache, use_cache=not args.no_cache
        )

        if args.save_to_wayback:
            if save_to_wayback(url):
                wayback_saved += 1
            else:
                wayback_failed += 1
            time.sleep(0.5)

        if error:
            errors += 1
            by_kind[kind]["errors"] += 1
            print("  FETCH ERROR  " + source_label)
            print("               " + url + "  (" + error + ")")
            continue

        if unchanged_hit:
            unchanged += 1

        if result == "good":
            good += 1
            by_kind[kind]["good"] += 1
            if ambiguous:
                ambiguous_count += 1
                print("  AMBIGUOUS  " + source_label)
                print("             quote occurs more than once on the page")
                print("             evidence: " + evidence[:80])
        else:
            bad += 1
            by_kind[kind]["bad"] += 1
            print("  MISMATCH  " + source_label)
            print("            evidence: " + evidence[:80])
            print("            url: " + url)

    save_cache(cache)

    print()
    print("Evidence checked: " + str(good) + " good, " + str(bad) + " mismatch, " +
          str(errors) + " fetch errors")
    print("  (" + str(unchanged) + " of those confirmed unchanged since last check)")
    if ambiguous_count:
        print("  (" + str(ambiguous_count) + " of the good matches are AMBIGUOUS)")
    print("  Events: " + str(by_kind["event"]["good"]) + " good, " +
          str(by_kind["event"]["bad"]) + " bad, " + str(by_kind["event"]["errors"]) + " errors")
    print("  Footnotes: " + str(by_kind["footnote"]["good"]) + " good, " +
          str(by_kind["footnote"]["bad"]) + " bad, " +
          str(by_kind["footnote"]["errors"]) + " errors")
    if args.save_to_wayback:
        print("Wayback Machine: " + str(wayback_saved) + " saved, " +
              str(wayback_failed) + " failed")

    if bad:
        print("\n" + str(bad) + " piece(s) of evidence no longer match their live source.")
        sys.exit(1)
    else:
        print("All checkable evidence matches live pages.")
        if errors:
            print("(" + str(errors) + " fetch errors — re-run later)")
        sys.exit(0)


if __name__ == "__main__":
    main()
