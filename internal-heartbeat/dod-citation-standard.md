# DOD citation standard — design notes

Status: **scoping**. Not yet an implemented standard. This document records the
research, the options, and the proposed direction so a future session can
pick it up and implement it.

## Background

DOD's existing citation model has two mechanisms:

1. **Event quotes** (`events:` frontmatter `quote:` field) — structured YAML,
   mechanically verified by `util/check_fragments.py`, rendered with
   `#:~:text=` browser-highlight fragments at build time.
2. **Prose footnotes** — markdown footnotes with optional verbatim quoted
   excerpts, same verification pipeline and `#:~:text=` treatment (added
   August 2026, PR #142).

Both are internal conventions, not a standard any external tool can read.
Making citations machine-exportable in a standard format that reference
managers (Zotero, Pandoc) can consume would serve researchers and let us
propose a novel extension: **content-integrity verification built into
the citation itself.**

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

No academic citation standard anywhere includes:

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

## Proposed DOD citation extension

Layered on CSL-JSON with a `dod-` namespace prefix (reasonable convention:
CSL-JSON spec says unknown keys are silently ignored by processors, and
`dod-` won't collide with future CSL variable names since CSL uses
lowercase-with-hyphens, not prefixes).

### Fields

```json
{
  "type": "webpage",
  "URL": "https://theyvoteforyou.org.au/about",
  "title": "About",
  "publisher": "They Vote For You",
  "accessed": {"date-parts": [[2026, 8, 10]]},
  "archive": "Internet Archive",
  "archive_location": "https://web.archive.org/web/20260810...",
  "dod-quote": "Forget what politicians say. What truly matters is what they do.",
  "dod-content-sha256": "a1b2c3d4e5f6...",
  "dod-verified": "2026-08-10"
}
```

### Field meanings

| Field | Required | Source | Purpose |
|---|---|---|---|
| Standard CSL-JSON fields | Yes | Frontmatter `url:`, `title` | Interoperable with Zotero, Pandoc, citeproc |
| `dod-quote` | Yes | `quote:` or footnote quote | Verbatim excerpt — the evidence the citation is built on |
| `dod-content-sha256` | Optional | `_fetch_page_text()` content hash at verify time | Pins the exact page text the quote was matched against. Makes drift mechanically detectable. |
| `dod-verified` | Optional | `url_checked:` or `date of check_fragments.py` run | When the quote was last confirmed to match the live page |

### Content hash — two contexts

- **PDFs:** Hash the entire file. A PDF is a static artifact — a SHA256
  pins the exact version cited. Straightforward and unambiguous.
- **Web pages:** Hash the extracted *page text* (not the quote, not the
  raw HTML). The text is what `text_contains()` checks against, and it's
  what our cache already stores as `content_hash`. This says "this is
  the page content that existed when I verified the quote against it" —
  it makes drift detectable and is what a citation-auditing system
  actually needs.

### Why not SHA256 the quote string itself?

A quote hash tells you the quote hasn't been edited since it was written.
But it doesn't tell you whether the *source page* still says the same
thing. Hashing the page text at verification time does: if the page
changes and your pre-computed hash no longer matches, the citation has
drifted. That's the signal that matters for evidence integrity.

## Pipeline vision

1. **Author:** human writes footnote in markdown (current convention,
   unchanged)
2. **Build-time hook:** `hooks/citation_export.py` derives CSL-JSON +
   `dod-*` fields from events frontmatter + parsed footnotes, writes
   `docs/data/citations.json`
3. **Offline consumers:** Pandoc reads `citations.json` for rendering
   references; Zotero imports it into a library
4. **Verification:** `util/check_fragments.py` continues to verify quotes
   against live pages and populate `content_hash` / `verified` timestamps
   in the cache. The export hook reads from the cache to fill
   `dod-content-sha256` and `dod-verified`.

Same single-source-of-truth rule as `#:~:text=`: humans never touch the
JSON — it's always derived from the markdown and the verification cache.

## Open questions

1. **Which CSL-JSON fields are mandatory?** The spec has many optional
   fields. A minimal `webpage` citation might only need `URL`, `title`,
   `type`, and the DOD extensions.
2. **One `citations.json` per page or one aggregate file?** Per-page is
   simpler to derive (hook runs per page). Aggregate is easier to consume
   (one file for Zotero import).
3. **Zotero import library?** Zotero reads CSL-JSON via its "Import from
   clipboard" or BetterBibTeX plugin. The `dod-*` fields would survive in
   the internal database as extra fields.
4. **Relationship to `#:~:text=` fragments.** The fragment link goes in
   the rendered HTML, not in the JSON. The `dod-quote` is the data; the
   fragment is a progressive-enhancement UI feature.
5. **Do we propose this as an extension to the CSL spec?** Premature —
   get it working internally first, then see if there's community interest.

## References

- CSL-JSON schema: https://github.com/citation-style-language/schema
- CSL 1.0.2 spec: https://docs.citationstyles.org/
- W3C Verifiable Credentials v2: https://www.w3.org/TR/vc-data-model-2.0/
- RFC 7089 (Memento): https://datatracker.ietf.org/doc/html/rfc7089
- RFC 6920 (Named Information): https://datatracker.ietf.org/doc/html/rfc6920
- W3C Subresource Integrity: https://www.w3.org/TR/SRI/
- h-cite microformat: https://indieweb.org/h-cite
