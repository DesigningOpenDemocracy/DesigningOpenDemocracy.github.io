"""
activity_selector.py — MkDocs hook that resolves page.meta.activity into
a single display-ready page.meta.computed_activity entry.

Schema expected in org frontmatter:
    activity:
      rss:
        date: YYYY-MM-DD
        note: "Latest post: ..."
        url: https://...
      sitemap:
        date: YYYY-MM-DD
        note: "Page last modified (from sitemap)"
      manual:
        date: YYYY-MM-DD
        note: "Visited site, confirmed active"

Selection logic:
  1. Walk sources in priority order: manual > dod > social > rss > sitemap
  2. Use the first source whose date is within its staleness threshold
  3. If none qualify (all stale), fall back to the most recent across all sources
"""

from datetime import date

PRIORITY = ["manual", "dod", "social", "rss", "sitemap"]

# How many days before a source is considered stale and skipped in favour of
# a lower-priority but fresher source.
STALENESS_DAYS = {
    "manual":  10 * 365,   # human-verified — essentially never stale
    "dod":     10 * 365,
    "social":  10 * 365,
    "rss":     365,         # prefer rss over sitemap if < 1 year old
    "sitemap": 10 * 365,
}


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
    activity = page.meta.get("activity")
    if not activity or not isinstance(activity, dict):
        return context

    today = date.today()

    # Walk in priority order, pick first fresh-enough source
    for source in PRIORITY:
        entry = activity.get(source)
        if not entry or not isinstance(entry, dict):
            continue
        d = _parse_date(entry.get("date"))
        if d is None:
            continue
        age = (today - d).days
        if age <= STALENESS_DAYS.get(source, 365):
            page.meta["computed_activity"] = {**entry, "method": source, "age_days": age, "date": d}
            return context

    # All sources stale — fall back to most recent
    best = None
    best_date = None
    for source in PRIORITY:
        entry = activity.get(source)
        if not entry or not isinstance(entry, dict):
            continue
        d = _parse_date(entry.get("date"))
        if d and (best_date is None or d > best_date):
            best_date = d
            best = {**entry, "method": source, "age_days": (today - d).days, "date": d}

    if best:
        page.meta["computed_activity"] = best

    return context
