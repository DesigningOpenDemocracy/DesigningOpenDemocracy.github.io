---
title: "The Habermas Machine: an AI mediator that beat humans at finding common ground"
date: 2026-08-16
summary: "A Google DeepMind system trained to write group statements — not to persuade — was preferred over human mediators 56% of the time by more than 5,000 UK participants, and was tested in a full virtual citizens' assembly recruited with the Sortition Foundation. A heads-up on the study, what it found, and where its own authors say it falls short."
authors:
  - DOD
  - Claude
ai_assist: drafted
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

Someone in DOD flagged this one around and the reaction has been consistently "wait, this is actually interesting" — so here's the heads-up version. Google DeepMind built an AI system, named after Jürgen Habermas, whose only job is to write a group statement that a divided room can agree describes their discussion fairly. In controlled experiments with UK citizens, it beat human mediators at that job more often than not. It was published in *Science* in October 2024, and the same team published a longer, more self-critical follow-up in mid-2025.[^science-paper]

<!-- more -->

**Main lesson** —

- The Habermas Machine wasn't trained to persuade anyone of anything — it was trained to write the sentence a room already half-agrees on but hasn't found the words for. That's a narrower, more mechanical task than "AI does deliberation," and it's worth being precise about the difference.
- The paper's own authors list the failure modes as readily as the win — over-weighting minority views, no room for participants to build empathy, and a scaling risk that optimizing for agreement produces short, bland statements. Read past the headline number.

## What it actually does

The system pairs a generative model, which drafts group statements from participants' individually-written opinions, with a reward model trained to predict how much each participant will endorse a given draft. Participants can then critique the statement, and the AI revises it — an iterative "caucus mediation" process, the same basic shape a human facilitator uses when shuttling between people who won't say things to each other's faces.[^mit-techreview]

