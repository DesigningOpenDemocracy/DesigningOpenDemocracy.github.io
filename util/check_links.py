#!/usr/bin/env python3
"""
check_links.py — Internal markdown link checker (MkDocs-aware)

Scans docs/organisations/ and docs/concepts/ for broken internal .md links.
Accounts for MkDocs use_directory_urls=True, which changes how relative links
resolve. Two resolution strategies are tried (see RESOLUTION NOTE below).

RESOLUTION NOTE (MkDocs use_directory_urls=True):
  With use_directory_urls, each page foo.md is served at /section/foo/ — one
  level deeper than the source file. This affects ../../-style links to blog
  posts but NOT ../sibling/ links. Two strategies are tried for each link:

    Strategy 1 (source-file): resolve relative to the source file's directory.
      Works for:  ../concepts/bar.md  from  docs/organisations/foo.md
                  → docs/concepts/bar.md ✓

    Strategy 2 (URL-based): resolve relative to the source file treated as a
      directory (simulating use_directory_urls output depth).
      Works for:  ../../blog/posts/bar.md  from  docs/organisations/foo.md
                  → docs/blog/posts/bar.md ✓

  A link is only reported as broken if BOTH strategies fail.

Filtering:
  Pages with a recent last_checked date are skipped (default: 365 days).
  Use --all to check everything regardless.

Usage:
    python util/check_links.py              # default threshold: 365 days
    python util/check_links.py --days 90
    python util/check_links.py --all        # ignore last_checked
    python util/check_links.py --dir concepts   # only check concept pages

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import os
import re
import sys
from datetime import date, datetime

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
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


def is_recently_checked(meta, threshold_days):
    d = parse_date(meta.get("last_checked"))
    age = days_since(d)
    return age is not None and age < threshold_days


def resolve_link(source_file, link_target):
    """
    Try both resolution strategies. Returns (resolved_path, strategy) if found,
    or (None, None) if both fail.
    """
    # Strip anchor and query string
    path = link_target.split('#')[0].split('?')[0]
    if not path.endswith('.md'):
        return None, None  # only validate .md links

    # Strategy 1: relative to source file's directory
    source_dir = os.path.dirname(source_file)
    c1 = os.path.normpath(os.path.join(source_dir, path))
    if os.path.isfile(c1):
        return c1, "source-dir"

    # Strategy 2: relative to source file treated as a directory
    # (simulates use_directory_urls output structure)
    virtual_dir = source_file[:-3]  # strip .md
    c2 = os.path.normpath(os.path.join(virtual_dir, path))
    if os.path.isfile(c2):
        return c2, "url-based"

    return None, None


def check_file(path, docs_dir):
    """Return list of (line_no, label, target) for broken links."""
    broken = []
    try:
        with open(path) as f:
            lines = f.readlines()
    except Exception:
        return broken

    for i, line in enumerate(lines, 1):
        for label, target in LINK_RE.findall(line):
            # Skip external links and anchors
            if target.startswith(('http://', 'https://', '#', 'mailto:')):
                continue
            if not target.endswith('.md') and '.md#' not in target:
                continue
            resolved, _ = resolve_link(path, target)
            if resolved is None:
                broken.append((i, label, target))
    return broken


def scan_dir(directory, threshold_days, ignore_threshold):
    results = []
    for path in sorted(glob.glob(os.path.join(directory, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        if not ignore_threshold and is_recently_checked(post.metadata, threshold_days):
            continue
        broken = check_file(path, DOCS_DIR)
        if broken:
            results.append((path, broken))
    return results


def main():
    parser = argparse.ArgumentParser(description="Find broken internal .md links")
    parser.add_argument("--days", type=int, default=365,
                        help="Skip pages checked within this many days (default: 365)")
    parser.add_argument("--all", action="store_true",
                        help="Ignore last_checked, check all pages")
    parser.add_argument("--dir", choices=["organisations", "concepts", "both"],
                        default="both", help="Which section to scan (default: both)")
    args = parser.parse_args()

    dirs_to_scan = []
    if args.dir in ("organisations", "both"):
        dirs_to_scan.append(os.path.join(DOCS_DIR, "organisations"))
    if args.dir in ("concepts", "both"):
        dirs_to_scan.append(os.path.join(DOCS_DIR, "concepts"))

    threshold = args.days
    ignore = args.all

    print(f"\n=== Internal link checker  (threshold: {'all' if ignore else f'{threshold} days'}) ===\n")

    total_broken = 0
    total_files = 0
    for d in dirs_to_scan:
        section = os.path.basename(d)
        results = scan_dir(d, threshold, ignore)
        if results:
            print(f"── {section} ──")
            for path, broken in results:
                print(f"  {os.path.relpath(path)}:")
                for line_no, label, target in broken:
                    print(f"    line {line_no}: [{label}]({target})")
                total_files += 1
                total_broken += len(broken)
            print()

    if total_broken == 0:
        print("  No broken internal links found.")
    else:
        print(f"Total: {total_broken} broken link(s) across {total_files} file(s)")
    print()
    sys.exit(1 if total_broken > 0 else 0)


if __name__ == "__main__":
    main()
