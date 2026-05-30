#!/usr/bin/env python3
"""
lint_orgs.py — Org page structural linter

Checks for inconsistencies between frontmatter fields and the conventions
documented in CLAUDE.md. Structural rules, not content accuracy — these checks
are most useful regardless of last_checked age, but --days can filter output.

Rules checked:
  1. Active org with a Wayback Machine website: URL
     (active orgs should have a live URL, not an archive link)

  2. Inactive/deregistered org with a live (non-Wayback) website: URL
     (defunct orgs should point to: https://web.archive.org/web/*/https://...)

  3. Active org missing location: coordinates
     (no location = doesn't appear on the interactive map)

  4. Org page with concepts: slugs not found in docs/concepts/
     (also caught by check_concepts.py — included here for a one-stop lint run)

  5. Status values outside the allowed set: active | inactive | deregistered

Filtering:
  By default, all pages are checked (structural rules don't go stale).
  Use --days N to suppress output for recently-verified pages.

Usage:
    python util/lint_orgs.py            # check all org pages
    python util/lint_orgs.py --days 90  # suppress pages checked within 90 days
    python util/lint_orgs.py --fix-hints  # print suggested frontmatter fixes

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
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
ALLOWED_STATUSES = {"active", "inactive", "deregistered"}


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
    return {
        os.path.basename(p)[:-3]
        for p in glob.glob(os.path.join(CONCEPTS_DIR, "*.md"))
        if os.path.basename(p) != "concepts.md"
    }


def check_org(meta, valid_slugs):
    """Return list of (rule_id, message) violations."""
    issues = []
    status = meta.get("status", "")
    website = meta.get("website", "") or ""
    location = meta.get("location")
    concepts = meta.get("concepts") or []

    # Rule 5: invalid status
    if status and status not in ALLOWED_STATUSES:
        issues.append(("status", f"Unknown status '{status}' (allowed: {', '.join(sorted(ALLOWED_STATUSES))})"))

    # Rule 1: active org with Wayback URL
    if status == "active" and WAYBACK_PREFIX in website:
        issues.append(("website-active", f"Active org has Wayback Machine URL: {website}"))

    # Rule 2: inactive/deregistered with live URL
    if status in ("inactive", "deregistered") and website and WAYBACK_PREFIX not in website:
        issues.append(("website-inactive", f"Inactive org has live URL — should point to Wayback: {website}"))

    # Rule 3: active org missing location
    if status == "active" and not location:
        issues.append(("location", "Active org is missing location: coordinates (won't appear on map)"))

    # Rule 4: invalid concept slugs
    bad_slugs = [s for s in concepts if s not in valid_slugs]
    if bad_slugs:
        issues.append(("concepts", f"Unknown concept slug(s): {bad_slugs}"))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Lint org page frontmatter for structural issues")
    parser.add_argument("--days", type=int, default=0,
                        help="Suppress output for pages checked within N days (default: 0 = check all)")
    parser.add_argument("--fix-hints", action="store_true",
                        help="Print suggested fixes alongside issues")
    args = parser.parse_args()

    valid_slugs = load_concept_slugs()

    FIX_HINTS = {
        "website-active": "Change website: to the live URL of the site.",
        "website-inactive": "Change website: to https://web.archive.org/web/*/https://originalurl.com/",
        "location": "Add location:\\n  latitude: XX.XXXX\\n  longitude: XX.XXXX\\n  name: City, Country",
        "concepts": "Fix the concept slug(s) to match filenames in docs/concepts/ (without .md).",
        "status": "Set status: to one of: active | inactive | deregistered",
    }

    pages_checked = pages_skipped = 0
    issues_found = 0

    print(f"\n=== Org page linter  (suppressing pages checked within {args.days} days) ===\n")

    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata

        # Apply --days filter
        if args.days > 0:
            lc = parse_date(meta.get("last_checked"))
            age = days_since(lc)
            if age is not None and age < args.days:
                pages_skipped += 1
                continue

        issues = check_org(meta, valid_slugs)
        pages_checked += 1

        if issues:
            lc = parse_date(meta.get("last_checked"))
            lc_str = f"last_checked: {lc}" if lc else "never checked"
            print(f"  {meta.get('title', os.path.basename(path))}")
            print(f"    {os.path.relpath(path)}  ({lc_str})")
            for rule_id, msg in issues:
                print(f"    ✗ {msg}")
                if args.fix_hints and rule_id in FIX_HINTS:
                    print(f"      → {FIX_HINTS[rule_id]}")
            print()
            issues_found += len(issues)

    if issues_found == 0:
        print(f"  No structural issues found.")
    print(f"Summary: {issues_found} issue(s) across {pages_checked} pages checked  |  {pages_skipped} skipped (recently verified)\n")


if __name__ == "__main__":
    main()
