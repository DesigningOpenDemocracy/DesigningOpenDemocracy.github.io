---
title: "The Habermas Machine: an AI mediator that beat humans at finding common ground"
date: 2026-08-16
summary: "A Google DeepMind system trained to write group statements — not to persuade — was preferred over human mediators 56% of the time by more than 5,000 UK participants, and was tested in a full virtual citizens' assembly recruited with the Sortition Foundation. A heads-up on the study, what it found, and where its own authors say it falls short."
authors:
  - Brian Khuu
  - Claude
ai_assist: drafted
origin: member-raised
shared_link:
  url: https://www.science.org/doi/10.1126/science.adq2852
  title: "AI can help humans find common ground in democratic deliberation"
  source: Science
  paywalled: true
  note: "The study this post is about. Full text is paywalled, but the abstract is free — and the link is still worth clicking if you have institutional access or are willing to pay. DOD's write-up below draws on the secondary sources listed at the bottom for everyone else."
  description: "Finding agreement through a free exchange of views is often difficult. Collective deliberation can be slow, difficult to scale, and unequally attentive to different voices. In this study, we trained an artificial intelligence (AI) to mediate human deliberation. Using participants’ personal opinions and critiques, the AI mediator iteratively generates and refines statements that express common ground among the group on social or political issues. Participants (N = 5734) preferred AI-generated statements to those written by human mediators, rating them as more informative, clear, and unbiased. Discussants often updated their views after the deliberation, converging on a shared perspective. Text embeddings revealed that successful group statements incorporated dissenting voices while respecting the majority position. These findings were replicated in a virtual citizens’ assembly involving a demographically representative sample of the UK population."
categories:
  - AI
  - Deliberative Democracy
tags:
  - ai
  - deliberative-democracy
  - citizens-assembly
  - collective-intelligence
  - consensus-mapping
---

Someone in DOD flagged this one around and the reaction has been consistently "wait, this is actually interesting" — so here's the heads-up version. Google DeepMind built an AI system, named after Jürgen Habermas, whose only job is to write a group statement that a divided room can agree describes their discussion fairly. In controlled experiments with UK citizens, it beat human mediators at that job more often than not — published in *Science* in October 2024, with a follow-up essay from the same team a year later if you want the caveats too.[^science-paper]

<!-- more -->

**Main lesson** —

- The Habermas Machine wasn't trained to persuade anyone of anything — it was trained to write the sentence a room already half-agrees on but hasn't found the words for. That's a narrower, more mechanical task than "AI does deliberation," and it's worth being precise about the difference.
- It's not a finished answer to anything, and the team's own follow-up says so — real limits worth knowing about, not a reason to write the result off.

## What it actually does

The system pairs a generative model, which drafts group statements from participants' individually-written opinions, with a reward model trained to predict how much each participant will endorse a given draft. Participants can then critique the statement, and the AI revises it — an iterative "caucus mediation" process, the same basic shape a human facilitator uses when shuttling between people who won't say things to each other's faces.[^mit-techreview]

