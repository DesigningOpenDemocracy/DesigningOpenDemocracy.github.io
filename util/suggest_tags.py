#!/usr/bin/env python3
"""
suggest_tags.py — Suggest concept tag additions to org pages

Given a concept slug, finds org pages that don't have it tagged but mention
related keywords in their body. Keywords are derived from the concept slug
and its page title; extend with --keywords for better recall.

Usage:
    python util/suggest_tags.py deliberative-democracy
    python util/suggest_tags.py citizens-assembly --keywords "mini-public" "citizen panel"
    python util/suggest_tags.py e-government --threshold 2   # require 2+ hits
    python util/suggest_tags.py sortition --all              # include already-tagged

Requirements: python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import os
import re
import sys

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
SKIP_FILES = {"organisations.md"}
STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "for", "in", "to", "is", "are",
    "was", "were", "that", "this", "it", "at", "by", "on", "with", "as",
    "from", "what", "how", "which", "who", "be", "been", "have", "has",
}


def slug_keywords(slug):
    return [w for w in slug.replace("-", " ").split()
            if w not in STOP_WORDS and len(w) > 2]


def concept_page_keywords(slug):
    """Extract bolded terms from the first 600 chars of the concept body."""
    path = os.path.join(CONCEPTS_DIR, f"{slug}.md")
    if not os.path.isfile(path):
        return []
    post = frontmatter.load(path)
    bold = re.findall(r'\*\*([^*]+)\*\*', post.content[:600])
    extra = []
    for term in bold:
        words = [w.lower() for w in term.split()
                 if w.lower() not in STOP_WORDS and len(w) > 2]
        extra.extend(words)
    return extra


def matches_in_body(content, patterns):
    hits = []
    for i, line in enumerate(content.splitlines(), 1):
        ll = line.lower()
        for pat in patterns:
            if pat.search(ll):
                hits.append((i, line.strip()))
                break
    return hits


def filter_ubiquitous(kws, org_paths, max_freq=0.4):
    """Drop keywords that appear in more than max_freq of org bodies — too broad to discriminate."""
    total = len(org_paths)
    if not total:
        return kws
    kept = []
    for kw in kws:
        pat = re.compile(r'\b' + re.escape(kw) + r'\b')
        hits = sum(1 for p in org_paths if _body_contains(p, pat))
        freq = hits / total
        if freq <= max_freq:
            kept.append(kw)
        else:
            pass  # silently drop — too common
    return kept


def _body_contains(path, pat):
    try:
        post = frontmatter.load(path)
        return bool(pat.search(post.content.lower()))
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Suggest concept tags for org pages based on keyword matches")
    parser.add_argument("slug", help="Concept slug (e.g. deliberative-democracy)")
    parser.add_argument("--keywords", nargs="+", metavar="TERM",
                        help="Extra search keywords (phrases OK)")
    parser.add_argument("--threshold", type=int, default=1,
                        help="Min keyword hits to suggest tagging (default: 1)")
    parser.add_argument("--all", action="store_true",
                        help="Include orgs already tagged (for audit)")
    args = parser.parse_args()

    concept_path = os.path.join(CONCEPTS_DIR, f"{args.slug}.md")
    if not os.path.isfile(concept_path):
        print(f"Unknown concept slug: {args.slug}")
        sys.exit(1)

    # Build keyword list
    kws = slug_keywords(args.slug) + concept_page_keywords(args.slug)
    if args.keywords:
        kws += [k.lower() for k in args.keywords]
    # Deduplicate, preserve order
    seen: set = set()
    kws = [k for k in kws if not (k in seen or seen.add(k))]  # type: ignore[func-returns-value]

    # Drop keywords that appear in >40% of org bodies — too broad to discriminate
    all_org_paths = sorted(glob.glob(os.path.join(ORGS_DIR, "*.md")))
    all_org_paths = [p for p in all_org_paths if os.path.basename(p) not in SKIP_FILES]
    kws_filtered = filter_ubiquitous(kws, all_org_paths)
    dropped = [k for k in kws if k not in kws_filtered]
    if dropped:
        print(f"    (Dropped overly common keywords: {', '.join(dropped)})")
    kws = kws_filtered

    if not kws:
        print(f"All derived keywords were too common (>40% of orgs).")
        print(f"Use --keywords to specify more distinctive terms.\n")
        sys.exit(0)

    patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in kws]

    print(f"\n=== Tag suggestions: {args.slug} ===")
    print(f"    Keywords: {', '.join(kws)}\n")

    suggestions = []
    already_count = 0
    no_match_count = 0

    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        title = m.get("title", os.path.basename(path)[:-3])
        tagged = args.slug in (m.get("concepts") or [])

        if tagged:
            already_count += 1
            if not args.all:
                continue

        hits = matches_in_body(post.content, patterns)

        if len(hits) >= args.threshold:
            suggestions.append({
                "path": path, "title": title,
                "tagged": tagged, "hits": hits,
            })
        elif not tagged:
            no_match_count += 1

    untagged_suggestions = [s for s in suggestions if not s["tagged"]]
    tagged_suggestions = [s for s in suggestions if s["tagged"]]

    if untagged_suggestions:
        print(f"Untagged orgs to consider  ({len(untagged_suggestions)}):\n")
        for s in untagged_suggestions:
            print(f"  {s['title']}")
            print(f"    {os.path.relpath(s['path'])}")
            for lineno, line in s["hits"][:3]:
                print(f"    {lineno:>4}: {line[:100]}")
            if len(s["hits"]) > 3:
                print(f"         … {len(s['hits']) - 3} more")
            print()
    else:
        print("No untagged orgs found with matching keywords.\n")

    if args.all and tagged_suggestions:
        print(f"Already-tagged orgs with matches  ({len(tagged_suggestions)}):")
        for s in tagged_suggestions:
            print(f"  ✓ {s['title']}  ({len(s['hits'])} hit(s))")
        print()

    print(f"Already tagged: {already_count}  |  "
          f"Suggested: {len(untagged_suggestions)}  |  "
          f"No match: {no_match_count}\n")


if __name__ == "__main__":
    main()
