set dotenv-load := false

venv := "venv"
python := venv + "/bin/python"
pip := venv + "/bin/pip"
mkdocs := venv + "/bin/mkdocs"

# Show available commands
default:
    @just --list

# --- Quick start ---

# Everything in MAINTENANCE.md that's automated, network-dependent, and doesn't
# need a human at the keyboard. Writes activity/contact/logo/calendar frontmatter
# as it goes and re-normalises field order at the end; review the diff before
# committing. Deliberately excludes the interactive review-orgs step, the slow
# Playwright-based contact-probe-deep, and the full mkdocs --strict build — see
# the printed next-steps for those. A few minutes to ~15min depending on how
# many orgs are due for a recheck.
#
# Gap-filling only: an org that already has a contact record on file is
# trusted and skipped outright, no matter how long ago it was checked — no
# one's watching, so there's no one to act on a `[CONFLICTS with existing:
# ...]` flag if a re-check turned one up. Use `maintenance-human-in-loop`
# for a pass that also re-verifies existing records.
#
# One-shot local maintenance pass — read nothing, just run this.
[group('quick start')]
maintenance: (_maintenance-pass "--skip-existing")

# Same as `maintenance`, but also re-checks orgs that already have a contact
# record instead of trusting it forever — still skips ones checked within the
# last 180 days (check_contact.py's own staleness gate), so it's not a full
# re-probe of everything either. The difference from `maintenance` is who's
# watching: re-checking an existing record can surface a `[CONFLICTS with
# existing: ...]` flag that needs a human (or an LLM doing a deliberate
# review pass) to look at the diff and decide, so only reach for this when
# you intend to actually read the output afterward.
#
# Also re-checks orgs with an existing contact record — for when a human's watching.
[group('quick start')]
maintenance-human-in-loop: (_maintenance-pass "")

_maintenance-pass contact_skip_flag: _deps
    @echo "=== 1/8  RSS & sitemap activity ==="
    just rss-probe --update-activity
    @echo "=== 2/8  News page scrape ==="
    just news-probe
    @echo "=== 3/8  Org website liveness ==="
    just site-check
    @echo "=== 4/8  Calendar (ics_feed) sync ==="
    just sync-events
    @echo "=== 5/8  Contact info probe ==="
    just contact-probe --write {{contact_skip_flag}}
    @echo "=== 6/8  Logo probe ==="
    just logo-probe --write
    @echo "=== 7/8  Shared-link preview metadata (blog posts) ==="
    just shared-links --write --write-description
    @echo "=== 8/8  Re-normalise frontmatter these probes just wrote ==="
    just reorder-frontmatter
    @echo ""
    @echo "Automated pass done. Review before committing:"
    @echo "  git status && git diff docs/organisations/ docs/data/ docs/blog/ docs/assets/org-logos/"
    @FILES=$(git status --porcelain -- docs/organisations/ docs/data/ docs/blog/ docs/assets/org-logos/ 2>/dev/null | wc -l | tr -d ' '); \
    if [ "$FILES" -gt 0 ]; then \
        echo ""; \
        echo "Suggested commit (after you've reviewed the diff above):"; \
        echo "  git add docs/organisations/ docs/data/ docs/blog/ docs/assets/org-logos/"; \
        echo "  git commit -m \"chore: automated maintenance pass — $(date +%Y-%m-%d)\" -m \"$FILES file(s) touched — activity/contact/logo/calendar/shared-link data refreshed by just maintenance\""; \
    else \
        echo ""; \
        echo "Nothing changed — everything was already fresh (or skipped). Nothing to commit."; \
    fi
    @echo ""
    @echo "Still worth doing by hand:"
    @echo "  just review-orgs               # interactive: opens each org site in your browser"
    @echo "  just discover-elections        # report-only: elections.yml gaps"
    @echo "  just maintenance-human-in-loop  # also re-checks orgs that already have a contact record, not just gaps"
    @echo "  just contact-probe-deep --slug <org>   # SPA org site still missing contact info? (needs: just setup-playwright, once)"
    @echo "  just check                     # full pre-push checklist (mkdocs --strict + lint gates)"

# --- Setup ---

# Set up Python virtual environment and install dependencies
[group('setup')]
setup:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur requirements.txt

# Set up utility script dependencies (createPost, frontmatter_updator)
[group('setup')]
setup-util:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur util/requirements.txt

# One-time extra setup for contact-probe-deep (headless Chromium via Playwright)
[group('setup')]
setup-playwright: _deps
    {{pip}} install playwright
    {{python}} -m playwright install chromium

# Internal: venv with utility-script deps only (no mkdocs stack needed)
_deps:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -qUr util/requirements.txt pyyaml

# --- Build & deploy ---

# Serve the site locally (opens browser)
[group('build & deploy')]
serve: setup
    xdg-open http://127.0.0.1:8000/ &
    {{mkdocs}} serve

# Build the site into site/
[group('build & deploy')]
build: setup
    {{mkdocs}} build

# Build with strict mode and check for broken internal links
[group('build & deploy')]
check-links: setup
    {{mkdocs}} build --strict
    {{python}} util/check_internal_links.py

# Remove generated site files
[group('build & deploy')]
clean:
    rm -rf site

# Deploy to GitHub Pages
[group('build & deploy')]
deploy: setup
    {{mkdocs}} gh-deploy --force

# --- Content authoring ---

# Create a new blog post interactively
[group('content authoring')]
post: setup
    {{python}} util/createPost.py

# Auto-fill frontmatter using OpenAI (requires OPENAI_API_KEY)
[group('content authoring')]
frontmatter file: setup setup-util
    {{python}} util/frontmatter_updator.py {{file}}

# Scaffold a new organisation page interactively (stdlib only)
[group('content authoring')]
add-org:
    python3 util/add_org.py

