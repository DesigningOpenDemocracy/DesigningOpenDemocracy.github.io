---
title: MieuxVoter
type: civil-society
status: active
country: FR
website: https://mieuxvoter.fr
news_page: https://mieuxvoter.fr/presse
summary: "A French association advocating for Majority Judgment voting — an alternative electoral method where voters grade each candidate rather than pick one, aimed at reducing strategic voting and better reflecting collective preferences."
concepts:
  - majority-judgment
  - e-government
location:
  latitude: 48.8566
  longitude: 2.3522
  name: France
activity:
  manual:
    date: 2025-08-29
    note: "Latest press item: Bilan des Primaires 2022"
    url: https://mieuxvoter.fr/presse
    checked: 2026-06-08
  rss:
    note: "No feed found"
    checked: 2026-06-08
  scrape:
    date: 2022-04-06
    note: "Scraper only finds URL-embedded dates; page shows 2025 items"
    url: https://mieuxvoter.fr/presse
    checked: 2026-06-08
---

MieuxVoter ("Better Vote") is a French association promoting **Majority Judgment** (Jugement Majoritaire) — a voting method developed by mathematicians Michel Balinski and Rida Laraki in which voters assign a grade to each candidate (e.g. Excellent / Good / Fair / Poor) rather than selecting a single name. The winner is determined by the median grade, which reduces the "lesser evil" problem and makes strategic voting harder.

The organisation combines advocacy with software. Their open-source ecosystem includes:

- **[majority-judgment-web-app](https://github.com/MieuxVoter/majority-judgment-web-app)** — a web platform for running Majority Judgment polls
- **[Urn](https://f-droid.org/packages/com.illiouchine.jm)** — an offline Android app for in-person groups: set up a poll, pass the phone around, get a result. No internet, no account. Works just as well for "where are we eating lunch?" as for a formal meeting vote. Available on F-Droid.
- **[majority-judgment-bot-discord-golang](https://github.com/MieuxVoter/majority-judgment-bot-discord-golang)** — a Discord bot for running polls in communities
- Libraries in Python, TypeScript, Rust, PHP, and Dart for embedding the algorithm in other tools

MieuxVoter runs citizen experiments, supports campaigns for local adoption of Majority Judgment, and maintains an educational presence across social media and events in France.

## Links

- Website: [mieuxvoter.fr](https://mieuxvoter.fr)
- GitHub: [github.com/MieuxVoter](https://github.com/MieuxVoter)
- Urn on F-Droid: [f-droid.org/packages/com.illiouchine.jm](https://f-droid.org/packages/com.illiouchine.jm)

## See also

- [Majority Judgment](../concepts/majority-judgment.md)
- [E-Government](../concepts/e-government.md)
- [Démocratie Ouverte](democratie-ouverte.md)
