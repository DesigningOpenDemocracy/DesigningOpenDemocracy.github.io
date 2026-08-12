"""
text_fragment.py — pure, dependency-free helpers for building and reading
Text Fragment (#:~:text=) directives (https://wicg.github.io/scroll-to-text-fragment/).

Shared by util/check_fragments.py (network verification, run offline/manually)
and hooks/org_events.py (the MkDocs build-time Jinja filter that renders
event links). Kept dependency-free (stdlib only: re, urllib.parse) so the
build hook can import it without pulling requests/frontmatter into the
`mkdocs build` path.

Fragments are never stored in frontmatter `url:` values — see the
"Prose footnote citations" / "events:" sections of CLAUDE.md. A stored
fragment and the quote: it was derived from can drift out of sync if
either is edited without the other; deriving the fragment at render time
from quote: instead makes that drift structurally impossible.
"""

import difflib
import json
import os
import re
from urllib.parse import quote as url_quote
from urllib.parse import unquote, urlparse, urlunparse

ARCHIVE_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "data", "event-evidence-cache.json"
)


def normalize_ws(text):
    """Collapse whitespace for forgiving substring matching."""
    return " ".join(text.split())


def count_occurrences(page_text, quote_text):
    """How many times quote_text appears verbatim (whitespace-normalised)
    in page_text. A count > 1 means the browser's #:~:text= highlight
    could land on the wrong occurrence, and the quote is weaker evidence
    than it looks — it isn't pinned to one specific place on the page.
    Used by check_fragments.py's AMBIGUOUS report."""
    if not page_text or not quote_text:
        return 0
    return normalize_ws(page_text).count(normalize_ws(quote_text))


def find_span(page_text, quote_text):
    """Locate quote_text in page_text, whitespace-tolerant (same matching
    semantics as text_contains/count_occurrences — any run of whitespace
    in the quote matches any run of whitespace on the page), returning
    (start, end) character offsets in page_text's OWN coordinate space —
    not a normalized copy's. Returns None if not found.

    This exists specifically so callers doing anything position-based
    with the match (e.g. check_fragments.py's paragraph_hash(), which
    needs to find paragraph boundaries around the quote) never mix
    normalized-text offsets with raw-text indexing. A prior version of
    paragraph_hash() did exactly that — searched a whitespace-normalized
    copy for the quote's position, then reused that offset to index into
    the original text — and drifted by one character per paragraph break
    preceding the quote (each "\\n\\n" shrinks to one space under
    normalization), landing in the wrong paragraph on any page with
    enough short paragraphs before the cited sentence. Building the
    match with a regex against page_text directly sidesteps the whole
    class of bug: the match's .start()/.end() are always in page_text's
    own coordinates, by construction.
    """
    if not page_text or not quote_text:
        return None
    words = normalize_ws(quote_text).split(" ")
    pattern = r"\s+".join(re.escape(w) for w in words)
    m = re.search(pattern, page_text)
    if not m:
        return None
    return m.start(), m.end()


def extract_fragment(url):
    """Decoded evidence text from a url's #:~:text= directive, or None."""
    parsed = urlparse(url)
    if parsed.fragment and parsed.fragment.startswith(":~:text="):
        return unquote(parsed.fragment[len(":~:text="):])
    return None


def strip_fragment(url):
    """Return url with any #:~:text= directive removed. Preserves a
    non-text fragment (e.g. #section-2) that preceded it, if present."""
    parsed = urlparse(url)
    if not parsed.fragment or not parsed.fragment.startswith(":~:text="):
        return url
    return urlunparse(parsed._replace(fragment=""))


def _split_ellipsis(quote_text):
    """If quote_text contains '...' (editorial truncation), return
    (start, end) — the text before and after it. Returns None if there's
    no '...' or either side is empty after stripping. Shared by
    make_text_fragment() (builds textStart,textEnd from it) and
    quote_matches() (verifies both sides appear on the page, in order) —
    the two must agree on what '...' means, or a quote using it verifies
    as a MISMATCH despite the fragment it generates being correct, which
    is exactly what happened before these shared the same split logic
    (see the CLAUDE.md "events:" #:~:text= note / issue #145)."""
    normalized = normalize_ws(quote_text)
    if "..." not in normalized:
        return None
    parts = normalized.split("...")
    start = parts[0].strip()
    end = parts[-1].strip()
    return (start, end) if start and end else None


