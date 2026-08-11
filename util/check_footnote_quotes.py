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

A footnote "has a quote" if text_fragment.py's footnote_citation() finds
one — the same eligibility rule used by check_fragments.py (verification),
hooks/footnote_fragments.py (render-time #:~:text= fragments), and
hooks/citation_export.py (CSL-JSON export): exactly one markdown link,
plus a quoted phrase found outside that link's own syntax (a page title
wrapped in quotes as link text, e.g. `["About"](url)`, doesn't count — it's
not a verbatim excerpt from the page). A footnote citing more than one
source is counted as citation-only here too, even if it contains a
quoted phrase, since none of the machine-verifiable tooling will act on
it either — see internal-heartbeat/machine-verifiable-citation.md's
"Footnote citation scope" note.

Local/offline — no network calls, not wired into CI or any build gate.

Usage:
    python util/check_footnote_quotes.py             # summary across all docs
    python util/check_footnote_quotes.py --missing    # list footnotes without a quote
    python util/check_footnote_quotes.py --path docs/organisations/g0v.md
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from text_fragment import footnote_citation, parse_footnote_def  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")


def find_footnotes(path):
    """Yield (line_no, label, text) for each footnote definition in a file.
    Footnote definitions are single logical lines in this repo's style —
    no continuation-line footnotes have been observed — so no multi-line
    joining is attempted."""
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            parsed = parse_footnote_def(line)
            if parsed:
                yield i, parsed[0], parsed[1]


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

            if footnote_citation(text) is not None:
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
