#!/usr/bin/env python3
"""
check_footnote_quotes.py — gates every prose footnote citation on carrying
either a verbatim quoted excerpt, or an explicit justification for why it
doesn't.

Local/offline, no network calls — and, since 2026-08, wired into CI and
the pre-commit hook as a hard gate (see CLAUDE.md's "Prose footnote
citations" convention). This started as a purely informational backlog
tracker (see git history / issue #140 for that phase) but a real incident
made the gap unacceptable to leave ungated: an AI-authored footnote was
left citation-only with no reason recorded — not because the source
resisted quoting, but because the claim was sourced from a summarizing
tool's paraphrase rather than the page's actual text, and that shortcut
was invisible in review. A required justification does not make the
underlying claim correct — a model can misjudge or misstate a reason the
same way it can misstate a quote — but it converts a silent gap into a
reviewable one, which is the realistic ceiling for what a lint step can
enforce here. See internal-heartbeat/ for the incident writeup.

A footnote "has a quote" if text_fragment.py's footnote_citation() finds
one — the same eligibility rule used by check_fragments.py (verification),
hooks/footnote_fragments.py (render-time #:~:text= fragments), and
hooks/citation_export.py (CSL-JSON export): exactly one markdown link,
plus a quoted phrase found outside that link's own syntax. A footnote
citing more than one source is "citation-only" here too, even if it
contains a quoted phrase — see internal-heartbeat/machine-verifiable-citation.md's
"Footnote citation scope" note.

A citation-only footnote passes the gate only if its definition line
carries a trailing `<!-- unquoted: type: reason -->` annotation (see
text_fragment.py's parse_unquoted_reason() for the format and the
established `type` vocabulary — open-ended, same spirit as ai_assist:/
origin: elsewhere in this repo). Two failure tiers, mirroring
check_event_sourcing.py's url:/source: vs note:/quote:/proof_warning:
split:

  MISSING JUSTIFICATION (hard fail, exit 1) — no annotation at all.
  VAGUE JUSTIFICATION (soft warning, printed, does not fail the build)
      — annotation present but the reason is under 15 characters, i.e.
      not really an explanation ("<!-- unquoted: legacy: n/a -->").

Usage:
    python util/check_footnote_quotes.py             # gate: exit 1 if any MISSING JUSTIFICATION
    python util/check_footnote_quotes.py --missing    # also list every citation-only footnote
    python util/check_footnote_quotes.py --path docs/organisations/g0v.md
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from text_fragment import footnote_citation, parse_footnote_def, parse_unquoted_reason  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
MIN_REASON_LEN = 15


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
        description="Gate: every citation-only footnote must carry an unquoted: justification"
    )
    parser.add_argument("--path", type=str, help="Check a single file")
    parser.add_argument("--missing", action="store_true",
                        help="List every citation-only footnote (justified or not)")
    args = parser.parse_args()

    if args.path:
        paths = [args.path]
    else:
        paths = sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True))

    total = 0
    with_quote = 0
    by_dir = {}
    missing_justification = []
    vague_justification = []

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
                continue

            if args.missing:
                print(f"  {rel}:{line_no}  [^{label}]: {text[:100]}")

            reason = parse_unquoted_reason(text)
            if reason is None:
                missing_justification.append((rel, line_no, label))
            elif len(reason[1]) < MIN_REASON_LEN:
                vague_justification.append((rel, line_no, label, reason))

    print()
    print(f"Footnotes checked: {total}")
    print(f"  with a verbatim quoted excerpt: {with_quote}")
    print(f"  citation-only, justified (unquoted: annotation present): "
          f"{total - with_quote - len(missing_justification)}")
    print(f"  citation-only, MISSING JUSTIFICATION: {len(missing_justification)}")
    if by_dir:
        print()
        print("By directory:")
        for d in sorted(by_dir):
            b = by_dir[d]
            print(f"  {d}: {b['with_quote']}/{b['total']}")

    if vague_justification:
        print()
        print(f"VAGUE JUSTIFICATION (reason under {MIN_REASON_LEN} chars — not a build failure, but weak):")
        for rel, line_no, label, (rtype, reason) in vague_justification:
            print(f"  {rel}:{line_no}  [^{label}]: unquoted: {rtype}: {reason!r}")

    if missing_justification:
        print()
        print("MISSING JUSTIFICATION — every citation-only footnote needs a trailing")
        print('  <!-- unquoted: type: reason --> comment. See this script\'s docstring')
        print("  and the CLAUDE.md \"Prose footnote citations\" convention.")
        for rel, line_no, label in missing_justification:
            print(f"  {rel}:{line_no}  [^{label}]")
        print()
        print(f"FAILED: {len(missing_justification)} footnote(s) missing a quote AND a justification.")
        sys.exit(1)

    if not args.missing and total - with_quote:
        print(f"\nRun with --missing to list the {total - with_quote} citation-only footnote(s).")

    sys.exit(0)


if __name__ == "__main__":
    main()
