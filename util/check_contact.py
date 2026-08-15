#!/usr/bin/env python3
"""
check_contact.py — Probe org websites for publicly-published email/phone/
contact-form/social-channel info.

Three tiers of finding, three different trust levels:

  - Email addresses (mailto: links, Cloudflare-obfuscated data-cfemail
    attributes, plain @domain.tld-shaped text) and detected public contact
    forms are "high confidence" and SAFE FOR --write TO RUN UNATTENDED
    ACROSS THE FULL ORG LIST. An @domain.tld string is an unambiguous
    pattern regardless of whether it's wrapped in a mailto: link, and a
    contact-page <form> with an email/message field is unambiguously "this
    org wants the public to reach them here" — there's no text-parsing
    guesswork involved in either. A contact form is only recorded when
    BOTH the page URL reads as a contact page AND the form itself has a
    field that looks like an email/message/enquiry field (see
    has_contact_form()) — a login form or newsletter widget elsewhere on
    the site won't be mistaken for one.
  - Social/chat channel links (Telegram, Discord, WhatsApp, Signal,
    Instagram — see SOCIAL_LINK_PATTERNS) are structurally unambiguous the
    same way mailto: is (a real href in the org's own page HTML, not a
    text-parsing guess) but are NOT auto-written even with --write —
    report-only, always. The reason is a real failure mode, not a
    theoretical one: confirmed on lismore-peoples-assembly.md, whose site
    is shared with its parent org (Reclaim Our Recovery) — the page's own
    prose correctly links instagram.com/lismorepeoplesassembly, but the
    site-wide footer chrome the crawler actually finds links
    instagram.com/reclaim_our_recovery, the *parent's* account. A wrong
    social handle actively misdirects a reader, unlike a shared parent
    email (still a genuinely valid way to reach the sub-project). Any org
    that's "a project of" another org sharing its domain is at risk of
    this, and there's no cheap heuristic that reliably tells the two
    apart — so every channel finding needs a human to actually look at the
    org's own page before it goes in the frontmatter.
  - Phone numbers: tel: links are high confidence, but phone-shaped digit
    sequences in free text are NOT — digit runs produce real false
    positives (dates, postcodes, prices; one comparison-testing run
    against orgs already researched by hand turned up a "(212) 555-0110"
    placeholder number lifted from a JS snippet). Free-text phone matches
    are report-only and never auto-written, full stop.

Comparison-testing the email/tel: tier against org contact info already
sourced by hand found it matched almost exactly; the few disagreements were
judgement calls a script can't make on its own (which of several valid
published addresses is the "right" one to record — see CLAUDE.md's contact:
convention for the preference order) rather than parsing failures. So: run
--write freely for the email/form tier at whatever scale you like, but treat
its choice among several valid addresses, and any --force overwrite of an
existing value, as something worth spot-checking in the resulting diff.

For each org with a live website (non-Wayback), fetches the homepage and a
handful of likely contact-page paths (/contact, /about, /get-involved, …).
When multiple pages each publish a different email, the one on a page whose
URL actually reads as the contact page wins (see page_tier()) — chosen after
the whole crawl, not by "whichever page happened to be checked last."
Earlier revisions picked whichever email was found on the last page fetched,
which meant a stray footer address on a low-relevance page could silently
outrank a real info@ address on the actual contact page.

Only high-confidence findings (email, tel:, detected form) are written to
contact: frontmatter, and only with --write (default is report-only).
Existing contact.email/contact.phone/contact.form values are never
overwritten unless --force.

Usage:
    python util/check_contact.py                 # report on active orgs missing contact info
    python util/check_contact.py --all            # include inactive orgs
    python util/check_contact.py --slug loomio     # check one org by slug
    python util/check_contact.py --timeout 8       # per-request timeout in seconds
    python util/check_contact.py --write           # write high-confidence email/phone/form to contact:
    python util/check_contact.py --slug X --write --write-channels  # also write social channels, one org at a time, after reading the report
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
SKIP_FILES = {"index.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = datetime.today().strftime("%Y-%m-%d")

# Likely contact-info paths, tried in order after the homepage.
CONTACT_PATHS = [
    "/contact", "/contact/", "/contact-us", "/contact-us/", "/contactus",
    "/about", "/about/", "/about-us", "/about-us/",
    "/get-involved", "/get-involved/",
    "/page/contacts", "/page/contact",
    "/en/page/contacts", "/en/about/contact/",
    "/tos", "/terms", "/terms-of-service",
    "/careers", "/careers/",
    "/support", "/support/",
]

# Anchored to href=["']mailto:/tel: specifically — not just the bare string
# "mailto:"/"tel:" anywhere in the page. Confirmed necessary: an unscoped
# `tel:` search matched into a minified-JS form-validation config object
# that happened to have a property key named `tel` ({email:!1,tel:!1,
# text:!1,...}), extracting a chunk of JS as a "phone number".
MAILTO_RE = re.compile(r'href=["\']mailto:([^"\'?\s<>]+)', re.IGNORECASE)
TEL_RE = re.compile(r'href=["\']tel:([^"\'\s<>]+)', re.IGNORECASE)
CF_EMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
# (?<!@) rejects Mastodon/Fediverse handles ("@user@instance.tld", commonly
# shown in social-links widgets) — without it, the text following the
# handle's leading @ sigil matches the local@domain shape perfectly and
# reads as a real email (confirmed against oaf@social.oaf.org.au, actually
# "@oaf@social.oaf.org.au" — a Mastodon handle in an org's social links list).
EMAIL_TEXT_RE = re.compile(r'(?<!@)\b[\w.+-]+@(?:[\w-]+\.)+[a-zA-Z]{2,}\b')
# Final sanity gate applied to every candidate regardless of which regex
# found it — anchored, allowed-characters-only. Confirmed necessary: a
# mailto: href inside an escaped JS string literal (mailto:foo@bar.org\')
# was captured with a trailing backslash, since MAILTO_RE's capture group
# excludes quotes but not backslash. Catches that class of leakage in
# general rather than chasing each escape sequence individually.
EMAIL_SHAPE_RE = re.compile(r'^[\w.+-]+@(?:[\w-]+\.)+[a-zA-Z]{2,}$')
# Loose local/international phone shapes; digit-count filter in add_phone()
# does most of the false-positive rejection (dates, postcodes, IDs, etc.)
PHONE_TEXT_RE = re.compile(
    r'(?<!\d)(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)'
)

GENERIC_EMAIL_PREFIXES = (
    "info@", "contact@", "hello@", "enquiries@", "enquiry@", "inquiries@",
    "admin@", "office@", "secretary@", "media@", "support@", "membership@",
    # non-English "hello"/"contact" equivalents — an org publishing e.g.
    # "hola@" or "kontakt@" as its address is doing the same generic-address
    # thing an English-language org does with "hello@"/"contact@"
    "hola@", "hallo@", "bonjour@", "kontakt@", "contacto@", "kontact@",
)

# A <form> is only treated as a "public contact form" when it's on a page
# whose own URL says it's the contact page (so a newsletter-signup widget
# embedded on some unrelated page doesn't get picked up) AND the form itself
# contains a field that looks like it's for a message/enquiry (so a search
# box or login form on that page isn't mistaken for one either).
CONTACT_PATH_HINT_RE = re.compile(r'contact', re.IGNORECASE)
FORM_TAG_RE = re.compile(r'<form\b[^>]*>(.*?)</form>', re.IGNORECASE | re.DOTALL)
CONTACT_FORM_FIELD_RE = re.compile(
    r'type=["\']?email|name=["\']?(?:email|e-?mail|message|msg|subject|enquiry|inquiry)|<textarea',
    re.IGNORECASE,
)

BAD_EMAIL_SUBSTRINGS = (
    "example.com", "yourdomain", "sentry.io", "wixpress.com", "godaddy.com",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "schema.org", "w3.org",
    "domain.com", "email.com",
)

# Social/chat channels, matched the same way as mailto:/tel: — an href
# structurally present in the org's own page HTML, not a text-parsing
# guess, so (like email) every match is "high confidence". Limited to the
# platforms CLAUDE.md's contact.channels: doc names as examples (Telegram,
# Discord, Signal, Instagram, WhatsApp) rather than trying to cover every
# social platform that exists — easy to extend with another tuple later.
# Each pattern captures the FULL url (not just a handle) since signal.me
# (personal contact link) and signal.group (group invite) aren't
# interchangeable — reconstructing from a handle + one template per type
# would silently rewrite one into the other. Each also requires a
# path/handle after the domain so a bare "instagram.com" or "t.me" link (a
# generic nav icon with no destination, or a share-widget stub) isn't
# captured as if it were the org's account.
SOCIAL_LINK_PATTERNS = [
    ("telegram", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?t\.me/(?!share\b)[^"\'\s<>]+)', re.IGNORECASE)),
    ("telegram", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?telegram\.me/(?!share\b)[^"\'\s<>]+)', re.IGNORECASE)),
    ("discord", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?discord\.gg/[^"\'\s<>]+)', re.IGNORECASE)),
    ("discord", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?discord\.com/invite/[^"\'\s<>]+)', re.IGNORECASE)),
    ("whatsapp", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?wa\.me/[^"\'\s<>]+)', re.IGNORECASE)),
    ("whatsapp", re.compile(r'href=["\']((?:https?:)?//chat\.whatsapp\.com/[^"\'\s<>]+)', re.IGNORECASE)),
    ("signal", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?signal\.group/[^"\'\s<>]+)', re.IGNORECASE)),
    ("signal", re.compile(r'href=["\']((?:https?:)?//(?:www\.)?signal\.me/[^"\'\s<>]+)', re.IGNORECASE)),
    ("instagram", re.compile(
        r'href=["\']((?:https?:)?//(?:www\.)?instagram\.com/'
        r'(?!p/|reel/|explore\b|accounts/|tv/|stories/)[^"\'\s<>/?#]+)', re.IGNORECASE)),
]

# Tracking query params (utm_*, igshid, etc.) commonly appended to social
# links copied from a share button — stripped so two links to the same
# account don't dedupe as "different", and so the stored URL is clean.
SOCIAL_TRACKING_PARAM_RE = re.compile(r'[?&](utm_[^=&]+|igshid|fbclid|ref)=[^&"\'\s<>]*')


SOCIAL_URL_TYPES = {channel_type for channel_type, _ in SOCIAL_LINK_PATTERNS}


def clean_social_url(url):
    """Normalise a captured social link: ensure a scheme, strip tracking
    params, drop a trailing bare '?' or '&' left after stripping them."""
    if url.startswith("//"):
        url = "https:" + url
    url = SOCIAL_TRACKING_PARAM_RE.sub("", url)
    url = re.sub(r'[?&]$', "", url)
    return url.rstrip("/.,;")


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
        if not addr or not EMAIL_SHAPE_RE.match(addr):
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


def extract_social_channels(html):
    """Return [(type, url)] for each recognised social/chat platform link
    found as a structural href in the page HTML — first match per type
    wins (social links are typically persistent site chrome present on
    every crawled page, so which specific page it was found on doesn't
    carry the significance page_tier() gives email addresses)."""
    seen = {}
    for channel_type, pattern in SOCIAL_LINK_PATTERNS:
        if channel_type in seen:
            continue
        m = pattern.search(html)
        if m:
            seen[channel_type] = clean_social_url(m.group(1))
    return list(seen.items())


def has_contact_form(url, html):
    """True if url's path reads as a contact page AND it has a <form> with
    an email/message-shaped field — not just any form on any page."""
    if not CONTACT_PATH_HINT_RE.search(urlparse(url).path):
        return False
    for m in FORM_TAG_RE.finditer(html):
        if CONTACT_FORM_FIELD_RE.search(m.group(1)):
            return True
    return False


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


def page_tier(url):
    """Rank a page's authority as an email source: lower is more authoritative.
    A /contact-ish page publishing an address is a deliberate "reach us here"
    statement; a homepage or /get-involved page might just have a stray
    footer/copyright address that happens to match the regex. Used so a
    later-crawled, lower-value page never silently outranks an earlier,
    more authoritative one purely because it was fetched later."""
    path = urlparse(url).path.lower()
    if "contact" in path:
        return 0
    if "about" in path or "get-involved" in path:
        return 1
    return 2


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


def crawl_urls(website):
    """The ordered, deduped list of URLs a contact probe should try: the
    org's own given website: URL first (it may already be a specific
    subpage, e.g. a university centre's page, that generic /contact-style
    paths on the domain root would miss), then the domain root, then each
    of CONTACT_PATHS. Shared by check_contact.py and check_contact_deep.py
    so the crawl strategy can't silently drift between the two."""
    parsed = urlparse(website)
    root = f"{parsed.scheme}://{parsed.netloc}"
    urls = []
    for candidate in [website, root + "/"] + [urljoin(root, p) for p in CONTACT_PATHS]:
        if candidate not in urls:
            urls.append(candidate)
    return urls


