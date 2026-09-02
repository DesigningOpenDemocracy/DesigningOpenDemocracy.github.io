#!/usr/bin/env python3
"""
check_fragments.py — mechanically re-verify evidence against live pages.

Verifies four sources of evidence through the same pipeline:

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

3. Shared-link descriptions — from a blog post's `shared_link.description:`
   frontmatter (see CLAUDE.md's "Convention — shared_link"). When set, this
   is expected to be the verbatim abstract/summary text of the linked page
   — checked against `shared_link.url` the same way a footnote quote is
   checked against its citation URL.

4. Election quotes — from docs/data/elections.yml, the curated polling
   days the site-wide calendar carries (see CLAUDE.md's Calendar section).
   Same rule as an event quote: the sentence stating the date has to be
   verbatim on the cited page. Scoped like shared links rather than like
   events — an election belongs to no organisation, so --slug (org-scoped)
   skips them; --elections-only checks just these ~20 citations.

All four sources share the same store, fetch machinery, and reporting.

Results are kept in docs/data/citation-state.json (committed, so state
survives across weekly cron runs on fresh checkouts) keyed by URL. Named
"state," not "cache," on purpose (renamed from "evidence" 2026-08-24 — see
internal-heartbeat/machine-verifiable-citation.md's changelog): most
of what it holds (content hashes, matched contexts, the sticky blocked
flag below) IS re-derivable by re-fetching, but --set-url-status's
url_status field is not — a human-curated verdict (most acutely "unfit,"
a parked domain that 200s exactly like a healthy page — no script can
ever recompute that) with no other source of truth. Treat this file like
any other durable, hand-curated data, not a disposable artifact safe to
bulk-regenerate or delete; docs/data/citations.json (see
hooks/citation_export.py) is the one that's actually disposable — fully
regenerated from this file plus markdown on every build. Non-
Wikipedia fetches use conditional GET (If-None-Match / If-Modified-Since) so
an unchanged page costs a 304 instead of a full download. Wikipedia's
extracts API has no meaningful conditional-GET support, so it's always
fetched fresh, but the extract is still hashed and compared to the cached
hash — this doesn't save the request, but it does tell you whether the
article actually changed since your last check, which is the signal that
matters for "has this citation drifted."

Separately from that verification state, every full page body fetched here is
also written through to .pagecache/ (gitignored; see util/pagecache.py) so a
later human/AI session can read what a cited page said without re-pinging the
site. Those copies never feed back into verification — pass --no-page-cache
to skip writing them (the weekly cron does). The reverse direction exists as
--offline: check evidence against those stored copies alone, no network and
no effect on official verification state — the cite-adjustment workflow
(does my reworded quote still match what the page said at last fetch?).

A URL that returns 403/429 (bot protection, not a transient failure) has
that recorded against it (cache[url]["blocked"]/["blocked_since"]) and is
skipped entirely — no network call — on every subsequent run, reported as
STILL BLOCKED rather than FETCH ERROR, until --no-cache forces a recheck
or the site starts answering normally again. Retrying a server that's
already told us no, every week, forever, produces no new information —
same reasoning as scrape_news.py's existing bot_blocked hint, which is
skipped on re-runs the same way. A transient error (a timeout, a 500) is
NOT sticky like this — only 403/429 are, since those are the ones that
mean "this server doesn't want scripted requests," not "try again later."

A newly-blocked URL is queued into manual-dump/requests.txt (see
util/manual_dump.py) — a plain-text worklist for a human to open each URL
in a real browser and save it, since bot-protection and rate limits (both
the origin site's own and Wayback Machine's Save Page Now) can make a page
unreachable to every automated path here even though a human can still
read it fine. util/import_manual_dump.py turns a saved snapshot into an
`evidence` entry with a `manual_verified` flag, which check_evidence()
checks before falling back to STILL BLOCKED — and also when a fetch
succeeds but returns less text than the evidence string is long (a
JS-rendered SPA shell or a bot-challenge holding page: the quote can't
possibly be there, so that's a fetch failure, not evidence drift) — so a
manually-resolved citation stops being reported as blocked without ever
needing the origin site itself to start cooperating again.

Usage:
    python util/check_fragments.py           # verify all events + footnotes
    python util/check_fragments.py --slug mosaiclab  # single org (events + that page's footnotes)
    python util/check_fragments.py --slug g0v --slug namfrel  # multiple orgs
    python util/check_fragments.py --no-cache        # ignore cache, re-fetch everything
    python util/check_fragments.py           # ...but only those due for re-verification (see --max-age)
    python util/check_fragments.py --max-age 30      # tighter window: re-verify anything older than 30d
    python util/check_fragments.py --full            # full scan: every citation this run (still cache-aware)
    python util/check_fragments.py --unchecked-only  # skip anything already verified — zero requests for it
    python util/check_fragments.py --offline         # check against .pagecache/ copies only (no network)
    python util/check_fragments.py --verbose (-v)    # also print one line per quiet GOOD result
    python util/check_fragments.py --save-to-wayback # archive each URL to Wayback Machine
    python util/check_fragments.py --footnotes-only  # only check footnotes
    python util/check_fragments.py --elections-only  # only check election dates

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import hashlib
import io
import json
import os
import random
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
    closest_match_hint, count_occurrences, find_evidence, find_span, html_to_text,
    iter_footnote_citations, normalize_ws, quote_matches, spacing_autofix,
)
import manual_dump  # noqa: E402 — the manual-dump request queue (see util/manual_dump.py)
import pagecache  # noqa: E402 — local reading copies of fetched pages (see util/pagecache.py)
import reorder_frontmatter  # noqa: E402 — canonical frontmatter re-serialization for the autofix fallback
from robots_check import robots_allowed  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORG_DIR = os.path.join(DOCS_DIR, "organisations")
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "citation-state.json")
USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
FETCH_DELAY = 0.5  # seconds between requests — same rate limit as before

# A citation URL's body is downloaded in full before any extraction can
# happen — text_fragment.html_to_text()'s 2MB cap only trims the *result*
# after the whole page is already in memory, and a PDF/docx has no
# equivalent cap at all: pdfminer and the zip-XML walk both need the
# complete file, not just a prefix, so nothing short of not downloading it
# stops an oversized one. This corpus's actual PDF/docx citations run under
# 2MB; 20MB is generous headroom for a legitimate large report, sized to
# stop a mislinked large file (a dataset dump, a video, an ISO) from being
# pulled down in full just to be discarded as unparseable moments later.
MAX_FETCH_BYTES = 20 * 1024 * 1024

# Page bodies already fetched during *this* run, keyed by URL. check_evidence()
# runs once per evidence string, so a URL carrying several quotes used to be
# downloaded once per quote: 499 evidence items sit on 358 distinct URLs, and
# pmg.org.za/page/what-is-pmg alone was fetched 11 times in a single run — 141
# redundant downloads, 28% of the run, all of them re-asking a server for a
# body this process already had in memory. Conditional GET cannot help here
# (only 31% of these URLs send an ETag or Last-Modified at all, and a 304 is
# still a request); not asking twice in the first place is the fix.
#
# Only ever holds bodies fetched in the current process, so it cannot serve a
# stale page the way the on-disk cache deliberately might — which is why
# --no-cache still uses it: that flag means "don't trust the stored verdict",
# not "fetch the same page twice in one run".
_RUN_PAGES = {}


def reset_run_pages():
    """Drop this run's in-memory page bodies (used by tests)."""
    _RUN_PAGES.clear()

