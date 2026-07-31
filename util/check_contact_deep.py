#!/usr/bin/env python3
"""
check_contact_deep.py — Headless-browser companion to check_contact.py.

check_contact.py fetches pages with a plain HTTP GET. That's invisible to
any client-side-rendered site: a React/Vue/etc. single-page app serves the
same near-empty HTML shell for every route (confirmed on vtaiwan.tw — every
path from / to /contact to /get-involved returned the identical 3855-byte
response, body content just `<div id="app"></div>`), so there's nothing for
a static fetcher to extract regardless of what the org actually publishes.

This tool drives a real headless browser (Playwright + Chromium) instead, so
client-side-rendered content actually exists in the DOM by the time it
scrapes. Same extraction logic as check_contact.py — imported from it, not
duplicated — just a different (much heavier) way of getting the HTML.

Use this AFTER check_contact.py, targeted at orgs it found nothing for and
that you suspect are a JS-rendered site (empty-looking page, or you've
confirmed it by hand like the vtaiwan.tw case above). Running it broadly
works too — page_tier()/choose_best_email() give identical results either
way if a site turns out not to be a SPA — but a full browser navigation per
URL is far slower than a plain GET, so default to --slug for one-off checks
rather than sweeping the whole org list unless you're prepared to wait.

Requires Playwright with the Chromium browser installed:
    pip install playwright
    playwright install chromium
(Not added to util/requirements.txt's default install — it pulls in a real
browser binary, not just a package, and most check_contact.py usage never
needs it.)

UNVERIFIED END-TO-END AS WRITTEN. The extraction logic (crawl_urls(),
choose_best_email(), extract_emails(), etc.) is imported directly from
check_contact.py and already validated by that tool's real-world testing.
The browser-driving part — the actual point of this file — is not: the
sandbox this was written in routes outbound traffic through a proxy that
plain HTTP clients (curl, requests) traverse fine but that headless
Chromium could not get through under any tested configuration (default,
explicit Playwright `proxy`, raw --proxy-server, with HTTP/2 and QUIC
disabled) — every attempt failed with ERR_CONNECTION_RESET or hung to
timeout, on a trivial control (example.com) as much as on any real org
site. Before trusting output from this tool, run it against a couple of
known SPA sites in an environment with normal outbound network access and
confirm it actually renders and extracts real content — don't assume the
code is correct just because it imports validated functions and runs
without raising.

Usage:
    python util/check_contact_deep.py --slug vtaiwan          # one org, deep-rendered
    python util/check_contact_deep.py --slug vtaiwan --write   # write high-confidence findings
    python util/check_contact_deep.py                          # all active orgs missing contact.email (slow)
    python util/check_contact_deep.py --all                    # include inactive orgs
    python util/check_contact_deep.py --timeout 25              # per-page navigation timeout in seconds
    python util/check_contact_deep.py --force                   # re-check/overwrite orgs that already have contact info
    python util/check_contact_deep.py --output results.json
"""

import argparse
import json
import signal
import sys

# check_contact.py lives in this same directory (util/), which Python adds
# to sys.path automatically for a directly-run script — no path munging needed.
from check_contact import (
    DOD_USER_AGENT,
    choose_best_email, crawl_urls, extract_emails, extract_phones,
    has_contact_form, page_tier, pick_best_phone, robots_allowed,
    strip_tags, write_contact, load_orgs,
)

class _DeepTimeout(Exception):
    pass

def _on_alarm(signum, frame):
    raise _DeepTimeout

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("Missing dependency: pip install playwright && playwright install chromium")
    sys.exit(1)


