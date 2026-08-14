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
    python util/check_fragments.py --slug g0v --slug namfrel  # multiple orgs
    python util/check_fragments.py --no-cache        # ignore cache, re-fetch everything
    python util/check_fragments.py --save-to-wayback # archive each URL to Wayback Machine
    python util/check_fragments.py --footnotes-only  # only check footnotes

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import hashlib
import html
import io
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import unquote, urlparse

import yaml

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))
from text_fragment import (  # noqa: E402
    closest_match_hint, count_occurrences, find_span, iter_footnote_citations, normalize_ws,
    quote_matches, spacing_autofix,
)
import reorder_frontmatter  # noqa: E402 — canonical frontmatter re-serialization for the autofix fallback

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


def paragraph_text(text, quote):
    """Return the paragraph containing the quote, bounded by \n\n delimiters,
    or None if the quote cannot be located. Uses find_span() in text's own
    coordinates — same logic as paragraph_hash() minus the hashing step."""
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
    return text[para_start:para_end]


CONTEXT_TEXT_MAX = 1000   # chars — cap paragraph text at this length
CONTEXT_SLICE = 150       # chars before and after the quote for prefix/suffix


def context_for_quote(text, quote):
    """Return a context dict with any combination of text, prefix, suffix,
    and sha256 for a quote confirmed to match the page. Returns None if
    the quote cannot be located.

    Always includes prefix and suffix (bracketing the quote's position).
    Includes text (the full containing paragraph) when it fits within
    CONTEXT_TEXT_MAX chars. sha256 is computed over text if present,
    otherwise prefix + quote + suffix.
    """
    para = paragraph_text(text, quote)
    if para is None:
        return None
    span = find_span(text, quote)
    idx, end_idx = span
    prefix_raw = text[max(0, idx - CONTEXT_SLICE):idx]
    suffix_raw = text[end_idx:end_idx + CONTEXT_SLICE]
    prefix = normalize_ws(prefix_raw).strip()
    suffix = normalize_ws(suffix_raw).strip()
    ctx = {"prefix": prefix, "suffix": suffix}
    para_norm = normalize_ws(para)
    if len(para_norm) <= CONTEXT_TEXT_MAX:
        ctx["text"] = para_norm
    ctx["sha256"] = sha256(ctx.get("text", prefix + quote + suffix))
    return ctx


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


