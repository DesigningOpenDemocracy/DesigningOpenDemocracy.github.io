---
title: Pol.is
type: platform
status: active
country: US
website: https://pol.is
last_checked: "2026-05-30"
summary: "An open-source consensus mapping platform used in large-scale public deliberations — participants rate statements rather than debating, and machine learning surfaces the points of genuine agreement across thousands of respondents."
location:
  latitude: 47.6062
  longitude: -122.3321
  name: Seattle, USA
concepts:
  - consensus-mapping
  - deliberative-democracy
  - citizens-assembly
---

Pol.is (pronounced "polis") is an open-source platform for large-scale online deliberation, developed by the Computational Democracy Project. Since its launch in 2012 it has hosted tens of thousands of conversations with over 10 million participants worldwide, and is now embedded as national democratic infrastructure in Taiwan.

## How it works

The core design decision is **no replies**. Instead of threaded debate (which amplifies disagreement and rewards combative voices), Pol.is presents participants with statements one at a time and asks them to agree, disagree, or pass. Participants can also submit new statements.

Machine learning clusters participants by their response patterns, then surfaces the statements that generate **cross-cluster agreement** — the points where people who disagree on most things nonetheless find common ground. This makes consensus visible in ways that comment-based platforms cannot.

## Notable deployments

- **vTaiwan** — the platform's most influential deployment. Used to deliberate on Uber regulation, fintech policy, and over a dozen other areas of Taiwanese law. The Uber consultation found 95% consensus on passenger safety, cutting across the pro-Uber / pro-taxi divide.
- **UK** — used by Nesta and others for public consultations
- **Finland** — used for national-level policy deliberation
- **Collective Intelligence Project** — exploring Pol.is as infrastructure for AI governance consultations

## Open source

Pol.is is fully open source (GitHub: [compdemocracy/polis](https://github.com/compdemocracy/polis)), meaning it can be self-hosted by any government or organisation. This distinguishes it from proprietary consultation platforms and makes it a genuine civic commons tool.

## Key people

- **Colin Megill, Christopher Small, Michael Bjorkegren** — co-founders, built Pol.is in Seattle around 2012 after the Occupy Wall Street and Arab Spring movements as an attempt to create civic infrastructure for large-scale public disagreement. See [Pol.is on Wikipedia](https://en.wikipedia.org/wiki/Pol.is) for further background.

## Relation to DOD interests

Pol.is is the technical backbone of [vTaiwan](vtaiwan.md) — the most-cited example of digital deliberative democracy at government scale. Understanding how Pol.is works is practically useful for anyone designing participation processes.

## Links

- Website: [pol.is](https://pol.is)
- Computational Democracy Project: [compdemocracy.org](https://compdemocracy.org)
- Guardian article: [Taiwan's civic hackers and Pol.is](https://www.theguardian.com/world/2020/sep/27/taiwan-civic-hackers-polis-consensus-social-media-platform)

## See also

- [Consensus Mapping](../concepts/consensus-mapping.md)
- [Citizens' Assembly](../concepts/citizens-assembly.md)
- [vTaiwan](vtaiwan.md)
- [Taiwan's digital democracy experiment: vTaiwan and g0v](../../blog/posts/2026-05-25-taiwan-digital-democracy.md)
