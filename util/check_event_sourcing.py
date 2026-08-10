#!/usr/bin/env python3
"""
check_event_sourcing.py — event sourcing validator and proof-level calculator.

Scans every org page's frontmatter `events:` entries and:
  - Hard-gates: every event must have url: or source: (exit 1 if missing)
  - Warns: vague source: values, weak URLs, notable events without proof
  - Reports: confidence distribution and proof_level distribution
  - Calculates: --calculate mode auto-sets proof_level from source signals

proof_level values (auto-computed from signals, or manually set):
  high    — #:~:text= fragment pins exact evidence on the page
  medium  — specific URL + note, or Wikipedia URL without fragment  
  low     — homepage URL, source-only, or click-through needed

Usage:
    python util/check_event_sourcing.py              # check all orgs
    python util/check_event_sourcing.py --calculate  # auto-set missing proof_level
    python util/check_event_sourcing.py --slug mosaiclab

Requirements: python-frontmatter, pyyaml (util/requirements.txt)
"""

import argparse
import glob
import os
import sys
from datetime import date, datetime
from urllib.parse import urlparse

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))
from reorder_frontmatter import reorder_frontmatter as _canonical_reorder  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md", "concepts.md"}
MIN_SOURCE_LENGTH = 20
STALE_CHECK_DAYS = 365


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip('"'))
    except ValueError:
        return None


def is_weak_url(url):
    parsed = urlparse(str(url).strip())
    return parsed.path in ("", "/") and not parsed.fragment


def confidence_score(event):
    """Calculate sourcing confidence for an event (0-4+).

    This is the single source of truth for sourcing quality — proof_level
    (what gets stored and displayed) is derived directly from this score
    via compute_proof_level(), so the two can never disagree.
    """
    score = 0
    has_url = "url" in event
    has_source = "source" in event
    has_note = "note" in event

    if has_url:
        url_str = str(event["url"]).strip()
        parsed = urlparse(url_str)
        # Require an actual article path, not just the bare wikipedia.org
        # domain — a homepage-only "citation" shouldn't earn the bonus a
        # specific article does.
        is_wikipedia_article = (
            "wikipedia.org" in parsed.netloc and parsed.path not in ("", "/")
        )
        if is_wikipedia_article:
            score += 2
        elif parsed.path not in ("", "/"):
            score += 1

        if parsed.fragment and parsed.fragment.startswith(":~:text="):
            score += 2
    elif has_source:
        score += 1

    if has_note:
        score += 1

    url_checked = parse_date(event.get("url_checked"))
    if url_checked and (date.today() - url_checked).days <= STALE_CHECK_DAYS:
        score += 1

    return score


def compute_proof_level(event):
    """Auto-compute proof_level from the unified confidence_score.

    high   — score >= 4  (e.g. a fragment-pinned or Wikipedia-article URL,
                           checked recently)
    medium — score >= 2  (a specific URL, or source: + note:)
    low    — everything else (homepage-only URL, bare source:, or a once-
                           strong citation that's gone stale/unverified)
    """
    score = confidence_score(event)
    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    return "low"


def _reorder_file(path):
    """Re-order a single org file's frontmatter to canonical ordering.

    Delegates to reorder_frontmatter.py's canonical field-order lists so
    there is exactly one place (plus its CLAUDE.md documentation) that
    defines the ordering — previously this function carried its own
    hand-copied lists, which could silently drift from the real ones.
    """
    import re
    with open(path) as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return
    fm_text = m.group(1)
    body = content[m.end():]
    new_fm = _canonical_reorder(fm_text)
    new_content = f"---\n{new_fm}\n---\n{body}"
    if new_content != content:
        with open(path, "w") as f:
            f.write(new_content)


def load_org_pages(slug_filter=None):
    pages = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        filename = os.path.basename(path)
        if filename in SKIP_FILES:
            continue
        slug = filename[:-3]
        if slug_filter and slug != slug_filter:
            continue
        post = frontmatter.load(path)
        pages.append({
            "path": path,
            "slug": slug,
            "title": post.metadata.get("title", slug),
            "events": post.metadata.get("events") or [],
            "post": post,
        })
    return pages


