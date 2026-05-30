#!/usr/bin/env python3
"""
check_concepts.py — Concept slug validator

Two checks:
  1. Org pages whose `concepts:` frontmatter lists slugs that don't match any
     file in docs/concepts/ (typo, stale slug, concept page renamed/deleted).

  2. Concept files that no org page references — possible orphans or naming
     mismatches that mean the concept chip never appears anywhere.

Filtering:
  Pages with a recent `last_checked` date are skipped for check 1 (they were
  presumably verified). Orphan check 2 always runs across all pages.

Usage:
    python util/check_concepts.py              # default: flag pages not checked in 365 days
    python util/check_concepts.py --days 90    # stricter threshold
    python util/check_concepts.py --all        # ignore last_checked, check everything
    python util/check_concepts.py --no-orphans # skip orphan concept check

Requirements: python-frontmatter (util/requirements.txt)
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

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
SKIP_FILES = {"organisations.md", "concepts.md"}


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip('"'))
    except ValueError:
        return None


def days_since(d):
    return (date.today() - d).days if d else None


def load_concept_slugs():
    slugs = set()
    for path in glob.glob(os.path.join(CONCEPTS_DIR, "*.md")):
        slug = os.path.basename(path)[:-3]
        if slug != "concepts":
            slugs.add(slug)
    return slugs


def load_org_pages(threshold_days, ignore_threshold):
    pages = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata
        last_checked = parse_date(meta.get("last_checked"))
        age = days_since(last_checked)
        skip = (not ignore_threshold) and (age is not None) and (age < threshold_days)
        pages.append({
            "path": path,
            "slug": os.path.basename(path)[:-3],
            "title": meta.get("title", os.path.basename(path)[:-3]),
            "status": meta.get("status", "unknown"),
            "concepts": meta.get("concepts") or [],
            "last_checked": last_checked,
            "age": age,
            "skip": skip,
        })
    return pages


def main():
    parser = argparse.ArgumentParser(description="Validate concept slugs in org pages")
    parser.add_argument("--days", type=int, default=365,
                        help="Skip pages checked within this many days (default: 365)")
    parser.add_argument("--all", action="store_true",
                        help="Ignore last_checked, check all pages")
    parser.add_argument("--no-orphans", action="store_true",
                        help="Skip orphaned concept check")
    args = parser.parse_args()

    valid_slugs = load_concept_slugs()
    pages = load_org_pages(args.days, args.all)

    print(f"\n=== Concept slug validation  (threshold: {'all' if args.all else f'{args.days} days'}) ===\n")

    # --- Check 1: invalid slugs on org pages ---
    bad_found = False
    checked = skipped = 0
    for p in pages:
        if p["skip"]:
            skipped += 1
            continue
        checked += 1
        bad = [s for s in p["concepts"] if s not in valid_slugs]
        if bad:
            lc = f"last_checked: {p['last_checked']}" if p["last_checked"] else "never checked"
            print(f"  INVALID SLUG  {p['title']}")
            print(f"    File: {os.path.relpath(p['path'])}")
            print(f"    Bad slugs: {bad}")
            print(f"    ({lc})")
            print()
            bad_found = True

    if not bad_found:
        print(f"  No invalid concept slugs found ({checked} pages checked, {skipped} skipped as recently verified)")
    else:
        print(f"  ({checked} pages checked, {skipped} skipped as recently verified)")
    print()

    # --- Check 2: orphaned concept pages (always runs) ---
    if not args.no_orphans:
        all_referenced = set()
        for p in pages:
            all_referenced.update(p["concepts"])

        orphans = sorted(valid_slugs - all_referenced)
        if orphans:
            print(f"ORPHANED concept pages — not referenced by any org's concepts: list ({len(orphans)}):")
            for slug in orphans:
                print(f"  docs/concepts/{slug}.md")
        else:
            print("No orphaned concept pages — all concepts are referenced by at least one org.")
        print()

    print(f"Known concept slugs: {len(valid_slugs)}")
    print(f"Org pages checked: {checked}  |  skipped (recently verified): {skipped}\n")


if __name__ == "__main__":
    main()
