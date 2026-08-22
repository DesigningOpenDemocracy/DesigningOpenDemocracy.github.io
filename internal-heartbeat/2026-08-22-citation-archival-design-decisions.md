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
   — i.e. `docs/data/event-evidence-cache.json`, already committed,
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

Neither renders anywhere on the site. Nobody had reconciled that there
were two.

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

**`event-evidence-cache.json` stays the one internal source of truth.**
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
without needing to know `event-evidence-cache.json` exists. Populate the
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
   add `url-status` to `event-evidence-cache.json`'s schema, loosen
   `_collect_items()`'s quote-only filter if full coverage is wanted.
2. Build the `citations.json` projection (`archive`/`archive_location`/
   `url-status`) + rendering (timeline, footnote fragments, cards).
3. Wire verification fallback + DEAD-verdict suggestions.

Tests alongside each piece, per repo convention (`tests/` already covers
`check_fragments.py`'s cache-handling paths — extend rather than
duplicate).

## Status

Design converged in conversation with the maintainer this session. Not yet
implemented. Task 1 (horizon-state.md provenance notes) and the CI fix
(digital-rights-watch.md footnote reflow) from the companion handoff entry
are both pushed to PR #183 (open, CI green, not yet merged as of this
writing). This design itself has not started implementation — next
session should build per the sequencing above, once #183 lands.
