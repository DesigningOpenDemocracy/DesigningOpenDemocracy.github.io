#!/usr/bin/env python3
"""
record_dod.py — Record an activity.dod entry on one or more org pages

Use during heartbeat AI runs to record that the bot verified an org.
Writes (or updates) the activity.dod block in org frontmatter and stamps
last_checked: today, using raw text substitution (same approach as stamp.py
and review_orgs.py).

This keeps bot evidence under the dod key (365-day staleness) separate from
human review_orgs.py entries under the manual key (730-day staleness).
See CLAUDE.md's activity: section for the full distinction.

Usage:
    python util/record_dod.py cddgg --note "Website confirmed active, seminar series running"
    python util/record_dod.py cddgg darkenu --note "Confirmed active" --date 2026-06-29
    python util/record_dod.py cddgg --note "..." --url https://example.org/news
    python util/record_dod.py cddgg --note "..." --no-stamp   # skip last_checked update

--date is the date of the evidence you found (e.g. a publication date); it
defaults to today. The checked: field always records today as the probe date.

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import json
import os
import re
import sys
from datetime import date

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
TODAY = date.today().isoformat()

LC_RE = re.compile(r'^(last_checked:\s*).*$', re.MULTILINE)


def resolve_slug(slug):
    p = os.path.join(ORGS_DIR, f"{slug}.md")
    return p if os.path.isfile(p) else None


def write_dod_activity(path, date_str, note, url=None, checked_str=None):
    """Write or update activity.dod in org frontmatter using raw text edit."""
    if checked_str is None:
        checked_str = TODAY
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False, "no frontmatter"
    yaml_block, rest = parts[1], parts[2]

    source_lines = [
        "  dod:",
        f"    date: {date_str}",
        f"    note: {json.dumps(note, ensure_ascii=False)}",
    ]
    if url:
        source_lines.append(f"    url: {url}")
    source_lines.append(f"    checked: {checked_str}")

    post = frontmatter.loads("---" + yaml_block + "---")
    if post.metadata.get("activity"):
        lines = yaml_block.split("\n")
        new_lines = []
        in_activity = False
        in_this_source = False
        inserted = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^activity\s*:", line):
                in_activity = True
                new_lines.append(line)
                i += 1
                continue
            if in_activity:
                # Top-level key ends the activity block
                if line and not line.startswith(" "):
                    if not inserted:
                        # dod: wasn't in the activity block — append before exit
                        while new_lines and new_lines[-1] == "":
                            new_lines.pop()
                        new_lines.extend(source_lines)
                        inserted = True
                    in_activity = False
                    in_this_source = False
                    new_lines.append(line)
                    i += 1
                    continue
                # Found the dod sub-block — replace it
                if re.match(r"^  dod\s*:", line):
                    in_this_source = True
                    i += 1
                    while i < len(lines) and lines[i].startswith("    "):
                        i += 1
                    new_lines.extend(source_lines)
                    inserted = True
                    continue
                if in_this_source and re.match(r"^  \w", line):
                    in_this_source = False
            new_lines.append(line)
            i += 1
        # activity block ran to end of YAML without a closing top-level key
        if in_activity and not inserted:
            while new_lines and new_lines[-1] == "":
                new_lines.pop()
            new_lines.extend(source_lines)
        yaml_block = "\n".join(new_lines)
        if not yaml_block.endswith("\n"):
            yaml_block += "\n"
    else:
        new_block = ["activity:"] + source_lines
        yaml_block = yaml_block.rstrip("\n") + "\n" + "\n".join(new_block) + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True, "ok"


def stamp_last_checked(path, date_str):
    """Update last_checked in-place (same logic as stamp.py)."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    match = LC_RE.search(content)
    new_val = f'last_checked: "{date_str}"'
    if match:
        if date_str in match.group(0):
            return False
        new_content = content[:match.start()] + new_val + content[match.end():]
    else:
        lines = content.splitlines(keepends=True)
        insert_at = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                insert_at = i
                break
        if insert_at is None:
            return False
        lines.insert(insert_at, f"{new_val}\n")
        new_content = "".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Record an activity.dod entry on org pages")
    parser.add_argument("slugs", nargs="+", help="Org slugs or file paths")
    parser.add_argument("--note", required=True,
                        help="Evidence note: what you found confirming the org is active")
    parser.add_argument("--url", help="URL of the evidence page")
    parser.add_argument("--date", dest="activity_date", default=TODAY,
                        help=f"Date of the observed activity (default: today, {TODAY})")
    parser.add_argument("--no-stamp", action="store_true",
                        help="Skip updating last_checked")
    args = parser.parse_args()

    errors = 0
    for slug in args.slugs:
        if os.path.isfile(slug):
            path = os.path.abspath(slug)
        else:
            path = resolve_slug(slug)
        if path is None:
            print(f"  ✗ Not found: {slug}")
            errors += 1
            continue
        rel = os.path.relpath(path)
        ok, msg = write_dod_activity(path, args.activity_date, args.note, url=args.url)
        if not ok:
            print(f"  ✗ {rel}: {msg}")
            errors += 1
            continue
        print(f"  ✓ {rel}: activity.dod → date={args.activity_date}")
        if not args.no_stamp:
            stamp_last_checked(path, TODAY)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