def main():
    parser = argparse.ArgumentParser(description="Validate event sourcing in org pages")
    parser.add_argument("--slug", type=str, help="Check a single org by slug")
    parser.add_argument("--calculate", action="store_true",
                        help="Auto-set proof_level on events that lack it")
    parser.add_argument("--recalculate", action="store_true",
                        help="Recompute proof_level on ALL events, overwriting existing "
                             "values (use after editing an event's url/note/source, or to "
                             "clear STALE PROOF_LEVEL warnings caused by url_checked aging "
                             "past the recency window). Implies --calculate.")
    args = parser.parse_args()
    if args.recalculate:
        args.calculate = True

    pages = load_org_pages(args.slug)

    no_events = []
    unsourced = 0
    vague_source = 0
    weak_url = 0
    notable_no_proof = 0
    stale_checked = 0
    mismatched_proof_level = 0
    total = 0
    has_issues = False
    proof_counts = {"high": 0, "medium": 0, "low": 0}
    calculated = 0

    for p in pages:
        events = p["events"]
        if not events:
            no_events.append(p["title"])
            continue

        changed = False
        for e in events:
            total += 1
            has_url = "url" in e
            has_source = "source" in e

            if not has_url and not has_source:
                unsourced += 1
                has_issues = True
                event_date = e.get("date", "?")
                title = e.get("title", "?")
                print(f"  UNSOURCED EVENT  {p['title']}  [{event_date}]  {title}")
                continue

            # proof_level is always derived from confidence_score() (see
            # compute_proof_level) so a stored value and a freshly computed
            # one can never silently disagree — check that invariant here.
            computed_level = compute_proof_level(e)
            if "proof_level" in e and e["proof_level"] != computed_level and args.recalculate:
                e["proof_level"] = computed_level
                proof_counts[computed_level] = proof_counts.get(computed_level, 0) + 1
                calculated += 1
                changed = True
            elif "proof_level" in e:
                proof_counts[e["proof_level"]] = proof_counts.get(e["proof_level"], 0) + 1
                if e["proof_level"] != computed_level:
                    mismatched_proof_level += 1
                    print(f"  STALE PROOF_LEVEL {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")
                    print(f"                     stored: {e['proof_level']}  now computes to: {computed_level}"
                          f"  (source signals changed since last --calculate — run --recalculate to refresh)")
            elif args.calculate:
                e["proof_level"] = computed_level
                proof_counts[computed_level] = proof_counts.get(computed_level, 0) + 1
                calculated += 1
                changed = True
            else:
                proof_counts["unset"] = proof_counts.get("unset", 0) + 1

            # Warnings
            if has_source and not has_url:
                src = str(e["source"]).strip()
                if len(src) < MIN_SOURCE_LENGTH:
                    vague_source += 1
                    print(f"  VAGUE SOURCE    {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")
                    print(f"                   source: {src!r}")

            if has_url and is_weak_url(e["url"]):
                weak_url += 1
                print(f"  WEAK URL        {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")
                print(f"                   url: {e['url']}")

            if e.get("notable") and "note" not in e:
                parsed = urlparse(str(e.get("url", ""))) if has_url else None
                has_frag = bool(parsed and parsed.fragment.startswith(":~:text="))
                if not has_frag:
                    notable_no_proof += 1
                    print(f"  NOTABLE NO PROOF {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")

            url_checked = parse_date(e.get("url_checked"))
            checked_recently = url_checked and (date.today() - url_checked).days <= STALE_CHECK_DAYS
            if e.get("proof_level") in ("high", "medium") and not checked_recently:
                stale_checked += 1

        if changed and args.calculate:
            frontmatter.dump(p["post"], p["path"])
            # Reorder frontmatter fields after writing (frontmatter.dump loses order)
            _reorder_file(p["path"])

    sourced = total - unsourced
    unset = proof_counts.pop("unset", 0)

    print()
    print(f"Orgs scanned: {len(pages)}")
    print(f"Events total: {total}  |  sourced: {sourced}  |  unsourced: {unsourced}")
    if unset:
        print(f"Proof levels: high: {proof_counts.get('high',0)}  medium: {proof_counts.get('medium',0)}  low: {proof_counts.get('low',0)}  unset: {unset}  (run --calculate to auto-set)")
    else:
        print(f"Proof levels: high: {proof_counts.get('high',0)}  medium: {proof_counts.get('medium',0)}  low: {proof_counts.get('low',0)}")
    if calculated:
        print(f"Calculated and set proof_level on {calculated} events.")
    if mismatched_proof_level:
        print(f"Stale proof_level (stored value no longer matches recomputed score): {mismatched_proof_level}  (run --recalculate to refresh)")
    if notable_no_proof:
        print(f"Notable events lacking proof (no note or fragment): {notable_no_proof}")
    if weak_url:
        print(f"Weak URLs (homepage-only): {weak_url}")
    if vague_source:
        print(f"Vague source values (below {MIN_SOURCE_LENGTH} chars): {vague_source}")
    if stale_checked:
        print(f"High/medium-proof events never checked or unchecked in {STALE_CHECK_DAYS}+ days: {stale_checked}  (citation may have drifted — see util/check_event_urls.py and util/check_fragments.py)")
    if no_events:
        print(f"Orgs with no events (info only): {len(no_events)}")

    if has_issues:
        print(f"\n{unsourced} event(s) missing both url: and source:. Add one to each.")
        sys.exit(1)
    else:
        print("All events have a url: or source:.")
        sys.exit(0)


if __name__ == "__main__":
    main()
