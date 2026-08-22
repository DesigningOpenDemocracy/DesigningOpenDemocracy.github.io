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
import html
import json
import os
import re
from urllib.parse import quote as url_quote
from urllib.parse import unquote, urlparse, urlunparse

ARCHIVE_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "data", "event-evidence-cache.json"
)

_BLOCK_TAGS = [
    "p", "div", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "header", "footer", "main", "aside", "nav",
    "figure", "figcaption", "br", "hr",
    "li", "ol", "ul", "dl", "dt", "dd", "table", "tr",
]
_BLOCK_PATTERN = re.compile(
    r"</?(" + "|".join(_BLOCK_TAGS) + r")\b[^>]*>",
    re.IGNORECASE
)
_PARAGRAPH_DELIM = "\x00P\x00"


def html_to_text(raw_html):
    """Convert raw HTML into flat, whitespace-normalised plain text with
    paragraph breaks preserved as blank lines. This is the same extraction
    check_fragments.py's _fetch_page_text() runs on every live fetch, and
    (via util/import_manual_dump.py) on a manually browser-saved snapshot
    of the same kind of page — both paths share this one implementation so
    a quote can't verify against a live fetch and then mismatch against a
    manual dump of the same markup (or vice versa) purely because two
    extractors disagreed on something as basic as tag-stripping.

    <script>/<style> bodies are dropped before tag-stripping — a bare
    <[^>]+> pass only removes the tags themselves, leaving inline
    JSON-LD/page-props payloads in place as "text", which has produced
    false AMBIGUOUS matches in practice (a quote appearing once in visible
    prose and again inside an embedded JSON blob). html.unescape() decodes
    entities (&#8211;, &amp;, &nbsp;, ...) left behind by tag-stripping.
    """
    no_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw_html, flags=re.S | re.I)
    with_paragraphs = _BLOCK_PATTERN.sub(" " + _PARAGRAPH_DELIM + " ", no_scripts)
    no_tags = re.sub(r"<[^>]+>", " ", with_paragraphs)
    text = re.sub(r"\s+", " ", html.unescape(no_tags))
    # An inline tag boundary immediately before punctuation (e.g.
    # "Wright</a>,") becomes "Wright ," above — a space that was never
    # actually rendered. Drop it so tag boundaries never introduce
    # punctuation spacing that didn't exist in the rendered page.
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    text = text.replace(_PARAGRAPH_DELIM, "\n\n").strip()
    return text[:2_000_000]


def normalize_ws(text):
    """Collapse whitespace for forgiving substring matching. Also drops
    whitespace immediately *inside* parentheses: html_to_text()'s handling
    of inline-tag boundaries can insert a space where the rendered page has
    none (confirmed on science.org — `(<i>N</i> = 5734)` extracted as
    '( N = 5734)'), while human-pasted quotes always carry the rendered
    form. The legitimate space *before* an open-paren is left alone."""
    text = re.sub(r"\(\s+", "(", text)
    return re.sub(r"\s+\)", ")", " ".join(text.split()))


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


