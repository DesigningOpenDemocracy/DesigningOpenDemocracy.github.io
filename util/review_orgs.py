#!/usr/bin/env python3
"""
review_orgs.py — Interactive CLI for manual org status review.

Opens each org's website in your browser and prompts for a status confirmation.
Writes activity.manual entries (highest-priority evidence source) to frontmatter.
Optionally updates the org's status field if you find it has changed.

Usage:
    python util/review_orgs.py              # interactive scope selection
    python util/review_orgs.py --only-stale # skip prompt; review orgs with no/stale manual review
    python util/review_orgs.py --all        # include inactive/deregistered orgs
    python util/review_orgs.py --slug loomio  # single org

Requirements: python-frontmatter, pyyaml (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import re
import sys
import webbrowser
from datetime import date, datetime

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

try:
    import yaml as _yaml
except ImportError:
    print("Missing dependency: pip install pyyaml")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = date.today().isoformat()

PRIORITY_ORDER = ["manual", "dod", "social", "rss", "scrape", "sitemap"]
STALENESS_DAYS = {"manual": 730, "dod": 730, "social": 365, "rss": 365, "scrape": 365, "sitemap": 180}
MANUAL_STALE_DAYS = 730


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def best_activity(activity_dict):
    """Return (source, date, note) for the best non-stale entry, falling back to most recent."""
    if not activity_dict:
        return None
    today = date.today()
    for source in PRIORITY_ORDER:
        entry = activity_dict.get(source)
        if not entry:
            continue
        d = parse_date(entry.get("date"))
        if d and (today - d).days <= STALENESS_DAYS[source]:
            return source, d, entry.get("note", "")
    # All stale — return most recent regardless
    best = None
    for source, entry in activity_dict.items():
        d = parse_date(entry.get("date"))
        if d and (best is None or d > best[1]):
            best = source, d, entry.get("note", "")
    return best


def manual_age_days(activity_dict):
    """Days since last manual review, or None if never reviewed."""
    entry = (activity_dict or {}).get("manual")
    if not entry:
        return None
    d = parse_date(entry.get("date"))
    return (date.today() - d).days if d else None


def load_orgs(slug_filter=None, include_inactive=False):
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata
        slug = os.path.basename(path)[:-3]
        if slug_filter and slug != slug_filter:
            continue
        status = meta.get("status", "")
        if not include_inactive and status not in ("active",):
            continue
        orgs.append({
            "slug": slug,
            "path": path,
            "title": meta.get("title", slug),
            "status": status,
            "website": meta.get("website", "") or "",
            "activity": meta.get("activity") or {},
        })
    return orgs


def write_manual_activity(path, date_str, note):
    """Write or update activity.manual in org frontmatter using raw text edit."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]

    meta = _yaml.safe_load(yaml_block) or {}
    source_lines = [
        "  manual:",
        f"    date: {date_str}",
        f"    note: {json.dumps(note, ensure_ascii=False)}",
    ]

    if meta.get("activity"):
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
                    if in_this_source and not inserted:
                        new_lines.extend(source_lines)
                        inserted = True
                    in_activity = False
                    in_this_source = False
                    new_lines.append(line)
                    i += 1
                    continue
                # Found the manual sub-block — replace it
                if re.match(r"^  manual\s*:", line):
                    in_this_source = True
                    i += 1
                    while i < len(lines) and lines[i].startswith("    "):
                        i += 1
                    new_lines.extend(source_lines)
                    inserted = True
                    continue
                # Another source sub-block begins — clear the source flag
                if in_this_source and re.match(r"^  \w", line):
                    in_this_source = False
            new_lines.append(line)
            i += 1
        # activity block ran to EOF without a closing top-level key
        if in_activity and not inserted:
            # strip trailing blank lines so the new entry lands flush after the last entry
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
    return True


