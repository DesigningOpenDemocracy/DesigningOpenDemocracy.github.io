---
title: Democracy Landscape Maintenance
template: project.html
status: active
summary: "Internal tooling and processes for keeping the Democracy Landscape directory accurate, active, and machine-readable."
contributors:
  - BrianKhuu
concepts: [democracy, e-government]
---

Internal project covering the technical infrastructure that keeps the [Democracy Landscape](../organisations/index.md) directory healthy — activity tracking, data quality checks, and automated maintenance scripts.

## Scope

- **Activity tracking** — automated scripts probe org websites for RSS feeds, sitemaps, and structured news content to keep "last active" dates current
- **Data quality** — URL reachability checks, Wikipedia link verification, frontmatter consistency
- **Data exports** — CSV, JSON, GeoJSON, and KML snapshots generated at build time from org frontmatter
- **Bot infrastructure** — unified crawler identity, partial robots.txt compliance (not yet universal — see the [bot page](../bot.md) for exactly which scripts honor it), public [bot page](../bot.md)

## Tooling

Utility scripts live under [`util/`](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/tree/main/util) and are documented in three places depending on kind: `util/SOUL.md` for the core org-maintenance workflow (staleness, structural lint, `stamp.py`/`check_orgs.py`/etc.), `CLAUDE.md`'s "Utility scripts" section for citation/event-sourcing verification tooling, and the [bot page](../bot.md) for exactly which scripts run automatically vs. by hand, at what frequency, and their `robots.txt` behavior — that table isn't repeated here to avoid the two drifting apart.

## Recurring tasks

See [`MAINTENANCE.md`](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/blob/main/MAINTENANCE.md) at the repo root for the full step-by-step maintenance pass. In short:

```bash
python util/check_rss.py --update-activity   # update activity dates from feeds
python util/scrape_news.py                   # update activity dates from news pages
python util/check_urls.py                    # verify org URLs still resolve
```

`check_rss.py` and `scrape_news.py` also run automatically every week via GitHub Actions (see the [bot page](../bot.md)); `check_urls.py` is a manual, human-run step, done roughly quarterly.

## Future ideas

- Aggregated iCal feed from orgs that publish calendar feeds
- Outreach to orgs to encourage RSS/iCal feed adoption

## See also

- [Democracy Landscape](../organisations/index.md)
- [Bot page](../bot.md)
- [HEARTBEAT.md](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/blob/main/HEARTBEAT.md)
