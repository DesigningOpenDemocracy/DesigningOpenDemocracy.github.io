# 2026-08-22 — citation-archival design: settled shape

Follow-on to `2026-08-22-citation-archival-handoff.md` (Task 2). That entry
preserved the prior session's open sketch and four open questions. This
entry records the actual design conversation with the maintainer
(mofosyne) that resolved them — and it lands somewhere much narrower than
the original sketch, because it turned out this repo already has half the
infrastructure built and just never wired it up.

## Conclusion up front

**No new frontmatter fields on `events:`, footnotes, or `shared_link:`.**
Archival status is a fact about a *URL*, not about which citation happens
to reference it — the same original source can be cited by an event on one
org page and a footnote on another, and they must not be allowed to
disagree about whether it's archived. That argues for a URL-keyed lookup,
not per-citation fields, and this repo already has one.

## What was already there, half-built, undiscovered until this session

Two independent, uncoordinated places already write Wayback archive URLs:

1. **`util/check_fragments.py --save-to-wayback`** (the real, documented,
   actively-used one) writes directly into the per-URL evidence cache:
   ```python
   cache[url] = {**cache.get(url, {}), "archive_url": archive_url,
                 "archive_checked": date.today().isoformat()}
   ```
   — i.e. `docs/data/citation-evidence.json`, already committed,
   already the file the weekly heartbeat cron and `manual_dump.py` key off.

2. **`util/citations_tool.py --augment --archive`** (built, wired, **never
   actually run**) independently calls Wayback itself and writes into
   `docs/data/citations.json` using real CSL-JSON standard fields:
   ```python
   cite["archive"] = "Internet Archive Wayback Machine"
   cite["archive_location"] = archive_url
   ```
   `hooks/citation_export.py`'s `on_pre_build` even carries these two
   fields forward across rebuilds specifically so they'd survive
   regeneration. Checked the committed file: **0 of 328 entries have
   `archive_location` set.** This path exists in code and has never been
   exercised.

**Correction, made during implementation (same session):** the line that
originally stood here — "Neither renders anywhere on the site" — was
wrong, from searching for the wrong string (`archive_location`) in
`docs/overrides/*.html` instead of the actual naming used. Mechanism 1's
data (`archive_url`) was, in fact, **already rendered**: `hooks/
org_events.py` had an `archive_url_for` Jinja filter and
`organisation.html` already showed a "🗃️ Archived copy" button for
events; `hooks/footnote_fragments.py` did the same for footnote
citations. Both were genuinely built and shipped, just fed by Mechanism 1
— which is why Mechanism 2's `citations.json` fields stayed empty:
nothing was rendering from them, so nobody noticed they were never
populated. What was actually still missing, once this was found: a
liveness/`url_status` field (neither mechanism had one), the
Wikipedia-style primary-link swap, and reconciling the two write paths.
See the "2026-08-22" entry in `internal-heartbeat/
machine-verifiable-citation.md`'s changelog and the implementation itself
(same-day, this PR) for what was actually built once this was corrected.

## Wikipedia's model (Help:Citation Style 1, pulled via API, not memory)

- `archive-url=` stores a full, pre-resolved URL — not a timestamp to
  reconstruct from — because they support multiple archive providers, not
  just Wayback. This overturned an earlier idea in this session (store just
  a Wayback timestamp, derive the link at render time) — not future-proof
  if DOD ever needs a second provider for a site Wayback won't capture
  (`manual_dump.py` already exists as exactly that kind of escape hatch).
- `archive-date=` is display-only, never used to construct the link.
- `url-status=` enum: `live` / `dead` (implicit default once an archive
  exists) / `unfit` / `usurped` / `deviated`. Default *rendering* links the
  archive as primary once one exists, demoting the original to a small
  "Archived from the original on `<date>`" trailer — not "original stays
  primary until proven dead." Their reasoning: a frozen snapshot is a more
  trustworthy long-term reference than a live page that can change under
  the citation without anyone noticing.
- `deviated` — page still resolves fine, but content changed and no longer
  supports the cited claim. DOD has no name for this today; only
  `check_fragments.py`'s quote verification would ever catch it (a
  liveness check like `check_event_urls.py` would call it healthy).

## Settled architecture

**`citation-evidence.json` stays the one internal source of truth.**
Only `check_fragments.py` (via `--save-to-wayback`) ever talks to Wayback
and writes `archive_url`/`archive_checked`. `citations_tool.py`'s
independent `--archive` path should be retired or repointed to read from
this cache rather than calling Wayback a second, uncoordinated way — this
is what actually closes the two-writers-disagreeing gap found above.

Add one field the cache doesn't have yet: a liveness/status flag. Keep the
enum small and honestly automatable rather than adopting Wikipedia's full
five states on day one:
- `live` (default/unset)
- `dead` — `check_event_urls.py` can already detect this automatically
  (404/5xx)
