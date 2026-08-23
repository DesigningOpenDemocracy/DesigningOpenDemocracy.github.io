"""
citation_export.py — on_pre_build MkDocs hook that produces and maintains
a CSL-JSON citations file with DOD content-integrity extension fields.

Output: docs/data/citations.json

Flow:
  1. Extract quotes from markdown (events + footnotes)
  2. Load existing citations.json (if any) to preserve verification data
  3. Load docs/data/citation-evidence.json for archive/url-status data
  4. Merge: add new quotes, drop removed ones, carry forward enrichment
  5. Write back

CSL-JSON fields: id, type, URL, title, accessed, archive, archive_location
  (id: sha256(url) hex digest truncated to 12 chars — short by design,
  a CSL/Pandoc-style citation key a human may type, unlike evidence[].id
  below which is machine-only)
DOD extension field: url-status (dead/unfit — see text_fragment.py's
  load_archive_info() docstring; absent means live/unset)
Evidence fields (per-claim, nested under evidence: array):
  id: sha256(normalize_ws(quote)) hex digest, full length — a stable,
    self-verifying pointer for something outside this file to address a
    specific evidence entry (a URL's evidence array can hold more than
    one quote). See internal-heartbeat/machine-verifiable-citation.md's
    "Evidence id length" for why it's never truncated here.
  type: quote-match, quote, status, last-verified, verified-by, context

archive/archive_location/url-status are a read-only projection of
docs/data/citation-evidence.json — see on_pre_build()'s comment for
why this file never independently writes those three fields itself.
"""

import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import (  # noqa: E402
    iter_footnote_citations,
    load_archive_info,
    normalize_ws,
)

try:
    import frontmatter
except ImportError:
    frontmatter = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
OUT_PATH = os.path.join(DOCS_DIR, "data", "citations.json")


def _extract_footnote_urls(markdown):
    for _label, url, title, quote in iter_footnote_citations(markdown):
        yield url, title, quote


def _collect_items():
    """Walk org pages + blog posts + concept pages, return list of
    (url, title, quote) tuples."""
    items = []
    md_files = sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True))

    for path in md_files:
        rel = os.path.relpath(path, DOCS_DIR)
        if rel.startswith("data/") or rel.startswith("overrides/"):
            continue

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # --- events with quote: frontmatter ---
        source_title = ""
        if frontmatter and "---" in content:
            post = frontmatter.loads(content)
            source_title = post.metadata.get("title", "")
            for event in post.metadata.get("events") or []:
                url = str(event.get("url", ""))
                quote = event.get("quote")
                if url and quote and url.startswith(("http://", "https://")):
                    items.append((url, event.get("title", ""), quote, source_title, "event"))

        # --- prose footnotes with verbatim quotes ---
        for url, title, quote in _extract_footnote_urls(content):
            items.append((url, title, quote, source_title, "footnote"))

    return items


def on_pre_build(config):
    items = _collect_items()
    if not items:
        return

    # Load existing citations.json to preserve enrichment
    existing = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH) as f:
            for cite in json.load(f):
                existing[cite["URL"]] = cite

    # archive/archive_location/url-status are a *projection* of
    # docs/data/citation-evidence.json, not carried forward from this
    # file's own previous output — that cache is the one place anything
    # ever writes a Wayback snapshot or a liveness verdict
    # (check_fragments.py's --save-to-wayback / --set-url-status), so
    # citations.json here is read-only with respect to those three
    # fields. See internal-heartbeat/2026-08-22-citation-archival-
    # design-decisions.md for why: two independent writers (this file's
    # old carry-forward plus a separate citations_tool.py --archive path)
    # could otherwise silently disagree about the same URL.
    archive_info = load_archive_info()

    # Group new items by URL
    by_url = {}
    for url, title, quote, _source, _kind in items:
        if url not in by_url:
            by_url[url] = {"title": "", "quotes": []}
        if not by_url[url]["title"] and title:
            by_url[url]["title"] = title
        by_url[url]["quotes"].append(quote)

    citations = []
    for url, group in sorted(by_url.items()):
        old = existing.get(url, {})
        cite = {
            # Short by design (a CSL/Pandoc-style citation key a human may
            # actually type), unlike evidence[].id below which nobody
            # types by hand — see internal-heartbeat/
            # machine-verifiable-citation.md's "Evidence id length" for
            # why the two ids have different length/hash choices despite
            # looking similar. sha256, not md5, for consistency with
            # evidence[].id — nothing here depends on md5 specifically.
            "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:12],
            "type": "webpage",
            "URL": url,
            "title": group["title"] or old.get("title", ""),
        }

        # Carry forward CSL-level fields from previous enrichment
        # (accessed comes from citations_tool.py --augment, run against
        # this file directly — a separate, still-valid mechanism)
        if old.get("accessed"):
            cite["accessed"] = old["accessed"]

        # archive/archive_location/url-status: freshly projected from the
        # evidence cache on every build, never carried forward from this
        # file's own prior output — see the comment above.
        info = archive_info.get(url)
        if info:
            if info.get("archive_url"):
                cite["archive"] = "Internet Archive Wayback Machine"
                cite["archive_location"] = info["archive_url"]
            if info.get("url_status"):
                cite["url-status"] = info["url_status"]

        # Build evidence: preserve per-quote enrichment, drop removed quotes
        old_evidence = {e["quote"]: e for e in old.get("evidence", [])}
        cite["evidence"] = []
        for quote in sorted(set(group["quotes"])):
            old_ev = old_evidence.get(quote, {})
            # Full, untruncated hash — this id is meant to be referenced
            # from outside this file (see internal-heartbeat/
            # machine-verifiable-citation.md's "Evidence id length"),
            # unlike the per-URL id above, so it gets no byte-budget
            # trim the way a value embedded in page markup would.
            ev_id = hashlib.sha256(normalize_ws(quote).encode("utf-8")).hexdigest()
            ev = {"id": ev_id, "type": "quote-match", "quote": quote}
            for field in ("status", "last-verified", "verified-by", "context"):
                if old_ev.get(field):
                    ev[field] = old_ev[field]
            cite["evidence"].append(ev)

        citations.append(cite)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(citations, f, indent=2, ensure_ascii=False)
        f.write("\n")
