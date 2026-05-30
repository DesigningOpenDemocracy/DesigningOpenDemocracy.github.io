# Heartbeat — Scheduled Maintenance Agent Brief

Read **CLAUDE.md** first for site conventions and curation standards.
Read **util/SOUL.md** for script usage and the `last_checked` convention.
Everything produced by a heartbeat run lands in a PR — never push direct to main.

---

## Mission

Keep the Democracy Landscape accurate and fresh: verify stale org pages,
catch structural issues, tag gaps, and produce a brief AI-authored sync post
for human review. One PR per run.

---

## Steps

### 1. Orient

```bash
python util/stats.py
```

Note the counts, freshness distribution, and concept coverage. These numbers
go directly into the sync post — capture them before making any changes.

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

Run for any concepts added recently or with low org coverage. Add tags where
the match is genuine — don't force it.

### 4. Structural check

```bash
python util/pre_commit_check.py
```

Fix any hard failures before writing the post. The 4 known lint exceptions
(FLACSO-Cuba, Kongra Star, Memorial, NAMFREL) are expected — do not touch
them. See util/SOUL.md for why.

### 5. Write the sync post

Create `docs/blog/posts/YYYY-MM-sync.md`. See **AI-authored sync posts**
in CLAUDE.md for the required frontmatter and disclaimer. Structure:

1. One-paragraph explanation of what this post is and how it was generated
2. Landscape snapshot (numbers from step 1)
3. What was verified this run — org count, any status changes found
4. Notable findings (broken links fixed, tag gaps closed, etc.)
5. What's next — which orgs are oldest in the queue

Keep it short. This is a maintenance record, not an essay.
Source every claim from the wiki's own data or org websites.

### 6. Open the PR

```bash
git add -p   # review what you're committing
git commit
git push
# open PR titled: "Heartbeat sync — YYYY-MM"
```

Include in the PR body: the `stats.py` snapshot before and after, and a
summary of what changed.

---

## Escalation — stop and flag in the PR if

- An org's website has a permanent error and you cannot determine from other
  sources whether the org is still operating
- An org appears to have merged with or been renamed to another org already
  in the landscape
- A status change requires verification beyond what the org's own website shows
- More than 20% of pages checked need status changes in a single run (unusual —
  worth flagging before committing)
- You find content that may require editorial judgment on inclusion/exclusion

---

## Boundaries

**Do autonomously:** verify websites, update summaries and last_checked,
add concept tags, fix structural lint issues, write the sync post, open a PR.

**Do not do:** merge the PR, change the curation standard, add or remove an
org based solely on your own judgment without a sourced rationale in the PR,
write blog posts about anything other than the maintenance run itself.
