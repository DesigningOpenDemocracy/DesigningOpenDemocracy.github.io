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

**Main lesson** —

- Every platform in this wave solved the same first half of the problem — surfacing genuine agreement at scale — and struggled with the same second half: converting that agreement into a binding decision. The tools that survived are the ones institutions adopted formally, not the ones that stayed purest to their protest-movement origins.
- "Absorbed by government" and "faded from disuse" turn out to be the two live outcomes, not "stayed independent and thriving." Absorption is worth calling a win for the idea, even when it caps the org's own ability to carry that idea to other countries — that distinction matters if you're building or backing the next one.

## Where it started: 2011

Two protest movements, six months apart, are the direct ancestors of this wave. Spain's **15-M** (or *Indignados*) movement began on 15 May 2011, protesting austerity, the two-party system, and public corruption — drawing explicit inspiration from the Arab Spring and demonstrations in Greece, Portugal, and Iceland.[^15m] **Occupy Wall Street** began four months later, on 17 September 2011, organised around leaderless general assemblies that made decisions by consensus rather than delegation.[^occupy]

Both movements ran into the same wall: a room-sized consensus process doesn't scale past a room. The 2010s civic-tech wave is, more than anything else, a series of attempts to solve that scaling problem in software.

## The platforms, in rough order

**Agora Voting** (Spain, 2011) was the first mover — a secure online voting system built directly out of the 15-M milieu.[^agora] When Podemos formed in 2014 as a party explicitly descended from 15-M, it adopted Agora Voting for binding internal elections (155,000 members voted on party leadership in February 2016) and built **Plaza Podemos**, a deliberation space for citizen-drafted proposals.[^agora] Plaza Podemos is the clearest documented case of participation decay in this whole wave: proposal counts fell from 1,405 to 407 and mean votes per proposal from 198.3 to 17.6 in a single year (Oct 2015–Oct 2016), and the party formally replaced it in 2019.[^agora]

**Loomio** (Wellington, NZ, 2012) came directly out of Occupy — its founders built it because Occupy Wellington needed better tools for the general-assembly process itself.[^loomio] Unlike most of what follows, Loomio stayed a worker cooperative rather than seeking government adoption, and that's arguably why it's still running fifteen years later: no institution's changing appetite can defund it.

**DemocracyOS** (Buenos Aires, 2012) was built by Argentina's Net Party (Partido de la Red) and got real institutional uptake — the Argentine Chamber of Deputies used it to consult citizens on specific bills, and early vTaiwan ran on it before Taiwan switched to Pol.is.[^demos] It's now [`status: inactive`](../../organisations/democracyos.md) in our own listing: the team moved on to Democracy Earth and Open Collective, and the software stopped being maintained.

**Pol.is** (Seattle, 2012) is the one DOD has covered in most depth already.[^taiwan-post] Built by Colin Megill, Christopher Small, and Michael Bjorkegren explicitly in response to Occupy and the Arab Spring, its core move — no replies, just agree/disagree/pass on statements, with clustering to surface cross-group consensus — became the technical backbone of **vTaiwan** (2015), the most internationally cited example of this entire wave. Our [existing analysis](2026-05-25-taiwan-digital-democracy.md) is worth re-reading here: vTaiwan's own numbers (80% of ~26 deliberations led to some government action, 2015–2018) are real, and so is the fact that it hasn't driven a major decision since 2018, because its recommendations were never legally binding. What happened next is the clearest "absorbed, not failed" case in this whole piece: Taiwan's Digital Affairs Ministry built **Join** (join.gov.tw), a government-run consultation platform reaching a broader, older, less tech-savvy public than vTaiwan ever did, ranging well beyond digital policy into drunk-driving law and child-abuse policy. vTaiwan proved the model and the state absorbed it — a genuine win for the underlying practice, even though it meant vTaiwan itself stopped being the thing other countries would point to and adopt directly.

**Decide Madrid / Consul Democracy** (Madrid, 2015) is the institutionalisation path done deliberately: Madrid City Council built it, then in 2019 spun it out to an independent foundation so it wouldn't live or die with one administration's politics. That choice looks prescient — [Consul Democracy](../../organisations/consul-democracy.md) is now used by roughly 350 governments worldwide and won a UN Public Service Award.

**Decidim** (Barcelona, 2016) took the same institutionalisation lesson further: built by Barcelona City Council, now governed by an independent Decidim Association, with [400+ active instances](../../organisations/decidim.md) across 20+ countries including Helsinki, Mexico City, and the French National Assembly.

