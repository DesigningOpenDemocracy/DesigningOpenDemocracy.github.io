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
  1. Among content sources (manual, dod, social, rss, ical, scrape), pick the
     most recent date that is within its staleness threshold.
  2. If no content source qualifies, fall back to site activity (sitemap)
     within its staleness threshold.
  3. If all sources are stale, fall back to the most recent across all sources.

The computed result is available two ways:
  - page.meta.computed_activity  — set per-page in on_page_context (used by organisation.html)
  - org_activity_cache Jinja2 global (keyed by slug) — pre-computed in on_pre_build and
    injected in on_env so the organisations index template can use it before individual
    org pages have been rendered.
"""

import glob
import os
from datetime import date

# Sources that indicate actual content publication (preferred)
CONTENT_SOURCES = ["manual", "dod", "social", "rss", "ical", "scrape"]
# Sources that indicate only site-level activity (fallback)
SITE_SOURCES = ["sitemap"]

# How many days before a source is considered stale and skipped in favour of
# a lower-priority but fresher source.
STALENESS_DAYS = {
    "manual":  730,   # human visit — strong, but visits are infrequent
    "dod":     730,   # same confidence as manual
    "social":  365,   # social presence decays as a signal within a year
    "rss":     365,   # actual content publication
    "ical":    365,   # calendar events — reliable structured feed like rss
    "scrape":  365,   # scraped news page date — same confidence as rss
    "sitemap": 180,   # weak signal (CMS can touch lastmod for any reason)
}

# Pre-computed cache populated by on_pre_build; slug → computed_activity dict.
# Injected as a Jinja2 global (org_activity_cache) in on_env so the org index
# template can use consistent selection logic even though it renders before
# individual org pages (before on_page_context has run on those pages).
_cache: dict = {}


def _parse_date(val):
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except ValueError:
        return None


def select_activity(activity, today=None):
    """Return a computed_activity dict for the given activity mapping, or None.

    Exported so data_export.py and other utilities can share the same logic.
    """
    if not activity or not isinstance(activity, dict):
        return None
    if today is None:
        today = date.today()

    # Step 1: freshest content signal within its staleness threshold
    best_content = None
    best_content_date = None
    for source in CONTENT_SOURCES:
        entry = activity.get(source)
        if not entry or not isinstance(entry, dict):
            continue
        d = _parse_date(entry.get("date"))
        if d is None:
            continue
        age = (today - d).days
        if age <= STALENESS_DAYS.get(source, 365) and (best_content_date is None or d > best_content_date):
            best_content_date = d
            best_content = {**entry, "method": source, "age_days": age, "date": d}

    if best_content:
        return best_content

    # Step 2: fall back to site activity (sitemap) if no content signals qualify
    for source in SITE_SOURCES:
        entry = activity.get(source)
        if not entry or not isinstance(entry, dict):
            continue
        d = _parse_date(entry.get("date"))
        if d is None:
            continue
        age = (today - d).days
        if age <= STALENESS_DAYS.get(source, 180):
            return {**entry, "method": source, "age_days": age, "date": d}

    # Step 3: all sources stale — prefer most recent content source; only use
    # site sources if no content dates exist at all.
    best = None
    best_date = None
    for source_group in [CONTENT_SOURCES, SITE_SOURCES]:
        for source in source_group:
            entry = activity.get(source)
            if not entry or not isinstance(entry, dict):
                continue
            d = _parse_date(entry.get("date"))
            if d and (best_date is None or d > best_date):
                best_date = d
                best = {**entry, "method": source, "age_days": (today - d).days, "date": d}
        if best:
            break  # don't fall through to site sources if any content date exists

    return best


def on_pre_build(config):
    """Pre-compute activity selection for all org pages.

    Populates _cache so on_env can inject it as a Jinja2 global before any
    page templates render.  This is needed because the organisations index
    page renders before individual org pages, so on_page_context hasn't run
    on those pages yet when the index template executes.
    """
    try:
        import frontmatter as _fm
    except ImportError:
        return

    _cache.clear()
    today = date.today()
    orgs_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
    for path in glob.glob(os.path.join(orgs_dir, "*.md")):
        if os.path.basename(path) == "organisations.md":
            continue
        try:
            post = _fm.load(path)
        except Exception:
            continue
        slug = os.path.basename(path)[:-3]
        ca = select_activity(post.metadata.get("activity"), today)
        if ca:
            _cache[slug] = ca


def on_env(env, config, files):
    """Inject pre-computed activity cache as a Jinja2 global."""
    env.globals["org_activity_cache"] = _cache


def on_page_context(context, page, config, nav):
    """Set page.meta.computed_activity for individual org page rendering."""
    activity = page.meta.get("activity")
    ca = select_activity(activity)
    if ca:
        page.meta["computed_activity"] = ca
    return context
