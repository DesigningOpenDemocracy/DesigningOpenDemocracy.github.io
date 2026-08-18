---
authors:
  - Brian Khuu
  - Claude
ai_assist: drafted
origin: milestone
categories:
  - project
date: 2026-08-03
summary: "We scored 21 political parties on how internally democratic they are and how much they push for governance reform. Centered −10 to +10 scale, 0 = typical major-party status quo as of 2026. Here's what we found."
tags:
  - party-governance
  - methodology
  - accountability-framework
---

# We scored 21 parties on internal democracy and reform advocacy

The Democracy Landscape has a lot of advocacy orgs in it. Which is fair — we built it that way. But we're an Australian group, and at some point you've got to stop staring at the international reform ecosystem and take a good hard look at your own backyard. So we did.

We picked every Australian party with enough documentation to score, tossed in a few historical ones and international comparators, and rated them on three things: internal governance, external reform advocacy, and ideology. Then we put it all on a page with graphs and a data file and told ourselves we'd update it when things change.

The [Australian Party Governance Comparison](../projects/au-party-governance-comparison.md) page is the result.

<!-- more -->

## The short version

We wanted to make the [Accountability Framework](https://www.designingopendemocracy.com/projects/accountability-framework/)'s "how people participate in governance" test concrete. So we scored every party on three things:

- **Internal governance**: who actually makes decisions inside the party
- **External reform advocacy**: does the party push for changing how governance works (voting systems, accountability, transparency)
- **Ideology**: standard left–right

The scale runs −10 to +10 on all three axes. We set 0 at "this is what a typical major party looks like as of 2026" — faction-controlled internally, no strong position on reform either way.

Go negative and you're more centralised, or actively opposing reform. Go positive and you're more member-driven, or pushing for systemic change.

A few things jump out:

- Liberal sits at 0 and Labor at +1.5 — both in the "faction-controlled with some member input" band. That's the anchor. One Member One Vote on paper, factional deals in practice.
- PVV sits at −9 on internal governance. Single leader, no formal membership. One Nation at −5.
- Your Party (UK) at +8.5 — sortition-based candidate selection. Flux at +7 — token delegation economy.
- One Nation scores −6 on external reform (actively undermines democratic norms), the Greens +8 (governance reform is central to platform).

The numbers are qualitative judgment, not a rubric. We're upfront about that. Someone could build a real matrix-based methodology on top of the same evidence.

**If you're an academic:** we'd love to see this done properly. Take our vibes as a starting point, build a weighted-rubric version with inter-rater calibration, and publish the comparison. It'd be genuinely interesting to see how far off we are.

[Go look at the graphs](../projects/au-party-governance-comparison.md) and tell us what we got wrong. PRs welcome.

---

## The full methodology

If you want the mechanics, here's how it works.

### The scale

We used to have a 0–10 scale where most parties clustered at 2–3. That made the visual centre meaningless — you couldn't distinguish "less democratic than the norm" from "about average." The new scale fixes that.

**Internal governance bands:**

| Score | Description |
|---|---|
| −10 to −8 | Single-leader, no formal membership. Party IS the leader. |
| −7 to −5 | Leader-appointed. Membership exists but leader controls everything. |
| −4 to −2 | Narrow elite circle. Membership is symbolic. |
| −1 | Leader-dominated but with some elite input. |
| 0 | Elite/faction-controlled with some member input (typical major party as of 2026). |
| 1–3 | One member, one vote on paper. Mixed or inconsistent practice. |
| 4–5 | Genuine OMOV. Competitive, with minority rights. |
| 6–7 | Novel mechanisms alongside standard OMOV. |
| 8–10 | Fully novel: sortition, liquid democracy, direct member control. |

**External reform bands:**

| Score | Description |
|---|---|
| −10 to −8 | Dismantles. Seeks to replace democracy with authoritarian rule. |
| −7 to −5 | Undermines. Attacks electoral integrity, accountability bodies, media. |
| −4 to −2 | Opposes reform. Blocks or weakens accountability mechanisms. |
| −1 | Disfavours reform. Publicly sceptical, controls damage. |
| 0 | No position or indifferent. |
| 1–3 | Platform mentions only. No documented action. |
| 4–5 | Specific policy commitments. Some legislative or campaign action. |
| 6–7 | Sustained campaigns with documented outcomes on multiple fronts. |
| 8–10 | Governance reform is a major platform pillar or the party's reason for existing. |

Both axes are symmetric: 4 negative bands, a zero band, 4 positive bands. The negative side has granularity because "opposes reform" isn't one thing.

### Party selection

21 parties total. 16 Australian (11 active, 5 historical or deregistered) plus 5 international comparators.

Historical parties are included because Flux and MiVote are genuinely interesting governance experiments (even though both deregistered), and the DLP, UAP, and Australia Party give a wider slice of Australian party history for comparison.

The Libertarian Party (formerly Liberal Democratic Party) was added specifically to check whether right-of-centre parties score low on external reform in general, or only the populist ones. Turns out it's the latter — the Libertarian Party scores +1, not negative.

International comparators (Your Party, Podemos, Five Star Movement, Pirate Party Germany, Party for Freedom) are hidden by default on the scatter graphs. Toggle them on with the button next to each chart. Each documents a specific internal-governance data point worth comparing: sortition, mass member votes on party structure, online voting platforms, binding liquid democracy, or deliberately closed single-member structures.

The PVV was included specifically to test whether right-wing populist parties pattern the same way internationally on internal governance. See its scoring note and the internal heartbeat research note for the fuller picture, including Reform UK's unresolved 2025 shift away from private-company ownership.

### Why this page exists

The Accountability Framework asks whether an org works on how people participate in governance. That question doesn't have a clean yes/no answer, and the framework itself acknowledges this.

A party with strong internal democracy but zero external reform advocacy is answering the question differently than one with strong external advocacy but weak internal structure. Whether either should qualify for the Democracy Landscape at all is still an open editorial question we're chewing on.

### Scoring approach

We scored based on what parties have actually done, not what their platforms say. The data file records every score change with a note and sources — there's a dated paper trail for each party. If a score looks wrong, check the justification entry first and then tell us why.

Each party gets a dated audit trail in `party-governance.json` with corresponding justification. 

To rescore a party or add a new one, edit `party-governance.json` directly. The graphs, table, and justification text all update from it at build time.

[Page](../projects/au-party-governance-comparison.md) · [Data file](../data/party-governance.json) · [PRs welcome](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io)
