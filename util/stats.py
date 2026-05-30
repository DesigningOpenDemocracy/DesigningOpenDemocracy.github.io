#!/usr/bin/env python3
"""
stats.py — Democracy Landscape snapshot

Quick situational overview: org counts, geographic spread, type breakdown,
last_checked freshness, and concept coverage. Run at the start of a
maintenance session to understand the current state of the wiki.

Usage:
    python util/stats.py
    python util/stats.py --concepts   # include orphaned concept list

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import os
import sys
from collections import Counter
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
TODAY = date.today()


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip('"'))
    except ValueError:
        return None


def load_orgs():
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        lc = parse_date(m.get("last_checked"))
        orgs.append({
            "title": m.get("title", os.path.basename(path)[:-3]),
            "status": m.get("status", "unknown"),
            "type": m.get("type", "unknown"),
            "country": m.get("country", "??"),
            "concepts": m.get("concepts") or [],
            "last_checked": lc,
            "age_days": (TODAY - lc).days if lc else None,
        })
    return orgs


def load_concept_slugs():
    slugs = set()
    for path in glob.glob(os.path.join(CONCEPTS_DIR, "*.md")):
        slug = os.path.basename(path)[:-3]
        if slug != "concepts":
            slugs.add(slug)
    return slugs


def bar(n, total, width=18):
    if not total:
        return "░" * width
    filled = round(width * n / total)
    return "█" * filled + "░" * (width - filled)


def main():
    parser = argparse.ArgumentParser(description="Democracy Landscape snapshot")
    parser.add_argument("--concepts", action="store_true",
                        help="List orphaned concept pages")
    args = parser.parse_args()

    orgs = load_orgs()
    concept_slugs = load_concept_slugs()
    total = len(orgs)

    W = 56
    print(f"\n{'═' * W}")
    print(f"  Democracy Landscape  —  {TODAY}")
    print(f"{'═' * W}\n")

    # --- Status breakdown ---
    status_counts = Counter(o["status"] for o in orgs)
    print(f"Orgs  ({total} total)")
    for s in ("active", "inactive", "deregistered", "unknown"):
        n = status_counts.get(s, 0)
        if n:
            print(f"  {s:<14} {n:>4}  {bar(n, total)}")
    print()

    # --- Country breakdown (active) ---
    active = [o for o in orgs if o["status"] == "active"]
    country_counts = Counter(o["country"] for o in active)
    print(f"Active orgs by country  ({len(active)} total)")
    for country, n in country_counts.most_common(12):
        print(f"  {country:<6} {n:>4}  {bar(n, len(active), 14)}")
    print()

    # --- Type breakdown (active) ---
    type_counts = Counter(o["type"] for o in active)
    print(f"Active orgs by type")
    for t, n in type_counts.most_common():
        print(f"  {t:<22} {n:>4}")
    print()

    # --- Freshness ---
    checked = [o for o in orgs if o["age_days"] is not None]
    never = [o for o in orgs if o["age_days"] is None]
    active_never = [o for o in never if o["status"] == "active"]

    print(f"Freshness  (last_checked)")
    print(f"  Never checked:      {len(never):>4}  ({len(active_never)} active)")
    if checked:
        buckets = [
            (0,   30,  "< 30 days"),
            (30,  90,  "30–90 days"),
            (90,  180, "90–180 days"),
            (180, 365, "180–365 days"),
            (365, None, "> 365 days"),
        ]
        for lo, hi, label in buckets:
            if hi is None:
                n = sum(1 for o in checked if o["age_days"] >= lo)
            else:
                n = sum(1 for o in checked if lo <= o["age_days"] < hi)
            if n:
                print(f"  {label:<16}  {n:>4}")
    print()

    # --- Concept coverage ---
    all_referenced = set()
    for o in orgs:
        all_referenced.update(o["concepts"])
    orphans = sorted(concept_slugs - all_referenced)

    concept_ref_counts = Counter()
    for o in orgs:
        for c in o["concepts"]:
            concept_ref_counts[c] += 1

    orgs_with_concepts = sum(1 for o in orgs if o["concepts"])

    print(f"Concepts  ({len(concept_slugs)} pages)")
    print(f"  Referenced by ≥1 org:   {len(all_referenced & concept_slugs):>4}")
    print(f"  Orphaned (no org ref):  {len(orphans):>4}")
    print(f"  Orgs with concepts:     {orgs_with_concepts:>4} / {total}")
    print()

    print(f"Most referenced concepts  (top 10)")
    for slug, n in concept_ref_counts.most_common(10):
        print(f"  {slug:<36} {n:>4}")
    print()

    if args.concepts and orphans:
        print(f"Orphaned concept pages  ({len(orphans)}):")
        for slug in orphans:
            print(f"  docs/concepts/{slug}.md")
        print()

    print(f"{'═' * W}\n")


if __name__ == "__main__":
    main()
