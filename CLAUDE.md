# Claude Code Notes

## Tech Stack

This is a MkDocs + Material for MkDocs static site deployed to GitHub Pages.

- Build: `mkdocs build` (or `make build`)
- Local dev: `make serve`
- Deploy: CI pushes to `gh-pages` branch via `mkdocs gh-deploy --force`
- Python deps: `requirements.txt` (site build), `util/requirements.txt` (utility scripts only)

## Known Watch Items

### MkDocs ecosystem fragmentation (as of May 2026)

The MkDocs ecosystem is in flux. The original maintainer went inactive and planned a v2 that would break all existing plugins and themes. This caused a community split:

- **ProperDocs** (`pip install properdocs`) — continuation of MkDocs 1.x, drop-in replacement
- **MaterialX** — continuation of mkdocs-material as a separate package

Current status: we are still on `mkdocs + mkdocs-material` and it works fine. `DISABLE_MKDOCS_2_WARNING=true` is set in CI to suppress advertising injected by `mkdocs-rss-plugin` (which added `properdocs` as a hard dependency).

**When to act:** If `mkdocs-material` stops releasing updates or moves to `materialx`, migrate by swapping package names in `requirements.txt` and replacing `mkdocs` commands with `properdocs`. It is designed to be a drop-in replacement.

Reference: https://fpgmaas.com/blog/collapse-of-mkdocs/

## Philosophy page

**Before editing `docs/philosophy/index.md`, read `docs/philosophy/soul.md`.**

That file records the human intent behind the page, the invariants that shaped the current text, and the AI dialogue (Claude, DeepSeek, ChatGPT, Gemini, Grok, Mistral) that contributed to it. Reading it first prevents accidentally collapsing earlier contributions.

The invariants recorded there are not immutable. Any document in this repo — including soul.md, this file, and HEARTBEAT.md — can be proposed for change by any contributor, human or AI. The requirement is transparency: if you change something foundational, say what you changed, why, and what prompted it. The PR review is the gate, not a list of forbidden edits.

## Conventions

### Project pages (`docs/projects/`)

- Use `template: project.html` in frontmatter — renders a metadata box (status, contributors, website)
- `status` values: `active` | `mothballed` | `cancelled`
- `status: active` pages appear in the front page projects section automatically
- All projects (any status) appear grouped on the `/projects/` index page

### Organisation pages (`docs/organisations/`)

- The section is framed as a **Democracy Landscape reference** — organisations we monitor, not formal affiliates
- Use `type`, `status`, `country`, `website`, `summary` in frontmatter
- `status` values: `active` | `inactive` | `deregistered`
- For defunct orgs, point `website` to the Wayback Machine calendar URL: `https://web.archive.org/web/*/https://originalurl.com/`
- **Curation standard**: An org belongs here if it works on systems of governance for/with the people, in good faith — regardless of ideological label. See `docs/philosophy/index.md` for the full framework, including the three disqualifiers (hypocrisy, bad faith, structural inflexibility). DOD is not a human rights observatory; orgs focused purely on documenting abuses without engaging governance design do not fit.
- `concepts: [slug, slug]` — list of concept slugs this org relates to. Used to populate concept chips in the metadata box and org index table. Slugs match filenames in `docs/concepts/` without the `.md` extension.
- `location: {latitude, longitude, name}` — required for the org to appear on the interactive map. Only `status: active` orgs are shown on the map.
- The `organisation.html` template is **auto-applied** to all org pages via `hooks/org_template.py` — no need to set `template:` in frontmatter unless overriding.
- `rss_feed: <url>` — optional; the org's RSS or Atom feed URL. Populated by `util/check_rss.py`.
- `news_page: <url>` — optional; URL of the org's news or blog index page. Opt-in for `util/scrape_news.py`.
- `ics_feed: <url>` — optional; URL of an iCal/ICS calendar feed. Opt-in for `util/check_rss.py --update-activity` (writes `activity.ical`).
- `related_orgs: [slug, slug]` — optional; list of org slugs with a direct relationship to this org. Rendered as orange edges in the knowledge graph. Declare on one side only — direction is normalised so duplicates are automatically suppressed.
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
  - `checked:` — optional; the date the source was last probed, regardless of whether new content was found. Written automatically by `check_rss.py`, `scrape_news.py`, and `review_orgs.py`. Entries with no `date` but a `checked` date mean the source was probed but found nothing.
  - Priority order (highest first): `manual` > `dod` > `social` > `rss` > `ical` > `scrape` > `sitemap`
  - Staleness thresholds: `manual`/`dod` 730 d · `social`/`rss`/`ical`/`scrape` 365 d · `sitemap` 180 d
  - A source is skipped if older than its threshold; the next-priority fresh source wins
  - If all sources are stale, the most recent entry is shown regardless
  - `util/check_rss.py --update-activity` populates `rss`, `sitemap`, and `ical` entries automatically; re-runs skip orgs checked within 7 days (use `--force` to override)
  - `util/scrape_news.py` populates `scrape` entries for orgs with `news_page:` set; same skip behaviour
- **Key people** is an optional section. Add it only when named individuals are central to understanding the org's story (founders, government champions, notable critics) and the information is sourced. Link names to Wikipedia where a confirmed article exists. Do not add it just to fill the template — most orgs are better served by institutional description.

### Blog posts (`docs/blog/posts/`)

- Blog posts are **human-authored**. A human must take primary responsibility for the content, accuracy, and framing of every post.
- Claude may assist with drafting, editing, or structuring a post, but should not create and publish a blog post autonomously — especially for factual or politically sensitive content (legislation, election results, organisational positions).
- When a topic warrants a blog post but no human has written one, note the gap rather than filling it unilaterally. Do not let "the information exists" be sufficient reason to publish.
- Concept and organisation pages are appropriate for AI-assisted content (with sourcing discipline); blog posts are not.

