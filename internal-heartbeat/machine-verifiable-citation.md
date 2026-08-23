# Machine-verifiable citation — standard

A citation format that tells you what the source said and how to check if it still says it. Ships as a `citations.json` alongside your content. No academic infrastructure required.

## Why this exists

Every existing citation format tells you *where* to find a source and
*when* you accessed it — a URL, a DOI, an access date. None of them tell
you *what the source actually said*, or give you a mechanical way to
check whether it still says it (see Appendix A's standards survey — this
is a real gap, not an oversight in the formats surveyed). A citation is
usually a trust-me link: correct the day it was written, then silently
rotting afterward as pages get edited, moved, or taken down, with
nothing to signal the drift to a reader and no way for a publisher to
catch it at scale beyond re-reading every citation by hand.

This format closes that gap with one addition layered on standard
CSL-JSON: an `evidence` array carrying the verbatim quote a claim
actually rests on, plus enough metadata — a status, a content hash, a
verification date — for a script to re-check that quote against the
live page and report, mechanically, whether the citation still holds.

This isn't a proposal in the abstract. DOD runs it today across 336
cited pages and 443 evidence entries, re-verified on a weekly schedule
(`check_fragments.py`), and this document is the working record of
building it — including the real failure modes that showed up doing so
and how they were fixed (Appendix C), and the ones still open (Appendix
B's "DOD-specific notes"). See Appendix A for what else was surveyed and
ruled out, Appendix B for the reference implementation and its numbers.

## Format

Layered on standard CSL-JSON. The `evidence` array groups per-claim data
under each URL. Standard processors (Zotero, Pandoc, citeproc) ignore
unknown fields and consume the item normally; a *strict schema
validator* will reject it, since `csl-data.json` sets
`additionalProperties: false` — a deliberate tradeoff, see Appendix D.

```json
{
  "id": "b5e1a04c9d2f7318e6c0a45b8f1d93e27a6c4051d8b3f9e2c7a0d64185b3f2c9",
  "convergence": {"sha256": "b5e1a04c9d2f7318e6c0a45b8f1d93e27a6c4051d8b3f9e2c7a0d64185b3f2c9"},
  "type": "webpage",
  "URL": "https://en.wikipedia.org/wiki/MySociety",
  "title": "mySociety",
  "accessed": {"date-parts": [[2026, 8, 12]]},
  "archive": "Internet Archive Wayback Machine",
  "archive_location": "https://web.archive.org/web/20260812123456/https://en.wikipedia.org/wiki/MySociety",
  "evidence": [
    {
      "id": "7f3a9c2e1b4d6f80c3e5a1b9d2f4680e91c7a3b5d0f2e4c6a8b0d2f4e6a8c0e2",
      "convergence": {"sha256": "7f3a9c2e1b4d6f80c3e5a1b9d2f4680e91c7a3b5d0f2e4c6a8b0d2f4e6a8c0e2"},
      "type": "quote-match",
      "quote": "mySociety was founded by Tom Steinberg in September 2003",
      "last-verified": "2026-08-12",
      "verified-by": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)",
      "status": "MATCH",
      "context": {
        "text": "mySociety was founded by Tom Steinberg in September 2003 and started with TheyWorkForYou, a parliamentary monitoring website that makes it easy for people to keep tabs on their elected representatives.",
        "prefix": "mySociety is a UK-based not-for-profit social enterprise,",
        "suffix": "and started with TheyWorkForYou, a parliamentary monitoring website.",
        "sha256": "9c1185a5c5e9fc54612808977ee8f548b2258d31ddcae9e3a3e9e0b1f2c4d7a6"
      }
    }
  ]
}
```

### Field meanings

**URL-level fields** (one per cited page):

| Field | Purpose |
|---|---|
| `id` | Standard CSL-JSON citation key. `sha256(URL)`, full 64-char lowercase hex for DOD's own implementation — see "Identifier construction" for why another implementation may generate this differently. |
| `convergence` | DOD extension, a wrapper object (mirrors `evidence[].context`'s shape: the wrapper names what's hashed and why, the value inside says how). `{"sha256": "<sha256(URL)>"}`, full 64-char lowercase hex. Always present, even though it is byte-identical to `id` in DOD's own file — see "id vs the sha256 field". |
| Standard CSL-JSON (`type`, `URL`, `title`, `accessed`, `archive`, `archive_location`) | Interoperable with Zotero, Pandoc, citeproc. `archive`/`archive_location` are standard CSL fields — a Wayback Machine snapshot (or equivalent) of the page at the time it was cited, so a reader can inspect what the citation originally pointed to even if the live page has changed or disappeared. |
| `url-status` | DOD extension. `dead` \| `unfit`; absent means live. Set by hand, never inferred — a parked domain returns HTTP 200, so this is not machine-detectable. |

**Per-claim fields** (one entry per quote, nested under `evidence`):

| Field | Required? | Purpose |
|---|---|---|
| `id` | No | Identifier for *this specific evidence entry*, for DOD's own implementation `sha256(normalize(quote))`, full 64-char lowercase hex — see "Identifier construction". Addressable from outside the file (a URL's `evidence` array can hold several quotes, so the URL alone doesn't identify a claim). |
| `convergence` | Yes | DOD extension, same wrapper shape as the item-level field above. `{"sha256": "<sha256(normalize(quote))>"}`, full 64-char lowercase hex. Always present alongside `id`, even when byte-identical to it — self-verifying (recompute from the quote to confirm the pointer and text still agree) and the value any implementation must compute identically to answer "same underlying fact." Not the same thing as `context.sha256` below: this hashes the quote alone; `context.sha256` hashes the surrounding span. See "id vs the sha256 field". |
| `type` | Yes | Evidence kind. `"quote-match"` for web-page text verification. Extensible: `screenshot`, `pdf-page`, `timestamp`. |
| `quote` | Yes | Verbatim excerpt from the source. Gate tier — must match the live page to keep the citation green. |
| `last-verified` | No | ISO date of last confirmation that `quote` matched the live page. |
| `verified-by` | No | Identity string of the verifier (e.g. `"DOD-Bot/1.0"`). Present = mechanically verified, absent = human claim. |
| `status` | No | `"MATCH"` (confirmed on page), `"MISMATCH"` (no longer present — citation broken), `"AMBIGUOUS"` (found but not unique — add `context` to disambiguate). Absent = not yet verified. |
| `context` | No | Disambiguation anchor. Any combination of these optional fields: |

**`context` fields** (all optional, any subset valid):

| Field | Purpose |
|---|---|
| `text` | Full paragraph or section containing the quote. Simplest form — hash it, substring-check `quote in text`. |
| `prefix` | Text immediately before the quote. Matches W3C TextQuoteSelector `prefix` and `#:~:text=prefix-` fragment syntax. |
| `suffix` | Text immediately after the quote. Matches W3C TextQuoteSelector `suffix` and `#:~:text=-suffix` fragment syntax. |
| `sha256` | SHA-256 of the context span. Computed over `text` if present (most authoritative), otherwise `prefix + quote + suffix`. |

A verifier extracts the same span from the page, hashes it, and compares.
Different hash + same quote → page was edited around the claim (review
signal, not failure). All fields absent → the quote is unique enough to
anchor itself without context.

### Naming and value conventions

This is a machine-read format; consumers compare these strings exactly,
so the conventions are normative, not cosmetic.

- **Field names.** Standard CSL-JSON names are inherited verbatim,
  including `archive_location`'s underscore — that is CSL's own
  inconsistency and not ours to correct. New DOD extension fields are
  lowercase, hyphen-separated (`url-status`).
- **Enumerated values** are lowercase, hyphen-separated: `webpage`,
  `quote-match`, `dead`, `unfit`.
- **Hex digests** are lowercase; see "Identifier construction".

**One known violation, flagged rather than silently tolerated:**
`evidence[].status` uses uppercase (`MATCH` / `MISMATCH` / `AMBIGUOUS`)
against every rule above. It reads as console output that leaked into
the data model — those are exactly the strings DOD's verifier prints.
The case for normalizing it to `match` / `mismatch` / `ambiguous` is
unusually strong *right now*: no published entry carries the field at
all (see Appendix B, "Specified but unpopulated"), so there is currently
nothing to break, and that stops being true the moment anything writes
it. The case against is that `util/citations_tool.py` also reads
third-party `citations.json` files, so the value vocabulary is not
purely DOD's to redefine. Unresolved — deliberately recorded here rather
than changed in passing.

### Identifier construction

Both `id` fields are content-derived hashes in DOD's own implementation,
constructed the same way `convergence.sha256` always is (see "id vs the
sha256 field" below for why the two coincide here but aren't the same
concept):

| Field | Hash input |
|---|---|
| item `id` / `convergence.sha256` | the item's `URL`, verbatim |
| `evidence[].id` / `evidence[].convergence.sha256` | the evidence `quote`, normalized (below) |

Normative rules for both:

- **SHA-256**, hex-encoded, **lowercase**, **full 64 characters**, input
  encoded as **UTF-8**.
- **Never truncated in the file.** A stored short form bakes a
  truncation decision into the canonical identity with no way back to a
  longer one. Truncate only where a named cost actually scales with
  length — in this whole design that is exactly one place: the
  `evidence_sha256` prefix inside a COinS span (Appendix E), which ships in
  HTML to every visitor on every page load. Resolve a short form by
  prefix match against the full id, the way Git resolves an abbreviated
  commit hash — Git likewise never truncates what it *stores*, only what
  it displays.
- Consumers may abbreviate for display. That is a rendering choice and
  carries no meaning in the data.

#### Quote normalization

`evidence[].id` hashes a *normalized* quote so that two parties holding
the same quote agree on the same id. The normalization is part of the
format: an implementation that skips it computes different ids for
identical evidence, which defeats the purpose. Applied in this order:

1. Remove whitespace immediately following `(`.
2. Collapse every run of whitespace to a single space (U+0020); strip
   leading and trailing whitespace.
3. Remove whitespace immediately preceding `)`.

DOD's implementation is `normalize_ws()` in `util/text_fragment.py`.

**Known wart, flagged rather than hidden:** rules 1 and 3 exist to
absorb an artifact of *one* HTML-to-text extractor — DOD's
`html_to_text()` renders `(<i>N</i> = 5734)` as `( N = 5734)` at
inline-tag boundaries. That is a reasonable tolerance when *matching* a
quote against page text, but here it does double duty as part of an
*identity*, where a lossy rule justified by a single implementation's
quirk is harder to defend. It is specified explicitly, rather than left
implicit in DOD's code, so an independent implementer can reproduce
these ids exactly. Separating the matching normalization from the
identity normalization is the first thing to revisit if this format is
adopted elsewhere — it would change every `evidence[].id`, so it is not
a change to make casually.

#### Why a content hash, not a UUID

`citations.json` is regenerated from source on every build and carries
nothing forward from its own prior output. A hash reproduces identically
with zero persisted state. A random UUID would mint a new id for
unchanged evidence on every rebuild, breaking any external reference to
it; making one stable would require persisting an id registry, which
reintroduces exactly the second-writer drift this pipeline already
removed once (Appendix C, 2026-08-22). A hash is also self-verifying,
and it *converges*: two independently-run sites citing the same quote
compute the same id with no coordination — the property a format meant
to span separate citation databases actually needs.

Centrally-allocated bibliographic identifiers (DOI, ISBN, ORCID) are not
a counter-example: they name mutable *works* — editions, formats, items
minted before final content exists — so there is no canonical byte
string to hash, and their real product is registry-backed resolution
rather than identity. Different problem.

#### `id` vs `convergence.sha256`: what's normative, what's implementation choice

The reasoning above is DOD's own justification for its own choice —
making `id` itself content-derived. That choice bundles two properties
into one field for free: self-verification (recompute from the quote,
compare) and the cross-site convergence just described. Both hold *only
because* `id` here happens to be a pure content hash — they are not the
same requirement in general, and conflating them stops working the
moment `id` isn't content-derived.

That can legitimately happen: a content-hash-based `id` changes on any edit
to the quote — a typo fix, a lengthened excerpt to disambiguate an
`AMBIGUOUS` match — with no forwarding path, because it has no notion of
"the same claim, re-transcribed." An implementation that needs a
citation instance to survive that kind of routine copy-edit (for a
stable pointer *into* it, like `evidence_sha256` in Appendix E, or its own
internal referencing) needs `id` to instead be a persisted, publisher-
local key, assigned once and carried forward independent of the quote's
current wording. Both are legitimate engineering choices for what `id`
*is*, and — same as CSL-JSON's own `id` already works across Zotero,
BetterBibTeX, and Pandoc today, with zero expectation that two libraries
agree on a value for "the same" reference — this format does not mandate
one. **How a program chooses to generate and store `id` is its own
business.**

What isn't optional, if this format is to mean anything across
independently-run sites, is a way to answer "are these two citations —
possibly with different local `id`s, possibly even differently excerpted
— pointing at the same underlying fact?" That question needs one
deterministic, content-derived value every implementation computes the
same way, which is what `convergence.sha256` is for:

- `convergence` = `{"sha256": "<sha256(normalize_ws(quote))>"}`, full
  64-char lowercase hex inside a wrapper object — identical hash
  construction to `id` above.
- **Always present, on every entry, regardless of what `id` is.** Even
  when `id` is already content-derived and `convergence.sha256` would be
  a byte-identical duplicate — DOD's own case — it is emitted anyway
  rather than omitted as "redundant." A conditional presence rule ("only
  emit this when it differs from `id`") pushes a branch onto every
  consumer, who now has to check whether `convergence` exists before
  knowing which field actually answers the convergence question. A
  uniform schema — the field is simply always there — costs a duplicated
  64-char string per entry and buys every consumer one less thing to get
  wrong. Same judgment already applied to truncation above: optimizing
  away a few bytes is not worth it in a JSON export with no byte-budget
  pressure.

DOD's own `citations.json` needs no logic change for this beyond emitting
the field: `id` already equals what `convergence.sha256` computes, so
the two values are simply written side by side. This section exists so
a future implementation choosing a non-content-derived `id` still has a
specified, mandatory field to populate, without this document silently
assuming its own default is the only valid choice.

**Why it's a wrapper object, named after its algorithm inside, not a
flat purpose-named field.** `id` is opaque by design — a consumer only
ever compares it for equality, never recomputes it, so it has no need to
declare how it was generated. This field is the opposite kind of value —
its entire job is "recompute this from the current content and check it
still matches," which is meaningless unless the field itself says which
algorithm to use. And it's a wrapper (`convergence`) with the algorithm
named inside (`sha256`) rather than a flat field, because that's the
exact shape `evidence[].context` already uses a few paragraphs up: the
wrapper says *what's being hashed and why*, the value inside says *how*.
Consistent naming avoids a real failure mode: if this format, or an
adopter of it, ever needs a second algorithm — a migration, a stronger
hash, a per-quote choice — it becomes a sibling key (`convergence.blake3`,
say) inside the same wrapper, rather than forcing either a second
top-level field or an ambiguous flat field that can no longer be trusted
to mean one specific thing. (See Appendix C for how this field's shape
evolved — a flat `convergence-id`, then a flat `sha256`, before settling
here; the history isn't repeated in this section.)

**A hash of the URL and a hash of the cited content are different
things, and this format currently only standardizes the former.** The
item-level `convergence.sha256` hashes the *URL* — it identifies the
citation entry, and says nothing about what is actually at that address;
a page can be rewritten completely underneath an unchanged URL and this
field never notices, by design, since verifying content is
`evidence[].quote`/`status`'s job. For an HTML page that split is
correct: the page is a living document, and only a specific excerpt is
being verified, not the whole thing. A fixed, downloaded artifact — a
PDF, a `.docx` — is a different case: the *whole file* is normally
immutable once published, so a hash of its complete bytes would be a
real, currently-missing signal ("has this exact file changed at all,"
categorically stronger than "does this substring still appear in its
extracted text"). `check_fragments.py` already extracts PDF/`.docx` text
via pdfminer/zip-XML and quote-matches it exactly like an HTML page (see
`util/check_fragments.py`'s entry in `CLAUDE.md`) — there is no
whole-file hash computed anywhere in this pipeline today. This also
turned up a documentation bug: `CLAUDE.md`'s Data exports table
described `/data/citations.json` as having "per-URL entries with
`content-sha256`" — no such field has ever existed in
`citation_export.py`'s output, and nothing in the codebase ever computed
one. Corrected 2026-08-23 to describe the fields the export actually
carries (`id`/`convergence.sha256` at both levels), with the
still-unpopulated verification fields called out as such.

**If this is ever built, it's an integrity signal, not an identity one —
and it needs its own name.** A whole-file hash answers "have this exact
file's bytes changed since I last looked": integrity/drift, the same
*axis* as `context.sha256`, not identity/agreement like `convergence`.
Convergence doesn't need it — URL plus normalized excerpt already fully
identifies "the same claim" for a PDF exactly as for an HTML page, since
`check_fragments.py` quote-matches extracted PDF text the same way it
does rendered HTML. In the signal map above it fills exactly one empty
cell: **resource-level review-tier integrity**, sitting at the item level
(a property of the whole cited resource, not of one quote), sibling to
`archive`/`url-status`.

**Naming: `document.sha256`, not `context.sha256`.** An earlier revision
of this note proposed a top-level `context: {...}` — wrong, and worth
recording as a near-miss rather than silently fixing, since it's the
same class of error this document has corrected twice already
(`convergence-id` vs `sha256`, flat vs wrapper). `evidence[].context`
already means "the text surrounding the quote"; reusing `context` at the
item level for "the whole document's bytes" would put two different
concepts behind one word at two different levels — precisely the
ambiguity the wrapper-naming convention exists to prevent. The wrapper
should name *what is hashed*: at claim level that's the surrounding
`context`; at resource level it's the `document` itself. `content` was
considered — it would retroactively justify `CLAUDE.md`'s phantom
`content-sha256` reference — and rejected: one letter from `context`,
at adjacent levels of the same structure, is a confusion waiting to
happen in exactly the code that has to tell them apart.

**Built 2026-08-23.** `check_fragments.py`'s `check_evidence()` computes
`sha256(text)` unconditionally on every successful fetch and stores it
as `document_sha256`; `citation_export.py` projects it as item-level
`document.sha256`, exactly the `archive_url` pattern. One deviation from
the sketch above, made deliberately rather than silently: `text` here is
the already-*extracted* plain text `quote_matches()`/`paragraph_hash()`
operate on, not the raw pre-extraction bytes this note originally
proposed hashing. Raw bytes would flag markup-only edits — a script tag
changed, an `alt` attribute tweaked, whitespace reflowed — as resource
drift, which is exactly the false-positive-review-signal problem already
flagged for a hypothetical section-wide `context` hash. Hashing the same
extracted text every other check in this pipeline already operates on
keeps this signal consistent with the rest of the format: it fires when
the visible content changes, not when the markup around it does.

This replaced a field named `content_hash` that turned out to be
computing something else entirely and was never read anywhere — see
`check_evidence()`'s docstring for the full account. Measured on the
real corpus: **0 of 336 items carry `document.sha256` yet**, not a bug —
the committed cache still holds the old field name on 322 entries, and
it self-heals the same way `PAGE_TOO_SHORT` does elsewhere in this
pipeline: the next scheduled `check_fragments.py` run that successfully
re-fetches a URL writes the new key, no backfill script needed.

#### The id is not an anti-spoofing mechanism

It is public and copyable, like a URL or a DOI. What has to hold up
under scrutiny is the record it resolves to, and that record is only
ever written by the publisher's own build pipeline. A third party can
quote a real id next to a claim it doesn't support, exactly as they can
misuse a real URL — id length changes nothing about that, and nothing
here tries to solve it. The trust boundary is who can write
`citations.json`.
### Content hash

`context.sha256` pins the evidence to a specific span of source text.
A verifier re-fetches the page, extracts the same span, and compares
hashes. If the hash changed but the quote still matches, the page was
edited *around* the claim — a review signal, not a failure.

The `sha256` is computed over `context.text` directly (paragraph form)
or `prefix + quote + suffix` concatenated (prefix/suffix form).
Plain-text substring slices — no HTML parsing needed.

### Signal map: identity × integrity, at two levels

Every field in this format answers one of two questions, at one of two
levels. Laying them out this way is not decoration — it is what makes it
obvious when a signal exists but nothing consults it (see the MISMATCH
gap in Appendix B, which is exactly a populated cell being ignored by
code that only reads the row above it).

| Level | **Identity** — "what is this?" | **Integrity, gate** — "is the citation broken?" | **Integrity, review** — "did something shift around it?" |
|---|---|---|---|
| **Resource** (item) | `convergence.sha256` = hash of `URL` | `url-status`: `dead` \| `unfit` | `document.sha256` = hash of extracted page text |
| **Claim** (`evidence[]`) | `convergence.sha256` = hash of normalized `quote` | `status`: `MISMATCH` | `context.sha256` = hash of containing paragraph |

All cells but one are populated in the published export as of
2026-08-23; see "Verification fields" in Appendix B for what projecting
them cost and which entries still lack a verdict.

**Identity fields are names, not checks.** They never change because a
page changed — only because the thing being named changed. They're what
lets two independently-run implementations agree they're talking about
the same resource or the same claim.

**Integrity fields are checks**, and they come in two severities:

- **Gate** — the citation is broken; fix or remove it. A `MISMATCH`
  means the cited sentence is no longer on the page. A `url-status` of
  `dead`/`unfit` means the resource itself is gone or replaced.
- **Review** — the cited thing survived, but its surroundings moved.
  Not a failure; a prompt for a human to check whether the framing still
  supports the claim. `context.sha256` changing while `quote` still
  matches is the canonical case: the page was edited *around* the claim.

A reader or bot checking `citations.json` can therefore distinguish
"this citation is dead" from "this page was edited but the cited
sentence is intact" — and, with the level axis, distinguish *which*
level died: the whole resource, or one claim within a resource that is
otherwise perfectly healthy.

**The map had one empty cell — resource-level review — filled
2026-08-23.** Before that, resource integrity had only a coarse,
hand-set gate (`url-status`) and no fine, machine-computed review
signal, while claim integrity had both. That asymmetry meant a document
whose content changed wholesale could pass every check this format ran,
so long as the one cited sentence survived the edit. See "A hash of the
URL and a hash of the cited content are different things" above for
`document.sha256` and why it belongs on this axis rather than under
`convergence`.

## Minimal viable implementation

The format is designed for **produce → augment → verify**. A human
writes the essentials. A tool fills in mechanical proof. Anyone
re-fetches later and confirms whether the citation still holds.

### 1. Produce (by hand)

Start with the essentials — an augmenter tool can fill in the rest.

1. For each citation, write `URL`, `title`, and at least one evidence
   entry with `type: "quote-match"` and `quote`.
2. Write the array as `citations.json`.

Fields a tool will add later: `accessed`, `archive`, `archive_location`,
`status`, `last-verified`, `verified-by`, `context`.

### 2. Augment (by tool)

An augmenter reads an existing `citations.json`, fetches each cited
page, and writes back the mechanical verification fields.

1. For each URL, fetch the page and extract plain text (strip HTML tags,
   collapse whitespace).
2. For each evidence entry: check `quote in page_text` (whitespace-
   normalized). Set `status` to MATCH, MISMATCH, or AMBIGUOUS.
3. If the quote matches: optionally extract context around it —
   `context.text` (the containing paragraph), `context.prefix`/`suffix`
   (N chars before/after), or both. Compute `context.sha256`.
4. Optionally: archive the page (Wayback Machine, Perma.cc, etc.) and
   record `archive` + `archive_location`.
5. Record `accessed`, `last-verified`, and `verified-by`.
6. Write back the enriched `citations.json`.

### 3. Verify (by anyone)

Re-run the checks to confirm whether the citation still holds up today.

1. For each URL, fetch the page and extract plain text.
2. For each evidence entry: check `quote in page_text`. Compare
   `status` against what the augmenter claimed.
3. If `context` is present: re-extract the span (`text` if present,
   otherwise `prefix + quote + suffix`), SHA-256 it, compare against
   `context.sha256`.
4. Different hashes → the page changed. Same quote with different
   surrounding text → possible framing drift. Flag for human review.

A verifier does not need the `verified-by` or `last-verified` from the
original — it produces its own. Those fields exist so a reader doesn't
have to run a verifier to know when the last check was.

---

## Appendix A: Design rationale

### Why CSL-JSON

CSL (Citation Style Language) is the lingua franca of reference
managers. CSL-JSON items are plain JSON consumed by Zotero, Pandoc,
citeproc, and Jupyter Book. The `webpage` type covers URL, title,
accessed date, and archive location. Standard processors ignore
non-CSL fields — the `evidence` array and its children don't break
existing tooling.

### Standards surveyed and ruled out

| Standard | Why not |
|---|---|
| **Memento (RFC 7089)** | Retrieval protocol, not a citation format. |
| **Schema.org `ScholarlyArticle`** | Has `archivedAt` but no access-date, no quote, no hash. |
| **h-cite microformat** | Has `dt-accessed` (the only one that does), but only 8 properties total. |
| **RFC 6920 `ni://` URIs** | Content-addressed URIs — relevant hash standard, not a citation format. |
| **BibTeX / RIS** | No extension mechanism, no standard place for a quote. |
| **W3C Verifiable Credentials** | Conceptually aligned but heavy (DIDs, JSON-LD signatures) — designed for multi-party trust, not a single-verifier wiki pipeline. |

No existing standard attaches a mechanically-verifiable claim to a
citation. Every format tells you *where* to find the source and *when*
you accessed it. None tell you *what* the source said and how to
*check* if it still says it.

### Prior art

**W3C TextQuoteSelector** (`exact`, `prefix`, `suffix`) — a REC standard
for exactly the quote-anchoring problem, independently arrived at in
this design. `evidence[].quote` maps to `exact`, `context.prefix`/`suffix`
map directly. Its answer to ambiguity ("match all matches") differs from
ours ("flag ambiguous, lengthen quote until unique") — a considered
difference: TextQuoteSelector preserves annotations under ambiguity;
we're proving specific claims, where "matches all matches" weakens the
guarantee.

**Hypothes.is fuzzy anchoring** — four-tier fallback (exact → position →
context-fuzzy → full-text search) for re-anchoring annotations after
page edits. Deliberately different from our exact-match gate: their
priority is not losing an annotation; ours is not silently accepting a
drifted citation. Our `closest_match_hint()` diagnostic (diff-based
"the page now says X instead of Y") makes mismatches actionable without
auto-resolving them.

**Robust Links** (Memento project) — `data-originalurl`/`data-versionurl`/
`data-versiondate` HTML attributes for pointing to archived snapshots.
Adopted: `--save-to-wayback` archives cited URLs, the archive URL
appears in `citations.json` (standard CSL `archive`/`archive_location`
fields) and as a visible 🗃️ archive-box link next to citations in
rendered HTML.

**Perma.cc** — whole-page WACZ capture + screenshot, no text anchoring.
Our pipeline does both: `--save-to-wayback` for whole-page preservation,
`quote` + `check_fragments.py` for specific-claim verification. They
answer different questions ("is there still a copy" vs. "does the page
still say the specific thing cited").

---

## Appendix B: DOD reference implementation

DOD's pipeline is the reference implementation. This section documents
how it works — not part of the format specification.

### Tooling (three phases)

All three phases read and write the same `citations.json` file — no
intermediate caches or markdown-specific extraction.

| Phase | Tool | What it does |
|---|---|---|
| Produce | `hooks/citation_export.py` | Build hook. Extracts quotes from markdown events and footnotes, merges with the existing `citations.json` (preserving any prior verification data), and writes back. |
| Augment | `util/citations_tool.py --augment` | Reads `citations.json`, fetches each page, verifies quotes, writes back `status`/`context`/`archive`/`accessed`. Uses a small `.citations-etag-cache.json` for conditional GETs on re-runs. |
| Verify | `util/citations_tool.py` | Reads any `citations.json`, fetches pages, reports MATCH/MISMATCH/AMBIGUOUS drift and context hash changes. Works on third-party files too. |

### DOD-specific notes

`citations.json` is always **derived, never authored**. Humans write
markdown. The build hook produces CSL-JSON. The JSON is never
hand-edited — it's consumed by Zotero, Pandoc, or a verifier.

**Verification fields: projected 2026-08-23, previously an open gap.**
For most of this format's life the mechanical-verification fields it
exists for were present on zero published entries. The data was never
missing — it was in the wrong file. `check_fragments.py` verifies every
quote on a schedule and writes results to
`docs/data/citation-evidence.json` (`verified` per-quote pass/fail,
`contexts` carrying `prefix`/`text`/`suffix`/`sha256`, `checked` for the
date) — and `citation_export.py` tried to *carry those fields forward
from its own previous output* rather than projecting them from that
cache. Since `citations.json` is gitignored and rebuilt from empty every
build, there was never a previous output to carry anything forward from:
the branch was structurally dead. Exactly the failure already caught
once for `archive`/`archive_location` (Appendix C, 2026-08-22), by
exactly the mechanism that entry named as the anti-pattern.

Now projected on every build, the same way the archive fields are. The
join needs no new plumbing: the cache is keyed by
`sha256(normalize_ws(quote))`, byte-identical to `evidence[].id`.
Measured on the real corpus, this moved the export from 313 KB to
400 KB (+27.8%) and filled in 340 of 443 evidence entries.

Three decisions worth recording, since none is forced by the mechanics:

- **`context` ships `sha256` plus `prefix`/`suffix`, but not `text`.**
  `prefix`/`suffix` are the TextQuoteSelector-shaped *disambiguation*
  anchors — a verifier that finds the quote more than once on the page
  needs them to know which occurrence the citation means, the one thing
  a hash alone cannot convey — so they're projected. `text` (the
  containing paragraph) is not: it's ~121 KB of other organisations'
  prose a verifier recomputes from the page it must fetch anyway, and
  republishing that much of someone else's writing in a bulk
  downloadable file is a materially different posture from quoting a
  sentence to verify it. (An earlier draft shipped *none* of the three,
  on the reasoning that all of it was offline diagnosis; prefix/suffix
  were split back out 2026-08-24 precisely because they are the
  *check*, not the diagnosis — see Appendix C.) Reversible later if a
  real consumer asks for the paragraph text too.
- **`verified-by` is omitted for `manual_verified` entries.** A human
  who opened a bot-blocked page in a real browser and saved it (see
  `util/manual_dump.py`) genuinely verified the quote — but the spec
  reads a present `verified-by` as "mechanically verified" and its
  absence as a human claim. Stamping those with the bot's identity
  would be false. `status` and `last-verified` still project.
- **`AMBIGUOUS` is unreachable from cache and never projected.**
  `check_fragments.py` only detects ambiguity on a fresh fetch and never
  persists it — a cache hit retains no page text to re-derive it from.
  Claiming it from cached data would assert something never stored.

**Still empty after this:** the ~103 entries with no cached verdict
(blocked, never fetched, or errored) carry no `status` — the spec reads
absence as "not yet verified", so the gap is honest rather than
papered over. `document.sha256` (resource-level review) is populated
separately, and only once `check_fragments.py` has re-fetched a URL
since the field was introduced — see "Built 2026-08-23" above for why
the real corpus shows 0/336 today rather than a backfilled number.

**A known limitation the signal map makes visible:** for 74 of 332
projected contexts, `context.sha256` equals the entry's own
`convergence.sha256` — the cited sentence *is* its entire containing
paragraph, so the two hashes are the same value by construction. The
review-tier signal cannot fire independently there: if the quote
survives, the context hash matches; if the quote changes, both change
together. It is emitted anyway rather than suppressed, since a consumer
can detect the degenerate case by comparing the two, whereas
suppressing it would be indistinguishable from "no context recorded".

**A drifted-but-live page never gets the archive-preferred treatment
`dead`/`unfit` gets (open gap, 2026-08-23).** `check_fragments.py`
already detects this exact case every week — `check_evidence()` computes
`result = quote_matches(text, evidence)` and stores it as a plain
boolean in `citation-evidence.json`'s `verified` map, keyed by the same
`sha256(normalize_ws(quote))` hash `evidence[].id`/`convergence.sha256`
already use. So a MISMATCH — the cited sentence is gone, but the site is
completely live and legitimate — is known and cached. Half of this is now fixed: as of
2026-08-23 the verdict *is* projected into `citations.json`'s
`evidence[].status` (see above), so a consumer reading the export can
see it. The rendering half is not — neither render path
(`organisation.html`'s `render_event` macro, `hooks/footnote_fragments.
py`) reads `citation-evidence.json`'s `verified` map at all — both
compute `is_rotted` from `url_status in ('dead', 'unfit')` only. Today's
actual behavior: a reader clicks through to a normal, working, entirely
legitimate page that simply no longer contains what's quoted, with no
visual signal at all — even when an `archive_url` from an earlier
snapshot already exists and would show them the real proof.

This is a third case, distinct from both existing `url_status` values,
and arguably the more common one in practice — pages get lightly edited
far more often than domains go fully dead or get parked. It isn't a new
`url_status` value, either: `url_status` is inherently about the *site*
(reachable? legitimate?), and a MISMATCH says nothing about that — the
site can be perfectly fine while one specific claim has drifted out of
it. The fix is evidence-scoped, not URL-scoped: extend `is_rotted` in
both render paths to also trigger per evidence entry when that entry's
`status` is `MISMATCH` and an `archive_url` exists for its URL,
independent of whatever `url_status` says at the item level. Flagged,
not built — same treatment as the gap above it.

**Multi-citation footnotes:** footnotes citing more than one source are
treated as citation-only — no quote is extracted for verification,
fragment rendering, or export, even if a quoted phrase is present.
Split into separate footnotes (one citation, one claim, one label) to
enable mechanical verification.

**Editorial notes and citation-only text are deliberately excluded
from `citations.json`** — this is a scope boundary, not a gap to fix.
Two sources on the wiki carry human-written prose that isn't a
verbatim `quote`: events' `note:` frontmatter field (an editorial
paraphrase, distinct from `quote:`) and citation-only footnotes (no
extractable quote — usually multi-link, book/person citations with no
URL, or a bare title/source/date). Neither ever appears in
`citations.json`, even though both are valid, spec-allowed sourcing on
the site itself (rendered directly on the page — see `note:` in the
"Organisation pages" section of `CLAUDE.md`, and "Prose footnote
citations"). The reason: `citations.json`'s entire value is in
`evidence[].quote` being mechanically re-checkable — `status: MATCH`
means something because `check_fragments.py` verified the substring
still appears on the live page. A paraphrase or a no-URL book citation
has nothing to re-check; folding it into `evidence` under some new
`type` would dilute that guarantee for every consumer without adding
real information (the note/citation is already readable in the page's
own rendered HTML). Considered 2026-08-13, on request, before building
it — see the reasoning above for why it doesn't clear the bar. Revisit
only if a concrete downstream consumer actually needs it.

---

## Appendix C: Changelog

- **2026-08-12:** Changed `context` from two mutually-exclusive forms
  (paragraph or prefix/suffix) to a bag of optional fields — any
  combination of `text`, `prefix`, `suffix` is valid. `sha256` is
  computed over `text` if present, otherwise `prefix + quote + suffix`.
- **2026-08-12:** Added `status` field (MATCH/MISMATCH/AMBIGUOUS) at
  evidence level.
- **2026-08-12:** Added archive-box link rendering (Robust Links-style)
  and `archive`/`archive_location` in `citations.json`.
- **2026-08-12:** Added fuzzy-diff `closest_match_hint()` diagnostic
  for MISMATCH events (Hypothes.is-inspired, diagnostic-only).
- **2026-08-14:** `closest_match_hint()` now also returns a rendered
  character-level diff (page − / quote +, whitespace made visible) so a
  MISMATCH from a one-character divergence — em-dash spacing, a stray
  sentence-terminating period on a quote that continues mid-clause — is
  fixable at a glance instead of requiring a manual page fetch to locate
  it. Verification semantics unchanged (still exact-match-only).
- **2026-08-14:** Added `spacing_autofix()` and a `--autofix-spaces` flag
  on `check_fragments.py` that rewrites a MISMATCHed stored quote in
  place when its only differences from the live page are space runs
  (em-dash spacing, stray spaces). This class is safe to auto-apply by
  construction — if only spaces differ, the quote's words are a
  contiguous substring of the page's, so the fix cannot change what the
  quote claims — and the corrected text is what the browser renders, so
  the `#:~:text=` highlight passes too. Deliberately scoped to spaces
  only: punctuation, case, content changes, and the "page continues past
  the quote" case all stay MISMATCH for human judgment (a trailing
  period vs. the page continuing is an editorial choice about quote
  extent and a genuine page-drift signal, not a typo to hide). Opt-in
  flag, writes to source files (surgical substring replace, refuses
  unless the old string occurs exactly once), refuses on ambiguity
  (corrected text appearing >1× on the page), records the corrected
  string as verified against that fetch.
- **2026-08-14:** Two fixes from the first real autofix run. (1) `--slug`
  is now repeatable (`action="append"`) — it used to silently honor only
  the last flag passed, so `--slug a --slug b` verified a alone while
  looking like it was checking both. (2) The raw substring replace behind
  `--autofix-spaces` silently gave up on quotes whose parsed value isn't
  verbatim in the file — the folded/single-quoted scalars YAML itself
  chooses for values containing `: ` or apostrophes (confirmed live: the
  démocratie-ouverte Convention Citoyenne quote stores as a single-quoted
  scalar with `''`-escaped apostrophes, which raw text search can never
  locate). `write_quote_fix()` now falls back to `_write_quote_fix_yaml()`,
  which locates the value by parsing the frontmatter, rewrites the unique
  matching event's `quote:`, and re-serializes through
  reorder_frontmatter's canonical dumper so `--check` still passes. Refuses
  safely: non-org files, a quote value shared by >1 event, or a file whose
  frontmatter isn't already canonical (re-serialization would fold unrelated
  reformatting into a one-line fix).
- **2026-08-14:** Added `tests/` (stdlib `unittest`, offline, wired into
  CI) covering both files — see issue #155, which was opened after the
  two bugs above shipped without any automated coverage catching them.
  Regression tests exist for both: `--slug`'s `action="append"` list
  behavior (`collect_evidence` filtering) and `_write_quote_fix_yaml()`'s
  success path plus its three refusal branches. Also covers the older
  `paragraph_hash()` offset-drift and `wikipedia_title()`
  non-English-subdomain bugs referenced elsewhere in this changelog, and
  the pure functions in `text_fragment.py`. See `CLAUDE.md`'s "Tests"
  section for how to run it.
- **2026-08-14:** `check_fragments.py`/`check_event_urls.py` gained a
  `--report PATH` flag writing a JSON findings summary (mismatches/
  ambiguous/fetch-errors; dead/blocked/redirected/errored URLs) alongside
  their normal stdout output — for ad hoc/manual review, not wired into
  the weekly cron. A GitHub-Actions-driven auto-filed tracking issue was
  prototyped and deliberately dropped: this repo keeps its Actions usage
  scoped to CI checks and light read-only probing, not scripts that open
  tickets on their own schedule. Deciding whether a finding is worth
  tracking stays a periodic, manual, human/AI-reviewed judgment call (see
  HEARTBEAT.md's note on `check_fragments.py`/`check_event_urls.py`), not
  something automated end-to-end.
- **2026-08-22:** Added `url_status` (`dead`/`unfit`, manually set via
  `check_fragments.py --set-url-status`, never inferred) to
  `docs/data/citation-evidence.json`, and a corresponding `url-status`
  DOD extension field on `citations.json`. Also fixed a real gap found
  while designing this: `archive`/`archive_location` had been sitting
  unpopulated (0 of 328 entries) since the 2026-08-12 changelog entry
  above added them, because `citations_tool.py --archive` — the only
  thing that ever wrote them — had never actually been run, while the
  archive-box *rendering* added that same day was wired to a completely
  different, independently-populated cache
  (`citation-evidence.json`'s `archive_url`, written by
  `check_fragments.py --save-to-wayback`). Two write paths for the same
  data, neither one populating the CSL export. Fixed by making
  `citations.json`'s `archive`/`archive_location`/`url-status` fields a
  **read-only projection** of `citation-evidence.json`, generated
  fresh by `hooks/citation_export.py` on every build rather than carried
  forward from the file's own previous output — `citations_tool.py
  --archive` remains valid for a third-party citations.json (its
  original use case) but is now discouraged on DOD's own file. Rendering
  also gained a Wikipedia `Help:Citation Style 1`-style behavior: once
  `url_status` is `dead`/`unfit` and an archive exists, the archive link
  becomes primary and the original is demoted to a plain trailer, instead
  of always showing the (possibly dead) original as primary with the
  archive as a secondary "🗃️" button. See
  `internal-heartbeat/2026-08-22-citation-archival-design-decisions.md`
  for the full design conversation.

- **2026-08-23:** Added `evidence[].id` — `sha256(normalize_ws(quote))`,
  full 64-char lowercase hex — so a specific *claim* is addressable from
  outside the file, not just the URL it came from (a URL's `evidence`
  array routinely holds several quotes). Needed by Appendix E's COinS
  pointer, which cannot embed the quote itself. The item-level `id`
  moved to full `sha256(URL)` in the same pass: it had been `md5(url)[:8]`,
  briefly became `sha256(url)[:12]`, and both truncations were
  optimizations for a constraint that does not exist — CSL-JSON `id`
  values are tool-generated, not hand-typed, and a JSON field has no
  byte budget. Settled rule, now stated normatively under "Identifier
  construction": store the full digest everywhere; truncate only where a
  named cost scales with length, which in this design is exactly one
  place (the COinS span), resolved by Git-style prefix match.
- **2026-08-23:** Specified quote normalization normatively instead of
  leaving it as a reference to DOD's `normalize_ws()`. Without this an
  independent implementer cannot reproduce `evidence[].id`, which breaks
  the cross-site convergence that is the main argument for using a
  content hash at all. Also flagged the wart it exposes: the paren rules
  inside that function are compensating for one HTML-to-text extractor's
  artifact, and are now doing double duty as part of an identity.
- **2026-08-23:** Recorded two consistency findings without changing
  them, both in Appendix B / "Naming and value conventions": `status`
  uses uppercase values against the format's own lowercase convention,
  and the entire mechanical-verification field set (`status`,
  `last-verified`, `verified-by`, `context`, plus `accessed`/`archive*`)
  is specified but present on zero published entries, because
  `citation_export.py` carries those fields forward from its own prior
  output rather than projecting them from `citation-evidence.json` —
  a structurally dead branch, since the file is gitignored and rebuilt
  from empty every time. Same failure mode as the 2026-08-22 archive
  entry below.
- **2026-08-23:** Added a second, deterministic content-hash field
  alongside `id`, motivated by a real tension: `id`'s self-verification
  and cross-site convergence properties both hold only because DOD made
  `id` itself content-derived, but an implementation needing `id` to
  survive a routine quote edit (a typo fix, a lengthened excerpt) needs
  it to be a persisted local key instead — which drops convergence.
  Introduced the split (`id`'s generation is implementation-defined;
  the new field is the one thing that must stay standardized), initially
  named `convergence-id`, present only when `id` wasn't already
  content-derived. Reconsidered twice in the same pass: (1) a conditional
  presence rule forces every consumer to branch on whether the field
  exists before knowing which one to read, so it's now always emitted,
  even when byte-identical to `id` for DOD's own implementation; (2) a
  purpose-named field (`convergence-id`) can't declare which algorithm to
  recompute it with, so it was renamed to `sha256`, matching
  `evidence[].context.sha256`'s own naming precedent; (3) that broke the
  same precedent's *shape* — `context` is a named wrapper object with
  `sha256` nested inside, not a flat field — so it became
  `convergence: {"sha256": "..."}` at both the item and evidence level.
- **2026-08-23:** While checking whether a hash of a URL and a hash of
  cited content were the same concept, found `CLAUDE.md`'s Data exports
  table describes `citations.json` as having a `content-sha256` field
  that `citation_export.py` has never written. Corrected the same day to
  list the fields actually exported, with the specified-but-unpopulated
  verification fields called out. Also specified where a whole-file hash
  (for a fixed artifact like a PDF, as opposed to a living HTML page)
  would belong if ever built — integrity/drift, not identity/agreement;
  an initial placement inside `convergence` was corrected once the
  distinction was made explicit, and a second near-miss (naming it
  top-level `context`, colliding with `evidence[].context`) was caught
  and settled on `document.sha256`.
- **2026-08-23:** Built `document.sha256`, filling the signal map's one
  remaining empty cell (resource-level review-tier integrity).
  `check_evidence()` now computes `sha256(text)` unconditionally on
  every successful fetch — the same *extracted* text `quote_matches()`/
  `paragraph_hash()` already operate on, not raw pre-extraction bytes as
  an earlier note in this file sketched, specifically to avoid flagging
  markup-only edits (a changed script tag, a tweaked `alt` attribute) as
  content drift. This replaced a field named `content_hash` that
  computed `paragraph_hash(text, evidence)` — the hash of whichever
  quote's paragraph was checked most recently — falling back to a whole-
  page hash only when that quote couldn't be located; since the function
  runs once per evidence string, a multi-quote URL had it silently
  overwritten by iteration order, not page identity, and it was never
  read anywhere. `citation_export.py` projects it as item-level
  `document.sha256`, the same pattern as `archive_url`. On the real
  corpus this shows 0/336 items populated today, not a bug — the
  committed cache still holds the old field name, and it self-heals the
  next time `check_fragments.py` successfully re-fetches each URL, same
  as `PAGE_TOO_SHORT` elsewhere in this pipeline.
- **2026-08-23:** Projected `status`/`last-verified`/`verified-by`/
  `context` from `citation-evidence.json` into `citations.json`,
  closing the "specified but unpopulated" gap recorded earlier the same
  day. These had tried to carry forward from the export's own prior
  output — structurally dead, since the file is gitignored and rebuilt
  from empty. Measured: 313 KB → 400 KB (+27.8%), filling 340 of 443
  evidence entries. Chosen over the alternative of also projecting
  `context`'s stored `prefix`/`suffix`/`text`, which measured at 592 KB
  (+89%) and would republish ~209 KB of other organisations' paragraphs
  in bulk for data a verifier doesn't need — it refetches the page to
  recompute the hash anyway. Two provenance details settled in the
  same pass: `verified-by` is omitted for human browser-snapshot
  verifications (the spec reads its absence as a human claim, so
  stamping the bot's identity there would be false), and `AMBIGUOUS` is
  never projected because `check_fragments.py` only detects it on a
  fresh fetch and never persists it. An earlier size estimate in this
  conversation put these at +8%/+67%; it measured value payloads
  without `indent=2` serialization overhead and was wrong — the
  ordering held, the numbers did not.
- **2026-08-24:** Split `context`'s `prefix`/`suffix` back into the
  `citations.json` projection, keeping `text` out. The 2026-08-23 entry
  above shipped none of the three on the reasoning that all of it was
  offline diagnosis a verifier doesn't need — but `prefix`/`suffix` are
  not diagnosis: they are the TextQuoteSelector-shaped disambiguation
  anchors that let a verifier pin *which* occurrence of a repeated
  sentence a citation means, the one thing a `sha256` alone cannot
  convey. Measured on the corpus: `prefix`+`suffix` ≈ 114 KB vs ~121 KB
  for the paragraph `text`, so projecting the anchors is ~+27% rather
  than the ~+89% the full projection measured. Also surfaced along the
  way: 86 of 430 cache context entries store no paragraph text at all
  (the paragraph exceeded the 1000-char cap), so for those the cache
  alone cannot say what claim the record refers to without joining
  against markdown — a self-description gap recorded here for a
  possible future cache-shape change, not addressed by this one.
- **2026-08-23:** Replaced the "Two tiers of integrity" section with a
  signal map on two axes — identity vs integrity, resource level vs
  claim level — after a conversation probing whether a `citation`/
  `locator`-style level belonged between source and evidence. Two
  findings from measuring the corpus rather than reasoning about it:
  (1) a first-class "passage" level would be ceremony — of 327 URLs with
  stored contexts, exactly one has two quotes sharing a paragraph, so a
  passage wrapper would hold exactly one quote 99.7% of the time;
  (2) the existing item/evidence split is load-bearing — 20.2% of URLs
  carry more than one quote, accounting for 39.5% of all evidence
  entries, so `rft_id` alone really is ambiguous for a large minority of
  citations and Appendix E's `evidence_sha256` is justified. The map's
  value is diagnostic: it has exactly one empty cell (resource-level
  review-tier integrity, `document.sha256`, built the same day), and it explains
  the MISMATCH-rendering gap below as a populated cell that the render
  code simply never reads. A speed argument for scoping quote search to
  a section was measured and dropped: ~5µs substring search on the
  largest real page (47,000 chars) against a deliberate
  `FETCH_DELAY = 0.5s` plus network round-trip.
- **2026-08-23:** Flagged that a quote going `MISMATCH` on an otherwise
  completely live, legitimate page never triggers the archive-preferred
  rendering that `url_status: dead`/`unfit` does — `check_fragments.py`
  already computes and caches this verdict weekly, but neither render
  path (`organisation.html`, `hooks/footnote_fragments.py`) reads it;
  both key their decision purely off the item-level `url_status`. Not a
  new `url_status` value — the gap is evidence-scoped, not URL-scoped.
  See "DOD-specific notes" in Appendix B.
- **2026-08-23:** Renamed Appendix E's proposed COinS key from
  `dod_evidence` to `evidence_sha256`. This document proposes a standard
  extension by example, not a DOD-local convention, and an org-branded
  key name contradicted that on its face — no other field in this format
  carries a `dod_` prefix in the key itself (`url-status` etc. are only
  ever called "DOD extension fields" in prose). Also softened
  surrounding language in the same appendix ("private, additive DOD
  convention" → "additive convention... usable by any implementation")
  for the same reason. Also added a cross-reference making explicit that
  a COinS span *is* DOD's version of a CSL `citation`/`citationItem`'s
  cite-location concept, with `evidence_sha256` playing `locator`'s role
  but resolving to mechanically-checkable text instead of a human-read
  position string, and flagged a reverse-index idea (evidence entries
  optionally listing which locations cite them) as a follow-on, not
  built.

---

## Appendix D: Promoting this to upstream CSL-JSON (not yet — how-to for later)

Idea raised 2026-08-12: propose `evidence`, `archive`/`archive_location`,
etc. as an actual CSL-JSON extension upstream, not just a convention
DOD's own tooling happens to produce. Checked what that would actually
take; recording it here rather than acting on it now.

**Where this format stands today — corrected 2026-08-13.** The original
note above ("evidence, archive/archive_location, etc. are all technically
invalid") overstated the gap: it was written against `csl-citation.json`
(the *in-text citation cluster* schema — citationID, citationItems, a
completely different object), not `csl-data.json`, the one that actually
governs the item objects `citations.json` produces. Re-checked against
the real one:
(https://github.com/citation-style-language/schema/blob/master/schemas/input/csl-data.json).
It does set `"additionalProperties": false` on item objects, confirmed —
but every field DOD's `citations.json` actually emits today (checked the
live file: `id`, `type`, `URL`, `title`, `accessed`, plus `archive`/
`archive_location` when populated) is already a real, defined CSL field.
**`evidence` is the only non-standard key**, not a family of them.

Better still, the schema defines an explicit escape hatch for exactly
this case — a `custom` property (`"type": "object"`, no
`additionalProperties` restriction of its own), documented in-schema as
"Used to store additional information that does not have a designated
CSL JSON field... preferred over the note field for storing custom
data." Nesting `evidence` under `custom.evidence` instead of at the top
level would make `citations.json` fully schema-valid *today*, with no
upstream involvement needed.

**Decided 2026-08-23: not doing this.** `custom` is a junk-drawer any
implementation can read differently or ignore — nesting `evidence` there
would make the file schema-valid but wouldn't get any other citation tool
to understand what `evidence`/`quote-match`/`status` actually mean, and
critically, it undercuts the actual goal: DOD wants to *push for
`evidence` becoming a real, recognized field*, not just avoid a validator
complaint. Hiding it in the sanctioned "doesn't fit anywhere" bucket reads
as "we know this isn't a real proposal" before anyone's even looked at
it. `citations.json` keeps `evidence` at the top level, and stays
strictly non-schema-valid, on purpose.

**Why that's an acceptable tradeoff, not just an oversight:** `citations.json`
is an opt-in file — a consumer has to deliberately fetch and parse it, and
the two that actually matter (Pandoc's citeproc, Zotero) don't run strict
schema validation at parse time regardless; they read known fields and
ignore the rest, which is why the Pandoc round-trip claim above holds
either way. A strict validator choking on `evidence` is a real but narrow
risk — one visible failure for a consumer who chose to engage, on a
small, unofficial file, not silent breakage for someone who never opted
in. The schema repo also still describes itself as "not yet fully
normative," so even upstream doesn't treat it as a closed contract this
would be violating. Contrast this with the COinS case in Appendix E below,
where the equivalent risk is NOT acceptable regardless of project size —
different consumer, different failure mode, not just a smaller version of
the same tradeoff.

**What accepting non-compliance now is actually buying:** not just "we
didn't have to do a refactor" — a real, running reference implementation
to point to later, which is the strongest form any standards pitch can
make (the old IETF framing: rough consensus and running code beats a
well-argued but untested proposal). A `custom.evidence`-nested version
would be schema-valid but wouldn't prove anything about whether
`evidence`/`quote-match`/`status`/`context` actually hold up as a shape —
it'd just be data nobody's built anything real against. The top-level,
non-compliant version is the one that's actually been exercised: produced
by `hooks/citation_export.py`, consumed by `util/citations_tool.py`,
mechanically verified against live pages by `check_fragments.py`, with
real MISMATCH/AMBIGUOUS findings from real citations (see Appendix C).
That's the artifact worth walking into `discourse.citationstyles.org`
with — not a compliance trick, a working example of the field doing its
actual job at real scale. Keep it clean and well-documented (this file
*is* that documentation) specifically so it can serve as the reference
implementation the eventual pitch points to, not just a private
convenience.

**The actual contribution path**, per the repo's `CONTRIBUTING.md`:
1. File an issue first, following their issue template — enough detail
   that maintainers can see "what you are requesting, how broad the need
   is, and what implementation options there are." Not a PR-first project.
2. Community discussion venue: https://discourse.citationstyles.org/
   — worth raising it there too, not just as a GitHub issue.
3. A schema change PR has to update the JSON Schema *and* the mirrored
   RNC (Relax NG Compact) files together — they're kept in sync by
   convention, not just the JSON one.

**Why not now:** the field set has been substantively reworked multiple
times in a single day as of this writing (paragraph-only context →
prefix/suffix → optional-fields bag; `status` added; archive fields
added — see Appendix C). Walking into an external project's tracker with
names that might change again next week costs credibility for no real
gain. Right call is to let it sit through some real-world use first —
confirm `citations_tool.py --verify` actually round-trips a citations.json
that DOD's own `citation_export.py` didn't produce — then file the issue
once the shape has actually stopped moving.

## Appendix E: Extending COinS for per-page discovery (do first, propose later)

Raised 2026-08-23: `citations.json` is a bulk file a researcher has to know
to look for. COinS (ContextObjects in Spans — an OpenURL/Z39.88-2004
ContextObject embedded as `<span class="Z3988" title="ctx_ver=...">`) is
the actual, currently-deployed mechanism reference managers (Zotero,
EndNote, RefWorks) use to detect "there's a citable thing right here" on
an arbitrary webpage, no separate file needed. Confirmed still live, not a
deprecated relic — fetched `https://en.wikipedia.org/wiki/Local_government_in_Victoria`
(a page this repo already cites in `how-victorian-councils-are-governed.md`)
directly and found 27 `Z3988` spans, one per reference, generated by
MediaWiki's own Cite templates.

**Same two-goal split as Appendix D, same reasoning, different format.**
This is a proposed extension, not a DOD-private convention — the point
is that any implementation of this standard can adopt the same key with
no coordination, the same way the rest of this format is meant to work:

1. *An additive convention, backwards-compatible, usable now by any
   implementation* — the actual target of this appendix.
2. *A genuine registered OpenURL extension/profile* — a real
   NISO-adjacent process, and a categorically different ask from (1):
   (1) needs no one's cooperation, since `rft_id` plus the small
   `evidence_sha256` pointer (see below) already let any tool that
   understands this standard resolve the exact verification record from
   `citations.json` without touching Zotero/EndNote/RefWorks at all; (2)
   is specifically
   about getting *those external tools themselves* to parse and surface
   DOD's verification semantics in their own UI, which only they can
   decide to build. Lower priority than the Appendix D CSL-JSON path,
   since CSL/citeproc (Zotero, Pandoc) is the actively-maintained
   ecosystem DOD's tooling already targets; OpenURL/COinS is comparatively
   legacy library-science infrastructure. **Deliberately not scoped
   here** — the concrete trigger for picking it up would be DOD deciding
   it specifically wants citation-manager-native visibility (not just
   DOD's own tools reading DOD's own data), which is its own decision
   with its own cost/benefit case, not a natural extension of anything
   already committed to. Recorded only so a future session doesn't have
   to re-derive that COinS *does* have an analogous escape hatch if that
   decision is ever made.

**Why (1) is safe to just do, backwards-compatibly, with no upstream
involvement:** a COinS `title` attribute is nothing more than a
URL-encoded query string. A conformant OpenURL parser reads the `rft.*`
keys it recognizes under whichever profile (`rft_val_fmt`) is declared —
journal, book, Dublin Core — and is expected to silently ignore keys it
doesn't know, the same tolerance every query-string-shaped format relies
on. So:

- Emit every standard key exactly as MediaWiki does today (same
  `rft_val_fmt`, same `rft.atitle`/`rft.date`/etc.) so Zotero/EndNote/
  RefWorks keep working completely unmodified — this is the backwards-
  compatibility requirement, not a nice-to-have.
- **`rft_id` (standard, already present) resolves the URL; one small
  extension key resolves *which claim* on that URL.** An earlier draft of
  this appendix tried to get away with adding nothing at all beyond
  `rft_id`, on the theory that a resolver could just look the URL up in
  `citations.json`. That's true as far as it goes, but incomplete: a
  single URL's `evidence` array can (and does) hold more than one quote
  — the same source cited for two different claims elsewhere on the
  site — so `rft_id` alone tells a resolver *which page to check*, not
  *which of that page's several recorded quotes this particular citation
  is vouching for*. Since the quote itself deliberately isn't embedded
  in the span (next bullet), resolving a specific citation instance
  needs a pointer to a specific `evidence[]` entry, and a URL isn't
  precise enough to be that pointer on its own. Concretely: add a single
  key — `evidence_sha256` — carrying a short **prefix** of that entry's
  `evidence[].id` (see "Identifier construction" above: the full 64-character
  hash is what's actually stored in `citations.json`; a resolver takes
  the prefix off the span and finds the one `evidence[].id` in the
  target URL's array that starts with it, same prefix-match resolution
  Git uses for abbreviated commit hashes). This is the one piece of
  non-standard vocabulary this appendix actually asks for; everything
  else stays standard COinS. Named after what it carries, not who
  implemented it first — same convention as `convergence.sha256`/
  `context.sha256` in the JSON format, and underscore-joined to match
  the existing `rft_val_fmt`/`rft_id` key style in this span rather than
  the hyphenated style DOD's own `citations.json` extension fields use.
  Any implementation of this standard can emit and resolve the same key;
  nothing about it is DOD-specific.
- **Don't embed the quote, context, or hash directly in the span.** Same
  mistake `check_evidence()`'s own docstring already warns against for
  the evidence file (storing full page text made it balloon to
  megabytes) — and COinS spans on Wikipedia already draw real complaints
  about page bloat without adding to it. `evidence_sha256` stays a short
  prefix, not the full 64-character hash, for exactly this reason — it's
  a pointer, not a copy of the content it points to, and the span is the
  one place in this design where byte size actually matters.

**Where this would live in code, when/if implemented:** a new Jinja
filter alongside `with_fragment`/`archive_info_for` (see
`hooks/org_events.py`'s `on_env`), rendered into `organisation.html`'s
event timeline and `hooks/footnote_fragments.py`'s footnote links — same
render-time-derived, never-stored-in-frontmatter pattern as everything
else in this file. Not yet built; this appendix is the design record, not
an implementation.

**This is, concretely, a location-links-to-evidence relationship** — the
rendered citation the COinS span sits next to (a footnote link, an
org-page timeline entry) *is* the "cite location," in the same sense
CSL's own `citation`/`citationItems` objects represent one citing
occurrence in a document. `evidence_sha256` is the pointer from that
location to the one canonical evidence entry backing it, the same job
`locator` does in a CSL `citationItem` — except `locator` is a
human-readable position string ("page 42") built for manual
verification, while `evidence_sha256` resolves to actual verbatim text a
script can mechanically re-check. DOD didn't adopt CSL's `citation`
object model to get this: those objects are citeproc processor state (a
Word/LibreOffice plugin's in-document cursor state), not something
published as a portable, fetchable file, so there's no natural home for
them in a static-site pipeline. The rendered page element already *is*
the location; COinS lets it carry a pointer without inventing a second,
parallel citation-tracking structure alongside the markdown that already
exists.

The link only runs one direction here — location knows which evidence
backs it, evidence doesn't know which locations cite it. A reverse index
(each evidence entry optionally listing which citing locations reference
it) would be the other direction, and wouldn't reintroduce the bloat
problem the bullet above rules out, since it's metadata about usage, not
a copy of the quote re-embedded per location. Nothing like it exists
today. Not scoped — recorded here as the natural follow-on if a concrete
use ever needs "everywhere this exact sentence is cited from" answered
without re-scanning every markdown file.

**Consistent with this repo's own working philosophy** (see Appendix D's
"Why not now" above, and how the `evidence`/`archive` CSL-JSON fields
themselves shipped in DOD's own tooling well before any upstream
conversation was even considered): ship the additive convention as a
proposal-by-example first, let it see real use, and only look at a formal OpenURL
registration — if ever — once the shape has actually stopped moving.
There's no equivalent "why not now" blocker here the way there was for
CSL-JSON's evolving field set, since this is purely additive to a spec
DOD doesn't control and isn't asking anyone to adopt.

## Appendix F: Point-to-point verification via a browser extension (idea, not scoped)

Raised 2026-08-23, in the same conversation as Appendix E. Sharpened into
the framing that makes it click: **`citations.json` + `check_fragments.py`
is bulk verification** — one server, on a schedule, sweeping the entire
corpus at once, limited to whatever a script is *allowed* to reach.
**This idea is point-to-point verification** — one person, one moment,
one specific citation they're already looking at, using their own
browser's access, which a bot-defended site can't distinguish from any
other real visitor. Different shape, not a competing mechanism: bulk
trades reach for coverage (checks everything, but bounces off anything
that blocks scripts); point-to-point trades coverage for reach (checks
almost nothing on its own, but can reach exactly the things bulk
structurally can't — the entire reason `STILL BLOCKED`, robots.txt gates,
and `PAGE_TOO_SHORT` SPA shells exist as categories in this repo).

**To be clear about what "verification" means here — same mechanical bar
as everywhere else in this file, not human judgment.** The extension
would run the identical substring-match check `check_fragments.py`
already runs server-side — "is this exact quote still present on this
page" — just executed inside the visitor's own browser instead of a
scheduled server fetch, so it inherits their real session/IP/fingerprint
and gets past bot-defenses a script can't. It is not a human manually
re-reading the source to judge whether the citation actually *supports*
the claim it's attached to — that editorial judgment call is made once,
at authorship, and stays out of scope for every part of this pipeline,
bulk or point-to-point alike.

**This isn't actually a new idea for DOD — it's an unautomated version of
one that already ships.** `util/manual_dump.py` *is* point-to-point
verification today: a maintainer deliberately opens a `STILL BLOCKED` URL
from `manual-dump/requests.txt` in a real browser, saves the rendered
page, and `import_manual_dump.py` checks the stored quote against it —
exactly "a human's real browser sees past what the script can't," just
triggered by a maintainer working through a worklist rather than by
ordinary browsing. A browser extension would be the passive/automatic
version of the same mechanism: any visitor's normal click-through to a
citation's original source becomes a verification opportunity, with
nobody having to remember to run the manual-dump workflow at all.

**What it would actually require, honestly:**

- **Bespoke software, not a COinS tweak.** Zotero/EndNote have no notion
  of DOD's `quote:`/evidence semantics — this needs its own extension,
  built and maintained by DOD, not an add-on behavior of an existing tool.
- **A live backend, which does not currently exist.** This site is fully
  static (GitHub Pages, `mkdocs gh-deploy`) with no server component at
  all. For an extension to report "I just saw this quote is still there"
  anywhere useful, something has to receive that report — an API
  endpoint, storage, ongoing hosting. This is the single biggest gap, well
  past the surface size of anything else in this document — every other
  mechanism here (COinS, citations.json, `.pagecache/`, the evidence file)
  is static-site-compatible; this one structurally isn't.
- **A trust story for self-reported results.** An anonymous "verified:
  true" ping is spoofable with no integrity check — it can't be trusted
  at the same tier as DOD's own server-side verification (a known,
  reviewable, git-committed algorithm run on a schedule). Right treatment:
  same tier as `manual_verified` already gets — a distinct, separately-
  labeled signal that can unblock a `STILL BLOCKED` citation or corroborate
  a stale one, but never silently promoted to the same trust level as an
  automated `MATCH`.
- **Sparse, opportunistic coverage.** Rare or low-traffic citations might
  never get a passive check — this supplements the bulk sweep for the
  specific subset it can't reach, it doesn't replace it as primary
  coverage.

**Not scoped or committed to** — recorded here so the bulk/point-to-point
distinction and the `manual_dump.py` precedent don't have to be
re-derived if this becomes worth actually building later. If pursued, the
natural sequencing mirrors this whole file's own history: ship the
extension against a minimal backend, prove it resolves real `STILL
BLOCKED`/`BLOCKED` cases faster than the manual worklist does, and only
then decide whether the trust-tier question needs more design than "treat
it like `manual_verified`."

## References

- CSL-JSON schema: https://github.com/citation-style-language/schema
- CSL-JSON item/data schema (governs citations.json's objects — NOT
  csl-citation.json, which is the separate in-text-citation-cluster
  schema): https://github.com/citation-style-language/schema/blob/master/schemas/input/csl-data.json
- CSL 1.0.2 spec: https://docs.citationstyles.org/
- W3C Web Annotation Data Model, TextQuoteSelector: https://www.w3.org/TR/annotation-model/#text-quote-selector
- WICG Text Fragments: https://wicg.github.io/scroll-to-text-fragment/
- RFC 7089 (Memento): https://datatracker.ietf.org/doc/html/rfc7089
- Robust Links specification: https://mementoweb.org/robustlinks/spec/
- Hypothes.is fuzzy anchoring: https://web.hypothes.is/blog/fuzzy-anchoring/
- Perma.cc documentation: https://perma.cc/docs/perma-link-creation
- CSL-JSON schema CONTRIBUTING guide: https://github.com/citation-style-language/schema/blob/master/CONTRIBUTING.md
- CSL discussion forum: https://discourse.citationstyles.org/
- NISO Z39.88-2004, The OpenURL Framework for Context-Sensitive Services: https://www.niso.org/standards-committees/openurl
- COinS (ContextObjects in Spans) specification: https://ocoins.info/
- OpenURL 1.0 KEV (key/encoded-value) guidelines (defines the `rft.*`/`rft_val_fmt`/`rft_id` query-string keys COinS spans carry): https://web.archive.org/web/2019/http://alcme.oclc.org/openurl/servlet/OAIHandler/extension?identifier=info:ofi/fmt:kev:mtx:ctx
