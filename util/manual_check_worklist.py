#!/usr/bin/env python3
"""
manual_check_worklist.py — generate a plain checklist for a human to verify
citations that check_fragments.py can't verify by itself.

Two categories of "can't verify automatically":

1. BLOCKED (the default, offline mode) — the URL is recorded in
   docs/data/event-evidence-cache.json as having returned 403/429 to a
   scripted request. check_fragments.py deliberately never retries these
   on its own (see that script's docstring on why the block is sticky) —
   the only way past a BLOCKED entry is a human opening the link in a real
   browser, where the network path and browser fingerprint look nothing
   like a script's. This mode makes no network calls; it just reads the
   cache.

2. --live — fetch every not-yet-blocked citation fresh and surface
   anything AMBIGUOUS (the quote occurs more than once on the page, so the
   #:~:text= highlight isn't guaranteed to land on the occurrence the
   citation actually means) or MISMATCH (the quote no longer appears
   verbatim). Ambiguity in particular is never written to the cache (a
   cache hit can't re-derive it — see check_evidence()'s docstring), so
   this is the only way to get a current list of it without re-running
   check_fragments.py itself and reading its console output as it scrolls
   past.

This script is read-only — it never edits a source file or writes
anything back except, with --live, the same evidence cache
check_fragments.py itself updates (so a later check_fragments.py run
doesn't redo the same fetches). It exists purely to hand a human a short,
concrete list of "open this link, search for this text, tell us what you
find" — the fix itself (editing the quote, or leaving it — see
check_fragments.py's --autofix-spaces for the mechanical subset of fixes
that don't need a human at all) still happens by hand afterward.

Usage:
    python util/manual_check_worklist.py                # offline: list BLOCKED citations
    python util/manual_check_worklist.py --live          # also fetch fresh, flag AMBIGUOUS/MISMATCH too
    python util/manual_check_worklist.py --slug radicalxchange
    python util/manual_check_worklist.py --out /tmp/worklist.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import check_fragments as cf  # noqa: E402


def build_worklist(args):
    """Return a list of (status, url, quote, source_label, kind, hint)
    tuples — hint is a closest-match passage string or None."""
    cache = cf.load_cache()
    items = cf.collect_evidence(args)
    if args.footnotes_only:
        items = [i for i in items if i[3] != "event"]

    entries = []
    if args.live:
        for url, quote, source_label, kind, _path in items:
            result, _unchanged, error, ambiguous, hint, _text = cf.check_evidence(
                url, quote, cache, use_cache=not args.no_cache)
            if result == "bad":
                passage = hint[0] if hint else None
                entries.append(("MISMATCH", url, quote, source_label, kind, passage))
            elif ambiguous:
                entries.append(("AMBIGUOUS (quote occurs more than once)",
                                 url, quote, source_label, kind, None))
            elif error:
                entries.append((f"FETCH ERROR ({error})", url, quote,
                                 source_label, kind, None))
        cf.save_cache(cache)
    else:
        for url, quote, source_label, kind, _path in items:
            blocked = cache.get(url, {}).get("blocked")
            if not blocked:
                continue
            since = cache.get(url, {}).get("blocked_since", "?")
            entries.append((f"BLOCKED ({blocked} since {since})",
                             url, quote, source_label, kind, None))

    return entries


def render_markdown(entries):
    if not entries:
        return "Nothing needs a manual check right now.\n"
    lines = [
        "# Manual citation check worklist",
        "",
        f"{len(entries)} item(s) that automated verification can't resolve on "
        "its own — each needs a human to open the URL in a real browser and "
        "confirm whether the quoted text is still there. Ctrl+F / Cmd+F for "
        "the quoted text works well; long quotes may need searching for just "
        "the first several words if the browser's find doesn't match across "
        "line breaks.",
        "",
    ]
    for i, (status, url, quote, source_label, kind, hint) in enumerate(entries, start=1):
        lines.append(f"## {i}. [{kind}] {source_label}")
        lines.append(f"- Status: {status}")
        lines.append(f"- URL: {url}")
        lines.append(f'- Search for (Ctrl+F): "{quote}"')
        if hint:
            lines.append(f'- Closest text found on the page instead: "{hint}"')
        lines.append("- Outcome: [ ] confirmed as quoted &nbsp; [ ] found, wording differs "
                      "&nbsp; [ ] not found &nbsp; [ ] page still unreachable")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a human checklist for citations automated "
                     "verification can't resolve (BLOCKED urls by default, "
                     "or with --live, fresh MISMATCH/AMBIGUOUS findings too).")
    parser.add_argument("--slug", type=str, action="append",
                        help="Limit to one org's events (repeatable: pass "
                             "once per org). Footnotes/shared links across "
                             "the whole site are still included unless "
                             "--events-only is also set.")
    parser.add_argument("--events-only", action="store_true",
                        help="Only consider event evidence")
    parser.add_argument("--footnotes-only", action="store_true",
                        help="Only consider footnote evidence")
    parser.add_argument("--live", action="store_true",
                        help="Fetch every citation fresh instead of just "
                             "reading the cache's BLOCKED entries — slower "
                             "(one request per citation, same rate limit as "
                             "check_fragments.py), but also surfaces current "
                             "AMBIGUOUS and MISMATCH findings.")
    parser.add_argument("--no-cache", action="store_true",
                        help="With --live, ignore cached etag/last-modified "
                             "and re-fetch everything, including URLs "
                             "already confirmed BLOCKED")
    parser.add_argument("--out", type=str, default=None,
                        help="Write the worklist to this file instead of stdout")
    args = parser.parse_args()

    entries = build_worklist(args)
    output = render_markdown(entries)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(entries)} item(s) to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
