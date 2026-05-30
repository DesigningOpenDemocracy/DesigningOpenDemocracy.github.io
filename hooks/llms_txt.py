"""
llms_txt.py — MkDocs hook: generate /llms.txt at build time

Writes docs/llms.txt during on_pre_build so it's included in the site as a
static page at /llms.txt. Content is derived entirely from org and concept
page frontmatter — no AI summarisation needed because the structured
frontmatter already captures what each page is about.

Format follows the llms.txt convention: plain Markdown, compact, designed
for an LLM to read once and then navigate directly to relevant pages rather
than crawling the whole site.
"""

import glob
import os
from collections import defaultdict

try:
    import frontmatter
except ImportError:
    frontmatter = None  # graceful degradation — hook is a no-op if not installed


DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
OUT_PATH = os.path.join(DOCS_DIR, "llms.txt")
SKIP_FILES = {"organisations.md", "concepts.md"}


def load_orgs():
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        if frontmatter is None:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        slug = os.path.basename(path)[:-3]
        orgs.append({
            "slug": slug,
            "title": m.get("title", slug),
            "status": m.get("status", "unknown"),
            "country": m.get("country", ""),
            "type": m.get("type", ""),
            "summary": (m.get("summary") or "").strip().strip('"'),
            "concepts": m.get("concepts") or [],
        })
    return orgs


def load_concepts():
    concepts = []
    for path in sorted(glob.glob(os.path.join(CONCEPTS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        if frontmatter is None:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        slug = os.path.basename(path)[:-3]
        title = m.get("title", slug.replace("-", " ").title())
        summary = (m.get("summary") or "").strip().strip('"')
        # Fall back to first non-empty body sentence if no summary
        if not summary and post.content:
            first = post.content.strip().lstrip("#").strip()
            first = first.replace("**", "").split("\n")[0].strip()
            if len(first) > 20:
                summary = first[:160]
        concepts.append({"slug": slug, "title": title, "summary": summary})
    return concepts


def build_llms_txt(site_url):
    orgs = load_orgs()
    concepts = load_concepts()

    by_status = defaultdict(list)
    for o in orgs:
        by_status[o["status"]].append(o)

    lines = []

    lines += [
        "# Designing Open Democracy — Democracy Landscape",
        "",
        "> A reference wiki monitoring organisations working on democratic governance design",
        "> worldwide. Covers deliberative democracy, sortition, participatory democracy,",
        "> civic technology, cooperative governance, and related fields.",
        ">",
        f"> Site: {site_url}",
        "> Curation standard: organisations that work on governance systems for/with the",
        "> people, in good faith. Not a human rights observatory — focus is governance design.",
        "",
        "---",
        "",
    ]

    # --- Active orgs ---
    active = by_status.get("active", [])
    lines.append(f"## Active Organisations ({len(active)})")
    lines.append("")
    lines.append("Format: **Name** (Country · Type) — Summary  [/organisations/slug/]")
    lines.append("")
    for o in active:
        meta = " · ".join(filter(None, [o["country"], o["type"]]))
        summary = o["summary"] or "No summary available."
        url = f"{site_url}/organisations/{o['slug']}/"
        lines.append(f"- **{o['title']}** ({meta}) — {summary}  [{url}]")
    lines.append("")

    # --- Inactive / deregistered ---
    defunct = by_status.get("inactive", []) + by_status.get("deregistered", [])
    if defunct:
        lines.append(f"## Inactive / Deregistered Organisations ({len(defunct)})")
        lines.append("")
        for o in defunct:
            meta = " · ".join(filter(None, [o["country"], o["type"], o["status"]]))
            summary = o["summary"] or "No summary available."
            url = f"{site_url}/organisations/{o['slug']}/"
            lines.append(f"- **{o['title']}** ({meta}) — {summary}  [{url}]")
        lines.append("")

    # --- Concepts ---
    lines.append(f"## Concepts ({len(concepts)})")
    lines.append("")
    lines.append("Concept pages are discovery aids — brief orientations with links to better sources.")
    lines.append("")
    for c in concepts:
        url = f"{site_url}/concepts/{c['slug']}/"
        summary_str = f" — {c['summary']}" if c["summary"] else ""
        lines.append(f"- **{c['title']}** (`{c['slug']}`){summary_str}  [{url}]")
    lines.append("")

    # --- Navigation hints ---
    lines += [
        "---",
        "",
        "## Key pages",
        "",
        f"- Organisation index (sortable table): {site_url}/organisations/",
        f"- Concept index: {site_url}/concepts/",
        f"- Knowledge graph (org↔concept relationships): {site_url}/graph/",
        f"- Blog (event posts, meetup summaries): {site_url}/blog/",
        f"- About / philosophy: {site_url}/about/",
        "",
    ]

    return "\n".join(lines)


def on_pre_build(config):
    if frontmatter is None:
        return
    site_url = (config.get("site_url") or "").rstrip("/")
    content = build_llms_txt(site_url)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
