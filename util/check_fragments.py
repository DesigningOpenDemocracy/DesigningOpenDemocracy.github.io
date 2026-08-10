#!/usr/bin/env python3
"""Verify all #:~:text= fragments against live Wikipedia extracts."""
import glob, os, sys, json, re, time
from urllib.parse import urlparse, unquote
from urllib.request import urlopen, Request

try:
    import frontmatter
except ImportError:
    print("Missing: pip install python-frontmatter"); sys.exit(1)

ORG_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")

def fetch_wp_extract(title):
    time.sleep(0.3)  # rate limit
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={title}&format=json"
    try:
        req = Request(url, headers={"User-Agent": "DOD-lint/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            pages = data.get("query", {}).get("pages", {})
            return next(iter(pages.values())).get("extract", "")
    except Exception as e:
        return None

def extract_fragment(url):
    parsed = urlparse(url)
    if parsed.fragment and parsed.fragment.startswith(":~:text="):
        return unquote(parsed.fragment[len(":~:text="):])
    return None

bad = []
good = 0
total = 0

for path in sorted(glob.glob(os.path.join(ORG_DIR, "*.md"))):
    slug = os.path.basename(path)[:-3]
    if slug in ("organisations", "concepts"):
        continue
    post = frontmatter.load(path)
    for e in post.metadata.get("events") or []:
        url = e.get("url", "")
        frag = extract_fragment(url)
        if not frag:
            continue
        total += 1
        parsed = urlparse(url)
        # Extract Wikipedia page title from URL
        m = re.search(r'/wiki/([^#]+)', parsed.path)
        if not m:
            continue
        title = unquote(m.group(1))
        extract = fetch_wp_extract(title)
        if extract is None:
            print(f"  ERROR fetching {title}")
            continue
        if frag in extract:
            good += 1
        else:
            bad.append((slug, e.get("date", "?"), e.get("title", "")[:60], frag, title))
            print(f"  MISMATCH  {slug}  [{e.get('date', '?')}]  {e.get('title', '')[:50]}")
            print(f"            fragment: {frag[:80]}")

print(f"\nVerified: {good} good, {len(bad)} mismatch (of {total} total fragments)")
sys.exit(1 if bad else 0)
