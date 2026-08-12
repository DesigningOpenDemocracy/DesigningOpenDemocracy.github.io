# Machine-verifiable citation standard — design notes

Status: **implemented, two correctness gaps found in review — see "Known
issues" below**. The `hooks/citation_export.py` hook and `check_fragments.py`
verification pipeline are live. Robust Links-style archive exposure (Open
question 5) and a fuzzy-diff MISMATCH diagnostic are also implemented as of
2026-08-12 — see the updated Open question 5 entry and the Hypothes.is prior-
art note below. This document records the research, decisions, and
rationale.

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

## Known issues (found in review, 2026-08-11)

A review of PRs #142-144 after merge found two real correctness bugs —
both reproduced, not theoretical. Recorded here per this repo's
transparency convention (say what was wrong, why, and what the fix is)
before the code changes to correct them land. Filed as follow-up work,
not yet fixed as of this writing.

### 1. `paragraph_hash()` hashes the wrong paragraph on long pages

The function locates the quote's position by searching the
whitespace-*normalized* page text, then reuses that same numeric offset
to search for `\n\n` paragraph boundaries in the *original*
(non-normalized) text. `_fetch_page_text()` already collapses all
whitespace runs to single spaces before re-inserting `\n\n` delimiters,
so `normalize_ws()` on top of that shrinks each `\n\n` (2 chars) to a
single space (1 char) — a drift of exactly one character per paragraph
break preceding the quote. On a page with enough short paragraphs before
the cited sentence, the drift exceeds the length of the paragraph the
offset is supposed to land in, and the function hashes an unrelated
paragraph — one that may not even contain the quote at all. Reproduced
directly: 60 short paragraphs before a quote → the function hashes
paragraph #59, not the one with the quote.

**Fix (spec-level invariant, to guide the re-implementation):** quote
position and paragraph-boundary search must be computed against the
*same* text representation. Either locate the quote in the raw text
directly (no normalization for the position lookup itself — only for the
containment check), or normalize the whole text once up front and search
for `\n\n`-equivalent boundaries in that same normalized string. Do not
compute an offset in one representation and index into the other.

### 2. Multi-citation footnotes have no defined quote↔URL pairing

The proposed format assumes a clean 1:1 mapping between "the footnote's
quote" and "the footnote's URL." That holds for `events:` (the YAML
schema enforces one `quote:` per one `url:` by construction) but was
never actually specified for footnotes, which can cite more than one
source in a single `[^label]:` block — e.g. a primary citation with a
quote plus a secondary "see also" or corroborating source with none:

```
[^agora]: "over 155,000 members of Podemos voted online to renew the
  party leadership," ["Agora Voting/nVotes"](https://www.opendemocracy.net/...),
  openDemocracy, 4 March 2017; the Plaza Podemos participation decay
  figures are from ["Two Steps Forward, One Step Back..."](https://www.tandfonline.com/...),
  *Journal of Contemporary European Studies*, 2022.
```

This exact footnote exists in the corpus today
(`docs/blog/posts/2026-08-07-civic-tech-wave-2010s.md`) and, because the
pairing contract was undefined, three separate implementations each
guessed differently and each guessed wrong:

- `check_fragments.py::find_footnote_evidence()` pairs URLs and quotes by
  position and falls back to reusing the first quote for any extra URL —
  so it checks the Podemos-voting quote against the *unrelated* journal
  article and reports a false MISMATCH.
- `hooks/footnote_fragments.py::on_page_content()` applies the one parsed
  quote's `#:~:text=` fragment to *every* link in the footnote's rendered
  `<li>`, so the journal citation would render with a fragment for text
  that isn't on that page. Harmless in the browser (nothing highlights),
  but still wrong.
- `hooks/citation_export.py::_extract_footnote_urls()` takes only the
  *first* URL in the footnote, silently dropping the journal citation
  from `citations.json` entirely — confirmed in the actual exported file.

**Fix (spec decision):** the machine-verifiable quote convention applies
only to footnotes citing **exactly one source** (exactly one
`[Title](url)` link). A footnote citing multiple sources is treated as
citation-only — no quote is extracted for verification, fragment
rendering, or export, even if a quoted phrase is present — until it's
split into separate `[^label]` footnotes, one citation each. This is a
hard, unambiguous rule rather than a smarter pairing heuristic
(e.g. "nearest quote by clause") on purpose: a heuristic just moves the
guessing into the parser instead of removing it, and multi-source
footnotes are rare enough (9 in the current corpus, only 1 of which has
a quote at all) that requiring a split is a small, one-time content fix
rather than an ongoing parsing risk. Splitting into separate footnotes
is also better editorial practice regardless — one citation, one claim,
one label — so this isn't a compromise made purely for parser
convenience.

