---
title: "Occupy to Plurality: what the 2010s civic-tech wave built, and where it stalled"
date: 2026-08-07
summary: "From Occupy's general assemblies to RadicalxChange's new Melbourne chapter, a decade and a half of protest-born democracy software shares one pattern: strong on making agreement visible, weak on making it binding."
authors:
  - DOD
  - Claude
ai_assist: drafted
categories:
  - civic tech
  - deliberative democracy
tags:
  - civic-tech
  - liquid-democracy
  - consensus-mapping
  - accountability
---

Loomio, DemocracyOS, Pol.is, Decide Madrid, Decidim, Democracy Earth, RadicalxChange — the Democracy Landscape already documents all of these individually. What it hasn't done yet is put them next to each other. Read as a sequence rather than a list, they tell one continuous story: a protest movement's decision-making problem, handed to software, again and again, for fifteen years.

<!-- more -->

> *This post was drafted by Claude Code with AI-assisted research. A human editor partially reviewed it for general accuracy. Verify specific claims against the linked sources.*

**Main lesson** —

- Every platform in this wave solved the same first half of the problem — surfacing genuine agreement at scale — and struggled with the same second half: converting that agreement into a binding decision. The tools that survived are the ones institutions adopted formally, not the ones that stayed purest to their protest-movement origins.
- "Absorbed by government" and "faded from disuse" turn out to be the two live outcomes, not "stayed independent and thriving." That's worth sitting with if you're building or backing the next one.

## Where it started: 2011

Two protest movements, six months apart, are the direct ancestors of this wave. Spain's **15-M** (or *Indignados*) movement began on 15 May 2011, protesting austerity, the two-party system, and public corruption — drawing explicit inspiration from the Arab Spring and demonstrations in Greece, Portugal, and Iceland.[^15m] **Occupy Wall Street** began four months later, on 17 September 2011, organised around leaderless general assemblies that made decisions by consensus rather than delegation.[^occupy]

Both movements ran into the same wall: a room-sized consensus process doesn't scale past a room. The 2010s civic-tech wave is, more than anything else, a series of attempts to solve that scaling problem in software.

## The platforms, in rough order

**Agora Voting** (Spain, 2011) was the first mover — a secure online voting system built directly out of the 15-M milieu.[^agora] When Podemos formed in 2014 as a party explicitly descended from 15-M, it adopted Agora Voting for binding internal elections (155,000 members voted on party leadership in February 2016) and built **Plaza Podemos**, a deliberation space for citizen-drafted proposals.[^agora] Plaza Podemos is the clearest documented case of participation decay in this whole wave: proposal counts fell from 1,405 to 407 and mean votes per proposal from 198.3 to 17.6 in a single year (Oct 2015–Oct 2016), and the party formally replaced it in 2019.[^agora]

**Loomio** (Wellington, NZ, 2012) came directly out of Occupy — its founders built it because Occupy Wellington needed better tools for the general-assembly process itself.[^loomio] Unlike most of what follows, Loomio stayed a worker cooperative rather than seeking government adoption, and that's arguably why it's still running fifteen years later: no institution's changing appetite can defund it.

**DemocracyOS** (Buenos Aires, 2012) was built by Argentina's Net Party (Partido de la Red) and got real institutional uptake — the Argentine Chamber of Deputies used it to consult citizens on specific bills, and early vTaiwan ran on it before Taiwan switched to Pol.is.[^demos] It's now [`status: inactive`](../../organisations/democracyos.md) in our own listing: the team moved on to Democracy Earth and Open Collective, and the software stopped being maintained.

**Pol.is** (Seattle, 2012) is the one DOD has covered in most depth already.[^taiwan-post] Built by Colin Megill, Christopher Small, and Michael Bjorkegren explicitly in response to Occupy and the Arab Spring, its core move — no replies, just agree/disagree/pass on statements, with clustering to surface cross-group consensus — became the technical backbone of **vTaiwan** (2015), the most internationally cited example of this entire wave. Our [existing analysis](2026-05-25-taiwan-digital-democracy.md) is worth re-reading here: vTaiwan's own numbers (80% of ~26 deliberations led to some government action, 2015–2018) are real, and so is the fact that it hasn't driven a major decision since 2018, because its recommendations were never legally binding.

**Decide Madrid / Consul Democracy** (Madrid, 2015) is the institutionalisation path done deliberately: Madrid City Council built it, then in 2019 spun it out to an independent foundation so it wouldn't live or die with one administration's politics. That choice looks prescient — [Consul Democracy](../../organisations/consul-democracy.md) is now used by roughly 350 governments worldwide and won a UN Public Service Award.

**Decidim** (Barcelona, 2016) took the same institutionalisation lesson further: built by Barcelona City Council, now governed by an independent Decidim Association, with [400+ active instances](../../organisations/decidim.md) across 20+ countries including Helsinki, Mexico City, and the French National Assembly.