# Errors that mean "this site's bot protection (or its own robots.txt)
# said no," not "try again later" — 500s, timeouts, and DNS errors are
# transient and should still be retried every run, but a 403/429 (or a
# robots.txt Disallow) from the same server, week after week, isn't new
# information. See check_evidence()'s "blocked" cache field.
BLOCKED_ERRORS = {"HTTP_403", "HTTP_429", "ROBOTS_DISALLOWED"}


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(evidence):
    with open(STATE_PATH, "w") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)
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


def _extract_zip_xml_text(content):
    """Extract plain text from zip-packaged XML documents — .docx (OOXML,
    text in word/document.xml <w:t> runs) and .odt/.ods/.odp (OpenDocument,
    text in content.xml <text:p>/<text:span> elements). Stdlib-only: a
    zip is a zip, and ElementTree handles the namespaces. Detected by the
    PK zip magic bytes, not by URL extension (a .docx URL may serve
    anything after a site redesign; the bytes don't lie). Returns None if
    the bytes aren't a readable zip or contain none of the known document
    members — the caller turns that into an explicit OFFICE_PARSE_ERROR
    rather than a false MISMATCH. Formatting is lost deliberately:
    verification only ever needs the words."""
    try:
        import xml.etree.ElementTree as ET
        import zipfile

        def local(tag):
            return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""

        def walk(el, out):
            tag = local(el.tag)
            if tag in ("t", "span"):          # w:t / text:span (spans nest)
                out.append(el.text or "")
                for child in el:
                    walk(child, out)
            elif tag in ("tab", "br"):
                out.append(" ")
            elif tag in ("p", "h"):           # w:p / text:p, plus headings
                # Mixed-content order preserved: the paragraph's own leading
                # text, then each child in turn, then the break AFTER them.
                out.append(el.text or "")
                for child in el:
                    walk(child, out)
                out.append("\n")
            else:                              # document/body/run containers
                for child in el:
                    walk(child, out)

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for member in ("word/document.xml",   # .docx (OOXML)
                           "content.xml"):         # .odt/.ods/.odp (OpenDocument)
                if member not in z.namelist():
                    continue
                parts = []
                walk(ET.fromstring(z.read(member)), parts)
                return "".join(parts)
    except Exception:
        return None
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
            extract = next(iter(pages.values())).get("extract", "")
            pagecache.store(url, extract)
            return extract, r, None
        # Wikipedia's own REST/action API is deliberately not gated above —
        # it's designed for exactly this kind of programmatic access (see
        # CLAUDE.md's "Sourcing from Wikipedia"). Every other citation URL
        # is a third-party org's own site, so honor its robots.txt the same
        # way docs/bot.md promises for the rest of DOD's bot.
        if not robots_allowed(url, USER_AGENT, timeout=15, session=requests):
            return None, None, "ROBOTS_DISALLOWED"
        r = requests.get(url, headers=headers, timeout=15, stream=True)
        if r.status_code == 304:
            r.close()
            return None, r, None
        r.raise_for_status()

        # Enforce MAX_FETCH_BYTES before committing to the download: a
        # server-declared Content-Length over the cap skips the body
        # entirely, and iter_content() enforces the same cap while reading
        # in case the header is absent, wrong, or lying (chunked transfer
        # has no length to check up front).
        declared_length = r.headers.get("Content-Length")
        if declared_length is not None:
            try:
                if int(declared_length) > MAX_FETCH_BYTES:
                    r.close()
                    return None, None, "TOO_LARGE"
            except ValueError:
                pass

        chunks = bytearray()
        for chunk in r.iter_content(chunk_size=65536):
            chunks.extend(chunk)
            if len(chunks) > MAX_FETCH_BYTES:
                r.close()
                return None, None, "TOO_LARGE"
        content_bytes = bytes(chunks)

        content_type = r.headers.get("Content-Type", "")
        if "application/pdf" in content_type.lower() or content_bytes[:5] == b"%PDF-":
            text = _extract_pdf_text(content_bytes)
            if text is None:
                return None, None, "PDF_PARSE_ERROR"
            text = re.sub(r"\s+", " ", text).strip()
            pagecache.store(url, text)
            return text, r, None

        # Zip-packaged office documents (.docx/.odt/...), detected by magic
        # bytes rather than URL extension — after a site redesign a .docx
        # link may serve anything, and the bytes don't lie. A readable zip
        # that isn't a known document format reports OFFICE_PARSE_ERROR
        # rather than falling through to the HTML path: decoding compressed
        # bytes as text would just false-MISMATCH every quote (the same
        # failure mode issue #149 fixed for PDFs).
        if content_bytes[:2] == b"PK":
            text = _extract_zip_xml_text(content_bytes)
            if text is None:
                return None, None, "OFFICE_PARSE_ERROR"
            text = re.sub(r"\s+", " ", text).strip()
            pagecache.store(url, text)
            return text, r, None

        # Extraction itself (tag-stripping, script/style removal, entity
        # decoding, paragraph-break preservation, the 2MB sanity cap) lives
        # in text_fragment.html_to_text() — shared with the manual-dump
        # import path (util/import_manual_dump.py) so a live fetch and a
        # browser-saved snapshot of the same page always produce identical
        # text. See that function's docstring for the "why" of each step.
        #
        # Charset gotcha, confirmed on climateassembly.uk (2026-08-22): the
        # site serves UTF-8 bytes but declares no charset, and requests'
        # RFC-default for unlabelled text/* is ISO-8859-1 — so r.text came
        # back mojibake'd ("â€™" for "’") and every curly-apostrophe quote
        # false-MISMATCHed against it. Browsers sniff and render these fine.
        # When the declared encoding is absent or a Latin-1 family default,
        # prefer a clean UTF-8 decode of the raw bytes; fall back to r.text
        # if that fails (a genuinely non-UTF-8 legacy page).
        # r.text isn't available once the body's been read via iter_content
        # above rather than the r.content property — decode content_bytes
        # the same way r.text would (per r.encoding, replacing anything
        # that doesn't fit) rather than reading r.text itself.
        try:
            body = str(content_bytes, r.encoding or "utf-8", errors="replace")
        except LookupError:
            body = str(content_bytes, errors="replace")
        declared = (r.encoding or "").lower()
        if declared in ("", "iso-8859-1", "latin-1", "windows-1252"):
            try:
                body = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                pass
        text = html_to_text(body)
        pagecache.store(url, text)
        return text, r, None
    except requests.HTTPError as e:
        return None, None, f"HTTP_{e.response.status_code if e.response is not None else '?'}"
    except requests.RequestException:
        return None, None, "NETWORK_ERROR"
    except Exception:
        return None, None, "FETCH_ERROR"