def probe_contact_deep(website, browser, nav_timeout_ms=20000, robots_session=None):
    """Same crawl/extraction strategy as check_contact.probe_contact(), but
    each URL is loaded in a real browser page instead of a plain GET, so
    client-side-rendered content is present in page.content() by the time
    it's scraped."""
    urls = crawl_urls(website)

    email_candidates = {}
    best_phone, best_phone_conf, phone_source = None, None, None
    form_url = None

    context = browser.new_context(user_agent=DOD_USER_AGENT)
    page = context.new_page()

    try:
        for url in urls:
            best_email_tier = min((c["tier"] for c in email_candidates.values()), default=None)
            if best_email_tier == 0 and best_phone_conf == "high" and form_url:
                break
            if not robots_allowed(url, timeout=10, session=robots_session):
                continue
            try:
                resp = page.goto(url, timeout=nav_timeout_ms, wait_until="domcontentloaded")
                if resp is None or resp.status != 200:
                    continue
                try:
                    page.wait_for_load_state("networkidle", timeout=max(5000, nav_timeout_ms // 2))
                except PlaywrightTimeoutError:
                    pass
            except PlaywrightTimeoutError:
                pass
            except Exception:
                continue

            html = page.content()
            text = strip_tags(html)
            tier = page_tier(url)

            for addr, _conf in extract_emails(html, text):
                key = addr.lower()
                if key not in email_candidates or tier < email_candidates[key]["tier"]:
                    email_candidates[key] = {"addr": addr, "tier": tier, "url": url}

            p, pc = pick_best_phone(extract_phones(html, text))
            if p and (best_phone_conf != "high" or pc == "high"):
                if best_phone is None or pc == "high":
                    best_phone, best_phone_conf, phone_source = p, pc, url

            if form_url is None and has_contact_form(url, html):
                form_url = url
    finally:
        context.close()

    best_email, best_email_conf, email_source = choose_best_email(email_candidates)

    return {
        "email": best_email, "email_confidence": best_email_conf, "email_source": email_source,
        "phone": best_phone, "phone_confidence": best_phone_conf, "phone_source": phone_source,
        "form": form_url,
    }


def _empty_result():
    return {"email": None, "email_confidence": None, "email_source": None,
            "phone": None, "phone_confidence": None, "phone_source": None,
            "form": None}

def _launch_browser(p):
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

def main():
    parser = argparse.ArgumentParser(description="Headless-browser deep probe for JS-rendered org sites")
    parser.add_argument("--all", action="store_true", help="Include inactive orgs (default: active only)")
    parser.add_argument("--slug", metavar="SLUG", help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=20, metavar="N", help="Per-page navigation timeout in seconds (default: 20)")
    parser.add_argument("--write", action="store_true", help="Write high-confidence findings to contact: frontmatter (default: report only)")
    parser.add_argument("--force", action="store_true", help="Re-check orgs that already have contact.email, and overwrite existing values")
    parser.add_argument("--output", metavar="FILE", help="Write JSON results to FILE")
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages found matching criteria.")
        sys.exit(0)

    robots_session = requests.Session()
    robots_session.headers.update({"User-Agent": DOD_USER_AGENT})

    results = []
    written = 0
    crashed = 0
    print(f"\nDeep-probing {len(orgs)} org website(s) with a headless browser "
          f"(timeout={args.timeout}s/page — this is slow, be patient)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        existing = org["contact"]
        if not args.force and existing.get("email"):
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has email)")
            continue

        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)

        found = _empty_result()
        signal.signal(signal.SIGALRM, _on_alarm)
        try:
            urls = crawl_urls(org["website"])
            wall_timeout = args.timeout * len(urls) + 30
            signal.alarm(wall_timeout)
            with sync_playwright() as p:
                browser = _launch_browser(p)
                try:
                    found = probe_contact_deep(
                        org["website"], browser,
                        nav_timeout_ms=args.timeout * 1000,
                        robots_session=robots_session,
                    )
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass
        except (_DeepTimeout, Exception) as e:
            msg = "timed out" if isinstance(e, _DeepTimeout) else str(e)
            print(f"ERROR ({msg}, skipping)")
            crashed += 1
            continue
        finally:
            signal.alarm(0)

        results.append({"slug": slug, **found})

        parts = []
        if found["email"]:
            parts.append(f"email={found['email']}")
        if found["phone"]:
            tag = "" if found["phone_confidence"] == "high" else " [low-confidence, verify manually]"
            parts.append(f"phone={found['phone']}{tag}")
        if found["form"]:
            parts.append(f"form={found['form']}")
        print("; ".join(parts) if parts else "nothing found (may genuinely not be a SPA gap)")

        if args.write:
            write_email = found["email"] if found["email_confidence"] == "high" else None
            write_phone = found["phone"] if found["phone_confidence"] == "high" else None
            write_form = found["form"]
            source = found["email_source"] or found["phone_source"] or write_form
            if (write_email or write_phone or write_form) and write_contact(
                org["path"], email=write_email, phone=write_phone, form=write_form,
                source=source, force=args.force
            ):
                written += 1
                print(f"           → wrote contact: block ({source})")

    print(f"\n{'=' * 60}")
    print(f"Checked {len(results)} org(s)")
    if crashed:
        print(f"{crashed} browser crash(es) — skipped; re-run to retry")
    if args.write:
        print(f"Wrote contact: block for {written} org(s)")
    else:
        print("Report only — pass --write to save findings to contact: frontmatter")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