- `unfit` — **not machine-detectable with current tooling.** A parked
  domain returns a normal HTTP 200; the horizon-state.com case this
  session was caught by a human reading the page, not a script. Stays a
  manually-set value for now (same precedent as
  `proof_level_locked: true` elsewhere in this repo — a human override the
  automation doesn't fight).
- `deviated` deferred — no detector for it exists yet either; revisit once
  the basic plumbing is in.

**`citations.json` becomes a generated, read-only, standards-shaped
*projection* of that cache** — not a second thing anyone writes to
directly. This is the file CLAUDE.md already documents as
"linked from the bottom of the org index table for researcher download,"
so it's the right place for an external consumer to get a self-contained
answer ("is this a known-dead link, and if so where's the fallback")
without needing to know `citation-evidence.json` exists. Populate the
real CSL-JSON `archive`/`archive_location` fields (already plumbed, just
empty) plus one small DOD extension field, `url-status`, mirroring the
`evidence` array's own precedent as a DOD addition on top of standard
CSL-JSON.

**Rendering** (`organisation.html`'s timeline, `hooks/footnote_fragments.py`,
shared_link/event cards): show an archive link only when one exists for
that citation's URL (no dead "[archive snapshot]" buttons); once
`url-status` is anything but `live`, link the title to the archive and
demote the original to a small trailer, matching Wikipedia's default
rather than the earlier "original always primary" sketch — this also
solves the `#:~:text=` fragment-consistency problem flagged earlier in the
conversation for free, since verification and rendering then always target
the same page.

**Verification fallback**: `check_fragments.py`/`check_event_urls.py`
should fall back to `archive_url` when the live fetch is confirmed dead,
and a `check_event_urls.py` DEAD verdict should *propose* setting
`url-status: dead` in the cache (print a suggestion) rather than
auto-flipping it — same human-in-the-loop precedent as `proof_level`'s
`--calculate`/`--recalculate` split.

## Known gaps, deliberately not solved in this pass

- `citation_export.py`'s `_collect_items()` only exports citations with a
  `quote:` — an event sourced only by `note:` or `proof_warning: true`
  gets no `citations.json` entry at all today, so it wouldn't get
  archive/dead-link tracking either. Loosening that filter (empty evidence
  array is fine) is needed if "any DOD citation" is the actual goal, but
  is a separate, smaller change from the above.
- `unfit`/`deviated` detection has no automated path yet — noted above,
  not blocking the rest of the design.

## Recommended sequencing

1. Reconcile the two writers (retire/repoint `citations_tool.py --archive`),
   add `url-status` to `citation-evidence.json`'s schema, loosen
   `_collect_items()`'s quote-only filter if full coverage is wanted.
2. Build the `citations.json` projection (`archive`/`archive_location`/
   `url-status`) + rendering (timeline, footnote fragments, cards).
3. Wire verification fallback + DEAD-verdict suggestions.

Tests alongside each piece, per repo convention (`tests/` already covers
`check_fragments.py`'s cache-handling paths — extend rather than
duplicate).

## Status

Design converged in conversation with the maintainer, and — after the
maintainer asked to implement rather than wait for a separate merge —
**built the same session**, on the same branch/PR (#183):

- `util/text_fragment.py`: `load_archive_info()` (returns `{url:
  {"archive_url":, "url_status":}}`), `load_archive_urls()` kept as a
  back-compat wrapper.
- `util/check_fragments.py`: `--set-url-status <url> <dead|unfit|live>`,
  writing/clearing `url_status` in `citation-evidence.json`. Never
  auto-called by anything.
- `util/check_event_urls.py`: prints a suggested `--set-url-status ... dead`
  command on a fresh `DEAD` verdict; does not write it itself.
- `hooks/org_events.py` / `docs/overrides/organisation.html`: the
  `archive_url_for` filter became `archive_info_for`; the event timeline
  now flips to Wikipedia-style primary-link-is-the-archive once
  `url_status` is `dead`/`unfit` and an archive exists, demoting the
  original to a plain "(original, no longer live: ...)" trailer.
  Confirmed end-to-end against real horizon-state.md data in a local
  build (temporarily injecting a test cache entry, then reverting it —
  never committed).
- `hooks/footnote_fragments.py`: same swap for prose footnote citations.
- `hooks/citation_export.py`: `citations.json`'s `archive`/
  `archive_location`/`url-status` are now a **read-only projection** of
  the evidence cache, generated fresh every build — replacing the old
  carry-forward-from-previous-output logic that let `citations_tool.py
  --archive`'s independent write path silently diverge.
- `util/citations_tool.py`: `--archive` documented as discouraged on
  DOD's own `citations.json` (would just be overwritten by the next
  build); still valid for a third-party file via `--file`.
- Tests: `tests/test_text_fragment.py` (`LoadArchiveInfoTests`, 6),
  `tests/test_footnote_fragments.py` (new file, 6 — covers live-additive,
  dead-swap, unfit-swap, no-archive, status-without-archive, and
  `live`-clears-back-to-default), `tests/test_check_fragments.py`
  (`SetUrlStatusCliTests`, 6), `tests/test_citation_export.py` (new file,
  5 — including a regression test that a stale prior `citations.json`
  entry does NOT survive when the evidence cache disagrees, which is the
  exact bug this change fixes). 258 tests passing total (was 235 at
  session start). `mkdocs build --strict` passes; a full local build
  before/after a temporary real-data injection confirmed the rendering
  end-to-end, then the injection was reverted before committing.
- CLAUDE.md: new "Citation archival: Wayback links and url_status"
  section, plus updates to the Hooks list, Data exports table, and the
  `check_fragments.py`/`check_event_urls.py` utility-script entries.
- `internal-heartbeat/machine-verifiable-citation.md`: Appendix C
  changelog entry recording the fix and why it was needed.

Not done in this pass (see "Known gaps" above): loosening
`citation_export.py`'s quote-only `_collect_items()` filter, and any
automated `unfit`/`deviated` detection (neither has a workable detector
yet). No real Wayback captures exist for any DOD citation as of this
writing — the whole feature is built and tested but dormant until
someone actually runs `check_fragments.py --save-to-wayback` for real.
