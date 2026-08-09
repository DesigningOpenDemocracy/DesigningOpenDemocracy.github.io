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
"""

from datetime import date


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
