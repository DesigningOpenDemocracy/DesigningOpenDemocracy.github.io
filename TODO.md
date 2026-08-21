# TODO

Everything mechanically fixable is done. Remaining items need editorial judgment.
Counts verified 2026-08-21 against `check_event_sourcing.py`, `check_footnote_quotes.py`,
and `check_concepts.py`.

## Hard leftovers (require research or judgment calls)

- [ ] 0 NOTABLE NO PROOF events (down from 43 when this list started) — backlog clear
  as of 2026-08-21. The last one (Governance Hub Africa's unverifiable 2018 founding
  claim) was replaced with a sourced April 2026 partnership event instead.
- [ ] 0 WEAK URLs (was 7) — the last one (Prediki's 2012 launch) now cites a dated
  Wayback snapshot bracketing the launch instead of the bare homepage
- [ ] 27 footnote citations without machine-verifiable quotes (129/156 have them):
  - folio.org.au — site unreachable to scripts (5 footnotes)
  - multi-source footnotes — parser deliberately treats these as citation-only until
    split one-citation-per-footnote (loomio, taiwan-post, china, russia, …)
  - books/journal articles with no URL to verify against (hennig, theatre, …)
  - internal DOD references (demos, join-gov-tw)
- [ ] 4 orphaned concepts — not referenced by any org's `concepts:`:
  employee-stock-ownership-plans, equity-compensation-plans, utopian-realpolitik,
  what-is-democracy

## Done

- Issue #139 closed (event sourcing backlog: quote mismatches + proof_warning events)
- NOTABLE NO PROOF 43→12→2; WEAK URLs 7→2→1; orphaned concepts 7→4
- Footnote quotes backfilled: 44/62 → 129/156
- 0 unsourced events, 0 no-proof events, 0 proof_warning events across 334 events
