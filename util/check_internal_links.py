#!/usr/bin/env python3
"""Check that relative links in docs/*.md resolve to existing files.

A link resolves if either:
  1. The target is a valid path relative to the linking file (or to docs/,
     for absolute "/..." targets), or
  2. mkdocs-ezlinks-plugin's fallback applies: the target's basename (with
     or without extension) matches some file anywhere under docs/. This is
     how this site's standard "../../blog/posts/<slug>.md" cross-references
     resolve from docs/concepts/ and docs/organisations/ — two levels up
     from those directories overshoots docs/ entirely, so ezlinks falls
     back to a basename search across the whole tree.

Run after `mkdocs build` so generated paths (e.g. docs/data/*) exist.
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"

# Matches [text](target) and ![alt](target). Target runs up to the first
# whitespace, ')' or '#' — same as how this site's existing links are written.
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "//")

# SUMMARY.md mixes literate-nav section links with plugin-generated virtual
# pages (blog categories, pagination) that don't exist as source files.
EXCLUDE_FILES = {DOCS_DIR / "SUMMARY.md"}


def build_known_names() -> set[str]:
    """Filenames and stems of every file under docs/, for the ezlinks basename fallback."""
    names = set()
    for f in DOCS_DIR.rglob("*"):
        if f.is_file():
            names.add(f.name)
            names.add(f.stem)
    return names


def find_broken_links(path: Path, known_names: set[str]) -> list[str]:
    errors = []
    in_code_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        for match in LINK_RE.finditer(line):
            target = match.group(1)
            if target.startswith(SKIP_PREFIXES) or target.startswith("#"):
                continue

            target_path, _, _fragment = target.partition("#")
            if not target_path:
                continue
            target_path = unquote(target_path)

            if target_path.startswith("/"):
                resolved = DOCS_DIR / target_path.lstrip("/")
            else:
                resolved = path.parent / target_path

            if resolved.exists():
                continue
            if Path(target_path).name in known_names:
                continue

            rel = path.relative_to(ROOT)
            errors.append(f"{rel}:{lineno}: broken link '{target}' -> {resolved} not found")
    return errors


def main() -> int:
    known_names = build_known_names()
    all_errors = []
    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        if md_file in EXCLUDE_FILES:
            continue
        all_errors.extend(find_broken_links(md_file, known_names))

    if all_errors:
        print(f"Found {len(all_errors)} broken internal link(s):\n")
        for err in all_errors:
            print(f"  {err}")
        return 1

    print("No broken internal links found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
