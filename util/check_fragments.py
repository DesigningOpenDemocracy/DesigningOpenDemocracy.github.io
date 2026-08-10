#!/usr/bin/env python3
"""
Verify event sourcing evidence against live pages.

Checks:
  - #:~:text= URL fragments against Wikipedia extracts (API, substring match)
  - quote: fields against source pages (fetch, substring match)

Skips events with proof_warning (explicitly unverified).
Whitespace is normalised before comparison to handle line breaks and formatting.

Usage:
    python util/check_fragments.py        # verify all events
    python util/check_fragments.py --slug mosaiclab  # single org

Requirements: python-frontmatter (util/requirements.txt)
"""

import glob, os, sys, json, re, time
from urllib.parse import urlparse, unquote
from urllib.request import urlopen, Request, HTTPError, URLError

try:
    import frontmatter
except ImportError:
    print("Missing: pip install python-frontmatter"); sys.exit(1)

ORG_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")
USER_AGENT = "DOD-fragments/1.0"
FETCH_DELAY = 0.5  # seconds between requests


def fetch_wp_extract(title):
    """Fetch Wikipedia article text via the API."""
    time.sleep(FETCH_DELAY)
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={title}&format=json"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            pages = data.get("query", {}).get("pages", {})
            return next(iter(pages.values())).get("extract", "")
    except Exception:
        return None


def fetch_page(url):
    """Fetch a non-Wikipedia page and return its text content (stripped of tags)."""
    time.sleep(FETCH_DELAY)
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text)
            return text[:100000]
    except HTTPError as e:
        return f"HTTP_{e.code}"
    except URLError:
        return "NETWORK_ERROR"
    except Exception:
        return "FETCH_ERROR"


def normalize_ws(text):
    """Collapse whitespace for forgiving substring matching."""
    return " ".join(text.split())


def text_contains(text, needle):
    """Check if needle appears in text, with whitespace normalization."""
    if not text or not needle:
        return False
    return normalize_ws(needle) in normalize_ws(text)


def extract_fragment(url):
    parsed = urlparse(url)
    if parsed.fragment and parsed.fragment.startswith(":~:text="):
        return unquote(parsed.fragment[len(":~:text="):])
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify event evidence against live pages")
    parser.add_argument("--slug", type=str, help="Check a single org")
    args = parser.parse_args()

    fragments_good = 0
    fragments_bad = 0
    fragments_err = 0
    quotes_good = 0
    quotes_bad = 0
    skipped = 0

    for path in sorted(glob.glob(os.path.join(ORG_DIR, "*.md"))):
        slug = os.path.basename(path)[:-3]
        if slug in ("organisations", "concepts"):
            continue
        if args.slug and slug != args.slug:
            continue

        post = frontmatter.load(path)
        for e in post.metadata.get("events") or []:
            title = e.get("title", "")[:50]
            date = e.get("date", "?")
            url = e.get("url", "")

            if "proof_warning" in e:
                skipped += 1
                continue

            # --- Check #:~:text= fragments ---
            frag = extract_fragment(url)
            if frag:
                parsed = urlparse(url)
                m = re.search(r"/wiki/([^#]+)", parsed.path)
                if not m:
                    continue
                wp_title = unquote(m.group(1))
                extract = fetch_wp_extract(wp_title)
                if extract is None:
                    fragments_err += 1
                    print(f"  FRAGMENT ERROR  {slug}  [{date}]  {title}")
                    print(f"                   {wp_title} (API error — rate-limited?)")
                elif text_contains(extract, frag):
                    fragments_good += 1
                else:
                    fragments_bad += 1
                    print(f"  FRAGMENT MISMATCH {slug}  [{date}]  {title}")
                    print(f"                    fragment: {frag[:80]}")

            # --- Check quote: fields ---
            if "quote" in e:
                quote = e["quote"]
                parsed = urlparse(url)
                is_wp = "wikipedia.org" in parsed.netloc
                if is_wp:
                    m = re.search(r"/wiki/([^#]+)", parsed.path)
                    text = fetch_wp_extract(unquote(m.group(1))) if m else None
                else:
                    text = fetch_page(url)

                if text is None:
                    quotes_bad += 1
                    print(f"  QUOTE FETCH ERR {slug}  [{date}]  {title}")
                elif not isinstance(text, str) or text.startswith(("HTTP_", "NETWORK", "FETCH")):
                    quotes_bad += 1
                    print(f"  QUOTE FETCH ERR {slug}  [{date}]  {title}  ({text})")
                elif text_contains(text, quote):
                    quotes_good += 1
                else:
                    quotes_bad += 1
                    print(f"  QUOTE MISMATCH  {slug}  [{date}]  {title}")
                    print(f"                   quote: {quote[:80]}")

    print()
    print(f"Fragments: {fragments_good} good, {fragments_bad} mismatch, {fragments_err} API errors")
    print(f"Quotes:    {quotes_good} good, {quotes_bad} bad")
    print(f"Skipped (proof_warning): {skipped}")

    if fragments_bad or quotes_bad:
        print(f"\n{fragments_bad + quotes_bad} verifiable source(s) no longer match live pages.")
        print("API errors (rate-limiting) are NOT counted as mismatches.")
        sys.exit(1)
    else:
        print("All verifiable evidence matches live pages.")
        if fragments_err:
            print(f"({fragments_err} fragment API errors — re-run later when not rate-limited)")
        sys.exit(0)


if __name__ == "__main__":
    main()
