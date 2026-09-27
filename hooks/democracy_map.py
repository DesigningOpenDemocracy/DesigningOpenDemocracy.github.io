"""
democracy_map.py — MkDocs hook: which organisations the Democracy Map
(/map/, docs/overrides/democracy-map.html) shows, and the link other pages
use to open the map on one.

There is one map. Rather than a second copy on the Democracy Landscape index
(two sets of filter and popup code to keep in step), the index's
quick-profile card and every org page link into it: `/map/?org=<slug>` zooms
to that org and opens its card (see the end of democracy-map.html's script).
The map's own popups link back to the org's profile, so the two views are
one click apart both ways. The map used to sit at the bottom of the home
page, which now carries a teaser card whose counts come from the same rule.

The inclusion rule lives here, not in each template, because the templates
must agree on it: a "Show on map" link rendered for an org the map left out
would open the map on nothing, with nothing to say why. The map's marker
loop, the home page teaser and both org templates use the `on_democracy_map`
test registered below.
"""


# Not named on_*: MkDocs registers every module-level on_<name> function in
# a hook file as a handler for event <name>, and fails the build on an
# unknown one.
def is_on_map(meta):
    """True when an org page's frontmatter puts it on the Democracy Map:
    active, with a location that has both coordinates."""
    if not meta:
        return False
    loc = meta.get("location") or {}
    return (
        meta.get("status") == "active"
        and bool(loc.get("latitude"))
        and bool(loc.get("longitude"))
    )


def map_url(slug):
    """URL that opens the Democracy Map on this org."""
    return f"/map/?org={slug}"


def on_env(env, config, files):
    env.tests["on_democracy_map"] = is_on_map
    env.filters["democracy_map_url"] = map_url
    return env
