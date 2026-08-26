"""Registers a `tag_url` Jinja filter that links a raw tag: frontmatter
string to its entry on the site-wide tags listing page (docs/tags.md,
built by mkdocs-material's tags plugin from its `<!-- material/tags -->`
directive).

Needed because the tags plugin only resolves a tag name to a {name, url}
object for the page actually being rendered (see plugin.py's
on_page_context) — that's enough for a post's own page, which uses
Material's stock partials/tags.html, but docs/overrides/partials/post.html
renders *other* posts' raw tags: frontmatter as excerpt cards on the blog
index, where no such per-page resolution has happened. Rather than
reimplementing tag-to-listing resolution generally, this hard-codes the one
listing page this site actually has (tags.md, at the fixed URL /tags/) and
replicates the exact slug format mkdocs-material's tags plugin computes for
it (`tags_slugify_format` "tag:{slug}" over `pymdownx.slugs.slugify`,
material/plugins/tags/structure/listing/manager/__init__.py's _slugify) —
importing the same slugify function from pymdownx (already a dependency of
mkdocs-material) rather than hand-rolling one that could drift from
whatever the plugin actually does under the hood.
"""
from pymdownx.slugs import slugify as _pymdownx_slugify

_slugify = _pymdownx_slugify(case="lower")


def tag_url(tag):
    return "/tags/#tag:" + _slugify(str(tag), "-")


def on_env(env, config, files):
    env.filters["tag_url"] = tag_url
