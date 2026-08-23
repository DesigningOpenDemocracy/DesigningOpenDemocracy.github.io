# Machine-verifiable citation — standard

A citation format that tells you what the source said and how to check if it still says it. Ships as a `citations.json` alongside your content. No academic infrastructure required.

## Format

Layered on standard CSL-JSON — ignored by Zotero, Pandoc, citeproc.
The `evidence` array groups per-claim data under each URL.

```json
{
  "type": "webpage",
  "URL": "https://en.wikipedia.org/wiki/MySociety",
  "title": "mySociety",
  "accessed": {"date-parts": [[2026, 8, 12]]},
  "archive": "Internet Archive Wayback Machine",
  "archive_location": "https://web.archive.org/web/20260812123456/https://en.wikipedia.org/wiki/MySociety",
  "evidence": [
    {
      "type": "quote-match",
      "quote": "mySociety was founded by Tom Steinberg in September 2003",
      "last-verified": "2026-08-12",
      "verified-by": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)",
      "status": "MATCH",
      "context": {
        "text": "mySociety was founded by Tom Steinberg in September 2003 and started with TheyWorkForYou, a parliamentary monitoring website that makes it easy for people to keep tabs on their elected representatives.",
        "prefix": "mySociety is a UK-based not-for-profit social enterprise,",
        "suffix": "and started with TheyWorkForYou, a parliamentary monitoring website.",
        "sha256": "abc789..."
      }
    }
  ]
}
```

### Field meanings

**URL-level fields** (one per cited page):

| Field | Purpose |
|---|---|
| Standard CSL-JSON (`type`, `URL`, `title`, `accessed`, `archive`, `archive_location`) | Interoperable with Zotero, Pandoc, citeproc. `archive`/`archive_location` are standard CSL fields — a Wayback Machine snapshot (or equivalent) of the page at the time it was cited, so a reader can inspect what the citation originally pointed to even if the live page has changed or disappeared. |

**Per-claim fields** (one entry per quote, nested under `evidence`):

| Field | Required? | Purpose |
|---|---|---|
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

### Content hash

`context.sha256` pins the evidence to a specific span of source text.
A verifier re-fetches the page, extracts the same span, and compares
hashes. If the hash changed but the quote still matches, the page was
edited *around* the claim — a review signal, not a failure.

The `sha256` is computed over `context.text` directly (paragraph form)
or `prefix + quote + suffix` concatenated (prefix/suffix form).
Plain-text substring slices — no HTML parsing needed.

### Two tiers of integrity

| Tier | Field | What it catches | Action |
|---|---|---|---|
| **Gate** | `quote`, `status` | Quote no longer matches source → citation broken | Fix or remove |
| **Review** | `context.sha256` | Hash changed but quote survived → page edited around claim | Open review ticket, human checks framing |

A reader or bot checking `citations.json` knows the difference between
"this citation is dead" (status: MISMATCH) and "this page was edited but
the cited sentence is intact" (context hash changed, quote survived).

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

**Same two-goal split as Appendix D, same reasoning, different format:**

1. *A private, additive DOD convention, usable now* — the actual target
   of this appendix.
2. *A genuine registered OpenURL extension/profile* — a real
   NISO-adjacent process, and a categorically different ask from (1):
   (1) needs no one's cooperation, since `rft_id` already lets any
   DOD-built tool resolve full verification data from `citations.json`
   without touching Zotero/EndNote/RefWorks at all; (2) is specifically
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
- Add DOD-prefixed keys *alongside* them in the same span for anything
  DOD-aware that wants more, e.g. a single `dod_status` flag
  (`live`/`dead`/`unfit`, mirroring `url_status` — see the "Citation
  archival" section of `CLAUDE.md`).
- **Don't embed the quote, context, or hash directly in the span.** Same
  mistake `check_evidence()`'s own docstring already warns against for
  the evidence file (storing full page text made it balloon to
  megabytes) — and COinS spans on Wikipedia already draw real complaints
  about page bloat without DOD adding to it.
- **The actually elegant part needs no new keys at all:** `rft_id` in a
  standard COinS span is already just the cited URL — the exact key
  `citations.json` is indexed by. A DOD-aware tool that wants the full
  verification record (quote, status, archive location) just takes
  `rft_id` off the span and looks it up in the already-public
  `citations.json`. `dod_status` above is a convenience to skip that
  round trip for the one-bit "is this flagged" question, not a
  requirement.

**Where this would live in code, when/if implemented:** a new Jinja
filter alongside `with_fragment`/`archive_info_for` (see
`hooks/org_events.py`'s `on_env`), rendered into `organisation.html`'s
event timeline and `hooks/footnote_fragments.py`'s footnote links — same
render-time-derived, never-stored-in-frontmatter pattern as everything
else in this file. Not yet built; this appendix is the design record, not
an implementation.

**Consistent with this repo's own working philosophy** (see Appendix D's
"Why not now" above, and how the `evidence`/`archive` CSL-JSON fields
themselves shipped in DOD's own tooling well before any upstream
conversation was even considered): ship the private, additive convention
first, let it see real use, and only look at a formal OpenURL
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