**Democracy Earth** (2015 onward) is the pivot case. Founded by DemocracyOS's Pia Mancini and Santiago Siri once that platform's momentum ran out, it moved the same underlying goal — legitimate participation without depending on state credentials — onto blockchain identity and quadratic voting. As of mid-2026 it's extended into **SAIRI**, a tokenised autonomous AI agent — which is either the wave's furthest evolution or a sign of how far a project drifts once its original institutional anchor is gone; see [our org page](../../organisations/democracy-earth.md) for both sides of that.

**RadicalxChange** (2018) is where the "quadratic" idea DemocracyEarth was already exploring gets its own foundation, built by economist Glen Weyl around quadratic voting and quadratic funding. It's the newest entry in this list and, as of this week, the one with live news: its Melbourne chapter [launches on 27 August 2026](2026-08-07-radicalxchange-melbourne.md), and its "Plurality" philosophy was co-authored with Audrey Tang — the same Audrey Tang who was vTaiwan's government champion a decade earlier. The wave, in other words, hasn't ended; it's still finding new institutional footing.

## Meanwhile, in Australia

DOD's own backyard produced two of the most binding-by-design attempts in the entire wave — political parties that constitutionally required their elected representatives to vote however the membership decided, no negotiation. Both failed to elect anyone. Both are gone.

**[Flux](../../organisations/flux-party.md)** (founded 2015 by Max Kaye and Nathan Spataro) built Issue-Based Direct Democracy: a market for political capital where unused votes on one issue convert into capital you can spend on issues you care about more. It fielded Senate candidates for years and built **DigiPol**, an open-source app for browsing and voting on bills before Federal Parliament. It never won a seat; the AEC deregistered the federal party in 2022.

**[MiVote](../../organisations/mivote.md)** (founded 2014, publicly launched 2016) went further on the binding side: a 60% supermajority threshold, with senators constitutionally required to vote the membership's position or publicly declare they had no mandate yet. By founder Adam Jacoby's account, every one of the five or six early votes it ran reached that 60% threshold — real evidence that structured, well-informed voting can produce consensus even on contested questions. It deregistered around 2019, having never elected a senator. Its in-house voting technology was spun out as **Horizon State**, which ran real pilots — South Australia's Recreational Fishing Advisory Council election, New Zealand's Opportunities Party — before winding down too.

Both organisations solved the output problem that stumped almost everything else in this post: a genuinely binding mandate, constitutionally locked in, not an advisory one. Neither could translate that into an electoral majority. It's a necessary correction to the pattern below: a binding mandate turns out to be necessary but not sufficient. You still have to win the argument in the room that allocates power in the first place — and for a minor party, that room is the ballot box.

## The pattern

