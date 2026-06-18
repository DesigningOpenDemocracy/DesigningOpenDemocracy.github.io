#!/usr/bin/env python3
"""
createPost.py — Interactive CLI to scaffold a new blog or microblog post

Creates a new file in docs/blog/posts/ (or docs/microblog/posts/ with
--micro) with frontmatter pre-filled from your answers. Open the file in
your editor to write the body.

Usage:
    python util/createPost.py
    python util/createPost.py --micro
"""

import argparse
import os
import re
from datetime import datetime


def ask(question, optional=False):
    suffix = " (optional, Enter to skip): " if optional else ": "
    val = input(question + suffix).strip()
    return val if val else None


def slugify(text):
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def list_field(items):
    return "\n".join(f"- {item.strip()}" for item in items if item.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--micro", "-m", action="store_true",
        help="Create a microblog post (docs/microblog/posts/) instead of a full blog post",
    )
    args = parser.parse_args()
    micro = args.micro

    print(f"\n── New {'microblog' if micro else 'blog'} post ──\n")

    title = ask("Title")
    while not title:
        print("  Title is required.")
        title = ask("Title")

    authors_raw = ask("Author(s) (comma-separated)")
    authors = [a.strip() for a in (authors_raw or "").split(",") if a.strip()]
    if not authors:
        authors = [""]

    if micro:
        link = ask("Link (URL)", optional=True)
        note = ask("Note (one-liner, optional)", optional=True)
        categories, summary = [], note
    else:
        categories_raw = ask("Categories (comma-separated, e.g. podcast, meetup)")
        categories = [c.strip() for c in (categories_raw or "").split(",") if c.strip()]
        summary = ask("Summary (one paragraph)")
        link = ask("Link (URL for meetup/event, if any)", optional=True)

    tags_raw = ask("Tags (comma-separated)")
    tags = [t.strip() for t in (tags_raw or "").split(",") if t.strip()]

    date_str = ask("Date (YYYY-MM-DD, Enter for today)", optional=True)
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Build frontmatter
    lines = ["---"]
    lines.append(f"title: {title}")
    lines.append("authors:")
    for a in authors:
        lines.append(f"- {a}")
    if categories:
        lines.append("categories:")
        for c in categories:
            lines.append(f"- {c}")
    elif not micro:
        lines.append("categories: []")
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"- {t}")
    lines.append(f"date: {date_str} 00:00:00")
    if summary:
        escaped = summary.replace('"', '\\"')
        lines.append(f'summary: "{escaped}"')
    if link:
        lines.append(f"link: {link}")
    lines.append("---")
    lines.append("")
    if micro:
        if note:
            lines.append(note)
            lines.append("")
        if link:
            lines.append(f"<{link}>")
            lines.append("")
    else:
        lines.append(f"## {title}")
        lines.append("")

    slug = slugify(title)
    filename = f"{date_str}-{slug}.md"
    blog_dir = "microblog" if micro else "blog"
    posts_dir = os.path.join(os.path.dirname(__file__), "..", "docs", blog_dir, "posts")
    os.makedirs(posts_dir, exist_ok=True)
    file_path = os.path.join(posts_dir, filename)

    if os.path.exists(file_path):
        print(f"\n  File already exists: {file_path}")
        overwrite = input("  Overwrite? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("  Aborted.")
            return

    with open(file_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\n  Created: {file_path}\n")


if __name__ == "__main__":
    main()
