#!/usr/bin/env python3
"""
discover_elections.py — ask Wikidata which elections are coming up, and
report the ones docs/data/elections.yml doesn't list yet.

A discovery aid, NOT a sync. It never writes to elections.yml, by design:

  Wikidata is a lead, not a source — the same rule CLAUDE.md states for
  WebSearch/WebFetch output, and for the same reason. Checked against this
  corpus on 2026-09-02, Wikidata's `point in time` for the 2027 New South
  Wales state election was 30 January 2027. That is the *earliest* date the
  election could legally be held, not the scheduled one: the fourth-Saturday
  default of 27 March 2027 falls on Holy Saturday, so the government
  announced 13 March instead. A sync script would have written the wrong
  date into the calendar with a straight face. The same query also returned
  an item labelled "2022 Bosnian presidential election" dated 2026-10-04,
  several unlabelled Q-ids, and every entry two or three times over
  (multiple P31 paths reach the same item).

  What it IS good for: telling you an election exists. The 2026 Tasmanian
  local elections were missing from elections.yml until this query surfaced
  them — which is exactly the job, and it ends there. The date, the
  wording, and the citation still get read off a real page by a human.

So: run this, read what it found, then go source each one properly and add
it by hand (see docs/data/elections.yml's header for the schema, and
util/check_elections.py for the gate it has to pass).

Usage:
    python util/discover_elections.py                    # Australia (default)
    python util/discover_elections.py --country NZ --country GB
    python util/discover_elections.py --all-countries    # everything, noisy
    python util/discover_elections.py --until 2029-01-01
    python util/discover_elections.py --known            # also list what we already have

Requirements: requests (util/requirements.txt)
"""

import argparse
import os
import sys
from datetime import date, timedelta

import yaml

try:
    import requests
except ImportError:
    print("Missing dependency: requests — pip install requests")
    sys.exit(1)

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ELECTIONS_FILE = os.path.join(REPO_ROOT, "docs", "data", "elections.yml")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
# Wikidata asks that automated clients identify themselves and a contact
# point; an anonymous client can be blocked without notice.
USER_AGENT = ("DesigningOpenDemocracy-election-discovery/1.0 "
              "(https://designingopendemocracy.com; see util/discover_elections.py)")

# Q40231 = election. The P279* walk picks up general/presidential/local
# election subclasses, which is what makes the query useful — and also what
# makes it return each item several times over, once per path that reaches
# it. Deduplicated below rather than in SPARQL: DISTINCT on the server costs
# more query time than a set() costs here.
QUERY = """
SELECT ?item ?itemLabel ?date ?iso WHERE {
  ?item wdt:P31/wdt:P279* wd:Q40231 ;
        wdt:P585 ?date .
  FILTER(?date >= "%(start)sT00:00:00Z"^^xsd:dateTime &&
         ?date <  "%(end)sT00:00:00Z"^^xsd:dateTime)
  %(country_clause)s
  OPTIONAL { ?item wdt:P17 ?country . ?country wdt:P297 ?iso . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?date
"""

COUNTRY_QIDS = {
    # Only what's needed to scope the query; the ISO code comes back in the
    # results either way. Add as needed — an unlisted code falls back to an
    # unscoped query filtered client-side.
    "AU": "Q408", "NZ": "Q664", "GB": "Q145", "US": "Q30", "CA": "Q16",
    "IE": "Q27", "IN": "Q668", "ZA": "Q258", "TW": "Q865", "PH": "Q928",
    "BR": "Q155", "FR": "Q142", "DE": "Q183", "CH": "Q39", "KE": "Q114",
    "NG": "Q1033", "MX": "Q96", "AR": "Q414", "SE": "Q34", "FI": "Q33",
}


def load_known():
    """(country, date-iso) pairs and titles already in elections.yml."""
    if not os.path.exists(ELECTIONS_FILE):
        return set(), []
    with open(ELECTIONS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    keys, rows = set(), []
    for e in (data.get("elections") or []):
        if not isinstance(e, dict):
            continue
        d = str(e.get("date"))[:10]
        keys.add((e.get("country"), d))
        rows.append((d, e.get("country"), e.get("title")))
    return keys, sorted(rows)


def run_query(countries, start, end, timeout):
    if countries and all(c in COUNTRY_QIDS for c in countries):
        values = " ".join("wd:" + COUNTRY_QIDS[c] for c in countries)
        country_clause = f"VALUES ?scope {{ {values} }} ?item wdt:P17 ?scope ."
    else:
        country_clause = ""
    query = QUERY % {"start": start.isoformat(), "end": end.isoformat(),
                     "country_clause": country_clause}
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def main():
    ap = argparse.ArgumentParser(description="Find upcoming elections Wikidata knows about and we don't.")
    ap.add_argument("--country", action="append",
                    help="ISO 3166-1 alpha-2 code to scope to (repeatable). Default: AU.")
    ap.add_argument("--all-countries", action="store_true",
                    help="Don't scope by country. Returns a lot of by-elections and local races.")
    ap.add_argument("--until", help="Only elections before this date (YYYY-MM-DD). Default: two years out.")
    ap.add_argument("--known", action="store_true", help="Also print what elections.yml already lists")
    ap.add_argument("--timeout", type=int, default=120, help="SPARQL request timeout in seconds")
    args = ap.parse_args()

    countries = None if args.all_countries else [c.upper() for c in (args.country or ["AU"])]
    start = date.today()
    end = date.fromisoformat(args.until) if args.until else start + timedelta(days=730)

    known_keys, known_rows = load_known()
    if args.known:
        print(f"Already in {os.path.relpath(ELECTIONS_FILE, REPO_ROOT)}:")
        for d, c, t in known_rows:
            print(f"  {d}  {c}  {t}")
        print()

    scope = "all countries" if countries is None else ", ".join(countries)
    print(f"Querying Wikidata for elections in {scope} between {start} and {end}…")
    try:
        rows = run_query(countries, start, end, args.timeout)
    except Exception as exc:
        print(f"Query failed: {exc}")
        sys.exit(1)

    seen, found = set(), []
    for r in rows:
        iso = r.get("iso", {}).get("value")
        if countries and iso not in countries:
            continue
        d = r["date"]["value"][:10]
        label = r["itemLabel"]["value"]
        # An unlabelled result comes back as its own Q-id: real data, but
        # nothing a human can act on without opening it, so it's flagged
        # rather than silently dropped.
        if (iso, d, label) in seen:
            continue
        seen.add((iso, d, label))
        found.append((d, iso, label, r["item"]["value"]))

    found.sort()
    new = [f for f in found if (f[1], f[0]) not in known_keys]

    print(f"\n{len(found)} distinct election(s) returned; {len(new)} not in elections.yml:\n")
    for d, iso, label, uri in new:
        flag = "  ?" if label.startswith("Q") and label[1:].isdigit() else "   "
        print(f"{flag} {d}  {iso or '--'}  {label}")
        print(f"       {uri}")

    if not new:
        print("  (nothing new)")

    print("\nReminder: these are leads, not sources. Read each election's own page,")
    print("quote the sentence that states the date, and add it to elections.yml by")
    print("hand — see this script's docstring for what Wikidata got wrong last time.")


if __name__ == "__main__":
    main()
