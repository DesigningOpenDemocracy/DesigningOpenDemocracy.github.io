---
title: Promise Ledger
template: project.html
status: idea
summary: "A federated record of election promises versus subsequent votes and actions in office — closing the accountability loop on the other side of an election, by aggregating existing open parliamentary and civic data rather than DOD doing its own fact-checking."
concepts: [accountability-sink, radical-transparency, e-government, representative-democracy]
---

A complementary idea to the [Federated Voting Guide](federated-voting-guide.md): if that tool helps voters decide *before* an election, this one helps them check *after* — did the people and parties anyone voted for actually do what they said they would?

## The idea

Track election promises (from manifestos, campaign speeches, press releases) against what representatives subsequently voted for or delivered in office — in the spirit of projects like the ABC's "Promise Tracker" or PolitiFact's "Obameter," but built as an **aggregator over existing open data** rather than a new DOD fact-checking operation.

Possible sources:

- Parliamentary voting records (e.g. Hansard, or open data from civic tech groups such as [Democracy Club](../organisations/democracy-club.md))
- Manifestos and policy platforms published by parties themselves
- Existing fact-checking and promise-tracking projects, aggregated rather than duplicated

## Existing trackers

Trackers this idea would aggregate rather than duplicate, as they're found:

- **Victorian Parliamentary Budget Office — [2026 Election Commitment Tracker](https://pbo.vic.gov.au/2026_election_commitment_tracker).** The PBO's own assessment of the parties' commitments ahead of the November 2026 Victorian election, browsable by funding, budget impact, party, policy area and electorate, and updated weekly during the campaign.[^vic-pbo-tracker] A [2022 edition](https://pbo.vic.gov.au/2022_election_commitment_tracker) covered the previous election. As of October 2026 it is published only as an embedded Power BI report, with no CSV, JSON or API, so the data can be viewed but not reused or archived. That's the gap this idea runs into: an official tracker can be public without being open data.

## Why it could matter

Voting-advice tools — including the [Federated Voting Guide](federated-voting-guide.md) idea — only cover half the loop. Informed voting also depends on being able to look back and see whether promises translated into action. Without that feedback, election promises carry little cost when broken, which is itself a structural [accountability sink](../concepts/accountability-sink.md).

## Pros

- Closes the loop with the Federated Voting Guide idea — past performance becomes one more "feed" a voter can tick
- Builds on existing open parliamentary data rather than requiring DOD to do original fact-checking
- Strengthens the case for [radical transparency](../concepts/radical-transparency.md) in legislatures that don't yet publish machine-readable voting records
- Can be genuinely nonpartisan if scoped to "promise vs. recorded vote/action" — a mechanical comparison, not DOD's opinion on whether the promise was good policy

## Cons / risks

- Matching "promise" text to "voting record" is hard to automate reliably — premature automation could misrepresent a representative's actual position
- Even a "neutral" promise-tracker can read as a scorecard in practice if, say, one party is shown breaking more promises than another — framing needs care
- Coverage will be very uneven across countries — some legislatures publish rich open data (UK, EU), many publish almost nothing
- Risk of becoming a large ongoing maintenance commitment if not scoped tightly to "aggregate existing trackers" rather than "build a new one from scratch"

## Open questions & potential evolution

- Start narrow: pick one jurisdiction with good open data (e.g. UK, via Democracy Club-style sources) as a proof of concept
- Could begin as a **links/aggregation concept page** — pointing to existing promise-trackers and open parliamentary data sources — before any DOD-built matching logic exists
- Long-term, could feed the [Federated Voting Guide](federated-voting-guide.md) as a "voting record" feed type
- Worth checking for overlap with the existing [Civics Ecosystem Toolkit](civics-ecosystem-toolkit.md) and [ElectionDates.org](electiondates.org.md) projects' data work

## Status

This is an idea-stage proposal with no committed owner. If you want to develop it — even just a concept page surveying existing promise-trackers and open parliamentary data sources — raise it in the [DOD community channels](../community/index.md), then update this page's `status` to `active` and add yourself under `contributors`.

## See also

- [Accountability Sink](../concepts/accountability-sink.md)
- [Radical Transparency](../concepts/radical-transparency.md)
- [E-Government](../concepts/e-government.md)
- [Representative Democracy](../concepts/representative-democracy.md)
- [Democracy Club](../organisations/democracy-club.md)
- [Federated Voting Guide](federated-voting-guide.md)

[^vic-pbo-tracker]: [2026 Election Commitment Tracker](https://pbo.vic.gov.au/2026_election_commitment_tracker), Parliamentary Budget Office (Victoria). <!-- unquoted: js-rendered: the intro text is rendered client-side from page-data JSON, so the fetched HTML has no sentence to verify against; the embedded report is Power BI, and the page's CMS data fields for CSV/JSON were empty when checked 2026-10-04 -->
