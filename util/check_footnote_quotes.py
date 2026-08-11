#!/usr/bin/env python3
"""
check_footnote_quotes.py — reports how many prose footnote citations carry
a verbatim quoted excerpt, as opposed to a bare title/source/date citation.

This is prep work for extending check_fragments.py's #:~:text= fragment
generation (currently only wired up for events:' quote: field) to prose
footnotes across org pages, blog posts, and concept pages. See
https://github.com/DesigningOpenDemocracy/DesigningOpenDemocracy.github.io/issues/140
for the full scoping — in short, fragment generation needs a quoted string
to work from, and almost no footnote in this repo has one today. This
script measures that gap so it's visible over time, without committing to
a backfill pace or gating anything on it yet (see the CLAUDE.md "Prose
footnote citations" convention).

A footnote "has a quote" if it contains a quote character (straight or
curly) OUTSIDE its markdown link syntax. Markdown link text is
conventionally wrapped in quotes as a page-title citation style
(`["About"](url)`) — that's not a verbatim excerpt from the page, so it's
stripped out before checking, otherwise nearly every footnote would look
like it already qualifies.

Local/offline — no network calls, not wired into CI or any build gate.

Usage:
    python util/check_footnote_quotes.py             # summary across all docs
    python util/check_footnote_quotes.py --missing    # list footnotes without a quote
    python util/check_footnote_quotes.py --path docs/organisations/g0v.md
"""

import argparse
import glob
import os
import re
import sys

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")

FOOTNOTE_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
QUOTE_CHARS = re.compile(r'["“”]')


def has_verbatim_quote(footnote_text):
    """True if a quote char survives once markdown link syntax is stripped —
    i.e. the footnote has quoted text beyond just a title-as-link-text."""
    stripped = MD_LINK_RE.sub("", footnote_text)
    return bool(QUOTE_CHARS.search(stripped))


def find_footnotes(path):
    """Yield (line_no, label, text) for each footnote definition in a file.
    Footnote definitions are single logical lines in this repo's style —
    no continuation-line footnotes have been observed — so no multi-line
    joining is attempted."""
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            m = FOOTNOTE_RE.match(line)
            if m:
                yield i, m.group(1), m.group(2)


def main():
    parser = argparse.ArgumentParser(
        description="Report how many prose footnotes carry a verbatim quoted excerpt"
    )
    parser.add_argument("--path", type=str, help="Check a single file")
    parser.add_argument("--missing", action="store_true",
                        help="List footnotes without a quote (the backlog)")
    args = parser.parse_args()

    if args.path:
        paths = [args.path]
    else:
        paths = sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True))

    total = 0
    with_quote = 0
    by_dir = {}

    for path in paths:
        rel = os.path.relpath(path, os.path.join(DOCS_DIR, ".."))
        for line_no, label, text in find_footnotes(path):
            total += 1
            top_dir = rel.split(os.sep)[1] if rel.startswith("docs" + os.sep) else rel.split(os.sep)[0]
            bucket = by_dir.setdefault(top_dir, {"total": 0, "with_quote": 0})
            bucket["total"] += 1

            if has_verbatim_quote(text):
                with_quote += 1
                bucket["with_quote"] += 1
            elif args.missing:
                print(f"  {rel}:{line_no}  [^{label}]: {text[:100]}")

    print()
    print(f"Footnotes checked: {total}")
    print(f"  with a verbatim quoted excerpt: {with_quote}")
    print(f"  citation-only (title/source/date, no quote): {total - with_quote}")
    if by_dir:
        print()
        print("By directory:")
        for d in sorted(by_dir):
            b = by_dir[d]
            print(f"  {d}: {b['with_quote']}/{b['total']}")

    if not args.missing and total - with_quote:
        print(f"\nRun with --missing to list the {total - with_quote} footnote(s) without a quote.")

    sys.exit(0)


if __name__ == "__main__":
    main()