All three parsing implementations should share a single function (e.g.
in `util/text_fragment.py`, alongside the rest of the render/verify
machinery) that enforces this single-citation rule, rather than each
independently reimplementing footnote parsing — the three-way
inconsistency above is exactly what happens when they don't.

### Minor: cache filename doesn't match this doc

The "Two stores" table below calls the internal cache
`docs/data/evidence-cache.json`; the actual path (see
`check_fragments.py`'s `CACHE_PATH`) is
`docs/data/event-evidence-cache.json` — a naming holdover from before it
covered footnote evidence too. Not worth a migration for a committed
data file; this doc is corrected to match the code instead.

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

### Prior art (found 2026-08-11, after the fact)

The survey above covers citation *formats* — where the *what did the source
say* problem was checked against RIS, BibTeX, Schema.org, and so on, all of
which turned out not to have an answer. That was the wrong search. The
right comparison is systems that already solve *anchoring a quote of text
to a page and re-finding it later* — annotation tools and citation-
permanence services, not bibliography formats. Four are directly relevant,
and each teaches something this design should account for.

**W3C Web Annotation Data Model — `TextQuoteSelector`**
(https://www.w3.org/TR/annotation-model/#text-quote-selector). A real REC
standard for exactly this problem: `exact` (the quoted text), plus optional
`prefix`/`suffix` (surrounding context for disambiguation). This is, field
for field, what `evidence[].quote` already is, independently arrived at —
and it's also the direct ancestor of the WICG Text Fragments
`prefix-,textStart,textEnd,-suffix` syntax `make_text_fragment()` already
speaks. Two things worth taking from it:
  - **Naming**: consider whether `evidence[].quote` should become (or
    alias) `exact`, for portability with any tool that already speaks
    TextQuoteSelector, rather than DOD inventing a parallel vocabulary for
    the same concept. Not urgent — CSL-JSON extension fields are already
    non-standard, one more non-standard name doesn't cost much — but worth
    a deliberate choice rather than an accident.
  - **Its answer to ambiguity is different from ours.** The spec says: "If
    ... the user agent discovers multiple matching text sequences, then
    the selection should be treated as matching all of the matches" —
    i.e. an ambiguous quote isn't an error, it's a multi-match. DOD's
    `check_fragments.py` instead flags AMBIGUOUS as a quality problem and
    expects a human to lengthen the quote until it's unique (see
    `count_occurrences()` / the AMBIGUOUS report). This is a considered
    difference, not an oversight: TextQuoteSelector is trying to keep an
    annotation attached to *something* even under ambiguity; DOD is trying
    to prove a *specific* claim is *specifically* supported, where "matches
    all of the matches" would weaken exactly the guarantee the system
    exists to provide. Recorded here so a future reader doesn't rediscover
    this same fork and wonder why DOD didn't just copy the spec.

**Robust Links** (Herbert Van de Sompel / Memento project,
https://mementoweb.org/robustlinks/spec/). Three HTML attributes —
`data-originalurl`, `data-versionurl`, `data-versiondate` — added directly
to an `<a>` tag so a reader (or any tool parsing the page, not just ours)
can find an archived snapshot without consulting a separate JSON file.
No text-quote anchoring, no content hash — purely a document-level
pointer plus timestamp. The lesson: `--save-to-wayback` already archives
every cited URL, but the resulting archive URL only lives in the
`check_fragments.py` cache today — it never reaches the rendered page.
Emitting it as a `data-versionurl` attribute on the citation's actual
`<a href>` (or as a fourth `evidence[]`-adjacent field in `citations.json`)
would make the fallback discoverable by anyone looking at the HTML or the
export, not just someone who knows to look in the internal cache.

**Implemented 2026-08-12** (see Open question 5 below for the final design):
rather than a `data-versionurl` attribute, the archive URL is rendered as a
separate, visible archive-box (🗃️) link next to the citation — additive, not
replacing the normal citation link, matching Robust Links' own "fallback,
not primary" framing. `citations.json` gets the standard `archive` /
`archive_location` CSL-JSON fields instead of a bespoke one, since those
were already identified as the correct mapping in the "What we already
have" table above.

**Hypothes.is "fuzzy anchoring"**
(https://web.hypothes.is/blog/fuzzy-anchoring/). A production annotation
tool solving the identical "the page changed slightly, is my anchor still
good" problem, with a four-tier fallback: exact range → stored character
position → context-fuzzy match (prefix/suffix search, then diff the exact
text against a similarity threshold, using the same Myers-diff/Bitap
approach as `google-diff-match-patch`) → last-resort fuzzy full-text
search. Explicitly a *graceful-degradation* design: losing the annotation
entirely is worse than an uncertain re-anchor. This is the opposite
tradeoff from DOD's: `quote_matches()` is exact-or-nothing, and a
near-miss reports MISMATCH for a human to resolve rather than silently
accepting a fuzzy match. Both are the *right* choice for what each tool
is for — Hypothes.is is preserving a reader's UI annotation, where a
slightly-wrong position is a minor inconvenience; DOD is asserting that a
specific factual claim is specifically supported, where a fuzzy "close
enough" match would quietly undermine the one thing the system exists to
guarantee. Worth stating explicitly (as this paragraph now does) rather
than leaving the strictness undefended — it was raised as a real question
earlier in this project ("are we making this more complicated than it
needs to be by not being more forgiving of drift?") and this is the
answer, now with a concrete counter-example to point to.

**Implemented 2026-08-12, diagnostic-only:** `text_fragment.py`'s
`closest_match_hint()` uses stdlib `difflib.SequenceMatcher` (no new
dependency — same spirit as Hypothes.is's Myers-diff/Bitap approach, at a
fraction of the sophistication) to find the passage on the page most
similar to a MISMATCHed quote, and prints it alongside the MISMATCH report
("closest match on page (91% similar): ..."). This makes a broken citation
actionable — "the page now says X instead of Y" instead of a bare
not-found — without weakening the gate: the fuzzy match never counts as
verification, `quote_matches()` still decides pass/fail on exact
(whitespace-normalized) containment alone. Confirmed against the two
already-known, deliberately-unfixed mismatches in the corpus (loomio.md's
`[^loomio-wiki]`, accountability-framework's `[^theatre]` — see issue
#139): the hint correctly surfaces the rewritten Wikipedia sentence at 99%
similarity for the former, and the actual nearby (but substantively
different) passage at 62% for the latter, in both cases telling a human
reviewer exactly where to look without ever attempting to auto-resolve
either citation.

**Perma.cc** (Harvard Library Innovation Lab,
https://perma.cc/docs/perma-link-creation). The other end of the
spectrum: no text-level anchoring or verification at all — captures a
full interactive snapshot (WACZ) plus a screenshot PNG of the entire
page, and that's the citation. Used widely in legal/academic citation
(The Bluebook recommends it). The lesson is really a confirmation: DOD's
pipeline already does the equivalent of *both* ends of what these four
tools each do separately — `--save-to-wayback` is DOD's Perma.cc-style
whole-page preservation, `quote:` + `check_fragments.py` is DOD's
Hypothes.is-style specific-claim verification. Most prior art picks one;
this design deliberately does both, because they answer different
questions ("is there still *a* copy of this page somewhere" vs. "does
the page *still say* the specific thing being cited").

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
  Live web page ──→ verify quote ──→ event-evidence-cache.json         │
    (weekly cron)    still matches       (committed)              │
                                         │                       │
                                         ├── content_hash        │
                                         ├── last verified date  │
                                         ├── archive_url ────────┼──→ 🗃️ archive-box
                                         │   (--save-to-wayback)  │    link (rendered
                                         └── ETag/Last-Modified  │    HTML, additive)
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
| `docs/data/event-evidence-cache.json` | Yes | Internal | ETags, per-URL content hashes, per-quote verification booleans, plus `archive_url`/`archive_checked` when `--save-to-wayback` has run for that URL. Optimized for `check_fragments.py` to skip redundant refetches. |
| `docs/data/citations.json` | Yes | External | CSL-JSON per URL with `content-sha256` and `evidence` array. One entry per URL, multiple `evidence[].quote` entries per URL. Standard CSL processors silently ignore the non-CSL fields. |

The cache feeds the export, but they serve different consumers. An external
verifier only needs `evidence[].quote` + `content-sha256` + `last-verified`
to mechanically check whether a claim still holds — they don't need our ETags
or per-quote booleans.

### Authorship model

`citations.json` is always **derived, never authored**. Humans write markdown
footnotes. The build hook parses them and produces CSL-JSON. This means the
JSON is never hand-edited in Zotero, Pandoc, or any citation manager — those
tools *consume* it as a bibliography file, not as an input format.

This is deliberate: the machine-verifiable fields (`content-sha256`,
`evidence[].last-verified`, `evidence[].verified-by`) come from the
automated verification pipeline. If a human edits the JSON directly, those
fields lose their meaning. The markdown is the source of truth; the JSON
is a build artifact.

## Open questions

1. **Pandoc round-trip — confirmed August 2026.** `citations.json` works as a
    bibliography with `pandoc --citeproc --bibliography`. Non-CSL fields are
    silently ignored. The `id` field (MD5 of URL) resolves citation keys.
    Zotero import via BetterBibTeX remains untested.
2. **Relationship to `#:~:text=` fragments.** The fragment link goes in
    the rendered HTML, not in the JSON. `evidence[].quote` is the data; the
    fragment is a progressive-enhancement UI feature.
3. **Proposing as a CSL extension?** Premature — prove the model internally
    first, then see if there's community interest.
4. **`paragraph_hash()` and footnote quote↔URL pairing** — resolved as
    spec decisions in "Known issues" above; code changes to match are the
    next step, not yet done as of this writing.
5. **Expose the Wayback archive URL as a Robust Link — implemented
    2026-08-12.** Final design, after "all your idea makes sense, proceed"
    plus a follow-up request for a *visible* link (not just a hidden HTML
    attribute):
    - `check_fragments.py::save_to_wayback()` is now two-step: trigger a
      fresh snapshot via Save Page Now, then resolve an actually-browsable
      snapshot URL via the read-only Availability API
      (`https://archive.org/wayback/available?url=...`) — the one just
      triggered if indexing was fast enough, otherwise the most recent
      existing one. Returns that URL (or `None`), not just a
      trigger-succeeded boolean, since a 200 from `/save/` doesn't tell you
      where the snapshot actually lives.
    - The returned URL is persisted into the evidence cache as
      `archive_url` / `archive_checked`, merged into (not replacing) the
      existing per-URL entry — `check_evidence()`'s own cache write was
      also fixed to preserve those two fields across a fresh
      fetch-verification cycle, since it used to fully overwrite the entry.
    - `text_fragment.py::load_archive_urls()` reads the cache once per
      build and exposes `{url: archive_url}`. `hooks/org_events.py`
      registers it as the `archive_url_for` Jinja filter;
      `hooks/footnote_fragments.py` uses the same map directly.
    - Rendered as a visible archive-box (🗃️) link — `organisation.html`'s
      `render_event` macro puts it next to the "↗ View source" button;
      `footnote_fragments.py` inserts it right after the citation's
      `<a href>` in footnote HTML. Always **additional** to the normal
      citation link, never a replacement, per explicit instruction.
    - `hooks/citation_export.py` maps `archive_url` onto the standard
      CSL-JSON `archive` / `archive_location` fields in `citations.json`.
    - **Caveat, not yet confirmed in a real deploy:** the Save Page Now
      trigger endpoint (`web.archive.org/save/...`) returned a connection
      reset in this sandbox during development — plausibly a sandbox-
      specific network restriction rather than a real endpoint problem, but
      untested end-to-end outside the sandbox. The Availability API
      fallback was live-tested successfully (confirmed returning real
      snapshot URLs for `en.wikipedia.org/wiki/Loomio`), so the feature
      degrades gracefully even if the trigger step never works here: no
      archive link renders for a URL with no existing snapshot, rather
      than a broken one. Worth a live check on a real `--save-to-wayback`
      run outside this sandbox before relying on the trigger step.
6. **Should `evidence[].quote` be renamed/aliased to `exact`, matching
    the W3C Web Annotation Data Model's `TextQuoteSelector`?** Same
    concept, independently arrived at. Interoperability benefit is real
    but small (no other tool in this pipeline consumes that vocabulary
    yet); revisit if `citations.json` ever needs to interoperate with an
    actual annotation tool rather than just citeproc/Pandoc.

## References

- CSL-JSON schema: https://github.com/citation-style-language/schema
- CSL 1.0.2 spec: https://docs.citationstyles.org/
- W3C Verifiable Credentials v2: https://www.w3.org/TR/vc-data-model-2.0/
- RFC 7089 (Memento): https://datatracker.ietf.org/doc/html/rfc7089
- RFC 6920 (Named Information): https://datatracker.ietf.org/doc/html/rfc6920
- W3C Subresource Integrity: https://www.w3.org/TR/SRI/
- h-cite microformat: https://indieweb.org/h-cite
- W3C Web Annotation Data Model, TextQuoteSelector: https://www.w3.org/TR/annotation-model/#text-quote-selector
- Robust Links specification (Memento project): https://mementoweb.org/robustlinks/spec/
- Hypothes.is fuzzy anchoring: https://web.hypothes.is/blog/fuzzy-anchoring/
- Perma.cc documentation: https://perma.cc/docs/perma-link-creation
- Wayback Machine Availability API: https://archive.org/help/wayback_api.php
