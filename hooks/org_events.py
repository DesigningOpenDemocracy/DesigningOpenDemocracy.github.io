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
every org for the site-wide calendar page. That aggregator only ever shows
future events; the per-org timeline this hook feeds shows both directions.

Also registers, via on_env, one Jinja global:
  - `org_event_highlight` — slug → the single event worth putting on the
    Democracy Landscape index's quick-profile card (see select_highlight()
    for which one that is and why), pre-formatted for display. Keyed by slug
    and built as a whole-corpus pass for the same reason
    hooks/activity_selector.py's `org_activity_cache` is: docs/organisations/
    index.md renders in the same pass as every other page, so it cannot read
    another org page's on_page_context output. It CAN read another page's
    meta — MkDocs populates every page before firing on_env — which is why
    this is built here off `files` rather than re-reading frontmatter from
    disk the way activity_selector.py does.

and three Jinja filters:
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


# ── Quick-profile highlight (Democracy Landscape index cards) ────────────
# slug → select_highlight() output. Populated in on_env, injected as the
# `org_event_highlight` Jinja global. See the module docstring for why this
# is a whole-corpus pass rather than per-page state.
_highlight_cache: dict = {}

# notable: is three-valued (see CLAUDE.md's events: docs). Ranked, not just
# tested, because the card has room for exactly one event and has to be able
# to say which of several past ones is the most major.
_NOTABLE_RANK = {True: 2, "medium": 1}

# The card is a quick read, not the org page. A note:/quote: written for the
# timeline can run several sentences; past this it is cut on a word boundary.
HIGHLIGHT_BLURB_CHARS = 220

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _notable_rank(entry):
    return _NOTABLE_RANK.get(entry.get("notable"), 0)


def _display_date(d):
    """2026-09-15 → '15 Sep 2026'. Deliberately not strftime('%-d %b %Y'),
    whose no-pad flag is glibc-only and silently differs on other platforms."""
    return "{} {} {}".format(d.day, _MONTHS[d.month - 1], d.year)


def _blurb(text):
    """Trim a note:/quote: to card length on a word boundary."""
    text = " ".join(str(text).split())
    if len(text) <= HIGHLIGHT_BLURB_CHARS:
        return text
    cut = text[:HIGHLIGHT_BLURB_CHARS].rsplit(" ", 1)[0].rstrip(",;:.—-")
    return cut + "…"


def select_highlight(events, today=None):
    """Pick the one event worth showing on an org's quick-profile card.

    A reader scanning the Democracy Landscape is asking "is anything
    happening with this org?", so anything still ahead wins over anything
    behind it, however major the past one was — and among upcoming events
    the soonest is the one they could still turn up to. Notability is
    deliberately NOT consulted for that half: an org's only upcoming entry
    being a routine meeting is itself the answer to the question, and
    skipping it to advertise a 2011 founding instead would be a worse one.

    With nothing upcoming the question becomes "what was the last
    significant thing they did?", and there notable: leads: true, then
    "medium", then untiered, each tier resolved by recency. That ordering is
    the whole point of the tiers — a founding or a landmark launch is the
    answer even when a routine working-group check-in happened more
    recently. The card carries the org's last-activity date separately, so
    reaching back for a major event does not cost the reader the recency
    signal.

    Returns a display-ready dict, or None when the org lists no dated event.
    """
    if not events:
        return None
    if today is None:
        today = date.today()

    upcoming, past = [], []
    for entry in events:
        if not isinstance(entry, dict):
            continue
        d = _parse_date(entry.get("date"))
        if d is None:
            continue
        (upcoming if d >= today else past).append((d, entry))

    if upcoming:
        d, entry = min(upcoming, key=lambda pair: pair[0])
        kind = "upcoming"
    elif past:
        d, entry = max(past, key=lambda pair: (_notable_rank(pair[1]), pair[0]))
        kind = "past"
    else:
        return None

    # note: is editorial paraphrase and reads as a description; quote: is
    # source text and only stands in when there is no note:. Which one it is
    # has to travel with the text, since the template renders a quote as a
    # blockquote rather than passing off someone else's words as DOD's.
    blurb, blurb_is_quote = entry.get("note"), False
    if not blurb and entry.get("quote"):
        blurb, blurb_is_quote = entry["quote"], True

    end = _parse_date(entry.get("end_date"))
    return {
        "kind": kind,
        "date": d.isoformat(),
        "date_display": _display_date(d),
        "end_date_display": _display_date(end) if end and end != d else None,
        "time": entry.get("time"),
        # short_title: exists precisely for one-line contexts like this one.
        "title": entry.get("short_title") or entry.get("title") or "",
        "url": entry.get("url"),
        "blurb": _blurb(blurb) if blurb else None,
        "blurb_is_quote": blurb_is_quote,
        "notable": entry.get("notable"),
        "notable_reason": entry.get("notable_reason"),
    }


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

    _highlight_cache.clear()
    today = date.today()
    for file in files.documentation_pages():
        src_path = file.src_uri if hasattr(file, "src_uri") else file.src_path
        if not src_path.startswith("organisations/") or src_path.endswith("/index.md"):
            continue
        if not file.page:
            continue
        highlight = select_highlight(file.page.meta.get("events"), today)
        if highlight:
            _highlight_cache[os.path.basename(src_path)[:-3]] = highlight
    env.globals["org_event_highlight"] = _highlight_cache
