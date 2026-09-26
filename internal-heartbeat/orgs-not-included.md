# Organisations considered and not included

A running registry of organisations someone proposed for the Democracy
Landscape that were assessed against the [Accountability
Framework](../docs/projects/accountability-framework/index.md) and judged
not to fit — kept so the same org doesn't get re-litigated from scratch
by a future session (human or AI) with no memory of why it was passed
over. This is the opposite list from the org index: an included org's own
page under `docs/organisations/` is its own record of having cleared the
bar, so this file only tracks the *no*s.

Not a final-forever list — the framework itself is revisable (see
`CLAUDE.md`'s note that any foundational document, including the
framework, "can be proposed for change by any contributor, human or AI"),
and an org's own behaviour can change too. Re-evaluate rather than
treating an entry here as permanently settled, especially if the stated
reason ("centre of gravity is X, not Y") stops being an accurate
description of the org.

Only borderline calls get logged here — not every org anyone has ever
mentioned in passing. If an org was obviously out of scope with no real
judgment call involved, it doesn't need a row.

## Rejection types

A closed-ish vocabulary mirroring the framework's own structure: the
three disqualifiers, plus its two explicit scope-exclusions. Feel free to
add a new value if none of these honestly fit a future case — same spirit
as `ai_assist:`/`origin:` in `CLAUDE.md` — but check first whether an
existing one already covers it before minting another.

| Type | Meaning |
|---|---|
| `human-rights-observatory` | Centre of gravity is documenting/campaigning against rights violations, not designing, reforming, or overseeing governance mechanisms. The "DOD is not a human rights observatory" scope line. |
| `coercive-interference` | Primary mode is external coercive pressure (sanctions, regime change, imposed governance models) rather than analysis/engagement. |
| `hypocrisy` | Claims to govern for the people while structurally serving a different interest. Disqualifier 1. |
| `bad-faith` | Performs democratic process without genuine intent, incl. legitimacy theatre. Disqualifier 2. |
| `structural-inflexibility` | Can't reform itself, or suppresses the organisations holding it to its own standards. Disqualifier 3. |
| `out-of-scope` | Doesn't engage governance/participation mechanisms at all — catch-all for orgs with no real disqualifier at play, just no fit. |

## Reasons (sub-tags, nested under a type)

The specific *why* within a `Type` category. Same open-vocabulary spirit —
add a new one when needed, reuse an existing one when it already fits.
Only `human-rights-observatory` has entries so far; other types will grow
their own reasons as real cases show up rather than being pre-guessed here.

| Reason | Under type | Meaning |
|---|---|---|
| `documentation-only` | `human-rights-observatory` | Org's output is research/reporting on violations, with no advocacy for a specific mechanism or structural reform. |
| `campaign-only` | `human-rights-observatory` | Org organises public pressure (petitions, letter-writing, protest) but doesn't work on mechanism design or oversight structures. |
| `marginal-mechanism-work` | `human-rights-observatory` | Org does some governance-mechanism work (e.g. legislative submissions) but it's a minor activity inside a mandate whose centre of gravity is documentation-and-campaigning. |

## Registry