**Exception — AI-assisted research posts:**

A post may be AI-drafted from research (sources, web fetches, pasted documents) if:

1. Frontmatter must include:
   ```yaml
   authors:
     - Claude
   ai_assisted: true
   ```
2. The post body must open with this disclaimer block (immediately after `<!-- more -->`):
   ```
   > *This post was drafted by Claude Code with AI-assisted research. A human editor
   > partially reviewed it for general accuracy. Verify specific claims against the
   > linked sources.*
   ```
3. Every factual claim must carry a linked source. No unsourced assertions.
4. A human must review and merge the PR.

`ai_assisted: true` is distinct from `ai_generated: true` (sync posts). Use `ai_assisted` when a human has directed the research and partially reviewed the output; use `ai_generated` only for the fully autonomous maintenance sync posts described below.

**Exception — AI-authored sync posts** (see `HEARTBEAT.md`):

Periodic maintenance sync posts may be AI-authored if they meet all of the following:

1. Frontmatter must include:
   ```yaml
   authors:
     - Claude
   ai_generated: true
   ```
2. The post body must open with this disclaimer block:
   ```
   > *This post was generated by Claude Code during a scheduled maintenance pass.
   > All statistics are derived from this wiki's own data. A human reviewed the
   > PR before merging.*
   ```
3. Content is restricted to two sections (see `HEARTBEAT.md` for full structure):
   - **Maintenance log:** landscape statistics, orgs verified, structural findings.
     All claims sourced from the wiki's own data.
   - **World commentary (optional):** 1–3 sourced observations on recent
     democracy-related events (new assemblies, reforms, backsliding, policy
     publications). Every factual claim must carry a linked source. DOD is
     nonpartisan — no partisan political commentary, no unsourced claims. If
     nothing notable happened, this section is omitted entirely.
4. A human must review and merge the PR — the post is never pushed direct to main.

### Concept pages (`docs/concepts/`)

- These are **discovery aids** — brief orientations pointing to better sources, not authoritative explanations.
- Content should come from DOD member discussions/events (linked back to blog posts) or point to external sources.
- Do not write extended explanations from general knowledge. If depth is needed, link outward.
- DOD is nonpartisan and agnostic to any specific democratic model; inclusion of a concept is not an endorsement.



- `util/createPost.py` — interactive CLI to create a new blog post with frontmatter
- `util/frontmatter_updator.py` — uses OpenAI API to auto-fill frontmatter; requires `util/requirements.txt`

## Architecture (as of May 2026)

### Template system

| Template | Location | Applied to |
|---|---|---|
| `organisation.html` | `docs/overrides/` | All org pages — auto-applied by hook, no frontmatter needed |
| `organisations.html` | `docs/overrides/` | `docs/organisations/organisations.md` — sortable table index |
| `community.html` | `docs/overrides/` | `docs/community/community.md` — auto-generates active projects grid |
| `project.html` | `docs/overrides/` | Project pages — must set `template: project.html` in frontmatter |
| `home.html` | `docs/overrides/` | Home page — hero pitch, CTA buttons, active projects, map |
| `knowledge-graph.html` | `docs/overrides/` | `docs/knowledge-graph.md` — interactive Cytoscape.js graph; set via `template:` frontmatter |

### Hooks

- `hooks/org_template.py` — fires on `on_page_markdown`; sets `template: organisation.html` on any page under `organisations/` that doesn't already have a template. Registered in `mkdocs.yml` under `hooks:`.
- `hooks/activity_selector.py` — fires on `on_page_context`; reads `page.meta.activity` and resolves it to a single `page.meta.computed_activity` dict using priority order and per-source staleness thresholds. Used by `organisation.html` to render the "Last activity" row. See priority/staleness table in the Organisation pages section.
- `hooks/data_export.py` — fires on `on_pre_build`; generates static data files under `docs/data/` from all org frontmatter. See Data exports section below.
- `hooks/graph_builder.py` — fires on `on_page_context` and `on_post_build`; collects concept/org/project nodes and edges (from `concepts:` frontmatter and "See also" sections) into `graph.json`. Org/project nodes include `activity_date` (best date across all `activity:` sources) used by the graph UI to fade dormant nodes.

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
| `/data/organisations.csv` | Flat table — all orgs, one row each. Includes `activity_date`, `activity_method`, `rss_feed`. |
| `/data/organisations.json` | Structured JSON — concepts as arrays, full `activity` dict, computed `activity_date`/`activity_method`. |
| `/data/organisations.geojson` | FeatureCollection — orgs with lat/lon only. |
| `/data/organisations.kml` | KML — orgs with lat/lon, colour-coded by status. |
| `/data/org-concepts.csv` | Edge list (`org_slug`, `concept_slug`) for network/graph analysis. |

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

- `util/scrape_news.py` — scrapes news/blog index pages for orgs that lack a usable RSS feed. Opt-in: only runs for orgs with `news_page:` set in frontmatter. Extracts dates from machine-readable signals (JSON-LD, OpenGraph, `<time datetime>`) and as a fallback from date patterns in article URLs (e.g. `/2026/01/15/`). Respects robots.txt. Writes `activity.scrape`.
  ```
  python util/scrape_news.py                  # all active orgs with news_page:
  python util/scrape_news.py --all            # include inactive orgs
  python util/scrape_news.py --slug loomio    # single org
  python util/scrape_news.py --dry-run        # print results without writing
  python util/scrape_news.py --debug          # show what date signals were found on each page
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

