---
title: Democracy Landscape Maintenance
template: project.html
status: active
summary: "Internal tooling and processes for keeping the Democracy Landscape directory accurate, active, and machine-readable."
contributors:
  - BrianKhuu
concepts: [democracy, e-government]
---

Internal project covering the technical infrastructure that keeps the [Democracy Landscape](../organisations/organisations.md) directory healthy — activity tracking, data quality checks, and automated maintenance scripts.

## Scope

- **Activity tracking** — automated scripts probe org websites for RSS feeds, sitemaps, and structured news content to keep "last active" dates current
- **Data quality** — URL reachability checks, Wikipedia link verification, frontmatter consistency
- **Data exports** — CSV, JSON, GeoJSON, and KML snapshots generated at build time from org frontmatter
- **Bot infrastructure** — unified crawler identity, robots.txt compliance, public [bot page](../bot.md)

## Tooling

Utility scripts live under [`util/`](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/tree/main/util):

| Script | Purpose |
|---|---|
| `check_rss.py` | Probes for RSS/Atom feeds and sitemaps; writes latest post dates to frontmatter |
| `scrape_news.py` | Scrapes news pages for orgs without feeds (opt-in via `news_page:` frontmatter) |
| `check_urls.py` | Verifies org website URLs are still reachable |
| `check_wikipedia.py` | Checks Wikipedia links in org pages resolve correctly |

All scripts identify as `DOD-Bot/1.0` — see the [bot page](../bot.md) for details.

## Recurring tasks

Run these periodically (roughly monthly) during maintenance passes:

```bash
python util/check_rss.py --update-activity   # update activity dates from feeds
python util/scrape_news.py                   # update activity dates from news pages
python util/check_urls.py                    # verify org URLs still resolve
```

## Future ideas

- Aggregated iCal feed from orgs that publish calendar feeds
- Outreach to orgs to encourage RSS/iCal feed adoption

## See also

- [Democracy Landscape](../organisations/organisations.md)
- [Bot page](../bot.md)
- [HEARTBEAT.md](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/blob/main/HEARTBEAT.md)
