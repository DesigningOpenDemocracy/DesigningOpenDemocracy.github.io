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

Two hooks:
  on_page_markdown — parse footnotes, store label→quote map on page
  on_page_content  — post-process HTML to add fragments
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import add_fragment_to_url  # noqa: E402

FOOTNOTE_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
QUOTED_RE = re.compile(r'["\u201c](.+?)["\u201d]')
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

FN_ID_PREFIX = 'id="fn:'
FN_LI = "<li "
LI_CLOSE = "</li>"


def _parse_footnotes(markdown_source):
    """Return {label: quote_text} for footnotes with verbatim quotes.
    Strips markdown link syntax before searching for quoted text,
    matching check_footnote_quotes.py's detection logic: a page-title
    wrapped in quotes inside link text (['Title'](url)) is not a
    verbatim excerpt, so it's excluded."""
    result = {}
    for line in markdown_source.split("\n"):
        m = FOOTNOTE_RE.match(line)
        if not m:
            continue
        label, text = m.group(1), m.group(2)
        stripped = MD_LINK_RE.sub("", text)
        qm = QUOTED_RE.search(stripped)
        lm = MD_LINK_RE.search(text)
        if qm and lm:
            result[label] = qm.group(1)
    return result


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


def on_page_markdown(markdown, page, config, files):
    page._fn_quotes = _parse_footnotes(markdown)
    return markdown


def on_page_content(html, page, config, files):
    quotes = getattr(page, "_fn_quotes", None)
    if not quotes:
        return html

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

        if label in quotes:
            quote = quotes[label]
            a_start = 0
            while True:
                a_idx = block.find('<a href="', a_start)
                if a_idx == -1:
                    break
                href_end = block.find('"', a_idx + len('<a href="'))
                href = block[a_idx + len('<a href="'):href_end]
                new_url = add_fragment_to_url(href, quote)
                if new_url and new_url != href:
                    old_link = '<a href="' + href + '"'
                    new_link = '<a href="' + new_url + '"'
                    block = block[:a_idx] + new_link + block[a_idx + len(old_link):]
                    a_start = a_idx + len(new_link)
                else:
                    a_start = href_end

        result.append(block)
        pos = li_end

    return "".join(result)
