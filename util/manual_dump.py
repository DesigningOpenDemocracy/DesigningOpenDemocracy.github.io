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
   and saves it via "Save Page As -> Web Page, HTML only" into
   manual-dump/snapshots/. The filename doesn't matter, because the source
   URL is recovered from the saved file itself — in order of preference:
     a. manual-dump/snapshots/url-map.txt, a sidecar you maintain with one
        '<filename> <url>' line per snapshot (see load_url_map()). This is
        the authoritative mapping: browsers have become unreliable about
        stamping the old `<!-- saved from url=(NNNN)... -->` comment (some
        versions/save modes write it, some don't), so an explicit line here
        always wins;
     b. the `saved from url=(NNNN)...` stamp itself, when the browser did
        write one (a convention shared by Firefox, Chrome, and IE/Edge);
     c. the page's own <link rel="canonical"> / <meta property="og:url">
        declaration — best-effort only, since sites occasionally declare a
        variant URL (AMP, tracking params, trailing slash) that won't match
        the citation exactly.
   If none of these yields a URL matching a current citation, the importer
   prints a ready-to-paste url-map.txt line instead of guessing.
3. util/import_manual_dump.py picks up every file in snapshots/, extracts
   its text with the same text_fragment.html_to_text() a live fetch uses,
   verifies it against whatever evidence cites that URL, records the
   result in the shared evidence cache's manual_verified/manual_checked
   fields, removes the URL from requests.txt, and moves the file into
   imported/ (a sibling of snapshots/, not inside it — the inbox stays
   free of processed clutter) so a re-run doesn't reprocess it.

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
# Human-maintained sidecar mapping snapshot filenames to their source URLs —
# the authoritative recovery path when a browser doesn't stamp the
# saved-from-url comment. Lives in snapshots/ so it travels with the inbox;
# the importer's file scan never picks it up.
URL_MAP_PATH = os.path.join(SNAPSHOTS_DIR, "url-map.txt")
# Machine-written counterpart to imported/: one JSON object per processed
# snapshot ({imported-filename: {url, source, checked, good, mismatch}}),
# accumulated across runs. This is how you answer "which saved file backs up
# this citation URL?" later — grep the URL here instead of opening HTML
# files hunting for stamps. Written only on real (non-dry-run) imports.
IMPORT_MAP_PATH = os.path.join(DUMP_DIR, "import.json")
# A sibling of snapshots/, deliberately not a child of it: snapshots/ is
# the human's messy inbox (saved pages, and — if they used "Save Page As →
# complete" — companion <name>_files asset folders), imported/ is what the
# importer has already processed. Keeping processed output out of the inbox
# makes "what's still waiting" readable at a glance.
IMPORTED_DIR = os.path.join(DUMP_DIR, "imported")

# Firefox/Chrome/IE-Edge historically write this as the first line of a
# page saved via "Save Page As" (either "HTML only" or "complete") —
# (NNNN) is a zero-padded length prefix for the URL that follows. Only the
# first 2KB is scanned since it's always the very first line. Not all
# current browsers/versions write it anymore, hence the url-map.txt and
# meta-tag fallbacks below.
_SAVED_FROM_RE = re.compile(r"saved from url=\(\d+\)(\S+)")

# Best-effort self-declared URLs inside the page itself. Less trustworthy
# than the stamp or url-map.txt: sites occasionally declare a variant
# (AMP version, tracking params, trailing slash) that won't string-match
# the citation URL — but they're often present even in unstamped saves,
# since most CMSes put them in the served <head>.
_CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"')
_OG_URL_RE = re.compile(r'<meta[^>]+property="og:url"[^>]+content="([^"]+)"')


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
    doesn't carry one (e.g. the browser didn't stamp it, or the file was
    hand-edited)."""
    m = _SAVED_FROM_RE.search(html_text[:2048])
    return m.group(1) if m else None


def parse_meta_url(html_text):
    """Best-effort fallback: the page's own <link rel="canonical"> or
    <meta property="og:url"> declaration, whichever comes first. Returns
    None when neither is present. Deliberately looser than the stamp —
    a site can declare a variant of the URL you actually visited (AMP,
    tracking params) — so callers should treat a mismatch with the
    expected citation as 'needs a url-map.txt line', not as ground truth.
    Two common malformed forms are normalised up front: protocol-relative
    ('//host/path') and scheme-less ('www.host/path') values both get an
    https: prefix, since a bare relative value could never string-match a
    citation URL anyway."""
    for regex in (_CANONICAL_RE, _OG_URL_RE):
        m = regex.search(html_text)
        if m:
            url = m.group(1).strip()
            if url.startswith("//"):
                return "https:" + url
            if url.startswith("www."):
                return "https://" + url
            return url
    return None


def load_url_map(path=None):
    """Parse manual-dump/snapshots/url-map.txt: one '<filename> <url>'
    line per snapshot whose source URL can't be recovered from the file
    itself (unstamped save + no canonical/og:url). The filename is taken
    as everything before the final whitespace run and the URL as the last
    token, so filenames containing spaces work without quoting; blank
    lines and #-comments are ignored. Returns {basename: url}."""
    path = path or URL_MAP_PATH
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.rsplit(None, 1)
            if len(parts) != 2:
                continue  # malformed line — skip rather than guess
            filename, url = parts
            mapping[filename] = url
    return mapping
