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

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md", "concepts.md"}
MIN_SOURCE_LENGTH = 20


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


def compute_proof_level(event):
    """Auto-compute proof_level from source signals."""
    has_url = "url" in event
    has_source = "source" in event
    has_note = "note" in event

    if has_url:
        url_str = str(event["url"]).strip()
        parsed = urlparse(url_str)
        if parsed.fragment and parsed.fragment.startswith(":~:text="):
            return "high"
        if has_note:
            return "medium"
        if parsed.path not in ("", "/"):
            return "medium"
        return "low"
    elif has_source:
        return "low" if not has_note else "medium"
    return "low"


def confidence_score(event):
    """Calculate sourcing confidence for an event (0-4+)."""
    score = 0
    has_url = "url" in event
    has_source = "source" in event
    has_note = "note" in event

    if has_url:
        url_str = str(event["url"]).strip()
        parsed = urlparse(url_str)
        is_wikipedia = "wikipedia.org" in parsed.netloc
        if is_wikipedia:
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
    if url_checked and (date.today() - url_checked).days <= 365:
        score += 1

    return score


def _reorder_file(path):
    """Re-order a single org file's frontmatter to canonical ordering."""
    import re
    try:
        import yaml
    except ImportError:
        return
    with open(path) as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return
    fm_text = m.group(1)
    body = content[m.end():]
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        return
    canonical = [
        "title", "type", "status", "country", "website",
        "logo", "logo_bg", "banner", "contact", "summary", "concepts",
        "location", "news_page", "rss_feed", "ics_feed", "related_orgs",
        "events", "activity", "last_checked",
    ]
    event_order = ["date", "title", "url", "source", "note", "url_checked",
                   "end_date", "notable", "type", "location", "proof_level", "coverage_url"]
    activity_order = ["manual", "dod", "social", "rss", "ical", "scrape", "sitemap"]

    def reorder(d, order):
        od = {}
        seen = set()
        for k in order:
            if k in d:
                od[k] = d[k]
                seen.add(k)
        for k in d:
            if k not in seen:
                od[k] = d[k]
        return od

    class OrderedDumper(yaml.Dumper):
        pass

    def dict_rep(dumper, d):
        return dumper.represent_mapping("tag:yaml.org,2002:map", d.items())

    OrderedDumper.add_representer(dict, dict_rep)

    data = reorder(data, canonical)
    if "events" in data:
        data["events"] = [
            reorder(e, event_order) if isinstance(e, dict) else e
            for e in data["events"]
        ]
    if "activity" in data and isinstance(data["activity"], dict):
        data["activity"] = reorder(data["activity"], activity_order)

    new_fm = yaml.dump(data, Dumper=OrderedDumper, default_flow_style=False,
                       sort_keys=False, allow_unicode=True).rstrip("\n")
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
    args = parser.parse_args()

    pages = load_org_pages(args.slug)

    no_events = []
    unsourced = 0
    vague_source = 0
    weak_url = 0
    notable_no_proof = 0
    total = 0
    has_issues = False
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
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
                date = e.get("date", "?")
                title = e.get("title", "?")
                print(f"  UNSOURCED EVENT  {p['title']}  [{date}]  {title}")
                continue

            # Compute confidence
            score = confidence_score(e)
            if score >= 4:
                confidence_counts["high"] += 1
            elif score >= 2:
                confidence_counts["medium"] += 1
            else:
                confidence_counts["low"] += 1

            # proof_level
            if "proof_level" in e:
                proof_counts[e["proof_level"]] = proof_counts.get(e["proof_level"], 0) + 1
            elif args.calculate:
                level = compute_proof_level(e)
                e["proof_level"] = level
                proof_counts[level] = proof_counts.get(level, 0) + 1
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
                has_frag = has_url and "text=" in str(e.get("url", ""))
                if not has_frag:
                    notable_no_proof += 1
                    print(f"  NOTABLE NO PROOF {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")

        if changed and args.calculate:
            frontmatter.dump(p["post"], p["path"])
            # Reorder frontmatter fields after writing (frontmatter.dump loses order)
            _reorder_file(p["path"])

    sourced = total - unsourced
    unset = proof_counts.pop("unset", 0)

    print()
    print(f"Orgs scanned: {len(pages)}")
    print(f"Events total: {total}  |  sourced: {sourced}  |  unsourced: {unsourced}")
    print(f"Confidence:   high: {confidence_counts['high']}  medium: {confidence_counts['medium']}  low: {confidence_counts['low']}")
    if unset:
        print(f"Proof levels: high: {proof_counts.get('high',0)}  medium: {proof_counts.get('medium',0)}  low: {proof_counts.get('low',0)}  unset: {unset}  (run --calculate to auto-set)")
    else:
        print(f"Proof levels: high: {proof_counts.get('high',0)}  medium: {proof_counts.get('medium',0)}  low: {proof_counts.get('low',0)}")
    if calculated:
        print(f"Calculated and set proof_level on {calculated} events.")
    if notable_no_proof:
        print(f"Notable events lacking proof (no note or fragment): {notable_no_proof}")
    if weak_url:
        print(f"Weak URLs (homepage-only): {weak_url}")
    if vague_source:
        print(f"Vague source values (below {MIN_SOURCE_LENGTH} chars): {vague_source}")
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
