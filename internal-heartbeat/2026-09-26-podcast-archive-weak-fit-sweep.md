# Sweep: weak-fit orgs across DOD's podcast/event archive

## What prompted this

Following the Anitra Nelson / Informal Urbanism Research Hub case (see the
sibling note in this folder and `orgs-not-included.md`'s new "Weak-fit
watch list" section), the user asked to sweep DOD's own event/podcast
archive for other organisations DOD has genuinely interacted with — a
speaker's employer, a co-host — that are a weak-not-zero fit for the
Democracy Landscape and haven't been logged anywhere.

## Method

Reviewed every post tagged `podcast` or `event` (by category or filename),
2016–2026 — 18 posts total. For each named institutional affiliation of a
guest, panellist, or co-host, checked whether it already has a
`docs/organisations/` page. Where it didn't, assessed the org's own
self-description (fetched directly, not summarized, where a live site
exists) against the Accountability Framework's bar: "working on *how*
people participate in governance — mechanisms, structures, reforms,
accountability systems."

## Already covered — no gap

These came up repeatedly but already have Landscape pages, so no action:
Flux Party, Pirate Party Australia, MosaicLab, Lateral Economics, 888
Co-operative Causeway, Cooperative Bonds, MiVote, Coalition of Everyone,
newDemocracy Foundation, RadicalxChange Foundation, vTaiwan, Earthworker
Cooperative.

## Considered and skipped (not logged anywhere)

- **Andrew Kay / "Angry Aussie" YouTube channel** ([2019-12-11
  podcast](../docs/blog/posts/2019-12-11-podcast.md)) — a personal
  political-commentary channel, not an organisation working on governance
  mechanisms. Zero fit, no real judgment call, so per `orgs-not-included.md`'s
  own convention it doesn't need a row anywhere.
- **Swinburne University** (Bridgette Engeler's employer, [2023-01-21
  podcast](../docs/blog/posts/2023-01-21-podcast.md)) — she's an individual
  academic ("torments MBA students") with no specific named research centre
  given, unlike Anitra Nelson's InfUr-. Logging an entire university on one
  employee's say-so is too broad to be a meaningful watch-list entry — skip
  unless a specific unit is ever named.

## New entries added to the weak-fit watch list

All four below are logged in `orgs-not-included.md`'s "Weak-fit watch list"
table, linking back to this section.

