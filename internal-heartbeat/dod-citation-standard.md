# DOD citation standard — design notes

Status: **implemented**. The `hooks/citation_export.py` hook and
`check_fragments.py` verification pipeline are live. This document records
the research, decisions, and rationale.

## Goal

A practical enhancement to web citation that anyone can adopt — not
university-only, not DOD-only. A blog, news site, or personal wiki that
ships a `citations.json` alongside its content gives readers mechanical
verification: the author's claim, the page text it matched at the time,
and a link to an archived copy. No academic infrastructure required.

The format is standard CSL-JSON plus a handful of extension fields for
content integrity. Our own pipeline happens to be the reference
implementation, but the standard is designed to stand alone.

## What we already have

DOD's existing citation model has two mechanisms that map directly onto
the proposed standard:

1. **Event quotes** (`events:` frontmatter `quote:` field) — structured YAML,
   mechanically verified by `util/check_fragments.py`, rendered with
   `#:~:text=` browser-highlight fragments at build time.
2. **Prose footnotes** — markdown footnotes with optional verbatim quoted
   excerpts, same verification pipeline and `#:~:text=` treatment (added
   August 2026, PR #142).

Both are internal conventions. The standard makes them exportable.

## Research findings

### CSL-JSON — the base standard

CSL (Citation Style Language) is the lingua franca of reference managers.
CSL-JSON items are plain JSON objects consumed by Zotero, Pandoc, citeproc,
and Jupyter Book. The `webpage` type already covers the basics:

| CSL variable | Meaning | We already have this |
|---|---|---|
| `URL` | Resource URL | `url:` |
| `accessed` | Date retrieved | `url_checked:` |
| `archive` | Archive name | `--save-to-wayback` targets IA |
| `archive_location` | Archived URL | Memento concepts map here |
| `note` | Free text | `note:` / `quote:` fields |

### Gaps — no standard covers content integrity

After surveying CSL-JSON, Memento, Schema.org, h-cite, BibTeX, RIS, and
the W3C Verifiable Credentials model: no existing standard attaches a
mechanically-verifiable claim to a citation. Every standard tells you
*where* to find the source and *when* you accessed it. None tell you
*what* the source said and how to *check* if it still says it.

Specifically, no academic citation standard anywhere includes:

- A **verbatim quote excerpt** from the cited source
- A **content hash** of the retrieved page at verification time
- A **verified date** recording when the quote was last confirmed

These are genuinely novel additions that would make a citation
verifiable without manual re-reading. The W3C Verifiable Credentials
data model (https://www.w3.org/TR/vc-data-model-2.0/) is conceptually
aligned — issuer makes a claim about a subject with timestamped proof —
but its implementation weight (DIDs, JSON-LD signatures, revocation
registries) is designed for multi-party trust frameworks, not a
single-verifier wiki pipeline.

### Standards surveyed and ruled out

| Standard | Why not |
|---|---|
| **Memento (RFC 7089)** | Retrieval protocol, not a citation format. Covers datetime negotiation but not content hash or quote. |
| **Schema.org `ScholarlyArticle`** | Has `archivedAt` but no access-date, no quote, no hash. |
| **h-cite microformat** | Has `dt-accessed` (the only one that does), but only 8 properties total. No hash, no archive URL. |
| **RFC 6920 `ni://` URIs** | Content-addressed URIs with hash algorithm + digest. Relevant as a hash standard, but not a citation format on its own. |
| **W3C SRI** | `sha256-abc123` integrity attribute. Hash format to adopt, but citation-specific. |
| **BibTeX** | LaTeX-world, text-based, big ecosystem but fewer web citation fields. |
| **RIS** | Simplest, most portable, but no extension mechanism and no standard place for a quote. |
| **WebCite** | Commercially dead. |

## Proposed format

Layered on CSL-JSON. The `evidence` array groups per-claim data under
each URL — multiple quotes citing the same page share one hash, one
access date, and are deduplicated into the array.

```json
{
  "type": "webpage",
  "URL": "https://en.wikipedia.org/wiki/MySociety",
  "title": "mySociety",
  "accessed": {"date-parts": [[2026, 8, 11]]},
  "content-sha256": "abc123...",
  "evidence": [
    {
      "type": "quote-match",
      "quote": "mySociety was founded by Tom Steinberg in September 2003",
      "last-verified": "2026-08-11",
      "verified-by": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
    },
    {
      "type": "quote-match",
      "quote": "TheyWorkForYou is a parliamentary monitoring website",
      "last-verified": "2026-08-11",
      "verified-by": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
    }
  ]
}
```

### Field meanings

**URL-level fields** (one per cited page):

| Field | Source | Purpose |
|---|---|---|
| Standard CSL-JSON | Frontmatter `url:`, `title` | Interoperable with Zotero, Pandoc, citeproc |
| `content-sha256` | Evidence cache | Fingerprint of the page text at last verification. Shared by all claims on this URL. Changed → open review ticket, human checks framing. |

**Per-claim fields** (one entry per quote, nested under `evidence`):

| Field | Source | Purpose |
|---|---|---|
| `type` | Always `"quote-match"` today | Evidence kind. Extensible: `screenshot`, `pdf-page`, `timestamp` in future. |
| `quote` | `quote:` or footnote quote | Verbatim excerpt. Gate tier — must match weekly to keep the citation green. |
| `last-verified` | Evidence cache `checked` | When this quote was last confirmed to match the live page. |
| `verified-by` | Verifier identity string | Present = mechanically verified, absent = human claim. The value identifies the tool that checked it (e.g. "DOD-Bot/1.0") — a reader can reproduce the check with the same method.

### Two tiers of integrity

| Tier | Field | What it catches | Action |
|---|---|---|---|
| **Gate** | `evidence[].quote` | Quote no longer matches source → citation broken | Fail build, fix or remove |
| **Review** | `content-sha256` | Hash changed but quotes survived → page was edited around the claims | Open review ticket, human checks framing |

A reader or bot checking `citations.json` knows the difference between "this
citation is dead" (quote mismatch) and "this page was edited, the cited
sentences are intact, but you should re-read the surrounding paragraph"
(hash changed, quotes survived). The hash is not a pass/fail check — it
feeds a review queue, not a CI gate.

### Content hash

- **PDFs:** Hash the entire file. A PDF is a static artifact — a SHA256
  pins the exact version cited. Straightforward and unambiguous.
- **Web pages:** Paragraph-scoped. Block-level HTML tags are replaced
  with `\n\n` paragraph delimiters during text extraction, then the
  paragraph containing the matching quote is located and hashed. Immune
  to nav/ads/timestamp changes elsewhere — only the paragraph the
  citation lives in matters. Implemented via `_fetch_page_text()` sentinel
  substitution and `paragraph_hash()` in `util/check_fragments.py`.
  (Previously: whole-page hashing — fragile to page furniture changes.)

### Why not SHA256 the quote string itself?

A quote hash tells you the quote hasn't been edited since it was written.
But it doesn't tell you whether the *source page* still says the same
thing. Hashing the page text at verification time does: if the page
changes and your pre-computed hash no longer matches, the citation has
drifted. That's the signal that matters for evidence integrity.

## Pipeline vision

### Data flow

```
                         INTERNAL                                │  PUBLIC
                                                                 │
  Markdown footnotes ──┐                                         │
    [^ref]: "quote,"   │  hooks/citation_export.py               │
    [Title](url)       ├──→ citations.json ──→ readers,          │
                       │      (CSL-JSON)       Zotero, Pandoc    │
  Events frontmatter ──┘                                         │
    quote: "..."                                                 │
    url: https://...                                             │
                                                                 │
                         check_fragments.py                      │
  Live web page ──→ verify quote ──→ evidence-cache.json         │
    (weekly cron)    still matches       (committed)              │
                                         │                       │
                                         ├── content_hash        │
                                         ├── last verified date  │
                                         └── ETag/Last-Modified  │
                                            (internal only)      │
                                                                 │
                                          citation_export.py      │
                                          reads cache, writes ───→
                                          content-sha256
                                          evidence[].last-verified
                                          evidence[].verified-by
```

### Two stores, two purposes

| Store | Committed? | Audience | Content |
|---|---|---|---|
| `docs/data/evidence-cache.json` | Yes | Internal | ETags, per-URL content hashes, per-quote verification booleans. Optimized for `check_fragments.py` to skip redundant refetches. |
| `docs/data/citations.json` | Yes | External | CSL-JSON per URL with `content-sha256` and `evidence` array. One entry per URL, multiple `evidence[].quote` entries per URL. Standard CSL processors silently ignore the non-CSL fields. |

The cache feeds the export, but they serve different consumers. An external
verifier only needs `evidence[].quote` + `content-sha256` + `last-verified`
to mechanically check whether a claim still holds — they don't need our ETags
or per-quote booleans.

## Open questions

1. **Zotero round-trip.** Zotero reads CSL-JSON via its "Import from
    clipboard" or BetterBibTeX plugin. The non-CSL fields (`content-sha256`,
    `evidence`) should survive as extra fields — needs testing.
2. **Relationship to `#:~:text=` fragments.** The fragment link goes in
    the rendered HTML, not in the JSON. `evidence[].quote` is the data; the
    fragment is a progressive-enhancement UI feature.
3. **Proposing as a CSL extension?** Premature — prove the model internally
    first (a working wiki with verifiable citations), then see if there's
    community interest. The schema is already clean enough to stand alone
    without a namespace prefix.

## References

- CSL-JSON schema: https://github.com/citation-style-language/schema
- CSL 1.0.2 spec: https://docs.citationstyles.org/
- W3C Verifiable Credentials v2: https://www.w3.org/TR/vc-data-model-2.0/
- RFC 7089 (Memento): https://datatracker.ietf.org/doc/html/rfc7089
- RFC 6920 (Named Information): https://datatracker.ietf.org/doc/html/rfc6920
- W3C Subresource Integrity: https://www.w3.org/TR/SRI/
- h-cite microformat: https://indieweb.org/h-cite
