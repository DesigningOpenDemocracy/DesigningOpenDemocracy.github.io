"""
draft_exclude.py — mkdocs hook: exclude draft: true blog/heartbeat posts
from the Files collection before literate-nav builds the navigation tree.

Bug this fixes: a draft: true post gets no built page (confirmed — no URL
exists for it) but its title still appeared as a dead link in the blog's
left-nav sidebar, pointing at a URL that 404s. Root cause: the blog
plugin's own draft-exclusion (mkdocs-material's blog plugin, which marks
file.inclusion = EXCLUDED) runs at event_priority(-50) by the plugin's own
design, deliberately late so other plugins can add generated posts/views
first. literate-nav runs at the default priority (0), i.e. earlier, and
attaches a nav entry for any unlisted markdown file under a section
(here, docs/blog/posts/) without checking file.inclusion — because at the
point literate-nav runs, the blog plugin hasn't marked the draft excluded
yet. By the time the blog plugin does mark it, literate-nav's nav tree
already has a stale reference to a page that will never be built.

Fix: mark draft posts excluded ourselves, before literate-nav ever sees
them, using event_priority(100) to guarantee this runs first regardless
of hooks:/plugins: declaration order. Reading frontmatter directly (not
importing the blog plugin's own post-resolution) keeps this hook simple
and independent of mkdocs-material internals.
"""

import yaml
from mkdocs.plugins import event_priority
from mkdocs.structure.files import InclusionLevel

_POST_DIRS = ("blog/posts/", "heartbeat/posts/")


def _is_draft(abs_src_path):
    try:
        with open(abs_src_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return False
    if not content.startswith("---"):
        return False
    end = content.find("\n---", 3)
    if end == -1:
        return False
    try:
        meta = yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return False
    return bool(meta.get("draft"))


@event_priority(100)
def on_files(files, *, config):
    for file in files:
        if not file.src_uri.endswith(".md"):
            continue
        if not file.src_uri.startswith(_POST_DIRS):
            continue
        if _is_draft(file.abs_src_path):
            file.inclusion = InclusionLevel.EXCLUDED
    return files
