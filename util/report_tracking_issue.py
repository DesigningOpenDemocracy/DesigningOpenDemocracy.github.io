#!/usr/bin/env python3
"""
report_tracking_issue.py — create/update a single persistent GitHub issue
summarizing citation-verification findings, so a human doesn't have to read
weekly Action logs to notice citation drift.

Reads the JSON --report files check_fragments.py and check_event_urls.py
already know how to produce (mismatches/ambiguous/fetch-errors, dead/
blocked/redirected/errored URLs) and posts a plain mechanical summary —
no LLM involved, no judgment calls, just counting and formatting.

Deliberately polite to the GitHub API and to anyone watching the repo:
  - One GET to find the tracking issue, then at most one POST/PATCH — never
    more than a handful of calls per run.
  - Never posts a comment — only edits the one issue's body in place, so
    watchers get a single evolving issue, not a growing thread.
  - Makes zero write calls on a clean run with no pre-existing issue, and
    zero on a clean run where the issue is already closed — closing only
    happens on the open->clean transition, not every clean week.
  - A missing --report file (the check step crashed before writing one) is
    treated as actionable rather than silently read as "zero findings" —
    otherwise a real failure could look like a clean sweep and quietly
    close the tracking issue.

Usage:
    python util/report_tracking_issue.py \\
        --fragments-report /tmp/fragments-report.json \\
        --urls-report /tmp/urls-report.json \\
        --dry-run                              # print the body, make no API calls

    # In CI (uses GITHUB_REPOSITORY / GITHUB_TOKEN from the environment):
    python util/report_tracking_issue.py \\
        --fragments-report /tmp/fragments-report.json \\
        --urls-report /tmp/urls-report.json
"""

import argparse
import json
import os
import sys
from datetime import date

try:
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install requests")
    sys.exit(1)

TITLE = "Citation verification tracking"
MARKER = "<!-- dod-citation-tracking-issue -->"
USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"


