#!/usr/bin/env python3
"""
stamp.py — Set last_checked: today on org (or concept) pages

Updates the last_checked frontmatter field in-place without reordering any
other keys. Accepts slugs (resolved against docs/organisations/ then
docs/concepts/) or explicit file paths.

Usage:
    python util/stamp.py namfrel
    python util/stamp.py docs/organisations/namfrel.md
    python util/stamp.py namfrel flacso-cuba mysociety
    python util/stamp.py --all-active     # all active orgs
    python util/stamp.py --all            # all org pages

Requirements: none (stdlib only)
"""

import argparse
import glob
import os
import re
import sys
from datetime import date

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
SKIP_FILES = {"organisations.md", "concepts.md"}
TODAY = date.today().isoformat()

LC_RE = re.compile(r'^(last_checked:\s*).*$', re.MULTILINE)


def resolve_target(target):
    if os.path.isfile(target):
        return os.path.abspath(target)
    p = os.path.join(ORGS_DIR, f"{target}.md")
    if os.path.isfile(p):
        return p
    p = os.path.join(CONCEPTS_DIR, f"{target}.md")
    if os.path.isfile(p):
        return p
    return None


def stamp_file(path):
    """Update last_checked in-place. Returns (changed, note)."""
    with open(path) as f:
        content = f.read()

    new_val = f'last_checked: "{TODAY}"'
    match = LC_RE.search(content)

    if match:
        old_line = match.group(0)
        if TODAY in old_line:
            return False, "already current"
        new_content = content[:match.start()] + new_val + content[match.end():]
        old_note = old_line.split(":", 1)[1].strip().strip('"')
    else:
        # Insert before the closing --- of frontmatter
        lines = content.splitlines(keepends=True)
        if not lines or not lines[0].startswith("---"):
            return False, "no frontmatter"
        insert_at = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                insert_at = i
                break
        if insert_at is None:
            return False, "no closing frontmatter fence"
        lines.insert(insert_at, f"{new_val}\n")
        new_content = "".join(lines)
        old_note = "unset"

    with open(path, "w") as f:
        f.write(new_content)
    return True, old_note


def org_status(path):
    """Read status field without full frontmatter parse — fast grep."""
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("status:"):
                    return line.split(":", 1)[1].strip()
                if line.strip() == "---" and f.tell() > 4:
                    break
    except Exception:
        pass
    return ""


def all_org_paths(active_only=False):
    paths = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        if active_only and org_status(path) != "active":
            continue
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description="Stamp last_checked: today on pages")
    parser.add_argument("targets", nargs="*", help="Slugs or file paths")
    parser.add_argument("--all-active", action="store_true", help="Stamp all active org pages")
    parser.add_argument("--all", action="store_true", help="Stamp all org pages")
    args = parser.parse_args()

    if not args.targets and not args.all_active and not args.all:
        parser.print_help()
        sys.exit(1)

    paths = []
    if args.all or args.all_active:
        paths = all_org_paths(active_only=args.all_active)
    else:
        for t in args.targets:
            p = resolve_target(t)
            if p is None:
                print(f"  ✗ Not found: {t}")
            else:
                paths.append(p)

    changed = skipped = errors = 0
    for path in paths:
        try:
            updated, note = stamp_file(path)
            rel = os.path.relpath(path)
            if updated:
                print(f"  ✓ {rel}  ({note} → {TODAY})")
                changed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ✗ {os.path.relpath(path)}: {e}")
            errors += 1

    print(f"\nDone: {changed} stamped, {skipped} already current, {errors} errors")


if __name__ == "__main__":
    main()
