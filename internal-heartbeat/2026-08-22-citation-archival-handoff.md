# 2026-08-22 — citation-archival design handoff

## What happened

A prior session left a handoff for continuing work on this repo. This entry
preserves it so it survives outside chat history. No code changes shipped in
that handoff itself — it's a starting point for the next session.

## Verified state at handoff time

- `main` @ `2aedb97`, clean tree, all prior verification-workflow work pushed
  (`6e12d0c`: `.pagecache/`, manual-dump PDF imports, paren-space quote
  matching).
- Tests: `venv/bin/python -m unittest discover tests` → 235 passing. Use the
  venv python — system python lacks pdfminer/requests-era deps (PEP 668
  blocks pip).
- Full offline evidence corpus verifies clean: 299 events + 115 footnotes +
  2 shared links, 0 bad (`util/check_fragments.py --offline`, ~0.4s).
- A separate incoming PR (not this session's work) only added tests; the
  post-pull state was independently re-verified — suite green, nothing
  broken. No further action needed there.

## Task 1 — small, maintainer half-approved

In `docs/organisations/horizon-state.md`, the two events repointed to
Wayback captures (`hst-faq`, `hst-token` — domain now parked) should get
provenance notes, e.g.:

```yaml
note: "Originally published at horizonstate.com/hst-faq/ — domain since parked."
```

Maintainer said "a note would make sense somewhat" — confirm wording with
them or just add it and let PR review gate it. Keep the frontmatter field
order canonical (pre-commit hook enforces it via `util/reorder_frontmatter.py`).

## Task 2 — main event: citation-archival convention (DESIGN FIRST)

The maintainer floated a general citation-archival convention and asked for
honest push-back; no decision was made. **Do not build without discussion.**

Maintainer's sketch:

- Keep `url:` always pointing at the ORIGINAL source.
- Add per-citation `archive_url:` (last known Wayback snapshot).
- Add `archive_state:` flipped when a domain dies (dead ⇒ archive becomes
  primary).
- Render an "[archive snapshot]" secondary link next to citations site-wide.

### Prior analysis (re-derive only if needed)

**For:** preserves provenance; readers always have a rot-proof fallback;
matches Wikipedia reference style; genuinely better than status quo for
LIVE-but-rottable citations (which this landscape has many of).

**Against / costs:**

- Every verifier fetches `url:` today — two URLs force rules about which
  gets fetched when. Suggestion: `archive_state=dead` ⇒ fetch `archive_url`
  only; alive ⇒ fetch `url:`, archive is mirror-only.
- `#:~:text=` fragments derive from `quote:` + `url:` at build time, so the
  fragment must target whichever URL verification actually checked — else
  readers get highlighted text that wasn't the verified text.
- `check_event_urls.py` DEAD verdicts should probably propose/flip
  `archive_state` rather than just alarm.
- Rendering touches `organisation.html`'s timeline, `hooks/footnote_fragments.py`,
  shared_link cards, and the data exports.
- The sticky-blocked evidence cache keys by URL — two URL spaces need
  thought (which URL is the cache key when both exist?).

### Open questions to put to the maintainer before building

1. Scope: `events:` only? Or also prose footnotes and `shared_link:`?
   Footnotes have no structured fields today (freeform markdown) —
   per-footnote `archive_url` may be impractical there.
2. Who creates captures: manual `--save-to-wayback` runs, or automated
   capture on first citation? (Politeness/robots implications differ.)
3. Does "[archive snapshot]" render for EVERY link or only ones with a
   recorded `archive_url`? (Every-link rendering without a stored capture
   is a dead button.)
4. Is `archive_state:` per-event, or derivable (e.g. auto-flip on a DEAD
   verdict from `check_event_urls.py`)?

### Recommended sequencing if approved

1. Schema + hook/template rendering first.
2. Verification-path changes second.
3. Automation last.

Add tests alongside each piece per repo convention. Update the relevant
`CLAUDE.md` sections as each piece lands.

## Gotchas learned in the prior session (not all obvious from CLAUDE.md)

- `parliament.vic.gov.au` robots.txt disallows ALL bots site-wide
  (`User-agent: * Disallow: /`) — never script-fetch it; its VEC response
  PDF lives only via manual snapshot/Wayback. `robots_allowed()` can
  transiently return `True` if the robots fetch itself fails
  (allow-everything fallback) — retest before trusting a green result.
- archive.org rate-limits hard (429) on rapid availability-API calls; sleep
  ~20s+ between calls.
- Firefox "Save Page As" often yields nav-only shells on SPAs
  (`science.org`) — print-to-PDF is the reliable save, and
  `import_manual_dump.py` handles PDFs now.
- `manual-dump/import.json` is local-only (gitignored); rebuild with
  `--rebuild-map` if it drifts from `imported/`.

## Status as of this entry

Task 1 not yet applied. Task 2 not yet discussed with the maintainer —
next session should raise the four open questions above before writing any
code.
