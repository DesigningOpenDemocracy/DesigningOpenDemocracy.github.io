# Heartbeat — Scheduled Maintenance Agent Brief

Read **CLAUDE.md** first for site conventions and curation standards.
Read **util/SOUL.md** for script usage and the `last_checked` convention.
Everything produced by a heartbeat run lands in a PR — never push direct to main.

---

## Mission

Two things in one run:

1. **Maintenance** — keep org data fresh, catch structural issues, close tag gaps.
2. **Commentary** — a brief, sourced DOD-voice observation on the state of
   democracy in the world, if anything notable happened this period.

Both land in a single blog post and PR. The commentary section is optional —
say nothing rather than force it.

---

## Steps

### 1. Orient

```bash
python util/stats.py
```

Note the counts, freshness distribution, and concept coverage. These numbers
anchor the maintenance section of the post.

### 2. Work the staleness queue

```bash
python util/check_orgs.py --active --days 180
```

Pick the oldest 10–15 pages. For each:
- Visit the org's website; confirm it loads and the org is still active
- Check the summary and status are still accurate
- Fix anything stale (summary, concepts, location, status)
- Stamp: `python util/stamp.py <slug>`

If a page needs status changed (active → inactive), update `website:` to a
Wayback URL per the CLAUDE.md convention.

### 3. Surface tag gaps

```bash
python util/suggest_tags.py <concept-slug>
```

Run for concepts with low org coverage. Add tags where the match is genuine.

### 4. Structural check

```bash
python util/pre_commit_check.py
```

Fix any hard failures. The 4 known lint exceptions (FLACSO-Cuba, Kongra Star,
Memorial, NAMFREL) are expected — do not touch them. See util/SOUL.md.

### 5. Read the room (commentary research)

Before writing: read `docs/philosophy/index.md` and `docs/philosophy/soul.md`
to ground yourself in DOD's values and framing.

Then search for recent news (past 30–180 days depending on run cadence) on:
- New citizens' assemblies or deliberative processes announced or concluded
- Significant electoral system or constitutional reforms passed or proposed
- Notable democratic backsliding (election suspended, assembly dissolved, press
  freedom laws, etc.)
- New participatory budgeting programs adopted at city or national scale
- Major academic or policy publications directly relevant to the landscape

**Threshold for inclusion:** something is worth commenting on only if it is
genuinely notable from a governance-design perspective AND you can link a
primary or reputable secondary source. If nothing clears that bar, skip the
commentary section entirely — a short maintenance post is better than
stretched commentary.

DOD is nonpartisan. Do not comment on which party won an election unless it
has direct structural governance implications. Do not take sides on contested
political questions. Reflect the philosophy page framing: governance design,
legitimacy, participation, accountability — not ideology.

### 6. Write the sync post

Create `docs/blog/posts/YYYY-MM-sync.md`. See **AI-authored sync posts** in
CLAUDE.md for required frontmatter and disclaimer.

**Structure:**

```
[Required disclaimer block]

## Landscape update

[2–3 sentences: current counts from stats.py, what was verified this run,
any status changes or notable findings]

## In the world  ← omit entirely if nothing notable

[1–3 items, each with:
 - A one-sentence statement of what happened
 - A linked source (title, outlet, date)
 - 1–2 sentences on why it's relevant to governance design / how it relates
   to concepts or orgs in the landscape
 - No opinion on whether it's good or bad unless DOD's philosophy gives
   unambiguous ground to stand on]

## What's next

[One sentence on which section of the landscape is oldest in the queue]
```

Keep each section short. This is a record and a signal, not an essay.

### 7. Open the PR

Commit all changes (org updates + blog post). Title: `Heartbeat sync — YYYY-MM`.
Include the `stats.py` before/after snapshot in the PR body.

---

## Escalation — stop and flag in the PR if

- An org's website has a permanent error and you can't determine if it's
  still operating from other sources
- An org appears to have merged with or been renamed to another in the landscape
- A status change requires verification beyond what the org's own site shows
- More than 20% of pages checked need status changes in a single run
- A news item seems important but you're unsure whether DOD's philosophy
  gives ground to comment — flag it for human editorial judgment rather than
  guessing

---

## Boundaries

**Do autonomously:** verify websites, update summaries and last_checked,
add concept tags, fix structural lint issues, write the sync post, open a PR.

**Do not do:** merge the PR, change the curation standard, add or remove an
org on your own judgment alone, comment on news items without a linked source,
write commentary that takes a partisan political position.

**When in doubt on commentary:** say nothing. A quiet period is an honest
signal, not a failure.
