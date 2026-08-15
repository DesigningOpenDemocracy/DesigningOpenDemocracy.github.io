"""
sync_events.py — fetch org iCal feeds and cache upcoming events for the site calendar.

For every org with `ics_feed:` set, fetches the feed and writes future events
(DTSTART >= today) to docs/data/events/<slug>.json. This cache is what
hooks/calendar_export.py reads at build time — the build itself never makes
network calls, only this script does, same division of labour as
check_rss.py's activity checks.

Usage:
  python util/sync_events.py                  # sync all active orgs with ics_feed:
  python util/sync_events.py --all             # include inactive orgs
  python util/sync_events.py --slug g0v        # single org
  python util/sync_events.py --dry-run         # print results without writing
  python util/sync_events.py --max-events 15   # cap events written per org (default 15)
  python util/sync_events.py --horizon-days 365  # only keep events this many days out (default 365)
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

import requests
from requests.exceptions import RequestException

try:
    import frontmatter
except ImportError:
    frontmatter = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
OUT_DIR = os.path.join(DOCS_DIR, "data", "events")
SKIP_FILES = {"index.md"}
USER_AGENT = "DOD-ICS-Reader/1.0 (democracy wiki)"


def parse_ical_date(val):
    """Parse a DTSTART value (YYYYMMDD or YYYYMMDDThhmmss) to a date."""
    if not val:
        return None
    val = val.strip()
    try:
        return datetime.strptime(val[:8], "%Y%m%d").date()
    except ValueError:
        return None


def parse_events(text, today, horizon_days):
    """Parse VEVENTs from raw iCal text, returning future events within the horizon.

    Returns a list of {"date": iso-str, "end_date": iso-str or omitted, "title": str,
    "url": str} sorted ascending. "end_date" is only included for genuine multi-day
    spans — per RFC 5545 §3.6.1, DTEND on an all-day VEVENT is exclusive (the day
    *after* the event ends), so a normal single-day event has DTEND = DTSTART + 1
    day and would misreport as a 2-day span if taken literally.
    """
    # Unfold continuation lines per RFC 5545 §3.1
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)

    events = []
    in_vevent = False
    start = end = summary = url = None

    for line in text.split("\n"):
        if line == "BEGIN:VEVENT":
            in_vevent = True
            start = end = summary = url = None
        elif line == "END:VEVENT":
            if in_vevent and start:
                d = parse_ical_date(start)
                if d and d >= today and (d - today).days <= horizon_days:
                    entry = {
                        "date": d.isoformat(),
                        "title": summary or "Untitled event",
                        "url": url or "",
                    }
                    end_d = parse_ical_date(end)
                    if end_d:
                        inclusive_end = end_d - timedelta(days=1)
                        if inclusive_end > d:
                            entry["end_date"] = inclusive_end.isoformat()
                    events.append(entry)
            in_vevent = False
        elif in_vevent:
            if line.startswith("DTSTART"):
                start = line.split(":", 1)[-1].strip()
            elif line.startswith("DTEND"):
                end = line.split(":", 1)[-1].strip()
            elif line.startswith("SUMMARY:"):
                summary = line[8:].strip()
            elif line.startswith("URL:"):
                url = line[4:].strip()

    events.sort(key=lambda e: e["date"])
    return events


def load_orgs(include_inactive, only_slug):
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        slug = os.path.basename(path)[:-3]
        if only_slug and slug != only_slug:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        if not m.get("ics_feed"):
            continue
        if not include_inactive and m.get("status") != "active":
            continue
        orgs.append({"slug": slug, "title": m.get("title", slug), "ics_feed": m["ics_feed"]})
    return orgs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="include inactive orgs")
    ap.add_argument("--slug", help="sync a single org by slug")
    ap.add_argument("--dry-run", action="store_true", help="print results without writing")
    ap.add_argument("--max-events", type=int, default=15, help="max events to cache per org")
    ap.add_argument("--horizon-days", type=int, default=365, help="only keep events this many days out")
    ap.add_argument("--timeout", type=int, default=10)
    args = ap.parse_args()

    if frontmatter is None:
        print("python-frontmatter is required (pip install python-frontmatter)", file=sys.stderr)
        sys.exit(1)

    orgs = load_orgs(args.all, args.slug)
    if not orgs:
        print("No orgs with ics_feed: found.")
        return

    today = date.today()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if not args.dry_run:
        os.makedirs(OUT_DIR, exist_ok=True)

    for org in orgs:
        print(f"{org['slug']:35s} … ", end="", flush=True)
        try:
            r = session.get(org["ics_feed"], timeout=args.timeout)
            r.raise_for_status()
        except RequestException as e:
            print(f"fetch failed ({e})")
            continue

        events = parse_events(r.text, today, args.horizon_days)[: args.max_events]
        if not events:
            print("no upcoming events")
            if not args.dry_run:
                out_path = os.path.join(OUT_DIR, f"{org['slug']}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            continue

        print(f"{len(events)} upcoming event(s)")
        if args.dry_run:
            for e in events:
                print(f"    {e['date']}  {e['title']}")
        else:
            out_path = os.path.join(OUT_DIR, f"{org['slug']}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
