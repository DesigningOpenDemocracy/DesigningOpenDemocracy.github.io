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

Also registers three Jinja filters (via on_env):
  - `with_fragment` — organisation.html uses this to build an event's link
    href. A #:~:text= fragment is derived from quote: at render time here
    rather than stored in url: — see util/text_fragment.py's docstring for
    why (single source of truth, no risk of the two drifting apart).
  - `archive_info_for` — looks up a citation url's recorded Wayback
    Machine snapshot and url_status (both written by
    `util/check_fragments.py`'s `--save-to-wayback`/`--set-url-status`
    flags), returning {"archive_url":, "url_status":} or None.
    organisation.html uses this both to render an additional
    Robust-Links-style archive link alongside the normal citation link,
    and — once url_status is "dead"/"unfit" — to swap which link renders
    as primary (see internal-heartbeat/2026-08-22-citation-archival-
    design-decisions.md). Loaded once at env setup, not per-page, since
    the cache is a single shared file.
  - `coins_for` — builds a COinS <span class="Z3988"> for an event with a
    url:, the mechanism Zotero/EndNote/RefWorks already scan any page for
    to detect a citable reference with no separate file needed. When the
    event also carries a quote:, the span's evidence_sha256 key points at
    that quote's specific evidence[] entry in citations.json — see
    util/text_fragment.py's coins_context() and Appendix E of
    internal-heartbeat/machine-verifiable-citation.md for the full design
    this implements. Events without url: get no span (nothing to cite).
"""

import hashlib
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))
from text_fragment import (  # noqa: E402
    coins_span_html, load_archive_info, normalize_ws, with_fragment,
)


def _coins_for_event(e):
    quote = e.get("quote")
    evidence_id = (hashlib.sha256(normalize_ws(quote).encode("utf-8")).hexdigest()
                   if quote else None)
    return coins_span_html(e.get("url"), e.get("title"), e.get("date"), evidence_id)


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
    archive_info = load_archive_info()
    env.filters["archive_info_for"] = lambda url: archive_info.get(url)
    env.filters["coins_for"] = _coins_for_event
