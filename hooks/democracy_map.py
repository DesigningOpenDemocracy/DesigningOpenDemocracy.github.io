"""
democracy_map.py — MkDocs hook: which organisations the home page's
Democracy Map shows, and the link other pages use to open the map on one.

There is one map, on the home page. Rather than a second copy on the
Democracy Landscape index (two sets of filter and popup code to keep in
step), the index's quick-profile card and every org page link into it:
`/?org=<slug>` scrolls the home page to the map, zooms to that org and opens
its card (see the end of home.html's map script). The map's own popups link
back to the org's profile, so the two views are one click apart both ways.

The inclusion rule lives here, not in each template, because the templates
must agree on it: a "Show on map" link rendered for an org the map left out
would open the map on nothing, with nothing to say why. home.html's marker
loop and both org templates use the `on_democracy_map` test registered below.
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
    """Home page URL that opens the Democracy Map on this org."""
    return f"/?org={slug}"


def on_env(env, config, files):
    env.tests["on_democracy_map"] = is_on_map
    env.filters["democracy_map_url"] = map_url
    return env
