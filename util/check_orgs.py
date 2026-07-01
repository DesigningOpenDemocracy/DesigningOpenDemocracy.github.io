#!/usr/bin/env python3
"""
check_orgs.py — Landscape maintenance checker

Scans docs/organisations/*.md and reports which pages are due for a re-check,
ordered by priority: active orgs with no last_checked date first, then oldest
last_checked date first. Inactive/deregistered orgs are listed separately at
the bottom as lower priority.

Usage:
    python util/check_orgs.py              # show all
    python util/check_orgs.py --days 180   # flag pages not checked in 180+ days
    python util/check_orgs.py --active     # active orgs only
    python util/check_orgs.py --since 2026-06-29  # orgs checked on/after this date

--since is useful for compiling the "verified this run" list for a heartbeat
sync post: run it with today's date after stamping orgs to get the title list.

Requirements: python-frontmatter (already in util/requirements.txt)
"""

import argparse
import glob
import os
import sys
from datetime import date, datetime

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)


DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
SKIP_FILES = {"organisations.md"}


def load_orgs():
    orgs = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))):
        filename = os.path.basename(path)
        if filename in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata

        last_checked = meta.get("last_checked")
        if last_checked:
            if isinstance(last_checked, (datetime, date)):
                last_checked = last_checked if isinstance(last_checked, date) else last_checked.date()
            else:
                try:
                    last_checked = date.fromisoformat(str(last_checked).strip('"'))
                except ValueError:
                    last_checked = None

        orgs.append({
            "path": path,
            "slug": filename[:-3],
            "title": meta.get("title", filename[:-3]),
            "status": meta.get("status", "unknown"),
            "type": meta.get("type", ""),
            "country": meta.get("country", ""),
            "last_checked": last_checked,
        })
    return orgs


def days_since(d):
    if d is None:
        return None
    return (date.today() - d).days


def format_row(org):
    lc = org["last_checked"]
    if lc is None:
        age = "never checked"
    else:
        n = days_since(lc)
        age = f"{lc}  ({n}d ago)"

    flag = ""
    if org["status"] == "active" and lc is None:
        flag = " *** MISSING"

    return f"  {org['title']:<45}  {age}{flag}"


def main():
    parser = argparse.ArgumentParser(description="Check which org pages need re-verification")
    parser.add_argument("--days", type=int, default=365,
                        help="Flag pages not checked within this many days (default: 365)")
    parser.add_argument("--active", action="store_true",
                        help="Show active orgs only")
    parser.add_argument("--since", metavar="DATE",
                        help="List orgs checked on/after DATE (YYYY-MM-DD); useful for "
                             "compiling the heartbeat 'verified this run' list")
    args = parser.parse_args()

    orgs = load_orgs()
    today = date.today()

    if args.since:
        try:
            since_date = date.fromisoformat(args.since)
        except ValueError:
            print(f"--since must be YYYY-MM-DD, got: {args.since}")
            sys.exit(1)
        recent = [
            o for o in orgs
            if o["last_checked"] is not None and o["last_checked"] >= since_date
        ]
        recent.sort(key=lambda o: (o["last_checked"], o["title"]), reverse=True)
        print(f"\nOrgs checked since {args.since}  ({len(recent)} total)\n")
        for o in recent:
            lc = o["last_checked"]
            print(f"  {o['title']:<45}  {lc}  {o['status']}")
        print()
        return

    active = [o for o in orgs if o["status"] == "active"]
    inactive = [o for o in orgs if o["status"] != "active"]

    # Sort active: never-checked first, then oldest last_checked
    active_no_date = sorted([o for o in active if o["last_checked"] is None], key=lambda o: o["title"])
    active_dated = sorted([o for o in active if o["last_checked"] is not None], key=lambda o: o["last_checked"])

    # Split dated into stale vs fresh
    stale = [o for o in active_dated if days_since(o["last_checked"]) >= args.days]
    fresh = [o for o in active_dated if days_since(o["last_checked"]) < args.days]

    print(f"\n=== Org Landscape maintenance report  (threshold: {args.days} days) ===\n")

    if active_no_date:
        print(f"ACTIVE — no last_checked date ({len(active_no_date)} pages):")
        for o in active_no_date:
            print(format_row(o))
        print()

    if stale:
        print(f"ACTIVE — stale (>{args.days} days since last check) ({len(stale)} pages):")
        for o in stale:
            print(format_row(o))
        print()

    if fresh:
        print(f"ACTIVE — up to date (<{args.days} days) ({len(fresh)} pages):")
        for o in fresh:
            print(format_row(o))
        print()

    if not args.active and inactive:
        inactive_no_date = sorted([o for o in inactive if o["last_checked"] is None], key=lambda o: o["title"])
        inactive_dated = sorted([o for o in inactive if o["last_checked"] is not None], key=lambda o: o["last_checked"])
        print(f"INACTIVE/DEREGISTERED ({len(inactive)} pages — lower priority):")
        for o in inactive_no_date + inactive_dated:
            print(format_row(o))
        print()

    total_missing = len(active_no_date)
    total_stale = len(stale)
    print(f"Summary: {len(active)} active orgs | {total_missing} missing date | {total_stale} stale | {len(fresh)} fresh")
    print(f"         {len(inactive)} inactive/deregistered orgs\n")


if __name__ == "__main__":
    main()
