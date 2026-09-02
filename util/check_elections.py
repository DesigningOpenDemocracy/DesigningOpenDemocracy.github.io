#!/usr/bin/env python3
"""
check_elections.py — validates docs/data/elections.yml, the curated list of
polling days the site-wide calendar carries alongside org events.

Local/offline, no network calls. Wired into CI and the pre-commit hook as a
hard gate, the same way check_event_sourcing.py gates org `events:` and
check_footnote_quotes.py gates prose footnotes — and for the same reason.
An election date is the one thing on this calendar a reader might act on
without clicking through (turning up to vote, or planning around a
campaign), so an unsourced or malformed one is worse than no entry at all:
hooks/calendar_export.py deliberately *skips* a malformed entry rather than
crashing the build, which means without this gate a typo'd date would
silently disappear from the calendar with nothing said.

Hard gates (exit 1):
  NOT SOURCED     — neither url: nor source:
  NO PROOF        — neither quote: nor note:
  BAD DATE        — date: missing or not YYYY-MM-DD (same for end_date:)
  BAD END DATE    — end_date: earlier than date:
  BAD LEVEL       — level: outside national/state/local/supranational
  BAD DATE STATUS — date_status: outside fixed/expected/deadline
  BAD COUNTRY     — country: missing, not two uppercase letters, or not in
                    calendar_export.py's _COUNTRY_NAMES (an unknown code
                    renders as the bare code and gets no flag, and the
                    per-country .ics feed it lands in would be unnamed)
  DUPLICATE       — two entries for the same country/jurisdiction/date/title
  UNKNOWN FIELD   — a key outside the documented schema, which is nearly
                    always a typo silently dropping whatever it meant

Soft warnings (printed, do not fail the build):
  PAST            — the election has been held; replace the entry with the
                    next one for that jurisdiction (the calendar drops it
                    either way, so a stale entry is invisible, not wrong)
  VAGUE SOURCE    — source: under 20 characters, matching
                    check_event_sourcing.py's bar for the same field
  NO DATE NOTE    — date_status: expected/deadline without a date_note:
                    saying where the date comes from
  STALE CHECK     — url_checked: missing or older than 365 days, matching
                    check_event_sourcing.py's STALE_CHECK_DAYS

Usage:
    python util/check_elections.py
    python util/check_elections.py --country AU
    python util/check_elections.py --file path/to/elections.yml
"""

import argparse
import importlib.util
import os
import sys
from datetime import date, datetime

import yaml

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ELECTIONS_FILE = os.path.join(REPO_ROOT, "docs", "data", "elections.yml")

# Same window check_event_sourcing.py uses for url_checked: on org events —
# one bar for "this citation needs re-reading", not two.
STALE_CHECK_DAYS = 365
MIN_SOURCE_LEN = 20

KNOWN_FIELDS = {
    "date", "end_date", "country", "jurisdiction", "level", "title",
    "date_status", "date_note", "url", "source", "quote", "note",
    "url_checked",
}