Line these up and there are really three outcomes, not two. Still active and, by their own metrics, growing: Loomio (cooperative-owned, never depended on one government), Consul Democracy and Decidim (both deliberately spun out to independent foundations early), Pol.is (open-source, embedded in Taiwan's digital-ministry infrastructure), RadicalxChange (still expanding chapters). Absorbed — the org's own growth capped, but the practice itself continuing under someone else's roof: vTaiwan, superseded domestically by Taiwan's own Join platform; DemocracyOS, whose consultation approach the Argentine Congress kept using directly and which shaped vTaiwan's own early phase, even as DemocracyOS itself stopped being maintained. Genuinely faded, with no clear successor carrying the idea forward: Plaza Podemos (formally replaced in 2019, after measurable participation collapse), Democracy Earth (moved from voting infrastructure to speculative AI-agent tokens), and Australia's Flux and MiVote — deregistered outright, despite having solved the binding-mandate problem architecturally better than anything else on this list.

The dividing line isn't technical quality — DemocracyOS and vTaiwan were both taken seriously by real governments doing real consultation. It's whether the platform got a durable institutional home that didn't depend on one administration's continued enthusiasm, or a legal mandate that made its outputs binding rather than advisory. Our [archive review](2026-06-02-archive-review.md) named this as DOD's own recurring finding across eight years of podcast discussions: input reforms (who gets to participate, how their agreement is surfaced) are the easy half. The output problem — how a considered public view actually reaches a binding decision — is the one almost nothing in this wave solved, and it's the same [accountability-sink](../../concepts/accountability-sink.md) gap Terrence Chen's research identified specifically in Taiwan's case: "thin" monitorial participation is achievable at scale; "strong" participation, where citizens hold real decision power, mostly isn't, because it requires institutions to give up authority, not just add a consultation layer on top of it.

Fifteen years in, the tools have gotten better. The problem they were built to solve hasn't moved.

## And DOD

Worth naming plainly: this site is also a product of the same moment. Designing Open Democracy held its first meetup in December 2016 — the same year MiVote launched, a year after Flux was founded, with Loomio, DemocracyOS, and vTaiwan already running. [Nick Merange's 2018 comparative evaluation of Flux, MiVote, Online Direct Democracy, and citizens' juries](2018-05-03.md) — with [Max Kaye's response](2018-05-03-Max.md) alongside it — is, structurally, the same exercise as this post: DOD doing this same reckoning eight years earlier, in real time, while its subjects were still active.

Some in the group describe DOD as a kind of [meta-organisation](../../concepts/meta-organisation.md) for that reason — paying attention across the reform space rather than building a platform or running for office itself, on the premise that most of what's tried has been tried before and the lesson shouldn't have to be re-learned each time. It's a premise a few people hold rather than a settled position, and [we've only just started asking in public whether it actually stands up](../../philosophy/index.md). Whichever way that goes, it depends entirely on organisations like the ones above being willing to do the costly, risky thing DOD hasn't: without Flux and MiVote actually running for office, or vTaiwan actually operating inside a ministry for three years, there would be nothing here to write about.

Worth saying outright, not just implying: thanks to everyone who built, ran, funded, or organised any of the efforts in this post. Ending up as a line item in someone else's retrospective about what didn't pan out is a strange reward for having tried something before anyone knew whether it would work.

## Sources & further reading

- [Loomio](../../organisations/loomio.md), [DemocracyOS](../../organisations/democracyos.md), [Pol.is](../../organisations/polis.md), [Consul Democracy](../../organisations/consul-democracy.md), [Decidim](../../organisations/decidim.md), [Democracy Earth Foundation](../../organisations/democracy-earth.md), [vTaiwan](../../organisations/vtaiwan.md), [g0v](../../organisations/g0v.md), [RadicalxChange Foundation](../../organisations/radicalxchange.md), [Flux Party](../../organisations/flux-party.md), [MiVote](../../organisations/mivote.md), [DigiPol](../../organisations/digipol.md), [Horizon State](../../organisations/horizon-state.md) — DOD Democracy Landscape entries
- [Taiwan's digital democracy experiment: what it shows, what it doesn't](2026-05-25-taiwan-digital-democracy.md) — DOD, May 2026
- [The small rooms: how DOD's podcast archive reads from 2026](2026-06-02-archive-review.md) — DOD, June 2026
- [RadicalxChange is launching a Melbourne chapter](2026-08-07-radicalxchange-melbourne.md) — DOD, August 2026
- [Meta-Organisation](../../concepts/meta-organisation.md) — DOD Concepts entry, including how this usage differs from the academic organisational-theory term
- [Evaluating Democracy Reform Proposals](2018-05-03.md) — Nick Merange, DOD, May 2018
- [Talk with Ben Ballingall about Flux Party and IBDD](2020-02-13-podcast.md) — DOD podcast, February 2020
- [Catching up with Adam Jacoby, founder of MiVote](2021-08-07-podcast.md) — DOD podcast, August 2021
- ["Agora Voting/nVotes"](https://www.opendemocracy.net/en/can-europe-make-it/agora-votingnvotes/) and ["Podemos: radical blueprint for democratic reform"](https://www.opendemocracy.net/en/can-europe-make-it/podemos-radical-blueprint-for-democratic-reform/), openDemocracy
- ["Two Steps Forward, One Step Back: The Evolution of Democratic Digital Innovations in Podemos"](https://www.tandfonline.com/doi/full/10.1080/13608746.2022.2161973), *Journal of Contemporary European Studies*, 2022 — source of the Plaza Podemos participation-decline figures

[^15m]: Wikipedia, ["Anti-austerity movement in Spain"](https://en.wikipedia.org/wiki/Anti-austerity_movement_in_Spain).

[^occupy]: Wikipedia, ["Occupy Wall Street"](https://en.wikipedia.org/wiki/Occupy_Wall_Street).

[^agora]: ["Agora Voting/nVotes"](https://www.opendemocracy.net/en/can-europe-make-it/agora-votingnvotes/), openDemocracy; ["Two Steps Forward, One Step Back: The Evolution of Democratic Digital Innovations in Podemos"](https://www.tandfonline.com/doi/full/10.1080/13608746.2022.2161973), *Journal of Contemporary European Studies*, 2022.

[^loomio]: [Loomio](https://en.wikipedia.org/wiki/Loomio), Wikipedia; DOD [org page](../../organisations/loomio.md).

[^demos]: DOD [DemocracyOS org page](../../organisations/democracyos.md).

[^taiwan-post]: [Taiwan's digital democracy experiment: what it shows, what it doesn't](2026-05-25-taiwan-digital-democracy.md), DOD, May 2026; DOD [Pol.is org page](../../organisations/polis.md).