# Scaffold a new concept page interactively (stdlib only)
[group('content authoring')]
new-concept:
    python3 util/new_concept.py

# --- Tests & pre-push checks (offline; same gates as CI) ---

# Run the offline regression test suite (tests/)
[group('tests & pre-push checks')]
test: setup-util
    {{pip}} install -q pyyaml
    {{python}} -m unittest discover tests

# Full pre-push checklist: strict build + internal links + event sourcing + elections + frontmatter order + footnote quotes
[group('tests & pre-push checks')]
check: check-links
    {{python}} util/check_event_sourcing.py
    {{python}} util/check_elections.py
    {{python}} util/reorder_frontmatter.py --check
    {{python}} util/check_footnote_quotes.py

# Lint org page structure against CLAUDE.md conventions (--fix-hints for suggestions)
[group('tests & pre-push checks')]
lint-orgs *args="": _deps
    {{python}} util/lint_orgs.py {{args}}

# Democracy Landscape snapshot stats (see also --concepts, --save/--diff <file>)
[group('tests & pre-push checks')]
stats *args="": _deps
    {{python}} util/stats.py {{args}}

# Which org pages are due for re-check, by priority
[group('tests & pre-push checks')]
due-orgs *args="": _deps
    {{python}} util/check_orgs.py {{args}}

# Report prose footnote citation quote coverage (--missing to list gaps)
[group('tests & pre-push checks')]
footnote-quotes *args="": _deps
    {{python}} util/check_footnote_quotes.py {{args}}

# Validate/score org event sourcing (--calculate/--recalculate fill proof_level)
[group('tests & pre-push checks')]
event-sourcing *args="": _deps
    {{python}} util/check_event_sourcing.py {{args}}

# Validate docs/data/elections.yml (sourcing, dates, duplicates)
[group('tests & pre-push checks')]
check-elections *args="": _deps
    {{python}} util/check_elections.py {{args}}

# Enforce canonical frontmatter ordering (omit --check to reorder in place)
[group('tests & pre-push checks')]
reorder-frontmatter *args="": _deps
    {{python}} util/reorder_frontmatter.py {{args}}

# --- Citation verification (network-dependent, not in CI) ---

# Verify quotes against live pages (--slug repeatable; --offline = stored .pagecache copies, no network; --unchecked-only)
[group('citation verification')]
verify-quotes *args="": _deps
    {{python}} util/check_fragments.py {{args}}

# Liveness check for event citation URLs (BLOCKED = bot protection, not dead — check in a browser first)
[group('citation verification')]
verify-urls *args="": _deps
    {{python}} util/check_event_urls.py {{args}}

# Checklist for human verification of citations automation can't resolve (--live adds AMBIGUOUS/MISMATCH)
[group('citation verification')]
worklist *args="": _deps
    {{python}} util/manual_check_worklist.py {{args}}

# List citation URLs waiting on a manual browser save (step 1 of the manual-dump runbook)
[group('citation verification')]
dump-requests:
    @cat manual-dump/requests.txt 2>/dev/null || echo "No pending requests (manual-dump/requests.txt does not exist)"

# Import manually-saved pages into the evidence cache (run --dry-run first)
[group('citation verification')]
import-dump *args="": _deps
    {{python}} util/import_manual_dump.py {{args}}

# Read locally-cached copies of cited pages in .pagecache/ (list | show | path)
[group('citation verification')]
page-cache *args="":
    python3 util/pagecache.py {{args}}

# --- Maintenance probes (network; most write frontmatter — review the diff) ---

# Probe org sites for RSS/Atom feeds (--update-activity writes activity.rss/sitemap/ical)
[group('maintenance probes')]
rss-probe *args="": _deps
    {{python}} util/check_rss.py {{args}}

# Scrape news/blog index pages for orgs with news_page: set
[group('maintenance probes')]
news-probe *args="": _deps
    {{python}} util/scrape_news.py {{args}}

# Check org website: URLs are still live (dead/redirecting sites need a look)
[group('maintenance probes')]
site-check *args="": _deps
    {{python}} util/check_urls.py {{args}}

# Sync ics_feed: calendars into docs/data/events/<slug>.json for the site calendar
[group('maintenance probes')]
sync-events *args="": _deps
    {{python}} util/sync_events.py {{args}}

# Probe org sites for public contact info (--write records high-confidence findings)
[group('maintenance probes')]
contact-probe *args="": _deps
    {{python}} util/check_contact.py {{args}}

# Headless-browser contact probe for SPA org sites (needs: just setup-playwright, once; slow)
[group('maintenance probes')]
contact-probe-deep *args="": _deps
    {{python}} util/check_contact_deep.py {{args}}

# Probe org sites for logos (--write populates logo: frontmatter)
[group('maintenance probes')]
logo-probe *args="": _deps
    {{python}} util/check_logo.py {{args}}

# Fetch shared_link preview metadata for blog posts (--write fills title:/image:)
[group('maintenance probes')]
shared-links *args="": _deps
    {{python}} util/fetch_shared_link_previews.py {{args}}

# Query Wikidata for upcoming elections missing from elections.yml (report-only, never writes)
[group('maintenance probes')]
discover-elections *args="": _deps
    {{python}} util/discover_elections.py {{args}}

# --- Interactive / editorial tools ---

# Interactive review of org statuses in your browser (writes activity.manual)
[group('editorial tools')]
review-orgs *args="": _deps
    {{python}} util/review_orgs.py {{args}}

# Stamp last_checked: today on org/concept pages
[group('editorial tools')]
stamp *args="": _deps
    {{python}} util/stamp.py {{args}}

# Full-text search across org and concept pages (use before adding a new org)
[group('editorial tools')]
find *args="": _deps
    {{python}} util/find.py {{args}}
