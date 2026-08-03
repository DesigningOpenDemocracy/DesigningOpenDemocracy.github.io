# Community Strong Australia — watch, not yet scoreable

## What was asked

A DOD member reading the [Party Governance Comparison](../docs/projects/au-party-governance-comparison.md)
wondered why no right-wing party scores well on either internal governance
or external reform advocacy, and specifically asked about a new party from
the "Teal movement" called Community Strong.

## What was found

**Community Strong Australia (CSA) is not right-wing.** Wikipedia describes
it as a centrist party formed in 2026 by Zali Steggall and Allegra Spender —
"teal independents," a term for centrist/independent politicians who found
electoral success in seats with a history of Liberal representatives. Teals
are generally progressive on climate and integrity, more small-l-liberal/
centrist on economics; not a right-wing formation. Notably, Wikipedia's own
"See also" for CSA links to **Australian Democrats** and **Centre
Alliance** — both already in the comparison dataset — suggesting real
thematic kinship (evidence-based, integrity-focused, centrist reform
politics), not a right-wing angle.

Timeline per Wikipedia (`Community Strong Australia`, checked 2026-08-02):
- May 2026: Steggall, Spender, and ACT senator David Pocock confirmed
  discussions about forming a new party. Pocock later said he would not
  join.
- 25 June 2026: party named "Community Strong Australia."
- Policies per Steggall: housing affordability, cost of living, climate
  change, childcare, education, healthcare, social cohesion — general
  policy positions, not a stated governance-reform program.
- Wikipedia's "Members of Parliament" section for the party is empty as of
  this check — the founding MPs appear to still be sitting as independents,
  not formally under the CSA banner yet.

## Why it's not in party-governance.json yet

No internal governance structure has been documented anywhere (how members
would select leadership, whether policy is put to member vote, what if any
binding-mandate mechanism exists) — the party is about six weeks old at
time of writing. Scoring `internal_governance` or `external_reform` right
now would mean guessing rather than sourcing, which breaks the standard
the rest of that page holds to.

**Revisit when:** the party publishes a constitution/governance document,
elects MPs formally run under its own banner, or produces enough of a
track record to source real notes+citations per dimension, matching the
schema every other entry on the comparison page uses.

## Related: the right-wing question itself

Separately, added the **Libertarian Party** (formerly Liberal Democratic
Party) to the comparison specifically to test whether the "no right-wing
party scores well" pattern is a real finding or a research gap — it's
philosophically distinct from the populist-right cluster already on the
page (Liberal, One Nation, Katter's): classical-liberal/libertarian,
small-government, not populist-establishment. Result: the pattern holds.
Its platform's only accountability-adjacent plank is opposition to mass
surveillance/digital IDs; everything else is deregulation and (recently)
culture-war positions, not electoral reform/anti-corruption/transparency
as the framework's `external_reform` axis defines it. It does score
slightly better than the populist-right cluster on `internal_governance`
(3 vs. ~1-2), on the strength of one genuinely documented member ballot —
the 2023 rebrand vote to "Libertarian Party" after the long-running name
dispute with the Liberal Party. See its `scoring_note` field in the data
file for the full reasoning.

No framework-notes-worthy friction surfaced here — this reads as a
genuine substantive finding (right-of-centre Australian parties, across
ideological flavors surveyed so far, frame "reform" as deregulation/
smaller government rather than participatory or accountability-mechanism
reform) rather than a gap in how the framework's `external_reform` axis is
worded. Worth another look if/when a right-of-centre party with an actual
transparency/anti-corruption/electoral-reform platform turns up.
