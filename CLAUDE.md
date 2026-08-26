# Claude Code Notes

## Tech Stack

This is a MkDocs + Material for MkDocs static site deployed to GitHub Pages.

- Build: `mkdocs build` (or `make build`)
- Local dev: `make serve`
- Deploy: CI pushes to `gh-pages` branch via `mkdocs gh-deploy --force`
- Python deps: `requirements.txt` (site build), `util/requirements.txt` (utility scripts only)
- Before pushing: `make build && python util/check_internal_links.py && python util/check_event_sourcing.py && python util/reorder_frontmatter.py --check && python util/check_footnote_quotes.py` — catches the same errors as CI. The pre-commit hook (`.githooks/pre-commit`) auto-runs `reorder_frontmatter.py` (which fixes frontmatter ordering in place) on staged org pages, so the `--check` should always pass — it's a safety net. `check_footnote_quotes.py` also runs in the hook on any staged docs page, but it can't auto-fix a missing justification the way `reorder_frontmatter.py` can reorder fields — it blocks the commit until a quote or an `unquoted:` annotation is added by hand.
- **If `.git/hooks/pre-commit` doesn't exist:** run `ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit` to install it. Claude should check this on first interaction with the repo and remind the user if it's missing.

## Tests (`tests/`)

Stdlib `unittest` regression coverage for the citation-verification tooling (`util/text_fragment.py`, `util/check_fragments.py`) and the bot's robots.txt compliance (`util/robots_check.py`, `util/check_event_urls.py`) — offline, no network calls, no new deps beyond what `util/requirements.txt` already installs plus `pyyaml`. Lives at repo root (outside `docs/`) so mkdocs never touches it. Run with:
```
python -m unittest discover tests   # or: just test
```
Wired into CI (`.github/workflows/build.yml`) as its own step, before the build/lint jobs. Covers the pure functions in `text_fragment.py` (`normalize_ws`, `find_span`, `quote_matches`, `_split_ellipsis`, `make_text_fragment`/`add_fragment_to_url`/`with_fragment`, `spacing_autofix`, `closest_match_hint`, footnote parsing) directly, plus the I/O-adjacent parts of `check_fragments.py` via fixture files in a tempdir: `paragraph_hash` (regression test for the offset-drift bug — see its docstring), `wikipedia_title` (including the non-English-subdomain regression), `write_quote_fix`/`_write_quote_fix_yaml` (the plain-scalar and YAML-scalar success paths, plus all three refusal cases: no frontmatter, ambiguous quote across events, non-canonical existing frontmatter), `collect_evidence`'s `--slug` filtering (the exact `--slug a --slug b` regression from 2026-08-14, plus the 2026-08-25 scoping fix that stopped `--slug` from silently re-fetching every footnote on the site), the `--max-age` freshness gate (`StalenessGateTests` — per-quote vs URL-level dating, the deterministic jitter that stops the corpus falling due on one day, and unparseable/missing dates reading as never-checked), `--full` scan mode and the not-a-no-op top-up (`FullScanModeTests`, `SpotCheckSampleTests` — including that a negative window means full scan, never skip-everything), `check_evidence`'s no-cache write path (`CheckEvidenceNoCachePreservesOtherEvidenceTests` — a successful `--no-cache` re-fetch must merge into the URL's stored evidence rather than rebuilding it, the 2026-08-25 28-quote data-loss regression — see the "Utility scripts" `check_fragments.py` entry below), and `_fetch_page_text`'s robots.txt gate (disallowed URLs are never requested; Wikipedia's own API is deliberately not gated). `test_robots_check.py` covers `robots_check.py` directly, including the regression that motivated it: an unreachable/unparseable robots.txt must resolve to "allow everything," not the `RobotFileParser` default of "deny everything" for a parser that never had `parse()`/`read()` called successfully. `test_normalize_tags.py` covers `hooks/normalize_tags.py`'s tag folding, including the invariant that its slug always matches the anchor `hooks/tag_links.py` builds — if those two ever disagree a tag chip links to an anchor no section carries, which is the duplicate-anchor bug in a new form. `test_check_event_urls.py`'s `CheckUrlCachedTests` covers the same sticky-cache treatment for a robots.txt disallow that `HTTP_403`/`429` already got (shared cache format, see `check_event_urls.py`'s entry below). When adding new verification logic to either file, add a test alongside it rather than validating by hand-running against real org files — see issue #155 for the motivating history of bugs this would have caught.

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

## Re-reading cited pages: prefer `.pagecache/` over re-fetching

Before an AI session fetches any cited URL to see what it says, check whether a local copy already exists — `.pagecache/` (see `util/pagecache.py`) holds plain-text captures of every page `check_fragments.py` has fetched, each stamped with its last-confirmed date:

- **Reading** what a cited page said: `just page-cache show <url-substring>`. Zero requests to anyone's webserver.
- **Adjusting a quote** while editing (`quote:`, footnote excerpts, `shared_link.description:`): verify the reworded text against stored copies with `just verify-quotes --offline --slug <org>` — no network, no cache writes.
- **Populating**: copies only exist for URLs fetched on *this machine*; one fetching pass (`just verify-quotes --no-cache --slug <org>`) fills them in.

Only go to the live site when there's genuinely no stored copy, or when currentness is the question being asked (has this page changed?). This is deliberate politeness to webadmins — review work shouldn't re-hit servers that already answered us once — and it's faster for the session too. Caveat to state in any conclusion drawn from a copy: its facts are "as of last fetch" (the date shown by `page-cache list`), not necessarily today. Official verification stays with the live run — offline answers never write to the evidence cache.

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
   - **Multi-day events** — `end_date:` / iCal `DTEND` (auto-parsed by `util/sync_events.py`, exclusive per RFC 5545 §3.6.1 so a normal 1-day all-day event doesn't misreport as 2 days) render as a date range instead of a single day: the date block's weekday line spans it ("WED–SUN"), and the details line carries an outlined `.calendar-event-range` chip with the span and its length ("📆 26–30 Aug · 5 days"). Year and month are repeated only when the range actually crosses one ("28 Aug – 2 Sep", "30 Dec 2026 – 2 Jan 2027"), so the common same-month case stays short. This line documented the range rendering well before it existed — until 2026-08-26 `end_date` reached the `.ics` export and the JSON-LD but nothing a reader could see, leaving a third of the calendar's events (8 of 26 at the time) showing only their first day.
   - **"Major event" highlighting** — `notable: true` gets the calendar's highlighted styling (colored cell, larger text, a "★ Major event" badge). Deliberately **not** available on raw `ics_feed` syncs — a synced feed has no "this one matters more" signal to key off, only the curated `events:` source does.

   **Client-side past-event collapse and today/tomorrow highlighting.** Since the calendar page is static (built at deploy time), an event that was future-dated at build time can have already passed by the time a visitor actually loads the page — there's no server-side "now" to filter against. `calendar.html`'s JS (`collapsePastAndHighlightNear()`, run once on load before `applyFilter()`) fixes this up client-side: it walks every `<li class="calendar-event">` (each carries a `data-date="YYYY-MM-DD"` attribute for this purpose), and for any event whose date is before today, moves it out of its month's list and into a single collapsed `<details class="calendar-past-events-details">` inserted above the month groups — collapsed by default, so a returning visitor's "what's current" view isn't pushed down by events that have already happened. Today's and tomorrow's events instead get a `calendar-event--today`/`--tomorrow` class (green/blue left-border + tinted background, styled in `customizations.css`) and an inline "Today"/"Tomorrow" badge prepended to their header — collapsing would be wrong for these, since they're the most relevant events on the page, not stale ones. Events 2–7 days out get a third, lighter tier: a plain "This week" badge (`calendar-event-badge--week`) with no border/background change — deliberately weaker than today/tomorrow's treatment, since highlighting every event in the coming week as strongly would drown out the "truly imminent" signal today/tomorrow are meant to give on a calendar aggregating many orgs' events. Past-ness is judged on an event's *end* (`data-end-date`/`data-end-time`, falling back to the start date's 23:59), not its start, so a multi-day event that's currently running stays in the main list with an "On now" badge and a `calendar-event--ongoing` class instead of being collapsed away as history. `updateCount()` excludes anything inside the collapsed past-events `<details>` from its "N events" tally, matching what a visitor can actually see without expanding it. Local-midnight dates are parsed manually (`parseLocalDate()`) rather than via `new Date("YYYY-MM-DD")`, which parses as UTC midnight and off-by-ones for negative-UTC-offset viewers. Verified via a headless-browser check with `Date` monkey-patched to a fixed instant, served over a real local HTTP server (not `file://`, which has its own unrelated image-loading quirks) — confirmed correct collapse/highlight/count behaviour and that `<img loading="lazy">` calendar logos (unrelated pre-existing behaviour) load fine once scrolled into view.

   **Live countdown per event.** The same "no server-side now" reasoning gives each event a countdown pill on its details line, written client-side by `renderCountdowns()` from the viewer's own clock (the span is rendered empty at build time and hidden by CSS's `.calendar-countdown:empty`, so a JS-less reader sees nothing rather than a stale number). Precision is a ladder that slides one unit at a time as the event nears — `in 1y 7mo 12d` → `in 3mo 1w 5d` → `in 3w 2d 04h` → `in 5d 04h 30m 09s` → `in 4h 30m 09s` → `in 12m 09s` — deliberately, since a seconds counter is useful in the last hour before a meetup and pure distraction on a row four months out. Weeks carry the two middle tiers because that's the unit people plan a month or two ahead in ("three weeks away" lands where "in 23 days" has to be counted out); below a week the day column no longer needs splitting. An event already underway reads `on now · 3d 06h left`, but only where a real end was published (`end_date:`/`end_time:`); for an all-day event the 23:59 end is a placeholder this code invented, so counting down to it would state a deadline the source never did. Past events (inside the collapsed `<details>`) read `yesterday` / `6 days ago`.

   Two implementation points worth knowing before touching it. **`breakdown()` borrows across the real calendar, in a loop, not a single step** — months and years have no fixed length, and an hour borrowed from the days column can push days one month further back than the previous month covers (31 Aug 10:00 → 1 Oct 00:00 needs September's 30 days *and* August's 31 to come out at `30d 14h`; a single borrow leaves it at a nonsensical `-1d`, which is exactly what the first draft printed). Walking the calendar rather than dividing by an average month also keeps "in 1y" landing on the actual anniversary and stays right across a DST change. **The tick rate follows what's on screen**: `renderCountdowns()` reports whether any row is currently showing seconds, and `scheduleCountdown()` re-arms at 1s if so and 30s otherwise (enough for a minute or midnight rollover), pausing entirely on `visibilitychange` when the tab is hidden. Rows are only written when their text actually changes, and on a ticking row every unit is held (zeros included) with hours/minutes/seconds zero-padded against `font-variant-numeric: tabular-nums`, so it never reflows as it counts down — an interior zero has to stay there anyway, since "in 3d 0h 12m 05s" collapsing to "in 3d 12m 05s" would read as a far shorter wait. A row that doesn't tick has neither problem, so `fmt()` drops every zero unit there except the leading one ("in 4mo 5d", not "in 4mo 0w 5d").

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
are freeform text with no YAML schema, so that discipline used to not apply to them at all —
most existing footnotes are pure citation-style (title, source, date), not verbatim excerpts.

