---
title: Federated Voting Guide
template: project.html
status: idea
summary: "A 'tick who you trust' voting guide aggregator: voters select orgs, parties, and commentators they already trust, and the tool displays those sources' stated positions side-by-side per race or policy — without DOD ranking anyone itself."
concepts: [liquid-democracy, democracy-tools, e-government]
---

An idea raised in DOD discussion: rather than building another voting advice application (VAA) that computes its own "match score," build an aggregator where **the voter picks which sources to trust**, and the tool simply displays what each of those sources has said about candidates, parties, and policies for an upcoming election — side by side, unranked.

## How it could work

1. Sources (parties, advocacy orgs, commentators, fact-checkers) publish their positions or endorsements in a structured feed
2. A voter ticks the sources they already trust from a directory
3. For the voter's electorate, the tool shows: "Source A says X about Candidate 1 on housing. Source B says Y."
4. DOD provides the plumbing and the directory of available feeds — never an opinion on who's right

This is structurally similar to how this wiki already aggregates organisation activity from RSS/sitemap feeds (`util/check_rss.py`, `hooks/activity_selector.py`) — applied to "stated positions" instead of "latest news."

## Pros

- DOD never rates or ranks political actors — it's pure aggregation based on the voter's own choices
- Decentralised and federated: any org can publish a feed and be added to the directory, no central editorial bottleneck
- Builds on infrastructure this wiki already has (RSS aggregation, structured data exports)
- Complements rather than competes with existing single-org VAAs like [Build a Ballot](../organisations/build-a-ballot.md) — those could simply be one of the feeds a voter ticks

## Cons / risks

- **Feed bootstrapping problem**: almost no orgs currently publish per-candidate/per-policy positions in a structured format — there's no standard to point them at yet
- **Menu curation**: even "which feeds are available to tick" is an editorial choice, though far lower-stakes than DOD ranking candidates directly
- **Cold start for voters**: a first-time user doesn't know which sources to tick either — the tool needs a neutral way to help people discover sources without nudging them
- **Echo chamber risk**: if people only tick sources they already agree with, the tool may reinforce existing views rather than broaden perspective — true of most information tools, but worth designing against (e.g. optionally surfacing a source the voter hasn't ticked, for contrast)

## Open questions & potential evolution

- Define a minimal feed schema for "positions on candidates/policies" — possibly building on schema.org's `Endorsement`/`Review` types or a simple RSS/JSON extension
- Start small: hand-curate a handful of feeds from orgs already in the [organisations index](../organisations/organisations.md) that publish election-relevant content, as a proof of concept
- Could connect to the [Political Creator Map](political-creator-map.md) idea — self-declared creator affiliations as one feed type
- Could connect to the [Promise Ledger](promise-ledger.md) idea — past-term voting records as a "feed" alongside pre-election promises
- Likely starts life as a concept page defining the feed format and listing candidate sources, well before any UI is built

## Status

This is an idea-stage proposal with no committed owner. If you want to develop it — even just drafting the feed schema as a concept page — raise it in the [DOD community channels](../community/community.md), then update this page's `status` to `active` and add yourself under `contributors`.

## See also

- [Liquid Democracy](../concepts/liquid-democracy.md)
- [Democracy Apps & Tools](../concepts/democracy-tools.md)
- [E-Government](../concepts/e-government.md)
- [Build a Ballot](../organisations/build-a-ballot.md)
- [Political Creator Map](political-creator-map.md)
- [Promise Ledger](promise-ledger.md)