def quote_matches(page_text, quote_text):
    """Does page_text satisfy quote_text as evidence? A quote containing
    '...' is satisfied when both the text before and after it are found
    on the page with the 'before' text appearing first — mirroring the
    textStart,textEnd Text Fragment semantics make_text_fragment()
    converts it to. A quote without '...' must appear verbatim
    (whitespace-normalised) as one contiguous run, same as always."""
    if not page_text or not quote_text:
        return False
    split = _split_ellipsis(quote_text)
    if split is None:
        return normalize_ws(quote_text) in normalize_ws(page_text)
    start, end = split
    start_span = find_span(page_text, start)
    if start_span is None:
        return False
    return find_span(page_text[start_span[1]:], end) is not None


def make_text_fragment(quote_text):
    """Build a `text=...` Text Fragment directive from an exact quote string.

    Browser support is near-universal on current versions (Chrome 80+,
    Edge 83+, Safari 16.1+, Firefox 131+, Opera 67+, Samsung Internet 13+) —
    an unsupporting browser just ignores the directive and loads the page
    normally, so this is pure progressive enhancement.

    Quotes over ~300 chars use the textStart,textEnd form (first/last few
    words) instead of encoding the whole string — matching a very long exact
    string across DOM node boundaries is more fragile, and it keeps the URL
    shorter.

    Quotes containing '...' (editorial truncation) are automatically
    converted to textStart,textEnd form — the text before the ellipsis is
    the start, the text after is the end. This lets editors write 'X... Y'
    as shorthand for 'text starts with X, ends with Y' without being
    verbatim across the omitted middle.
    """
    normalized = normalize_ws(quote_text)
    split = _split_ellipsis(quote_text)
    if split is not None:
        start, end = split
        return "text=" + url_quote(start, safe="") + "," + url_quote(end, safe="")
    words = normalized.split(" ")
    if len(normalized) <= 300:
        return "text=" + url_quote(normalized, safe="")
    start = " ".join(words[:8])
    end = " ".join(words[-8:])
    return "text=" + url_quote(start, safe="") + "," + url_quote(end, safe="")


def add_fragment_to_url(url, quote_text):
    """Return `url` with a #:~:text= directive derived from quote_text
    appended, or None if there's no quote_text to derive one from, or the
    url already carries a fragment (never overwritten). An existing
    non-text anchor (e.g. #section-2) is preserved — a page anchor and a
    text directive can coexist in the same fragment, joined by ':~:' per
    the spec.
    """
    if not quote_text or not url:
        return None
    parsed = urlparse(url)
    if parsed.fragment:
        return None
    directive = make_text_fragment(quote_text)
    return urlunparse(parsed._replace(fragment=f":~:{directive}"))


def with_fragment(url, quote_text):
    """Jinja-filter-friendly wrapper: always returns a usable url — the
    fragment-bearing version when derivable, otherwise the url unchanged."""
    return add_fragment_to_url(url, quote_text) or url


