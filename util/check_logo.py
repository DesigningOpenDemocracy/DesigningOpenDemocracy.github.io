#!/usr/bin/env python3
"""
check_logo.py — Probe org websites for a logo image and populate logo: frontmatter.

For each org with a live website (non-Wayback), fetches the homepage and looks
for a logo candidate in priority order:

  1. An <img> tag whose class/id/alt hints "logo" (excluding hints like
     "sponsor"/"partner"/"client" that belong to someone else's logo shown on
     the page) — the strongest signal, since the page itself is asserting
     "this is my logo".
  2. An SVG favicon (<link rel="icon" type="image/svg+xml">) — usually the
     site's actual brand mark reduced to a vector icon.
  3. An apple-touch-icon (<link rel="apple-touch-icon">) — typically a
     reasonable-resolution (120px+) brand icon, larger `sizes=` wins when
     several are declared.
  4. og:image / twitter:image — a social-share image; not always square or
     logo-shaped, so this and the two below are LOW confidence.
  5. A generic favicon <link rel="icon">, largest declared `sizes=` first.
  6. /favicon.ico as a last-resort guess if nothing else was found at all.

Only high-confidence candidates (1-3) are written to logo: frontmatter by
default; pass --include-low to also write og:image/generic-favicon guesses
(worth a visual spot-check afterwards — see the README table this script
maintains). Existing logo: values are never touched unless --force.

Downloaded images are saved to docs/assets/org-logos/<slug>.<ext> and the
sourcing table in docs/assets/org-logos/README.md is regenerated from
docs/assets/org-logos/sources.json (which this script also maintains) so the
per-logo License/Source columns stay in sync automatically rather than
requiring hand edits at 100+-org scale.

Usage:
    python util/check_logo.py                    # report on active orgs missing logo:
    python util/check_logo.py --all               # include inactive orgs
    python util/check_logo.py --slug loomio        # check one org by slug
    python util/check_logo.py --timeout 10         # per-request timeout in seconds
    python util/check_logo.py --write              # download + write high-confidence finds
    python util/check_logo.py --write --include-low  # also write low-confidence finds
    python util/check_logo.py --force              # re-check orgs that already have logo:
    python util/check_logo.py --output results.json

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
from urllib.parse import urljoin, urlparse
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
LOGOS_DIR = os.path.join(DOCS_DIR, "assets", "org-logos")
SOURCES_JSON = os.path.join(LOGOS_DIR, "sources.json")
README_PATH = os.path.join(LOGOS_DIR, "README.md")
SKIP_FILES = {"organisations.md"}
WAYBACK_PREFIX = "https://web.archive.org"
TODAY = datetime.today().strftime("%Y-%m-%d")

# Excludes another org's logo (a funder/sponsor badge) that happens to also
# carry the word "logo" in its class/alt on the target org's own homepage.
LOGO_HINT_EXCLUDE = ("sponsor", "partner", "client", "funder", "award", "badge")

ATTR_RE = re.compile(
    r'''([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"([^"]*)"|([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*'([^']*)\''''
)

EXT_BY_CONTENT_TYPE = {
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/gif": ".gif",
}
VALID_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif"}

# Rows for these slugs are hand-curated (proof-of-concept batch) — the script
# never overwrites their sources.json entry, only appends new ones.
CURATED_SEED = {
    "vtaiwan": {"title": "vTaiwan", "path": "vtaiwan.png", "license": "Fair use",
                "source": "https://vtaiwan.tw/apple-touch-icon.png", "note": "site icon"},
    "g0v": {"title": "g0v (gov zero)", "path": "g0v.svg", "license": "Fair use",
            "source": "https://g0v.tw/assets/img/g0v-only.svg", "note": "site asset"},
    "decidim": {"title": "Decidim", "path": "decidim.svg", "license": "CC BY-SA 4.0",
                "source": "https://commons.wikimedia.org/wiki/File:Decidim-logo.svg", "note": None},
    "loomio": {"title": "Loomio", "path": "loomio.png", "license": "Fair use",
               "source": "https://www.loomio.com/images/brand/icon-yellow-on-white-1024.png", "note": "brand asset"},
    "consul-democracy": {"title": "Consul Democracy", "path": "consul-democracy.png", "license": "Fair use",
                          "source": "https://consuldemocracy.org/wp-content/uploads/consul_logo.png", "note": "site asset"},
}


def parse_attrs(tag_inner):
    attrs = {}
    for m in ATTR_RE.finditer(tag_inner):
        if m.group(1):
            attrs[m.group(1).lower()] = m.group(2)
        else:
            attrs[m.group(3).lower()] = m.group(4)
    return attrs


def _sizes_value(sizes):
    """Best single dimension out of a sizes="180x180" (or "16x16 32x32") attr."""
    best = 0
    for part in (sizes or "").split():
        m = re.match(r"(\d+)x(\d+)", part)
        if m:
            best = max(best, int(m.group(1)))
    return best


def find_logo_candidates(html, base_url):
    """Return an ordered list of {url, kind, confidence} candidates, best first."""
    img_logo, svg_icon, touch_icon, social_image, favicon = [], [], [], [], []

    for m in re.finditer(r"<img\b([^>]*)>", html, re.IGNORECASE):
        attrs = parse_attrs(m.group(1))
        # Lazy-load libraries commonly stash a tiny blur/placeholder in src and
        # the real image in a data-* attribute — prefer those when present
        # (confirmed necessary: flacso-cuba and internet-freedom-foundation
        # both resolved to blank-white placeholder images via bare src).
        src = (attrs.get("data-src") or attrs.get("data-lazy-src")
               or attrs.get("data-original") or attrs.get("src"))
        if not src:
            continue
        hint = " ".join([attrs.get("class", ""), attrs.get("id", ""), attrs.get("alt", "")]).lower()
        if "logo" in hint and not any(bad in hint for bad in LOGO_HINT_EXCLUDE):
            img_logo.append({"url": urljoin(base_url, src), "kind": "img-logo", "confidence": "high"})

    for m in re.finditer(r"<link\b([^>]*)>", html, re.IGNORECASE):
        attrs = parse_attrs(m.group(1))
        rel = (attrs.get("rel") or "").lower()
        href = attrs.get("href")
        if not href or "icon" not in rel:
            continue
        if attrs.get("type", "").lower() == "image/svg+xml":
            svg_icon.append({"url": urljoin(base_url, href), "kind": "svg-icon", "confidence": "high"})
        elif "apple-touch-icon" in rel:
            touch_icon.append({"url": urljoin(base_url, href), "kind": "apple-touch-icon",
                                "confidence": "high", "_size": _sizes_value(attrs.get("sizes"))})
        else:
            favicon.append({"url": urljoin(base_url, href), "kind": "favicon",
                             "confidence": "low", "_size": _sizes_value(attrs.get("sizes"))})

    for m in re.finditer(r"<meta\b([^>]*)>", html, re.IGNORECASE):
        attrs = parse_attrs(m.group(1))
        prop = (attrs.get("property") or attrs.get("name") or "").lower()
        content = attrs.get("content")
        if prop in ("og:image", "twitter:image") and content:
            social_image.append({"url": urljoin(base_url, content), "kind": "og-image", "confidence": "low"})

    touch_icon.sort(key=lambda c: -c.pop("_size"))
    favicon.sort(key=lambda c: -c.pop("_size"))

    candidates = img_logo + svg_icon + touch_icon + social_image + favicon
    candidates.append({"url": urljoin(base_url, "/favicon.ico"), "kind": "favicon-fallback", "confidence": "low"})
    return candidates


def robots_allowed(url, timeout=5, session=None):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, timeout=timeout)
        rp.parse(resp.text.splitlines())
    except Exception:
        return True
    return rp.can_fetch(DOD_USER_AGENT, url)


def download_logo(url, dest_path_noext, timeout=10, session=None):
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code != 200 or len(r.content) < 300:
            return None
    except RequestException:
        return None

    content_type = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    ext = EXT_BY_CONTENT_TYPE.get(content_type)
    if not ext:
        path_ext = os.path.splitext(urlparse(url).path)[1].lower()
        if path_ext in VALID_EXTS:
            ext = path_ext
    if not ext:
        return None

    dest_path = dest_path_noext + ext
    with open(dest_path, "wb") as f:
        f.write(r.content)
    return dest_path, ext, len(r.content)


def probe_logo(website, slug, timeout=10, session=None):
    if not robots_allowed(website, timeout=timeout, session=session):
        return {"error": "blocked by robots.txt"}
    try:
        r = session.get(website, timeout=timeout)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
    except RequestException as e:
        return {"error": str(e)}

    candidates = find_logo_candidates(r.text, website)
    for cand in candidates:
        dest_noext = os.path.join(LOGOS_DIR, slug)
        result = download_logo(cand["url"], dest_noext, timeout=timeout, session=session)
        if result:
            dest_path, ext, size = result
            return {
                "kind": cand["kind"], "confidence": cand["confidence"],
                "source_url": cand["url"], "logo_path": f"/assets/org-logos/{slug}{ext}",
                "dest_path": dest_path, "bytes": size,
            }
        time.sleep(0.2)
    return {"error": "no downloadable candidate found"}


def write_logo_field(path, logo_value, force=False):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if not content.startswith("---\n"):
        return False
    closing = content.index("\n---\n", 3)
    yaml_block = content[3:closing]
    rest = content[closing:]

    if re.search(r"^logo\s*:", yaml_block, re.MULTILINE):
        if not force:
            return False
        yaml_block = re.sub(r"^logo\s*:.*$", f"logo: {logo_value}", yaml_block, count=1, flags=re.MULTILINE)
    else:
        m = re.search(r"^(website\s*:.*\n)", yaml_block, re.MULTILINE)
        if m:
            yaml_block = yaml_block[:m.end()] + f"logo: {logo_value}\n" + yaml_block[m.end():]
        else:
            # No trailing \n here: yaml_block never includes the newline
            # immediately before the closing "\n---\n" (that belongs to
            # `rest`), so adding one would leave a blank line before it.
            yaml_block = yaml_block.rstrip("\n") + "\n" + f"logo: {logo_value}"

    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + rest)
    return True


def load_sources():
    if os.path.exists(SOURCES_JSON):
        with open(SOURCES_JSON, encoding="utf-8") as f:
            return json.load(f)
    seed = {}
    for slug, entry in CURATED_SEED.items():
        seed[slug] = dict(entry)
    return seed


def save_sources(sources):
    with open(SOURCES_JSON, "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def write_readme(sources):
    rows = []
    for slug, e in sorted(sources.items(), key=lambda kv: kv[1]["title"].lower()):
        source_label = "Commons" if "commons.wikimedia.org" in e["source"] else urlparse(e["source"]).netloc
        note = f" ({e['note']})" if e.get("note") else ""
        rows.append(f"| {e['title']} | ![]({e['path']}) | {e['license']} | [{source_label}]({e['source']}){note} |")

    table = "\n".join(rows)
    content = f"""# Organisation logos