def load_archive_info():
    """Read the committed evidence cache and return {url: {"archive_url":,
    "url_status":}} for every citation that has a recorded Wayback Machine
    snapshot and/or an explicit url_status. Used at render time
    (hooks/org_events.py, hooks/footnote_fragments.py, hooks/citation_export.py)
    both to add a Robust-Links-style archive link alongside the normal
    citation link, and — once url_status is anything but the implicit
    "live" — to swap which link renders as primary, matching
    Wikipedia's own Help:Citation Style 1 convention (see
    internal-heartbeat/2026-08-22-citation-archival-design-decisions.md).

    url_status is written by check_fragments.py's --set-url-status flag,
    never inferred here — this function only reads what's already
    recorded. Valid stored values: "dead", "unfit". "live" is never
    stored explicitly; its absence from an entry (or the entry itself
    being absent) means live/unset.

    Returns {} if the cache doesn't exist or is unreadable — this must
    never break a build, since archive links are a pure enhancement on top
    of the normal citation url, never a replacement for it.
    """
    try:
        with open(ARCHIVE_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return {}
    result = {}
    for url, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        archive_url = entry.get("archive_url")
        url_status = entry.get("url_status")
        if archive_url or url_status:
            result[url] = {"archive_url": archive_url, "url_status": url_status}
    return result


def load_archive_urls():
    """Back-compat convenience wrapper over load_archive_info(): returns
    just {url: archive_url} for every citation with a recorded snapshot,
    dropping url_status. Prefer load_archive_info() for any caller that
    needs to know liveness, not just whether a backup exists."""
    return {
        url: info["archive_url"]
        for url, info in load_archive_info().items()
        if info.get("archive_url")
    }


def _visible(s):
    """Make whitespace visible in diff output so a missing/extra space
    (the classic em-dash case: page renders '— with', quote has '—with')
    isn't an invisible one-character difference. Only called on already
    whitespace-normalised strings (normalize_ws collapses every unicode
    whitespace char, U+00A0 included, down to a single plain space), so a
    bare space is the only run type worth escaping."""
    return (s.replace(" ", "␣")
             .replace("\t", "→").replace("\n", "␤"))


def _diff_text(a, b):
    """Render the character-level differences between two strings as
    compact -/+ lines (one per differing run, whitespace made visible),
    or '' if they're identical. Built from SequenceMatcher opcodes —
    stdlib only, same as the rest of this module. The runs are the
    unaligned fragments themselves, so the reader sees the exact
    characters to add/remove rather than a whole-line ndiff."""
    lines = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        lines.append("    - " + (_visible(a[i1:i2]) or "∅"))
        lines.append("    + " + (_visible(b[j1:j2]) or "∅"))
    return "\n".join(lines)


def closest_match_hint(page_text, quote_text, min_ratio=0.6):
    """Best-effort fuzzy-diff diagnostic for a MISMATCH report: find the
    passage in page_text that most closely resembles quote_text, using
    stdlib difflib (no new dependency). Returns (passage, ratio, diff) —
    ratio is a 0..1 similarity score and diff is a rendered
    character-level diff of the two (see _diff_text), making a near-miss
    fixable at a glance (em-dash spacing, a stray sentence-terminating
    period, a reworded word) instead of requiring a manual page fetch to
    locate the one-character divergence. Returns None if page_text/
    quote_text is empty or nothing clears min_ratio.

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
    # Anchor the diff on the longest common block itself, with a bounded
    # context on each side, rather than diffing the slack-expanded passage
    # against the whole quote — the two are not aligned to the same start,
    # so the window offset produces a spurious leading insert/delete
    # (confirmed: a near-miss differing only in em-dash spacing rendered a
    # 37-char phantom insertion). Slicing both sides around the same match
    # keeps them aligned; a real divergence sits within the context either
    # side of the block, which is what makes this diagnostic useful.
    context = 80
    a_lo, a_hi = max(0, match.a - context), min(len(page_norm), match.a + match.size + context)
    b_lo, b_hi = max(0, match.b - context), min(len(quote_norm), match.b + match.size + context)
    diff = _diff_text(page_norm[a_lo:a_hi], quote_norm[b_lo:b_hi])
    return passage, ratio, diff


def spacing_autofix(page_text, quote_text):
    """Return the corrected version of quote_text to store, if the ONLY
    differences between it and the page are space-run insertions/deletions
    (the page renders '— with', the pasted quote has '—with') — otherwise
    None. Caller applies the result (writes it into the source file) and
    re-verifies; this function never mutates anything itself.

    Why this class is safe to auto-apply, and the others are not: if the
    only differences are spaces, then the quote's word content is a
    contiguous substring of the page's by construction, so the fix cannot
    alter what the quote claims — it's the same non-semantic-whitespace
    judgment quote_matches() already makes (normalize_ws), just applied to
    the stored text instead of the comparison. Anything else — letters,
    case, punctuation (',', '.', ':' at word boundaries are semantic:
    "stop, thief" != "stop thief"), or the page simply having extra text
    where the quote ends — returns None and stays a MISMATCH for human
    judgment. In particular the 'page continues after the quote' case is
    deliberately NOT auto-fixed: where a quote ends is an editorial choice
    (trim vs. extend) and the extra text is a genuine page-drift signal a
    MISMATCH is supposed to surface, not hide.

    The correction is the page's whitespace-normalized text over the
    quote's span, which is what a browser actually renders (HTML collapses
    whitespace runs), so a stored correction makes both the verification
    and the #:~:text= highlight pass. Refuses (returns None) if the
    corrected text would occur more than once on the page — an ambiguous
    highlight is worth leaving for a human to lengthen, not worth
    auto-creating. Never returns a string identical to the (normalized)
    input, so callers can use 'is not None' as 'something to apply'.
    """
    if not page_text or not quote_text:
        return None
    page_norm = normalize_ws(page_text)
    quote_norm = normalize_ws(quote_text)
    if quote_norm in page_norm:
        return None  # already a verbatim match — nothing to fix
    matcher = difflib.SequenceMatcher(None, page_norm, quote_norm, autojunk=False)
    match = matcher.find_longest_match(0, len(page_norm), 0, len(quote_norm))
    if match.size == 0:
        return None
    # Window covering the whole quote's span on the page, bounded by ~2x
    # quote length plus margin (the quote is a near-substring, so its span
    # can't drift more than a couple of quote-lengths from the anchor).
    margin = len(quote_norm) + 40
    start = max(0, match.a - margin)
    end = min(len(page_norm), match.a + match.size + margin)
    win = page_norm[start:end]
    opcodes = difflib.SequenceMatcher(None, win, quote_norm, autojunk=False).get_opcodes()
    # The page is usually a long document and the quote a short extract, so
    # the opcode list starts and ends with page-only runs (the header before
    # the quote, the body after it). Those are outside the quote's span and
    # must be ignored — only page content that sits BETWEEN quote characters
    # (or is what the quote chars themselves differ from) counts.
    touched = [j2 > j1 for _, _, _, j1, j2 in opcodes]
    first, last = touched.index(True), len(touched) - 1 - touched[::-1].index(True)
    parts = []
    for tag, i1, i2, j1, j2 in opcodes[first:last + 1]:
        if tag == "equal":
            parts.append(quote_norm[j1:j2])
            continue
        a, b = win[i1:i2], quote_norm[j1:j2]
        if a.strip(" ") or b.strip(" "):
            return None  # a real difference — not spacing
        # delete/replace: take the page's space run. insert: a is empty,
        # so appending a drops the quote's stray space. Either way append a.
        parts.append(a)
    corrected = "".join(parts)
    if not corrected or corrected == quote_norm:
        return None
    if corrected not in page_norm:
        return None
    if count_occurrences(page_norm, corrected) > 1:
        return None  # ambiguous — human should lengthen the quote
    return corrected


FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
QUOTED_PHRASE_RE = re.compile(r'["“](.+?)["”]')
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(((?:[^()]|\([^()]*\))+)\)")
UNQUOTED_REASON_RE = re.compile(r"<!--\s*unquoted:\s*([\w-]+):\s*(.+?)\s*-->")


def parse_footnote_def(line):
    """Match a footnote-definition line ([^label]: body text...).
    Returns (label, body_text), or None if the line isn't one."""
    m = FOOTNOTE_DEF_RE.match(line)
    return (m.group(1), m.group(2)) if m else None


def parse_unquoted_reason(body_text):
    """Match a trailing `<!-- unquoted: type: reason -->` annotation on a
    footnote-definition line — the required justification for a footnote
    that cites a source without the machine-verifiable quote: convention
    (see footnote_citation()). Returns (type, reason) or None if absent.

    `type` is deliberately an open vocabulary rather than a hard-coded
    enum, same spirit as ai_assist:/origin: elsewhere in this repo (see
    CLAUDE.md) — check_footnote_quotes.py judges whether `reason` reads
    as a substantive explanation, not whether `type` is from a fixed
    list. Established values in use: legacy (predates this convention,
    not individually reviewed), bot-blocked, paywalled, no-single-sentence,
    multi-source, non-web-source, not-yet-verified.

    Avoid quote characters (\" or “/”) inside the reason text — they can
    be misread as a verbatim excerpt by footnote_citation()'s quote
    regex, which runs over the same line."""
    m = UNQUOTED_REASON_RE.search(body_text)
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
