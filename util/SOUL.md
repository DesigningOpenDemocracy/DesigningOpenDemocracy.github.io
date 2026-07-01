# util/ — Maintenance Scripts: Intent and Conventions

This directory holds scripts for maintaining the Democracy Landscape wiki. Read this before running or modifying any of them — it records the *why*, not just the *what*.

---

## The maintenance philosophy

The Landscape is a living reference, not a snapshot. Orgs close, URLs rot, concept pages get renamed. The scripts here exist to surface those problems systematically rather than discovering them by accident.

**The `last_checked` convention** is the foundation: any org or concept page that has been recently verified (by a human or an AI with source access) should have `last_checked: "YYYY-MM-DD"` in its frontmatter. All scripts respect a `--days N` threshold: pages checked within N days are skipped as presumably correct. This means:

- Each maintenance pass focuses work on what actually needs attention.
- After verifying a page, update `last_checked` and commit it — that resets the clock.
- Set `--days 0` (or `--all`) to check everything regardless.

**Active orgs are highest priority.** Inactive/deregistered orgs still need checking but less urgently — they've already been marked as closed, so there's less harm in a stale URL or missing detail.

---

## Scripts

### `suggest_tags.py` — Suggest concept tags for org pages

Given a concept slug, finds org pages that don't have it tagged but mention
related keywords in their body. Keywords are derived from the concept slug
and its page; overly common words (appearing in >40% of orgs) are dropped
automatically. Extend with `--keywords` for better recall on niche concepts.

```bash
python util/suggest_tags.py deliberative-democracy
python util/suggest_tags.py citizens-assembly --keywords "mini-public" "citizen panel"
python util/suggest_tags.py sortition --threshold 2
```

Useful after adding a new concept page to surface which existing orgs should
be back-tagged, and after adding a batch of org pages to catch missed tags.

---

### `new_concept.py` — Scaffold a new concept page

Interactive CLI that creates `docs/concepts/<slug>.md` with the standard
discovery-aid structure: title, summary, Wikipedia link, See also.

```bash
python util/new_concept.py
```

Per CLAUDE.md conventions: concept pages are brief orientations pointing to
better sources, not authoritative explanations. The scaffolder reminds you.

---

### `pre_commit_check.py` — Run all checks in one pass

Runs `lint_orgs`, `check_concepts`, and `check_links` in sequence. Exits
non-zero if any hard check fails. Safe to install as a git pre-commit hook.