In the largest arm of the study, more than 5,000 UK participants — recruited partly through the [Sortition Foundation](../../organisations/sortition-foundation.md), the same org DOD already tracks for its [citizens'-assembly](../../concepts/citizens-assembly.md) recruitment work — took part in small-group deliberations on questions like whether to lower the voting age to 16. Participants chose between a human mediator's statement and the AI's statement for the same group discussion. They preferred the AI's statement 56% of the time, and agreement across the group rose by roughly 8 percentage points when the AI mediated instead of a human.[^guardian] The team then ran the system inside a full virtual citizens' assembly — the closer-to-real-world test — rather than stopping at the lab-scale result.

Christopher Summerfield, the DeepMind research director who led the work, described what the statements were actually doing: "What it seems to do is write statements which are faithful to the majority, but include prominent elements of dissent. So they weave in stuff of people who would otherwise feel kind of disenfranchised."[^summerfield] That's the [consensus-mapping](../../concepts/consensus-mapping.md) problem DOD already has a page on — Pol.is takes a clustering approach to the same problem at internet scale; this is a single-statement approach built for a room.

## Worth knowing before you get too excited

The team's own follow-up doesn't dodge the failure modes: across revision rounds "the HM tended to over-weight minority viewpoints," and they flag "algorithmic aversion" — people resisting AI outputs "even when these outcomes are demonstrably superior to those achieved by humans" — as a real adoption risk.[^knight] Melanie Garson, a conflict-resolution scholar at UCL, adds a sharper question from outside the team: the system "does not offer participants the chance to explain their feelings, and hence develop empathy with those of a different view."[^guardian] Worth knowing, not disqualifying — see the sources below if you want to go deeper than this post does.

## Why it's worth DOD's attention

Not as an endorsement — just as a live, well-resourced experiment in the exact space this site pays attention to: what actually helps a diverse group reach a fair, shared account of a disagreement. It sits close to [collective intelligence](../../concepts/collective-intelligence.md) and [deliberative democracy](../../concepts/deliberative-democracy.md), and it's a concrete answer to the CI-vs-AI framing DOD has discussed before — a tool that seems to raise a group's collective judgement without replacing it, in a narrow, mechanically testable way. Worth watching where the team takes it next.

## Sources & further reading

- Michael Henry Tessler et al., ["AI can help humans find common ground in democratic deliberation"](https://www.science.org/doi/10.1126/science.adq2852), *Science* 386, eadq2852, October 2024
- MH Tessler et al., ["Can AI Mediation Improve Democratic Deliberation?"](https://knightcolumbia.org/content/can-ai-mediation-improve-democratic-deliberation), Knight First Amendment Institute, August 2025 — a follow-up essay from the same research team, with the limitations discussed above
- Nicola Davis, ["AI mediation tool may help reduce culture war rifts, say researchers"](https://www.taipeitimes.com/News/feat/archives/2024/10/19/2003825522), The Guardian (republished, Taipei Times), 19 October 2024 — Melanie Garson's critique
- ["AI could help people find common ground during deliberations"](https://www.technologyreview.com/2024/10/17/1105810/ai-could-help-people-find-common-ground-during-deliberations/), MIT Technology Review, October 2024
- ["How to get people to agree with each other using AI — an interview with Prof. Chris Summerfield"](https://overtone.ai/how-to-get-people-to-agree-with-each-other-using-ai-an-interview-with-prof-chris-summerfield/), Overtone.ai
- Beth Simone Noveck, ["Research Radar: The Peacemaking Machine? How AI can help humans find common ground in democratic deliberation"](https://rebootdemocracy.ai/blog/habermas-machine), RebootDemocracy.ai — a different angle: whether this kind of research is aimed at the right problem
- [Sortition Foundation](../../organisations/sortition-foundation.md), [Citizens' Assembly](../../concepts/citizens-assembly.md), [Consensus Mapping](../../concepts/consensus-mapping.md), [Collective Intelligence](../../concepts/collective-intelligence.md), [Deliberative Democracy](../../concepts/deliberative-democracy.md) — DOD entries
- [Occupy to Plurality: what the 2010s civic-tech wave built, and where it stalled](2026-08-07-civic-tech-wave-2010s.md) — DOD, August 2026

[^science-paper]: Michael Henry Tessler et al., "AI can help humans find common ground in democratic deliberation," *Science* 386, eadq2852, published 18 October 2024. Full text is paywalled at the DOI (confirmed inaccessible while researching this post) — facts and quotes here are drawn entirely from the secondary sources listed below and from the team's own August 2025 follow-up essay, not from the paper itself.

[^mit-techreview]: The system pairs a generative model (drafting statements from individual opinions) with a personalized reward model (predicting endorsement), refined through iterative participant critique — described in ["AI could help people find common ground during deliberations"](https://www.technologyreview.com/2024/10/17/1105810/ai-could-help-people-find-common-ground-during-deliberations/), MIT Technology Review, 17 October 2024.

[^guardian]: "the Habermas Machine does not offer participants the chance to explain their feelings, and hence develop empathy with those of a different view" — Melanie Garson, quoted in Nicola Davis, ["AI mediation tool may help reduce culture war rifts, say researchers"](https://www.taipeitimes.com/News/feat/archives/2024/10/19/2003825522), The Guardian, republished in Taipei Times, 19 October 2024. The same article reports over 5,000 UK participants, a 56% preference for AI-generated statements over human-mediator statements, and an average 8-percentage-point increase in agreement.

[^summerfield]: "What it seems to do is write statements which are faithful to the majority, but include prominent elements of dissent. So they weave in stuff of people who would otherwise feel kind of disenfranchised." — Christopher Summerfield, in ["How to get people to agree with each other using AI — an interview with Prof. Chris Summerfield"](https://overtone.ai/how-to-get-people-to-agree-with-each-other-using-ai-an-interview-with-prof-chris-summerfield/), Overtone.ai.

[^knight]: "the HM tended to over-weight minority viewpoints." and "even when these outcomes are demonstrably superior to those achieved by humans" (on algorithmic aversion) — MH Tessler, Georgina Evans, Michiel A. Bakker, Iason Gabriel, Sophie Bridgers, Rishub Jain, Raphael Koster, Verena Rieser, Anca Dragan, Matthew Botvinick & Christopher Summerfield, ["Can AI Mediation Improve Democratic Deliberation?"](https://knightcolumbia.org/content/can-ai-mediation-improve-democratic-deliberation), Knight First Amendment Institute, 1 August 2025.