def choose_best_email(email_candidates):
    """Given the {addr.lower(): {"addr","tier","url"}} map accumulated across
    a crawl, pick the one to report: lowest tier (contact page > about page
    > homepage) first, then the generic-address preference in
    pick_best_email(). Returns (addr, confidence, source_url) or (None, None,
    None). Split out so both check_contact.py and check_contact_deep.py make
    this choice identically — deliberately avoids "last page crawled wins",
    since with every extracted email treated as equally high-confidence,
    naively overwriting on each new match would let a stray footer address
    on a later-fetched, less relevant page silently outrank a real info@
    found earlier on the actual contact page."""
    if not email_candidates:
        return None, None, None
    min_tier = min(c["tier"] for c in email_candidates.values())
    pool = [c for c in email_candidates.values() if c["tier"] == min_tier]
    chosen_addr, _ = pick_best_email([(c["addr"], "high") for c in pool])
    chosen = next(c for c in pool if c["addr"] == chosen_addr)
    return chosen["addr"], "high", chosen["url"]


def probe_contact(website, timeout=10, session=None):
    """Fetch the org's own page, the site homepage, and likely contact pages
    with a plain HTTP GET; return the best email/phone/form found. Only sees
    what's in the raw server-rendered HTML — a JavaScript-rendered page (a
    React/Vue/etc. single-page app with an empty <div id="app"> shell in the
    static response) is invisible to this. check_contact_deep.py is the
    companion tool for that case: same extraction logic, but driven by a
    real (headless) browser so client-side-rendered content actually exists
    by the time it scrapes."""
    urls = crawl_urls(website)

    email_candidates = {}  # addr.lower() -> {"addr", "tier", "url"} (best tier kept per address)
    best_phone, best_phone_conf, phone_source = None, None, None
    form_url = None
    channels = {}  # type -> url, first found across the crawl

    for url in urls:
        best_email_tier = min((c["tier"] for c in email_candidates.values()), default=None)
        if (best_email_tier == 0 and best_phone_conf == "high" and form_url
                and len(channels) == len(SOCIAL_URL_TYPES)):
            break  # already have a contact-page email, a tel: phone, a form, and every known channel type
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

        for channel_type, channel_url in extract_social_channels(html):
            channels.setdefault(channel_type, channel_url)

        time.sleep(0.3)

    best_email, best_email_conf, email_source = choose_best_email(email_candidates)

    return {
        "email": best_email, "email_confidence": best_email_conf, "email_source": email_source,
        "phone": best_phone, "phone_confidence": best_phone_conf, "phone_source": phone_source,
        "form": form_url,
        "channels": channels,
    }


