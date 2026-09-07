"""
heartbeat_current.py — MkDocs hook that renders docs/heartbeat/current.md
from whichever heartbeat post currently has draft: true, computed at
build time.

Previously this page's body was a manually-maintained second copy of the
active draft, kept in sync by running `util/heartbeat_post.py --mirror`
after every edit. That copy could silently go stale if a run forgot the
extra step. Single-sourcing at build time removes the step entirely: the
only thing on disk is the actual post in docs/heartbeat/posts/, and this
page always reflects whatever that file currently says.

If no draft: true post exists (nothing accumulating, or this month's post
was just released), the page falls back to a placeholder.

A metadata line (date, ai_generated badge, tags) is prepended above the
mirrored body — a real released post shows this in its sidebar via the
blog plugin's own post decoration, which this page never gets since it
isn't a blog-plugin post, just a plain doc page. Built directly from the
draft's frontmatter rather than trying to reuse docs/overrides/blog-post.html's
sidebar markup, since that template relies on page.authors/page.categories
objects the blog plugin populates only for actual posts.
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tag_links import tag_url  # noqa: E402

MARKER = "<!-- HEARTBEAT_CURRENT_BODY -->"

PLACEHOLDER = (
    "*No draft is currently accumulating. Check back after the next scheduled\n"
    "heartbeat run.*\n"
)

AI_LABELS = {
    "generated": "AI-generated",
    "drafted": "AI-drafted, human-reviewed & revised",
    "collaborated": "Human-AI collaboration",
    "reviewed": "Human-authored, AI-reviewed & edited",
    "assisted": "AI-assisted",
}


def _find_active_draft(docs_dir):
    """Return the frontmatter.Post of the single draft: true heartbeat post, or None.

    Raises if more than one is found — the whole heartbeat system assumes at
    most one draft: true post exists at a time (see HEARTBEAT.md Step 6 and
    util/heartbeat_post.py's find_active_draft). Silently picking one would
    hide a real process violation instead of surfacing it.
    """
    try:
        import frontmatter
    except ImportError:
        return None
    posts_dir = os.path.join(docs_dir, "heartbeat", "posts")
    candidates = []
    for path in sorted(glob.glob(os.path.join(posts_dir, "*-sync.md"))):
        post = frontmatter.load(path)
        if post.metadata.get("draft") is True:
            candidates.append((path, post))
    if len(candidates) > 1:
        paths = ", ".join(p for p, _ in candidates)
        raise RuntimeError(
            f"heartbeat_current.py: found {len(candidates)} draft:true heartbeat "
            f"posts ({paths}) — expected at most one. Resolve (release or delete "
            f"the stale one) before building."
        )
    return candidates[0][1] if candidates else None


def _extract_body(post):
    """Body content from the first '## ' heading onward (drops the teaser
    line, <!-- more -->, and disclaimer — this page doesn't need those)."""
    m = re.search(r"^##\s", post.content, re.MULTILINE)
    return post.content[m.start():].rstrip() + "\n" if m else post.content.rstrip() + "\n"


def _meta_block(post):
    """Date/AI-badge/tags line, mirroring what a released post's sidebar shows."""
    meta = post.metadata
    parts = []

    date_val = meta.get("date")
    if date_val:
        parts.append(f"<strong>Started:</strong> {date_val}")

    ai_level = meta.get("ai_assist") or ("generated" if meta.get("ai_generated") else None)
    if ai_level:
        label = AI_LABELS.get(ai_level, ai_level)
        parts.append(f'<span class="ai-assist-badge ai-assist-{ai_level}">{label}</span>')

    tags = meta.get("tags") or []
    if tags:
        chips = " ".join(f'<a class="concept-tag" href="{tag_url(t)}">{t}</a>' for t in tags)
        parts.append(f"<strong>Tags:</strong> {chips}")

    if not parts:
        return ""
    return '<p class="heartbeat-current-meta">' + " &nbsp;·&nbsp; ".join(parts) + "</p>\n\n"


def on_page_markdown(markdown, *, page, config, files):
    if page.file.src_path != "heartbeat/current.md" or MARKER not in markdown:
        return markdown
    post = _find_active_draft(config["docs_dir"])
    body = (_meta_block(post) + _extract_body(post)) if post else PLACEHOLDER
    return markdown.replace(MARKER, body)