def _calendar_export():
    """Import hooks/calendar_export.py for the vocabularies it renders from.

    The hook is the thing that actually has to display an entry, so it owns
    the level labels, the date_status labels, and the country-name map. This
    linter checking a second copy of any of them would let the two drift
    until a lint-clean entry rendered as a bare country code with no flag."""
    path = os.path.join(REPO_ROOT, "hooks", "calendar_export.py")
    spec = importlib.util.spec_from_file_location("calendar_export", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_date(val, field):
    """Return (date, error). A YAML date: line parses to a datetime.date by
    itself; anything else has to be an exact ISO string — a permissive
    parser here would be guessing at what a typo meant."""
    if val is None:
        return None, f"{field}: is missing"
    if isinstance(val, datetime):
        return val.date(), None
    if isinstance(val, date):
        return val, None
    try:
        return date.fromisoformat(str(val).strip()), None
    except ValueError:
        return None, f"{field}: {val!r} is not a YYYY-MM-DD date"


def check_entry(entry, index, levels, statuses, countries, today):
    """Return (errors, warnings) for one election entry."""
    errors, warnings = [], []
    label = entry.get("title") or f"entry #{index + 1}"

    if not isinstance(entry, dict):
        return [(f"entry #{index + 1}", "BAD ENTRY", "not a mapping")], []

    unknown = sorted(set(entry) - KNOWN_FIELDS)
    if unknown:
        errors.append((label, "UNKNOWN FIELD", ", ".join(unknown)))

    d, err = _parse_date(entry.get("date"), "date")
    if err:
        errors.append((label, "BAD DATE", err))
    elif d < today:
        warnings.append((label, "PAST", f"held on {d.isoformat()} — replace with the next one for this jurisdiction"))

    if entry.get("end_date") is not None:
        end, err = _parse_date(entry.get("end_date"), "end_date")
        if err:
            errors.append((label, "BAD DATE", err))
        elif d and end < d:
            errors.append((label, "BAD END DATE", f"{end.isoformat()} is before date: {d.isoformat()}"))

    if not entry.get("url") and not entry.get("source"):
        errors.append((label, "NOT SOURCED", "needs a url: or a source:"))
    source = entry.get("source")
    if source and len(str(source).strip()) < MIN_SOURCE_LEN:
        warnings.append((label, "VAGUE SOURCE", f"{source!r} is too short to locate the claim"))

    if not entry.get("quote") and not entry.get("note"):
        errors.append((label, "NO PROOF", "needs a quote: (verbatim) or a note: (paraphrase)"))

    level = entry.get("level")
    if level not in levels:
        errors.append((label, "BAD LEVEL", f"{level!r} — expected one of {', '.join(sorted(levels))}"))

    status = entry.get("date_status")
    if status not in statuses:
        errors.append((label, "BAD DATE STATUS", f"{status!r} — expected one of {', '.join(sorted(statuses))}"))
    elif status != "fixed" and not entry.get("date_note"):
        warnings.append((label, "NO DATE NOTE", f"date_status: {status} without a date_note: saying where the date comes from"))

    country = entry.get("country")
    if not isinstance(country, str) or len(country) != 2 or not country.isupper():
        errors.append((label, "BAD COUNTRY", f"{country!r} — expected an ISO 3166-1 alpha-2 code"))
    elif country not in countries:
        errors.append((label, "BAD COUNTRY", f"{country!r} is not in calendar_export.py's _COUNTRY_NAMES — "
                                             "add it there so the entry gets a name and a flag"))

    checked, err = _parse_date(entry.get("url_checked"), "url_checked") if entry.get("url_checked") else (None, None)
    if err:
        errors.append((label, "BAD DATE", err))
    elif checked is None:
        warnings.append((label, "STALE CHECK", "no url_checked: — record when the citation was last read"))
    elif (today - checked).days > STALE_CHECK_DAYS:
        warnings.append((label, "STALE CHECK", f"url_checked: {checked.isoformat()} is over {STALE_CHECK_DAYS} days old"))

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description="Validate the curated election dates feeding the calendar.")
    ap.add_argument("--file", default=ELECTIONS_FILE, help="elections YAML file to check")
    ap.add_argument("--country", action="append", help="only check entries for this ISO country code (repeatable)")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"No elections file at {args.file} — nothing to check.")
        sys.exit(0)

    with open(args.file, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            print(f"FAILED: {args.file} is not valid YAML:\n  {exc}")
            sys.exit(1)

    entries = data.get("elections")
    if entries is None:
        print(f"FAILED: {args.file} has no top-level `elections:` list.")
        sys.exit(1)
    if not isinstance(entries, list):
        print(f"FAILED: `elections:` in {args.file} is a {type(entries).__name__}, not a list.")
        sys.exit(1)

    ce = _calendar_export()
    levels = set(ce.ELECTION_LEVEL_LABELS)
    statuses = set(ce.ELECTION_DATE_STATUS_LABELS)
    countries = set(ce._COUNTRY_NAMES)
    today = date.today()

    wanted = {c.upper() for c in args.country} if args.country else None

    errors, warnings, seen = [], [], {}
    checked_count = 0
    for i, entry in enumerate(entries):
        if wanted and isinstance(entry, dict) and entry.get("country") not in wanted:
            continue
        checked_count += 1
        e, w = check_entry(entry, i, levels, statuses, countries, today)
        errors.extend(e)
        warnings.extend(w)

        if isinstance(entry, dict):
            key = (entry.get("country"), entry.get("jurisdiction"),
                   str(entry.get("date")), entry.get("title"))
            if key in seen:
                errors.append((entry.get("title") or f"entry #{i + 1}", "DUPLICATE",
                               f"same country/jurisdiction/date/title as entry #{seen[key] + 1}"))
            else:
                seen[key] = i

    print(f"Elections checked: {checked_count}")
    upcoming = sum(1 for e in entries if isinstance(e, dict)
                   and _parse_date(e.get("date"), "date")[0]
                   and _parse_date(e.get("date"), "date")[0] >= today)
    print(f"  upcoming (will appear on the calendar): {upcoming}")

    if warnings:
        print()
        print("Warnings (not a build failure):")
        for label, kind, detail in warnings:
            print(f"  {kind}: {label} — {detail}")

    if errors:
        print()
        print("FAILED:")
        for label, kind, detail in errors:
            print(f"  {kind}: {label} — {detail}")
        print()
        print(f"{len(errors)} problem(s) in {args.file}. See that file's header for the schema.")
        sys.exit(1)

    print("\nAll election entries are sourced and well-formed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