def check_evidence(url, evidence, cache, use_cache=True, from_pagecache=False):
    """Verify one piece of evidence text against a URL, using the cache to
    avoid redundant fetches. The cache stores ETag/Last-Modified/content
    hash plus a small per-evidence-string good/bad map — deliberately NOT
    the fetched page text itself (that made the committed cache file grow
    to multiple megabytes when it was tried; hashes and booleans are all
    that's actually needed to skip redundant work).

    Returns (result, unchanged, error, ambiguous, hint, page_text) where
    result is "good"/"bad"/None, unchanged is True if this was answered
    from cache without a fetch that could reveal new content (i.e. a real
    304, or a URL already confirmed BLOCKED on a prior run — see the
    "blocked" cache field above check_evidence — not just "first look"),
    ambiguous is True if the evidence text
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
    the fetch-verification fields (etag/last_modified/document_sha256/
    evidence/checked); --save-to-wayback owns the archive fields and
    writes them separately in main().

    document_sha256 is sha256 of the full fetched page text, unconditional
    — the resource-level integrity signal projected into citations.json
    as item-level document.sha256 (see "Signal map" in
    internal-heartbeat/machine-verifiable-citation.md). It replaced a
    field named content_hash that computed paragraph_hash(text, evidence)
    — i.e. the hash of whichever quote's paragraph happened to be checked
    most recently — falling back to a whole-page hash only when that
    quote couldn't be located. Since this function runs once per evidence
    string, a multi-quote URL had that field overwritten on every check
    with a value that depended on iteration order, not page identity, and
    it was never actually read anywhere. Confirmed broken on a real
    multi-quote URL before being replaced: the stored value matched
    neither quote's own context hash.
    """
    entry = cache.get(url, {}) if use_cache else {}
    ev_key = sha256(normalize_ws(evidence))
    is_wikipedia = wikipedia_title(url) is not None

    # --offline: answer from the .pagecache/ reading copy only — no network,
    # no state-file writes, no manual-dump queueing. The cite-adjustment
    # use case: "does my reworded quote match what this page said last time
    # we actually fetched it?" Deliberately bypasses the sticky-blocked cache
    # too (a URL whose live fetch is blocked can still have a stored copy),
    # and returns the stored text as page_text so --autofix-spaces works
    # against it. The cache dict is left untouched: offline answers never
    # become official verification state — the live run owns that.
    if from_pagecache:
        stored = pagecache.get(url)
        if stored is None:
            return None, False, "NOT_CACHED", False, None, None
        text, meta = stored
        result = quote_matches(text, evidence)
        ambiguous = result and count_occurrences(text, evidence) > 1
        hint = None if result else closest_match_hint(text, evidence)
        return ("good" if result else "bad"), False, None, ambiguous, hint, text

    # A URL already confirmed BLOCKED (403/429) on a prior run is skipped
    # entirely — no network call this run at all — until --no-cache forces
    # a recheck. Retrying a site that's already told us no, every week,
    # forever, is wasted traffic that can't even produce new information;
    # this mirrors scrape_news.py's existing bot_blocked hint, which is
    # skipped on re-runs the same way. A manual_verified entry for this
    # exact evidence (written by util/import_manual_dump.py from a
    # human-saved browser snapshot — see util/manual_dump.py) is checked
    # first: a human's own browser reached the page even though a script
    # can't, so that result is used instead of reporting STILL BLOCKED
    # forever. Otherwise, queue this URL for a manual dump.
    if use_cache and entry.get("blocked"):
        manual_result = (find_evidence(entry, ev_key) or {}).get("manual_verified")
        if manual_result is not None:
            return ("good" if manual_result else "bad"), True, None, False, None, None
        manual_dump.queue_request(url)
        return None, True, entry["blocked"], False, None, None

    # Already downloaded this URL for a sibling quote in this same run? Then
    # the body in hand is this run's fetch — verify against it rather than
    # asking the server again. `validators` carries forward exactly what that
    # fetch would have written for etag/last_modified, so a second quote can't
    # blank them out (`entry` is deliberately empty under --no-cache).
    fetched = _RUN_PAGES.get(url)
    if fetched is not None:
        text, resp, validators = fetched["text"], None, fetched["validators"]
    else:
        validators = None
        headers = {"User-Agent": USER_AGENT}
        if not is_wikipedia:
            if entry.get("etag"):
                headers["If-None-Match"] = entry["etag"]
            if entry.get("last_modified"):
                headers["If-Modified-Since"] = entry["last_modified"]

        time.sleep(FETCH_DELAY)
        text, resp, error = _fetch_page_text(url, headers)
        if error:
            if error in BLOCKED_ERRORS:
                # Merge into whatever is already on disk for this URL (not the
                # possibly-emptied `entry` above) — a failed re-check must never
                # destroy a previously-successful verification's evidence data just
                # because *this* run's environment (a
                # different IP, a stricter bot filter) couldn't reach the page.
                # Confirmed happening in practice: a --no-cache run from a
                # network-disadvantaged sandbox overwrote real prefix/suffix/text
                # evidence a prior run had captured from an unblocked network,
                # with a bare {"blocked": ...} stub — see git history around
                # 2026-08-20 for the incident this guards against.
                prior = cache.get(url, {})
                cache[url] = {**prior, "blocked": error,
                              "blocked_since": prior.get("blocked_since", date.today().isoformat())}
                if (find_evidence(prior, ev_key) or {}).get("manual_verified") is None:
                    manual_dump.queue_request(url)
            return None, False, error, False, None, None

        if text is None:
            # 304 — server confirms unchanged. If we've already verified this
            # exact evidence string against this URL before, trust that result
            # without needing the body at all. Otherwise (a new event pointing
            # at an already-cached, unchanged URL) fall through to a fresh
            # unconditional fetch — correctness for the rare case beats trying
            # to be clever with a body we don't have.
            cached_result = (find_evidence(entry, ev_key) or {}).get("verified")
            if cached_result is not None:
                # Stamp this quote too, not just the URL: a 304 re-establishes
                # *this* verdict, and evidence_age_days() reads the per-quote
                # date so a sibling quote's check can't make this one look fresh.
                disk = cache.get(url, {})
                q = find_evidence(disk, ev_key)
                if q is not None:
                    q["checked"] = date.today().isoformat()
                cache[url] = {**disk, "checked": date.today().isoformat()}
                return ("good" if cached_result else "bad"), True, None, False, None, None
            time.sleep(FETCH_DELAY)
            text, resp, error = _fetch_page_text(url, {"User-Agent": USER_AGENT})
            if error:
                if error in BLOCKED_ERRORS:
                    # Same non-regression guard as above — merge into the entry
                    # already on disk, not the possibly-emptied local `entry`.
                    prior = cache.get(url, {})
                    cache[url] = {**prior, "blocked": error,
                                  "blocked_since": prior.get("blocked_since", date.today().isoformat())}
                    if (find_evidence(prior, ev_key) or {}).get("manual_verified") is None:
                        manual_dump.queue_request(url)
                return None, False, error, False, None, None

    if len(text) < len(evidence):
        # A 200/202-range response whose extracted text is shorter than the
        # evidence string itself cannot possibly contain it — we didn't get
        # the real page. Two confirmed shapes: a completely empty body
        # (glenweyl.com serves HTTP 202 with a blank page to DOD-Bot's plain
        # requests.get() — almost certainly a bot-challenge holding page), and
        # a JS-rendered SPA shell that serves only its title/nav chrome to
        # plain fetches while a browser sees thousands of characters
        # (governancehubafrica.org/about: 21 chars vs ~8,000 rendered).
        # Matching a quote against such text always "fails," which would
        # report a guaranteed, uninformative MISMATCH asserting the page no
        # longer says something we never actually saw — a fetch failure, not
        # evidence drift. A human's browser reads these pages fine, so consult
        # any manual_verified snapshot for this exact evidence first (same as
        # the blocked path above), otherwise queue the URL for a manual dump
        # and surface an error. Deliberately NOT cached as sticky-blocked:
        # unlike a 403, a shell-to-server-rendered switch is a realistic
        # recovery, so each run re-fetches and self-heals if the site changes.
        manual_result = (find_evidence(entry, ev_key) or {}).get("manual_verified")
        if manual_result is not None:
            return ("good" if manual_result else "bad"), True, None, False, None, None
        manual_dump.queue_request(url)
        return None, False, "EMPTY_RESPONSE" if not text else "PAGE_TOO_SHORT", False, None, None

    # What this run's fetch established for the URL's validators — computed
    # once, so a sibling quote reusing the body writes the same values rather
    # than falling back to `entry` (empty under --no-cache) and blanking them.
    if validators is None:
        if resp is not None and not is_wikipedia:
            validators = {"etag": resp.headers.get("ETag"),
                          "last_modified": resp.headers.get("Last-Modified")}
        else:
            validators = {"etag": entry.get("etag"),
                          "last_modified": entry.get("last_modified")}
        _RUN_PAGES[url] = {"text": text, "validators": validators}

    document_hash = sha256(text)
    # Merge into whatever is already on disk for this URL, not the local
    # `entry` — which --no-cache deliberately empties. Same non-regression
    # guard the two BLOCKED_ERRORS paths above already carry, which the
    # success path was missing: rebuilding "evidence" from an emptied
    # `entry` silently drops every *other* quote recorded against this URL,
    # since one run only ever re-checks the quotes it collected. Confirmed
    # in practice on 2026-08-25: a --no-cache run narrowed with --slug
    # dropped 28 verified event quotes belonging to orgs outside the slug
    # list, on URLs those orgs share with a checked page. --no-cache means
    # "don't trust the cached verdict for the quote I'm checking now," not
    # "erase what's known about the others."
    disk = cache.get(url, {})
    evidence_list = list(disk.get("evidence", []))
    result = quote_matches(text, evidence)
    q = find_evidence(disk, ev_key)
    if q is None:
        q = {"id": ev_key}
        evidence_list.append(q)
    q["quote"] = evidence
    q["verified"] = result
    q["checked"] = date.today().isoformat()
    if result:
        ctx = context_for_quote(text, evidence)
        if ctx:
            q["context"] = ctx
    cache[url] = {
        **{k: v for k, v in disk.items() if k not in
           ("etag", "last_modified", "document_sha256", "content_hash",
            "evidence", "checked", "blocked", "blocked_since")},
        "etag": validators["etag"],
        "last_modified": validators["last_modified"],
        "document_sha256": document_hash,
        "evidence": evidence_list,
        "checked": date.today().isoformat(),
    }
    ambiguous = result and count_occurrences(text, evidence) > 1
    hint = None if result else closest_match_hint(text, evidence)
    return ("good" if result else "bad"), False, None, ambiguous, hint, text


