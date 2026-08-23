---
title: How Victorian Councils Are Governed
contributors:
  - Claude
---

> *This is a raw working note, not a maintained reference page — see [docs/research/research.md](research.md)'s
> own disclaimer. It was compiled by Claude from public government and council sources to support the
> [Council Watch](../organisations/council-watch.md) entry and the
> [City of Casey case study](case-study-city-of-casey-operation-sandon.md). It has not been reviewed or
> promoted by a human editor. Treat it as a sourced starting point, not a finished DOD explainer, and check
> the cited primary sources (the Local Government Act text and Local Government Victoria/LGI guidance)
> before relying on it. A few government sources this note would ideally cite directly
> (localgovernment.vic.gov.au, austlii's Local Government Act 2020 text) return a bot challenge to automated
> fetches, so those claims lean on secondary reporting instead — flagged individually below.*

A short explainer on the formal governance structure of Victorian local councils — who holds which power, and why the split matters for accountability design.

## The Mayor/Lord Mayor vs CEO split

Every Victorian council has two distinct leadership roles that are easy to conflate:

- **The Mayor** — an elected councillor, chosen to chair council meetings and act as the council's public face for a term (commonly one or two years, council-dependent). In the City of Melbourne alone, the **Lord Mayor** (and Deputy Lord Mayor) is directly elected by the public; every other Victorian council instead elects its mayor internally, by a vote of the councillors themselves.[^mayor-election]
- **The Chief Executive Officer (CEO)** — an unelected executive appointment, responsible for the day-to-day administration of the council. Convention across Victorian councils is that the CEO is the only staff member the council itself appoints, with the CEO in turn employing everyone else — though this note could not verify that specific structural detail against a directly-fetchable primary source (see the caveat on [^ceo-role]).

## Formal control: who actually hires and fires the CEO

The CEO is appointed, reappointed, and can be removed only by the **Council as a collective body, via resolution** — not by the Mayor acting individually. Local Government Inspectorate guidance frames this directly: the CEO "is employed and managed by an entity comprised of elected community representatives who make decisions by democratic vote."[^ceo-collective]

Under the Act's employment provisions, "the council must review the CEO's performance at least once a year."[^ceo-review] Giving the Mayor a specific, formal role in *leading* that review is not itself a settled statutory requirement — a 2018 reform bill proposed "that required the Mayor and/or council to obtain independent advice in overseeing CEO recruitment, contractual arrangements and performance monitoring," but that bill lapsed before passing.[^ceo-review-reform] In practice, individual councils commonly assign the Mayor a leading role in the review through their own CEO Employment and Remuneration Policy, but that is a council-level policy choice sitting on top of the Act's baseline requirement, not something the Act itself mandates.

CEO contracts run for a maximum of five years at a time, but are renewable with no limit on the number of reappointments — a council can keep re-contracting the same CEO indefinitely, five years at a time.[^ceo-term]

## Design intent

This is a deliberate **policy/administration split**: elected councillors (and the Mayor, as their chair) are meant to set strategic direction, while the CEO is meant to implement it apolitically, insulated from day-to-day political pressure by a contract that only the whole Council — not any single councillor — controls.

## Live tension

Local Government Victoria's own first-principles review process that led to the Local Government Act 2020 — the "Act for the Future" review of the old 1989 Act — is reported to have named the goal of establishing clearer and more complementary relationships between mayors, CEOs, and councillors, suggesting the government itself saw that relationship as underspecified.[^act-review] This note could not independently verify the exact wording against the source PDF directly (see the caveat on that footnote), so treat the specific phrasing as reported rather than confirmed verbatim.

The most recent substantial council-governance reform, the **Local Government Amendment (Governance and Integrity) Bill 2024** (passed 19 June 2024), is reported to have followed from IBAC's Operation Sandon report (see the [Casey case study](case-study-city-of-casey-operation-sandon.md)) — but its content is councillor-focused: mandatory induction and annual professional-development training for all councillors, mandatory mayoral training, and a new prescribed Model Councillor Code of Conduct applying across all 79 Victorian councils.[^bill-2024] It does not add new CEO accountability mechanisms. This note could confirm the Bill's councillor-focused content directly, but could not independently verify the specific Operation Sandon linkage against a directly-fetchable primary source — the Local Government Inspectorate's own bulletin describing the Bill, read in full, does not itself state that connection; it is reported elsewhere (Lexology, parliamentary coverage) that the reform package followed the Special Report.

Read together, this is a signal — not a settled conclusion — that government's current working assumption may be that the **elected layer**, not the unelected CEO layer, is the weaker link in council accountability right now. See the [Casey case study](case-study-city-of-casey-operation-sandon.md) for a concrete instance of that elected-layer failure, and [Accountability Sink](../concepts/accountability-sink.md) for the general concept this bears on.

## See also

- [Accountability Sink](../concepts/accountability-sink.md)
- [Case study: City of Casey and Operation Sandon](case-study-city-of-casey-operation-sandon.md)
- [Council Watch](../organisations/council-watch.md)

[^mayor-election]: "The City of Melbourne has a Lord Mayor and Deputy Lord Mayor, who are directly elected, and in the other councils a mayor and deputy mayor are elected by fellow Councillors from among their own number." [Local government in Victoria](https://en.wikipedia.org/wiki/Local_government_in_Victoria), Wikipedia.
[^ceo-role]: [The role of CEO](https://www.lgi.vic.gov.au/managing-employment-cycle-council-ceo/role-ceo), Local Government Inspectorate (lgi.vic.gov.au) — this note originally cited this page for the claim that the CEO is the council's only direct appointment, but on checking the page's actual text directly it covers CEO political risk and workplace-safety obligations, not that specific claim; the claim is left in the body as commonly-understood practice, not as something verified against this or any other primary source fetched for this note. <!-- unquoted: no-single-sentence: page's actual content doesn't state this specific claim; left uncited pending a source that does -->
[^ceo-collective]: "is employed and managed by an entity comprised of elected community representatives who make decisions by democratic vote." [Managing the employment cycle of a council CEO](https://www.lgi.vic.gov.au/managing-employment-cycle-council-ceo), Local Government Inspectorate.
[^ceo-review]: "The CEO’s contract must specify performance criteria, and the council must review the CEO’s performance at least once a year." [Current employment arrangements](https://www.lgi.vic.gov.au/managing-employment-cycle-council-ceo/current-employment-arrangements), Local Government Inspectorate.
[^ceo-review-reform]: "There were also reforms proposed that required the Mayor and/or council to obtain independent advice in overseeing CEO recruitment, contractual arrangements and performance monitoring." [Current employment arrangements](https://www.lgi.vic.gov.au/managing-employment-cycle-council-ceo/current-employment-arrangements), Local Government Inspectorate — describing a 2018 reform bill that, per the same page, lapsed before passing.
[^ceo-term]: "A CEO’s contract cannot extend beyond five years but there is no limit on how many times a CEO can be reappointed and enter into a new contract." [Current employment arrangements](https://www.lgi.vic.gov.au/managing-employment-cycle-council-ceo/current-employment-arrangements), Local Government Inspectorate.
[^act-review]: [Act for the Future — Directions for a new Local Government Act](https://www.localgovernment.vic.gov.au/__data/assets/pdf_file/0015/167100/Act_for_the_Future_-_Directions_for_a_new_Local_Government_Act.pdf), Local Government Victoria. This document is behind a bot-challenge that blocked this note's automated fetch attempts; the clearer-relationships-between-mayors-CEOs-and-councillors framing is reported via search-engine-indexed summaries of the document rather than confirmed by this note against the PDF's own text. <!-- unquoted: bot-blocked: localgovernment.vic.gov.au returns a Cloudflare challenge page to curl, confirmed 2026-08-21 -->
[^bill-2024]: "The Bill includes reforms to strengthen council leadership, capability and councillor conduct, improve early intervention and effective dispute resolution and strengthen oversight mechanisms." [Local Government Amendment (Governance and Integrity) Bill 2024](https://www.lgi.vic.gov.au/winter-2024-local-government-integrity-matters/local-government-amendment-governance-and-integrity-bill-2024), Local Government Inspectorate.
