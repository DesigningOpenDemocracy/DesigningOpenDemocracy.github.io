"""
footnote_fragments.py — MkDocs hooks that derive #:~:text=
browser-highlight fragments for prose footnote citations, the same
way hooks/org_events.py does for event quote: fields.

A footnote with a verbatim quoted excerpt (per the CLAUDE.md prose
footnote convention):

    [^label]: "quoted phrase," [Title](url), Source.

gets its rendered <a href="url"> link augmented with a #:~:text=
directive — purely progressive enhancement at render time, never
stored in the markdown. The same text_fragment.py module is used.

If a Wayback Machine snapshot for that same url has been recorded
(via `util/check_fragments.py --save-to-wayback`, cached in
docs/data/citation-state.json), a second, visible archive-box
link is added right after the citation link — in addition to it, not
replacing it — pointing at the archived copy as a Robust-Links-style
fallback. See util/text_fragment.py's load_archive_info().

If that same URL also has an explicit url_status of "dead" or "unfit"
(set by `util/check_fragments.py --set-url-status`, never inferred),
the citation link itself is swapped to point at the archived copy
instead — matching Wikipedia's own Help:Citation Style 1 convention of
linking the archive as primary once the original is known bad — and the
original is demoted to a small "(original: no longer live)" trailer
rather than getting a #:~:text= fragment nobody can safely follow. See
internal-heartbeat/2026-08-22-citation-archival-design-decisions.md.

Two more badges, added 2026-08-24 as the prose-footnote counterpart of
organisation.html's event proof_level pills — see the "traffic lights"
discussion this was designed in:

- A citation-only footnote (no verbatim quote — see text_fragment.py's
  footnote_citation() eligibility rule, and the CLAUDE.md "Prose footnote
  citations" convention) gets a neutral grey "Citation only" badge. This
  is NOT a fourth confidence tier alongside high/medium/low — footnotes
  don't have a computed proof_level the way org events do — it's a
  distinct "off" state meaning "nothing to mechanically check here,"
  parallel to how a grey CI badge means "not run," not "failing."
- A quoted footnote whose stored verification verdict (in
  docs/data/citation-state.json, written by check_fragments.py) is a
  MISMATCH gets a red "⚠ Quote drifted" warning — the same visual
  language as organisation.html's existing proof_warning/url_status
  warnings. This is new coverage, not a rename: until now a MISMATCH was
  only ever visible in the weekly cron log, never on the live site, for
  footnotes or events alike. A citation never checked yet (no verdict on
  file) gets neither badge — "not yet verified" is not a warning.

These two are deliberately separate signals, not one three-state badge:
sourcing shape (is there a quote at all) and live accuracy (does the
page still say it) can move independently — a citation-only footnote is
never "wrong," just unrated, and a quoted footnote can drift to MISMATCH
regardless of how strong its sourcing looked at authoring time.

Four hooks:
  on_page_markdown — parse footnotes, store label→(url, quote) map and
                      citation-only label set on page
  on_page_content  — post-process HTML to add fragments, archive links,
                      and the two badges above
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import (  # noqa: E402
    add_fragment_to_url, find_evidence, iter_footnote_citations,
    load_archive_info, load_state, normalize_ws, parse_footnote_def,
)

FN_ID_PREFIX = 'id="fn:'
FN_LI = "<li "
LI_CLOSE = "</li>"

ARCHIVE_LINK_TEMPLATE = (
    ' <a href="{url}" target="_blank" rel="noopener" class="org-event-archive-btn"'
    ' title="Archived snapshot (Wayback Machine)">🗃️</a>'
)

ORIGINAL_DEAD_TEMPLATE = (
    ' <span class="org-event-source-cited">(original, no longer live: '
    '<a href="{url}" target="_blank" rel="noopener">{url}</a>)</span>'
)

CITATION_ONLY_BADGE = (
    ' <span class="org-event-proof proof-citation" '
    'title="No verbatim quote to mechanically verify — see the citation itself.">'
    'Citation only</span>'
)

MISMATCH_WARNING_BADGE = (
    ' <span class="org-event-warning" '
    'title="The stored quote no longer matches the live page as of the last check — needs a recheck.">'
    '⚠ Quote drifted</span>'
)

ROTTED_STATUSES = ("dead", "unfit")


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quote_drifted(state, url, quote):
    """True only if this quote's most recently recorded verification (in
    docs/data/citation-state.json) came back negative. Automated
    'verified' takes precedence over 'manual_verified' when both are
    present, same as hooks/citation_export.py's _verification_for() —
    a fresh automated recheck should win over a stale manual one.
    Returns False (no warning) when nothing has ever been recorded for
    this quote — "not yet checked" is not the same claim as "checked and
    wrong."""
    entry = state.get(url) or {}
    ev = find_evidence(entry, _sha256(normalize_ws(quote))) or {}
    if "verified" in ev:
        return ev["verified"] is False
    if "manual_verified" in ev:
        return ev["manual_verified"] is False
    return False


def _first_link_end(block):
    """Return the block index right after the first <a href="...">...</a>
    closes, or None if no link is found (shouldn't happen for a footnote
    definition, but this is post-processing of already-rendered HTML —
    fail quiet rather than crash the build over a malformed block)."""
    a_idx = block.find('<a href="')
    if a_idx == -1:
        return None
    tag_close = block.find(">", a_idx)
    if tag_close == -1:
        return None
    a_close = block.find("</a>", tag_close)
    if a_close == -1:
        return None
    return a_close + len("</a>")


def _parse_footnotes(markdown_source):
    """Return (citations, citation_only):

    citations — {label: (url, quote_text)} for footnotes that qualify for
    the machine-verifiable quote convention. See text_fragment.py's
    footnote_citation() for the exactly-one-citation eligibility rule —
    a footnote citing more than one source is citation-only here too
    (see below), rather than guessing which quote goes with which link.

    citation_only — the set of every other footnote-definition label on
    the page: no quote to check, fragment, or drift-warn — badged grey
    instead (see CITATION_ONLY_BADGE)."""
    citations = {label: (url, quote) for label, url, title, quote
                 in iter_footnote_citations(markdown_source)}
    citation_only = set()
    for line in markdown_source.split("\n"):
        parsed = parse_footnote_def(line)
        if parsed and parsed[0] not in citations:
            citation_only.add(parsed[0])
    return citations, citation_only


def _find_li_end(html, start):
    """Find the </li> that closes the <li> starting at 'start'.
    Tracks nesting depth to handle bulleted lists inside footnotes."""
    depth = 1
    pos = start
    while depth > 0 and pos < len(html):
        next_open = html.find(FN_LI, pos)
        next_close = html.find(LI_CLOSE, pos)

        if next_open == -1:
            next_open = len(html) + 1
        if next_close == -1:
            next_close = len(html) + 1

        if next_close < next_open:
            depth -= 1
            pos = next_close + len(LI_CLOSE)
        elif next_open < next_close:
            depth += 1
            pos = next_open + len(FN_LI)
        else:
            break

    return pos - len(LI_CLOSE)  # position of the closing </li>


_archive_info_cache = None
_state_cache = None


def _get_archive_info():
    """Lazily load and cache the archive-info map for the life of the build
    process — the hooks module is imported once per `mkdocs build`, and the
    cache file doesn't change mid-build, so there's no need to re-read it
    per page."""
    global _archive_info_cache
    if _archive_info_cache is None:
        _archive_info_cache = load_archive_info()
    return _archive_info_cache


def _get_state():
    """Lazily load and cache the raw citation-state.json map (unlike
    _get_archive_info(), the full per-URL entries, needed here for
    per-quote 'verified'/'manual_verified' lookups via find_evidence())."""
    global _state_cache
    if _state_cache is None:
        _state_cache = load_state()
    return _state_cache


def on_page_markdown(markdown, page, config, files):
    citations, citation_only = _parse_footnotes(markdown)
    page._fn_citations = citations
    page._fn_citation_only = citation_only
    return markdown


def on_page_content(html, page, config, files):
    citations = getattr(page, "_fn_citations", None)
    citation_only = getattr(page, "_fn_citation_only", None)
    if not citations and not citation_only:
        return html

    archive_info = _get_archive_info()
    state = _get_state()

    result = []
    pos = 0
    while True:
        idx = html.find(FN_ID_PREFIX, pos)
        if idx == -1:
            result.append(html[pos:])
            break

        li_start = idx - len("<li ")  # back up to <li  start
        if li_start < 0 or html[li_start:li_start + len(FN_LI)] != FN_LI:
            result.append(html[pos:idx + len(FN_ID_PREFIX)])
            pos = idx + len(FN_ID_PREFIX)
            continue

        result.append(html[pos:li_start])

        end_attr = html.find(">", idx)
        label = html[idx + len(FN_ID_PREFIX):end_attr].rstrip('"')

        li_end = _find_li_end(html, li_start + len(FN_LI))
        block = html[li_start:li_end]

        if label in citations:
            url, quote = citations[label]
            a_start = 0
            link_found = False
            while True:
                a_idx = block.find('<a href="', a_start)
                if a_idx == -1:
                    break
                link_found = True
                href_attr_start = a_idx + len('<a href="')
                href_end = block.find('"', href_attr_start)
                href = block[href_attr_start:href_end]

                # href is the citation's raw url (never the fragment-bearing
                # one at this point — markdown rendering doesn't add
                # fragments itself), so it's exactly the key
                # load_archive_info() stores.
                info = archive_info.get(href) or {}
                archive_url = info.get("archive_url")
                is_rotted = info.get("url_status") in ROTTED_STATUSES and archive_url

                primary_target = archive_url if is_rotted else href
                new_url = add_fragment_to_url(primary_target, quote)
                display_url = new_url or primary_target
                if display_url != href:
                    old_link = '<a href="' + href + '"'
                    new_link = '<a href="' + display_url + '"'
                    block = block[:a_idx] + new_link + block[a_idx + len(old_link):]
                    href_end += len(new_link) - len(old_link)

                tag_close = block.find(">", href_end)
                a_close = block.find("</a>", tag_close)
                if a_close == -1:
                    a_start = href_end
                    continue

                insert_at = a_close + len("</a>")
                if is_rotted:
                    # Archive is now the primary, clickable link (above);
                    # the original is demoted to plain, clearly-labeled
                    # text rather than a second live link, since it's
                    # known not to resolve (or to resolve to junk).
                    trailer = ORIGINAL_DEAD_TEMPLATE.format(url=href)
                    block = block[:insert_at] + trailer + block[insert_at:]
                    a_start = insert_at + len(trailer)
                elif archive_url:
                    # Original still primary; archive is a pure additive
                    # Robust-Links-style fallback next to it.
                    archive_link = ARCHIVE_LINK_TEMPLATE.format(url=archive_url)
                    block = block[:insert_at] + archive_link + block[insert_at:]
                    a_start = insert_at + len(archive_link)
                else:
                    a_start = insert_at

            if link_found and _quote_drifted(state, url, quote):
                block = block[:a_start] + MISMATCH_WARNING_BADGE + block[a_start:]
        elif citation_only and label in citation_only:
            insert_at = _first_link_end(block)
            if insert_at is not None:
                block = block[:insert_at] + CITATION_ONLY_BADGE + block[insert_at:]

        result.append(block)
        pos = li_end

    return "".join(result)
