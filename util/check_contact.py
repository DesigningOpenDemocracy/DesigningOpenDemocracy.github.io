#!/usr/bin/env python3
"""
check_contact.py — Probe org websites for publicly-published email/phone contact info.

For each org with a live website (non-Wayback), fetches the homepage and a
handful of likely contact-page paths (/contact, /about, /get-involved, …)
and extracts:
  - email addresses from mailto: links, Cloudflare-obfuscated data-cfemail
    attributes, and plain @domain.tld-shaped text (all high confidence — the
    pattern itself is unambiguous, whether or not it's wrapped in a link)
  - phone numbers from tel: links (high confidence) and phone-shaped digit
    sequences in page text (low confidence — reported only, never
    auto-written; digit runs produce real false positives: dates, postcodes,
    prices)

Only high-confidence findings are written to contact: frontmatter, and only
with --write (default is report-only). Existing contact.email/contact.phone
values are never overwritten unless --force. This is a starting point, not
a substitute for judgement — it can't tell a general office line from a
named individual's personal mobile, or a stale number from a current one.
Review what it finds before trusting it.

Usage:
    python util/check_contact.py                 # report on active orgs missing contact info
    python util/check_contact.py --all            # include inactive orgs
    python util/check_contact.py --slug loomio     # check one org by slug
    python util/check_contact.py --timeout 8       # per-request timeout in seconds
    python util/check_contact.py --write           # write high-confidence findings to contact:
    python util/check_contact.py --force           # re-check/overwrite orgs that already have contact info
    python util/check_contact.py --output results.json

Requirements: requests, python-frontmatter (util/requirements.txt)
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse, unquote
from urllib.robotparser import RobotFileParser

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

DOD_USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = datetime.today().strftime("%Y-%m-%d")

# Likely contact-info paths, tried in order after the homepage.
CONTACT_PATHS = [
    "/contact", "/contact/", "/contact-us", "/contact-us/",
    "/about", "/about/", "/about-us", "/about-us/",
    "/get-involved", "/get-involved/",
]

MAILTO_RE = re.compile(r'mailto:([^"\'?\s<>]+)', re.IGNORECASE)
TEL_RE = re.compile(r'tel:([^"\'\s<>]+)', re.IGNORECASE)
CF_EMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
EMAIL_TEXT_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b')
# Loose local/international phone shapes; digit-count filter in add_phone()
# does most of the false-positive rejection (dates, postcodes, IDs, etc.)
PHONE_TEXT_RE = re.compile(
    r'(?<!\d)(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)'
)

GENERIC_EMAIL_PREFIXES = (
    "info@", "contact@", "hello@", "enquiries@", "enquiry@", "inquiries@",
    "admin@", "office@", "secretary@", "media@", "support@", "membership@",
)

BAD_EMAIL_SUBSTRINGS = (
    "example.com", "yourdomain", "sentry.io", "wixpress.com", "godaddy.com",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "schema.org", "w3.org",
    "domain.com", "email.com",
)


def decode_cf_email(hexstr):
    """Decode a Cloudflare email-obfuscation data-cfemail hex string."""
    try:
        r = int(hexstr[:2], 16)
        return "".join(
            chr(int(hexstr[i:i + 2], 16) ^ r)
            for i in range(2, len(hexstr), 2)
        )
    except Exception:
        return None


def strip_tags(html):
    """Crude visible-text extraction: drop script/style blocks, then tags."""
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    return unescape(text)


def extract_emails(html, text):
    """Return [(email, confidence)] found via mailto:/cfemail links or in visible text.

    Email matches are all treated as 'high' confidence (after the bad-substring
    filter, an `@domain.tld` shaped string in page text is an unambiguous signal
    whether or not it's wrapped in a mailto: link — many sites just print the
    address as plain text). Contrast with extract_phones(), where free-text
    digit sequences are a much noisier signal and stay 'low' confidence.
    """
    seen = {}

    def add(addr):
        addr = addr.strip().strip(".,;")
        if not addr or "@" not in addr:
            return
        if any(bad in addr.lower() for bad in BAD_EMAIL_SUBSTRINGS):
            return
        seen[addr.lower()] = addr

    for m in MAILTO_RE.finditer(html):
        add(unquote(m.group(1).split("?")[0]))
    for m in CF_EMAIL_RE.finditer(html):
        decoded = decode_cf_email(m.group(1))
        if decoded:
            add(decoded)
    for m in EMAIL_TEXT_RE.finditer(text):
        add(m.group(0))

    return [(addr, "high") for addr in seen.values()]


def extract_phones(html, text):
    """Return [(phone, confidence)] — 'high' from tel: links, 'low' from free text."""
    seen = {}

    def add(num, conf):
        digits = re.sub(r"\D", "", num)
        if not (8 <= len(digits) <= 12):
            return
        key = digits
        num = num.strip()
        if key not in seen:
            seen[key] = {"num": num, "conf": conf}
        elif conf == "high" and seen[key]["conf"] == "low":
            seen[key]["conf"] = "high"

    for m in TEL_RE.finditer(html):
        add(unquote(m.group(1)), "high")
    for m in PHONE_TEXT_RE.finditer(text):
        add(m.group(0), "low")

    return [(v["num"], v["conf"]) for v in seen.values()]


def pick_best_email(candidates):
    if not candidates:
        return None, None
    high = [c for c in candidates if c[1] == "high"]
    pool = high or candidates
    for addr, conf in pool:
        if addr.lower().startswith(GENERIC_EMAIL_PREFIXES):
            return addr, conf
    return pool[0]


def pick_best_phone(candidates):
    if not candidates:
        return None, None
    high = [c for c in candidates if c[1] == "high"]
    pool = high or candidates
    return pool[0]


def robots_allowed(url, timeout=5, session=None):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, timeout=timeout)
        rp.parse(resp.text.splitlines())
    except Exception:
        return True  # unreachable robots.txt → assume allowed
    return rp.can_fetch(DOD_USER_AGENT, url)


def probe_contact(website, timeout=10, session=None):
    """Fetch the org's own page, the site homepage, and likely contact pages;
    return the best email/phone found. The org's given website: URL is tried
    first — it may already be a specific subpage (e.g. a university centre's
    page) that generic /contact-style paths on the domain root would miss."""
    parsed = urlparse(website)
    root = f"{parsed.scheme}://{parsed.netloc}"

    urls = []
    for candidate in [website, root + "/"] + [urljoin(root, p) for p in CONTACT_PATHS]:
        if candidate not in urls:
            urls.append(candidate)

    best_email, best_email_conf, email_source = None, None, None
    best_phone, best_phone_conf, phone_source = None, None, None

    for url in urls:
        if best_email_conf == "high" and best_phone_conf == "high":
            break
        if not robots_allowed(url, timeout=timeout, session=session):
            continue
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code != 200:
                continue
        except RequestException:
            continue

        html = r.text
        text = strip_tags(html)

        e, ec = pick_best_email(extract_emails(html, text))
        if e and (best_email_conf != "high" or ec == "high") and e.lower() != (best_email or "").lower():
            if best_email is None or ec == "high":
                best_email, best_email_conf, email_source = e, ec, url

        p, pc = pick_best_phone(extract_phones(html, text))
        if p and (best_phone_conf != "high" or pc == "high"):
            if best_phone is None or pc == "high":
                best_phone, best_phone_conf, phone_source = p, pc, url

        time.sleep(0.3)

    return {
        "email": best_email, "email_confidence": best_email_conf, "email_source": email_source,
        "phone": best_phone, "phone_confidence": best_phone_conf, "phone_source": phone_source,
    }


def write_contact(path, email=None, phone=None, source=None, force=False):
    """Write/update the contact: frontmatter block. Only overwrites existing
    email/phone values when force=True. Returns True if the file changed."""
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0] != "":
        return False
    yaml_block, rest = parts[1], parts[2]
    meta = _yaml.safe_load(yaml_block) or {}
    existing = meta.get("contact") or {}

    new_email = existing.get("email")
    if email and (force or not new_email):
        new_email = email
    new_phone = existing.get("phone")
    if phone and (force or not new_phone):
        new_phone = phone

    if new_email == existing.get("email") and new_phone == existing.get("phone"):
        return False  # nothing changed

    block_lines = ["contact:"]
    if new_email:
        block_lines.append(f"  email: {new_email}")
    if new_phone:
        block_lines.append(f'  phone: "{new_phone}"')
    block_lines.append(f"  source: {source or existing.get('source', '')}")
    block_lines.append(f"  checked: {TODAY}")

    if "contact" in meta:
        lines = yaml_block.split("\n")
        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^contact\s*:", line):
                out.extend(block_lines)
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") and lines[i].strip() != ""):
                    i += 1
                continue
            out.append(line)
            i += 1
        yaml_block = "\n".join(out)
    else:
        m = re.search(r'^(website\s*:.*\n)', yaml_block, re.MULTILINE)
        block_text = "\n".join(block_lines) + "\n"
        if m:
            yaml_block = yaml_block[:m.end()] + block_text + yaml_block[m.end():]
        else:
            yaml_block = yaml_block.rstrip("\n") + "\n" + block_text

    if not yaml_block.endswith("\n"):
        yaml_block += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True


def load_orgs(slug_filter=None, include_inactive=False):
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        meta = post.metadata
        slug = os.path.basename(path)[:-3]
        if slug_filter and slug != slug_filter:
            continue
        website = meta.get("website", "") or ""
        if not website or WAYBACK_PREFIX in website:
            continue
        status = meta.get("status", "")
        if not include_inactive and status != "active":
            continue
        orgs.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "website": website,
            "status": status,
            "path": path,
            "contact": meta.get("contact") or {},
        })
    return orgs


def main():
    parser = argparse.ArgumentParser(description="Probe org websites for publicly-published email/phone contact info")
    parser.add_argument("--all", action="store_true", help="Include inactive orgs (default: active only)")
    parser.add_argument("--slug", metavar="SLUG", help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=10, metavar="N", help="Per-request timeout in seconds (default: 10)")
    parser.add_argument("--write", action="store_true", help="Write high-confidence findings to contact: frontmatter (default: report only)")
    parser.add_argument("--force", action="store_true", help="Re-check orgs that already have contact.email and contact.phone, and overwrite existing values")
    parser.add_argument("--output", metavar="FILE", help="Write JSON results to FILE")
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages found matching criteria.")
        sys.exit(0)

    session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})

    results = []
    written = 0
    print(f"\nProbing {len(orgs)} org website(s) for contact info (timeout={args.timeout}s)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        existing = org["contact"]
        if not args.force and existing.get("email") and existing.get("phone"):
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has email + phone)")
            continue

        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)
        found = probe_contact(org["website"], timeout=args.timeout, session=session)
        results.append({"slug": slug, **found})

        parts = []
        if found["email"]:
            tag = "" if found["email_confidence"] == "high" else " [low-confidence, verify manually]"
            parts.append(f"email={found['email']}{tag}")
        if found["phone"]:
            tag = "" if found["phone_confidence"] == "high" else " [low-confidence, verify manually]"
            parts.append(f"phone={found['phone']}{tag}")
        print("; ".join(parts) if parts else "nothing found")

        if args.write:
            write_email = found["email"] if found["email_confidence"] == "high" else None
            write_phone = found["phone"] if found["phone_confidence"] == "high" else None
            source = found["email_source"] or found["phone_source"]
            if (write_email or write_phone) and write_contact(
                org["path"], email=write_email, phone=write_phone, source=source, force=args.force
            ):
                written += 1
                print(f"           → wrote contact: block ({source})")

    print(f"\n{'=' * 60}")
    print(f"Checked {len(results)} org(s)")
    if args.write:
        print(f"Wrote contact: block for {written} org(s) — only high-confidence (mailto:/tel:) findings are auto-written")
    else:
        print("Report only — pass --write to save high-confidence findings to contact: frontmatter")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
