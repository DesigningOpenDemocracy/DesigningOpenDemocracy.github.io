#!/usr/bin/env python3
"""
stats.py — Democracy Landscape snapshot

Quick situational overview: org counts, geographic spread, type breakdown,
last_checked freshness, and concept coverage. Run at the start of a
maintenance session to understand the current state of the wiki.

Usage:
    python util/stats.py
    python util/stats.py --concepts          # include orphaned concept list
    python util/stats.py --json              # machine-readable snapshot to stdout
    python util/stats.py --save before.json  # also write snapshot to a file
    python util/stats.py --diff before.json  # compare current state to a saved snapshot

The --save / --diff pair is meant for bracketing a maintenance run: save a
snapshot before starting the staleness queue, then diff against it at the
end to get the before/after numbers a heartbeat commit message needs,
without having to recall or recompute them by hand.

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import json
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

FRESHNESS_BUCKETS = [
    (0,   30,  "< 30 days"),
    (30,  90,  "30–90 days"),
    (90,  180, "90–180 days"),
    (180, 365, "180–365 days"),
    (365, None, "> 365 days"),
]


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


def build_snapshot(orgs, concept_slugs):
    """Compute every metric the report prints, as a flat JSON-able dict.

    This is the single source of truth for both the human report and
    --json/--save/--diff, so the two can never silently disagree.
    """
    total = len(orgs)
    status_counts = Counter(o["status"] for o in orgs)
    active = [o for o in orgs if o["status"] == "active"]
    country_counts = Counter(o["country"] for o in active)
    type_counts = Counter(o["type"] for o in active)

    checked = [o for o in orgs if o["age_days"] is not None]
    never = [o for o in orgs if o["age_days"] is None]
    active_never = [o for o in never if o["status"] == "active"]
    freshness_buckets = {}
    for lo, hi, label in FRESHNESS_BUCKETS:
        if hi is None:
            n = sum(1 for o in checked if o["age_days"] >= lo)
        else:
            n = sum(1 for o in checked if lo <= o["age_days"] < hi)
        freshness_buckets[label] = n

    all_referenced = set()
    for o in orgs:
        all_referenced.update(o["concepts"])
    orphans = sorted(concept_slugs - all_referenced)

    concept_ref_counts = Counter()
    for o in orgs:
        for c in o["concepts"]:
            concept_ref_counts[c] += 1

    orgs_with_concepts = sum(1 for o in orgs if o["concepts"])

    return {
        "date": TODAY.isoformat(),
        "total_orgs": total,
        "status_counts": dict(status_counts),
        "active_orgs": len(active),
        "country_counts": dict(country_counts),
        "type_counts": dict(type_counts),
        "never_checked_total": len(never),
        "never_checked_active": len(active_never),
        "freshness_buckets": freshness_buckets,
        "concept_pages": len(concept_slugs),
        "concepts_referenced": len(all_referenced & concept_slugs),
        "concepts_orphaned": len(orphans),
        "orphaned_concept_slugs": orphans,
        "orgs_with_concepts": orgs_with_concepts,
        "top_concepts": concept_ref_counts.most_common(10),
    }


def print_report(snap, show_orphans):
    W = 56
    print(f"\n{'═' * W}")
    print(f"  Democracy Landscape  —  {snap['date']}")
    print(f"{'═' * W}\n")

    total = snap["total_orgs"]
    print(f"Orgs  ({total} total)")
    for s in ("active", "inactive", "deregistered", "unknown"):
        n = snap["status_counts"].get(s, 0)
        if n:
            print(f"  {s:<14} {n:>4}  {bar(n, total)}")
    print()

    active_total = snap["active_orgs"]
    print(f"Active orgs by country  ({active_total} total)")
    for country, n in Counter(snap["country_counts"]).most_common(12):
        print(f"  {country:<6} {n:>4}  {bar(n, active_total, 14)}")
    print()

    print(f"Active orgs by type")
    for t, n in Counter(snap["type_counts"]).most_common():
        print(f"  {t:<22} {n:>4}")
    print()

    print(f"Freshness  (last_checked)")
    print(f"  Never checked:      {snap['never_checked_total']:>4}  ({snap['never_checked_active']} active)")
    for label, n in snap["freshness_buckets"].items():
        if n:
            print(f"  {label:<16}  {n:>4}")
    print()

    print(f"Concepts  ({snap['concept_pages']} pages)")
    print(f"  Referenced by ≥1 org:   {snap['concepts_referenced']:>4}")
    print(f"  Orphaned (no org ref):  {snap['concepts_orphaned']:>4}")
    print(f"  Orgs with concepts:     {snap['orgs_with_concepts']:>4} / {total}")
    print()

    print(f"Most referenced concepts  (top 10)")
    for slug, n in snap["top_concepts"]:
        print(f"  {slug:<36} {n:>4}")
    print()

    if show_orphans and snap["orphaned_concept_slugs"]:
        print(f"Orphaned concept pages  ({snap['concepts_orphaned']}):")
        for slug in snap["orphaned_concept_slugs"]:
            print(f"  docs/concepts/{slug}.md")
        print()

    print(f"{'═' * W}\n")


def print_diff(old, new):
    """Compact before/after summary for a heartbeat commit message."""
    def line(label, old_val, new_val, suffix=""):
        if old_val == new_val:
            print(f"  {label}: {new_val}{suffix}  -- unchanged")
        else:
            print(f"  {label}: {old_val}{suffix} -> {new_val}{suffix}")

    print(f"stats.py diff:  {old.get('date', '?')}  ->  {new.get('date', '?')}")

    old_status, new_status = old.get("status_counts", {}), new.get("status_counts", {})
    old_desc = f"{old.get('total_orgs', '?')} total ({old_status.get('active', 0)} active/{old_status.get('inactive', 0)} inactive/{old_status.get('deregistered', 0)} deregistered)"
    new_desc = f"{new.get('total_orgs', '?')} total ({new_status.get('active', 0)} active/{new_status.get('inactive', 0)} inactive/{new_status.get('deregistered', 0)} deregistered)"
    if old_desc == new_desc:
        print(f"  Orgs: {new_desc}  -- unchanged")
    else:
        print(f"  Orgs: {old_desc} -> {new_desc}")

    line("Never-checked active orgs", old.get("never_checked_active"), new.get("never_checked_active"))
    line("Never-checked total", old.get("never_checked_total"), new.get("never_checked_total"))
    line("Concept pages", old.get("concept_pages"), new.get("concept_pages"))
    line("Orphaned concepts", old.get("concepts_orphaned"), new.get("concepts_orphaned"))
    line("Concepts referenced by ≥1 org", old.get("concepts_referenced"), new.get("concepts_referenced"))

    old_orphans, new_orphans = set(old.get("orphaned_concept_slugs", [])), set(new.get("orphaned_concept_slugs", []))
    newly_tagged = old_orphans - new_orphans
    if newly_tagged:
        print(f"  Newly tagged concepts: {', '.join(sorted(newly_tagged))}")


def main():
    parser = argparse.ArgumentParser(description="Democracy Landscape snapshot")
    parser.add_argument("--concepts", action="store_true",
                        help="List orphaned concept pages")
    parser.add_argument("--json", action="store_true",
                        help="Print the snapshot as JSON instead of the human report")
    parser.add_argument("--save", metavar="PATH",
                        help="Write the JSON snapshot to PATH (in addition to the normal output)")
    parser.add_argument("--diff", metavar="PATH",
                        help="Compare current state against a snapshot saved earlier with --save")
    args = parser.parse_args()

    orgs = load_orgs()
    concept_slugs = load_concept_slugs()
    snapshot = build_snapshot(orgs, concept_slugs)

    if args.diff:
        with open(args.diff) as f:
            old_snapshot = json.load(f)
        print_diff(old_snapshot, snapshot)
        return

    if args.json:
        print(json.dumps(snapshot, indent=2))
    else:
        print_report(snapshot, show_orphans=args.concepts)

    if args.save:
        with open(args.save, "w") as f:
            json.dump(snapshot, f, indent=2)
        if not args.json:
            print(f"Snapshot saved to {args.save}\n")


if __name__ == "__main__":
    main()
