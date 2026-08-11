"""
citation_export.py — on_pre_build MkDocs hook that generates a
CSL-JSON citations file with DOD content-integrity extension fields.

Output: docs/data/citations.json

Sources:
  - Org events: frontmatter `events:` entries with `quote:` + `url:`
  - Prose footnotes: markdown footnotes with verbatim quoted excerpts
  - Evidence cache: docs/data/event-evidence-cache.json (content_hash, checked)

CSL-JSON fields: type, URL, title, accessed, content-sha256
Evidence fields (per-claim, nested under evidence: array):
  type: quote-match (extensible: screenshot, pdf-page, etc.)
  quote: verbatim excerpt
  last-verified: YYYY-MM-DD of last confirmation
"""

import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import iter_footnote_citations  # noqa: E402

try:
    import frontmatter
except ImportError:
    frontmatter = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "event-evidence-cache.json")
OUT_PATH = os.path.join(DOCS_DIR, "data", "citations.json")
VERIFIED_BY = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"


def _extract_footnote_urls(markdown):
    """Yield (url, title, quote) from footnotes that qualify for the
    machine-verifiable quote convention. See text_fragment.py's
    footnote_citation() for the exactly-one-citation eligibility rule —
    a footnote citing more than one source is skipped entirely rather
    than guessing which quote supports which URL (a prior version here
    took only the *first* URL in a multi-citation footnote, silently
    dropping any others from the export)."""
    for label, url, title, quote in iter_footnote_citations(markdown):
        yield url, title, quote


def _collect_items():
    """Walk org pages + blog posts + concept pages, return list of citation dicts."""
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
                    items.append({"url": url, "title": event.get("title", ""),
                                  "quote": quote, "source": source_title,
                                  "kind": "event"})

        # --- prose footnotes with verbatim quotes ---
        for url, title, quote in _extract_footnote_urls(content):
            items.append({"url": url, "title": title,
                          "quote": quote, "source": source_title,
                          "kind": "footnote"})

    return items


def on_pre_build(config):
    items = _collect_items()
    if not items:
        return

    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)

    # Group by URL — one fetch, one hash, multiple claims
    by_url = {}
    for item in items:
        url = item["url"]
        if url not in by_url:
            by_url[url] = {"url": url, "title": "", "quotes": []}
        if not by_url[url]["title"] and item["title"]:
            by_url[url]["title"] = item["title"]
        by_url[url]["quotes"].append(item["quote"])

    citations = []
    for url, group in sorted(by_url.items()):
        cite = {
            "id": hashlib.md5(url.encode("utf-8")).hexdigest()[:8],
            "type": "webpage",
            "URL": url,
            "title": group["title"],
        }

        entry = cache.get(url, {})
        if entry.get("checked"):
            parts = [int(x) for x in entry["checked"].split("-")]
            cite["accessed"] = {"date-parts": [parts]}
        if entry.get("content_hash"):
            cite["content-sha256"] = entry["content_hash"]

        cite["evidence"] = []
        for quote in sorted(set(group["quotes"])):
            ev = {"type": "quote-match", "quote": quote}
            if entry.get("checked"):
                ev["last-verified"] = entry["checked"]
                ev["verified-by"] = VERIFIED_BY
            cite["evidence"].append(ev)

        citations.append(cite)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(citations, f, indent=2, ensure_ascii=False)
        f.write("\n")
