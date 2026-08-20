---
title: DOD Bot
---

# DOD Bot

**Designing Open Democracy** runs automated scripts to monitor the organisations listed in its [Democracy Landscape](/organisations/). This page describes what those scripts do, how often they run, and how to opt out.

## What the bot does

The bot performs read-only checks against publicly accessible URLs. It does not create accounts, submit forms, or interact with authenticated content.

**Runs automatically, weekly** (GitHub Actions, Fridays 03:00 UTC):

| Script | Purpose |
|---|---|
| `check_rss.py` | Probes for RSS/Atom feeds and sitemaps; records the latest post date to show activity status |
| `scrape_news.py` | Reads news/blog index pages for orgs that lack a machine-readable feed; extracts dates from structured markup only (JSON-LD, OpenGraph, `<time>` tags) |
| `check_fragments.py` | Re-fetches pages cited as evidence for an org's timeline events and prose citations, to confirm the quoted text is still there |
| `check_event_urls.py` | Checks that URLs cited as event evidence are still live (not 404/redirected) |

**Run manually by a human maintainer**, roughly quarterly, not on a fixed schedule:

| Script | Purpose |
|---|---|
| `check_urls.py` | Verifies that `website:` URLs in the landscape are still reachable |
| `check_wikipedia.py` | Checks that Wikipedia links in org pages resolve correctly (queries Wikipedia's own REST API, not third-party sites) |
| `check_contact.py` / `check_contact_deep.py` | Looks for publicly published contact info (email/phone/form) on an org's own site |
| `check_logo.py` | Looks for a usable logo image on an org's own site |

## Frequency

The automated pass above runs weekly. The manually-run scripts run whenever a
human maintainer does a maintenance pass — in practice more like quarterly.
None of this is a high-frequency or continuous crawl.

## robots.txt

`scrape_news.py`, `check_contact.py`/`check_contact_deep.py`, and `check_logo.py`
check `robots.txt` before fetching a page and skip it if disallowed. The
others currently do not consult `robots.txt` at all before fetching (`check_rss.py`
reads it only to look up a `Sitemap:` declaration, not as an allow/disallow
gate) — so a `Disallow` entry for `DOD-Bot` does not yet stop every script
listed here. If you'd rather not be probed at all, the reliable way to opt
out today is the contact-us route below, not `robots.txt` alone.

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

`scrape_news.py`, `check_contact.py`/`check_contact_deep.py`, and `check_logo.py`
honor this. As noted above, the rest don't check `robots.txt` yet, so this alone
won't stop every script — the reliable way to opt out fully is to
[contact us](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/issues)
and we will remove your organisation from automated checks.

## Source code

The scripts are open source: [util/](https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/tree/main/util)

## Our own automation

DOD also runs a periodic maintenance pass over its own [Democracy Landscape](/organisations/), authored by Claude Code and reviewed by a human before merging. The log of these runs — landscape stats, orgs verified, structural fixes — is kept separate from the [main blog](/blog/) at [/heartbeat](/heartbeat/), with its own RSS feed, so it doesn't mix with human-written posts.
