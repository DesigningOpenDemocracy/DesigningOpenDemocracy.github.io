"""
org_events.py — MkDocs hook that splits an org's `events:` frontmatter list
into page.meta.upcoming_events / page.meta.history_events for organisation.html.

Schema expected in org frontmatter:
    events:
      - date: YYYY-MM-DD
        title: "Founded during COVID lockdown protests"
        url: https://...      # optional

Manually curated per org — separate from hooks/calendar_export.py, which
aggregates *future* events (from this same field, plus ics_feed syncs) across
every org for the site-wide calendar page. This hook only concerns a single
org's own page: it shows both directions (past and future), the aggregator
only ever shows future.

Also registers two Jinja filters (via on_env):
  - `with_fragment` — organisation.html uses this to build an event's link
    href. A #:~:text= fragment is derived from quote: at render time here
    rather than stored in url: — see util/text_fragment.py's docstring for
    why (single source of truth, no risk of the two drifting apart).
  - `archive_url_for` — looks up a citation url's Wayback Machine snapshot
    (recorded by `util/check_fragments.py --save-to-wayback`), for
    rendering an additional Robust-Links-style archive link alongside the
    normal citation link. Loaded once at env setup, not per-page, since
    the cache is a single shared file.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import load_archive_urls, with_fragment  # noqa: E402


def _parse_date(val):
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def on_page_context(context, page, config, nav):
    events = page.meta.get("events")
    if not events:
        return context

    today = date.today()
    upcoming, history = [], []
    for entry in events:
        d = _parse_date(entry.get("date"))
        if d is None:
            continue
        item = {**entry, "date": d}
        (upcoming if d >= today else history).append(item)

    upcoming.sort(key=lambda e: e["date"])
    history.sort(key=lambda e: e["date"], reverse=True)

    if upcoming:
        page.meta["upcoming_events"] = upcoming
    if history:
        page.meta["history_events"] = history
    return context


def on_env(env, config, files):
    env.filters["with_fragment"] = with_fragment
    archive_urls = load_archive_urls()
    env.filters["archive_url_for"] = lambda url: archive_urls.get(url)
