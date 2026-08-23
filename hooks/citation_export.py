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
DOD extension fields: convergence (see below), url-status (dead/unfit —
  see text_fragment.py's load_archive_info() docstring; absent means
  live/unset)
Evidence fields (per-claim, nested under evidence: array):
  id, convergence, type, quote, status, last-verified, verified-by,
  context

`id` is an opaque identifier: compared for equality, never recomputed, so
it doesn't need to name an algorithm. `convergence.sha256` is the
opposite kind of field — its entire job is "recompute this from the
current content and check it still matches," which is meaningless unless
the field itself says which algorithm to use, so it's named after the
algorithm rather than its purpose (an earlier draft called the field
itself `convergence-id`, flat, before that). `convergence` is a wrapper
object rather than a flat `sha256` field for the same reason
`evidence[].context` is one: the wrapper names *what's being hashed and
why*, `sha256` inside it says *how*. This also leaves room to add a
sibling key later — e.g. `convergence.file-sha256` for a whole-file hash
of a downloaded PDF/.docx, a real but currently-unbuilt gap (see the
design doc) — without a second top-level field to invent when that day
comes.

`id` and `convergence.sha256` are both full-length lowercase sha256 hex
digests, never truncated here — item-level over the URL, evidence-level
over the normalized quote. For DOD's own implementation the two are
byte-identical at both levels, since DOD's `id` is itself content-
derived; `convergence` is emitted anyway rather than omitted as a
"redundant" duplicate, so consumers never need conditional presence-
checking logic to know which field to read — a uniform schema is worth
more than the few bytes saved by leaving it out. See "id vs the sha256
field" in internal-heartbeat/machine-verifiable-citation.md for why both
exist (an implementation using a non-content-derived `id` still needs
`convergence.sha256` to stay comparable with everyone else), and
"Identifier construction" for the normative hash rules, including the
quote normalization an external implementer needs to reproduce these
values.

archive/archive_location/url-status are a read-only projection of
docs/data/citation-evidence.json — see on_pre_build()'s comment for
why this file never independently writes those three fields itself.

KNOWN GAP: status/last-verified/verified-by/context are carried forward
from this file's own previous output, which never exists (citations.json
is gitignored and rebuilt from empty), so they are populated on zero
entries despite check_fragments.py having already computed all of them
into citation-evidence.json. Same failure mode the archive fields hit
before they became a projection. See "Specified but unpopulated" in
Appendix B of the design doc.
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
        # Full, untruncated hash — same reasoning as evidence[].id below:
        # this file stores the canonical identity, and a JSON field has
        # no byte-budget pressure pushing toward truncation (unlike the
        # dod_evidence COinS-span pointer, which does). Truncating for a
        # shorter human-facing citation key is a display-time choice for
        # whoever renders one, not something baked into the stored data.
        # sha256, not md5, for consistency with evidence[].id — nothing
        # here depends on md5 specifically.
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cite = {
            "id": url_hash,
            # Byte-identical to id here, since DOD's id is itself
            # content-derived — emitted anyway rather than omitted, so
            # every consumer can read convergence.sha256 unconditionally.
            # A wrapper object, not a flat field, matching
            # evidence[].context's own shape: the wrapper names what's
            # being hashed and why, sha256 says how. See "id vs the
            # sha256 field" in internal-heartbeat/
            # machine-verifiable-citation.md.
            "convergence": {"sha256": url_hash},
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
            # machine-verifiable-citation.md's "Identifier construction"),
            # unlike the per-URL id above, so it gets no byte-budget
            # trim the way a value embedded in page markup would.
            ev_id = hashlib.sha256(normalize_ws(quote).encode("utf-8")).hexdigest()
            # Byte-identical to id here, same reasoning as the item-level
            # convergence object above — always emitted, never treated as
            # a redundant duplicate to skip. Not the same thing as
            # context.sha256 below: convergence hashes the quote alone
            # (identity/agreement across implementations); context.sha256
            # hashes the surrounding span (did the page change around an
            # otherwise-intact claim).
            ev = {
                "id": ev_id,
                "convergence": {"sha256": ev_id},
                "type": "quote-match",
                "quote": quote,
            }
            for field in ("status", "last-verified", "verified-by", "context"):
                if old_ev.get(field):
                    ev[field] = old_ev[field]
            cite["evidence"].append(ev)

        citations.append(cite)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(citations, f, indent=2, ensure_ascii=False)
        f.write("\n")
