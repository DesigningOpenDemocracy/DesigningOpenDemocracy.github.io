# Internal heartbeat

This is a private diary, not a publication. It lives outside `docs/`, so
mkdocs never builds it — nothing here reaches the site, the sitemap, or
search, no matter what's written. It's tracked in git like everything else
in the repo, so it's visible to anyone reading the source, but it is not
presented as content.

## What goes here vs. `docs/heartbeat/`

`docs/heartbeat/posts/` (see `HEARTBEAT.md`) is DOD's *public* maintenance
log — a real blog instance with its own feed, written for readers, gated by
the sourcing/disclaimer rules in `CLAUDE.md`.

This folder is the opposite: research notes, draft assessments, and working
judgment calls that aren't (yet, or ever) ready to be a public statement.
Typical uses:

- Politically sensitive curation research — e.g. assessing whether a
  political party belongs in the Democracy Landscape — where the findings
  and the reasoning are worth keeping, but publishing them as a dated
  editorial verdict on named parties isn't something to do unprompted.
- Draft framework friction notes before they're distilled into the terser,
  public-facing form that belongs in a heartbeat post's "Framework notes"
  section.
- Any research trail a future session (human or AI) would benefit from
  finding, without it needing to clear the bar of public-facing prose.

## Conventions

- One file per entry: `YYYY-MM-DD-short-slug.md`.
- No frontmatter needed — these aren't mkdocs pages.
- Write for a future reader who wasn't in the conversation: state what was
  asked, what was found, and what's still an open call. Cite sources the
  same way the public site does — a claim without a link is a claim nobody
  can check later. Write every entry as if it might eventually be promoted
  (see below) — sourced and dated, not shorthand only you'd understand.
- If a note here eventually becomes a real editorial decision (an org page
  added, a framework change, a blog post), say so at the top of the file
  with a link to what shipped, rather than leaving the diary entry looking
  like an unresolved question forever.

## Promoting an entry to public

DOD's default is transparency (see the Soul Document's own framing), so an
entry here staying private is a decision, not a default that should be
assumed to last forever. "Private for now" and "private forever" are
different calls — this folder only handles the first. Nothing here
publishes itself, on purpose: promotion is a deliberate act, not a flag
(like a blog post's `draft: true`) that could silently lapse.

To promote an entry: copy it into `docs/heartbeat/posts/` (AI-authored
maintenance voice) or `docs/blog/posts/` (needs a human author and the
`ai_assisted: true` disclaimer block — see CLAUDE.md) with real frontmatter,
edit it to the standard that section holds itself to, and note in this
file what shipped and where.