**Democracy Earth** (2015 onward) is the pivot case. Founded by DemocracyOS's Pia Mancini and Santiago Siri once that platform's momentum ran out, it moved the same underlying goal — legitimate participation without depending on state credentials — onto blockchain identity and quadratic voting. As of mid-2026 it's extended into **SAIRI**, a tokenised autonomous AI agent — which is either the wave's furthest evolution or a sign of how far a project drifts once its original institutional anchor is gone; see [our org page](../../organisations/democracy-earth.md) for both sides of that.

**RadicalxChange** (2018) is where the "quadratic" idea DemocracyEarth was already exploring gets its own foundation, built by economist Glen Weyl around quadratic voting and quadratic funding. It's the newest entry in this list and, as of this week, the one with live news: its Melbourne chapter [launches on 27 August 2026](2026-08-07-radicalxchange-melbourne.md), and its "Plurality" philosophy was co-authored with Audrey Tang — the same Audrey Tang who was vTaiwan's government champion a decade earlier. The wave, in other words, hasn't ended; it's still finding new institutional footing.

## The pattern

Line these up and the split is stark. Still active and, by their own metrics, growing: Loomio (cooperative-owned, never depended on one government), Consul Democracy and Decidim (both deliberately spun out to independent foundations early), Pol.is (open-source, embedded in Taiwan's digital-ministry infrastructure), RadicalxChange (still expanding chapters). Faded or pivoted away from their original form: DemocracyOS (unmaintained), Plaza Podemos (formally replaced in 2019, after measurable participation collapse), vTaiwan (no major decision since 2018), Democracy Earth (moved from voting infrastructure to speculative AI-agent tokens).

The dividing line isn't technical quality — DemocracyOS and vTaiwan were both taken seriously by real governments doing real consultation. It's whether the platform got a durable institutional home that didn't depend on one administration's continued enthusiasm, or a legal mandate that made its outputs binding rather than advisory. Our [archive review](2026-06-02-archive-review.md) named this as DOD's own recurring finding across eight years of podcast discussions: input reforms (who gets to participate, how their agreement is surfaced) are the easy half. The output problem — how a considered public view actually reaches a binding decision — is the one almost nothing in this wave solved, and it's the same [accountability-sink](../../concepts/accountability-sink.md) gap Terrence Chen's research identified specifically in Taiwan's case: "thin" monitorial participation is achievable at scale; "strong" participation, where citizens hold real decision power, mostly isn't, because it requires institutions to give up authority, not just add a consultation layer on top of it.

Fifteen years in, the tools have gotten better. The problem they were built to solve hasn't moved.

## Sources & further reading

- [Loomio](../../organisations/loomio.md), [DemocracyOS](../../organisations/democracyos.md), [Pol.is](../../organisations/polis.md), [Consul Democracy](../../organisations/consul-democracy.md), [Decidim](../../organisations/decidim.md), [Democracy Earth Foundation](../../organisations/democracy-earth.md), [vTaiwan](../../organisations/vtaiwan.md), [g0v](../../organisations/g0v.md), [RadicalxChange Foundation](../../organisations/radicalxchange.md) — DOD Democracy Landscape entries
- [Taiwan's digital democracy experiment: what it shows, what it doesn't](2026-05-25-taiwan-digital-democracy.md) — DOD, May 2026
- [The small rooms: how DOD's podcast archive reads from 2026](2026-06-02-archive-review.md) — DOD, June 2026
- [RadicalxChange is launching a Melbourne chapter](2026-08-07-radicalxchange-melbourne.md) — DOD, August 2026
- ["Agora Voting/nVotes"](https://www.opendemocracy.net/en/can-europe-make-it/agora-votingnvotes/) and ["Podemos: radical blueprint for democratic reform"](https://www.opendemocracy.net/en/can-europe-make-it/podemos-radical-blueprint-for-democratic-reform/), openDemocracy
- ["Two Steps Forward, One Step Back: The Evolution of Democratic Digital Innovations in Podemos"](https://www.tandfonline.com/doi/full/10.1080/13608746.2022.2161973), *Journal of Contemporary European Studies*, 2022 — source of the Plaza Podemos participation-decline figures

[^15m]: Wikipedia, ["Anti-austerity movement in Spain"](https://en.wikipedia.org/wiki/Anti-austerity_movement_in_Spain).

[^occupy]: Wikipedia, ["Occupy Wall Street"](https://en.wikipedia.org/wiki/Occupy_Wall_Street).

[^agora]: ["Agora Voting/nVotes"](https://www.opendemocracy.net/en/can-europe-make-it/agora-votingnvotes/), openDemocracy; ["Two Steps Forward, One Step Back: The Evolution of Democratic Digital Innovations in Podemos"](https://www.tandfonline.com/doi/full/10.1080/13608746.2022.2161973), *Journal of Contemporary European Studies*, 2022.

[^loomio]: [Loomio](https://en.wikipedia.org/wiki/Loomio), Wikipedia; DOD [org page](../../organisations/loomio.md).

[^demos]: DOD [DemocracyOS org page](../../organisations/democracyos.md).

[^taiwan-post]: [Taiwan's digital democracy experiment: what it shows, what it doesn't](2026-05-25-taiwan-digital-democracy.md), DOD, May 2026; DOD [Pol.is org page](../../organisations/polis.md).
