#!/usr/bin/env python3
"""
new_concept.py — Interactive CLI to scaffold a new concept page

Creates docs/concepts/<slug>.md with the standard discovery-aid structure.

Convention (from CLAUDE.md): concept pages are brief orientations pointing
to better sources — not authoritative explanations. Do not write extended
prose from general knowledge. If depth is needed, link outward.

Usage:
    python util/new_concept.py

Requirements: none (stdlib only)
"""

import glob
import os
import re
import sys
from datetime import date

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
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


def ask(prompt, required=True):
    suffix = " (required)" if required else " (optional, Enter to skip)"
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if val or not required:
            return val or None
        print("    Required.")


def main():
    valid_slugs = load_concept_slugs()

    print("\n── New concept page ──")
    print("  Keep it as a discovery aid: brief orientation, link outward.")
    print("  No extended explanations from general knowledge.\n")

    title = ask("Title (e.g. Liquid Democracy)")
    slug = slugify(title)

    if os.path.isfile(os.path.join(CONCEPTS_DIR, f"{slug}.md")):
        print(f"\n  Already exists: docs/concepts/{slug}.md")
        return

    summary = ask("One-line summary for search/metadata", required=False)

    wiki_url = ask("Wikipedia URL (if one exists)", required=False)

    print(f"\n  See Also — related concept slugs (comma-separated).")
    print(f"  Enter ? to list all {len(valid_slugs)} known slugs, or Enter to skip.")
    see_also = []
    while True:
        raw = input("  > ").strip()
        if raw == "?":
            for s in sorted(valid_slugs):
                print(f"    {s}")
            continue
        if not raw:
            break
        candidates = [s.strip() for s in raw.split(",") if s.strip()]
        unknown = [s for s in candidates if s not in valid_slugs]
        if unknown:
            print(f"  Warning: unknown slug(s): {unknown}")
        see_also = candidates
        break

    # Build file
    lines = ["---"]
    lines.append(f"title: {title}")
    if summary:
        lines.append(f'summary: "{summary.replace(chr(34), chr(92)+chr(34))}"')
    lines.append(f'last_checked: "{TODAY}"')
    lines.append("---")
    lines.append("")
    lines.append(f"**{title}** is …")
    lines.append("")
    lines.append("## Further reading")
    lines.append("")
    if wiki_url:
        lines.append(f"- Wikipedia: [{title}]({wiki_url})")
    else:
        wp_slug = title.replace(" ", "_")
        lines.append(f"- Wikipedia: [{title}](https://en.wikipedia.org/wiki/{wp_slug})")
    lines.append("")
    if see_also:
        lines.append("## See also")
        lines.append("")
        for s in see_also:
            label = s.replace("-", " ").title()
            lines.append(f"- [{label}]({s}.md)")

    file_path = os.path.join(CONCEPTS_DIR, f"{slug}.md")
    with open(file_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n  Created: docs/concepts/{slug}.md  (slug: {slug})")
    print(f"  Fill in the body — keep it to 1–2 paragraphs, then link outward.\n")


if __name__ == "__main__":
    main()
