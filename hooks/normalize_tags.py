"""Fold tag spellings together so one topic is one tag.

Material's tags plugin treats every distinct tag *string* as its own tag,
but the anchor it gives each section on the tags index is a slug of that
string. Two spellings of one topic therefore produce two sections sharing
one id — and since the plugin sorts case-sensitively, every `Title Case`
tag sorts above every `lowercase` one, so the two halves land far apart on
the page. A browser jumps to the first of the duplicate ids, so
`/tags/#tag:deliberative-democracy` showed a single 2021 podcast while the
five pages actually carrying that tag sat 45 KB further down, unreachable
by the link. 18 slugs were split this way, `#democracy` (5 vs 13 pages)
and `#podcast` (7 vs 5) worst among them.

Normalising here rather than only in the source files is what keeps it
fixed: a contributor writing `Citizens Assembly` gets folded in with
`citizens-assembly` instead of silently splitting the tag again. The
alternative — `tags_allowed:`, which fails the build on any tag outside a
listed vocabulary — was deliberately not used: new topics get tagged on
this site all the time, and a gate that blocks them is the wrong trade for
a problem that is really about spelling, not vocabulary.

Runs at priority 100 so it lands well before the tags plugin collects
`page.meta["tags"]` in its own `on_page_markdown` (priority -50).
"""

from mkdocs.plugins import event_priority
from pymdownx.slugs import slugify as _pymdownx_slugify

# The same slugify the tags plugin itself uses to build the anchor ids
# (`tags_slugify_format` over `pymdownx.slugs.slugify`), for the same
# reason hooks/tag_links.py imports it rather than hand-rolling one: a
# local approximation could drift from what the plugin actually computes,
# and folding on a different rule than the plugin anchors on would put the
# duplicate sections right back. Keep these two hooks in step.
_slugify = _pymdownx_slugify(case="lower")


def normalize_tag(tag):
    return _slugify(str(tag), "-")


@event_priority(100)
def on_page_markdown(markdown, page, config, files):
    tags = page.meta.get("tags")
    if not tags:
        return

    seen = set()
    folded = []
    for tag in tags:
        slug = normalize_tag(tag)
        # A page carrying both spellings of one tag would otherwise list
        # itself twice in that tag's section.
        if slug and slug not in seen:
            seen.add(slug)
            folded.append(slug)

    page.meta["tags"] = folded
