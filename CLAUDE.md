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
- **Curation standard**: An org belongs here if it works on systems of governance for/with the people, in good faith — regardless of ideological label. See `docs/philosophy.md` for the full framework, including the three disqualifiers (hypocrisy, bad faith, structural inflexibility). DOD is not a human rights observatory; orgs focused purely on documenting abuses without engaging governance design do not fit.

### Blog posts (`docs/blog/posts/`)

- Blog posts are **human-authored**. A human must take primary responsibility for the content, accuracy, and framing of every post.
- Claude may assist with drafting, editing, or structuring a post, but should not create and publish a blog post autonomously — especially for factual or politically sensitive content (legislation, election results, organisational positions).
- When a topic warrants a blog post but no human has written one, note the gap rather than filling it unilaterally. Do not let "the information exists" be sufficient reason to publish.
- Concept and organisation pages are appropriate for AI-assisted content (with sourcing discipline); blog posts are not.

### Concept pages (`docs/concepts/`)

- These are **discovery aids** — brief orientations pointing to better sources, not authoritative explanations.
- Content should come from DOD member discussions/events (linked back to blog posts) or point to external sources.
- Do not write extended explanations from general knowledge. If depth is needed, link outward.
- DOD is nonpartisan and agnostic to any specific democratic model; inclusion of a concept is not an endorsement.



- `createPost.py` — interactive CLI to create a new blog post with frontmatter
- `frontmatter_updator.py` — uses OpenAI API to auto-fill frontmatter; requires `util/requirements.txt`
