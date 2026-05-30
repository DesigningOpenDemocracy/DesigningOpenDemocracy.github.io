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
# 1. See what needs attention
python util/check_orgs.py --days 365 --active

# 2. Pick the oldest N pages, verify each one (check website, status, content)
# 3. Update last_checked in frontmatter after verifying
# 4. Run lint to catch anything structural
python util/lint_orgs.py --fix-hints

# 5. Run concept and link checks
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

All scripts use `python-frontmatter`, `python-dateutil` — both in `util/requirements.txt`.

```bash
pip install -r util/requirements.txt
```

Scripts are standalone; no shared library needed.
