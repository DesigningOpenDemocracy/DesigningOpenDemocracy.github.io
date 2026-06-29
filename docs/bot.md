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

## Making your site bot-friendly

The bot works best when your site publishes machine-readable signals. In priority order:

**1. Publish an RSS or Atom feed**
This is the most reliable signal. The bot probes [23 common feed paths](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/blob/main/util/check_rss.py) automatically — no configuration needed on your end if your CMS already generates one. WordPress, Ghost, Substack, and most modern platforms do this by default.

**2. Add structured markup to your news/blog pages**
If you don't have a feed, the bot falls back to scraping your news page. It reads dates only from machine-readable markup — not from visible text. Any of these work:

- **JSON-LD** — `"datePublished"` or `"dateModified"` in a `<script type="application/ld+json">` block
- **OpenGraph** — `<meta property="article:published_time">` or `article:modified_time`
- **HTML time element** — `<time datetime="2026-05-01">` on article listings

**3. Publish a sitemap**
A `sitemap.xml` with `<lastmod>` dates is used as a last-resort activity signal when no feed or structured news page is available.

**4. Explicitly allow the bot in robots.txt**
If your site uses aggressive bot-blocking, add an explicit allow:

```
User-agent: DOD-Bot
Allow: /
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

## Our own automation

DOD also runs a periodic maintenance pass over its own [Democracy Landscape](/organisations/), authored by Claude Code and reviewed by a human before merging. The log of these runs — landscape stats, orgs verified, structural fixes — is kept separate from the [main blog](/blog/) at [/heartbeat](/heartbeat/), with its own RSS feed, so it doesn't mix with human-written posts.
