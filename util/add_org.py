#!/usr/bin/env python3
"""
add_org.py — Interactive CLI to scaffold a new org page

Prompts for all standard frontmatter fields, validates inline (ISO country
code, concept slugs, Wayback URL convention for inactive orgs), and writes
docs/organisations/<slug>.md ready to fill in.

Usage:
    python util/add_org.py

Requirements: none (stdlib only)
"""

import glob
import os
import re
import sys
from datetime import date

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
WAYBACK_PREFIX = "https://web.archive.org"
ALLOWED_STATUSES = ("active", "inactive", "deregistered")
ALLOWED_TYPES = (
    "research", "education", "advocacy", "platform", "civic_tech",
    "practice", "philanthropy", "cooperative", "party", "political_party",
    "political_movement", "governance", "government",
)
ISO2_RE = re.compile(r'^[A-Z]{2}$')
TODAY = date.today().isoformat()


def load_concept_slugs():
    slugs = set()
    for path in glob.glob(os.path.join(CONCEPTS_DIR, "*.md")):
        slug = os.path.basename(path)[:-3]
        if slug != "concepts":
            slugs.add(slug)
    return slugs


def slugify(text):
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def ask(prompt, required=True, default=None):
    suffix = f" [{default}]" if default else (" (required)" if required else " (optional, Enter to skip)")
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default:
            return default
        if val or not required:
            return val or None
        print("    Required.")


def ask_choice(prompt, choices):
    print(f"\n  {prompt}:")
    for i, c in enumerate(choices, 1):
        print(f"    {i:>2}. {c}")
    while True:
        val = input("  Choice (number or name): ").strip().lower()
        try:
            n = int(val)
            if 1 <= n <= len(choices):
                return choices[n - 1]
        except ValueError:
            pass
        if val in choices:
            return val
        matches = [c for c in choices if c.startswith(val)]
        if len(matches) == 1:
            return matches[0]
        print(f"    Enter a number 1–{len(choices)} or start of a name.")


def ask_concepts(valid_slugs):
    print(f"\n  Concepts — comma-separated slugs ({len(valid_slugs)} known).")
    print(f"  Enter ? to list all, or press Enter to skip.")
    while True:
        raw = input("  > ").strip()
        if raw == "?":
            for slug in sorted(valid_slugs):
                print(f"    {slug}")
            continue
        if not raw:
            return []
        slugs = [s.strip() for s in raw.split(",") if s.strip()]
        unknown = [s for s in slugs if s not in valid_slugs]
        if unknown:
            print(f"  Warning: unknown slug(s): {unknown}  (saved but won't render as chips)")
        return slugs


def main():
    valid_slugs = load_concept_slugs()

    print("\n── New org page ──\n")

    title = ask("Title")

    org_type = ask_choice("Type", list(ALLOWED_TYPES))

    status = ask_choice("Status", list(ALLOWED_STATUSES))

    # Country
    while True:
        country = ask("Country (2-letter ISO code, e.g. AU  GB  US  DE)")
        if country and ISO2_RE.match(country.upper()):
            country = country.upper()
            break
        print("    Must be a 2-letter ISO 3166-1 alpha-2 code.")

    # Website
    website = ask("Website URL", required=False)
    if website:
        if status in ("inactive", "deregistered") and not website.startswith(WAYBACK_PREFIX):
            suggested = f"https://web.archive.org/web/*/{website.rstrip('/')}/"
            print(f"\n  {status.capitalize()} orgs should point to the Wayback Machine calendar URL.")
            print(f"  Suggested: {suggested}")
            use_wb = input("  Use Wayback URL? [Y/n]: ").strip().lower()
            if use_wb != "n":
                website = suggested
        elif status == "active" and website.startswith(WAYBACK_PREFIX):
            print("  Warning: active orgs normally use a live URL (Wayback is for defunct orgs).")

    summary = ask("Summary (one sentence for the metadata box)", required=False)

    concepts = ask_concepts(valid_slugs)

    # Location — active orgs need this to appear on the map
    location = None
    if status == "active":
        print("\n  Location — required for the org to appear on the interactive map.")
        lat = ask("    Latitude (decimal, e.g. -37.8136)", required=False)
        if lat:
            lon = ask("    Longitude (decimal, e.g. 144.9631)")
            loc_name = ask("    Name (e.g. Melbourne, Australia)")
            try:
                location = {"latitude": float(lat), "longitude": float(lon), "name": loc_name}
            except ValueError:
                print("  Invalid coordinates — location skipped. Add manually later.")

    # Build frontmatter
    slug = slugify(title)
    file_path = os.path.join(ORGS_DIR, f"{slug}.md")

    if os.path.exists(file_path):
        print(f"\n  File already exists: {file_path}")
        overwrite = input("  Overwrite? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("  Aborted.")
            return

    lines = ["---"]
    lines.append(f"title: {title}")
    lines.append(f"type: {org_type}")
    lines.append(f"status: {status}")
    lines.append(f"country: {country}")
    if website:
        lines.append(f"website: {website}")
    if summary:
        lines.append(f'summary: "{summary.replace(chr(34), chr(92)+chr(34))}"')
    if concepts:
        lines.append("concepts:")
        for c in concepts:
            lines.append(f"  - {c}")
    if location:
        lines.append("location:")
        lines.append(f"  latitude: {location['latitude']}")
        lines.append(f"  longitude: {location['longitude']}")
        lines.append(f'  name: "{location["name"]}"')
    lines.append(f'last_checked: "{TODAY}"')
    lines.append("---")
    lines.append("")
    lines.append(f"{title} is a …")
    lines.append("")
    lines.append("## Links")
    lines.append("")
    if website:
        if website.startswith(WAYBACK_PREFIX):
            lines.append(f"- Archive: [{title} (Wayback Machine)]({website})")
        else:
            domain = re.sub(r"https?://", "", website).rstrip("/")
            lines.append(f"- Website: [{domain}]({website})")
    lines.append("")
    lines.append("## See also")
    lines.append("")
    for c in concepts[:3]:
        lines.append(f"- [{c.replace('-', ' ').title()}](../concepts/{c}.md)")

    with open(file_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n  Created: {file_path}")
    print(f"  Slug: {slug}")
    if not location and status == "active":
        print(f"  Remember to add location: coordinates (needed for the map).")
    print()


if __name__ == "__main__":
    main()
