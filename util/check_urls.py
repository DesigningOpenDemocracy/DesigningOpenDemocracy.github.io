#!/usr/bin/env python3
"""
check_urls.py — External URL reachability checker for org pages

Checks that website: URLs in org frontmatter actually respond. Active orgs
with Wayback URLs are skipped (known exceptions — see SOUL.md). Inactive
orgs are skipped by default (Wayback URLs are always reachable).

Results: OK · REDIRECT (notes final URL) · CLIENT_ERROR · SERVER_ERROR ·
         TIMEOUT · SSL_ERROR · CONNECTION_ERROR

Usage:
    python util/check_urls.py              # active orgs not checked in 365 days
    python util/check_urls.py --all        # ignore last_checked
    python util/check_urls.py --inactive   # also check inactive/deregistered
    python util/check_urls.py --timeout 15
    python util/check_urls.py --delay 1    # polite crawl delay (seconds)

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import os
import sys
import time
from datetime import date, datetime

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = date.today()

HEADERS = {
    "User-Agent": "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"
}


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip('"'))
    except ValueError:
        return None


def check_url(url, timeout):
    """Return (result_code, http_status, detail_string)."""
    try:
        r = requests.head(url, timeout=timeout, headers=HEADERS,
                          allow_redirects=True, verify=False)
        code = r.status_code
        final = r.url.rstrip("/")
        original = url.rstrip("/")

        # HEAD blocked — retry with GET
        if code in (403, 405):
            r2 = requests.get(url, timeout=timeout, headers=HEADERS,
                              allow_redirects=True, verify=False, stream=True)
            r2.close()
            code = r2.status_code
            final = r2.url.rstrip("/")

        if code < 400:
            if final != original:
                return "REDIRECT", code, final
            return "OK", code, None
        if 400 <= code < 500:
            return "CLIENT_ERROR", code, None
        return "SERVER_ERROR", code, None

    except requests.exceptions.Timeout:
        return "TIMEOUT", None, None
    except requests.exceptions.SSLError as e:
        return "SSL_ERROR", None, str(e)[:80]
    except requests.exceptions.ConnectionError:
        return "CONNECTION_ERROR", None, None
    except Exception as e:
        return "ERROR", None, str(e)[:80]


def main():
    parser = argparse.ArgumentParser(description="Check external URLs in org frontmatter")
    parser.add_argument("--days", type=int, default=365,
                        help="Skip pages checked within N days (default: 365)")
    parser.add_argument("--all", action="store_true",
                        help="Ignore last_checked, check all")
    parser.add_argument("--inactive", action="store_true",
                        help="Also check inactive/deregistered orgs")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Request timeout in seconds (default: 10)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between requests in seconds (default: 0.5)")
    args = parser.parse_args()

    pages = []
    skipped_wayback = skipped_recent = 0

    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        status = m.get("status", "")
        website = (m.get("website") or "").strip()

        if not website or status not in ("active", "inactive", "deregistered"):
            continue
        if status != "active" and not args.inactive:
            continue
        # Active orgs with Wayback URLs are known exceptions — don't check
        if status == "active" and website.startswith(WAYBACK_PREFIX):
            skipped_wayback += 1
            continue

        if not args.all:
            lc = parse_date(m.get("last_checked"))
            if lc and (TODAY - lc).days < args.days:
                skipped_recent += 1
                continue

        pages.append({
            "path": path,
            "title": m.get("title", os.path.basename(path)[:-3]),
            "status": status,
            "website": website,
        })

    if not pages:
        print(f"\nNothing to check ({skipped_recent} skipped as recently verified, "
              f"{skipped_wayback} Wayback exceptions).\n")
        return

    print(f"\n=== URL checker  ({len(pages)} pages, timeout: {args.timeout}s, "
          f"delay: {args.delay}s) ===")
    print(f"    {skipped_recent} skipped (recently verified)  "
          f"|  {skipped_wayback} Wayback exceptions skipped\n")

    ok = redirects = errors = 0

    for p in pages:
        result, code, detail = check_url(p["website"], args.timeout)
        code_str = f" ({code})" if code else ""

        if result == "OK":
            print(f"  ✓  {p['title']}")
            ok += 1
        elif result == "REDIRECT":
            print(f"  →  {p['title']}{code_str}")
            print(f"       {p['website']}")
            print(f"       → {detail}")
            redirects += 1
        else:
            print(f"  ✗  {p['title']}  [{result}{code_str}]")
            print(f"       {p['website']}")
            if detail:
                print(f"       {detail}")
            errors += 1

        if args.delay:
            time.sleep(args.delay)

    print(f"\nSummary: {ok} OK  |  {redirects} redirect(s)  |  {errors} error(s)"
          f"  ({len(pages)} checked)\n")


if __name__ == "__main__":
    main()
