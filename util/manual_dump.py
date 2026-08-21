"""
manual_dump.py — shared helpers for the manual page-dump workflow: a local
escape hatch for citation URLs no automated fetch can reach (bot-blocked,
rate-limited, robots.txt-disallowed) but a human's own browser still can.

manual-dump/ lives at the repo root, entirely gitignored — it's local
working state, not archival. The durable, shareable copy of a citation is
still Wayback Machine (check_fragments.py --save-to-wayback); this exists
only for the URLs that neither Wayback nor a script can reach, but a human
sitting at a real browser can.

Workflow:
1. check_fragments.py (and check_event_urls.py) append a URL to
   manual-dump/requests.txt whenever they hit BLOCKED_ERRORS for it and no
   manual_verified evidence already covers the citations at that URL.
2. A human opens each URL in a real browser, waits for it to fully load,
   and saves it via Firefox's "Save Page As -> Web Page, HTML only" (not
   "Web Page, complete" — that also writes a folder of asset files nothing
   here needs) into manual-dump/snapshots/. The filename doesn't matter:
   the browser stamps a `<!-- saved from url=(NNNN)https://... -->` comment
   as the first line of the file (a convention shared by Firefox, Chrome,
   and IE/Edge), which is how the source URL is recovered.
3. util/import_manual_dump.py picks up every file in snapshots/, extracts
   its text with the same text_fragment.html_to_text() a live fetch uses,
   verifies it against whatever evidence cites that URL, records the
   result in the shared evidence cache's manual_verified/manual_checked
   fields, removes the URL from requests.txt, and moves the file into
   snapshots/imported/ so a re-run doesn't reprocess it.

See check_fragments.py's check_evidence(): a URL marked "blocked" is
normally skipped with no fetch, but a manual_verified entry for the exact
evidence hash being checked is consulted first, so a manually-imported
snapshot resolves what would otherwise report STILL BLOCKED forever.
"""

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
DUMP_DIR = os.path.join(ROOT, "manual-dump")
REQUESTS_PATH = os.path.join(DUMP_DIR, "requests.txt")
SNAPSHOTS_DIR = os.path.join(DUMP_DIR, "snapshots")
IMPORTED_DIR = os.path.join(SNAPSHOTS_DIR, "imported")

# Firefox/Chrome/IE-Edge all write this as the first line of a page saved
# via "Save Page As" (either "HTML only" or "complete") — (NNNN) is a
# zero-padded length prefix for the URL that follows. Only the first 2KB
# is scanned since this is always the very first line.
_SAVED_FROM_RE = re.compile(r"saved from url=\(\d+\)(\S+)")


def queue_request(url):
    """Append url to manual-dump/requests.txt if not already listed.
    Best-effort — never raises, since this is a convenience nudge for a
    human, not something that should ever fail a verification run."""
    try:
        os.makedirs(DUMP_DIR, exist_ok=True)
        existing = set()
        if os.path.exists(REQUESTS_PATH):
            with open(REQUESTS_PATH, encoding="utf-8") as f:
                existing = {line.strip() for line in f if line.strip()}
        if url in existing:
            return
        with open(REQUESTS_PATH, "a", encoding="utf-8") as f:
            f.write(url + "\n")
    except OSError:
        pass


def dequeue_request(url):
    """Remove url from manual-dump/requests.txt, if present. Used by
    import_manual_dump.py once a snapshot for that url has been imported."""
    if not os.path.exists(REQUESTS_PATH):
        return
    with open(REQUESTS_PATH, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]
    remaining = [line for line in lines if line.strip() != url]
    if remaining == lines:
        return
    with open(REQUESTS_PATH, "w", encoding="utf-8") as f:
        for line in remaining:
            f.write(line + "\n")


def parse_saved_from_url(html_text):
    """Recover the source URL from a browser-saved HTML file's leading
    'saved from url=(NNNN)https://...' comment. Returns None if the file
    doesn't carry one (e.g. it wasn't saved via "Save Page As", or was
    hand-edited)."""
    m = _SAVED_FROM_RE.search(html_text[:2048])
    return m.group(1) if m else None