**Where the cited source has a specific sentence that supports the claim**, include it as a
verbatim quoted phrase in the footnote text itself, e.g.:

```
[^tvfy-about]: "today the OpenAustralia Foundation is launching a new site They Vote for You,"
  [About](https://theyvoteforyou.org.au/about), They Vote For You.
```

This is an in-prose analogue of `events:`' `quote:` field — same reason (a claim should be
traceable to specific source text, not just a link) — but lighter-touch, since footnotes don't
have a structured field to hang it on.

**When a footnote can't carry a quote, it must instead carry a justification** — a trailing
`<!-- unquoted: type: reason -->` HTML comment on the same footnote-definition line, e.g.:

```
[^cw-about]: "Registered since 2001," [Council Watch](https://www.councilwatch.com.au), Council Watch website footer.
[^some-ref]: [Some Page](https://example.org/page), Example Org. <!-- unquoted: bot-blocked: example.org returns a Cloudflare challenge to automated fetches, confirmed 2026-08-21 -->
```

This is a hard gate (`util/check_footnote_quotes.py`, wired into CI and the pre-commit hook —
see that script's entry below), not a style preference: a citation-only footnote with neither a
quote nor an `unquoted:` annotation fails the build. `type` is an open vocabulary (same spirit
as `ai_assist:`/`origin:` elsewhere in this file) — established values in use: `legacy`
(predates this convention, not individually reviewed — the backfilled default for pre-existing
footnotes), `bot-blocked`, `paywalled`, `no-single-sentence` (the source supports the claim but
no single verbatim sentence captures it), `multi-source` (see below), `non-web-source`,
`not-yet-verified` (a deliberate backlog marker, same spirit as events' `proof_warning: true`).
Avoid literal quote characters inside the `reason` text — they can be misread as a verbatim
excerpt by the same line's quote-extraction regex.

**This gate exists because of a real incident, not preemptively**: an AI-authored footnote was
left citation-only with no reason recorded, not because the source resisted quoting but because
the underlying claim had been sourced from a summarizing tool's paraphrase rather than the
page's actual text — and that shortcut was invisible in review. A required justification does
not make the underlying claim correct on its own (a model can misjudge or misstate a reason
the same way it can misstate a quote), but it converts a silent gap into a reviewable one,
which is the realistic ceiling for what a lint step can enforce here. **The actual fix is
upstream of any lint**: WebSearch/WebFetch output is a *lead*, not a *source* — before writing
any quote or specific factual claim (a name, a date, a statute number, a legal/criminal status),
fetch the page's raw text directly (e.g. `curl` + `util/text_fragment.py`'s `html_to_text()`,
not a summarizing tool) and confirm the claim against it. See
`internal-heartbeat/` for the incident writeup if one exists for a given case.

Footnote quotes get render-time `#:~:text=` treatment. `hooks/footnote_fragments.py`
(registered in `mkdocs.yml`) parses the page's markdown source at build time to find footnotes
with verbatim quoted excerpts, then post-processes the rendered HTML to add `#:~:text=`
fragments to their `<a href="url">` links — no fragment is ever stored in the markdown, same
single-source-of-truth rule as events. Footnote quotes are also mechanically verified by
`util/check_fragments.py` in the same weekly cron pass as event quotes, with the same cache,
conditional GET, and AMBIGUOUS detection.

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

### Citation archival: Wayback links and url_status

**No frontmatter fields exist for this, on purpose** — an event, a footnote, and a `shared_link:` can all cite the same real-world URL, and whether that URL is archived or dead is a fact about the *URL*, not about which citation happens to reference it. Storing it per-citation would let two citations of the same source silently disagree. Instead, archival state lives in one place, keyed by URL: `docs/data/citation-state.json` (the same committed evidence cache `check_fragments.py` already uses for quote verification — see above). Everything else (rendering, the CSL-JSON export) reads from it; nothing else ever writes to it. See `internal-heartbeat/2026-08-22-citation-archival-design-decisions.md` for the full design conversation, including how this replaced an earlier, uncoordinated second write path (`util/citations_tool.py --archive`) that called Wayback independently and wrote straight into `citations.json` — that flag still exists for verifying/archiving a **third-party** citations.json (its original, still-valid use case), but DOD's own `docs/data/citations.json` should never be populated that way, since the build now projects it fresh from the evidence cache every time (see below) and would just overwrite it.

- **`archive_url`** — a citation URL's Wayback Machine snapshot, written only by `util/check_fragments.py --save-to-wayback`. Purely additive by default: rendering adds a small "🗃️ Archived copy" link next to the normal citation link (both event timelines via `hooks/org_events.py`'s `archive_info_for` Jinja filter, and prose footnotes via `hooks/footnote_fragments.py`), without changing which link is primary.
- **`url_status`** — `dead` (site 404s/unreachable — `check_event_urls.py` can detect this) or `unfit` (resolves, but to a parked domain/spam/unrelated content — **not machine-detectable**; a parked domain answers a normal 200, so this needs a human to actually look at the page, the same way the horizon-state.com case was caught). Set only by hand, via `util/check_fragments.py --set-url-status <url> <dead|unfit|live>` (`live` clears the field back to the implicit default) — **never auto-inferred or auto-written by any script**, same human-in-the-loop precedent as `proof_level_locked:`. `check_event_urls.py` prints a suggested command when it finds a `DEAD` verdict, but does not set the field itself.
- **Once `url_status` is `dead` or `unfit` and an `archive_url` exists**, rendering flips to Wikipedia's own `Help:Citation Style 1` convention: the archive becomes the primary, clickable link (with its own `#:~:text=` fragment, since that's the page verification would actually be checking against), and the original is demoted to a small "(original, no longer live: ...)" trailer rather than a second live-looking link. Below that threshold (no `url_status`, or `live`), behavior is unchanged from the plain additive case above.
- **`docs/data/citations.json`** (see Data exports below; gitignored, regenerated at every build) reflects the same two fields — via the real CSL-JSON `archive`/`archive_location` fields, plus a DOD extension field `url-status` — as a **read-only projection** generated fresh by `hooks/citation_export.py` on every build. It never carries these three fields forward from its own previous output on disk, specifically so a stale or since-corrected verdict from an earlier local build can't survive a rebuild that disagrees with the current evidence file.

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
- `hooks/org_events.py` — fires on `on_page_context`; splits a single org's `events:` frontmatter into `page.meta.upcoming_events` / `page.meta.history_events` for that org's own page timeline. Also fires on `on_env` to register two Jinja filters: `with_fragment` (from `util/text_fragment.py`), which `organisation.html` uses to derive each event's `#:~:text=` link at build time from `quote:` — see Calendar section below — and `archive_info_for`, which looks up a citation url's recorded Wayback snapshot/`url_status` for the archive-link rendering described in "Citation archival" above.
- `hooks/citation_export.py` — fires on `on_pre_build`; exports all event and footnote citations to `/data/citations.json` in CSL-JSON format with `evidence` array (machine-verifiable citation standard), plus a read-only projection of `archive`/`archive_location`/`url-status` from the evidence cache (see "Citation archival" above). See `internal-heartbeat/machine-verifiable-citation.md` for the original design and `internal-heartbeat/2026-08-22-citation-archival-design-decisions.md` for the archive-projection addition.
- `hooks/footnote_fragments.py` — fires on `on_page_markdown` and `on_page_content`; parses prose footnotes for verbatim quoted excerpts (same convention as event `quote:`), then post-processes the rendered HTML to add `#:~:text=` fragments to footnote citation links. The counterpart of `with_fragment` for the prose footnote world — derives fragments at build time, never stores them in markdown. Also adds/swaps in Wayback archive links the same way `hooks/org_events.py` does for events — see "Citation archival" above.
- `hooks/calendar_export.py` — fires on `on_pre_build`/`on_env`; merges every org's future `events:` entries with every org's cached `ics_feed` sync (`docs/data/events/<slug>.json`) into one sorted list, writes `docs/calendar.ics` + `docs/data/events.json`, and injects the list as the `calendar_events` Jinja global used by `docs/overrides/calendar.html`. Makes no network calls itself — see Calendar section below for the fetch step.
- `hooks/shared_link_card.py` — fires on `on_page_markdown`; injects a reader-facing card at the top of a blog post's body from `shared_link:` frontmatter. See "Convention — shared_link" above.
- `hooks/event_card.py` — fires on `on_page_markdown`; injects a reader-facing card at the top of a blog post's body from `event:` frontmatter, reusing the page's own `location:` for an embedded map. Presentational only — deliberately never read by `hooks/calendar_export.py`. See "Convention — event" above.
- `hooks/normalize_tags.py` — fires on `on_page_markdown` at `event_priority(100)`, i.e. before mkdocs-material's tags plugin collects `page.meta["tags"]` in its own `on_page_markdown` (priority -50); folds every tag to the lowercase-hyphen slug the plugin anchors on, deduplicating. **Tags are matched case-insensitively because of this hook, not by the plugin.** The plugin treats each distinct tag *string* as its own tag while slugifying them all into one anchor id, so `Deliberative Democracy` and `deliberative-democracy` emitted two `<h2>` sections sharing `id="tag:deliberative-democracy"` — and because the plugin sorts case-sensitively, every Title Case tag sorted above every lowercase one, putting the halves ~45 KB apart on the page. A browser jumps to the first of two duplicate ids, so `/tags/#tag:deliberative-democracy` showed one 2021 podcast while the five pages actually carrying that tag were unreachable by the link. 18 slugs were split this way (`#democracy` 5 vs 13 pages, `#podcast` 7 vs 5, `#sortition` 1 vs 6). The source frontmatter was normalised to slug form in the same pass, so the hook is a guard against re-drift rather than a live crutch — but it is what makes a future `Citizens Assembly` fold in rather than split the tag again. It shares `hooks/tag_links.py`'s import of the plugin's own `pymdownx.slugs.slugify`; keep those two in step, since folding on a different rule than the plugin anchors on would put the duplicate sections straight back. `tags_allowed:` (fails the build on any tag outside a listed vocabulary) was considered and rejected — new topics get tagged here all the time, and blocking them is the wrong trade for what is really a spelling problem. `tests/test_normalize_tags.py` covers it.
  - **Blog `categories:` do not have this problem** — checked while fixing it: four category slugs are also written two ways (`Podcast`/`podcast`, `Deliberative Democracy`/`deliberative democracy`, …), but the blog plugin merges spellings into a single generated category page (confirmed: `/blog/category/deliberative-democracy/` lists all six posts across both spellings), picking one spelling for the heading. Cosmetic, no posts lost, so categories were deliberately left alone.

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
| `/data/citations.json` | CSL-JSON — per-URL entries with `id` + `convergence.sha256` (both the full 64-char `sha256(URL)`), `type`, `URL`, `title`, and an `evidence` array (`id` + `convergence.sha256`, both `sha256(normalize_ws(quote))`, plus `type` and `quote`), plus `archive`/`archive_location`/`url-status` and `document` (`{sha256}` — hash of the extracted page text, resource-level integrity) when recorded (a read-only projection of `citation-state.json` — see "Citation archival" above). Evidence's `last-verified` is projected from that quote's own `checked` date, falling back to the URL-level one for entries predating per-quote stamping (they are different facts — a URL's date refreshes when any quote on it is fetched, so on a multi-quote URL it overstates when this specific quote was last confirmed). `status` (`MATCH`/`MISMATCH`), `verified-by`, and `context` (`{sha256, prefix, suffix}`) are projected from the same cache, added 2026-08-23 — absent on any quote `check_fragments.py` hasn't successfully checked yet, which the spec reads as "not yet verified". `verified-by` is deliberately omitted for quotes confirmed from a human's browser snapshot (`manual_verified`), since the spec reads its absence as a human claim rather than a mechanical check. `context` ships `sha256` plus the TextQuoteSelector `prefix`/`suffix` disambiguation anchors but not the paragraph `text`: the anchors let a verifier pin which occurrence of a repeated sentence a citation means, while the paragraph text is ~121 KB of others' prose a verifier recomputes from the page it fetches anyway (anchors-only ~+27% vs full ~+89% — see the 2026-08-24 changelog entry in `internal-heartbeat/machine-verifiable-citation.md`). (This row previously described a `content-sha256` field that has never existed in this file's output.) A citation-only footnote (no verbatim quote, per the "Prose footnote citations" convention below — the ones gated on carrying an `unquoted:` justification) still gets a bare item here — `id`/`convergence`/`type`/`URL`/`title` with `evidence: []` — rather than no representation at all, one item per link named; a multi-source citation-only footnote (`[First](url1) and [Second](url2)`) isn't skipped the way a multi-source *quoted* footnote is (there's no quote to mispair with either link, so `footnote_citation()`'s "don't guess which URL" reasoning doesn't apply here) — it exports as two ordinary bare items instead of one combined entry, since CSL-JSON items are inherently single-URL. Added 2026-08-24 via `util/text_fragment.py`'s `citation_only_links()`/`iter_citation_only_footnotes()`. **Gitignored, regenerated at every build** — same treatment as `events.json`/`calendar.ics` below, since it's now a strict projection of two committed sources (markdown quotes + `citation-state.json`) with zero information that isn't already versioned elsewhere. Was committed until 2026-08-22; stopped once that projection became lossless, at which point committing it was pure build-output noise. |

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

- `util/check_fragments.py` — mechanically re-verifies evidence against live pages for three sources through the same pipeline: (1) every event's `quote:` field, (2) every prose footnote's verbatim quoted excerpt (per the "Prose footnote citations" convention above), and (3) every blog post's `shared_link.description:` (per the "Convention — shared_link" section above) checked against `shared_link.url`. All evidence shares the same cache (`docs/data/citation-state.json`, committed), fetch machinery, and AMBIGUOUS detection. The cache is keyed by URL; each URL's entry holds an `evidence` **list** (not a hash-keyed map — each item carries its own `id`, matching `citations.json`'s `evidence` array; `util/text_fragment.py`'s `find_evidence()` scans it, which is free in practice since a URL rarely has more than a handful of quotes). Each item carries `id` (= `sha256(normalize_ws(quote))`), the `quote` text, a `verified` (bot) and/or `manual_verified` (human) verdict, its own `checked` date, and a `context` (`prefix`/`text`/`suffix`/`sha256`), alongside URL-level fields (`checked`, `etag`, `last_modified`, `document_sha256`, `blocked`, `archive_url`, `url_status`, `manual_checked`). Network-dependent, so **not** wired into CI (matches this repo's fetch-then-cache convention of keeping the build offline) — instead runs report-only (`continue-on-error`, doesn't block the RSS/scrape commit) in the weekly `.github/workflows/heartbeat-probes.yml` cron alongside `check_rss.py`/`scrape_news.py`; check that workflow's log for findings. `--save-to-wayback` archives each URL to the Wayback Machine's Save Page Now service (no account needed); `--events-only` scopes verification to just events, skipping footnotes and shared links; `--unchecked-only` skips anything whose quote already carries a `verified` verdict in the evidence file's `evidence` map, with zero network calls for it (see the AMBIGUOUS/STILL BLOCKED bullets below for what the *default* cache-aware path still does per URL, even for something that hasn't changed). Honors `robots.txt` via `util/robots_check.py` before fetching any citation URL — a disallowed URL is recorded with `blocked: "ROBOTS_DISALLOWED"` in the same sticky cache 403/429 uses (see `check_evidence()`'s `BLOCKED_ERRORS`), skipped entirely on later runs. Wikipedia's own extracts API is deliberately not gated — it's designed for exactly this kind of programmatic access (see "Sourcing from Wikipedia" above).
  - **AMBIGUOUS quotes** — a separate, non-blocking category printed alongside MISMATCH: when a quote is found on the page (a "good" match) but occurs *more than once*, the browser's `#:~:text=` highlight isn't guaranteed to land on the occurrence the citation actually means, and the repetition itself is a sign the phrase may be too generic to specifically confirm the claim. `util/text_fragment.py`'s `count_occurrences()` does the counting; only detected on a fresh fetch (a cache hit doesn't retain page text, so it can't re-derive this — ambiguity on an unchanged, already-cached page silently isn't re-flagged until that page's cache entry next expires or `--no-cache` is used). The fix is editorial — lengthen the quote until it's unique on its own page — not a new stored field; see the note above about why fragment disambiguation data (WICG prefix-/-suffix context) is deliberately not persisted in frontmatter. Confirmed in practice on this corpus: most flagged cases (CAPaD, mckinnon.co) turned out to be a *false* ambiguity signal from JSON-LD/page-props payloads embedded in `<script>` tags getting swept into the extracted "page text" alongside the real prose — `_fetch_page_text()` now strips `<script>`/`<style>` bodies before tag-stripping to avoid this. The one genuine case (a Wikipedia article mentioning "Decidim Association" twice in adjacent sentences) was fixed by lengthening the quote to span both mentions, which is unique as a whole even though the short phrase alone wasn't.
  - **A page is downloaded once per run, not once per quote.** `check_evidence()` runs once per evidence string, so a URL carrying several quotes used to be fetched once for each of them: 499 evidence items sit on 358 distinct URLs, and `pmg.org.za/page/what-is-pmg` was downloaded **11 times in a single run** — 141 redundant requests, 28% of the run, every one of them re-asking a server for a body the process already had in memory. `_RUN_PAGES` (reset per `main()`, and by `reset_run_pages()` in tests) holds this run's fetched bodies, so a sibling quote verifies against the body already in hand. Conditional GET cannot substitute for this: only 31% of these URLs (117 of 367) have an ETag or Last-Modified stored at all — a 12-URL sample of the rest returned **zero** validators — and even a 304 is still a request. `--no-cache` deliberately still reuses within the run: that flag means "don't trust the stored verdict", not "fetch the same page twice in one run". The one trap, pinned by `tests/test_check_fragments.py`'s `RunPageReuseTests`: the reusing sibling must carry the validators the fetch established rather than reading them back off `entry`, which `--no-cache` empties — otherwise the second quote blanks the URL's `etag`/`last_modified` and destroys the next run's chance of a 304.
  - **A citation body is capped at `MAX_FETCH_BYTES` (20MB), streamed rather than read whole.** This corpus checks page *text*, not a rendered browser page — no images, CSS, JS, or fonts are ever requested, and the median citation page is tens of KB (see the "Sourcing" bandwidth measurement above) — but a PDF/docx citation is the one case where the whole file has to be downloaded and held in memory before extraction can even start (`pdfminer`/the zip-XML walk both need the complete document, not a prefix), and nothing capped that before this. `_fetch_page_text()` fetches with `stream=True`: a declared `Content-Length` over the cap skips the download outright, and `iter_content()` enforces the same cap while reading in case the header is absent, wrong, or lying (chunked transfer has no length to check up front). Tripping the cap reports `TOO_LARGE`, treated the same as `PDF_PARSE_ERROR`/`OFFICE_PARSE_ERROR` — a plain (non-sticky) `FETCH ERROR`, retried next run rather than cached as blocked, since re-checking costs almost nothing (the cap trips within one `Content-Length` header read, or a bounded number of chunks). `tests/test_check_fragments.py`'s `MaxFetchBytesTests` covers both enforcement paths.
  - **STILL BLOCKED / the shared "blocked" cache** — a URL that answers 403/429 (bot protection, not a transient failure) is recorded as `blocked`/`blocked_since` in the same cache file and skipped entirely — no network call at all — on every later run, printed as `STILL BLOCKED` rather than `FETCH ERROR`, until `--no-cache` forces a recheck or the site starts answering normally again (a successful fetch clears the flag). `util/check_event_urls.py` and `util/fetch_shared_link_previews.py` write to and read from this exact same cache/field, so a URL any one of the three scripts has confirmed blocked stays skipped for all three, not just the one that found it. Added after a real gap: none of these scripts remembered a block before this, so the weekly cron re-hit every known-bot-protected site fresh every single run — pointless traffic to a server that had already said no, and (per `check_event_urls.py`'s HEAD-then-GET-fallback design) sometimes two requests per run, not one, since a 403 used to trigger a GET retry too. A transient error (a timeout, a 500) is deliberately NOT sticky like this — only 403/429 mean "this server doesn't want scripted requests," not "try again later."
  - **The default run re-verifies on a schedule, not every run (`--max-age`, default 90 days).** Evidence that has never been verified is always fetched; evidence already carrying a verdict is re-fetched only once *its own* verdict has aged past the window. `--max-age 0` restores the old "check everything, every run" behaviour. Two design points worth knowing before touching this:
    - **Age is per-quote, not per-URL.** Each evidence item now carries its own `checked` date. A URL's `checked` refreshes whenever *any* quote on it is fetched, but only the quotes a run collected are re-evaluated — and 204 of this corpus's 479 quotes (43%) sit on multi-quote URLs, so keying the window off the URL date would mark a quote fresh because a sibling was checked. Items written before this field existed fall back to the URL date, so the field fills in organically as the window rotates through the corpus rather than needing a migration pass.
    - **`--max-age` is a ceiling, not a target.** It names the most staleness tolerated for any one quote — the same sense HTTP `Cache-Control: max-age` carries — and nothing may exceed it. This matters because of how the spreading works (below): an early draft *added* the jitter to the window, which made `--max-age 90` silently mean "90 to 179 days, averaging 135." A flag that misses its own stated bound is worse than no flag.
    - **Due dates are deterministically jittered** (`staleness_offset()`), because the corpus is not evenly aged: 297 of 367 URLs shared a single `checked` date. An unjittered window would age all of them out on the same day, re-check them together, and re-stamp them to one identical date — the cron alternating between zero requests and the whole corpus forever. The offset is `sha256(url) % (max_age // 2)` and is **subtracted**, so re-checks land in `[max_age/2, max_age]` (mean ~0.75×) and the ceiling holds. Keyed on the URL's own hash so a due date is stable across runs and machines — the same deterministic-jitter trick `home.html` uses to spread coincident map markers. Measured on this corpus: busiest day 23 quotes, busiest week 97, median day 9, longest wait 88 days — versus 497 every run before.
    - **The 90-day default is derived, not picked.** `check_event_sourcing.py`'s `STALE_CHECK_DAYS = 365` already declares this repo's bar for "a citation needs rechecking," and `activity_selector.py` uses 730/365/180 tiers. A verifier running at the same period as the deadline it enforces is always marginally late, so this runs at roughly a quarter of that bar. It should not be raised above 365, or `check_event_sourcing.py` would start flagging citations this script is meant to be keeping fresh.
  - **`--full` is the full-scan mode** — verify every citation this run, ignoring the age window (it normalises to `--max-age 0` at parse time, so the gate only ever reads one setting). It stays *cache-aware*: conditional GETs still apply, and URLs already confirmed BLOCKED stay skipped. That's the difference from `--no-cache`, which additionally distrusts every stored verdict and retries blocked URLs — reach for `--full` when you want complete coverage this run, and `--no-cache` when you suspect the stored state itself is wrong. Contradictory combinations (`--full` with `--max-age`, `--full` with `--unchecked-only`) are rejected at parse time rather than silently resolved.
  - **`--spot-check N` (default 10) keeps a run from ever being a no-op.** Once everything is fresh the window legitimately selects nothing, and a scheduled run that checks nothing detects nothing — a page rewritten the day after its last check would go unnoticed for the rest of the window. When fewer than N items are due, the run tops up to N by sampling the not-due pile. The sample is seeded on today's date: stable within a day (running twice doesn't hit twice as many servers) and rotating across days. `--spot-check 0` disables it.
  - **`--unchecked-only`** — the strictest end of the same dial as `--max-age`: never re-verify at all, only fetch citations with no verdict yet. (Before the `--max-age` window existed, the default issued a conditional GET per URL on every run forever, and this flag was the only way out of that.) It skips any quote already carrying a `verified` verdict in the evidence file's `evidence` map — no request at all, not even a conditional one — and only fetches evidence that's genuinely new: a citation added since the last run, or a new `quote:`/footnote/`shared_link.description:` on an already-known URL. A prior MISMATCH still counts as "checked" and is skipped too — this flag is for catching up quickly on new evidence, not for re-litigating known failures (drop the flag, or use `--no-cache`, for that — the two can't be combined, since they pull in opposite directions on how much to trust the evidence file).
  - **A `--no-cache` run never erases what it didn't check.** `check_evidence()` deliberately empties its local view of a URL's cache entry under `--no-cache` (that's the flag's whole point — don't trust the stored verdict for the quote being checked now), and the two "blocked" paths have merged writes back from what's actually on disk since the 2026-08-20 incident. The *success* path did not, until 2026-08-25: it rebuilt the URL's whole `evidence` list from the emptied view, so every other quote recorded against that URL — one a different org's event cites, say — silently vanished from `citation-state.json`, along with URL-level `archive_url`/`url_status`. One `--no-cache --slug ...` run dropped 28 verified event quotes this way. All three paths now merge from disk; `tests/test_check_fragments.py`'s `CheckEvidenceNoCachePreservesOtherEvidenceTests` pins it. The general shape is worth remembering when touching this file: **one run only re-checks the quotes it collected, so any write that rebuilds a URL's `evidence` list rather than appending to it is a data-loss bug.**
  - **`--slug` scopes the whole run, not just events** — it narrows the event checks to those orgs, narrows footnote checks to those orgs' own pages, and skips blog `shared_link.description:` evidence entirely. It did not always: until 2026-08-25 `--slug` filtered only the events loop, so `--slug one-org --no-cache` still collected every footnote citation across `docs/` and re-fetched all of them — roughly 180 requests, one to nearly every cited webserver in the landscape, to verify three quotes on one page (a ~35-minute run that the same check now finishes in ~70 seconds). To deliberately re-check a blog post's or concept page's footnotes, drop `--slug` rather than naming an org.
  ```
  python util/check_fragments.py             # exits 1 if any evidence no longer matches
  python util/check_fragments.py --slug g0v  # single org — its events and its own page's footnotes
  python util/check_fragments.py --slug g0v --slug namfrel  # multiple orgs — --slug is repeatable
  python util/check_fragments.py --no-cache  # ignore the cache, re-fetch and re-verify everything, including URLs already confirmed BLOCKED
  python util/check_fragments.py --max-age 30 # tighter window: re-verify anything older than 30 days
  python util/check_fragments.py --full      # full scan: every citation this run (still cache-aware)
  python util/check_fragments.py --spot-check 0  # disable the not-a-no-op top-up
  python util/check_fragments.py --unchecked-only  # skip anything already verified — zero requests for it, not even a conditional GET
  python util/check_fragments.py --offline   # check evidence against .pagecache/ copies only (no network) — the cite-adjustment workflow
  python util/check_fragments.py --save-to-wayback  # archive each URL to Wayback Machine
  python util/check_fragments.py --set-url-status "<url>" dead  # record a citation as known-dead (or unfit/live) — see "Citation archival" above
  python util/check_fragments.py --events-only     # only check event evidence (original behaviour)
  python util/check_fragments.py --autofix-spaces  # rewrite spacing-only MISMATCHes in place
  python util/check_fragments.py --report /tmp/fragments-report.json  # also write a JSON findings summary (for ad hoc/manual review — not consumed by anything in CI)
  ```
  - **`.pagecache/` — local reading copies of cited pages** — every full page body this script fetches (live HTML, extracted PDF text, extracted .docx/.odt text, Wikipedia API extracts) is written through to `.pagecache/` (gitignored, via `util/pagecache.py`; see that file's docstring), so a later human/AI session can read what a cited page said without re-pinging the origin site — the mirror image of `manual-dump/`, which handles pages scripts *can't* reach. Successful manual-dump imports also seed `.pagecache/` with the snapshot's extracted text (a human-obtained copy is often the best text a bot-blocked/SPA URL ever yields to us — confirmed on governancehubafrica.org/about: 21-char shell from scripts vs ~7,900 chars rendered), so `--offline` quote work covers manually-resolved citations too. Deliberately one-directional: stored copies never feed back into verification (`check_evidence()` keeps its own conditional-GET/sticky-block freshness machinery, so a stale copy can't mask real page drift with an old verdict). `--no-page-cache` opts out of writing (the weekly cron passes it — the artifact would be discarded with the runner anyway); `just page-cache list|show|path` reads what's stored. **`--offline`** is the reverse direction: verifies selected evidence against stored copies alone — no network, no evidence-cache writes, no manual-dump queueing, and it deliberately bypasses the sticky-blocked cache (a URL whose live fetch is blocked can still have a stored copy) — for adjusting a quote's wording offline ("does my reworded `quote:` still match what the page said at last fetch?"). URLs with no stored copy report `NOT CACHED`, don't count as errors, and don't fail the run — do one fetching pass (`--no-cache`) first to populate. Office documents (`.docx`, `.odt`) are detected by zip magic bytes, not URL extension; an unreadable zip reports `OFFICE_PARSE_ERROR` rather than false-mismatching quotes against binary garbage.
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

- `util/check_event_urls.py` — liveness check for every event's `url:` citation (HEAD request, GET fallback for hosts that don't support HEAD). Catches the failure mode neither of the two scripts above does: a citation URL 404ing, redirecting, or its host disappearing. Distinguishes `DEAD` (404/5xx — a real problem, needs a replacement citation) from `BLOCKED` (403/429 — near-certainly bot/scraper protection, e.g. Cloudflare; several sites in this landscape are confirmed reachable-in-a-browser-but-403-to-scripts, so don't "fix" a BLOCKED citation without manually checking it in a real browser first) from `REDIRECT` (informational — citation still resolves, consider updating the URL to the canonical target). Network-dependent, not in CI; also runs report-only in the same weekly cron as `check_fragments.py` above. A HEAD that comes back 403/429 does **not** trigger the GET fallback (only 405/501 — genuine "HEAD not supported" signals — do) — a GET immediately after would almost certainly hit the same block, doubling the request for no new information. Shares `check_fragments.py`'s "blocked" cache (see that entry's STILL BLOCKED bullet above) — a URL already confirmed BLOCKED is skipped with zero requests on later runs until `--no-cache`. Unlike `check_fragments.py`, a BLOCKED result here does **not** queue a manual-dump request (see `util/manual_dump.py`) or consult `manual_verified` — this script checks bare URL liveness, not a specific quote, so there's no evidence hash for a manually-saved snapshot to verify against. Also checks `robots.txt` (same shared implementation, same cache — a `ROBOTS_DISALLOWED` entry written by either script is honored by both) before ever issuing the HEAD/GET; reported as `ROBOTS.TXT DISALLOWED`/`STILL ROBOTS-BLOCKED`, separately from `DEAD`/`BLOCKED`, and never causes a non-zero exit — it's DOD respecting the site's own opt-out, not a citation problem. On a fresh `DEAD` verdict, prints a suggested `check_fragments.py --set-url-status <url> dead` command rather than writing it itself — see "Citation archival" above for why this stays a human call.
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

- `util/check_footnote_quotes.py` — gates every prose footnote citation (org pages, blog posts, concept pages) on carrying either a verbatim quoted excerpt or an explicit `unquoted:` justification (see the "Prose footnote citations" convention above). Local/offline, no network calls. Wired into CI (`.github/workflows/build.yml`) and the pre-commit hook (`.githooks/pre-commit`, whenever any staged file matches `docs/**/*.md`) as a hard gate — exits 1 if any citation-only footnote has neither a quote nor an `unquoted:` annotation. A separate soft warning (printed, doesn't fail the build) flags an annotation whose `reason` is under 15 characters — present but not really an explanation.
  ```
  python util/check_footnote_quotes.py             # gate: exit 1 if any MISSING JUSTIFICATION
  python util/check_footnote_quotes.py --missing    # also list every citation-only footnote (justified or not)
  python util/check_footnote_quotes.py --path docs/organisations/g0v.md  # single file
  ```

- `util/manual_check_worklist.py` — generates a plain checklist for a human to verify citations `check_fragments.py` can't resolve by itself. Two modes: the default (offline, no network) reads `citation-state.json`'s `blocked` entries — URLs that have returned 403/429 to a script and are deliberately never auto-retried (see `check_fragments.py`'s docstring on why that's sticky) — and lists them with the exact quote to Ctrl+F for. `--live` instead fetches every not-yet-blocked citation fresh and additionally surfaces current AMBIGUOUS (quote occurs more than once on the page) and MISMATCH findings, which aren't persisted to the cache the way BLOCKED is — the only way to get a current list of those without re-running `check_fragments.py` and reading its console output. Never edits a source file; the fix (or the decision that no fix is needed) still happens by hand after checking the page in a real browser, where the network path and browser fingerprint look nothing like a script's — confirmed useful in practice on `radicalxchange.md`'s `glenweyl.com` citation, which resets the connection for both plain HTTP and headless-Chromium requests alike.
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
  3. **Firefox: File → Save Page As → "Web Page, HTML only"** (a "complete" save also works — its `_files` folder just tags along into `imported/`). Save into `manual-dump/snapshots/`; the filename doesn't matter. **For JS-rendered/SPA pages that save as a nav-only shell, use print-to-PDF instead** (Ctrl+P → Save to PDF) — a PDF snapshot is imported via pdfminer and its rendered text is exactly what you saw. Direct file downloads (a citation URL that IS a .pdf/.docx) just get saved as-is.
  4. Run `python util/import_manual_dump.py --dry-run` first to preview what will be matched/imported, then `python util/import_manual_dump.py` for real.
  5. `git diff docs/data/citation-state.json` and skim the new `evidence` entries before committing — same spot-check judgment as reviewing any other automated write to this file.
  6. Re-run `check_fragments.py` (or just check its next report) to confirm the citation no longer shows as STILL BLOCKED.

  Mechanism, for reference:
  - Whenever `check_fragments.py` hits a BLOCKED citation with no manual coverage for that exact evidence yet, it appends the URL to `manual-dump/requests.txt` (deduplicated).
  - Source-URL recovery order: (1) `manual-dump/snapshots/url-map.txt`, a human-maintained `<filename> <url>` sidecar (authoritative — filenames may contain spaces, URL is the last token); (2) the `<!-- saved from url=(NNNN)https://... -->` stamp browsers *used* to write as the file's first line — current Firefox versions often don't anymore (confirmed August 2026: 26 saves, zero stamps); (3) the page's own `<link rel="canonical">` / `og:url` meta tag, best-effort (sites occasionally declare a variant URL that won't match the citation — surfaces as NO MATCH). A snapshot with no recoverable URL is skipped with a ready-to-paste url-map.txt line printed.
  - `import_manual_dump.py` extracts text with the same `text_fragment.html_to_text()` a live fetch uses (so a quote verifies identically against either path) — or, for downloaded binary documents (PDFs via pdfminer; `.docx`/`.odt` via stdlib zip-XML extraction — both detected by magic bytes, not extension, since citation URLs whose last path segment is literally a filename are direct file downloads), the same `_fetch_page_text` extraction paths; those carry no stamp and no meta tags, so they require a url-map.txt line. A **print-to-PDF** of a JS-rendered page works here too — it sniffs as the PDF case and its rendered text is what a human actually saw, which plain "Save Page As" often fails to capture on SPA sites (confirmed on science.org: a saved HTML came through as a nav-only shell and false-MISMATCHed a description that a Wayback capture of the same page later confirmed verbatim). Either way it checks the extracted text against every citation currently pointing at that URL, records each result in the shared evidence cache as `evidence[hash].manual_verified: <bool>` / `manual_checked: <date>` plus one entry in `manual-dump/import.json` (`{filename: url, source, checked, good, mismatch}` — the greppable index of what's in `imported/` backing which URL), removes the URL from `requests.txt`, and moves the file into `manual-dump/imported/` (a sibling of `snapshots/`, so the inbox only ever holds unprocessed saves) so a re-run doesn't reprocess it. `--rebuild-map` regenerates import.json from imported/ contents alone (URL re-recovered per file's own markers/url-map, verdict counts read back out of the evidence cache) — for backfilling entries created before the manifest existed or recovering a lost one.
  - `manual_verified` is a separate flag from the automated `verified` verdict, never merged into it — stale automated data captured before a site started blocking scripts must never be silently presented as reconfirmed just because an unrelated snapshot was imported later. `check_evidence()` consults `manual_verified` for the specific evidence hash being checked *before* falling back to reporting STILL BLOCKED, and also when a fetch succeeds but returns less text than the evidence string is long (a JS-rendered SPA shell or bot-challenge holding page — confirmed on governancehubafrica.org/about, 21 chars of title vs ~8,000 rendered; the quote can't possibly be there, so that's a fetch failure reported as `PAGE_TOO_SHORT`, not a MISMATCH), so a manually-resolved citation stops being reported as blocked without the origin site ever needing to cooperate again. Unlike a 403 this is deliberately not sticky-cached — a shell-to-server-rendered switch is a realistic recovery, so each run re-fetches and self-heals if the site changes.
  - A snapshot whose recovered URL doesn't match any current citation is left in place (not moved) and reported — more likely a mistake (wrong page saved, or the citation was since removed) than something to silently discard.

- `util/merge_citation_state.py` — merges two divergent copies of `docs/data/citation-state.json` without dropping either side's verification work. Exists because of a real, months-long failure: the weekly probe cron spends hours re-verifying citations, commits the result, then rebases onto whatever `main` has become — and `citation-state.json` is one machine-generated JSON blob, so any concurrent edit collides and git cannot resolve it line-by-line. **9 of the first 10 scheduled runs died exactly there, each discarding its own commit**, which is why no citation in this repo had ever carried an `archive_url` despite the cron passing `--save-to-wayback` since day one (the `checked` dates that did exist came from local runs, which don't pass that flag). `.github/workflows/heartbeat-probes.yml` now calls this on a conflict in that one file; a conflict in any *other* file still fails the job loudly rather than being auto-resolved.
  - Merge rule is the same one `check_fragments.py` follows internally — **merge, never rebuild**. Both sides hold real work, so `-X ours`, `-X theirs` and `--force` are all wrong answers. URLs and `evidence` items (keyed by `id`) are unioned; an item on both sides resolves to whichever was `checked` more recently, and a dated item beats an undated one (undated entries predate per-quote stamping, so they're strictly older).
  - URL-level fetch state (`checked`, `etag`, `last_modified`, `document_sha256`, `blocked`, `blocked_since`) moves as a **unit** from whichever side is newer — an etag belongs to the body whose hash sits beside it, and mixing them across sides yields a validator that doesn't match its own document. A cleared `blocked` on the newer side wins, since that means the site started answering again.
  - Additive/human-owned fields (`archive_url`, `archive_checked`, `url_status`, `manual_checked`) survive from *either* side rather than riding on the fetch-state winner — otherwise an archive snapshot recorded by one run vanishes because the other fetched later, which is the exact regression this file was written to prevent. `url_status` is the one field a human sets by hand, so a genuine disagreement is reported on stderr rather than silently resolved.
  - The script refuses to write if the merge would drop any evidence, rather than trusting its own logic — a silent drop here is the bug class it exists to prevent. Verified against the real 367-URL corpus (two lossy divergent copies merged back to a full union, 0 lost); `tests/test_merge_citation_state.py` also reproduces the actual rebase conflict in a throwaway git repo end to end.
  ```
  python util/merge_citation_state.py OURS.json THEIRS.json --out MERGED.json
  python util/merge_citation_state.py OURS.json THEIRS.json --check   # report only, write nothing
  ```

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

