#!/usr/bin/env python3
"""
citations_tool.py — verify and augment a machine-verifiable citations.json.

Reads a citations.json file (CSL-JSON + evidence extension), fetches each
cited page, checks quotes against live text, and reports mismatches.

    python util/citations_tool.py                          # verify only
    python util/citations_tool.py --augment                # verify + write back
    python util/citations_tool.py --augment --archive      # also archive URLs
    python util/citations_tool.py --file my-citations.json # custom path

Requirements: requests (util/requirements.txt), plus check_fragments.py
for context extraction (stdlib shim otherwise).

--archive on DOD's OWN docs/data/citations.json is discouraged: as of
2026-08-22, hooks/citation_export.py projects archive/archive_location/
url-status onto that file fresh on every build, straight from
docs/data/event-evidence-cache.json (the one place check_fragments.py's
--save-to-wayback/--set-url-status ever write) — so a manual --archive
run here would just get overwritten by the next build, and having two
independent things call Wayback for the same URL is exactly the
disagreement this change was meant to close. See internal-heartbeat/
2026-08-22-citation-archival-design-decisions.md. --archive remains the
right tool for a THIRD-PARTY citations.json passed via --file, which has
no DOD evidence cache behind it.
"""

import argparse
import hashlib
import html as _html
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

# Try to import context extraction and diagnostics from our own
# check_fragments. Falls back to a simple prefix/suffix extractor if
# unavailable.
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from check_fragments import context_for_quote
except ImportError:
    context_for_quote = None

try:
    from text_fragment import closest_match_hint, count_occurrences
except ImportError:
    closest_match_hint = None
    count_occurrences = None

ETAG_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "data", ".citations-etag-cache.json"
)

DEFAULT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "data", "citations.json"
)
USER_AGENT = "Citations-Tool/1.0 (+https://github.com/DesigningOpenDemocracy)"
FETCH_DELAY = 0.5
CONTEXT_SLICE = 150
CONTEXT_TEXT_MAX = 1000

BLOCK_TAGS = re.compile(
    r"<(p|div|section|article|h[1-6]|blockquote|pre|"
    r"header|footer|main|aside|nav|figure|figcaption|br|hr|"
    r"li|ol|ul|dl|dt|dd|table|tr)\b[^>]*>",
    re.I,
)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_ws(text):
    return " ".join(text.split())


