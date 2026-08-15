# AU parties follow-up: Greens added, Labor/JLN assessed as a lower tier

**Status:** Follow-up to `2026-07-31-au-parties-democracy-reform-assessment.md`. One
part of that entry has now shipped; the rest is recorded here as reasoning for a
future session, not a public statement.

## What happened

The 2026-07-31 entry left three options on the table for the Australian Greens,
explicitly deferred to the human founder given the precedent question (a
general-purpose party's partial governance-reform record vs. a single-issue party
like Pirate Party Australia, whose whole platform is reform). The founder chose
Option 2 — add the Greens only — in an interactive session on 2026-08-15.

**Shipped:** [`docs/organisations/australian-greens.md`](../docs/organisations/australian-greens.md)
(commit `72f4508`, plus a CI line-wrap fix in `7b4d574`). Every event was sourced
directly against `greens.org.au` primary documents and mechanically verified with
`check_fragments.py` (4/4 events good, 0 mismatches) — a stricter bar than the
original three-agent research pass, after that same session found and fixed two
overclaimed citations on an unrelated page (McKinnon) and the founder pushed for
the same rigor here. The page carries an explicit "Position and caveats" section
matching the Australian Democrats page: inclusion is for the sourced
governance-mechanism record, not the party's broader platform, which DOD does not
track or endorse.

`docs/data/party-governance.json`'s existing Greens entry was cross-linked to the
new page (`dod_page` field + a source citation on its latest history entry) —
same pattern already used for Pirate Party Australia and the Australian Democrats.

## Follow-up question: who else clears the bar?

The founder asked directly whether any other party from the original research sits
in the same tier as the three now in the Landscape. Re-checking the actual
`external_reform` scores in `party-governance.json` (not just the qualitative
verdicts) showed a clean numeric break, not just a vibe:

| Party | `external_reform` | In Landscape? |
|---|---|---|
| Pirate Party Australia | 9.0 | Yes |
| Australian Greens | 8.0 | Yes (this entry) |
| Australian Democrats | 7.0 | Yes |
| — gap — | | |
| Labor (ALP) | 4.0 | No |
| Jacqui Lambie Network | 4.0 | No |
| Liberal Party / Coalition | −3.0 | No |
| One Nation | −6.0 | No |

The three currently-included parties cluster at 7.0–9.0. Labor and JLN are tied at
4.0, a full 3 points below the floor of that cluster — and the qualitative story
matches the number: PPAU/Greens/Democrats each have a *sustained, multi-front*
record (several distinct reforms/campaigns over years), whereas:

- **Labor** did legislate the NACC Act itself outright (a stronger single action
  than the Greens' amendments-only role) — but it's actively undercut by its own
  conduct: Transparency International Australia and the Centre for Public
  Integrity jointly criticised the "exceptional circumstances" public-hearings
  threshold as too restrictive (25+ hearings held, zero public as of Dec 2025 per
  the original research), and Andrew Leigh has publicly criticised Labor's own
  preselection "factional duopoly." A real external win sitting next to a live
  internal-accountability critique, not a clean case.
- **Jacqui Lambie Network** has a genuinely sustained record of specific,
  on-the-record criticism of integrity-body design since 2018 across two different
  governments' proposals — but the original research flagged a real gap: its
  claimed donations-disclosure bill was never independently verified against
  parliamentary records, just asserted on the party's own site.

**Working conclusion (provisional, not a rule):** the current de facto threshold
for a general-purpose party sits somewhere around `external_reform` 7.0 with a
multi-front, not-just-one-bill record. 4.0 reads as "genuine but not enough,"
not "borderline yes." Nothing here changes the decision not to add Labor or JLN
right now.

**Worth naming separately: Reason Party.** Arguably the single strongest concrete
legislative win in the whole original batch — Fiona Patten personally negotiated
Victoria's 2018 donations-reform bill into law (capped donations, banned foreign
donations, dropped the disclosure threshold from $13,500 to $1,000) — stronger on
the merits than the Greens' amendments-only NACC role. But the party voluntarily
deregistered with the VEC in March 2024 and can't re-register under a similar name
before the 2026 Victorian election. There's no live entity to track; noted here so
a future session doesn't re-derive this and then hit the same dead end.

## If this comes up again

Before adding Labor or JLN (or reopening this), re-verify the specific claims
above against a primary source directly fetched and quoted — the original
2026-07-31 research was three parallel general-purpose agents, not held to the
fetch-and-quote-verify standard now being applied (see the McKinnon page's commit
history the same day for what that standard catches: claims that are plausible,
repeated across secondary sources, and still don't trace to a source that actually
says them).
