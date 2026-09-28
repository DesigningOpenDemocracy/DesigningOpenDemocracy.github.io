"""
backoff.py — one retry schedule for anything DOD's scripts keep failing to fetch.

Before this, a failure was forgotten as soon as a run ended. A feed that
404s, a citation whose site has gone, a host that no longer resolves: each
was requested again on the next weekly run, and the one after, forever,
because nothing recorded that it had failed last time. Only 403/429 were
remembered (check_fragments.py's sticky "blocked" cache), since those mean
"this server doesn't want scripted requests". Everything else counted as
"try again later", with no later ever arriving.

The rule here: record each failure, and don't ask again until the retry
interval has passed. The interval starts at a week (the probe cron's own
cadence, so one failure costs nothing extra) and doubles with each
consecutive failure up to a quarter: 7, 14, 28, 56, then 90 days. A single
success clears the record. So a transient outage costs one skipped week at
most, while a site that's really gone is asked about four times a year
rather than fifty-two, and still gets noticed if it comes back.

A failure record is a small dict, stored beside whatever else the calling
script keeps about that URL:

    {"error": "HTTP_404", "since": "2026-09-28", "count": 3, "last": "2026-10-26"}

`since` is the first failure in the current run of failures, `last` the most
recent attempt. Used by check_rss.py (docs/data/feeds/<slug>.json) and by
check_fragments.py / check_event_urls.py (docs/data/citation-state.json,
shared, so a URL either script finds dead is backed off for both).
"""

import hashlib
from datetime import date, timedelta

FIRST_RETRY_DAYS = 7
MAX_RETRY_DAYS = 90


def as_date(value):
    """An ISO date string (or date) as a date, or None."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def retry_days(count):
    """Days to wait after the count-th consecutive failure."""
    count = max(int(count or 1), 1)
    return min(FIRST_RETRY_DAYS * 2 ** (count - 1), MAX_RETRY_DAYS)


def next_try(failing):
    """The first date a failing URL may be requested again, or None if the
    record has no usable date (treated as "try now")."""
    if not failing:
        return None
    last = as_date(failing.get("last"))
    if last is None:
        return None
    return last + timedelta(days=retry_days(failing.get("count")))


def backing_off(failing, today=None):
    """True while a failing URL's retry interval hasn't passed yet."""
    retry = next_try(failing)
    return retry is not None and (today or date.today()) < retry


def record_failure(failing, error, today=None):
    """The failure record after one more failed attempt."""
    today = today or date.today()
    prior = failing or {}
    return {
        "error": error,
        "since": prior.get("since") or today.isoformat(),
        "count": int(prior.get("count") or 0) + 1,
        "last": today.isoformat(),
    }


def spread_days(key, window):
    """A deterministic 0..window/2 day offset for `key`, for spreading work
    that would otherwise all fall due on one day. Keyed on a hash rather
    than random, so a given key's due date is stable across runs and
    machines (the same trick check_fragments.py's staleness_offset() uses).
    Subtract it from the window, never add, so the window stays a ceiling."""
    if window <= 1:
        return 0
    digest = hashlib.sha256(str(key).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, window // 2)
