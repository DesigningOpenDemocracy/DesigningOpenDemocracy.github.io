set dotenv-load := false

venv := "venv"
python := venv + "/bin/python"
pip := venv + "/bin/pip"
mkdocs := venv + "/bin/mkdocs"

# Show available commands
default:
    @just --list

# Set up Python virtual environment and install dependencies
setup:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur requirements.txt

# Set up utility script dependencies (createPost, frontmatter_updator)
setup-util:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur util/requirements.txt

# Serve the site locally (opens browser)
serve: setup
    xdg-open http://127.0.0.1:8000/ &
    {{mkdocs}} serve

# Build the site into site/
build: setup
    {{mkdocs}} build

# Build with strict mode and check for broken internal links
check-links: setup
    {{mkdocs}} build --strict
    {{python}} util/check_internal_links.py

# Remove generated site files
clean:
    rm -rf site

# Deploy to GitHub Pages
deploy: setup
    {{mkdocs}} gh-deploy --force

# Create a new blog post interactively
post: setup
    {{python}} util/createPost.py

# Auto-fill frontmatter using OpenAI (requires OPENAI_API_KEY)
frontmatter file: setup setup-util
    {{python}} util/frontmatter_updator.py {{file}}

# Run the offline regression test suite (tests/)
test: setup-util
    {{pip}} install -q pyyaml
    {{python}} -m unittest discover tests

# --- Offline checks (pre-push checklist; same gates as CI) ---

# Internal: venv with utility-script deps only (no mkdocs stack needed)
_deps:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -qUr util/requirements.txt pyyaml

# Full pre-push checklist: build + internal links + event sourcing + frontmatter order
check: build
    {{python}} util/check_internal_links.py
    {{python}} util/check_event_sourcing.py
    {{python}} util/reorder_frontmatter.py --check

# Lint org page structure against CLAUDE.md conventions (--fix-hints for suggestions)
lint-orgs *args="": _deps
    {{python}} util/lint_orgs.py {{args}}

# Democracy Landscape snapshot stats (see also --concepts, --save/--diff <file>)
stats *args="": _deps
    {{python}} util/stats.py {{args}}

# Which org pages are due for re-check, by priority
due-orgs *args="": _deps
    {{python}} util/check_orgs.py {{args}}

# Report prose footnote citation quote coverage (--missing to list gaps)
footnote-quotes *args="": _deps
    {{python}} util/check_footnote_quotes.py {{args}}

# Validate/score org event sourcing (--calculate/--recalculate fill proof_level)
event-sourcing *args="": _deps
    {{python}} util/check_event_sourcing.py {{args}}

# Enforce canonical frontmatter ordering (omit --check to reorder in place)
reorder-frontmatter *args="": _deps
    {{python}} util/reorder_frontmatter.py {{args}}

# --- Citation verification (network-dependent, not in CI) ---

# Verify quotes against live pages (--slug repeatable; --offline = stored .pagecache copies, no network; --unchecked-only)
verify-quotes *args="": _deps
    {{python}} util/check_fragments.py {{args}}

# Liveness check for event citation URLs (BLOCKED = bot protection, not dead — check in a browser first)
verify-urls *args="": _deps
    {{python}} util/check_event_urls.py {{args}}

# Checklist for human verification of citations automation can't resolve (--live adds AMBIGUOUS/MISMATCH)
worklist *args="": _deps
    {{python}} util/manual_check_worklist.py {{args}}

# List citation URLs waiting on a manual browser save (step 1 of the manual-dump runbook)
dump-requests:
    @cat manual-dump/requests.txt 2>/dev/null || echo "No pending requests (manual-dump/requests.txt does not exist)"

# Import manually-saved pages into the evidence cache (run --dry-run first)
import-dump *args="": _deps
    {{python}} util/import_manual_dump.py {{args}}

# Read locally-cached copies of cited pages in .pagecache/ (list | show | path)
page-cache *args="":
    python3 util/pagecache.py {{args}}

# --- Maintenance probes (network; most write frontmatter — review the diff) ---

# Probe org sites for RSS/Atom feeds (--update-activity writes activity.rss/sitemap/ical)
rss-probe *args="": _deps
    {{python}} util/check_rss.py {{args}}

# Scrape news/blog index pages for orgs with news_page: set
news-probe *args="": _deps
    {{python}} util/scrape_news.py {{args}}

# Sync ics_feed: calendars into docs/data/events/<slug>.json for the site calendar
sync-events *args="": _deps
    {{python}} util/sync_events.py {{args}}

# Probe org sites for public contact info (--write records high-confidence findings)
contact-probe *args="": _deps
    {{python}} util/check_contact.py {{args}}

# Probe org sites for logos (--write populates logo: frontmatter)
logo-probe *args="": _deps
    {{python}} util/check_logo.py {{args}}

# Fetch shared_link preview metadata for blog posts (--write fills title:/image:)
shared-links *args="": _deps
    {{python}} util/fetch_shared_link_previews.py {{args}}

# --- Interactive / editorial tools ---

# Interactive review of org statuses in your browser (writes activity.manual)
review-orgs *args="": _deps
    {{python}} util/review_orgs.py {{args}}

# Stamp last_checked: today on org/concept pages
stamp *args="": _deps
    {{python}} util/stamp.py {{args}}

# Full-text search across org and concept pages (use before adding a new org)
find *args="": _deps
    {{python}} util/find.py {{args}}

# Scaffold a new organisation page interactively (stdlib only)
add-org:
    python3 util/add_org.py

# Scaffold a new concept page interactively (stdlib only)
new-concept:
    python3 util/new_concept.py