Each logo file is the property of its respective organisation. Used here for identification
and informational purposes under fair dealing / fair use provisions, except where a file is
sourced from Wikimedia Commons under an open license (marked below).

This table is auto-generated by `util/check_logo.py` from `docs/assets/org-logos/sources.json`
— don't hand-edit the table below, edit `sources.json` (or re-run the script) instead. The
`logo:` field convention itself is documented in `CLAUDE.md` under "Organisation pages".

| Organisation | Logo | License | Source |
|---|---|---|---|
{table}

## Adding a logo

Run `python util/check_logo.py --slug <org-slug> --write` to probe the org's own website and
download the best logo candidate automatically. It writes the image to
`docs/assets/org-logos/<slug>.<ext>`, sets `logo:` in the org's frontmatter, and updates this
README's table. Only high-confidence candidates (an explicit `<img>` logo tag, an SVG favicon,
or an apple-touch-icon) are written by default — pass `--include-low` to also accept a
lower-confidence guess (a generic favicon or social-share image), and spot-check those visually
afterwards.

To add one by hand instead:

1. Download the highest-quality version available (prefer SVG, then PNG) from the org's own
   site, or from Wikimedia Commons if a suitably licensed version exists there.
2. Place it at `docs/assets/org-logos/<org-slug>.<ext>`, where `<org-slug>` matches the org's
   filename under `docs/organisations/` (without `.md`).
