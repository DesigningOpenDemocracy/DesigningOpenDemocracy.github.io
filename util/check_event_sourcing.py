#!/usr/bin/env python3
"""
check_event_sourcing.py — event sourcing validator and proof-level calculator.

Scans every org page's frontmatter `events:` entries and:
  - Hard-gates: every event must have url: or source: (exit 1 if missing)
  - Warns: vague source: values, weak URLs, notable events without proof
  - Reports: confidence distribution and proof_level distribution
  - Calculates: --calculate mode auto-sets proof_level from source signals

proof_level values (auto-computed from signals, or manually set):
  high    — quote: pins exact evidence text on the page (rendered as a
            #:~:text= scroll-to-fragment at build time, see
            util/text_fragment.py — never stored in url: itself)
  medium  — specific URL + note, or Wikipedia URL without a quote
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
SKIP_FILES = {"index.md"}
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


# Bare collection/index pages — e.g. https://org.example/events/ rather than
# .../events/the-specific-event-slug/. Same problem as a homepage-only URL
# (flagged below): the citation isn't pinned to the claimed event and will
# silently rot once that event scrolls off the list. Deliberately narrow to
# unambiguous list-noun segments rather than every short single-segment path
# (e.g. "/about", "/training") — those may well be a genuine specific page,
# not a rotating collection, and flagging them would be a false positive.
GENERIC_LIST_SEGMENTS = {"events", "event", "news", "blog", "calendar", "press", "media", "updates", "whats-on"}


def is_weak_url(url):
    parsed = urlparse(str(url).strip())
    if parsed.fragment:
        return False
    if parsed.path in ("", "/"):
        return True
    segments = [s for s in parsed.path.split("/") if s]
    return len(segments) == 1 and segments[0].lower() in GENERIC_LIST_SEGMENTS


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
    has_quote = "quote" in event

    if has_url:
        url_str = str(event["url"]).strip()
        parsed = urlparse(url_str)
        is_wikipedia_article = (
            "wikipedia.org" in parsed.netloc and parsed.path not in ("", "/")
        )
        if is_wikipedia_article:
            score += 2
        elif parsed.path not in ("", "/"):
            score += 1
    elif has_source:
        score += 1

    if has_quote:
        score += 2

    if has_note:
        score += 1

    url_checked = parse_date(event.get("url_checked"))
    if url_checked and (date.today() - url_checked).days <= STALE_CHECK_DAYS:
        score += 1

    return score


def compute_proof_level(event):
    """Auto-compute proof_level from source signals.

    Respects proof_level_locked: true — an explicit opt-out for a
    deliberately hand-set value (documented in CLAUDE.md as allowed) that
    --calculate/--recalculate and the pre-commit hook must not overwrite.
    Callers that need the "what would this compute to" answer regardless
    (e.g. the STALE PROOF_LEVEL check, which should still warn about a
    locked value that's drifted, just not silently fix it) should call
    _compute_proof_level_unlocked directly.
    """
    if event.get("proof_level_locked") and "proof_level" in event:
        return event["proof_level"]
    return _compute_proof_level_unlocked(event)


def _compute_proof_level_unlocked(event):
    has_url = "url" in event
    has_source = "source" in event
    has_note = "note" in event
    has_quote = "quote" in event

    if has_url:
        url_str = str(event["url"]).strip()
        parsed = urlparse(url_str)
        if has_quote:
            return "high"
        if has_note:
            return "medium"
        if parsed.path not in ("", "/"):
            return "medium"
        return "low"
    elif has_source:
        return "medium" if (has_note or has_quote) else "low"
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
    no_proof = 0
    notable_soft = 0
    mismatched_proof_level = 0
    stale_checked = 0
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
            # locked events are compared against the *unlocked* score too,
            # purely as an FYI (their lock is respected either way, but a
            # human should know if the reason they locked it may no longer
            # apply — e.g. a note: got added later, raising the real score).
            is_locked = bool(e.get("proof_level_locked"))
            computed_level = compute_proof_level(e)
            unlocked_level = _compute_proof_level_unlocked(e) if is_locked else computed_level

            if "proof_level" in e and e["proof_level"] != computed_level and args.recalculate:
                e["proof_level"] = computed_level
                proof_counts[computed_level] = proof_counts.get(computed_level, 0) + 1
                calculated += 1
                changed = True
            elif "proof_level" in e:
                proof_counts[e["proof_level"]] = proof_counts.get(e["proof_level"], 0) + 1
                if is_locked and e["proof_level"] != unlocked_level:
                    print(f"  LOCKED (FYI)    {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")
                    print(f"                   locked at: {e['proof_level']}  unlocked score would give: {unlocked_level}"
                          f"  (not auto-changed — confirm the lock reason still applies)")
                elif not is_locked and e["proof_level"] != computed_level:
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

            # Hard gate: every event needs evidence — quote or note.
            # proof_warning overrides (event passes CI but shows a warning badge).
            has_quote = "quote" in e
            has_note = "note" in e
            has_warning = "proof_warning" in e

            if not has_quote and not has_note and not has_warning:
                no_proof += 1
                has_issues = True
                print(f"  NO PROOF        {p['title']}  [{e.get('date','?')}]  {e.get('title','?')}")

            # Soft warning: notable events should have mechanical proof (quote),
            # not just a note. proof_warning also counts as a gap — notable + override = flagged.
            if e.get("notable") and not has_quote:
                notable_soft += 1
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
    if no_proof:
        print(f"Events lacking proof (no quote, note, or proof_warning): {no_proof}")
    if notable_soft:
        print(f"Notable events without mechanical proof (no quote): {notable_soft}")
    if weak_url:
        print(f"Weak URLs (homepage or generic list page, e.g. /events/): {weak_url}")
    if vague_source:
        print(f"Vague source values (below {MIN_SOURCE_LENGTH} chars): {vague_source}")
    if stale_checked:
        print(f"High/medium-proof events never checked or unchecked in {STALE_CHECK_DAYS}+ days: {stale_checked}  (citation may have drifted — see util/check_event_urls.py and util/check_fragments.py)")
    if no_events:
        print(f"Orgs with no events (info only): {len(no_events)}")

    if has_issues:
        print(f"\n{no_proof} event(s) need evidence (quote, note, or proof_warning). Add one to each.")
        sys.exit(1)
    else:
        print("All events have a url: or source:.")
        sys.exit(0)


if __name__ == "__main__":
    main()