def write_quote_fix(path, old, new):
    """Surgically replace `old` with `new` in the source file at `path` (a
    quote: field value in org frontmatter, a shared_link.description:
    value in blog-post frontmatter, or a quoted footnote body).

    First tries a plain substring replace, which covers the common case of
    a plain YAML scalar: there the parsed value is stored verbatim, so the
    raw search finds it. When the value ISN'T stored verbatim — a folded or
    single/double-quoted scalar (the ones YAML itself chooses for values
    containing ': ' or apostrophes, e.g. 'l''été'), or one wrapped across
    lines at 80 chars — the raw text differs from the parsed value by
    escaping and line-wrapping and the search can't find it. Those fall
    back to _write_quote_fix_yaml() (org-page events:) or
    _write_shared_link_fix_yaml() (blog-post shared_link:), which locate
    the value by parsing the frontmatter instead of matching raw text.

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
    if _write_quote_fix_yaml(path, old, new):
        return True
    return _write_shared_link_fix_yaml(path, old, new)


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


def _write_shared_link_fix_yaml(path, old, new):
    """YAML-aware fallback for write_quote_fix, for a blog post's
    shared_link.description: value. Unlike org pages, blog-post frontmatter
    has no canonical field order to preserve (reorder_frontmatter.py only
    covers docs/organisations/), so this round-trips through
    python-frontmatter's own dumper rather than the canonical one — it will
    reformat the rest of the file's frontmatter, same tradeoff
    _write_quote_fix_yaml accepts for org pages, but with no ordering
    check to gate on first.

    Refuses (returns False) when the file has no frontmatter or
    shared_link.description doesn't equal `old` exactly.

    Never raises; returns True only after the file was actually written."""
    try:
        post = frontmatter.load(path)
        link = post.metadata.get("shared_link")
        if not isinstance(link, dict) or link.get("description") != old:
            return False
        link["description"] = new
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
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


def find_shared_link_evidence(path):
    """Yield (url, description_text, source_label, path) for a blog post's
    shared_link.description: — the abstract/summary of the linked resource,
    checked against shared_link.url the same way a footnote quote is
    checked against its citation URL."""
    post = frontmatter.load(path)
    link = post.metadata.get("shared_link")
    if not isinstance(link, dict):
        return
    url = str(link.get("url", ""))
    description = link.get("description")
    if not url or not description:
        return
    rel = os.path.relpath(path, os.path.join(DOCS_DIR, ".."))
    title = str(link.get("title", ""))[:50]
    yield url, description, "".join([rel, " shared_link (", title, ")"]), path


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


# The repo already has a staleness vocabulary — check_event_sourcing.py's
# STALE_CHECK_DAYS = 365 (a citation older than this is flagged for recheck),
# and activity_selector.py's 730/365/180 tiers. This window is deliberately
# derived from that bar rather than being a fourth unexplained number: a
# verifier that runs at the same period as the deadline it enforces is always
# marginally late, so it runs at roughly a quarter of it. Raise it toward 365
# to trade detection latency for traffic; it should not exceed 365, or
# check_event_sourcing.py would start flagging citations this script is
# supposed to be keeping fresh.
DEFAULT_MAX_AGE_DAYS = 90

# A floor on each run, not a cap: if more than this many are due, all of them
# run. Small enough to be free on a weekly cron, large enough that a
# fully-fresh corpus is still sampled.
DEFAULT_SPOT_CHECK = 10


def evidence_age_days(cache, url, ev_key, today=None):
    """Days since this specific quote was last verified against this URL,
    or None if it never has been.

    Reads the per-quote `checked` date, falling back to the URL-level one
    for entries written before that field existed. The distinction is not
    academic: a URL's `checked` refreshes whenever *any* quote on it is
    fetched, but only the quotes a run actually collected get re-evaluated.
    43% of this corpus's quotes (204 of 479) sit on multi-quote URLs, so
    keying staleness off the URL date alone would mark a quote fresh
    because a sibling was checked.
    """
    entry = cache.get(url, {})
    q = find_evidence(entry, ev_key) or {}
    stamp = q.get("checked") or entry.get("checked")
    if not stamp:
        return None
    try:
        then = date.fromisoformat(stamp)
    except ValueError:
        return None
    return ((today or date.today()) - then).days


def staleness_offset(url, max_age_days):
    """A deterministic 0..(max_age/2) day offset, subtracted from the window
    so a corpus checked in one batch doesn't all fall due on the same day.

    Without this the window degenerates: 297 of this repo's 367 URLs share a
    single `checked` date, so they would age out together, re-check together,
    and land on one identical date again — the weekly cron alternating
    between zero requests and the entire corpus rather than a steady trickle.
    Keyed on the URL's own hash (not random) so a given URL's due date is
    stable across runs and machines — the same deterministic-jitter trick
    home.html uses to spread coincident map markers.

    Subtracted, never added: `--max-age` names a *ceiling* on how stale a
    verdict may get, the same sense HTTP Cache-Control's max-age carries, so
    no quote may exceed it. Spreading by adding would have made --max-age 90
    mean "90 to 179 days, averaging 135" — a flag that silently misses its own
    stated bound. Capping the offset at half the window keeps re-checks inside
    [max_age/2, max_age] (mean ~0.75x) rather than letting a large offset make
    everything due almost immediately.
    """
    if max_age_days <= 0:
        return 0
    digest = hashlib.sha256(url.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, max_age_days // 2)


def is_due(cache, url, evidence_text, max_age_days, today=None):
    """True if this quote should be fetched this run.

    Never-checked evidence is always due, whatever the window. Otherwise it
    is due once its own age reaches the window *minus* its deterministic
    offset — so max_age is a genuine ceiling, never exceeded, with the offset
    spreading due dates across the back half of the window. max_age_days <= 0
    means "check everything" (the pre-window behaviour, still available as
    --max-age 0 or --full); a negative window is treated the same rather than
    being a way to skip everything.
    """
    age = evidence_age_days(cache, url, sha256(normalize_ws(evidence_text)), today)
    if age is None:
        return True
    if max_age_days <= 0:
        return True
    return age >= max_age_days - staleness_offset(url, max_age_days)


def spot_check_sample(not_due, want, today=None):
    """Pick `want` items from the not-due pile so a run is never a no-op.

    Once the corpus is fully fresh the staleness gate legitimately returns
    nothing, and a scheduled run that checks nothing detects nothing — a page
    can be rewritten the day after its last check and go unnoticed for the
    rest of the window. Sampling a handful anyway keeps a floor under drift
    detection for a fixed, small request cost.

    Seeded on today's date, so re-running on the same day re-checks the same
    sample (running twice doesn't hit twice as many servers) while the sample
    rotates day to day. Sorted by URL first so the seeding — not dict order —
    is what decides the pick.
    """
    if want <= 0 or not not_due:
        return []
    pool = sorted(not_due, key=lambda item: (item[0], item[1]))
    rng = random.Random((today or date.today()).isoformat())
    return rng.sample(pool, min(want, len(pool)))


def collect_evidence(args):
    """Return list of (url, quote, source_label, kind, path) tuples from
    events, footnotes, shared-link descriptions, and election dates.
    'kind' is 'event', 'footnote', 'shared_link', or 'election' for
    reporting."""
    items = []

    if getattr(args, "elections_only", False):
        return collect_election_evidence()

    event_paths = sorted(glob.glob(os.path.join(ORG_DIR, "*.md")))
    for path in event_paths:
        slug = os.path.basename(path)[:-3]
        if slug == "index":
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
        # --slug narrows footnotes to those orgs' own pages, and drops blog
        # shared links entirely. Before this, --slug only filtered events:
        # asking for one org still re-fetched every footnote citation on the
        # whole site, which on --no-cache means a request to every cited
        # webserver in the landscape to check three quotes.
        if args.slug:
            footnote_paths = [os.path.join(ORG_DIR, slug + ".md")
                              for slug in args.slug]
            footnote_paths = [p for p in footnote_paths if os.path.exists(p)]
        else:
            footnote_paths = sorted(glob.glob(
                os.path.join(DOCS_DIR, "**", "*.md"), recursive=True))

        for path in footnote_paths:
            for url, quote, source_label, path in find_footnote_evidence(path):
                items.append((url, quote, source_label, "footnote", path))

        if not args.slug:
            for path in sorted(glob.glob(os.path.join(DOCS_DIR, "blog", "posts", "*.md"))):
                for url, quote, source_label, path in find_shared_link_evidence(path):
                    items.append((url, quote, source_label, "shared_link", path))

            # Election dates (docs/data/elections.yml) — the calendar's one
            # source with no organisation behind it, so --slug (which is
            # org-scoped) skips them the same way it skips blog shared
            # links. --elections-only is the way to check just these.
            items.extend(collect_election_evidence())

    return items


def collect_election_evidence():
    """Evidence items for every election date carrying a quote:.

    Same treatment org event quotes get, for the same reason: an election
    date is a factual claim about someone else's page, and pages get
    rewritten. util/check_elections.py gates that the quote *exists*
    (offline, in CI); this is what checks it still says what we say it
    says."""
    items = []
    # Resolved from DOCS_DIR at call time, not pinned at import: the tests
    # point DOCS_DIR at a temp tree, and a module-level constant would keep
    # reading the repo's real election list into their runs.
    elections_file = os.path.join(DOCS_DIR, "data", "elections.yml")
    if not os.path.exists(elections_file):
        return items
    try:
        with open(elections_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return items
    for entry in (data.get("elections") or []):
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url", ""))
        quote = entry.get("quote")
        if not url or not quote:
            continue
        label = "election [" + str(entry.get("date", "?")) + "] " + str(entry.get("title", ""))[:50]
        items.append((url, quote, label, "election", elections_file))
    return items


def main():
    # Bodies are only ever reused within one run; a second main() in the same
    # process starts from an empty store rather than last run's pages.
    reset_run_pages()
    parser = argparse.ArgumentParser(
        description="Verify event and footnote evidence against live pages")
    parser.add_argument("--slug", type=str, action="append",
                        help="Check a single org — its events and its own page's "
                             "footnotes; blog shared links are skipped "
                             "(repeatable: pass --slug once per org)")
    parser.add_argument("--max-age", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        metavar="DAYS",
                        help="Re-verify a quote only once its last verdict is "
                             "this many days old (default: %(default)s). Evidence "
                             "never checked before is always verified, whatever "
                             "the window. Pass 0 to check everything every run "
                             "(the pre-2026-08-26 behaviour).")
    parser.add_argument("--full", action="store_true",
                        help="Full scan: verify every citation this run, ignoring "
                             "the --max-age window. Still cache-aware — conditional "
                             "GETs, and URLs already confirmed BLOCKED stay skipped. "
                             "Use --no-cache instead to also distrust stored verdicts "
                             "and retry blocked URLs.")
    parser.add_argument("--spot-check", type=int, default=DEFAULT_SPOT_CHECK,
                        metavar="N",
                        help="When fewer than N items are due, top the run up "
                             "to N by sampling already-fresh evidence, so a run "
                             "is never a no-op (default: %(default)s). The "
                             "sample is seeded on today's date: stable within a "
                             "day, rotating across days. 0 disables it.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the state file")
    parser.add_argument("--no-page-cache", action="store_true",
                        help="Don't write fetched page text to the local .pagecache/ "
                             "reading archive (util/pagecache.py). Used by the weekly "
                             "cron, where the artifact would be discarded with the "
                             "runner anyway; locally it's how you opt out.")
    parser.add_argument("--offline", action="store_true",
                        help="Check evidence against .pagecache/ copies only — no "
                             "network, no writes to the state file or the "
                             "manual-dump queue. For cite adjustment: verifies a "
                             "reworded quote against what its page said at last "
                             "fetch; URLs with no stored copy are reported as "
                             "NOT CACHED and don't fail the run.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print one line per checked item, including the quiet "
                             "GOOD results (problems always print regardless). "
                             "Useful as progress output on long --no-cache runs.")
    parser.add_argument("--save-to-wayback", action="store_true",
                        help="Archive each URL to Wayback Machine's Save Page Now")
    parser.add_argument("--set-url-status", type=str, nargs=2, default=None,
                        metavar=("URL", "STATUS"),
                        help="Manually record a citation URL's liveness in "
                             "the state file: STATUS is 'dead' (site is "
                             "gone/404s), 'unfit' (resolves, but to a parked "
                             "domain/spam — check_event_urls.py can't tell "
                             "this from a healthy 200 automatically), or "
                             "'live' (clears the field back to the implicit "
                             "default). Never auto-set by any script — a "
                             "human judgment call, same spirit as "
                             "proof_level_locked. Exits immediately after "
                             "writing; does not run verification.")
    parser.add_argument("--unchecked-only", action="store_true",
                        help="Skip any evidence already verified in a prior run "
                             "(its quote hash holds a 'verified' verdict in "
                             "citation-state.json's evidence list for that URL) "
                             "with zero network calls — not even a "
                             "conditional-GET 304 like the default cache-aware path "
                             "still makes. Only fetches evidence that has never been "
                             "checked before: a newly-added quote, or a newly-added "
                             "citation URL entirely. A MISMATCH from a prior run still "
                             "counts as checked and is skipped — this flag is for "
                             "catching up on new evidence quickly, not re-litigating "
                             "known failures (re-run without it, or --no-cache, for "
                             "that). Cannot be combined with --no-cache — they pull in "
                             "opposite directions on how much to trust the cache.")
    parser.add_argument("--footnotes-only", action="store_true",
                        help="Only check footnote evidence (skip events)")
    parser.add_argument("--events-only", action="store_true",
                        help="Only check event evidence (skip footnotes, shared links and elections)")
    parser.add_argument("--elections-only", action="store_true",
                        help="Only check docs/data/elections.yml's quotes — the ~20 "
                             "citations behind the calendar's polling days, rather than "
                             "every cited page on the site. Cannot be combined with "
                             "--events-only or --slug, which scope to orgs.")
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
    parser.add_argument("--report", type=str, default=None,
                        help="Write a JSON summary of findings to this path "
                             "(mismatches/ambiguous/fetch-errors, with counts) "
                             "for ad hoc/manual review. Purely additive: never "
                             "changes stdout or the exit code.")
    args = parser.parse_args()
    if args.offline and args.save_to_wayback:
        parser.error("--offline cannot be combined with --save-to-wayback")
    if args.full and args.unchecked_only:
        parser.error("--full and --unchecked-only are opposites: one verifies every "
                     "citation, the other only never-verified ones.")
    if args.full and args.max_age != DEFAULT_MAX_AGE_DAYS:
        parser.error("--full already means 'ignore the age window' — passing "
                     "--max-age as well is contradictory.")
    if args.full:
        # --full is the discoverable spelling of "no window"; everything
        # downstream reads args.max_age, so normalise here rather than
        # threading a second flag through the gate.
        args.max_age = 0
    if args.unchecked_only and args.max_age != DEFAULT_MAX_AGE_DAYS:
        parser.error("--unchecked-only and --max-age are two settings of the same "
                     "dial: --unchecked-only already means 'never re-verify'. "
                     "Pass one or the other.")
    if args.unchecked_only and args.no_cache:
        parser.error("--unchecked-only cannot be combined with --no-cache")
    if args.elections_only and (args.events_only or args.slug):
        parser.error("--elections-only cannot be combined with --events-only or --slug: "
                     "elections belong to no organisation, so an org-scoped run never "
                     "includes them")

    if args.set_url_status:
        url, status = args.set_url_status
        status = status.strip().lower()
        if status not in ("dead", "unfit", "live"):
            parser.error("--set-url-status STATUS must be one of: dead, unfit, live")
        evidence = load_state()
        entry = evidence.get(url, {})
        if status == "live":
            entry.pop("url_status", None)
            print(f"Cleared url_status for {url} (back to implicit live/unset)")
        else:
            entry["url_status"] = status
            print(f"Set url_status={status} for {url}")
        evidence[url] = entry
        save_state(evidence)
        return

    pagecache.enabled = not args.no_page_cache

    # Always start from the committed state file, even with --no-cache:
    # that flag means "don't use cached data to answer *this run's* checks"
    # (handled per-URL via use_cache= below, which check_evidence() already
    # respects), not "discard the file." save_state() at the end writes
    # this same dict back out — starting from {} here silently dropped
    # every entry not touched by this run's (possibly --slug-narrowed)
    # evidence set, which wiped ~500 unrelated entries the one time this
    # was run with --no-cache --slug together.
    cache = load_state()

    evidence_items = collect_evidence(args)

    # Freshness gate. --no-cache means "re-verify everything regardless", so
    # it bypasses this entirely. Otherwise: evidence that has never been
    # checked is always due, and evidence already carrying a verdict is
    # re-fetched only once it ages past --max-age (plus its deterministic
    # per-URL offset). --unchecked-only is the max-age-of-infinity end of the
    # same rule, kept as its own flag because "catch up on new citations
    # only" is a distinct intent from "re-verify on a schedule".
    skipped_stale_gate = 0
    spot_checked = 0
    if not args.no_cache:
        before = len(evidence_items)
        if args.unchecked_only:
            # Deliberately keyed on the presence of a verdict, NOT on age.
            # Evidence written before per-quote stamping carries `verified`
            # with no date at all, and an age-based predicate would read
            # every one of those as never-checked and re-fetch the entire
            # corpus — the exact opposite of what this flag is for.
            def _already_checked(item):
                ev_key = sha256(normalize_ws(item[1]))
                return "verified" in (find_evidence(cache.get(item[0], {}), ev_key) or {})
            evidence_items = [item for item in evidence_items
                              if not _already_checked(item)]
        else:
            due, not_due = [], []
            for item in evidence_items:
                (due if is_due(cache, item[0], item[1], args.max_age)
                 else not_due).append(item)
            # Top the run up to --spot-check items so a fully-fresh corpus
            # still gets sampled rather than checking nothing at all.
            topup = spot_check_sample(not_due, args.spot_check - len(due))
            spot_checked = len(topup)
            evidence_items = due + topup
        skipped_stale_gate = before - len(evidence_items)

    good = 0
    bad = 0
    errors = 0
    still_blocked = 0
    unchanged = 0
    ambiguous_count = 0
    autofixed = 0
    autofix_pending = 0
    not_cached = 0
    wayback_saved = 0
    wayback_failed = 0
    by_kind = {"event": {"good": 0, "bad": 0, "errors": 0},
               "footnote": {"good": 0, "bad": 0, "errors": 0},
               "shared_link": {"good": 0, "bad": 0, "errors": 0},
               "election": {"good": 0, "bad": 0, "errors": 0}}
    report_mismatches = []
    report_ambiguous = []
    report_fetch_errors = []
    # URLs this run has already downloaded — purely so the verbose line can
    # say a body was reused rather than claiming a fetch that didn't happen.
    # check_evidence()'s own _RUN_PAGES store is what actually does the
    # reusing; this just mirrors what it will have found.
    fetched_urls = set()
    reused_fetches = 0

    for url, evidence, source_label, kind, path in evidence_items:
        reused = url in fetched_urls
        result, unchanged_hit, error, ambiguous, hint, page_text = check_evidence(
            url, evidence, cache, use_cache=not args.no_cache,
            from_pagecache=args.offline
        )

        if page_text is not None and not args.offline:
            if reused:
                reused_fetches += 1
            fetched_urls.add(url)

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
            if unchanged_hit:
                # Already confirmed BLOCKED on a prior run — skipped
                # entirely this run, no network call made. See
                # check_evidence()'s "blocked" cache field.
                still_blocked += 1
                by_kind[kind]["errors"] += 1
                blocked_since = cache.get(url, {}).get("blocked_since", "?")
                report_fetch_errors.append({"source": source_label, "url": url, "error": error,
                                             "blocked_since": blocked_since})
                print("  STILL BLOCKED  " + source_label)
                print("               " + url + "  (" + error + ", confirmed blocked since " +
                      blocked_since + " — skipped, use --no-cache to recheck)")
            elif error == "NOT_CACHED":
                # --offline mode only: no .pagecache copy for this URL yet.
                # A coverage gap, not a fetch failure or a bad quote — so it
                # gets its own counter, is excluded from the per-kind error
                # tallies, and never affects the exit code.
                not_cached += 1
                report_fetch_errors.append({"source": source_label, "url": url, "error": error})
                print("  NOT CACHED  " + source_label)
                print("              " + url)
                print("              no .pagecache copy yet — do one fetching pass "
                      "(e.g. --no-cache) before relying on --offline here")
            else:
                errors += 1
                by_kind[kind]["errors"] += 1
                report_fetch_errors.append({"source": source_label, "url": url, "error": error})
                print("  FETCH ERROR  " + source_label)
                print("               " + url + "  (" + error + ")")
            continue

        if unchanged_hit:
            unchanged += 1

        if result == "good":
            good += 1
            by_kind[kind]["good"] += 1
            if args.verbose:
                # page_text non-None means this run had a full body in hand
                # (a live fetch, or the stored copy in --offline mode).
                # None means answered without one — within this no-error
                # branch that only happens on a genuine 304 (see
                # check_evidence()'s docstring), so say that explicitly
                # rather than leaving it as a silent blank suffix.
                if page_text:
                    if args.offline:
                        origin = "from .pagecache"
                    elif reused:
                        origin = "reused this run's fetch"
                    else:
                        origin = "fetched"
                    suffix = f"  ({origin}, {len(page_text):,} chars)"
                else:
                    suffix = "  (304, server confirmed unchanged since last check)"
                print("  ok  " + source_label + suffix)
            if ambiguous:
                ambiguous_count += 1
                report_ambiguous.append({"source": source_label, "url": url, "evidence": evidence[:200]})
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
                        evidence_list = list(entry.get("evidence", []))
                        q = find_evidence(entry, new_key)
                        if q is None:
                            q = {"id": new_key}
                            evidence_list.append(q)
                        q["quote"] = corrected
                        q["verified"] = True
                        q["checked"] = date.today().isoformat()
                        cache[url] = {**entry, "evidence": evidence_list}
                        autofixed += 1
                        print("  AUTOFIXED (spacing only)  " + source_label)
                        print("            quote: " + evidence[:80])
                        print("            →      " + corrected[:80])
                        continue
                    autofix_pending += 1
            bad += 1
            by_kind[kind]["bad"] += 1
            report_mismatches.append({"source": source_label, "url": url, "evidence": evidence[:200]})
            print("  MISMATCH  " + source_label)
            if page_text is None:
                # Only reachable via a genuine 304 in this no-error branch —
                # the server confirmed the page hasn't changed at all, so
                # this MISMATCH is a repeat of an already-known failure, not
                # something newly discovered this run.
                print("            (304, server confirmed unchanged since last "
                      "check — not a new failure)")
            print("            evidence: " + evidence[:80])
            print("            url: " + url)
            if hint:
                passage, ratio, diff = hint
                print("            closest match on page ({:.0%} similar): {}".format(
                    ratio, passage[:120]))
                if diff:
                    print("            diff (page − / quote +):")
                    print(diff)

    # Offline answers never touch the cache dict (check_evidence returns
    # before any mutation), but guard the save anyway so that invariant
    # holds even if future code paths start writing.
    if not args.offline:
        save_state(cache)

    print()
    print("Evidence checked: " + str(good) + " good, " + str(bad) + " mismatch, " +
          str(errors) + " fetch errors")
    print("  (" + str(unchanged) + " of those confirmed unchanged since last check)")
    if still_blocked:
        print("  (" + str(still_blocked) + " more skipped — already confirmed BLOCKED on a "
              "prior run; pass --no-cache to recheck)")
    if not_cached:
        print("  (" + str(not_cached) + " more had no local copy — offline mode checks "
              ".pagecache/ only)")
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
    print("  Shared links: " + str(by_kind["shared_link"]["good"]) + " good, " +
          str(by_kind["shared_link"]["bad"]) + " bad, " +
          str(by_kind["shared_link"]["errors"]) + " errors")
    print("  Elections: " + str(by_kind["election"]["good"]) + " good, " +
          str(by_kind["election"]["bad"]) + " bad, " +
          str(by_kind["election"]["errors"]) + " errors")
    if args.save_to_wayback:
        print("Wayback Machine: " + str(wayback_saved) + " saved, " +
              str(wayback_failed) + " failed")
    if spot_checked:
        print(str(spot_checked) + " of the above were not due — spot-checked "
              "anyway to keep the run from being a no-op (--spot-check)")
    if reused_fetches:
        print(str(reused_fetches) + " evidence item(s) verified against a page "
              "this run had already downloaded for another quote — no second "
              "request made")
    if skipped_stale_gate:
        reason = ("--unchecked-only" if args.unchecked_only
                  else "verified within the last " + str(args.max_age) +
                       "d — pass --max-age 0 or --no-cache to force")
        print(str(skipped_stale_gate) + " already-verified evidence item(s) "
              "skipped (" + reason + ")")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "generated": date.today().isoformat(),
                "counts": {"good": good, "bad": bad, "errors": errors,
                           "ambiguous": ambiguous_count},
                "mismatches": report_mismatches,
                "ambiguous": report_ambiguous,
                "fetch_errors": report_fetch_errors,
            }, f, indent=2)
            f.write("\n")

    if bad:
        print("\n" + str(bad) + " piece(s) of evidence no longer match their " +
              ("stored .pagecache copy" if args.offline else "live source") + ".")
        sys.exit(1)
    else:
        print("All checkable evidence matches " +
              ("stored .pagecache copies." if args.offline else "live pages."))
        if errors:
            print("(" + str(errors) + " fetch errors — re-run later)")
        sys.exit(0)


if __name__ == "__main__":
    main()