3. Add `logo: /assets/org-logos/<org-slug>.<ext>` to the org's frontmatter.
   - A remote URL (e.g. a Wikimedia Commons or the org's own hosted file) is also valid when a
     local copy isn't warranted — see the international-comparator pattern in
     `docs/assets/party-logos/README.md`.
4. For non-free/fair use logos, prefer the org's own official site asset (favicon, brand kit,
   masthead) over a third-party mirror.
5. Add an entry to `docs/assets/org-logos/sources.json` (slug → title/path/license/source/note)
   and re-run the script (or just edit the table above) so it stays in sync.
"""
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


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
            "slug": slug, "title": meta.get("title", slug), "website": website,
            "status": status, "path": path, "logo": meta.get("logo", ""),
        })
    return orgs


def main():
    parser = argparse.ArgumentParser(description="Probe org websites for a logo and populate logo: frontmatter")
    parser.add_argument("--all", action="store_true", help="Include inactive orgs (default: active only)")
    parser.add_argument("--slug", metavar="SLUG", help="Check a single org by slug")
    parser.add_argument("--timeout", type=int, default=10, metavar="N", help="Per-request timeout in seconds (default: 10)")
    parser.add_argument("--write", action="store_true", help="Download + write high-confidence finds to logo: frontmatter (default: report only)")
    parser.add_argument("--include-low", action="store_true", help="Also write low-confidence finds (og:image / generic favicon)")
    parser.add_argument("--force", action="store_true", help="Re-check orgs that already have logo: and overwrite")
    parser.add_argument("--output", metavar="FILE", help="Write JSON results to FILE")
    args = parser.parse_args()

    orgs = load_orgs(slug_filter=args.slug, include_inactive=args.all)
    if not orgs:
        print("No org pages found matching criteria.")
        sys.exit(0)

    os.makedirs(LOGOS_DIR, exist_ok=True)
    sources = load_sources()

    session = requests.Session()
    session.headers.update({"User-Agent": DOD_USER_AGENT})

    results = []
    written = 0
    print(f"\nProbing {len(orgs)} org website(s) for a logo (timeout={args.timeout}s)…\n")

    for i, org in enumerate(orgs, 1):
        slug = org["slug"]
        if not args.force and org["logo"]:
            print(f"  [{i:3d}/{len(orgs)}] SKIP  {slug} (already has logo:)")
            continue

        print(f"  [{i:3d}/{len(orgs)}] {slug} … ", end="", flush=True)
        found = probe_logo(org["website"], slug, timeout=args.timeout, session=session)
        results.append({"slug": slug, **found})

        if "error" in found:
            print(f"nothing found ({found['error']})")
            continue

        tag = "" if found["confidence"] == "high" else " [low-confidence, verify manually]"
        print(f"{found['kind']} → {found['logo_path']} ({found['bytes']} bytes){tag}")

        should_write = args.write and (found["confidence"] == "high" or args.include_low)
        wrote_field = should_write and write_logo_field(org["path"], found["logo_path"], force=args.force)
        if wrote_field:
            written += 1
            sources[slug] = {
                "title": org["title"], "path": os.path.basename(found["dest_path"]),
                "license": "Fair use", "source": found["source_url"],
                "note": f"site asset, auto-detected {found['kind']}",
            }
            print(f"           → wrote logo: {found['logo_path']}")
        elif os.path.exists(found["dest_path"]):
            # Not written (report-only mode, low-confidence without --include-low, or
            # write_logo_field declined e.g. already has logo: without --force) — don't
            # leave the just-downloaded file as an orphan un-referenced by any frontmatter.
            os.remove(found["dest_path"])

    if args.write and written:
        save_sources(sources)
        write_readme(sources)
        print(f"\nUpdated sources.json and README.md for {written} newly-written logo(s)")

    print(f"\n{'=' * 60}")
    print(f"Checked {len(results)} org(s)")
    if args.write:
        print(f"Wrote logo: field for {written} org(s)"
              + ("" if args.include_low else " — only high-confidence finds; pass --include-low to also accept weaker guesses"))
    else:
        print("Report only — pass --write to download and save findings to logo: frontmatter")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
