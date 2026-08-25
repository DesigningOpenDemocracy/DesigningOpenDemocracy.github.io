#!/usr/bin/env python3
"""
merge_citation_state.py — merge two divergent copies of docs/data/citation-state.json.

Why this exists: the weekly probe cron (.github/workflows/heartbeat-probes.yml)
spends hours re-verifying citations, commits the result, then rebases onto
whatever `main` has become in the meantime. citation-state.json is a single
machine-generated JSON blob, so any concurrent edit to it collides — and git's
line-based rebase cannot resolve that. Nine of the first ten scheduled runs
died exactly there, discarding the whole run's commit; that is why no citation
in this repo has ever carried an `archive_url` despite the cron passing
--save-to-wayback since day one.

The fix is the same rule check_fragments.py itself follows: **merge, never
rebuild.** Both sides hold real verification work — neither may be dropped
wholesale, so `-X ours` / `-X theirs` / `--force` are all wrong answers here.

Merge semantics, per URL:

  * The union of both sides' URLs.
  * The union of both sides' `evidence` items, keyed by `id`. An item present
    on both sides resolves to whichever was `checked` more recently; a dated
    item beats an undated one, since undated entries predate per-quote
    stamping and are strictly older.
  * URL-level fetch state (`checked`, `etag`, `last_modified`,
    `document_sha256`, `blocked`, `blocked_since`) is taken as a *unit* from
    whichever side has the newer URL-level `checked`. Taken as a unit
    deliberately: an etag belongs to the body whose hash sits beside it, and
    mixing them across sides would produce a validator that doesn't match its
    own document. A cleared `blocked` on the newer side is a real signal (the
    site started answering again), so the newer side simply wins.
  * Additive/human-owned fields (`archive_url`, `archive_checked`,
    `url_status`, `manual_checked`) survive from either side rather than
    riding on the fetch-state winner — an archive snapshot recorded by one
    run must not be dropped because the other side fetched more recently.

`url_status` is the one field a human sets by hand (check_fragments.py
--set-url-status), so a genuine disagreement between the two sides is never
resolved silently: it is reported on stderr and the newer side's value kept,
so the log shows a human what to look at.

Usage:
    python util/merge_citation_state.py OURS.json THEIRS.json --out MERGED.json
    python util/merge_citation_state.py OURS.json THEIRS.json          # to stdout
    python util/merge_citation_state.py OURS.json THEIRS.json --check  # report, write nothing
"""

import argparse
import json
import sys

# Written together by one fetch; see the module docstring on why these move
# as a unit rather than field-by-field.
FETCH_STATE_FIELDS = ("checked", "etag", "last_modified", "document_sha256",
                      "content_hash", "blocked", "blocked_since")

# Recorded independently of any single fetch, so they survive from either side.
ADDITIVE_FIELDS = ("archive_url", "archive_checked", "url_status", "manual_checked")

# Set by hand only — a real disagreement here is reported, never silently dropped.
HUMAN_FIELDS = ("url_status",)


def _newer(a, b):
    """True if ISO date string `a` is strictly newer than `b`. A present date
    beats a missing one; two missing dates are not newer than each other."""
    if not a:
        return False
    if not b:
        return True
    return a > b


def merge_evidence(ours, theirs, warn):
    """Union two evidence lists by `id`, newest `checked` winning a collision."""
    merged = {}
    order = []
    for side in (ours or [], theirs or []):
        for item in side:
            if not isinstance(item, dict):
                continue
            key = item.get("id")
            if key is None:
                continue
            if key not in merged:
                merged[key] = item
                order.append(key)
            elif _newer(item.get("checked"), merged[key].get("checked")):
                merged[key] = item
    return [merged[k] for k in order]


def merge_entry(url, ours, theirs, warn):
    """Merge one URL's entry. See the module docstring for the field rules."""
    ours = ours or {}
    theirs = theirs or {}

    for field in HUMAN_FIELDS:
        a, b = ours.get(field), theirs.get(field)
        if a and b and a != b:
            warn("%s: %s differs between sides (%r vs %r) — keeping the newer "
                 "side's value; a human set this, so confirm it" % (url, field, a, b))

    fresher = theirs if _newer(theirs.get("checked"), ours.get("checked")) else ours
    staler = ours if fresher is theirs else theirs

    out = {k: v for k, v in fresher.items()
           if k not in ("evidence",) + ADDITIVE_FIELDS}
    for field in FETCH_STATE_FIELDS:
        out.pop(field, None)
        if field in fresher:
            out[field] = fresher[field]

    for field in ADDITIVE_FIELDS:
        if field in fresher:
            out[field] = fresher[field]
        elif field in staler:
            out[field] = staler[field]

    evidence = merge_evidence(ours.get("evidence"), theirs.get("evidence"), warn)
    if evidence or "evidence" in ours or "evidence" in theirs:
        out["evidence"] = evidence
    return out


def merge_states(ours, theirs, warn=None):
    """Merge two whole citation-state dicts. Returns (merged, stats)."""
    warn = warn or (lambda msg: print("WARNING: " + msg, file=sys.stderr))
    merged = {}
    for url in sorted(set(ours) | set(theirs)):
        merged[url] = merge_entry(url, ours.get(url), theirs.get(url), warn)

    def _count(state):
        return sum(len(v.get("evidence") or []) for v in state.values())

    stats = {
        "urls_ours": len(ours), "urls_theirs": len(theirs), "urls_merged": len(merged),
        "evidence_ours": _count(ours), "evidence_theirs": _count(theirs),
        "evidence_merged": _count(merged),
    }
    return merged, stats


def main():
    parser = argparse.ArgumentParser(
        description="Merge two divergent citation-state.json copies without "
                    "dropping either side's verification work")
    parser.add_argument("ours", help="One side (during a rebase: git show :2:<path>)")
    parser.add_argument("theirs", help="The other side (during a rebase: git show :3:<path>)")
    parser.add_argument("--out", metavar="FILE",
                        help="Write merged JSON here (default: stdout)")
    parser.add_argument("--check", action="store_true",
                        help="Report what the merge would do and write nothing")
    args = parser.parse_args()

    with open(args.ours, encoding="utf-8") as f:
        ours = json.load(f)
    with open(args.theirs, encoding="utf-8") as f:
        theirs = json.load(f)

    merged, stats = merge_states(ours, theirs)

    print("citation-state merge: URLs %d + %d -> %d | evidence %d + %d -> %d"
          % (stats["urls_ours"], stats["urls_theirs"], stats["urls_merged"],
             stats["evidence_ours"], stats["evidence_theirs"], stats["evidence_merged"]),
          file=sys.stderr)

    # The whole point is that neither side loses work — assert it rather than
    # trusting the logic above, since a silent drop here is exactly the class
    # of bug this file was written to prevent.
    lost = max(stats["evidence_ours"], stats["evidence_theirs"]) - stats["evidence_merged"]
    if lost > 0:
        print("ERROR: merge would drop %d evidence item(s) — refusing" % lost,
              file=sys.stderr)
        return 1

    if args.check:
        return 0
    payload = json.dumps(merged, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
