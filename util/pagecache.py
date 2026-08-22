#!/usr/bin/env python3
"""
pagecache.py — local reading copies of citation pages, captured at fetch time.

Every full page body that check_fragments.py fetches (live HTML, extracted
PDF text, Wikipedia API extracts) is written through to .pagecache/ —
gitignored local working state, same spirit as manual-dump/ but for the
opposite problem: manual-dump/ exists for pages no automated fetch can reach
(a human saves them from a real browser instead); this stores pages that
automated fetches DO reach, so a later session (human or AI assistant) can
read what a cited page said without pinging the origin site again.

Deliberately one-directional: stored copies never feed back into
verification. check_evidence() keeps its own freshness machinery (conditional
GET, sticky-blocked cache), so a stale local copy can't mask real page drift
with an old verdict. Readers should treat each copy's "checked" date as "last
confirmed", not "current" — `check_fragments.py --no-cache` forces a full
refetch and overwrites every copy it touches along the way.

Layout: index.json maps <sha256(url)[0:16]> keys to {url, file, checked,
sha256, chars} records; page text lives in sibling flat .txt files named by
the same key. Plain files on purpose — greppable/globbable by any tool with
no lock-in to this module. The CLI below is a thin convenience over them:

    python util/pagecache.py list               # cached pages, newest first
    python util/pagecache.py show <substr>      # print matching pages' text
    python util/pagecache.py path <substr>      # print matching file paths

Requirements: none (stdlib only)
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import date

PAGECACHE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".pagecache"))
INDEX_PATH = os.path.join(PAGECACHE_DIR, "index.json")

# Callers that must never leave local artifacts flip this off (the weekly CI
# cron passes --no-page-cache to check_fragments.py); store() becomes a no-op.
enabled = True


def key_for(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def path_for(url):
    return os.path.join(PAGECACHE_DIR, key_for(url) + ".txt")


def load_index():
    try:
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
        return index if isinstance(index, dict) else {}
    except (OSError, ValueError):
        # Missing, unreadable, or hand-mangled index: start over rather than
        # fail — the .txt files are the data; the index is just their catalog.
        return {}


def save_index(index):
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, sort_keys=True)


def get(url):
    """Return (text, meta) for url's stored copy, or None if absent."""
    meta = load_index().get(key_for(url))
    if not meta:
        return None
    try:
        with open(os.path.join(PAGECACHE_DIR, meta["file"]), encoding="utf-8") as f:
            return f.read(), meta
    except OSError:
        return None


def store(url, text):
    """Write-through capture of one successfully fetched page's text.

    Best-effort by design: a full disk or read-only checkout should degrade
    to "no local copy" with a warning, never break a verification run that
    was doing fine before this feature existed.
    """
    if not enabled or not text:
        return
    try:
        os.makedirs(PAGECACHE_DIR, exist_ok=True)
        fname = key_for(url) + ".txt"
        with open(os.path.join(PAGECACHE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(text)
        index = load_index()
        index[key_for(url)] = {
            "url": url,
            "file": fname,
            "checked": date.today().isoformat(),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "chars": len(text),
        }
        save_index(index)
    except OSError as e:
        print(f"pagecache: write failed ({e}); continuing without it", file=sys.stderr)


def matching_entries(substr):
    """Index entries whose URL contains substr, newest-checked first."""
    entries = [e for e in load_index().values() if substr.lower() in e["url"].lower()]
    return sorted(entries, key=lambda e: e["checked"], reverse=True)


def main():
    parser = argparse.ArgumentParser(
        description="Read .pagecache/ — locally cached copies of cited pages "
                    "(written by util/check_fragments.py at fetch time)")
    parser.add_argument("command", nargs="?", default="list",
                        choices=["list", "show", "path"],
                        help="list (default) | show <substr> | path <substr>")
    parser.add_argument("substr", nargs="?", default="",
                        help="case-insensitive substring of the citation URL")
    args = parser.parse_args()
    entries = matching_entries(args.substr)
    if args.command == "path":
        for e in entries:
            print(os.path.join(PAGECACHE_DIR, e["file"]))
        return
    for e in entries:
        label = e["url"]
        if args.command == "path":
            continue
        if args.command == "list":
            print(f"{e['checked']}  {e['chars']:>7}  {label}")
            continue
        print("=" * 78)
        print(f"{label}   (checked {e['checked']})")
        print("=" * 78)
        try:
            with open(os.path.join(PAGECACHE_DIR, e["file"]), encoding="utf-8") as f:
                sys.stdout.write(f.read())
            print()
        except OSError as err:
            print(f"(unreadable: {err})")
    if args.command == "list" and not entries:
        print("No cached pages"
              + (f" matching {args.substr!r}" if args.substr else "")
              + f". Copies appear as check_fragments.py fetches; "
                f"run it with --no-cache to populate everything fresh.")


if __name__ == "__main__":
    main()
