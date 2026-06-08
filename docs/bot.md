---
title: DOD Bot
---

# DOD Bot

**Designing Open Democracy** runs automated scripts to monitor the organisations listed in its [Democracy Landscape](/organisations/). This page describes what those scripts do, how often they run, and how to opt out.

## What the bot does

The bot performs read-only checks against publicly accessible URLs. It does not create accounts, submit forms, or interact with authenticated content.

| Script | Purpose |
|---|---|
| `check_rss.py` | Probes for RSS/Atom feeds and sitemaps; records the latest post date to show activity status |
| `scrape_news.py` | Reads news/blog index pages for orgs that lack a machine-readable feed; extracts dates from structured markup only (JSON-LD, OpenGraph, `<time>` tags) |
| `check_urls.py` | Verifies that `website:` URLs in the landscape are still reachable |
| `check_wikipedia.py` | Checks that Wikipedia links in org pages resolve correctly |

## Frequency

Scripts run as part of periodic maintenance passes — roughly monthly, not continuously. They are not high-frequency crawlers.

## User-Agent string

All requests identify as:

```
DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)
```

## Opting out

If you would prefer your site not be checked, add the following to your `robots.txt`:

```
User-agent: DOD-Bot
Disallow: /
```

All scripts respect `robots.txt`. Alternatively, [contact us](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/issues) and we will remove your organisation from automated checks.

## Source code

The scripts are open source: [util/](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/tree/main/util)
