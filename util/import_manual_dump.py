#!/usr/bin/env python3
"""
import_manual_dump.py — turn a human-saved browser snapshot into a
manual_verified cache entry, for citation URLs no automated fetch can
reach (bot-blocked, rate-limited, robots.txt-disallowed) but a human's own
browser still can. See util/manual_dump.py's docstring for the full
workflow and why this exists as a local, gitignored escape hatch rather
than something CI or the weekly cron ever runs.

For each manual-dump/snapshots/*.html file:
  1. Recover the source URL from the browser's leading
     '<!-- saved from url=(NNNN)https://... -->' comment.
  2. Extract plain text with text_fragment.html_to_text() — the exact same
     extraction a live fetch uses (see check_fragments.py's
     _fetch_page_text), so a quote verifies identically either way.
  3. Check every piece of evidence (event/footnote/shared-link quotes)
     that cites this URL against the extracted text, and record each
     result in the shared evidence cache as manual_verified[hash] = bool.
  4. Remove the URL from manual-dump/requests.txt and move the snapshot
     into manual-dump/snapshots/imported/, so a re-run doesn't reprocess
     it.

manual_verified is deliberately a separate field from the automated
verified map, not merged into it — stale automated data captured before a
site started blocking scripts must never be silently presented as if it
were reconfirmed just because a human happened to import an unrelated
snapshot later. Only entries this script itself writes go in
manual_verified.

A snapshot whose URL doesn't match any known citation is left in place
(not moved) and reported, since that's more likely a mistake (wrong page
saved, or the citation was since removed) than something to silently
discard.

Usage:
    python util/import_manual_dump.py             # import every pending snapshot
    python util/import_manual_dump.py --dry-run    # report what would happen, write nothing

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import os
import shutil
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(__file__))
import manual_dump  # noqa: E402
from check_fragments import (  # noqa: E402
    CACHE_PATH, collect_evidence, context_for_quote, load_cache, save_cache, sha256,
)
from text_fragment import html_to_text, normalize_ws, quote_matches  # noqa: E402


def import_snapshot(path, cache, evidence_by_url, dry_run=False):
    """Import one saved-HTML file. Returns True if it was matched to at
    least one citation (and, unless dry_run, imported), False otherwise."""
    with open(path, encoding="utf-8", errors="replace") as f:
        raw_html = f.read()

    url = manual_dump.parse_saved_from_url(raw_html)
    if not url:
        print("  SKIPPED  " + os.path.basename(path) +
              "  (no 'saved from url=' comment found — not a browser-saved file?)")
        return False

    items = evidence_by_url.get(url)
    if not items:
        print("  NO MATCH  " + os.path.basename(path))
        print("            url: " + url)
        print("            (no citation in the wiki currently points at this URL)")
        return False

    text = html_to_text(raw_html)
    if not text:
        print("  EMPTY  " + os.path.basename(path) + "  (" + url + ") — extracted no text, skipped")
        return False

    entry = cache.get(url, {})
    manual_verified = dict(entry.get("manual_verified", {}))
    contexts = dict(entry.get("contexts", {}))
    good = bad = 0
    for evidence, source_label, kind in items:
        ev_key = sha256(normalize_ws(evidence))
        result = quote_matches(text, evidence)
        manual_verified[ev_key] = result
        if result:
            good += 1
            ctx = context_for_quote(text, evidence)
            if ctx:
                contexts[ev_key] = ctx
        else:
            bad += 1
        print(("  MANUAL GOOD  " if result else "  MANUAL MISMATCH  ") + source_label)

    print("  IMPORTED  " + os.path.basename(path) + "  (" + url + ") — " +
          str(good) + " good, " + str(bad) + " mismatch")

    if dry_run:
        return True

    cache[url] = {**entry, "manual_verified": manual_verified,
                  "manual_checked": date.today().isoformat(), "contexts": contexts}
    manual_dump.dequeue_request(url)

    os.makedirs(manual_dump.IMPORTED_DIR, exist_ok=True)
    dest = os.path.join(manual_dump.IMPORTED_DIR, os.path.basename(path))
    if os.path.exists(dest):
        stem, ext = os.path.splitext(dest)
        dest = stem + "-" + date.today().isoformat() + ext
    shutil.move(path, dest)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Import human-saved browser snapshots from manual-dump/snapshots/ "
                    "into the evidence cache as manual_verified entries.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be imported without writing the cache "
                            "or moving/removing any files.")
    args = parser.parse_args()

    snapshots = sorted(glob.glob(os.path.join(manual_dump.SNAPSHOTS_DIR, "*.html")))
    if not snapshots:
        print("No snapshots found in " + manual_dump.SNAPSHOTS_DIR)
        return

    fake_args = SimpleNamespace(slug=None, events_only=False)
    evidence_by_url = {}
    for url, evidence, source_label, kind, _path in collect_evidence(fake_args):
        evidence_by_url.setdefault(url, []).append((evidence, source_label, kind))

    cache = load_cache()
    imported = 0
    for path in snapshots:
        if import_snapshot(path, cache, evidence_by_url, dry_run=args.dry_run):
            imported += 1

    if not args.dry_run:
        save_cache(cache)

    print()
    print(str(imported) + " of " + str(len(snapshots)) + " snapshot(s) imported" +
          (" (dry run — nothing written)" if args.dry_run else ""))
    print("Cache: " + CACHE_PATH)


if __name__ == "__main__":
    main()