def merge_channels(existing_channels, found_channels, force):
    """Merge newly-probed {type: url} findings into an existing channels:
    list (list of {type, url, label?, note?} dicts). Unlike email/phone/
    form (single values, overwrite-or-keep), channels is a growing list —
    a type not already present is always appended; a type that IS already
    present only has its url touched when force=True, and label/note (if
    a human added them, e.g. "main point of contact") are always
    preserved rather than being dropped by a re-probe. Returns
    (new_channels_list, changed_bool)."""
    existing_channels = [dict(c) for c in (existing_channels or [])]
    existing_types = {c.get("type") for c in existing_channels}
    changed = False

    for channel_type, url in found_channels.items():
        if channel_type in existing_types:
            if force:
                existing = next(c for c in existing_channels if c.get("type") == channel_type)
                if existing.get("url") != url:
                    existing["url"] = url
                    changed = True
        else:
            existing_channels.append({"type": channel_type, "url": url})
            existing_types.add(channel_type)
            changed = True

    return existing_channels, changed


def write_contact(path, email=None, phone=None, form=None, channels=None, source=None, force=False):
    """Write/update the contact: frontmatter block. Only overwrites existing
    email/phone/form values when force=True; channels: (a list, not a
    single value) merges new channel types in rather than replacing the
    whole list — see merge_channels(). Returns True if the file changed."""
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---\n"):
        return False
    closing = content.index("\n---\n", 3)
    yaml_block = content[3:closing]
    rest = content[closing:]  # "\n---\n..." — includes closing delimiter and body
    meta = _yaml.safe_load(yaml_block) or {}
    existing = meta.get("contact") or {}

    new_email = existing.get("email")
    if email and (force or not new_email):
        new_email = email
    new_phone = existing.get("phone")
    if phone and (force or not new_phone):
        new_phone = phone
    new_form = existing.get("form")
    if form and (force or not new_form):
        new_form = form
    new_channels, channels_changed = merge_channels(existing.get("channels"), channels or {}, force)

    if (new_email == existing.get("email") and new_phone == existing.get("phone")
            and new_form == existing.get("form") and not channels_changed):
        return False  # nothing changed

    block_lines = ["contact:"]
    if new_email:
        block_lines.append(f"  email: {new_email}")
    if new_phone:
        block_lines.append(f'  phone: "{new_phone}"')
    if new_form:
        block_lines.append(f"  form: {new_form}")
    if new_channels:
        block_lines.append("  channels:")
        for ch in new_channels:
            block_lines.append(f"  - type: {ch['type']}")
            block_lines.append(f"    url: {ch['url']}")
            if ch.get("label"):
                block_lines.append(f"    label: {ch['label']}")
            if ch.get("note"):
                block_lines.append(f"    note: {ch['note']}")
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

    # yaml_block must NOT end with its own trailing "\n" here — content[3:closing]
    # (the original slice this is built from/spliced into) never includes the
    # newline immediately before the closing "\n---\n" delimiter, and `rest`
    # (below) already starts with that "\n". A blanket "add one if missing"
    # safety net used to live here and broke exactly this: it fired on the
    # two branches above that correctly reconstruct without a trailing
    # newline (replacing an existing contact: block, or inserting after an
    # existing website: line), producing "...checked: DATE\n" + "\n---\n" —
    # a blank line before the closing delimiter on every write. Confirmed on
    # lismore-peoples-assembly.md. The `else` branch above is the only one
    # that legitimately needs a trailing newline, and it already adds
    # exactly one itself (via block_text), so no generic fixup belongs here.
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + rest)
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
    parser.add_argument("--write", action="store_true", help="Write high-confidence email/phone/form findings to contact: frontmatter (default: report only)")
    parser.add_argument("--write-channels", action="store_true", help="Also write social/chat channel findings (Telegram, Instagram, etc.) — only after reviewing the report; see module docstring for why these aren't included in plain --write")
    parser.add_argument("--force", action="store_true", help="Re-check orgs that already have contact.email and a full set of known channel types, and overwrite existing email/phone/form/channel values")
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
        existing_channel_types = {c.get("type") for c in (existing.get("channels") or [])}
        already_full = existing.get("email") and SOCIAL_URL_TYPES <= existing_channel_types
        if not args.force and already_full:
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has email + all known channel types)")
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
        if found["form"]:
            parts.append(f"form={found['form']}")
        new_channel_types = set(found["channels"]) - existing_channel_types
        for channel_type in sorted(new_channel_types):
            parts.append(f"{channel_type}={found['channels'][channel_type]} [verify it's this org's own account, not a shared parent's]")
        print("; ".join(parts) if parts else "nothing found")

        if args.write:
            write_email = found["email"] if found["email_confidence"] == "high" else None
            write_phone = found["phone"] if found["phone_confidence"] == "high" else None
            write_form = found["form"]
            # channels are report-only by default (see module docstring —
            # confirmed on lismore-peoples-assembly.md that a shared-domain
            # sub-project's page can surface its PARENT org's social
            # handle) — only written when a human explicitly opts in with
            # --write-channels after reviewing the report output above.
            write_channels = found["channels"] if args.write_channels else {}
            source = found["email_source"] or found["phone_source"] or write_form or (
                org["website"] if write_channels else None)
            if (write_email or write_phone or write_form or write_channels) and write_contact(
                org["path"], email=write_email, phone=write_phone, form=write_form,
                channels=write_channels, source=source, force=args.force
            ):
                written += 1
                print(f"           → wrote contact: block ({source})")

    print(f"\n{'=' * 60}")
    print(f"Checked {len(results)} org(s)")
    if args.write:
        print(f"Wrote contact: block for {written} org(s) — high-confidence email/tel: findings and "
              f"detected public contact forms are auto-written; free-text phone matches never are"
              + (" (channels included — verify each in the diff)" if args.write_channels
                 else "; social channels were report-only (pass --write-channels to also write them)"))
    else:
        print("Report only — pass --write to save high-confidence email/phone/form findings to contact: frontmatter "
              "(social channels always need --write-channels too, and a manual check they're the org's own account)")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