```bash
python util/pre_commit_check.py
python util/pre_commit_check.py --fix-hints

# Install as git hook:
echo 'python util/pre_commit_check.py' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Hard failures: broken internal links, invalid concept slugs.
Informational only: `lint_orgs` (4 known Wayback exceptions always appear).

---

### `add_org.py` — Scaffold a new org page

Interactive CLI that prompts for all standard frontmatter fields and validates
them inline: ISO country code, concept slugs against known list, Wayback URL
convention for inactive/deregistered orgs, location prompt for active orgs.
Writes `docs/organisations/<slug>.md` ready to fill in.

```bash
python util/add_org.py
```

No dependencies beyond stdlib.

---

### `find.py` — Full-text search

Searches title, summary (frontmatter), and body across org and concept pages.
Use before adding a new org to check for existing coverage, or to find pages
that mention a topic without explicitly tagging it.

```bash
python util/find.py "participatory budgeting"
python util/find.py "stafford beer" --concepts
python util/find.py "liquid" --orgs --context 2
```

No dependencies beyond stdlib.

---

### `check_rss.py` — Probe for RSS/Atom feeds and sitemap activity

Probes ~23 common feed URL paths per org site. Writes `activity.rss` (latest
post date/title) when a real feed is found, or `activity.sitemap`
(`<lastmod>`) as a fallback. With `ics_feed:` set, also fetches the iCal
calendar and writes `activity.ical`. Stamps `checked:` on every probe
regardless of outcome, so re-runs skip orgs probed within 7 days unless
`--force`.

```bash
python util/check_rss.py                    # probe all active orgs
python util/check_rss.py --update-activity   # also write activity.* fields
python util/check_rss.py --slug loomio       # single org
```

---

### `scrape_news.py` — Scrape news/blog index pages for activity dates

Opt-in: only runs for orgs with `news_page:` set. Extracts dates from
JSON-LD → meta/microdata → `<time>` → URL path patterns → human-readable
text, in that priority order. Writes `activity.scrape`. On failure, writes
a `hint:` (`spa`, `no_markup`, `bot_blocked`, `unreachable`) so future runs
know whether retrying is worth it — `spa`/`bot_blocked` are skipped on
re-runs unless `--force`.

```bash
python util/scrape_news.py                  # all active orgs with news_page:
python util/scrape_news.py --debug           # show which date signals were found
python util/scrape_news.py --update-rss      # also write discovered rss_feed:
```

---

### `review_orgs.py` — Interactive human review CLI

Opens each org's website in a browser and prompts for a status
confirmation, writing `activity.manual` (highest-priority, 730-day staleness)
and optionally updating `status:`. This is a **human-in-the-loop** tool —
it expects an interactive terminal and a browser, so an AI agent without
that can't drive it directly. For AI-assisted heartbeat runs, fetch the site
directly (or web-search as a fallback) and write an `activity.dod` entry
instead — `dod` is reserved for bot/automated checks (365-day staleness,
distinct from the human-visit `manual`). This script exists for a human
doing the same kind of pass.

```bash
python util/review_orgs.py --only-stale  # orgs with no/stale manual review
python util/review_orgs.py --slug loomio
```

Requires `pyyaml` in addition to `python-frontmatter`.

---

### `check_urls.py` — External URL reachability

HTTP-checks the `website:` field on org pages. Active orgs with Wayback URLs
(known exceptions) are skipped. Inactive orgs skipped by default. Reports
OK, REDIRECT (with final URL), CLIENT_ERROR, SERVER_ERROR, TIMEOUT,
SSL_ERROR, CONNECTION_ERROR.

```bash
python util/check_urls.py              # active orgs not checked in 365 days
python util/check_urls.py --all        # ignore last_checked
python util/check_urls.py --inactive   # also check inactive orgs
python util/check_urls.py --timeout 15 --delay 1
```

Requires `requests` (`util/requirements.txt`). Slow — run periodically, not
on every maintenance pass.

---

### `stamp.py` — Set last_checked: today

Updates `last_checked` in-place on one or more pages without reordering other keys. Use immediately after verifying a page.

```bash
python util/stamp.py namfrel                        # by slug
python util/stamp.py docs/organisations/namfrel.md  # by path
python util/stamp.py namfrel flacso-cuba            # multiple at once
python util/stamp.py --all-active                   # every active org
```

Slugs resolve against `docs/organisations/` first, then `docs/concepts/`. Running twice is safe — already-current pages are skipped. No dependencies beyond stdlib.

---

### `stats.py` — Landscape snapshot

Situational overview: org counts by status, geographic spread, type breakdown, `last_checked` freshness, and concept coverage. Run at the start of a session.

```bash
python util/stats.py
python util/stats.py --concepts          # also list orphaned concept pages
python util/stats.py --json              # machine-readable snapshot to stdout
python util/stats.py --save before.json  # also write snapshot to a file
python util/stats.py --diff before.json  # compare current state to a saved snapshot
```

`--save`/`--diff` are meant to bracket a maintenance run: save a snapshot
before starting the staleness queue, then diff against it at the end to get
the before/after numbers a heartbeat commit message or sync post needs,
without recomputing them by hand.

---

### `heartbeat_post.py` — Scaffold and manage the monthly heartbeat draft

Automates the mechanical parts of HEARTBEAT.md Step 6: finding or creating
this month's `docs/heartbeat/posts/YYYY-MM-sync.md`, typing the exact
required frontmatter and disclaimer block (risk of drift if done by hand —
e.g. the disclaimer's "pushed directly to main" wording), mirroring the
draft's body into `docs/heartbeat/current.md`, and releasing the draft
(dropping `draft: true`) once the month rolls over.

```bash
python util/heartbeat_post.py                  # find-or-create this month's draft, report status
python util/heartbeat_post.py --month 2026-07   # override the month label for a fresh draft
python util/heartbeat_post.py --mirror          # sync current.md from the active draft's body
python util/heartbeat_post.py --release         # drop draft: true, reset current.md
```

`--release` refuses to run while `<!-- tentative: revisit next run -->`
markers remain in the draft — resolve each first. Does not write the actual
content (Landscape update / In the world / Framework notes / What's next);
that's still a judgment call for whoever is running the brief.

---

### `check_orgs.py` — Staleness report

Who to re-verify next. Orders active orgs by: no `last_checked` date first, then oldest first.

```bash
python util/check_orgs.py              # active + inactive, 365-day threshold
python util/check_orgs.py --days 180   # flag pages not checked in 6 months
python util/check_orgs.py --active     # active orgs only
```

Run this to plan a maintenance pass — gives you a prioritised queue.

---

### `check_concepts.py` — Concept slug validator

Two checks:
1. **Invalid slugs**: org pages listing concept slugs that don't match any file in `docs/concepts/`. These silently produce broken concept chips in the UI.
2. **Orphaned concepts**: concept pages not referenced by any org. May indicate a renamed file or a concept that needs org coverage.

```bash
python util/check_concepts.py              # pages not checked in 365 days
python util/check_concepts.py --days 90
python util/check_concepts.py --all        # check all pages
python util/check_concepts.py --no-orphans # skip orphan check
```

Check 1 respects `--days`. Check 2 always runs against all pages (orphan status depends on the whole corpus, not individual page age).

---

### `check_internal_links.py` — Internal link checker (ezlinks-aware)

A stricter successor to `check_links.py`: same goal (flag `[text](path.md)`
links that don't resolve), but also replicates mkdocs-ezlinks-plugin's
basename-fallback resolution — the mechanism that makes this site's
`../../blog/posts/<slug>.md`-style cross-references from `concepts/` and
`organisations/` actually work despite overshooting `docs/`. This is the
version wired into CI (`.github/workflows/build.yml`); prefer it over
`check_links.py` for anything that needs to match what CI will catch.

```bash
python util/check_internal_links.py
```

---

### `check_links.py` — Internal link checker

Finds `[text](path.md)` links that resolve to non-existent files. Only checks `.md` links (not external URLs).

**MkDocs link resolution**: with `use_directory_urls: true` (default), relative link paths resolve differently for cross-section links vs. blog post links. Two strategies are tried for each link and a link is only flagged if both fail. See the script's docstring for the full explanation if you need to debug false positives.

```bash
python util/check_links.py              # both sections, 365-day threshold
python util/check_links.py --all        # check all pages
python util/check_links.py --dir concepts   # only check concept pages
```

---

### `lint_orgs.py` — Structural linter

Enforces conventions from CLAUDE.md that are easy to get wrong when marking orgs inactive or adding new entries:

| Rule | What it checks |
|---|---|
| `website-active` | Active org with a Wayback Machine URL — should be a live URL |
| `website-inactive` | Inactive/deregistered org with a live URL — should point to Wayback |
| `location` | Active org missing `location:` coordinates — won't appear on the interactive map |
| `concepts` | Concept slugs not matching any `docs/concepts/` file (also in `check_concepts.py`) |
| `status` | Status value outside `active \| inactive \| deregistered` |
| `country` | Country field is not a 2-letter ISO 3166-1 alpha-2 code |

Structural rules don't go stale — a wrong URL is still wrong regardless of `last_checked`. So `--days` defaults to 0 (check all). Use `--days N` to suppress noise during rapid-edit sessions.

```bash
python util/lint_orgs.py               # check all pages
python util/lint_orgs.py --days 30     # suppress pages touched this month
python util/lint_orgs.py --fix-hints   # print suggested frontmatter corrections
```

---

## Wayback Machine convention

From CLAUDE.md: **defunct orgs** should have their `website:` field pointing to the Wayback Machine calendar URL:

```yaml
website: https://web.archive.org/web/*/https://originalurl.com/
```

The `*` gives a calendar of all captures rather than a single snapshot. `lint_orgs.py` enforces this.

**Known exceptions**: a small number of `active` orgs intentionally use Wayback URLs because their live site is in a restricted or unreliable jurisdiction (e.g. FLACSO-Cuba, Kongra Star in AANES/Syria). `lint_orgs.py` will flag these — they are false positives. Do not "fix" them to a live URL unless you can verify the live site is reliably accessible to international readers.

---

## Typical maintenance workflows

### AI-assisted recheck pass

```bash
# 1. Situational overview
python util/stats.py

# 2. See what needs attention
python util/check_orgs.py --days 365 --active

# 3. Pick the oldest N pages, verify each one (check website, status, content)
# 4. Stamp verified pages
python util/stamp.py slug1 slug2 slug3

# 5. Run lint to catch anything structural
python util/lint_orgs.py --fix-hints

# 6. Run concept and link checks
python util/check_concepts.py --all
python util/check_links.py --all
```

### Quick pre-PR check

```bash
python util/lint_orgs.py --days 0      # full structural scan
python util/check_concepts.py --all    # all concept slugs
python util/check_links.py --all       # all links
```

---

## Requirements

`add_org.py`, `find.py`, and `stamp.py` use stdlib only. Most other scripts use `python-frontmatter`, `python-dateutil`, and `requests` — all in `util/requirements.txt`. `stats.py` and `heartbeat_post.py` need `python-frontmatter` only; `review_orgs.py` additionally needs `pyyaml`.

```bash
pip install -r util/requirements.txt
```

Scripts are standalone; no shared library needed.