def _extract_pdf_text(content):
    """Extract plain text from PDF bytes via pdfminer.six. Returns None if
    pdfminer isn't installed or extraction otherwise fails — the caller
    turns that into an explicit PDF_PARSE_ERROR rather than treating empty
    text as evidence of a genuine MISMATCH (see issue #149: a bare
    requests.get(url).text on a PDF silently decodes the raw compressed
    bytes as if they were HTML, finding nothing and false-MISMATCHing an
    otherwise-accurate quote — this replaces that path for PDF responses,
    detected by Content-Type or the %PDF- magic bytes)."""
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return None
    try:
        return extract_text(io.BytesIO(content))
    except Exception:
        return None


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

        content_type = r.headers.get("Content-Type", "")
        if "application/pdf" in content_type.lower() or r.content[:5] == b"%PDF-":
            text = _extract_pdf_text(r.content)
            if text is None:
                return None, None, "PDF_PARSE_ERROR"
            return re.sub(r"\s+", " ", text).strip(), r, None

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
        # An inline tag boundary immediately before punctuation (e.g.
        # "Wright</a>,") becomes "Wright ," above — a space that was never
        # actually rendered, since the closing tag carries no whitespace of
        # its own. Left in, this makes an accurately-transcribed quote that
        # spans an inline element (a link, a <span>, ...) false-MISMATCH,
        # and a quote "fixed" to match it would no longer be the real DOM
        # text a browser's #:~:text= lookup searches. Drop it so tag
        # boundaries never introduce punctuation spacing that didn't exist
        # in the rendered page.
        text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
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

    Returns (result, unchanged, error, ambiguous, hint, page_text) where
    result is "good"/"bad"/None, unchanged is True if this was answered
    from cache without a fetch that could reveal new content (i.e. a real
    304, not just "first look"), ambiguous is True if the evidence text
    occurs more than once on a freshly-fetched page (only known when a
    fetch actually happened — a cache hit reports ambiguous=False rather
    than re-deriving it, since the cache doesn't retain page text), hint
    is a (passage, ratio, diff) fuzzy-diff diagnostic (see
    text_fragment.closest_match_hint()) when result is "bad" and a fetch
    actually happened, else None, and page_text is the freshly-fetched
    page (None on 304/error paths) — supplied for --autofix-spaces, which
    derives a corrected quote from the live text and must never do so from
    a cache answer. hint is diagnostic only — it never changes result.

    Any existing archive_url/archive_checked fields on the cache entry
    are preserved across a fresh-fetch write — this function only owns
    the fetch-verification fields (etag/last_modified/content_hash/
    verified/checked); --save-to-wayback owns the archive fields and
    writes them separately in main().
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
        return None, False, error, False, None, None

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
            return ("good" if cached_result else "bad"), True, None, False, None, None
        time.sleep(FETCH_DELAY)
        text, resp, error = _fetch_page_text(url, {"User-Agent": USER_AGENT})
        if error:
            return None, False, error, False, None, None

    new_hash = paragraph_hash(text, evidence) or sha256(text)
    verified = dict(entry.get("verified", {}))
    result = quote_matches(text, evidence)
    verified[ev_key] = result
    contexts = dict(entry.get("contexts", {}))
    if result:
        ctx = context_for_quote(text, evidence)
        if ctx:
            contexts[ev_key] = ctx
    cache[url] = {
        **{k: v for k, v in entry.items() if k not in
           ("etag", "last_modified", "content_hash", "verified", "checked")},
        "etag": resp.headers.get("ETag") if resp is not None and not is_wikipedia else entry.get("etag"),
        "last_modified": resp.headers.get("Last-Modified") if resp is not None and not is_wikipedia else entry.get("last_modified"),
        "content_hash": new_hash,
        "verified": verified,
        "contexts": contexts,
        "checked": date.today().isoformat(),
    }
    ambiguous = result and count_occurrences(text, evidence) > 1
    hint = None if result else closest_match_hint(text, evidence)
    return ("good" if result else "bad"), False, None, ambiguous, hint, text


def write_quote_fix(path, old, new):
    """Surgically replace `old` with `new` in the source file at `path`
    (a quote: field value in org frontmatter, or a quoted footnote body).

    First tries a plain substring replace, which covers the common case of
    a plain YAML scalar: there the parsed value is stored verbatim, so the
    raw search finds it. When the value ISN'T stored verbatim — a folded or
    single/double-quoted scalar (the ones YAML itself chooses for values
    containing ': ' or apostrophes, e.g. 'l''été'), or one wrapped across
    lines at 80 chars — the raw text differs from the parsed value by
    escaping and line-wrapping and the search can't find it. Those fall
    back to _write_quote_fix_yaml(), which locates the value by parsing the
    frontmatter instead of matching raw text.

    Footnote bodies have no frontmatter to fall back to; if the raw
    substring isn't found there exactly once, return False and let the
    human edit: never guess.

    Returns True if the file was rewritten."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) == 1:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src.replace(old, new, 1))
        return True
    return _write_quote_fix_yaml(path, old, new)


def _write_quote_fix_yaml(path, old, new):
    """YAML-aware fallback for write_quote_fix: rewrite the event whose
    quote: value equals `old` (compared on the PARSED value, not raw text),
    then re-serialize the whole frontmatter through reorder_frontmatter's
    canonical dumper so the file still passes `reorder_frontmatter.py
    --check` after the edit.

    Refuses (returns False, letting the human edit) when:
      - the file has no frontmatter, no events list, or is otherwise not an
        org page (a footnote/markdown file — there's no YAML to rewrite);
      - `old` is not the quote: value of EXACTLY ONE event (a duplicate
        quote across two events would make which event to fix ambiguous);
      - the file's existing frontmatter isn't already canonical — the
        re-serialization would otherwise fold unrelated reformatting of
        every field into what should be a one-line fix (run
        reorder_frontmatter.py first if it isn't).

    Never raises; returns True only after the file was actually written."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not m:
            return False
        fm_text, body = m.group(1), content[m.end():]
        data = yaml.safe_load(fm_text)
        if not isinstance(data, dict):
            return False
        events = data.get("events")
        if not isinstance(events, list):
            return False
        targets = [e for e in events
                   if isinstance(e, dict) and e.get("quote") == old]
        if len(targets) != 1:
            return False
        if reorder_frontmatter.reorder_frontmatter(fm_text) != fm_text:
            return False
        targets[0]["quote"] = new
        new_fm = reorder_frontmatter.reorder_frontmatter(
            reorder_frontmatter.canonical_yaml_dump(data)).rstrip("\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n" + new_fm + "\n---\n" + body)
        return True
    except Exception:
        return False


def find_footnote_evidence(path):
    """Yield (url, quote_text, source_label, path) for footnote definitions
    that qualify for the machine-verifiable quote convention — see
    text_fragment.py's footnote_citation() for the exactly-one-citation
    eligibility rule and why it exists."""
    rel = os.path.relpath(path, os.path.join(DOCS_DIR, ".."))
    with open(path, encoding="utf-8") as f:
        source = f.read()
    for i, line in enumerate(source.split("\n"), start=1):
        for label, url, title, quote in iter_footnote_citations(line):
            source_label = "".join([rel, ":", str(i), " [^", label, "]"])
            yield url, quote, source_label, path


def save_to_wayback(url, timeout=30):
    """Best-effort archival, in two steps: (1) trigger a fresh snapshot via
    Save Page Now, (2) ask the read-only Availability API for a snapshot
    URL to actually record — the one just triggered if indexing was fast
    enough, otherwise the most recent existing one. Either way this
    returns a real, browsable Robust-Links-style fallback URL rather than
    just a yes/no on whether the trigger request succeeded (the old
    behavior — a 200 from /save/ doesn't mean a snapshot exists or tells
    you where to find it, and the trigger endpoint's own redirect chain
    isn't reliable enough to parse for the snapshot URL directly).

    Returns the snapshot URL (str) on success, None on failure. Never
    raises — both steps are best-effort and independent; a failed trigger
    doesn't prevent returning a URL from a snapshot that already existed.
    """
    try:
        requests.get("https://web.archive.org/save/" + url,
                     headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException:
        pass  # trigger is best-effort; the availability check below is what matters

    try:
        r = requests.get("https://archive.org/wayback/available",
                         params={"url": url},
                         headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        closest = r.json().get("archived_snapshots", {}).get("closest", {})
        if closest.get("available") and closest.get("url"):
            return closest["url"]
    except (requests.RequestException, ValueError):
        pass
    return None


def collect_evidence(args):
    """Return list of (url, quote, source_label, kind) tuples from
    events and footnotes. 'kind' is 'event' or 'footnote' for reporting."""
    items = []

    event_paths = sorted(glob.glob(os.path.join(ORG_DIR, "*.md")))
    for path in event_paths:
        slug = os.path.basename(path)[:-3]
        if slug in ("organisations", "concepts"):
            continue
        if args.slug and slug not in args.slug:
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
                         "event", path))

    if not args.events_only:
        for path in sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.md"),
                                     recursive=True)):
            for url, quote, source_label, path in find_footnote_evidence(path):
                items.append((url, quote, source_label, "footnote", path))

    return items


def main():
    parser = argparse.ArgumentParser(
        description="Verify event and footnote evidence against live pages")
    parser.add_argument("--slug", type=str, action="append",
                        help="Check a single org (repeatable: pass --slug once per org)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the evidence cache")
    parser.add_argument("--save-to-wayback", action="store_true",
                        help="Archive each URL to Wayback Machine's Save Page Now")
    parser.add_argument("--footnotes-only", action="store_true",
                        help="Only check footnote evidence (skip events)")
    parser.add_argument("--events-only", action="store_true",
                        help="Only check event evidence (skip footnotes)")
    parser.add_argument("--autofix-spaces", action="store_true",
                        help="Fix MISMATCHes that differ from the page only by "
                             "spacing (em-dash spacing, stray spaces): rewrite the "
                             "stored quote in place to the page's text. Only ever "
                             "applies to pure space-run differences — punctuation, "
                             "case, content, or the page having extra text stay "
                             "MISMATCH for manual judgment. Works on quotes stored "
                             "as plain YAML scalars AND folded/quoted ones (which "
                             "the raw substring can't find) — the latter are "
                             "rewritten via a frontmatter re-serialization that "
                             "keeps canonical ordering. Writes to source files, "
                             "so run it on a reviewable branch, not in the cron.")
    args = parser.parse_args()

    # Always start from the committed cache, even with --no-cache: that flag
    # means "don't use cached data to answer *this run's* checks" (handled
    # per-URL via use_cache= below, which check_evidence() already respects),
    # not "discard the cache file." save_cache() at the end writes this same
    # dict back out — starting from {} here silently dropped every entry not
    # touched by this run's (possibly --slug-narrowed) evidence set, which
    # wiped ~500 unrelated cached entries the one time this was run with
    # --no-cache --slug together.
    cache = load_cache()

    evidence_items = collect_evidence(args)

    good = 0
    bad = 0
    errors = 0
    unchanged = 0
    ambiguous_count = 0
    autofixed = 0
    autofix_pending = 0
    wayback_saved = 0
    wayback_failed = 0
    by_kind = {"event": {"good": 0, "bad": 0, "errors": 0},
               "footnote": {"good": 0, "bad": 0, "errors": 0}}

    for url, evidence, source_label, kind, path in evidence_items:
        result, unchanged_hit, error, ambiguous, hint, page_text = check_evidence(
            url, evidence, cache, use_cache=not args.no_cache
        )

        if args.save_to_wayback:
            archive_url = save_to_wayback(url)
            if archive_url:
                wayback_saved += 1
                cache[url] = {
                    **cache.get(url, {}),
                    "archive_url": archive_url,
                    "archive_checked": date.today().isoformat(),
                }
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
            # A MISMATCH that differs from the live page only by spaces is
            # safe to fix in place (spacing can't change what a quote claims
            # — see text_fragment.spacing_autofix); everything else stays a
            # MISMATCH for human judgment.
            if args.autofix_spaces:
                if page_text is None:
                    print("  AUTOFIX SKIPPED  " + source_label +
                          "  (answered from cache — rerun with --no-cache)")
                else:
                    corrected = spacing_autofix(page_text, evidence)
                    if corrected and write_quote_fix(path, evidence, corrected):
                        # Record the corrected string as verified against
                        # this fetch — we have the live text in hand, so
                        # this is the same evidence-confidence as any good
                        # result, not an unverified claim.
                        new_key = sha256(normalize_ws(corrected))
                        entry = cache.get(url, {})
                        verified = dict(entry.get("verified", {}))
                        verified[new_key] = True
                        cache[url] = {**entry, "verified": verified}
                        autofixed += 1
                        print("  AUTOFIXED (spacing only)  " + source_label)
                        print("            quote: " + evidence[:80])
                        print("            →      " + corrected[:80])
                        continue
                    autofix_pending += 1
            bad += 1
            by_kind[kind]["bad"] += 1
            print("  MISMATCH  " + source_label)
            print("            evidence: " + evidence[:80])
            print("            url: " + url)
            if hint:
                passage, ratio, diff = hint
                print("            closest match on page ({:.0%} similar): {}".format(
                    ratio, passage[:120]))
                if diff:
                    print("            diff (page − / quote +):")
                    print(diff)

    save_cache(cache)

    print()
    print("Evidence checked: " + str(good) + " good, " + str(bad) + " mismatch, " +
          str(errors) + " fetch errors")
    print("  (" + str(unchanged) + " of those confirmed unchanged since last check)")
    if autofixed:
        print("  (" + str(autofixed) + " auto-fixed in place (spacing-only differences))")
    if autofix_pending:
        print("  (" + str(autofix_pending) + " spacing-only fixes left for manual edit — "
              "quote text not found verbatim in the source file)")
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
