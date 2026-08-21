"""
Registers the `insert_after_heading` Jinja filter used by
docs/overrides/partials/post.html to show each post's category/tag chips
directly under its title in the blog listing pages (blog/index.html,
heartbeat/index.html).

The blog plugin's excerpt HTML (`post.content`) has the post's title
synthesized as its own leading heading (e.g. `<h2 class="toclink">...`),
linked to the full post — there's no separate template hook to insert
content between that heading and the rest of the excerpt body, since it's
all one rendered HTML blob. This filter does a simple string insertion
right after the first closing heading tag, mirroring the render-time HTML
post-processing pattern already used by hooks/footnote_fragments.py.
"""

import re

from markupsafe import Markup

_HEADING_CLOSE_RE = re.compile(r"</h[1-6]>", re.IGNORECASE)


def insert_after_heading(html, snippet):
    if not html or not snippet:
        return html
    text = str(html)
    match = _HEADING_CLOSE_RE.search(text)
    if not match:
        return html
    pos = match.end()
    return Markup(text[:pos] + str(snippet) + text[pos:])


def on_env(env, config, files):
    env.filters["insert_after_heading"] = insert_after_heading
    return env
