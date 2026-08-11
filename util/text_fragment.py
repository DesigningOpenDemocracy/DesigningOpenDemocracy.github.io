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

import re
from urllib.parse import quote as url_quote
from urllib.parse import unquote, urlparse, urlunparse


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
    """
    normalized = normalize_ws(quote_text)
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
