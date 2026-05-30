#!/usr/bin/env python3
"""
find.py — Full-text search across org and concept pages

Searches title, summary (frontmatter) and body text. Case-insensitive by
default. Use before adding a new org to check for existing coverage, or to
find pages that mention a keyword without explicitly tagging it.

Usage:
    python util/find.py "participatory budgeting"
    python util/find.py "stafford beer" --concepts
    python util/find.py "liquid" --orgs --context 2
    python util/find.py "Porto Alegre" --case-sensitive

Requirements: none (stdlib only)
"""

import argparse
import glob
import os
import re
import sys

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
SKIP_FILES = {"organisations.md", "concepts.md"}
FM_RE = re.compile(r'^---\s*$', re.MULTILINE)
TITLE_RE = re.compile(r'^title:\s*(.+)$', re.MULTILINE)


def read_file(path):
    with open(path) as f:
        content = f.read()
    title_match = TITLE_RE.search(content)
    title = title_match.group(1).strip().strip('"') if title_match else os.path.basename(path)[:-3]
    return title, content.splitlines()


def search_file(path, pattern, context_n):
    title, lines = read_file(path)
    hits = []
    for i, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, i - context_n)
            end = min(len(lines), i + context_n + 1)
            hits.append((i + 1, lines[start:end], i - start))
    return title, hits


def main():
    parser = argparse.ArgumentParser(description="Full-text search across org/concept pages")
    parser.add_argument("query", help="Search term or regex")
    parser.add_argument("--orgs", action="store_true", help="Search org pages only")
    parser.add_argument("--concepts", action="store_true", help="Search concept pages only")
    parser.add_argument("--context", "-c", type=int, default=1,
                        help="Context lines around each match (default: 1)")
    parser.add_argument("--case-sensitive", action="store_true")
    args = parser.parse_args()

    flags = 0 if args.case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(args.query, flags)
    except re.error as e:
        print(f"Invalid regex: {e}")
        sys.exit(1)

    sections = []
    if not args.orgs and not args.concepts:
        sections = ["organisations", "concepts"]
    else:
        if args.orgs:
            sections.append("organisations")
        if args.concepts:
            sections.append("concepts")

    total_hits = total_files = 0
    print(f"\n=== find: '{args.query}' ===\n")

    for section in sections:
        section_dir = os.path.join(DOCS_DIR, section)
        results = []
        for path in sorted(glob.glob(os.path.join(section_dir, "*.md"))):
            if os.path.basename(path) in SKIP_FILES:
                continue
            try:
                title, hits = search_file(path, pattern, args.context)
            except Exception:
                continue
            if hits:
                results.append((path, title, hits))

        if results:
            print(f"── {section} ──")
            for path, title, hits in results:
                print(f"  {title}  ({os.path.relpath(path)})")
                shown = 0
                for lineno, ctx, match_offset in hits:
                    for j, ctx_line in enumerate(ctx):
                        marker = ">" if j == match_offset else " "
                        print(f"   {marker} {lineno - match_offset + j:>4}  {ctx_line}")
                    shown += 1
                    if shown < len(hits):
                        print()
                print()
                total_files += 1
                total_hits += len(hits)

    if total_hits == 0:
        print("  No matches found.")
    else:
        print(f"Found {total_hits} match(es) in {total_files} file(s)")
    print()


if __name__ == "__main__":
    main()
