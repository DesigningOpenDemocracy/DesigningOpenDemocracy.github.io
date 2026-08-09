# 2026-08-09 — landscape session retrospective

## What happened

A single extended session (2026-08-09 AU time) turned the Democracy Landscape from a list of orgs into a living reference. Everything below was built, verified, and pushed same-day.

## Org coverage

- **33 new orgs** added across all five geographic gaps (LA, Africa, Europe, E/SE Asia, NZ)
- 159 orgs total across ~50 countries, up from ~120
- Streaks completed: all new orgs have logo, coordinates, contact, activity evidence, last_checked

## Events & calendar

- **74 orgs with event timelines** (128 events total), up from zero orgs at session start
- 56 founding dates, 19 notable milestones (Nobel Prizes, People Power, court rulings)
- **28 upcoming events** on the site-wide calendar, mostly AU/EU
- Calendar page now has: country filter with flag emojis and `?country=` query param, date blocks with weekdays, Schema.org Event JSON-LD, RSVP/More info buttons, org logos, CJK translations, DOD coverage links
- Blog posts no longer duplicate on the calendar (coverage_url instead)

## Site infrastructure

- Footer now has subscribe links (Blog RSS, Calendar ICS, Heartbeat RSS, Telegram)
- About page has Telegram CTA button
- Both RSS feeds now carry the DOD logo
- `llms.txt` updated to include calendar/events endpoints for AI crawlers
- Frontmatter lint in CI (YAML syntax + stray `---` detection)
- Canonical key ordering on all 159 frontmatter blocks
- Blank line convention applied after closing `---`

## Known gaps (not blocking, revisit later)

- **85 orgs still no timeline events** — founding dates and milestones not yet researched
- **No time data on most events** — only RXC Melbourne has 6pm–8pm
- **Most orgs haven't announced H2 2026 events** — calendar will look thin until they do
- **Internal link checker doesn't cover URLs in frontmatter event data** — the `--` dash bug on the RXC blog coverage link was only caught manually
- **Zero upcoming events from Africa, Middle East, India, Indonesia, most of LatAm** — these orgs publish events on their own schedule
- **Portuguese, Dutch orgs still unrepresented** — no strong candidates surfaced
- **Folio Collective** added but has no upcoming events (check again in a month)

## Useful scripts used

- `util/check_logo.py --write` — auto-detected 30 of 33 logos
- `util/check_rss.py --update-activity` — filled activity data for 19 new orgs
- `util/check_contact.py --write` — populated contact info
- `util/lint_orgs.py` — structural + syntax checks, now in CI

## Design decisions worth remembering

- Calendar event `country` can be overridden per-event (org's home country ≠ event location)
- `coverage_url` is for DOD blog coverage; `url` is for the org's own event page
- Calendar filter updates URL via `history.replaceState` for shareable links
- `frontmatter.dumps()` writes both frontmatter AND body — never append content separately
- Use line-level `\n---\n` matching, not `str.find("---")` — URLs containing `---` break string-level matching
- `yaml.dump(sort_keys=False)` preserves insertion order; canonical key order reduces diff noise
