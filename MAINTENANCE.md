# Human Maintenance Guide

A step-by-step pass for a human contributor to keep org data fresh.
Run this whenever you have an hour or two — quarterly is a reasonable cadence.

Read **CLAUDE.md** first for site conventions and curation standards.

---

## Quick start (copy-paste sequence)

```bash
# 1. automated data collection (no input needed)
python util/check_rss.py --update-activity
python util/scrape_news.py
python util/check_urls.py

# 2. manual review pass (interactive — opens each site in browser)
python util/review_orgs.py

# 3. lint check
python util/pre_commit_check.py

# 4. commit
git add docs/organisations/
git commit -m "Maintenance pass — YYYY-MM: N orgs verified"
```

Read the detail sections below if anything looks unfamiliar.

---

## Setup (first time)

### 1. System dependencies

**Ubuntu / Debian:**
```bash
sudo apt install git python3 python3-pip python3-venv
```

**Arch Linux:**
```bash
sudo pacman -S git python python-pip
```

**macOS (Homebrew):**
```bash
brew install git python
```

### 2. Clone the repo

```bash
git clone https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io.git
cd DesigningOpenDemocracy.github.io
```

### 3. Python environment

Using a virtual environment keeps the project dependencies isolated:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r util/requirements.txt
```

Activate the venv at the start of every session:

```bash
source .venv/bin/activate
```

### 4. Verify

```bash
python util/stats.py
```

If that prints org counts without errors, you're ready.

---

## The sequence

### 1. Orient

```bash
python util/stats.py
```

Gives you a snapshot: org counts, freshness distribution, concept coverage.
Take note of how many orgs have no recent activity signal — that's your backlog.

---

### 2. Automated data collection

Run these in order. They write `activity.*` entries to frontmatter automatically
and do not require any manual input.

**Probe RSS feeds and sitemaps:**

```bash
python util/check_rss.py --update-activity
```

Tries 23 common feed paths per site. Writes `activity.rss` with the latest
post date and title, or `activity.sitemap` as a fallback (confirms the site
is alive but carries less weight). Takes a few minutes for the full set.

**Scrape news pages** (orgs that have `news_page:` set):

```bash
python util/scrape_news.py
```

Extracts dates from JSON-LD, OpenGraph, and `<time>` elements only.
Writes `activity.scrape`. Respects robots.txt.

**Check for dead websites:**

```bash
python util/check_urls.py
```

Reports which org websites return errors or have gone offline. Any
`CLIENT_ERROR` or `CONNECTION_ERROR` result warrants a manual check —
the org may have moved, gone inactive, or shut down.

---

### 3. Manual review pass

This is the highest-value step. `activity.manual` carries the most weight in
the activity ranking and stays fresh for two years.

```bash
python util/review_orgs.py
```

At startup it asks which scope to review:

```
Which orgs do you want to review?
  [1] All active orgs
  [2] Never manually reviewed
  [3] Stale manual review (>1 year old)
  [4] No or stale manual review (>2 years)
```

For each org it shows the current status and best existing activity date, then
opens the website in your browser. You confirm:

```
[a] Active      [i] Inactive    [d] Deregistered
[s] Skip        [q] Quit
```

Choosing `a`, `i`, or `d` writes `activity.manual` with today's date and updates
the `status:` field if it changed. You can add a note (e.g. "blog last updated
Jan 2025, looks dormant") or press Enter for the default.

Press `q` at any time to quit — progress is saved org by org as you go.

**If you find an org has shut down or gone inactive:**
- Set status to `inactive` or `deregistered` via the prompt
- Manually update `website:` to the Wayback Machine calendar URL:
  `https://web.archive.org/web/*/https://originalurl.com/`
- Update the summary if it refers to the org in present tense

**Useful flags:**

```bash
python util/review_orgs.py --only-stale   # skip the scope prompt; review >2yr orgs
python util/review_orgs.py --all          # include inactive/deregistered orgs
python util/review_orgs.py --slug loomio  # single org
```

---

### 4. Structural check

```bash
python util/pre_commit_check.py
```

Catches broken internal links and invalid concept slugs. Fix any hard failures
before committing. The four known lint exceptions (FLACSO-Cuba, Kongra Star,
Memorial, NAMFREL) are expected — see `util/SOUL.md`.

---

### 5. Commit and open a PR

Stage and commit your changes:

```bash
git add docs/organisations/
git commit -m "Maintenance pass — YYYY-MM: N orgs verified, M status updates"
```

Open a PR. In the body, include the `stats.py` before/after snapshot and a
brief note on anything notable you found (orgs gone inactive, websites moved,
new RSS feeds discovered, etc.).

---

## What counts as a good pass

You don't need to review every org in one sitting. A focused pass on options
`[2]` or `[4]` — orgs that have never been manually reviewed or are overdue —
is more valuable than a shallow pass over everything. Work at whatever pace
lets you actually look at each site rather than clicking through.

The automated tools (step 2) run fast and are worth doing every time even
if you don't have time for the full manual review.
