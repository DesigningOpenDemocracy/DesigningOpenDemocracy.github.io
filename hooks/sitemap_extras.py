"""
sitemap_extras.py — MkDocs hook: list the machine-readable data endpoints
in sitemap.xml.

MkDocs builds sitemap.xml by iterating `pages` — the rendered markdown
documentation pages — so nothing that isn't a page is ever listed, including
every data export the build itself generates (hooks/data_export.py,
hooks/calendar_export.py, hooks/citation_export.py, hooks/llms_txt.py).
They are linked from /organisations/ and /calendar/, so a crawler that walks
those pages does reach them, but a tool acting on a search result rather than
on a crawl has no way to learn the URLs exist at all. That's the gap this
closes: the exports get their own sitemap entries instead of being reachable
only by transitive discovery.

The list is curated rather than "everything under docs/data/", because that
directory also holds build *input* and internal state that is not published
interface: the per-org iCal sync cache (data/events/<slug>.json, one file per
org), the citation evidence cache, elections.yml. Listing those would dilute
the sitemap rather than add to it. What's here is exactly the set CLAUDE.md
documents under "Data exports", plus the calendar feed and llms.txt — keep
the two in step when an export is added or dropped.

Two deliberate omissions:

  - The per-country calendar feeds (/calendar-<CC>.ics, one per country with
    an upcoming event, plus /calendar-elections.ics) are slices of
    /calendar.ics, and /calendar/ already lists every one of them in its
    feeds table. The canonical feed is the one worth a sitemap entry.
  - graph.json, which hooks/graph_builder.py writes straight into site_dir
    during on_post_build — after this hook runs and after sitemap.xml has
    been rendered. There would be nothing on disk to check it against at the
    point the list is built, and an unverifiable entry is exactly what the
    existence check below exists to prevent.

No <lastmod> is emitted. These files are rewritten on every build whether or
not their content changed, so a build-time lastmod would claim a change on
every deploy — search engines discount a lastmod that behaves that way, and
it would be a false statement besides. MkDocs' own page entries omit it on
the same grounds unless a page carries a real update_date.
"""

import os

# Published data endpoints, as paths relative to docs_dir. Mirrors CLAUDE.md's
# "Data exports" table plus the calendar feed and the llms.txt index.
DATA_ENDPOINTS = (
    "llms.txt",
    "data/organisations.csv",
    "data/organisations.json",
    "data/organisations.geojson",
    "data/organisations.kml",
    "data/org-concepts.csv",
    "data/citations.json",
    "data/events.json",
    "calendar.ics",
)


def data_endpoint_urls(docs_dir, site_url=""):
    """Absolute URLs for every declared endpoint that was actually written.

    A generator that was skipped or failed leaves no file behind, and an
    entry pointing at a file the build never produced is a 404 advertised to
    every crawler that reads the sitemap — so existence on disk, not the
    declaration above, decides what gets listed.

    Falls back to root-relative paths when the site has no `site_url`, which
    is what MkDocs' own sitemap entries degrade to in that case (`abs_url`).
    """
    base = (site_url or "").rstrip("/")
    return [
        f"{base}/{rel}"
        for rel in DATA_ENDPOINTS
        if os.path.isfile(os.path.join(docs_dir, rel))
    ]


def on_env(env, config, files):
    """Expose the endpoint list to docs/overrides/sitemap.xml.

    on_env runs after every generator's on_pre_build and before MkDocs
    renders its static templates, so the files are on disk to be checked and
    the global is in place by the time sitemap.xml is rendered.
    """
    env.globals["sitemap_extra_urls"] = data_endpoint_urls(
        config["docs_dir"], config.get("site_url") or ""
    )
    return env
