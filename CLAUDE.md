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



- `createPost.py` — interactive CLI to create a new blog post with frontmatter
- `frontmatter_updator.py` — uses OpenAI API to auto-fill frontmatter; requires `util/requirements.txt`

## Architecture (as of May 2026)

### Template system

| Template | Location | Applied to |
|---|---|---|
| `organisation.html` | `docs/overrides/` | All org pages — auto-applied by hook, no frontmatter needed |
| `organisations.html` | `docs/overrides/` | `docs/organisations/organisations.md` — sortable table index |
| `community.html` | `docs/overrides/` | `docs/community/community.md` — auto-generates active projects grid |
| `project.html` | `docs/overrides/` | Project pages — must set `template: project.html` in frontmatter |
| `home.html` | `docs/overrides/` | Home page — hero pitch, CTA buttons, active projects, map |

### Hooks

- `hooks/org_template.py` — fires on `on_page_markdown`; sets `template: organisation.html` on any page under `organisations/` that doesn't already have a template. Registered in `mkdocs.yml` under `hooks:`.

### Frontmatter — active gates

- `status: active` on a **project** page → appears in the home page projects grid and community page
- `status: active` on an **org** page + `location:` coordinates → appears on the interactive map

### CSS conventions (`docs/assets/css/customizations.css`)

- `.project-status-badge.status-<value>` — coloured status pill (active/inactive/deregistered/mothballed/cancelled)
- `.concept-tag` — indigo chip linking a concept slug to its concept page; used in org metadata box and org index table
- `.org-sortable-table` / `.org-search-input` — org index table and filter input
- `.hero-cta-btn` / `.hero-cta-primary` — home page call-to-action buttons

### URL gotcha

`file.page.url` in MkDocs Jinja2 templates is **root-relative without a leading `/`**. Always prefix with `/` in `href` attributes: `href="/{{ file.page.url }}"`. Omitting the slash causes triple-nested 404s when navigating from deep pages.

### Pending work (separate PRs)

- **Knowledge graph visualisation** — build hook extracts `concepts:` frontmatter + See Also links → `graph.json`; rendered with Cytoscape.js as a dedicated page. The structured `concepts:` frontmatter on org pages is the intended data source.