def update_status_field(path, new_status):
    """Update the status: line in org frontmatter using raw text substitution."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
    yaml_block = re.sub(
        r"^(status\s*:\s*)\S+",
        rf"\g<1>{new_status}",
        yaml_block,
        flags=re.MULTILINE,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def prompt_scope(orgs):
    """Ask the user which orgs to review; return the filtered list."""
    never = [o for o in orgs if not (o["activity"] or {}).get("manual")]
    stale_1yr = [
        o for o in orgs
        if manual_age_days(o["activity"]) is not None
        and manual_age_days(o["activity"]) > 365
    ]
    stale_2yr = [
        o for o in orgs
        if manual_age_days(o["activity"]) is None
        or manual_age_days(o["activity"]) > MANUAL_STALE_DAYS
    ]

    print()
    print("Which orgs do you want to review?")
    print(f"  [1] All loaded orgs                          ({len(orgs)} orgs)")
    print(f"  [2] Never manually reviewed                  ({len(never)} orgs)")
    print(f"  [3] Stale manual review (>1 year old)        ({len(stale_1yr)} orgs)")
    print(f"  [4] No or stale manual review (>2 years)     ({len(stale_2yr)} orgs)")
    print()
    while True:
        choice = input("Choice [1-4]: ").strip()
        if choice == "1":
            return orgs
        if choice == "2":
            return never
        if choice == "3":
            return stale_1yr
        if choice == "4":
            return stale_2yr
        print("Please enter 1, 2, 3, or 4.")


def review_org(org, index, total):
    """Interactively review one org. Returns True to continue, False to quit."""
    print()
    print("=" * 62)
    print(f"[{index}/{total}]  {org['title']}  ({org['slug']})")
    print(f"  Status:   {org['status']}")
    print(f"  Website:  {org['website'] or '(none)'}")

    activity = org["activity"]
    best = best_activity(activity)
    if best:
        src, d, note = best
        print(f"  Activity: {src} {d}  —  {note or '(no note)'}")
    else:
        print("  Activity: none recorded")

    manual_entry = activity.get("manual")
    if manual_entry:
        age = manual_age_days(activity)
        print(f"  Manual:   {manual_entry.get('date')} ({age}d ago)  —  {manual_entry.get('note', '')}")
    else:
        print("  Manual:   never reviewed")

    website = org["website"]
    if website and WAYBACK_PREFIX not in website:
        input(f"\n  Press Enter to open website in browser... ")
        webbrowser.open(website)
    else:
        print("\n  (No live website — skipping browser open)")

    print()
    print("  [a] Active      [i] Inactive    [d] Deregistered")
    print("  [s] Skip        [q] Quit")
    print()

    while True:
        choice = input("  > ").strip().lower()
        if choice == "q":
            return False
        if choice == "s":
            print("  Skipped.")
            return True
        if choice in ("a", "i", "d"):
            new_status = {"a": "active", "i": "inactive", "d": "deregistered"}[choice]
            note = input("  Note (Enter to use default): ").strip()
            if not note:
                note = f"Visited site, confirmed {new_status}"

            write_manual_activity(org["path"], TODAY, note)
            print(f"  ✓ Wrote activity.manual: {TODAY}")

            if new_status != org["status"]:
                update_status_field(org["path"], new_status)
                print(f"  ✓ Status updated: {org['status']} → {new_status}")

            return True
        print("  Invalid choice. Enter a, i, d, s, or q.")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive org status review — opens each org's website and records a manual activity entry."
    )
    parser.add_argument("--slug", help="Review a single org by slug")
    parser.add_argument(
        "--all", action="store_true", dest="include_all",
        help="Include inactive/deregistered orgs (default: active only)",
    )
    parser.add_argument(
        "--only-stale", action="store_true",
        help="Skip scope prompt; only review orgs with no or stale (>2yr) manual review",
    )
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.include_all)
    if not orgs:
        print("No orgs found matching criteria.")
        sys.exit(0)

    if args.slug:
        to_review = orgs
    elif args.only_stale:
        to_review = [
            o for o in orgs
            if manual_age_days(o["activity"]) is None
            or manual_age_days(o["activity"]) > MANUAL_STALE_DAYS
        ]
        print(f"Reviewing {len(to_review)} orgs with no or stale manual review (>{MANUAL_STALE_DAYS}d).")
    else:
        to_review = prompt_scope(orgs)

    if not to_review:
        print("No orgs to review in selected scope.")
        sys.exit(0)

    total = len(to_review)
    print(f"\nStarting review of {total} org(s). Press q at any time to quit.")

    for i, org in enumerate(to_review, 1):
        if not review_org(org, i, total):
            print(f"\nQuit after {i - 1}/{total} orgs reviewed.")
            break
    else:
        print(f"\nDone — reviewed all {total} orgs.")


if __name__ == "__main__":
    main()