In the largest arm of the study, more than 5,000 UK participants — recruited partly through the [Sortition Foundation](../../organisations/sortition-foundation.md), the same org DOD already tracks for its [citizens'-assembly](../../concepts/citizens-assembly.md) recruitment work — took part in small-group deliberations on questions like whether to lower the voting age to 16. Participants chose between a human mediator's statement and the AI's statement for the same group discussion. They preferred the AI's statement 56% of the time, and agreement across the group rose by roughly 8 percentage points when the AI mediated instead of a human.[^guardian] The team then ran the system inside a full virtual citizens' assembly — the closer-to-real-world test — rather than stopping at the lab-scale result.

Christopher Summerfield, the DeepMind research director who led the work, described what the statements were actually doing: "What it seems to do is write statements which are faithful to the majority, but include prominent elements of dissent. So they weave in stuff of people who would otherwise feel kind of disenfranchised."[^summerfield] That's the [consensus-mapping](../../concepts/consensus-mapping.md) problem DOD already has a page on — Pol.is takes a clustering approach to the same problem at internet scale; this is a single-statement approach built for a room.

## Where the authors themselves push back

The most useful part of the follow-up paper isn't the result — it's the limitations section, written by the people who'd most want to oversell it. They found that across revision rounds, "the HM tended to over-weight minority viewpoints" — a fairness concern in the opposite direction from the one you'd expect. They flagged "algorithmic aversion" as a real risk to adoption, noting people resist algorithmic outcomes "even when these outcomes are demonstrably superior to those achieved by humans." And on scale: "simply expanding the HM protocol to large groups and optimizing for endorsement might lead to short, bland statements that say little of substance" — the same flattening risk any aggregation mechanism runs into once the group gets big enough.[^knight]

Outside critics push in a similar direction. Melanie Garson, a conflict-resolution scholar at UCL, pointed out that the system "does not offer participants the chance to explain their feelings, and hence develop empathy with those of a different view," and asked directly: "how much value does this deliver in the perception that mediation is more than just finding agreement?"[^guardian] Beth Simone Noveck raised a different kind of caution — that a lot of research effort is going into perfecting consensus-statement generation for assemblies that are themselves a small, high-resource slice of governance, when the harder and more consequential problem is what happens to a considered public view once it has to compete for a binding decision.[^noveck] That's a familiar shape to DOD: it's the same output-problem gap [our own review of the 2010s civic-tech wave](2026-08-07-civic-tech-wave-2010s.md) kept running into — a considered group view is one thing, getting it to bind a decision is another.

## Why it's worth DOD's attention

Not as an endorsement, and not as a finished answer to anything — just as a live, well-resourced experiment in the exact space this site pays attention to: what actually helps a diverse group reach a fair, shared account of a disagreement, and what that costs. It sits close to [collective intelligence](../../concepts/collective-intelligence.md) and [deliberative democracy](../../concepts/deliberative-democracy.md), and it's a concrete answer to the CI-vs-AI framing DOD has discussed before — a tool that seems to raise a group's collective judgement without replacing it, in a narrow, mechanically testable way. Worth watching where the team takes it next, and worth reading the caveats as carefully as the headline.

## Sources & further reading

- Michael Henry Tessler et al., ["AI can help humans find common ground in democratic deliberation"](https://www.science.org/doi/10.1126/science.adq2852), *Science* 386, eadq2852, October 2024
- MH Tessler et al., ["Can AI Mediation Improve Democratic Deliberation?"](https://knightcolumbia.org/content/can-ai-mediation-improve-democratic-deliberation), Knight First Amendment Institute, August 2025 — the follow-up piece with the limitations discussed above
- Nicola Davis, ["AI mediation tool may help reduce culture war rifts, say researchers"](https://www.taipeitimes.com/News/feat/archives/2024/10/19/2003825522), The Guardian (republished, Taipei Times), 19 October 2024 — Melanie Garson's critique
- ["AI could help people find common ground during deliberations"](https://www.technologyreview.com/2024/10/17/1105810/ai-could-help-people-find-common-ground-during-deliberations/), MIT Technology Review, October 2024
- ["How to get people to agree with each other using AI — an interview with Prof. Chris Summerfield"](https://overtone.ai/how-to-get-people-to-agree-with-each-other-using-ai-an-interview-with-prof-chris-summerfield/), Overtone.ai
- Beth Simone Noveck, ["Research Radar: The Peacemaking Machine? How AI can help humans find common ground in democratic deliberation"](https://rebootdemocracy.ai/blog/habermas-machine), RebootDemocracy.ai
- [Sortition Foundation](../../organisations/sortition-foundation.md), [Citizens' Assembly](../../concepts/citizens-assembly.md), [Consensus Mapping](../../concepts/consensus-mapping.md), [Collective Intelligence](../../concepts/collective-intelligence.md), [Deliberative Democracy](../../concepts/deliberative-democracy.md) — DOD entries
- [Occupy to Plurality: what the 2010s civic-tech wave built, and where it stalled](2026-08-07-civic-tech-wave-2010s.md) — DOD, August 2026

[^science-paper]: Michael Henry Tessler et al., "AI can help humans find common ground in democratic deliberation," *Science* 386, eadq2852, published 18 October 2024. Full text is paywalled at the DOI; facts and quotes in this post are drawn from the secondary sources cited below and from the team's own August 2025 follow-up.

[^mit-techreview]: The system pairs a generative model (drafting statements from individual opinions) with a personalized reward model (predicting endorsement), refined through iterative participant critique — described in ["AI could help people find common ground during deliberations"](https://www.technologyreview.com/2024/10/17/1105810/ai-could-help-people-find-common-ground-during-deliberations/), MIT Technology Review, 17 October 2024.

[^guardian]: "one concern was that some minorities might be too small to influence such group statements, yet could be disproportionately affected by the result" and "the Habermas Machine does not offer participants the chance to explain their feelings, and hence develop empathy with those of a different view" and "how much value does this deliver in the perception that mediation is more than just finding agreement?" — Melanie Garson, quoted in Nicola Davis, ["AI mediation tool may help reduce culture war rifts, say researchers"](https://www.taipeitimes.com/News/feat/archives/2024/10/19/2003825522), The Guardian, republished in Taipei Times, 19 October 2024. The same article reports over 5,000 UK participants, a 56% preference for AI-generated statements over human-mediator statements, and an average 8-percentage-point increase in agreement.

[^summerfield]: "What it seems to do is write statements which are faithful to the majority, but include prominent elements of dissent. So they weave in stuff of people who would otherwise feel kind of disenfranchised." — Christopher Summerfield, in ["How to get people to agree with each other using AI — an interview with Prof. Chris Summerfield"](https://overtone.ai/how-to-get-people-to-agree-with-each-other-using-ai-an-interview-with-prof-chris-summerfield/), Overtone.ai.

[^knight]: "the HM tended to over-weight minority viewpoints," "even when these outcomes are demonstrably superior to those achieved by humans" (on algorithmic aversion), and "simply expanding the HM protocol to large groups and optimizing for endorsement might lead to short, bland statements that say little of substance" — MH Tessler, Georgina Evans, Michiel A. Bakker, Iason Gabriel, Sophie Bridgers, Rishub Jain, Raphael Koster, Verena Rieser, Anca Dragan, Matthew Botvinick & Christopher Summerfield, ["Can AI Mediation Improve Democratic Deliberation?"](https://knightcolumbia.org/content/can-ai-mediation-improve-democratic-deliberation), Knight First Amendment Institute, 1 August 2025.

[^noveck]: Beth Simone Noveck, ["Research Radar: The Peacemaking Machine? How AI can help humans find common ground in democratic deliberation"](https://rebootdemocracy.ai/blog/habermas-machine), RebootDemocracy.ai.