def load_archive_urls():
    """Read the committed evidence cache and return {url: archive_url} for
    every citation that has a recorded Wayback Machine snapshot. Used at
    render time (hooks/org_events.py, hooks/footnote_fragments.py) to add a
    Robust-Links-style archive link alongside the normal citation link —
    see internal-heartbeat/machine-verifiable-citation.md's Open question 5.

    Returns {} if the cache doesn't exist or is unreadable — this must
    never break a build, since archive links are a pure enhancement on top
    of the normal citation url, never a replacement for it.
    """
    try:
        with open(ARCHIVE_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return {}
    return {
        url: entry["archive_url"]
        for url, entry in cache.items()
        if isinstance(entry, dict) and entry.get("archive_url")
    }


def closest_match_hint(page_text, quote_text, min_ratio=0.6):
    """Best-effort fuzzy-diff diagnostic for a MISMATCH report: find the
    passage in page_text that most closely resembles quote_text, using
    stdlib difflib (no new dependency). Returns (passage, ratio) — ratio
    is a 0..1 similarity score — or None if page_text/quote_text is empty
    or nothing clears min_ratio.

    Diagnostic only. This must never be used to decide pass/fail — the
    trust model stays exact-match-only (see quote_matches()); this exists
    purely to make a MISMATCH report actionable ("the page now says X
    instead of Y") instead of just "not found".
    """
    if not page_text or not quote_text:
        return None
    quote_norm = normalize_ws(quote_text)
    page_norm = normalize_ws(page_text)
    matcher = difflib.SequenceMatcher(None, page_norm, quote_norm, autojunk=False)
    match = matcher.find_longest_match(0, len(page_norm), 0, len(quote_norm))
    if match.size == 0:
        return None
    # Expand from the longest common block out to roughly the quote's own
    # length, so the returned passage is comparable in size to what was
    # being searched for rather than just the matched fragment itself.
    target_len = len(quote_norm)
    slack = max(0, target_len - match.size)
    start = max(0, match.a - slack // 2)
    end = min(len(page_norm), start + target_len + slack // 2)
    passage = page_norm[start:end]
    ratio = difflib.SequenceMatcher(None, passage, quote_norm, autojunk=False).ratio()
    if ratio < min_ratio:
        return None
    return passage, ratio


FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
QUOTED_PHRASE_RE = re.compile(r'["“](.+?)["”]')
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def parse_footnote_def(line):
    """Match a footnote-definition line ([^label]: body text...).
    Returns (label, body_text), or None if the line isn't one."""
    m = FOOTNOTE_DEF_RE.match(line)
    return (m.group(1), m.group(2)) if m else None


def footnote_citation(body_text):
    """Extract (url, title, quote) from a footnote's body text IF it
    qualifies for the machine-verifiable quote convention: exactly one
    markdown link, pointing to an absolute http(s) URL, plus exactly one
    quoted phrase found outside that link's own markdown syntax (a page
    title wrapped in quotes as link text, e.g. ["About"](url), is not a
    verbatim excerpt and doesn't count). Returns None otherwise.

    Deliberately the single canonical implementation of this check —
    check_fragments.py (verification), hooks/footnote_fragments.py
    (render-time #:~:text= fragments), and hooks/citation_export.py
    (CSL-JSON export) all call this rather than each re-parsing
    footnotes independently. They used to: three separate
    reimplementations each guessed differently at which quote paired
    with which URL when a footnote cited more than one source, and each
    guessed wrong (one produced a false MISMATCH by checking the wrong
    page, one attached a fragment for text that doesn't exist on the
    linked page, one silently dropped the second citation from the CSL
    export). Requiring exactly one link removes the guess entirely: a
    footnote citing multiple sources is treated as citation-only — no
    quote is extracted for verification, fragment rendering, or export —
    until it's split into separate [^label] footnotes, one citation
    each. See internal-heartbeat/machine-verifiable-citation.md's
    "Footnote citation scope" note for the full reasoning.
    """
    links = MD_LINK_RE.findall(body_text)
    if len(links) != 1:
        return None
    title, url = links[0]
    if not url.startswith(("http://", "https://")):
        return None
    stripped = MD_LINK_RE.sub("", body_text)
    qm = QUOTED_PHRASE_RE.search(stripped)
    if not qm:
        return None
    return url, title, qm.group(1)


def iter_footnote_citations(markdown_source):
    """Yield (label, url, title, quote) for every single-citation,
    verbatim-quoted footnote definition in markdown_source. See
    footnote_citation() for the eligibility rule."""
    for line in markdown_source.split("\n"):
        parsed = parse_footnote_def(line)
        if not parsed:
            continue
        label, body = parsed
        cite = footnote_citation(body)
        if cite:
            url, title, quote = cite
            yield label, url, title, quote