def _load_etag_cache():
    if os.path.exists(ETAG_CACHE_PATH):
        with open(ETAG_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_etag_cache(cache):
    with open(ETAG_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _fetch_page_text(url, etag_cache=None, timeout=15):
    """Fetch a URL and return plain text (HTML tags stripped, whitespace
    collapsed), the requests response, and an error string or None.
    If etag_cache is provided, sends conditional GET headers and records
    ETag/Last-Modified on success."""
    headers = {"User-Agent": USER_AGENT}
    is_wikipedia = "wikipedia.org" in urlparse(url).netloc

    # Wikipedia → extracts API for clean plain text (no conditional GET)
    if is_wikipedia:
        parsed = urlparse(url)
        m = re.search(r"/wiki/([^#]+)", parsed.path)
        if m:
            lang = parsed.netloc.split(".")[0]
            api_url = (
                f"https://{lang}.wikipedia.org/w/api.php"
                f"?action=query&prop=extracts&explaintext=1"
                f"&titles={m.group(1)}&format=json"
            )
            try:
                r = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
                r.raise_for_status()
                pages = r.json().get("query", {}).get("pages", {})
                text = ""
                for p in pages.values():
                    text += p.get("extract", "")
                return text.strip(), r, None
            except Exception as e:
                return None, None, str(e)

    # Conditional GET for non-Wikipedia URLs
    if etag_cache and url in etag_cache and not is_wikipedia:
        cached = etag_cache[url]
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        return None, None, str(e)

    # 304 — page unchanged, return sentinel
    if r.status_code == 304:
        return None, r, None

    raw = r.text

    # Update ETag cache
    if etag_cache is not None and not is_wikipedia:
        entry = {}
        if r.headers.get("ETag"):
            entry["etag"] = r.headers["ETag"]
        if r.headers.get("Last-Modified"):
            entry["last_modified"] = r.headers["Last-Modified"]
        if entry:
            etag_cache[url] = entry

    # Strip <script>/<style> bodies, replace block tags with paragraph
    # delimiters, strip remaining tags, collapse whitespace.
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = BLOCK_TAGS.sub(r" \n\n ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", _html.unescape(raw)).strip()[:2_000_000]
    return text, r, None


def quote_matches(page_text, quote):
    """Check if quote appears in page_text (whitespace-normalized)."""
    return normalize_ws(quote) in normalize_ws(page_text)


def _extract_context(page_text, quote):
    """Extract context around a quote. Uses check_fragments.context_for_quote
    if available, otherwise a stdlib-only prefix/suffix extractor."""
    if context_for_quote:
        return context_for_quote(page_text, quote)

    # Simple stdlib fallback
    idx = page_text.find(normalize_ws(quote))
    if idx == -1:
        ns = normalize_ws(page_text)
        idx = ns.find(normalize_ws(quote))
        if idx == -1:
            return None
        page_text = ns

    end_idx = idx + len(normalize_ws(quote))
    prefix = normalize_ws(page_text[max(0, idx - CONTEXT_SLICE):idx]).strip()
    suffix = normalize_ws(page_text[end_idx:end_idx + CONTEXT_SLICE]).strip()
    ctx = {"prefix": prefix, "suffix": suffix}
    ctx["sha256"] = sha256(prefix + normalize_ws(quote) + suffix)
    return ctx


def _save_to_wayback(url):
    """Attempt to archive a URL via Wayback Machine's Save Page Now.
    Returns (archive_url, error) — archive_url is the resolved snapshot URL
    or None."""
    # Trigger a save
    save_url = "https://web.archive.org/save/" + url
    try:
        r = requests.get(save_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except Exception as e:
        return None, str(e)

    # Try availability API for a resolved snapshot URL
    avail = f"https://archive.org/wayback/available?url={url}"
    try:
        r2 = requests.get(avail, headers={"User-Agent": USER_AGENT}, timeout=15)
        r2.raise_for_status()
        data = r2.json()
        snapshots = data.get("archived_snapshots", {})
        closest = snapshots.get("closest", {})
        if closest.get("available") and closest.get("url"):
            return closest["url"], None
    except Exception as e:
        return None, str(e)

    return None, "no snapshot available"


def process_citations(citations, augment=False, archive=False, use_cache=True):
    """Fetch each cited page, verify evidence, optionally write back
    status/context/archive. Returns (updated_citations, report_lines)."""
    etag_cache = _load_etag_cache() if use_cache else {}
    report = []
    for cite in citations:
        url = cite.get("URL")
        if not url:
            continue
        label = cite.get("title", url)[:80]
        report.append(f"\n--- {label} ---")

        time.sleep(FETCH_DELAY)
        page_text, resp, error = _fetch_page_text(url, etag_cache=etag_cache)

        if resp is not None and resp.status_code == 304:
            report.append("  (unchanged since last check — skipping)")
            # Carry forward existing status for summary counts
            for ev in cite.get("evidence", []):
                if not ev.get("status"):
                    ev["status"] = "MATCH"  # assumed from prior check
            continue

        if error or not page_text:
            report.append(f"  FETCH ERROR: {error or 'empty response'}")
            continue

        for ev in cite.get("evidence", []):
            quote = ev.get("quote", "")
            if not quote:
                continue

            matched = quote_matches(page_text, quote)
            old_status = ev.get("status")

            # --- status ---
            if matched:
                new_status = "MATCH"
                # Check for ambiguity on the fresh page
                if count_occurrences:
                    if count_occurrences(page_text, quote) > 1:
                        new_status = "AMBIGUOUS"
            else:
                new_status = "MISMATCH"

            ev["status"] = new_status
            if augment:
                ev["last-verified"] = date.today().isoformat()
                ev["verified-by"] = USER_AGENT

            if old_status and old_status != new_status:
                report.append(
                    f"  STATUS DRIFT: {old_status} → {new_status}  "
                    f"quote: {quote[:60]}..."
                )
            elif not old_status:
                report.append(
                    f"  STATUS: {new_status}  quote: {quote[:60]}..."
                )

            # --- fuzzy hint on mismatch ---
            if not matched and closest_match_hint:
                hint = closest_match_hint(page_text, quote)
                if hint:
                    passage, ratio, diff = hint
                    report.append(
                        f"    closest match ({ratio:.0%}): {passage[:80]}..."
                    )
                    if diff:
                        for line in diff.splitlines():
                            report.append("    " + line)

            # --- context ---
            if matched and augment:
                ctx = _extract_context(page_text, quote)
                if ctx:
                    ev["context"] = ctx

            stored_ctx = ev.get("context", {})
            if stored_ctx and matched:
                stored_hash = stored_ctx.get("sha256")
                if stored_hash:
                    # Recompute hash from the same context source
                    ctx_text = stored_ctx.get("text")
                    if ctx_text:
                        new_hash = sha256(ctx_text)
                    else:
                        prefix = stored_ctx.get("prefix", "")
                        suffix = stored_ctx.get("suffix", "")
                        new_hash = sha256(prefix + normalize_ws(quote) + suffix)
                    if new_hash != stored_hash:
                        report.append(
                            f"  CONTEXT DRIFT: sha256 changed (stored={stored_hash[:12]}..., "
                            f"now={new_hash[:12]}...)"
                        )

            # --- archive ---
            if archive and augment:
                if not cite.get("archive_location"):
                    archive_url, arch_err = _save_to_wayback(url)
                    if archive_url:
                        cite["archive"] = "Internet Archive Wayback Machine"
                        cite["archive_location"] = archive_url
                        report.append(f"  ARCHIVED: {archive_url}")
                    elif arch_err:
                        report.append(f"  ARCHIVE ERROR: {arch_err}")

        if augment and resp is not None:
            cite["accessed"] = {
                "date-parts": [[date.today().year, date.today().month, date.today().day]]
            }

    if etag_cache:
        _save_etag_cache(etag_cache)

    return citations, report


def main():
    parser = argparse.ArgumentParser(
        description="Verify and augment a machine-verifiable citations.json"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=DEFAULT_PATH,
        help=f"Path to citations.json (default: {DEFAULT_PATH})",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        help="Write verification results (status, context, archive) back to the file",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Also submit each URL to the Wayback Machine for archiving. "
             "Discouraged on DOD's own docs/data/citations.json — that "
             "file's archive fields are now projected fresh from "
             "docs/data/event-evidence-cache.json on every build (see "
             "check_fragments.py --save-to-wayback/--set-url-status) and "
             "would just overwrite whatever this writes. Intended for a "
             "third-party citations.json passed via --file instead.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip ETag cache — fetch every page unconditionally",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    with open(args.file) as f:
        citations = json.load(f)

    print(f"Loaded {len(citations)} citations from {args.file}")
    if args.augment:
        print("Mode: AUGMENT (will write back)")
    else:
        print("Mode: VERIFY (report only)")

    updated, report = process_citations(
        citations, augment=args.augment, archive=args.archive,
        use_cache=not args.no_cache,
    )

    for line in report:
        print(line)

    if args.augment:
        backup = args.file + ".bak"
        os.replace(args.file, backup)
        with open(args.file, "w") as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nWrote {len(updated)} citations to {args.file} (backup: {backup})")

    # Summary
    total = sum(len(c.get("evidence", [])) for c in updated)
    matches = sum(
        1 for c in updated for e in c.get("evidence", []) if e.get("status") == "MATCH"
    )
    mismatches = sum(
        1 for c in updated for e in c.get("evidence", []) if e.get("status") == "MISMATCH"
    )
    unknown = total - matches - mismatches
    print(f"\n{total} evidence entries: {matches} MATCH, {mismatches} MISMATCH, {unknown} unknown")


if __name__ == "__main__":
    main()
