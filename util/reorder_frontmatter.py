#!/usr/bin/env python3
"""
Re-order org frontmatter to the canonical key ordering defined in CLAUDE.md.

Fields not in the canonical list are preserved at the end in their original order.

Usage:
    python util/reorder_frontmatter.py            # reorder all org pages in place
    python util/reorder_frontmatter.py --check    # report only, exit 1 if any need reordering
    python util/reorder_frontmatter.py --slug mosaiclab  # single org
"""

import argparse
import glob
import os
import sys
import re

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"index.md"}

# Canonical ordering (fields not listed are appended at end in original order)
CANONICAL_TOP = [
    "title", "type", "status", "country", "website",
    "logo", "logo_bg", "banner", "contact", "summary", "concepts",
    "location", "news_page", "rss_feed", "ics_feed", "related_orgs",
    "events", "activity", "last_checked",
]

# Per-event canonical field order
EVENT_FIELD_ORDER = [
    "date", "title", "url", "source", "quote", "note", "proof_level",
    "url_checked", "end_date", "time", "end_time", "notable", "type", "location",
    "proof_warning", "coverage_url",
]

# Activity sub-key canonical order
ACTIVITY_FIELD_ORDER = [
    "manual", "dod", "social", "rss", "ical", "scrape", "sitemap",
]


def ordered_dict(d, order):
    """Return a new OrderedDict with keys in `order` first, then remaining."""
    ordered = {}
    seen = set()
    for key in order:
        if key in d:
            ordered[key] = d[key]
            seen.add(key)
    for key in d:
        if key not in seen:
            ordered[key] = d[key]
    return ordered


def reorder_events(events):
    """Reorder per-event field keys."""
    if not isinstance(events, list):
        return events
    return [
        ordered_dict(e, EVENT_FIELD_ORDER) if isinstance(e, dict) else e
        for e in events
    ]


def reorder_activity(activity):
    """Reorder activity sub-keys."""
    if not isinstance(activity, dict):
        return activity
    return ordered_dict(activity, ACTIVITY_FIELD_ORDER)


def canonical_yaml_dump(data, **kwargs):
    """Dump YAML with keys in canonical order and flow style disabled."""

    class CanonicalDumper(yaml.Dumper):
        pass

    def dict_representer(dumper, d):
        return dumper.represent_mapping(
            "tag:yaml.org,2002:map", d.items()
        )

    CanonicalDumper.add_representer(dict, dict_representer)

    return yaml.dump(
        data,
        Dumper=CanonicalDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        **kwargs,
    )


def reorder_frontmatter(fm_text):
    """Parse frontmatter, reorder keys, return new frontmatter text."""
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        return fm_text

    data = ordered_dict(data, CANONICAL_TOP)
    if "events" in data:
        data["events"] = reorder_events(data["events"])
    if "activity" in data:
        data["activity"] = reorder_activity(data["activity"])

    return canonical_yaml_dump(data).rstrip("\n")



def main():
    parser = argparse.ArgumentParser(description="Re-order org frontmatter keys")
    parser.add_argument("--check", action="store_true",
                        help="Report only, exit 1 if any file needs reordering")
    parser.add_argument("--slug", type=str, help="Process a single org by slug")
    args = parser.parse_args()

    slugs_needing_fix = []
    skip_files = SKIP_FILES

    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in skip_files:
            continue
        slug = os.path.basename(path)[:-3]
        if args.slug and slug != args.slug:
            continue

        with open(path) as f:
            content = f.read()

        m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not m:
            continue

        fm_text = m.group(1)
        body = content[m.end():]
        new_fm = reorder_frontmatter(fm_text)
        new_content = f"---\n{new_fm}\n---\n{body}"

        if new_content != content:
            slugs_needing_fix.append(slug)
            if not args.check:
                with open(path, "w") as f:
                    f.write(new_content)

    if slugs_needing_fix:
        if args.check:
            print(f"Ordering mismatch in {len(slugs_needing_fix)} org pages:")
            for s in slugs_needing_fix:
                print(f"  {s}")
            print(f"\nRun 'python util/reorder_frontmatter.py' to fix.")
            return 1
        else:
            print(f"Reordered frontmatter in {len(slugs_needing_fix)} org pages.")
    else:
        print("All org frontmatter follows canonical ordering.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