**Write In Stone** ([writeinstone.com](https://www.writeinstone.com)) —
founder Austin interviewed by DOD, [2021-08-08
podcast](../docs/blog/posts/2021-08-08-podcast.md). A journalism-transparency
startup: shows a reporter's research process, not just the finished
article, on the premise that informed public participation needs
trustworthy information. Adjacent to DOD's interest in collective
intelligence and information ecosystems, but its centre of gravity is
journalism/media tooling, not governance-mechanism design. Weak-not-zero.

**Open Source Industry Australia (OSIA)**
([Wikipedia](https://en.wikipedia.org/wiki/Open_Source_Industry_Australia))
— Alexar Pendashteh, a recurring DOD co-organiser/host across many episodes,
is a director there ([2019-12-11
podcast](../docs/blog/posts/2019-12-11-podcast.md) describes him as "then
director of Open Source Industries Australia"). OSIA is an industry body
promoting FOSS adoption and public policy support for the open-source
sector — real overlap with DOD's civic-tech interest (open-source values,
transparency), but its actual mission is industry advocacy for open-source
businesses, not democratic participation mechanisms. Weak-not-zero, and
worth tracking given how central Pendashteh has been to DOD itself.

**Action Foresight**
([actionforesight.net](https://actionforesight.net/)) — Jose Ramos's
foresight/futures consultancy, panellist at the [2023-01-21 Basil's Table
event](../docs/blog/posts/2023-01-21-podcast.md) ("wealth concentration as a
governance problem"). Foresight/futures-studies methodology work for
governments, agencies and communities — genuinely adjacent to governance
(helps institutions plan and adapt) but its own description frames it as a
futures-thinking practice, not a governance-mechanism or accountability
body. Weak-not-zero.

**Small Giants Academy**
([smallgiants.com.au](https://www.smallgiants.com.au/about)) — co-host of
the [RadicalxChange Melbourne launch](../docs/blog/posts/2026-08-07-radicalxchange-melbourne.md)
and host of the Wisdom & Action Forum where Audrey Tang spoke on "Trust by
Design: Digital Democracy in the Age of AI." A not-for-profit leadership
academy ("the business, social and political leaders we need in the Next
Economy") — real, repeated interaction with DOD's civic-tech orbit through
its events, but its own mission is leadership development/education, not
governance-mechanism work itself. Weak-not-zero.

## Flagged separately: two candidates that may be more than "weak"

These read as closer to a genuine landscape fit than the four above —
flagging for an explicit decision rather than unilaterally adding a full
`docs/organisations/` page, since that's a bigger commitment (accurate
contact info, concepts, precise summary) than a watch-list row.

**Bank Australia** — Rowan Dowland (Bank Australia's Head of Strategy and
Planning) was the main speaker at [Basil's Table's inaugural
event](../docs/blog/posts/2020-02-20-podcast.md), 2020. Australia's first
cooperative bank (est. as a credit union in 1957, cooperative bank status
2011, renamed 2015): one-member-one-vote governance, part of the Global
Alliance for Banking on Values, and Dowland co-founded the Business Council
of Co-operatives and Mutuals. This looks structurally comparable to
already-included cooperative orgs (888 Co-operative Causeway, Cooperative
Bonds, Earthworker Cooperative) — arguably a stronger fit than the four
above, not just weak-not-zero.

**Cohousing Australia**
([cohousingaustralia.org.au](https://www.cohousingaustralia.org.au/about))
— the national network for the cohousing movement (people co-designing and
collaboratively governing shared living spaces). Elena Pereyra, a panellist
at the [2023-01-21 event](../docs/blog/posts/2023-01-21-podcast.md), framed
her own work explicitly as "collective housing as a model for collective
governance." A non-profit that explicitly advocates for and coordinates a
movement, not just a research lens on it (contrast with InfUr-, which is
academic research rather than movement advocacy/coordination) — also reads
as a stronger candidate than a plain weak-fit watch entry.

## Update: both promoted, 2026-09-26

The user confirmed both should get full pages. Added
[`docs/organisations/bank-australia.md`](../docs/organisations/bank-australia.md)
and [`docs/organisations/cohousing-australia.md`](../docs/organisations/cohousing-australia.md)
the same day, sourced directly (Bank Australia's own site + the Wikipedia
extracts API for its history; CoHousing Australia's own site for its
structure and mission) rather than from the podcast transcripts alone.
Removed both rows from `orgs-not-included.md`'s weak-fit watch list per the
README's promotion convention. `reorder_frontmatter.py`,
`check_event_sourcing.py --calculate`, `check_footnote_quotes.py`,
`check_internal_links.py` and a full `mkdocs build --strict` all pass
clean.

Bank Australia's page notes an open governance question of its own — its
2025 mergers (Qudos Bank, Australian Unity) and a further one under
exploration (P&N Bank) raise whether one-member-one-vote control survives
consolidation at that scale. Worth a recheck alongside its `last_checked`
date rather than assumed settled.

CoHousing Australia has no confirmed founding date (checked its own site;
not stated) — its page has no `events:` frontmatter as a result, which is
fine per convention (`events:` is optional), but worth filling in if a
founding date ever surfaces.

## Update: Cohousing Australia reverted, same day

On a second look, prompted by the user asking two follow-up questions —
whether this reading of the framework was getting too loose, and whether
the entry was actually useful to DOD's readership — Cohousing Australia's
promotion doesn't hold up on either count, while Bank Australia's does:

- **Framework fit**: CoHA's own self-description leads with advocacy for a
  housing model ("advancing resident-driven collaborative housing"); the
  "collective governance" framing used to justify the page was Elena
  Pereyra's own gloss on her work, not CoHA's self-description. That's a
  weaker case than Bank Australia's AGM one-member-one-vote mechanism,
  which is squarely governance-mechanism work in CLAUDE.md's own terms.
- **Readership usefulness** (a second, separate gate this session's
  discussion led to formalising in `CLAUDE.md`'s Organisation pages
  Curation standard bullet): Bank Australia is actionable for DOD's
  audience (switch banking to a democratically-governed institution, at
  real scale) in a way Cohousing Australia isn't — its practical hook
  (find/start a cohousing community) serves a housing-movement interest
  more than a democracy-movement one.

`docs/organisations/cohousing-australia.md` was removed and the entry
restored to `orgs-not-included.md`'s weak-fit watch list, with both
reasons noted there. Bank Australia's page stands unchanged.