| Org | Country | Date considered | Type | Reason | Notes |
|---|---|---|---|---|---|
| [Amnesty International (Australia)](https://www.amnesty.org.au/) | AU | 2026-08-21 | `human-rights-observatory` | `marginal-mechanism-work` | [Full reasoning](2026-08-21-amnesty-international-not-included.md) |
| [Forensic Architecture](https://forensic-architecture.org/) | GB | 2026-08-21 (recorded retroactively — a DOD member recalled this being rejected previously, no prior written record found) | `human-rights-observatory` | `documentation-only` | [Full reasoning](2026-08-21-forensic-architecture-not-included.md) |

## Weak-fit watch list

A separate, distinct list from the registry above. The registry above is a
settled *no* — assessed and declined. This one is for organisations whose
fit is genuinely weak-not-zero: some relevance to self-governance or
participation, but not clearly "working on *how* people participate in
governance" the way a landscape entry needs to be, so not worth a page
yet — without being a clean `out-of-scope` miss either. Not a rejection,
so it doesn't get a `Type`/`Reason` from the vocabulary above; it's an
open call, logged so it isn't silently forgotten.

Only logged when both are true: (1) DOD has had a genuine interaction with
the org — hosted them, cited their work, one of their people spoke at a
DOD event — not just "this org sounds vaguely adjacent"; and (2) the fit
is weak-not-zero, not a clear miss (a clear miss with an interaction still
goes in the registry above as usual, just with a note on how DOD
encountered it). The interaction is what makes this worth tracking at
all: a speaker's or co-host's own institutional home is the kind of thing
that accumulates evidence over repeat encounters in a way a stranger's org
never will, and losing that thread each time is the failure mode this
list exists to prevent.

The underlying bet is Granovetter's [strength of weak
ties](https://en.wikipedia.org/wiki/The_Strength_of_Weak_Ties): the useful
next lead — a co-host worth approaching, a research angle worth citing, an
org that turns out to be doing more governance-relevant work than its
public summary suggests — is more likely to come through a loose,
already-existing connection than a cold one. A weak fit DOD has actually
brushed up against is exactly that kind of tie, which is why it's worth
keeping a thread on rather than letting it evaporate the moment the post
that mentioned it goes stale.

| Org | Country | Date considered | Interacted via | Notes |
|---|---|---|---|---|
| [Informal Urbanism Research Hub](https://infur.msd.unimelb.edu.au/) | AU | 2026-09-26 | Panellist Anitra Nelson's institutional affiliation — [International Day of Democracy panel recap](../docs/blog/posts/2026-09-26-international-day-of-democracy-recap.md) | [Full reasoning](2026-09-26-informal-urbanism-research-hub-weak-fit.md) |
| [Write In Stone](https://www.writeinstone.com) | AU | 2026-09-26 | Founder Austin interviewed — [2021-08-08 podcast](../docs/blog/posts/2021-08-08-podcast.md) | Journalism-transparency tooling, not governance-mechanism work. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |
| [Open Source Industry Australia](https://en.wikipedia.org/wiki/Open_Source_Industry_Australia) | AU | 2026-09-26 | Recurring DOD co-organiser Alexar Pendashteh is a director — [2019-12-11 podcast](../docs/blog/posts/2019-12-11-podcast.md) | FOSS industry advocacy, not participation mechanisms. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |
| [Action Foresight](https://actionforesight.net/) | AU | 2026-09-26 | Director Jose Ramos, panellist — [2023-01-21 podcast](../docs/blog/posts/2023-01-21-podcast.md) | Futures/foresight consultancy, adjacent but not governance-mechanism-focused. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |
| [Small Giants Academy](https://www.smallgiants.com.au/about) | AU | 2026-09-26 | Co-host, RadicalxChange Melbourne launch + Wisdom & Action Forum — [2026-08-07 post](../docs/blog/posts/2026-08-07-radicalxchange-melbourne.md) | Leadership-development academy, not governance-mechanism work itself. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |
| [Bank Australia](https://www.bankaust.com.au/) | AU | 2026-09-26 | Rowan Dowland (Head of Strategy) spoke at Basil's Table's inaugural event — [2020-02-20 podcast](../docs/blog/posts/2020-02-20-podcast.md) | **Flagged as possibly stronger than weak-fit** — cooperative bank, one-member-one-vote governance, comparable to existing cooperative Landscape entries. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |
| [Cohousing Australia](https://www.cohousingaustralia.org.au/about) | AU | 2026-09-26 | Panellist Elena Pereyra's "collective housing as a model for collective governance" — [2023-01-21 podcast](../docs/blog/posts/2023-01-21-podcast.md) | **Flagged as possibly stronger than weak-fit** — national advocacy/coordinating network for collaboratively-governed housing. [Sweep notes](2026-09-26-podcast-archive-weak-fit-sweep.md) |

## Possible spinoff: a rights-documentation/advocacy tracker

Two entries in a row now tagged `human-rights-observatory` (Amnesty,
Forensic Architecture) — both organisations DOD members clearly rate
highly, just outside what the Democracy Landscape is scoped to cover.
That's worth flagging as a pattern, not just filing away as two
individual "no"s.

**Not a decision to build anything, and — on reflection — not a DOD
project either.** A `docs/projects/` `status: idea` page (DOD's normal
mechanism for an unowned ideation-stage proposal) was the first instinct,
but that's the wrong shape for this: a `docs/projects/` entry is
something *DOD itself* might build under its own name. Cataloguing
rights-documentation and rights-advocacy organisations (evidence
production, violation reporting, campaign-based pressure) is a genuinely
different mission with its own identity — not a DOD sub-initiative — and
there's a neat self-referential reason why: such a meta-org would almost
certainly fail DOD's *own* accountability-framework scope test, the same
way Amnesty and Forensic Architecture themselves did. A cataloguing/advocacy
body isn't governance-mechanism work either. It shouldn't live inside the
organisation whose own standard it wouldn't clear.

So: a separate meta-org, run by whoever wants to found it — possibly DOD
members acting outside DOD, possibly nobody, possibly worth floating to
Amnesty/Forensic Architecture/EFA/DRW's own networks as a gap they might
already be aware of. This file's job is just to record that the idea
came up and why, not to own it. If such a meta-org is ever founded, it's
a normal candidate for a future `docs/organisations/` entry in its own
right (a body of orgs cataloguing accountability-relevant human-rights
work, refereed against its own standard, is itself arguably closer to
DOD's landscape than any single documentation org is) — that's a call
for whenever, if ever, it exists.
