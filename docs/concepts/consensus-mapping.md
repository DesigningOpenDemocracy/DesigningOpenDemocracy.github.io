---
title: Consensus Mapping
---

Consensus mapping is an approach to large-scale public deliberation that surfaces areas of agreement across a population rather than amplifying disagreement. It is distinct from polling (which measures the distribution of views) and from open comment threads (which tend to be dominated by the most vocal and polarised participants).

## The problem it addresses

Standard online public consultation produces noise. Comment fields fill with repetitive arguments; extreme positions attract disproportionate attention; genuine points of consensus are invisible within the volume. Worse, platforms optimised for engagement (social media, open forums) actively reward conflict — disagreement generates more interaction than agreement.

The result is that decision-makers receive a distorted picture of public opinion: they see what people fight about, not what they agree on. And what people agree on is often the more useful input for policy.

## How it works

The most widely used implementation is **[Pol.is](../organisations/polis.md)**, an open-source opinion-mapping tool developed in the US and used extensively in Taiwan's [vTaiwan](../organisations/vtaiwan.md) process.

Rather than open-ended comment threads, Pol.is shows participants a series of statements and asks them to agree, disagree, or pass. As responses accumulate, a dimensionality-reduction algorithm (PCA) clusters participants into groups with similar response patterns. The visualisation reveals:

- Which positions command broad agreement across all clusters
- Which positions are contested between clusters
- Where unexpected cross-partisan consensus exists

The key design insight: participants can only respond to existing statements, not generate new ones freely. This removes the amplification dynamic. A statement with one loud proponent shows up as one data point; a statement that 70% of participants agree with across all clusters is immediately visible.

## In practice: vTaiwan and the Uber case

Taiwan's [vTaiwan](../organisations/vtaiwan.md) process used Pol.is for public consultations on contested policy questions including ride-sharing regulation, online alcohol sales, and fintech.

In the Uber consultation, Pol.is results showed that most participants — across pro-Uber and pro-taxi clusters — agreed on safety requirements, insurance obligations, and worker protections. The areas of genuine disagreement were narrower than the noise suggested. The regulation that followed drew on those consensus points.

The process also surfaced positions that cut across conventional political lines — agreements that would never have appeared in a partisan framing of the debate.

## Relationship to other deliberative approaches

Consensus mapping scales differently from [citizens' assemblies](citizens-assembly.md): it can involve thousands of participants rather than dozens, and at much lower cost. But it produces a different kind of output — a map of opinion structure rather than a deliberated recommendation.

The two approaches complement each other: consensus mapping can identify the shape of the landscape; a citizens' assembly can then deliberate on the contested terrain.

## See also

- [Pol.is](../organisations/polis.md) — the main open-source implementation
- [vTaiwan](../organisations/vtaiwan.md) — the most documented application
- [Citizens' Assembly](citizens-assembly.md) — complementary deliberative approach
- [Radical Transparency](radical-transparency.md) — related concept from Taiwan's digital democracy practice
