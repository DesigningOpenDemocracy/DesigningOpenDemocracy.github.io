# Claude Code Notes

## Tech Stack

This is a MkDocs + Material for MkDocs static site deployed to GitHub Pages.

- Build: `mkdocs build` (or `make build`)
- Local dev: `make serve`
- Deploy: CI pushes to `gh-pages` branch via `mkdocs gh-deploy --force`
- Python deps: `requirements.txt` (site build), `util/requirements.txt` (utility scripts only)
- Before pushing: `make build && python util/check_internal_links.py && python util/check_event_sourcing.py && python util/reorder_frontmatter.py --check` — catches the same errors as CI. The pre-commit hook (`.githooks/pre-commit`) auto-runs `reorder_frontmatter.py` on staged org pages, so the `--check` should always pass — it's a safety net.
- **If `.git/hooks/pre-commit` doesn't exist:** run `ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit` to install it. Claude should check this on first interaction with the repo and remind the user if it's missing.

## Tests (`tests/`)

Stdlib `unittest` regression coverage for the citation-verification tooling (`util/text_fragment.py`, `util/check_fragments.py`) and the bot's robots.txt compliance (`util/robots_check.py`, `util/check_event_urls.py`) — offline, no network calls, no new deps beyond what `util/requirements.txt` already installs plus `pyyaml`. Lives at repo root (outside `docs/`) so mkdocs never touches it. Run with:
```
python -m unittest discover tests   # or: just test
```
Wired into CI (`.github/workflows/build.yml`) as its own step, before the build/lint jobs. Covers the pure functions in `text_fragment.py` (`normalize_ws`, `find_span`, `quote_matches`, `_split_ellipsis`, `make_text_fragment`/`add_fragment_to_url`/`with_fragment`, `spacing_autofix`, `closest_match_hint`, footnote parsing) directly, plus the I/O-adjacent parts of `check_fragments.py` via fixture files in a tempdir: `paragraph_hash` (regression test for the offset-drift bug — see its docstring), `wikipedia_title` (including the non-English-subdomain regression), `write_quote_fix`/`_write_quote_fix_yaml` (the plain-scalar and YAML-scalar success paths, plus all three refusal cases: no frontmatter, ambiguous quote across events, non-canonical existing frontmatter), `collect_evidence`'s `--slug` filtering (the exact `--slug a --slug b` regression from 2026-08-14 — see the "Utility scripts" `check_fragments.py` entry below), and `_fetch_page_text`'s robots.txt gate (disallowed URLs are never requested; Wikipedia's own API is deliberately not gated). `test_robots_check.py` covers `robots_check.py` directly, including the regression that motivated it: an unreachable/unparseable robots.txt must resolve to "allow everything," not the `RobotFileParser` default of "deny everything" for a parser that never had `parse()`/`read()` called successfully. `test_check_event_urls.py`'s `CheckUrlCachedTests` covers the same sticky-cache treatment for a robots.txt disallow that `HTTP_403`/`429` already got (shared cache format, see `check_event_urls.py`'s entry below). When adding new verification logic to either file, add a test alongside it rather than validating by hand-running against real org files — see issue #155 for the motivating history of bugs this would have caught.

## Known Watch Items

### MkDocs ecosystem fragmentation (as of May 2026)

The MkDocs ecosystem is in flux. The original maintainer went inactive and planned a v2 that would break all existing plugins and themes. This caused a community split:

- **ProperDocs** (`pip install properdocs`) — continuation of MkDocs 1.x, drop-in replacement
- **MaterialX** — continuation of mkdocs-material as a separate package

Current status: we are still on `mkdocs + mkdocs-material` and it works fine. `DISABLE_MKDOCS_2_WARNING=true` is set in CI to suppress advertising injected by `mkdocs-rss-plugin` (which added `properdocs` as a hard dependency).

**When to act:** If `mkdocs-material` stops releasing updates or moves to `materialx`, migrate by swapping package names in `requirements.txt` and replacing `mkdocs` commands with `properdocs`. It is designed to be a drop-in replacement.

Reference: https://fpgmaas.com/blog/collapse-of-mkdocs/

## Sourcing from Wikipedia

Use the API, not scraped page HTML: `https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=<Page_Title>&format=json` (add `&exintro=1` for just the lead section). Returns clean plain-text article content directly — no tag-stripping/regex needed, far less bytes transferred than fetching the fully rendered page (infoboxes, references, styling, scripts), and it's the endpoint Wikipedia actually intends for this kind of programmatic reading rather than a full page load per lookup. Use `action=query&list=search&srsearch=...` first when unsure of the exact page title (Wikipedia's naming disambiguation, e.g. "Democratic Labor Party" vs "Democratic Labour Party", trips up direct title guesses often enough to check first rather than iterating 404s). Established while sourcing historical Australian parties for the [Party Governance Comparison](docs/projects/au-party-governance-comparison.md) — apply it to any future Wikipedia-sourced research (concept pages, org pages, heartbeat world-commentary items) rather than fetching rendered HTML.

## Philosophy section vs. Accountability Framework

These two are separate on purpose (split June 2026 — see the Soul Document's relocation note):

- **`docs/philosophy/index.md`** — the open discussion space. Any DOD member's idea about democracy or governance belongs here, including repeated, unpopular, or half-formed ones. No sourcing discipline required; this is the conversation that happens *before* an idea is polished. Edit it freely — it's meant to stay informal and is not gated by the soul document below.
- **`docs/projects/accountability-framework/index.md`** — DOD's rigorous, AI-reviewed standard for what belongs in the Democracy Landscape. This is the document the rule below applies to.

**Before editing `docs/projects/accountability-framework/index.md`, read `docs/projects/accountability-framework/soul.md`.**

That file records the human intent behind the framework, the invariants that shaped the current text, and the AI dialogue (Claude, DeepSeek, ChatGPT, Gemini, Grok, Mistral) that contributed to it. Reading it first prevents accidentally collapsing earlier contributions.

The invariants recorded there are not immutable. Any document in this repo — including soul.md, this file, and HEARTBEAT.md — can be proposed for change by any contributor, human or AI. The requirement is transparency: if you change something foundational, say what you changed, why, and what prompted it. The PR review is the gate, not a list of forbidden edits.

## Conventions

### Project pages (`docs/projects/`)

- Use `template: project.html` in frontmatter — renders a metadata box (status, contributors, website)
- `status` values: `active` | `idea` | `mothballed` | `cancelled`
- `status: active` pages appear in the front page projects section automatically
- `status: idea` is for ideation-stage proposals with no committed owner — written up with pros/cons and open questions so anyone can adopt one. To activate an idea, change `status` to `active` and add yourself under `contributors`.
- All projects (any status) appear grouped on the `/projects/` index page

### Organisation pages (`docs/organisations/`)

- The section is framed as a **Democracy Landscape reference** — organisations we monitor, not formal affiliates
- Use `type`, `status`, `country`, `website`, `summary` in frontmatter
- **Frontmatter field order** — org pages use a canonical key ordering. All org frontmatter should follow this order. Scripts that write or modify frontmatter MUST preserve it:
  ```
  title
  type
  status
  country
  website
  logo
  logo_bg
  banner
  contact
  summary
  concepts
  location
  news_page
  rss_feed
  ics_feed
  related_orgs
  events
  activity
  last_checked
  ```
  Entries under `activity:` should follow: `manual`, `dod`, `social`, `rss`, `ical`, `scrape`, `sitemap`.
  Per-event fields under `events:` should follow: `date`, `title`, `url`, `source`, `note`, `proof_level`, `url_checked`, `end_date`, `notable`, `type`, `location`.
  `util/check_orgs.py` validates ordering. Use the `ordered_dump` pattern when writing YAML (see `util/check_rss.py` for an example of field-order-aware writing).

- `status` values: `active` | `inactive` | `deregistered`
- For defunct orgs, point `website` to the Wayback Machine calendar URL: `https://web.archive.org/web/*/https://originalurl.com/`
- **Curation standard**: An org belongs here if it works on systems of governance for/with the people, in good faith — regardless of ideological label. See `docs/projects/accountability-framework/index.md` for the full framework, including the three disqualifiers (hypocrisy, bad faith, structural inflexibility). DOD is not a human rights observatory; orgs focused purely on documenting abuses without engaging governance design do not fit.
- `concepts: [slug, slug]` — list of concept slugs this org relates to. Used to populate concept chips in the metadata box and org index table. Slugs match filenames in `docs/concepts/` without the `.md` extension.
- `logo: <path or URL>` — optional; the org's logo, shown on its own page, as a thumbnail in the `/organisations/` index table, and as the map marker in place of the plain type-icon pin. Path under `docs/assets/org-logos/<slug>.<ext>`, or a remote URL when a local copy isn't warranted. See `docs/assets/org-logos/README.md` for the sourcing/licensing convention (a per-logo table with License + Source columns) and `util/check_logo.py`, which can probe an org's site for a logo automatically.
  - **Backing card is transparent by default** on the org page and index table (the map marker is the one exception — it always gets a solid white card, since pins sit on variable-colored map tiles rather than the site's uniform dark background). Most logos read fine directly against the page; do not add a default background back in `customizations.css` — see the warning comment above `.org-page-header-logo` there. A card is added only per-org via:
    - `logo_bg: dark` — the logo is white/light-coloured content on a transparent background (would vanish against the default transparent/dark page) — adds a translucent dark card. Confirmed needed e.g. CAfSA's white icon-on-transparent logo.
    - `logo_bg: light` — the logo is black/dark-coloured content on a transparent background (would vanish for the same reason, opposite direction) — adds a solid white card. Confirmed needed e.g. Democracy in Colour's dark wordmark.
    - Neither is needed for a logo that already carries its own opaque (non-transparent) background baked into the image — e.g. a logo that's genuinely a solid black square with white text is fine as-is on any theme; check the image's actual alpha channel before assuming a light/dark flag is needed, since a colorful thumbnail can look deceptively "mostly dark" or "mostly light" at a glance without actually having a transparent background at all.
- `banner: <path or URL>` — optional; a wide wordmark shown full-width across the top of the org page instead of `logo:`'s boxed-in-the-corner treatment (`organisation.html` prefers `banner:` over `logo:` for the page header when both are set). Commonly used *alongside* `logo:`, not instead of it — `logo:` is still required separately for the map marker/index table, which always render at small icon size regardless of `banner:` (e.g. Its Rio, Democracy in Colour, Susan McKinnon Foundation, CAPaD all pair a wide `banner:` wordmark with a separate square `logo:` icon sourced from the org's own favicon/apple-touch-icon). Same sourcing convention as `logo:`. `logo_bg:` applies to both fields' rendering, since they share the same light/dark-content problem.
- `location: {latitude, longitude, name}` — required for the org to appear on the interactive map. Only `status: active` orgs are shown on the map.
  - `precision: city` — optional. Set this when the coordinate is a best-effort "somewhere in this city" guess rather than a geocoded street address — e.g. you looked up "coordinates of Melbourne" rather than the org's actual office. Confirmed pattern: dozens of orgs across the landscape share an exact city-centroid coordinate with several unrelated orgs in the same city (11 Melbourne orgs all sitting on the same point, etc.) — that's the tell that a coordinate is this kind of guess rather than a real address. Flagged pins render jittered (spread onto a small ring around the stated point, computed client-side in `home.html`'s marker JS, deterministic per org so it doesn't jump around between page loads) and their popup notes the location is approximate, so the map doesn't claim precision it doesn't have. Omit this field once you've confirmed a real address.
- The `organisation.html` template is **auto-applied** to all org pages via `hooks/org_template.py` — no need to set `template:` in frontmatter unless overriding.
- `rss_feed: <url>` — optional; the org's RSS or Atom feed URL. Populated by `util/check_rss.py`.
- `news_page: <url>` — optional; URL of the org's news or blog index page. Opt-in for `util/scrape_news.py`.
- `ics_feed: <url>` — optional; URL of an iCal/ICS calendar feed. Opt-in for `util/check_rss.py --update-activity` (writes `activity.ical`) **and** for `util/sync_events.py`, which caches the org's upcoming events into `docs/data/events/<slug>.json` for the site-wide calendar (see Calendar section below).
- `events: [{date, title, url, source, note, quote, proof_level, proof_level_locked, proof_warning, url_checked, end_date, time, end_time, notable}]` — optional; a manually curated, editorial list of an org's significant milestones — **not** derived from `ics_feed:` and not meant to mirror it. `hooks/org_events.py` splits entries at build time into `page.meta.upcoming_events` (date >= today) and `page.meta.history_events` (date < today), rendered by `organisation.html` as two timeline sections. Keep each entry to one line — a terse `title`, no prose paragraph; if a milestone needs real narrative, put that in the page body instead (same judgment call as the optional "Key people" section). Future-dated entries here are also picked up by the site-wide calendar (see below) as a `manual`-source candidate alongside `ics_feed`-synced ones — no separate declaration needed. `end_date:` is optional, for events spanning more than one day (inclusive last day — same convention `util/sync_events.py` uses for iCal `DTEND`). `notable: true` is optional, for events significant enough to warrant the calendar's highlighted "major event" styling — use sparingly, it's meant to stand out.
  - **`time:`/`end_time:` are both optional, strict 24-hour `"HH:MM"` strings** (quote them — `18:00` unquoted parses as a YAML sexagesimal number, not a time). Rendered on the site-wide calendar (`docs/overrides/calendar.html`) and — this is the part worth knowing — actually wired into the `.ics` export: `hooks/calendar_export.py`'s `_parse_time()` only accepts this exact shape and falls back to an all-day `DTSTART;VALUE=DATE` for anything else, deliberately not attempting to parse natural-language times ("6pm", "2:00 PM AEST"). Real event pages checked while sourcing citations use wildly inconsistent time/date formats for the same fact (sometimes contradicting themselves within one page), so a fuzzy parser here would produce confident, wrong calendar entries rather than a convenience — better to silently fall back to all-day than to guess. No timezone field exists, so a `.ics` subscriber sees this as floating local time, not the event's actual timezone-anchored moment — an honest limitation given nothing here currently records which IANA timezone the event is in, not a claim of full precision.
  - **`proof_level:` — `high` | `medium` | `low`** — how trustworthy the sourcing is. Auto-computed by `check_event_sourcing.py --calculate`/`--recalculate` from source signals (`quote:` → high, note or specific URL → medium, homepage → low) — never hand-set without `proof_level_locked: true` (below), since an unlocked value is silently overwritten by the pre-commit hook the next time that org page is touched. Displayed in the history timeline as a colour-coded badge.
    - **`proof_level_locked: true`** — opt-out for a deliberately hand-set `proof_level` that shouldn't be auto-recalculated (e.g. you have good reason to trust a source less than the formula would credit it). The pre-commit hook and `--calculate`/`--recalculate` skip locked events entirely; the linter still prints an FYI (not a failure) if a locked value has drifted from what the formula would now compute, so you can confirm the lock reason still applies.
  - **Every event MUST carry either `url:` or `source:`** (or both). `url:` is for a link (web page, PDF, Wikipedia article, etc.) that substantiates the event. `source:` is for a non-URL citation — a book, a named person's testimony, an archival reference — when no URL exists. Prefer `url:` whenever one is available (e.g. a Wikipedia article is a `url:`, not `source: "Wikipedia"`). `source:` values should be specific enough to actually locate the claim (at minimum ~20 characters — "Book" is not a citation). `util/check_event_sourcing.py` enforces this at lint time; unsourced events cause a non-zero exit code. Vague `source:` values (under 20 chars) are flagged as a warning but do not fail the build.
  - **Every event MUST also carry at least one of `note:`, `quote:`, or `proof_warning: true`** — a second, separate hard gate from the `url:`/`source:` one above. A bare `url:` with none of these is a "click through and take our word for it" citation; the linter exits non-zero (`NO PROOF`) if all three are missing. `proof_warning: true` is the honest escape hatch for a citation you haven't been able to strengthen yet — it passes the gate but renders a ⚠ badge on the live timeline and is printed by the linter as a tracked backlog item, so the gap stays visible instead of silently disappearing. Don't reach for it as a shortcut when a `note:` would take one extra minute to write.
  - **`note:` vs `quote:`** — `note:` is *editorial paraphrase*, your summary of what the source says in your own words, third person (`"Site states the org was founded in 2014"`, not `"We were founded in 2014"` — a bare first-person quote in a `note:` has no identifier for who "we" is). `quote:` is *exact source text*, mechanically verified by `check_fragments.py` (fetches the URL, substring-matches with whitespace normalisation) — use it when the source has a citable sentence worth quoting verbatim rather than paraphrasing. Both count as "notable event has proof" for the linter's stricter check below; only `quote:` counts as *mechanical* proof (independently re-checkable without a human re-reading the page).
    - Additional nuance on `note:`: if a source needs person-attributed paraphrase (e.g. an interview spread across many paragraphs), still write it in editorial voice: `"Willow Berzin describes founding the Coalition after attending Extinction Rebellion's first Melbourne meeting in late 2018."` If something is worth quoting verbatim with attribution, put it in `quote:` instead — you already have the `url:`.
    - When picking which sentence to quote for an event, prefer one that states the date and/or location inline (e.g. "will hold its annual Global Forum on 1 October 2026 in Athens") over one that doesn't, all else equal. There's no separate mechanical check for whether an event's `date:`/`location:` fields match what the source actually says — considered and deliberately not built, since real event pages use too many inconsistent date/time formats (sometimes contradicting themselves within the same page) for a fuzzy matcher to be trustworthy rather than a false-confidence trap. A date/location-bearing `quote:` gets you that confirmation for free, as a side effect of `check_fragments.py`'s existing verification, at no extra tooling cost.
  - **Notable events (`notable: true`) need *mechanical* proof** — a `quote:`, not just a `note:`. This is a separate, softer check (printed as `NOTABLE NO PROOF`, does not fail the build) reflecting that a claim significant enough to be flagged `notable` deserves independently-verifiable evidence, not just an editor's paraphrase.
  - **`url_checked:` is optional** — a date (YYYY-MM-DD) recording when the URL was last verified to still contain the claimed evidence. Useful for Wayback Machine fallback if a page changes and a `quote:` stops matching. Adds a +1 confidence bonus in `check_event_sourcing.py` if within 365 days; high/medium-proof events whose `url_checked:` has aged past that window are flagged for a recheck.
  - **`#:~:text=` URL fragments are derived, never stored.** When an event has a `quote:`, the org page renders its links with a `#:~:text=` Text Fragment directive built from that quote at *build time* — the browser scrolls to and highlights the exact sentence on click, a real reader-facing benefit `quote:` alone doesn't provide. This is computed on the fly (`util/text_fragment.py`'s `make_text_fragment()`/`with_fragment()`, wired in as a Jinja filter by `hooks/org_events.py`'s `on_env`) rather than written into `url:` — a stored fragment and the `quote:` it was derived from could drift out of sync if either was edited without the other, and it bloated the frontmatter diff for no benefit since `quote:` was already the source of truth. `url:` in frontmatter should always be the plain citation URL with no fragment. Browser support for the underlying Text Fragments spec is near-universal on current versions (Chrome 80+, Edge 83+, Safari 16.1+, Firefox 131+, Opera 67+, Samsung Internet 13+) — an unsupporting browser just loads the page normally, so this is pure progressive enhancement with no downside. `quote:` values should start and end on whole words — matching (both for the derived fragment and for `check_fragments.py`'s live-page verification) is whitespace-normalised, but word-boundary truncation (`"founded in 201"` matching `"founded in 2019"` but not verifying the year) will still pass, so always include enough text to confirm the specific claim.
- `related_orgs: [slug, slug]` — optional; list of org slugs with a direct relationship to this org. Rendered as orange edges in the knowledge graph. Declare on one side only — direction is normalised so duplicates are automatically suppressed.
- `contact:` — optional dict of publicly-published contact details, sourced only from the org's own official website (never third-party registries/aggregators):
  ```yaml
  contact:
    email: info@example.org
    phone: "+61 2 xxxx xxxx"   # quote phone numbers — a leading + or 0 breaks unquoted YAML
    form: https://example.org/contact      # public contact-form page, when there's no email to record
    channels:                              # any other contact/social channel — deliberately open-ended
      - type: telegram
        url: https://t.me/joinchat/...
        label: Telegram                    # optional; defaults to type capitalized
        note: main point of contact        # optional
      - type: instagram
        url: https://instagram.com/example
    source: https://example.org/contact    # page the info was found on
    checked: 2026-07-24                    # date it was last verified
    note: "Click the Contact Us button to reveal the email address"  # optional hint for non-obvious contact points
  ```
  - Prefer general `info@` / `contact@` / `hello@` addresses over named individuals; only use a named person's address if it's the org's sole/designated general contact channel.
  - `form:` is a fallback for orgs whose only public contact channel is a web form (no address published anywhere) — a link to that contact-form page. Not mutually exclusive with `email:`, but mainly useful when there's no email to record.
  - `channels:` — optional list, for any contact/social channel that isn't email/phone/form: Telegram, Discord, Signal, Mastodon, Instagram, WhatsApp, etc. Deliberately a flat `{type, url, label, note}` list rather than one named field per platform, so a new channel type never needs a schema change. `type` is a free-text lowercase slug (used as the fallback rendered label, capitalized, when `label:` is omitted); `url` is required; `label:` and `note:` are both optional (`note:` renders inline next to the link, e.g. "— main point of contact"). Rendered by `organisation.html` alongside email/phone/form; exported as `contact_channels` in the CSV (`type:url` pairs, `; `-joined) and JSON data exports.
  - `note:` (top-level, not per-channel) — optional. A short hint for future checkers or visitors when the contact point isn't obvious (e.g. a JS popup button, a footer block, a mirror site, a specific sub-page to navigate to). Not for general notes; only use when someone would otherwise miss the contact channel.
  - Omit `email`/`phone`/`form`/`channels`/`note` individually if not needed — don't fabricate or guess. If nothing is publicly published, omit the whole `contact:` block rather than adding an empty one.
- `activity:` — optional dict of evidence sources, each keyed by method name. The build hook
  (`hooks/activity_selector.py`) picks the best entry for display using a priority order and
  per-source staleness thresholds.
  ```yaml
  activity:
    rss:
      date: 2026-03-04
      note: "Latest post: Final report on Community Consultation"
      url: https://...
      checked: 2026-06-07       # last probe date (written automatically by check_rss.py)
    scrape:
      date: 2026-05-10
      note: "Latest post: Democracy Forum 2026 announced"
      url: https://example.org/news
      checked: 2026-06-07
    sitemap:
      date: 2026-06-04
      note: "Page last modified (from sitemap)"
      url: https://...
      checked: 2026-06-07
    manual:
      date: 2026-05-01
      note: "Visited site, confirmed active"
      checked: 2026-05-01       # same as date for manual reviews
  ```
  - `method` keys: `manual` | `rss` | `ical` | `scrape` | `sitemap` | `dod` | `social`
    - `manual` — a human personally visited the site via `review_orgs.py` (730-day staleness)
    - `dod` — an AI/bot acting on DOD's behalf fetched or searched for evidence (365-day staleness); use this for heartbeat-run checks, not `manual`
    - `social`/`rss`/`ical`/`scrape` — automated third-party signals (365-day staleness)
    - `sitemap` — site-level lastmod, weakest signal (180-day staleness)
  - `checked:` — optional; the date the source was last probed, regardless of whether new content was found. Written automatically by `check_rss.py`, `scrape_news.py`, and `review_orgs.py`. Entries with no `date` but a `checked` date mean the source was probed but found nothing.
  - Selection logic: (1) pick the **most recent** date among content sources (`manual`, `dod`, `social`, `rss`, `ical`, `scrape`) that are within their staleness threshold; (2) if none qualify, fall back to `sitemap` within its threshold; (3) if all stale, show the most recent across everything
  - Staleness thresholds: `manual` 730 d · `dod`/`social`/`rss`/`ical`/`scrape` 365 d · `sitemap` 180 d
  - If all sources are stale, the most recent entry is shown regardless
  - `util/check_rss.py --update-activity` populates `rss`, `sitemap`, and `ical` entries automatically; re-runs skip orgs checked within 7 days (use `--force` to override)
  - `util/scrape_news.py` populates `scrape` entries for orgs with `news_page:` set; same skip behaviour
  - `hint:` — written automatically by `scrape_news.py` on failure. Values: `spa` (JS-rendered, headless browser needed), `no_markup` (page loaded but no structured date signals — consider requesting RSS), `bot_blocked` (403/429 — consider requesting RSS), `unreachable` (network error). `spa` and `bot_blocked` are skipped on re-runs unless `--force`.
- **Key people** is an optional section. Add it only when named individuals are central to understanding the org's story (founders, government champions, notable critics) and the information is sourced. Link names to Wikipedia where a confirmed article exists. Do not add it just to fill the template — most orgs are better served by institutional description.

### Calendar (`docs/calendar.md`)

Top-level nav tab, next to Blog — promoted there deliberately (not left nested under Community) since "what's coming up" is a distinct, equally prominent use-case to "what we've written about."

Three deliberately separate mechanisms handle "events," each for a different purpose — don't collapse them:

1. **External event links** — an org's own calendar/events page, linked from its org page (e.g. `news_page:`, or just a link in prose). No parsing, no sync — a pointer, nothing more.
2. **Org history/upcoming timeline** (per-org, on the org's own page) — the `events:` frontmatter field, manually curated by an editor (see Organisation pages section above). Split at build time into "Upcoming events" / "History" by `hooks/org_events.py`. Purely editorial judgment about what's *significant* for that org — not a feed dump.
3. **Site-wide future calendar** (`docs/calendar.md`, template `calendar.html`) — a forward-looking, cross-org aggregate meant to help people find events to attend, not an archive. Built from two future-only sources merged by `hooks/calendar_export.py`:
   - Every org's `events:` entries with a future date (the same field from #2 — no separate declaration needed to appear here). This is also how DOD's own events reach the calendar: DOD is itself a tracked org (`designing-open-democracy.md`) with its own `events:` list, same as any other org — there's no separate "DOD's events" path.
   - Every org's cached `ics_feed` sync, written by `util/sync_events.py` to `docs/data/events/<slug>.json` (committed; the build hook only reads this, it never fetches feeds itself)

   A third source — an optional `event_date:` field on blog posts, letting a post announce an event separately from its own `date:` (publish date) — existed briefly but was removed. Every post that had set it was DOD *covering* another org's event, not hosting its own, so the event landed on the calendar twice: once from the org's own `events:` entry, once from the post. Confirmed on both posts that had used it (`2026-08-07-radicalxchange-melbourne.md`, `2026-07-31-prsa-electoral-reform-society-vote.md`) — the date matched the subject org's own `events:` entry exactly in both cases. If DOD ever hosts a genuine event of its own, it belongs in `designing-open-democracy.md`'s `events:`, same as any org — not a blog-post field.

   Output: `docs/calendar.ics` (combined, subscribable VCALENDAR — each `VEVENT` tagged `CATEGORIES:` with the org name) and `docs/data/events.json`, both gitignored/regenerated at build time. Also `docs/calendar-<CC>.ics` — one per ISO 3166-1 country code actually present among upcoming events, gitignored the same way (`docs/calendar-*.ics`) — since most calendar apps (Google Calendar included) have no way to filter a subscribed feed after the fact (`CATEGORIES` is ignored on import), a single combined feed is all-or-nothing once subscribed; `calendar.html`'s existing country-filter dropdown swaps the "Subscribe" button's target to match. `docs/data/events/<slug>.json` (the sync cache) is the opposite of all of these — it **is** committed, since it's the thing the network-free build hook depends on.

   Because raw `ics_feed` calendars are usually full of routine/recurring items (confirmed on g0v's feed — regular meetup dates, not milestones), the aggregate calendar does not attempt to filter for "importance" — it only filters by date (future only). If noise becomes a problem, that's a future curation layer on top of this, not a reason to skip syncing an org's feed.

   Two additive, opt-in refinements on top of the base date filter — neither one hides anything, so they don't conflict with the "no importance filtering" rule above:
   - **Multi-day events** — `end_date:` / iCal `DTEND` (auto-parsed by `util/sync_events.py`, exclusive per RFC 5545 §3.6.1 so a normal 1-day all-day event doesn't misreport as 2 days) render as a date range ("27–31 Aug") instead of a single day.
   - **"Major event" highlighting** — `notable: true` gets the calendar's highlighted styling (colored cell, larger text, a "★ Major event" badge). Deliberately **not** available on raw `ics_feed` syncs — a synced feed has no "this one matters more" signal to key off, only the curated `events:` source does.

   **Client-side past-event collapse and today/tomorrow highlighting.** Since the calendar page is static (built at deploy time), an event that was future-dated at build time can have already passed by the time a visitor actually loads the page — there's no server-side "now" to filter against. `calendar.html`'s JS (`collapsePastAndHighlightNear()`, run once on load before `applyFilter()`) fixes this up client-side: it walks every `<li class="calendar-event">` (each carries a `data-date="YYYY-MM-DD"` attribute for this purpose), and for any event whose date is before today, moves it out of its month's list and into a single collapsed `<details class="calendar-past-events-details">` inserted above the month groups — collapsed by default, so a returning visitor's "what's current" view isn't pushed down by events that have already happened. Today's and tomorrow's events instead get a `calendar-event--today`/`--tomorrow` class (green/blue left-border + tinted background, styled in `customizations.css`) and an inline "Today"/"Tomorrow" badge prepended to their header — collapsing would be wrong for these, since they're the most relevant events on the page, not stale ones. Events 2–7 days out get a third, lighter tier: a plain "This week" badge (`calendar-event-badge--week`) with no border/background change — deliberately weaker than today/tomorrow's treatment, since highlighting every event in the coming week as strongly would drown out the "truly imminent" signal today/tomorrow are meant to give on a calendar aggregating many orgs' events. `updateCount()` excludes anything inside the collapsed past-events `<details>` from its "N events" tally, matching what a visitor can actually see without expanding it. Local-midnight dates are parsed manually (`parseLocalDate()`) rather than via `new Date("YYYY-MM-DD")`, which parses as UTC midnight and off-by-ones for negative-UTC-offset viewers. Verified via a headless-browser check with `Date` monkey-patched to a fixed instant, served over a real local HTTP server (not `file://`, which has its own unrelated image-loading quirks) — confirmed correct collapse/highlight/count behaviour and that `<img loading="lazy">` calendar logos (unrelated pre-existing behaviour) load fine once scrolled into view.

### Blog posts (`docs/blog/posts/`)

- Blog posts are **human-authored**. A human must take primary responsibility for the content, accuracy, and framing of every post.
- Claude may assist with drafting, editing, or structuring a post, but should not create and publish a blog post autonomously — especially for factual or politically sensitive content (legislation, election results, organisational positions).
- When a topic warrants a blog post but no human has written one, note the gap rather than filling it unilaterally. Do not let "the information exists" be sufficient reason to publish.
- Concept and organisation pages are appropriate for AI-assisted content (with sourcing discipline); blog posts are not.
- A post covering an org's event does not get its own calendar entry — that would duplicate the org's own `events:` entry for the same date (see Calendar section above for why the `event_date:` field that used to do this was removed). If the org's page doesn't have that event listed yet, add it there instead.

**Exception — AI-assisted research posts:**

A post may be AI-drafted or AI-collaborated from research (sources, web fetches, pasted
documents) if:

1. Frontmatter must include an `ai_assist:` level. This is the current marker — it replaced
   the old boolean `ai_assisted: true`, which the badge template (`docs/overrides/blog-post.html`)
   still renders as a generic "AI-assisted" fallback for old posts but which new posts should
   not use. Pick the level that actually describes how the post was produced:

   | Level | Meaning | Badge text |
   |---|---|---|
   | `drafted` | AI produced the first full draft from directed research; a human editor reviewed and revised it before merge. | "AI-drafted, human-reviewed & revised" |
   | `collaborated` | Human and AI wrote the post together, back and forth — neither side owns the first draft outright. | "Human-AI collaboration" |
   | `reviewed` | A human wrote the post; the AI's role was limited to review/editing (fact-check, copyedit, structure suggestions). | "Human-authored, AI-reviewed & edited" |

   Feel free to add a new level (and its badge label in `blog-post.html`) if none of these
   honestly describe how a post came together — the point is the marker should be accurate,
   not that this list is closed.

   ```yaml
   authors:
     - <reviewing human's name>
     - Claude
   ai_assist: drafted
   ```

   Authorship by level:
   - `drafted` / `collaborated`: the reviewing human goes first — by the time the post is
     merged, a human editor has reviewed and passed it, so they hold primary authorship
     credit, with every AI that materially contributed (e.g. `Claude`, `DeepSeekV4Pro`) listed
     after them. Name whichever person actually did the review for *this* post — don't
     default to any one name across posts, since different posts get reviewed by different
     people. Don't use the collective `DOD` credit either — `DOD` implies a multi-person
     editorial team standing behind the post, which overstates it while review is really
     done by one person at a time. Use `DOD` only once a post has genuinely been
     reviewed/passed by the org collectively rather than an individual. (This differs from
     the heartbeat log below, which is pushed direct to main without prior human review and
     so lists `Claude` alone.) If you don't know who reviewed a given post, ask rather than
     guessing a name.
   - `reviewed`: the AI didn't materially author content, so don't add it to `authors:` just
     because the marker is set — list only the reviewing human. The `ai_assist: reviewed`
     marker itself is what discloses the AI's editing role.
2. Every factual claim must carry a linked source. No unsourced assertions.
3. A human must review and merge the PR.

   No inline disclaimer paragraph is needed in the post body — the `ai_assist` level
   set in frontmatter renders as a badge in the post's metadata sidebar (via
   `docs/overrides/blog-post.html`), which is where this now gets disclosed. An
   inline disclaimer used to be required here too; it was dropped as redundant once
   the sidebar badge existed. If you're touching an older post that still carries the
   old disclaimer paragraph, feel free to remove it while you're in there.

`ai_assist:` (any level) is distinct from `ai_generated: true` (sync posts) — that boolean is
a load-bearing flag for the heartbeat log's direct-to-main push path, not a display preference,
so leave it as-is there rather than migrating it to `ai_assist: generated`.

**Convention — origin (optional):**

An optional `origin:` frontmatter field records *why* a post was written — a small,
closed vocabulary meant for future automation (e.g. a script that wants to treat
"we covered this org's event" posts differently from "we're reacting to the news"
posts) rather than for display. Set it when the trigger is clear-cut; leave it off
rather than guessing when a post's origin is genuinely mixed or not obviously one
of these.

| Value | Meaning |
|---|---|
| `member-raised` | A DOD member raised or discussed the topic internally (meeting, chat, forum) before it became a post. |
| `event-coverage` | Written around another org's event DOD is covering — an announcement/preview or a recap. |
| `world-commentary` | Reacting to an external news item, publication, study, or development. |
| `milestone` | Announcing DOD's own project output or site change. |
| `reader-question` | Prompted by a reader or community question. |

```yaml
origin: world-commentary
```

Feel free to add a new value if none of these honestly fit — same spirit as `ai_assist`
levels above: the point is that the value is accurate, not that this list is closed.
Rendered as a badge in the post's metadata sidebar (`docs/overrides/blog-post.html`,
styled in `customizations.css`'s `.origin-*` rules) alongside the `ai_assist` badge, and
also readable by future automation off the raw frontmatter value — adding a new value
means adding its label to `origin_labels` in the template and a `.origin-<value>` colour
rule in the CSS, same pattern as `ai_assist`'s `ai_labels`/`.ai-assist-*`.

**Convention — shared_link (optional, for posts that exist to point at one external thing):**

When a post's whole reason for existing is "look at this" — a paper, article, video,
someone shared in the DOD chat — set `shared_link:` in frontmatter so the actual link
gets a prominent, unmissable card instead of being just one more bullet in "Sources &
further reading" at the bottom, indistinguishable from secondary citations. This was a
real gap: the Habermas Machine post's paywalled *Science* paper — the thing the whole
post is about — was buried in a 7-item source list with no visual weight.

```yaml
shared_link:
  url: https://www.science.org/doi/10.1126/science.adq2852
  title: "AI can help humans find common ground in democratic deliberation"
  source: Science
  paywalled: true
  note: "The paper DOD is writing about"
  description: "Online deliberations at scale are a promising way to elicit citizens' opinions on policy issues, but existing approaches lack scalable mechanisms..."
```

- `url:` — required; everything else is optional.
- `title:` / `source:` / `note:` — plain text, author-written by hand. Deliberately not
  auto-fetched (no oEmbed/Open Graph scraping) — this repo's convention is fetch-once-
  cache-to-a-committed-file for anything network-dependent (see `util/sync_events.py`),
  and most things worth sharing here are paywalled or otherwise unfetchable anyway, so a
  live-fetch approach would fail more often than it'd help.
- `cta:` — optional button text override. Defaults to "Read the original →", except for a
  known video-hosting URL (`youtube.com`/`youtu.be`/`vimeo.com` — see `_VIDEO_HOSTS` in
  `hooks/shared_link_card.py`), where it defaults to "Watch →" instead — "read" doesn't fit
  a video link. Deterministic on the URL's own host, not a content-sniffing guess, so it
  stays manual/no-heuristics in spirit like the rest of this field. `cta:` overrides either
  default for any case the host list misses.
- `description:` — optional; the source's own abstract/summary text, pasted in verbatim
  and rendered as a blockquote on the card — this is what gives the card the substance a
  real oEmbed/Open Graph fetch would (`title` + `description` + `thumbnail_url` is
  basically that shape already; the difference is a human pastes it once instead of a
  script fetching it every build). Unlike `title:`/`source:`/`note:`, this one IS
  mechanically re-verified against `url:` — same pipeline as event/footnote `quote:` — by
  `util/check_fragments.py`, which now checks three evidence sources instead of two (see
  that script's docstring). Word it as the source's actual abstract, not editorial
  commentary — that's what `note:` is for.
- `image:` — optional; a thumbnail rendered at the top of the card, clickable through to
  `url:` same as the button below it. Either a path under `docs/assets/` (no leading
  slash — the hook adds one; see the "URL gotcha" note below for why) or a full remote
  URL. Manually sourced, same as `logo:`/`banner:` on org pages — not auto-fetched, for
  the same reason `title:`/`source:`/`note:` aren't. Used for `2026-06-26-anarchist-
  critique-of-democracy.md`'s Andrewism video: `image:` replaced what used to be a
  hand-built `[![thumb](...)](url)` markdown block right after the frontmatter, so the
  same card now covers both the text-only paper case and the video-with-thumbnail case
  under one system instead of two competing patterns.
  - **If the image lives next to the post itself** (`docs/blog/posts/<file>.jpg`, the
    common case for a hand-sourced banner — see `event.image:` below), the path is
    **not** `blog/posts/<file>.jpg`. mkdocs-material's blog plugin flattens post-colocated
    assets to `site/blog/<file>.jpg` at build time (confirmed on
    `2026-08-07-radicalxchange-melbourne-event-banner.jpg`), so the frontmatter value
    needs to be `blog/<file>.jpg` to resolve correctly as raw `<img src>` HTML — unlike a
    markdown `![](file.jpg)` reference in the post body itself, which mkdocs resolves
    relative to the source file and gets this right automatically. Only an issue for
    raw-HTML-injecting hooks (this one, `hooks/event_card.py`); doesn't affect ordinary
    markdown images elsewhere in a post.
- `paywalled: true` — optional; renders a small "Paywalled" badge next to the button, so
  readers calibrate expectations before clicking through. The button and link stay live
  regardless — a paywall doesn't mean the link isn't worth following: abstracts are
  usually free, and some readers have institutional access or are willing to pay. If
  `note:` mentions the paywall, word it so the link still reads as worth clicking (e.g.
  "full text is paywalled, but the abstract is free") rather than steering readers away
  from it entirely.
- Rendered by `hooks/shared_link_card.py` (registered in `mkdocs.yml`), which injects the
  card as raw HTML at the very top of the post body — before the author's own opening
  paragraph, regardless of where in the markdown source it would otherwise land — styled
  in `customizations.css`'s `.shared-link-*` rules. The button reuses the existing
  `.hero-cta-btn.hero-cta-primary` classes from the home page rather than inventing new
  button styling.
- Not a replacement for `[^footnote]` citations or the "Sources & further reading" list —
  the shared link should usually still appear there too, exactly as before. This card is
  purely about giving *the* link visual priority a reader shouldn't have to hunt for.
- **Don't stack this with a separate hand-built "watch/read this" treatment for the same
  link** (a manual thumbnail block, an inline embed) — migrate the post onto `shared_link:`
  instead, the way `2026-06-26-anarchist-critique-of-democracy.md` was, rather than layering
  a second prompt for the same URL on top of the first.

**Convention — event (optional, for posts pointing at a ticketed/RSVP'd event):**

When a post's whole reason for existing is "here's an event, go register" — someone else's
conference, workshop, or meetup DOD is flagging, not hosting — set `event:` in frontmatter
so the RSVP link gets a prominent card instead of a hand-rolled mix of banner image, button,
and map that drifts in shape from post to post. Confirmed drifting before this existed:
`2026-08-07-radicalxchange-melbourne.md` had a banner image, a styled button, and an embedded
map; `2026-05-29-people-powered-democracy-forum.md` had none of those, just a plain link.

```yaml
event:
  url: https://events.humanitix.com/radicalxchange-foundation-in-melbourne
  title: "An invitation to meet RadicalxChange Foundation in Melbourne"
  host: RadicalxChange Foundation
  cta: "RSVP for 27 August"
  date: 2026-08-27
  time: "18:00"
  end_time: "20:00"
  note: "This is a RadicalxChange event, not a DOD event — we're just pointing at it."
  image: 2026-08-07-radicalxchange-melbourne-event-banner.jpg
```

- `url:` — required; everything else is optional.
- `title:` — the event's own name (from its ticket page), not necessarily the same as this
  post's own title.
- `host:` — who's actually running it. Rendered in the card's eyebrow ("Event · Host Name")
  so nobody mistakes it for a DOD-run event.
- `cta:` — button text override. Defaults to "RSVP →" if omitted.
- `date:` / `time:` / `end_time:` — same shapes as org `events:` frontmatter (`time:`/
  `end_time:` are strict 24-hour `"HH:MM"` strings — quote them, an unquoted `18:00` parses
  as a YAML sexagesimal number). Rendered as e.g. "Thursday, 27 August 2026, 6:00–8:00 PM".
- `note:` — plain text, typically the "this isn't a DOD event" disclaimer.
- `image:` — same convention as `shared_link.image:` (a `docs/assets/` path with no leading
  slash, or a full remote URL) — a banner shown at the top of the card, clickable through to
  `url:`.
- **Location and map come from the post's own top-level `location:` frontmatter** (`name`,
  `latitude`, `longitude`) — not duplicated inside `event:`. When `location:` has
  coordinates, the card embeds an OpenStreetMap iframe with a "View larger map / directions"
  link, the same pattern `2026-08-07-radicalxchange-melbourne.md` used to hand-build.
- Rendered by `hooks/event_card.py` (registered in `mkdocs.yml`), which injects the card as
  raw HTML at the very top of the post body, styled in `customizations.css`'s `.event-card-*`
  rules. The RSVP button reuses `.hero-cta-btn.hero-cta-primary`, same as `shared_link:`'s
  button — one consistent action-button color across the site regardless of card type; the
  card's own amber accent (vs. `shared_link:`'s blue) is what signals which kind of card it is.
- **This card is presentational only and must never be read by `hooks/calendar_export.py`.**
  A blog-post field that looked similar to this — `event_date:` — was tried and removed for
  exactly the failure mode this would reintroduce: it fed the site-wide calendar and
  duplicated the org's own `events:` entry for the same date (see the Calendar section
  below). The actual calendar-worthy entry for an event like this still belongs on the
  *host org's own page*, per the "A post covering an org's event does not get its own
  calendar entry" rule in the Blog posts section below — `event:` here is only ever a reader-
  facing card on the post itself.
- **Don't stack this with a separate hand-built banner-image/button/map combination for the
  same event** — migrate the post onto `event:` instead, same spirit as `shared_link:`'s
  equivalent rule above.

**Convention — main lesson (optional):**

Each blog post should include a `**Main lesson** —` section positioned directly after
`<!-- more -->`. Format as up to 3 short bullet points answering "what should a
reader walk away with?" — not a summary of what happened, but why it matters. Omit
for short posts, podcast announcements, and maintenance notes where there is no
clear lesson.

Periodic maintenance sync posts do **not** go here — see Heartbeat log below. They
get their own blog instance and feed so the human-curated blog and its RSS feed
stay free of bot noise.

### Heartbeat log (`docs/heartbeat/posts/`)

A second, separate Material-for-MkDocs blog instance (`blog_dir: heartbeat` in
`mkdocs.yml`), with its own RSS/JSON feed (`feed_heartbeat_rss_created.xml` /
`feed_heartbeat_*`). It is deliberately kept out of `docs/blog/` and out of primary
nav (`docs/heartbeat/index.md` explains itself to anyone who lands there directly)
so its posts never mix with — or get mistaken for — human-written blog content.
It has its own `.authors.yml` (mirrors the `Claude` entry in `docs/blog/.authors.yml`).

Periodic maintenance sync posts (see `HEARTBEAT.md`) are AI-authored and may be
pushed direct to main — no PR — if they meet all of the following:

1. File: `docs/heartbeat/posts/YYYY-MM-sync.md`. One file per calendar month,
   not per run — see **Cadence** in `HEARTBEAT.md`. The brief may run weekly;
   the post is a `draft: true` work-in-progress that gets refined across that
   month's runs and is released (drop `draft: true`) only when the month rolls
   over. A `draft: true` post is excluded from the production build entirely
   (no page, no feed entry — this is mkdocs-material's blog plugin behavior),
   so it's safe to commit mid-month without it going live.
2. Frontmatter must include:
   ```yaml
   authors:
     - Claude
   ai_generated: true
   draft: true   # while the month is still accumulating; removed on release
   ```
3. The post body must open with this disclaimer block:
   ```
   > *This post was generated by Claude Code during a scheduled maintenance pass.
   > All statistics are derived from this wiki's own data. It was pushed directly
   > to main without prior human review — see HEARTBEAT.md for the trust model.
   > A human may review and amend it after the fact.*
   ```
4. Content is restricted to these sections (see `HEARTBEAT.md` for full structure):
   - **Maintenance log:** landscape statistics, orgs verified, structural findings.
     All claims sourced from the wiki's own data.
   - **World commentary (optional):** 1–3 sourced observations on recent
     democracy-related events (new assemblies, reforms, backsliding, policy
     publications). Every item must carry at least one linked source and every
     claim in it must be traceable to one of that item's links — when an item
     cites more than one source, use Working notes (below) to say which claim
     came from which, rather than leaving the reader to guess from link order.
     DOD is nonpartisan — no partisan-election commentary, no unsourced claims
     — but opinion grounded in the accountability framework is fine; this is
     the bot's own venue, with more editorial latitude than `docs/blog/posts/`
     AI-assisted posts (see **Voice** in HEARTBEAT.md Step 5). An item that's
     notable-seeming but not yet confirmed may be included tentatively and
     resolved on a later run (see HEARTBEAT.md Step 5/6). If nothing notable
     happened, this section is omitted entirely.
   - **Framework notes (optional):** the bot flagging friction it hit while
     applying the accountability framework this run — to an org decision, a
     tag call, or a commentary item — not commentary on the world, but
     feedback on DOD's own standard (see Mission/Step 6 in `HEARTBEAT.md`).
     A concrete proposed fix to the framework still requires a PR per the
     normal foundational-document gate; this section is the notice, not the
     fix. Omitted entirely if nothing surfaced this run.
   - **Working notes:** dot-point methodology appendix — which script produced
     the Landscape update numbers and when, any fallback method used during
     verification, and per-claim source attribution for any World commentary
     item citing more than one source. Process transparency, not new
     findings; see HEARTBEAT.md Step 6 for what belongs here.
5. Pushed straight to main, no PR — see Push permissions in `HEARTBEAT.md`.

### Internal heartbeat (`internal-heartbeat/`)

A private counterpart to the public heartbeat log, for research and draft
editorial reasoning that isn't (yet, or ever) ready to be public — e.g.
assessing whether a politically sensitive org (a political party, say)
meets the accountability framework's bar for the Democracy Landscape. Lives
outside `docs/`, so mkdocs never builds it — nothing there can accidentally
reach the site, unlike a blog post relying on `draft: true` staying set.
See `internal-heartbeat/README.md` for conventions and how an entry gets
promoted to a real public post later, if it ever does. Writable by
interactive sessions and, per `HEARTBEAT.md`'s Push permissions, the
scheduled heartbeat bot itself during maintenance runs — lower-stakes than
anything else the bot direct-pushes, since nothing here can go live
regardless of what's written.

### Concept pages (`docs/concepts/`)

- These are **discovery aids** — brief orientations pointing to better sources, not authoritative explanations.
- Content should come from DOD member discussions/events (linked back to blog posts) or point to external sources.
- Do not write extended explanations from general knowledge. If depth is needed, link outward.
- DOD is nonpartisan and agnostic to any specific democratic model; inclusion of a concept is not an endorsement.
- A "Search organisations working on X in the Democracy Landscape →" bubble is auto-injected
  under the title by `hooks/concept_filter.py` — concept authors do not need to add it manually.
  The org index page reads the `?concept=` query param and pre-checks the Concepts facet.

### Prose footnote citations (org pages, blog posts, concept pages)

Markdown footnotes (`[^ref]: ["Title"](url), Source, date.`) are the citation mechanism for
narrative prose, distinct from the structured `events:` frontmatter field (which has its own
`quote:`/`note:`/`proof_level` sourcing discipline — see Organisation pages above). Footnotes
are freeform text with no YAML schema, so that discipline doesn't apply to them today — most
existing footnotes are pure citation-style (title, source, date), not verbatim excerpts.

**Going forward**: where the cited source has a specific sentence that supports the
claim, include it as a verbatim quoted phrase in the footnote text itself, e.g.:

```
[^tvfy-about]: "today the OpenAustralia Foundation is launching a new site They Vote for You,"
  [About](https://theyvoteforyou.org.au/about), They Vote For You.
```

This is an in-prose analogue of `events:`' `quote:` field — same reason (a claim should be
traceable to specific source text, not just a link) — but lighter-touch, since footnotes don't
have a structured field to hang it on. Don't retrofit this onto footnotes that already read
fine as plain citations; apply it to *new* footnotes as they're added, and opportunistically
when an existing footnote is already being touched for another reason.

Footnote quotes now get the same render-time `#:~:text=` treatment as event quotes.
`hooks/footnote_fragments.py` (registered in `mkdocs.yml`) parses the page's markdown
source at build time to find footnotes with verbatim quoted excerpts, then post-processes
the rendered HTML to add `#:~:text=` fragments to their `<a href="url">` links — no
fragment is ever stored in the markdown, same single-source-of-truth rule as events.
Footnote quotes are also mechanically verified by `util/check_fragments.py` in the same
weekly cron pass as event quotes, with the same cache, conditional GET, and AMBIGUOUS
detection. `util/check_footnote_quotes.py` reports current coverage
(local/offline, informational only — not wired into CI or any gate) so the backfill pace
can be tracked over time without committing to finishing it all at once.

**Multi-source footnotes:** when a footnote cites more than one source, the
verbatim quote should come from the source supporting the most specific
claim. If the claims are from different sources and equally important,
prefer splitting into separate footnotes (one per source). For paywalled
sources where only the article lead is visible, quote from the lead text
and note which claims rely on the full article — the mechanical
verification will flag the mismatch, but the footnote still gives readers
more than a bare link.

- `util/createPost.py` — interactive CLI to create a new blog post with frontmatter
- `util/frontmatter_updator.py` — uses OpenAI API to auto-fill frontmatter; requires `util/requirements.txt`

## Architecture (as of May 2026)

### Template system

| Template | Location | Applied to |
|---|---|---|
| `organisation.html` | `docs/overrides/` | All org pages — auto-applied by hook, no frontmatter needed |
| `organisations.html` | `docs/overrides/` | `docs/organisations/index.md` — sortable table index |
| `community.html` | `docs/overrides/` | `docs/community/community.md` — auto-generates active projects grid |
| `project.html` | `docs/overrides/` | Project pages — must set `template: project.html` in frontmatter |
| `home.html` | `docs/overrides/` | Home page — hero pitch, CTA buttons, active projects, map |
| `knowledge-graph.html` | `docs/overrides/` | `docs/knowledge-graph.md` — interactive Cytoscape.js graph; set via `template:` frontmatter |
| `calendar.html` | `docs/overrides/` | `docs/calendar.md` — site-wide future events list + `.ics` subscribe link; set via `template:` frontmatter |

### Hooks

- `hooks/draft_exclude.py` — fires on `on_files` at `event_priority(100)` (i.e. before every other plugin/hook, regardless of `hooks:`/`plugins:` list order); marks any `draft: true` post under `docs/blog/posts/` or `docs/heartbeat/posts/` as `InclusionLevel.EXCLUDED` before `literate-nav` builds the navigation tree. Fixes a real bug: the blog plugin's own draft-exclusion runs late (`event_priority(-50)`, by its own design, so other plugins can add generated posts first) — correctly prevents a draft's page from being built, but by the time it runs, `literate-nav` (default priority, runs earlier) has already auto-attached a nav entry for the unlisted file, since it doesn't check `file.inclusion`. Without this hook, a draft post gets no page (confirmed — no URL exists) but its title still appears as a dead link in the blog's nav sidebar.
- `hooks/org_template.py` — fires on `on_page_markdown`; sets `template: organisation.html` on any page under `organisations/` that doesn't already have a template, and sets `hide: [navigation]` on every page in the section (index + all org pages) so Material's left sidebar doesn't render a nav tree of 100+ orgs — the section is reached via its top nav tab, and browsing within it uses the index page's own filterable/sortable table instead. Registered in `mkdocs.yml` under `hooks:`.
- `hooks/activity_selector.py` — fires on `on_page_context`; reads `page.meta.activity` and resolves it to a single `page.meta.computed_activity` dict using priority order and per-source staleness thresholds. Used by `organisation.html` to render the "Last activity" row. See priority/staleness table in the Organisation pages section.
- `hooks/data_export.py` — fires on `on_pre_build`; generates static data files under `docs/data/` from all org frontmatter. See Data exports section below.
- `hooks/graph_builder.py` — fires on `on_page_context` and `on_post_build`; collects concept/org/project nodes and edges (from `concepts:` frontmatter and "See also" sections) into `graph.json`. Org/project nodes include `activity_date` (best date across all `activity:` sources) used by the graph UI to fade dormant nodes.
- `hooks/org_events.py` — fires on `on_page_context`; splits a single org's `events:` frontmatter into `page.meta.upcoming_events` / `page.meta.history_events` for that org's own page timeline. Also fires on `on_env` to register the `with_fragment` Jinja filter (from `util/text_fragment.py`), which `organisation.html` uses to derive each event's `#:~:text=` link at build time from `quote:` — see Calendar section below.
- `hooks/citation_export.py` — fires on `on_pre_build`; exports all event and footnote citations to `/data/citations.json` in CSL-JSON format with `evidence` array (machine-verifiable citation standard). See `internal-heartbeat/machine-verifiable-citation.md` for the design.
- `hooks/footnote_fragments.py` — fires on `on_page_markdown` and `on_page_content`; parses prose footnotes for verbatim quoted excerpts (same convention as event `quote:`), then post-processes the rendered HTML to add `#:~:text=` fragments to footnote citation links. The counterpart of `with_fragment` for the prose footnote world — derives fragments at build time, never stores them in markdown.
- `hooks/calendar_export.py` — fires on `on_pre_build`/`on_env`; merges every org's future `events:` entries with every org's cached `ics_feed` sync (`docs/data/events/<slug>.json`) into one sorted list, writes `docs/calendar.ics` + `docs/data/events.json`, and injects the list as the `calendar_events` Jinja global used by `docs/overrides/calendar.html`. Makes no network calls itself — see Calendar section below for the fetch step.
- `hooks/shared_link_card.py` — fires on `on_page_markdown`; injects a reader-facing card at the top of a blog post's body from `shared_link:` frontmatter. See "Convention — shared_link" above.
- `hooks/event_card.py` — fires on `on_page_markdown`; injects a reader-facing card at the top of a blog post's body from `event:` frontmatter, reusing the page's own `location:` for an embedded map. Presentational only — deliberately never read by `hooks/calendar_export.py`. See "Convention — event" above.

### Frontmatter — active gates

- `status: active` on a **project** page → appears in the home page projects grid and community page
- `status: active` on an **org** page + `location:` coordinates → appears on the interactive map

### CSS conventions (`docs/assets/css/customizations.css`)

- `.project-status-badge.status-<value>` — coloured status pill (active/inactive/deregistered/mothballed/cancelled)
- `.concept-tag` — indigo chip linking a concept slug to its concept page; used in org metadata box and org index table
- `.org-filter-bar` — flex row wrapping all filter controls on the org index page
- `.org-search-input` / `.org-filter-select` — text search input and dropdowns in the filter bar
- `.org-activity-btn` / `.org-activity-btn.active` — pill buttons for the "Active within" recency filter
- `.org-sortable-table` — sortable org index table
- `.org-ext-link` — small superscript ↗ link on org names pointing to the org's website
- `.org-export-links` — download links row below the table (CSV / JSON / GeoJSON)
- `.activity-method-chip.method-<source>` — coloured chip showing the activity evidence source (rss=orange, sitemap=purple, manual=green, dod=blue, social=pink, scrape=teal)
- `.hero-cta-btn` / `.hero-cta-primary` — home page call-to-action buttons

### URL gotcha

`file.page.url` in MkDocs Jinja2 templates is **root-relative without a leading `/`**. Always prefix with `/` in `href` attributes: `href="/{{ file.page.url }}"`. Omitting the slash causes triple-nested 404s when navigating from deep pages.

### Data exports (`docs/data/`)

Generated at build time by `hooks/data_export.py`. Served as static assets:

| File | Description |
|---|---|
| `/data/organisations.csv` | Flat table — all orgs, one row each. Includes `activity_date`, `activity_method`, `rss_feed`, `ics_feed`, `contact_email`, `contact_phone`, `contact_form`. |
| `/data/organisations.json` | Structured JSON — concepts as arrays, full `activity` dict, computed `activity_date`/`activity_method`. |
| `/data/organisations.geojson` | FeatureCollection — orgs with lat/lon only. |
| `/data/organisations.kml` | KML — orgs with lat/lon, colour-coded by status. |
| `/data/org-concepts.csv` | Edge list (`org_slug`, `concept_slug`) for network/graph analysis. |
| `/data/citations.json` | CSL-JSON — per-URL entries with `content-sha256` and `evidence` array (`type`, `quote`, `last-verified`). Committed (reflects last known verification state from the evidence cache). |

These are linked from the bottom of the org index table for researcher download.

### Utility scripts (`util/`)

- `util/check_rss.py` — probes org websites for RSS/Atom feeds and optionally updates `activity.rss` / `activity.sitemap` / `activity.ical` in frontmatter.
  ```
  python util/check_rss.py                    # probe all active orgs
  python util/check_rss.py --all              # include inactive orgs
  python util/check_rss.py --slug loomio      # single org
  python util/check_rss.py --update-activity  # write latest post date/title to frontmatter
  python util/check_rss.py --skip-existing    # skip orgs already with rss_feed:
  ```
  Probes 23 common feed URL paths per site. For real feeds, writes `activity.rss` with latest post date and title. For sitemaps (fallback), writes `activity.sitemap` with `<lastmod>` date. When `ics_feed:` is set, also fetches the iCal calendar and writes `activity.ical` with the most recent past event date. Never overwrites a newer existing entry for the same source.

- `util/check_event_sourcing.py` — validates and scores every org's `events:` entries. Local/offline (no network), part of both `make build`'s pre-push checklist and CI (`.github/workflows/build.yml`).
  ```
  python util/check_event_sourcing.py                 # check all orgs, hard-gate on unsourced events
  python util/check_event_sourcing.py --slug mosaiclab # single org
  python util/check_event_sourcing.py --calculate      # fill in proof_level on events that lack it
  python util/check_event_sourcing.py --recalculate    # recompute proof_level on ALL events, overwriting
  ```
  `proof_level` (high/medium/low) is always *derived* from a single `confidence_score()` function — never hand-computed separately — so a stored value and a freshly recomputed one can't silently disagree; if they do (source signals changed since the value was last set), it's printed as `STALE PROOF_LEVEL` and `--recalculate` fixes it (skips `proof_level_locked: true` events, printing an FYI instead if a locked value has drifted). The pre-commit hook runs `--recalculate` automatically on every commit touching an org page, so this should rarely need running by hand. Two hard gates (exit 1): every event needs a `url:` or `source:`; every event separately needs at least one of `note:`/`quote:`/`proof_warning: true` (`NO PROOF` if all three are missing — see the `events:` frontmatter docs above for what each means and when to reach for `proof_warning:` vs actually sourcing it). Soft warnings (printed, don't fail the build): vague `source:` text under 20 chars, "weak" URLs — either homepage-only with no path or fragment, *or* a single-segment generic list/index page (`/events/`, `/news/`, `/blog/`, `/calendar/`, `/press/`, `/media/`, `/updates/`, `/whats-on/` — see `GENERIC_LIST_SEGMENTS`) rather than the specific event's own page; both rot the same way, since the cited page keeps changing out from under the claim as newer items push the cited one off the list — `notable: true` events without *mechanical* proof (a `quote:` — a `note:` alone isn't enough for this stricter check), and high/medium-proof events whose `url_checked:` is missing or older than 365 days (a nudge to recheck the citation still says what's claimed — pairs with the two scripts below, which actually do that rechecking).

- `util/check_fragments.py` — mechanically re-verifies evidence against live pages for three sources through the same pipeline: (1) every event's `quote:` field, (2) every prose footnote's verbatim quoted excerpt (per the "Prose footnote citations" convention above), and (3) every blog post's `shared_link.description:` (per the "Convention — shared_link" section above) checked against `shared_link.url`. All evidence shares the same cache (`docs/data/event-evidence-cache.json`, committed), fetch machinery, and AMBIGUOUS detection. Network-dependent, so **not** wired into CI (matches this repo's fetch-then-cache convention of keeping the build offline) — instead runs report-only (`continue-on-error`, doesn't block the RSS/scrape commit) in the weekly `.github/workflows/heartbeat-probes.yml` cron alongside `check_rss.py`/`scrape_news.py`; check that workflow's log for findings. `--save-to-wayback` archives each URL to the Wayback Machine's Save Page Now service (no account needed); `--events-only` scopes verification to just events, skipping footnotes and shared links. Honors `robots.txt` via `util/robots_check.py` before fetching any citation URL — a disallowed URL is recorded with `blocked: "ROBOTS_DISALLOWED"` in the same sticky cache 403/429 uses (see `check_evidence()`'s `BLOCKED_ERRORS`), skipped entirely on later runs. Wikipedia's own extracts API is deliberately not gated — it's designed for exactly this kind of programmatic access (see "Sourcing from Wikipedia" above).
  - **AMBIGUOUS quotes** — a separate, non-blocking category printed alongside MISMATCH: when a quote is found on the page (a "good" match) but occurs *more than once*, the browser's `#:~:text=` highlight isn't guaranteed to land on the occurrence the citation actually means, and the repetition itself is a sign the phrase may be too generic to specifically confirm the claim. `util/text_fragment.py`'s `count_occurrences()` does the counting; only detected on a fresh fetch (a cache hit doesn't retain page text, so it can't re-derive this — ambiguity on an unchanged, already-cached page silently isn't re-flagged until that page's cache entry next expires or `--no-cache` is used). The fix is editorial — lengthen the quote until it's unique on its own page — not a new stored field; see the note above about why fragment disambiguation data (WICG prefix-/-suffix context) is deliberately not persisted in frontmatter. Confirmed in practice on this corpus: most flagged cases (CAPaD, mckinnon.co) turned out to be a *false* ambiguity signal from JSON-LD/page-props payloads embedded in `<script>` tags getting swept into the extracted "page text" alongside the real prose — `_fetch_page_text()` now strips `<script>`/`<style>` bodies before tag-stripping to avoid this. The one genuine case (a Wikipedia article mentioning "Decidim Association" twice in adjacent sentences) was fixed by lengthening the quote to span both mentions, which is unique as a whole even though the short phrase alone wasn't.
  - **STILL BLOCKED / the shared "blocked" cache** — a URL that answers 403/429 (bot protection, not a transient failure) is recorded as `blocked`/`blocked_since` in the same cache file and skipped entirely — no network call at all — on every later run, printed as `STILL BLOCKED` rather than `FETCH ERROR`, until `--no-cache` forces a recheck or the site starts answering normally again (a successful fetch clears the flag). `util/check_event_urls.py` and `util/fetch_shared_link_previews.py` write to and read from this exact same cache/field, so a URL any one of the three scripts has confirmed blocked stays skipped for all three, not just the one that found it. Added after a real gap: none of these scripts remembered a block before this, so the weekly cron re-hit every known-bot-protected site fresh every single run — pointless traffic to a server that had already said no, and (per `check_event_urls.py`'s HEAD-then-GET-fallback design) sometimes two requests per run, not one, since a 403 used to trigger a GET retry too. A transient error (a timeout, a 500) is deliberately NOT sticky like this — only 403/429 mean "this server doesn't want scripted requests," not "try again later."
  ```
  python util/check_fragments.py             # exits 1 if any evidence no longer matches
  python util/check_fragments.py --slug g0v  # single org
  python util/check_fragments.py --slug g0v --slug namfrel  # multiple orgs — --slug is repeatable
  python util/check_fragments.py --no-cache  # ignore the cache, re-fetch and re-verify everything, including URLs already confirmed BLOCKED
  python util/check_fragments.py --save-to-wayback  # archive each URL to Wayback Machine
  python util/check_fragments.py --events-only     # only check event evidence (original behaviour)
  python util/check_fragments.py --autofix-spaces  # rewrite spacing-only MISMATCHes in place
  python util/check_fragments.py --report /tmp/fragments-report.json  # also write a JSON findings summary (for ad hoc/manual review — not consumed by anything in CI)
  ```
  - **`--autofix-spaces`** — fixes MISMATCHes whose only differences from the live page
    are space runs (em-dash spacing, stray spaces): rewrites the stored `quote:` in the
    source file to the page's text. Safe by construction — if only spaces differ, the
    quote's words are a contiguous substring of the page's, so the fix can't change what
    the quote claims — and it also makes the reader-facing `#:~:text=` highlight work,
    since the page's whitespace-normalised text is what the browser renders. Deliberately
    **spaces only**: punctuation, case, content changes, and the "page continues past the
    quote" case (e.g. `quote: "…pilot."` vs page `"…pilot, followed by…"`) all stay
    MISMATCH for human judgment — where a quote ends is an editorial choice, and the
    extra text is a genuine page-drift signal a MISMATCH is supposed to surface, not hide.
    Refuses if the corrected text would appear more than once on the page (human should
    lengthen the quote instead), refuses to write unless the old string occurs exactly
    once in the file, and marks the corrected string verified against that fetch. Quotes
    stored as plain YAML scalars are replaced as raw text; folded/quoted scalars (the
    form YAML itself picks for values containing `: ` or apostrophes, where the parsed
    value isn't verbatim in the file) are rewritten via a frontmatter re-serialization
    that keeps canonical ordering (`util/reorder_frontmatter.py --check` still passes)
    — the raw substring search alone used to silently give up on those. Writes
    to source files, so **don't pass it in the weekly cron** — run it on a reviewable
    branch and check the git diff, same as `check_rss.py --update-activity`.
  The `#:~:text=` fragment-building functions it used to also expose via `--add-fragments` now
  live in `util/text_fragment.py` — a small, dependency-free module imported both here (not
  actually needed anymore, since verification only ever checks `quote:`) and by
  `hooks/org_events.py`, which registers `with_fragment` as a Jinja filter so
  `organisation.html` derives each event's fragment-bearing link at build time. Fragments are
  never written back to frontmatter — see the "events:" `#:~:text=` docs above for why.

- `util/check_event_urls.py` — liveness check for every event's `url:` citation (HEAD request, GET fallback for hosts that don't support HEAD). Catches the failure mode neither of the two scripts above does: a citation URL 404ing, redirecting, or its host disappearing. Distinguishes `DEAD` (404/5xx — a real problem, needs a replacement citation) from `BLOCKED` (403/429 — near-certainly bot/scraper protection, e.g. Cloudflare; several sites in this landscape are confirmed reachable-in-a-browser-but-403-to-scripts, so don't "fix" a BLOCKED citation without manually checking it in a real browser first) from `REDIRECT` (informational — citation still resolves, consider updating the URL to the canonical target). Network-dependent, not in CI; also runs report-only in the same weekly cron as `check_fragments.py` above. A HEAD that comes back 403/429 does **not** trigger the GET fallback (only 405/501 — genuine "HEAD not supported" signals — do) — a GET immediately after would almost certainly hit the same block, doubling the request for no new information. Shares `check_fragments.py`'s "blocked" cache (see that entry's STILL BLOCKED bullet above) — a URL already confirmed BLOCKED is skipped with zero requests on later runs until `--no-cache`. Unlike `check_fragments.py`, a BLOCKED result here does **not** queue a manual-dump request (see `util/manual_dump.py`) or consult `manual_verified` — this script checks bare URL liveness, not a specific quote, so there's no evidence hash for a manually-saved snapshot to verify against. Also checks `robots.txt` (same shared implementation, same cache — a `ROBOTS_DISALLOWED` entry written by either script is honored by both) before ever issuing the HEAD/GET; reported as `ROBOTS.TXT DISALLOWED`/`STILL ROBOTS-BLOCKED`, separately from `DEAD`/`BLOCKED`, and never causes a non-zero exit — it's DOD respecting the site's own opt-out, not a citation problem.
  ```
  python util/check_event_urls.py                  # check all event URLs
  python util/check_event_urls.py --slug mosaiclab  # single org
  python util/check_event_urls.py --timeout 8       # per-request timeout
  python util/check_event_urls.py --no-cache        # recheck URLs already confirmed BLOCKED
  python util/check_event_urls.py --report /tmp/urls-report.json  # also write a JSON findings summary (for ad hoc/manual review — not consumed by anything in CI)
  ```

- `util/fetch_shared_link_previews.py` — fetches Open Graph / oEmbed metadata for blog posts' `shared_link.url` and fills in missing `title:`/`image:`/`description:` (see "Convention — shared_link" above). `title:`/`image:` are freely written whenever missing (or always with `--force`); `description:` is only ever written when independently confirmed to appear verbatim in the same page's body text — the exact check `check_fragments.py` runs on it forever after — so it never hands that script's next run a guaranteed MISMATCH. Writes via a full `python-frontmatter` round-trip, not raw-text splicing (blog posts have no canonical field order to preserve, unlike org pages). Shares `check_fragments.py`'s "blocked" cache.
  ```
  python util/fetch_shared_link_previews.py                              # report only, all posts with shared_link: url
  python util/fetch_shared_link_previews.py --post 2026-08-16-habermas-machine-ai-mediation
  python util/fetch_shared_link_previews.py --write                      # write missing title:/image:
  python util/fetch_shared_link_previews.py --write --write-description  # also attempt description: (only when it verifies)
  python util/fetch_shared_link_previews.py --write --force              # overwrite existing title:/image: too
  python util/fetch_shared_link_previews.py --no-cache                   # recheck URLs already confirmed BLOCKED
  ```

- `util/reorder_frontmatter.py` — enforces the canonical frontmatter field ordering documented above (org top-level keys, `events:` sub-keys, `activity:` sub-keys). Local/offline, part of `make build`'s pre-push checklist and CI. The pre-commit hook (`.githooks/pre-commit`) runs this automatically on staged org pages, so `--check` failing locally usually means the hook isn't installed — see the note at the top of this file.
  ```
  python util/reorder_frontmatter.py            # reorder all org pages in place
  python util/reorder_frontmatter.py --check    # report only, exit 1 if any need reordering
  python util/reorder_frontmatter.py --slug mosaiclab  # single org
  ```

- `util/check_footnote_quotes.py` — reports how many prose footnote citations (org pages, blog posts, concept pages) carry a verbatim quoted excerpt vs. a bare title/source/date citation. Local/offline, informational only — not wired into CI or any gate, but tracks the backfill pace.
  ```
  python util/check_footnote_quotes.py             # summary across all docs
  python util/check_footnote_quotes.py --missing    # list footnotes without a quote
  python util/check_footnote_quotes.py --path docs/organisations/g0v.md  # single file
  ```

- `util/manual_check_worklist.py` — generates a plain checklist for a human to verify citations `check_fragments.py` can't resolve by itself. Two modes: the default (offline, no network) reads `event-evidence-cache.json`'s `blocked` entries — URLs that have returned 403/429 to a script and are deliberately never auto-retried (see `check_fragments.py`'s docstring on why that's sticky) — and lists them with the exact quote to Ctrl+F for. `--live` instead fetches every not-yet-blocked citation fresh and additionally surfaces current AMBIGUOUS (quote occurs more than once on the page) and MISMATCH findings, which aren't persisted to the cache the way BLOCKED is — the only way to get a current list of those without re-running `check_fragments.py` and reading its console output. Never edits a source file; the fix (or the decision that no fix is needed) still happens by hand after checking the page in a real browser, where the network path and browser fingerprint look nothing like a script's — confirmed useful in practice on `radicalxchange.md`'s `glenweyl.com` citation, which resets the connection for both plain HTTP and headless-Chromium requests alike.
  ```
  python util/manual_check_worklist.py                # offline: list BLOCKED citations
  python util/manual_check_worklist.py --live          # also fetch fresh, flag AMBIGUOUS/MISMATCH too
  python util/manual_check_worklist.py --slug radicalxchange --events-only
  python util/manual_check_worklist.py --out /tmp/worklist.md
  ```

- `util/manual_dump.py` / `util/import_manual_dump.py` — an escape hatch for citation URLs that stay unreachable to every automated path (bot protection, rate limits — both the origin site's own and Wayback Machine's Save Page Now — or robots.txt) but a human's own browser can still load fine. `manual-dump/` lives at the repo root, entirely gitignored — local working state, not archival; the durable, shareable copy of a citation is still Wayback Machine (`check_fragments.py --save-to-wayback`), not this.

  **Maintainer runbook — steps to actually do this:**
  1. Run `cat manual-dump/requests.txt` (or just check whether the file exists — `check_fragments.py`/`git status` won't remind you, since the directory is gitignored). Each line is a URL waiting on a human.
  2. Open each URL in a real browser and let it fully load (wait out any JS-rendered content).
  3. **Firefox: File → Save Page As → "Web Page, HTML only"** (not "Web Page, complete" — that also writes a folder of asset files nothing here needs). Save into `manual-dump/snapshots/`; the filename doesn't matter.
  4. Run `python util/import_manual_dump.py --dry-run` first to preview what will be matched/imported, then `python util/import_manual_dump.py` for real.
  5. `git diff docs/data/event-evidence-cache.json` and skim the new `manual_verified` entries before committing — same spot-check judgment as reviewing any other automated write to this file.
  6. Re-run `check_fragments.py` (or just check its next report) to confirm the citation no longer shows as STILL BLOCKED.

  Mechanism, for reference:
  - Whenever `check_fragments.py` hits a BLOCKED citation with no manual coverage for that exact evidence yet, it appends the URL to `manual-dump/requests.txt` (deduplicated).
  - Firefox (like Chrome and IE/Edge) stamps a `<!-- saved from url=(NNNN)https://... -->` comment as the saved file's first line, which is how `import_manual_dump.py` recovers the source URL — no need to separately record it.
  - `import_manual_dump.py` extracts text with the same `text_fragment.html_to_text()` a live fetch uses (so a quote verifies identically against either path), checks it against every citation currently pointing at that URL, records each result in the shared evidence cache as `manual_verified: {hash: bool}` / `manual_checked: <date>`, removes the URL from `requests.txt`, and moves the file into `snapshots/imported/` so a re-run doesn't reprocess it.
  - `manual_verified` is a separate field from the automated `verified` map, never merged into it — stale automated data captured before a site started blocking scripts must never be silently presented as reconfirmed just because an unrelated snapshot was imported later. `check_evidence()` consults `manual_verified` for the specific evidence hash being checked *before* falling back to reporting STILL BLOCKED, and also when a fetch succeeds but returns less text than the evidence string is long (a JS-rendered SPA shell or bot-challenge holding page — confirmed on governancehubafrica.org/about, 21 chars of title vs ~8,000 rendered; the quote can't possibly be there, so that's a fetch failure reported as `PAGE_TOO_SHORT`, not a MISMATCH), so a manually-resolved citation stops being reported as blocked without the origin site ever needing to cooperate again. Unlike a 403 this is deliberately not sticky-cached — a shell-to-server-rendered switch is a realistic recovery, so each run re-fetches and self-heals if the site changes.
  - A snapshot whose recovered URL doesn't match any current citation is left in place (not moved) and reported — more likely a mistake (wrong page saved, or the citation was since removed) than something to silently discard.

- `util/sync_events.py` — fetches every org's `ics_feed:` and caches *upcoming* events (not just the latest, unlike `check_rss.py`'s activity check above) to `docs/data/events/<slug>.json`, which is committed to the repo and consumed by `hooks/calendar_export.py` at build time. This is the only place the calendar's iCal data touches the network — the build itself never fetches anything, matching the rest of this repo's fetch-then-cache convention.
  ```
  python util/sync_events.py                    # sync all active orgs with ics_feed:
  python util/sync_events.py --all               # include inactive orgs
  python util/sync_events.py --slug g0v          # single org
  python util/sync_events.py --dry-run           # print results without writing
  python util/sync_events.py --max-events 15     # cap events cached per org (default 15)
  python util/sync_events.py --horizon-days 365  # only keep events this many days out (default 365)
  ```

- `util/scrape_news.py` — scrapes news/blog index pages for orgs that lack a usable RSS feed. Opt-in: only runs for orgs with `news_page:` set in frontmatter. Extracts dates from multiple signals in priority order: JSON-LD → `<meta>` / microdata (`itemprop="datePublished"`) → `<time datetime>` → `<time>` text content → URL path patterns (`/2026/01/15/`) → human-readable text date patterns ("January 15, 2026" etc.). Also detects `<link rel="alternate">` RSS/Atom feeds in the page `<head>`. Respects robots.txt. Writes `activity.scrape`.
  ```
  python util/scrape_news.py                  # all active orgs with news_page:
  python util/scrape_news.py --all            # include inactive orgs
  python util/scrape_news.py --slug loomio    # single org
  python util/scrape_news.py --dry-run        # print results without writing
  python util/scrape_news.py --debug          # show what date signals were found on each page
  python util/scrape_news.py --update-rss     # write discovered RSS feed URLs to rss_feed: frontmatter
  python util/scrape_news.py --update-ics     # write discovered iCal feed URLs to ics_feed: frontmatter
  python util/scrape_news.py --force          # re-scrape even if checked recently or spa/bot_blocked
  ```

- `util/check_contact.py` — probes org websites for publicly-published email/phone/contact-form info and optionally writes them to `contact:` frontmatter. Fetches the homepage plus common contact-page paths (`/contact`, `/about`, `/get-involved`, …), respecting robots.txt. Two trust tiers: emails (`mailto:` links, Cloudflare-obfuscated `data-cfemail` attributes, or plain `@domain.tld`-shaped text) and detected public contact forms (a `<form>` with an email/message-shaped field, on a page whose URL reads as the contact page) are "high confidence" — **safe for `--write` to run unattended across the full org list**, since neither involves text-parsing guesswork. Phone numbers are the opposite: `tel:` links are high confidence, but phone-shaped digit sequences in plain text are "low confidence" and report-only, never auto-written — digit runs produce real false positives (dates, postcodes, prices) that `@domain.tld` text and `<form>` detection don't. Comparison-testing the email/tel: tier against org contact info already sourced by hand found it matched almost exactly; the disagreements were judgement calls (which of several valid published addresses is the right one to record — see the preference order in the Organisation pages `contact:` convention above) rather than parsing failures, so treat that choice, and any `--force` overwrite, as worth a spot-check in the resulting diff rather than blindly trusting every write. Existing `contact.email`/`contact.phone`/`contact.form` values are never overwritten unless `--force`.
  ```
  python util/check_contact.py                 # report on active orgs missing contact info
  python util/check_contact.py --all            # include inactive orgs
  python util/check_contact.py --slug loomio    # single org
  python util/check_contact.py --write          # write high-confidence findings (email/tel:/form) to contact:
  python util/check_contact.py --force          # re-check/overwrite orgs that already have contact info
  ```

- `util/check_contact_deep.py` — headless-browser (Playwright + Chromium) companion to `check_contact.py`, for orgs whose site is a client-side-rendered SPA (confirmed on vtaiwan.tw: every path served an identical near-empty `<div id="app"></div>` shell, invisible to a plain HTTP fetch regardless of what's actually published). Reuses `check_contact.py`'s crawl/extraction functions directly rather than duplicating them, so the two tools can't silently diverge on what counts as a match. Not in `util/requirements.txt`'s default install (`pip install playwright && playwright install chromium` — a real browser binary, not just a package) since most `check_contact.py` usage never needs it. **Unverified end-to-end as written** — see the docstring for why (a sandbox proxy issue blocked all headless-Chromium network access while ordinary HTTP clients worked fine); confirm it actually renders and extracts real content against a known SPA before trusting its output.
  ```
  python util/check_contact_deep.py --slug vtaiwan   # one org, deep-rendered (slow: full browser nav per URL)
  python util/check_contact_deep.py --slug vtaiwan --write
  python util/check_contact_deep.py                   # all active orgs missing contact.email (very slow)
  ```

### Org index table filters (`docs/overrides/organisations.html`)

The `/organisations/` index table has four combinable filters:

| Control | Default | What it filters |
|---|---|---|
| Text search | empty | Full row text (name, type, country, concepts) |
| Type dropdown | All types | `type:` frontmatter value |
| Country dropdown | All countries | `country:` frontmatter value |
| Status dropdown | **Active only** | `status:` frontmatter value |
| Activity recency | All time | Days since best activity date |

Both the type and country dropdowns are auto-populated from row data at page load. Filters are AND-combined. A live count shows matching organisations below the table.

The "Last active" column shows the best-date ISO string + a method chip. Best date is computed in Jinja2 directly from the raw `activity:` dict using ISO string comparison (no hook dependency) so it works on the index page where `computed_activity` may not yet be set.

