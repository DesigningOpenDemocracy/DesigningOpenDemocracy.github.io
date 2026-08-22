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
docs/data/event-evidence-cache.json), a second, visible archive-box
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

Two hooks:
  on_page_markdown — parse footnotes, store label→(url, quote) map on page
  on_page_content  — post-process HTML to add fragments + archive links
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import add_fragment_to_url, iter_footnote_citations, load_archive_info  # noqa: E402

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

ROTTED_STATUSES = ("dead", "unfit")


def _parse_footnotes(markdown_source):
    """Return {label: (url, quote_text)} for footnotes that qualify for the
    machine-verifiable quote convention. See text_fragment.py's
    footnote_citation() for the exactly-one-citation eligibility rule —
    a footnote citing more than one source is skipped here entirely
    (citation-only, no fragment), rather than guessing which quote goes
    with which link."""
    return {label: (url, quote) for label, url, title, quote
            in iter_footnote_citations(markdown_source)}


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


def _get_archive_info():
    """Lazily load and cache the archive-info map for the life of the build
    process — the hooks module is imported once per `mkdocs build`, and the
    cache file doesn't change mid-build, so there's no need to re-read it
    per page."""
    global _archive_info_cache
    if _archive_info_cache is None:
        _archive_info_cache = load_archive_info()
    return _archive_info_cache


def on_page_markdown(markdown, page, config, files):
    page._fn_citations = _parse_footnotes(markdown)
    return markdown


def on_page_content(html, page, config, files):
    citations = getattr(page, "_fn_citations", None)
    if not citations:
        return html

    archive_info = _get_archive_info()

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
            while True:
                a_idx = block.find('<a href="', a_start)
                if a_idx == -1:
                    break
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

        result.append(block)
        pos = li_end

    return "".join(result)