def load_report(path):
    """Return the parsed JSON report at path, or None if it's missing or
    unreadable — callers must treat None as "unknown", not "empty"."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def is_actionable(fragments, urls, fragments_missing=False, urls_missing=False):
    """Whether the tracking issue should be open. A missing report counts
    as actionable — see module docstring on why."""
    if fragments_missing or urls_missing:
        return True
    return bool(
        fragments.get("mismatches") or fragments.get("ambiguous") or
        fragments.get("fetch_errors") or urls.get("dead") or urls.get("errored")
    )


def _fragment_bullets(items, error_field=None):
    lines = []
    for it in items:
        source = it.get("source", "?")
        url = it.get("url", "")
        lines.append(f"- `{source}` — {url}")
        if error_field:
            lines.append(f"  error: {it.get(error_field, '?')}")
        else:
            ev = (it.get("evidence") or "").strip()
            if ev:
                if len(ev) > 160:
                    ev = ev[:160] + "…"
                lines.append(f"  > {ev}")
    return lines


def _url_bullets(items, extra_key):
    lines = []
    for it in items:
        org = it.get("org", "?")
        d = it.get("date", "?")
        ev = it.get("event", "?")
        url = it.get("url", "")
        extra = it.get(extra_key, "")
        lines.append(f"- `{org}` [{d}] {ev} — {url}  ({extra})")
    return lines


def _section(label, bullet_lines):
    if not bullet_lines:
        return []
    # Every bullet group emits one leading "- `source` ..." line per item
    # plus an optional detail line, so the item count is the number of
    # lines starting with "- ", not len(bullet_lines).
    count = sum(1 for line in bullet_lines if line.startswith("- "))
    return [f"### {label} ({count})", ""] + bullet_lines + [""]


def build_issue_body(fragments, urls, generated, fragments_missing=False, urls_missing=False):
    """Pure formatting: JSON report dicts (as produced by check_fragments.py
    --report / check_event_urls.py --report) in, markdown issue body out.
    No network calls — kept separate from sync_issue() so this is testable
    without mocking anything."""
    mismatches = fragments.get("mismatches") or []
    ambiguous = fragments.get("ambiguous") or []
    fetch_errors = fragments.get("fetch_errors") or []
    dead = urls.get("dead") or []
    errored = urls.get("errored") or []
    blocked = urls.get("blocked") or []
    redirected = urls.get("redirected") or []

    body = [
        MARKER,
        "",
        "Automated summary of citation-verification findings from "
        "`util/check_fragments.py` and `util/check_event_urls.py`, posted by "
        "the weekly heartbeat probe workflow "
        "(`.github/workflows/heartbeat-probes.yml`). Purely mechanical — no "
        "LLM involved, no editorial judgment made. This issue is edited in "
        "place each run (never a new comment) and closes itself automatically "
        "once every section below is empty.",
        "",
        f"_Last checked: {generated}_",
        "",
    ]

    if fragments_missing:
        body += ["> ⚠ `check_fragments.py`'s report was missing this run — the "
                 "step may have failed before writing it. Check the Action log.", ""]
    if urls_missing:
        body += ["> ⚠ `check_event_urls.py`'s report was missing this run — the "
                 "step may have failed before writing it. Check the Action log.", ""]

    needs_attention = (
        _section("Quote mismatches", _fragment_bullets(mismatches)) +
        _section("Ambiguous quotes (occur more than once on the page)", _fragment_bullets(ambiguous)) +
        _section("Fetch errors", _fragment_bullets(fetch_errors, error_field="error")) +
        _section("Dead citation URLs", _url_bullets(dead, "status")) +
        _section("Errored citation URLs", _url_bullets(errored, "error"))
    )
    if needs_attention:
        body += ["## Needs attention", ""] + needs_attention

    informational = (
        _section("Blocked (403/429 — likely bot-blocking, verify manually before touching)",
                  _url_bullets(blocked, "status")) +
        _section("Redirected (informational only)", _url_bullets(redirected, "final_url"))
    )
    if informational:
        body += ["## Informational (not gating this issue's open/closed state)", ""] + informational

    if not needs_attention and not informational and not fragments_missing and not urls_missing:
        body += ["All checkable evidence and citation URLs matched on the last run. Nothing to do."]

    return "\n".join(body).rstrip() + "\n"


def find_existing_issue(session, api_base):
    """Return the existing tracking issue dict (any state), or None. One
    GET, listing this repo's issues and matching by exact title — matching
    by title rather than a label avoids depending on a label existing
    first, and this repo's issue volume is small enough that one page
    (100 issues) is always enough."""
    resp = session.get(f"{api_base}/issues", params={"state": "all", "per_page": 100})
    resp.raise_for_status()
    for issue in resp.json():
        if issue.get("title") == TITLE and "pull_request" not in issue:
            return issue
    return None


def sync_issue(session, api_base, body, actionable):
    """Create, update, close, or reopen the tracking issue as needed.
    Returns a short string describing what happened (for logging/tests)."""
    existing = find_existing_issue(session, api_base)

    if not actionable:
        if existing and existing["state"] == "open":
            r = session.patch(f"{api_base}/issues/{existing['number']}",
                               json={"state": "closed", "body": body})
            r.raise_for_status()
            return "closed"
        return "noop-clean"

    if existing is None:
        r = session.post(f"{api_base}/issues", json={"title": TITLE, "body": body})
        r.raise_for_status()
        return "created"

    if existing["state"] == "closed":
        r = session.patch(f"{api_base}/issues/{existing['number']}",
                           json={"state": "open", "body": body})
        r.raise_for_status()
        return "reopened"

    r = session.patch(f"{api_base}/issues/{existing['number']}", json={"body": body})
    r.raise_for_status()
    return "updated"


def main():
    parser = argparse.ArgumentParser(
        description="Create/update a tracking issue from citation-verification reports")
    parser.add_argument("--fragments-report", type=str, default=None,
                        help="Path to check_fragments.py's --report JSON output")
    parser.add_argument("--urls-report", type=str, default=None,
                        help="Path to check_event_urls.py's --report JSON output")
    parser.add_argument("--repo", type=str, default=os.environ.get("GITHUB_REPOSITORY"),
                        help="owner/repo (defaults to $GITHUB_REPOSITORY)")
    parser.add_argument("--token", type=str, default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token (defaults to $GITHUB_TOKEN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the issue body and intended action; make no API calls")
    args = parser.parse_args()

    fragments_raw = load_report(args.fragments_report)
    urls_raw = load_report(args.urls_report)
    fragments_missing = args.fragments_report is not None and fragments_raw is None
    urls_missing = args.urls_report is not None and urls_raw is None
    fragments = fragments_raw or {}
    urls = urls_raw or {}

    generated = date.today().isoformat()
    body = build_issue_body(fragments, urls, generated, fragments_missing, urls_missing)
    actionable = is_actionable(fragments, urls, fragments_missing, urls_missing)

    if args.dry_run:
        print(body)
        print(f"[dry-run] actionable={actionable} — no API calls made")
        return 0

    if not args.repo or not args.token:
        print("Missing --repo/--token (or $GITHUB_REPOSITORY/$GITHUB_TOKEN) — "
              "nothing to do outside CI. Use --dry-run to preview the issue body locally.")
        return 1

    api_base = f"https://api.github.com/repos/{args.repo}"
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {args.token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    })
    action = sync_issue(session, api_base, body, actionable)
    print(f"Tracking issue: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
