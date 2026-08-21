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
