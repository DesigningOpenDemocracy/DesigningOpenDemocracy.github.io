#!/usr/bin/env python3
"""
fetch_shared_link_previews.py — fetch Open Graph / oEmbed metadata for blog
posts' shared_link: url and fill in missing title:/image:/description:.

This is the network-fetching half of the shared_link: feature (see CLAUDE.md's
"Convention — shared_link"): hooks/shared_link_card.py, which renders the
card at build time, is deliberately network-free — per this repo's
fetch-then-cache convention, anything that hits the network is a separate
util/ script run manually or by the weekly heartbeat cron, and only its
*results* (frontmatter fields, here) are read at build time.

Two different trust levels for what gets found, matching check_contact.py's
tiered approach:

  - title: / image: are freely overwritable display metadata — wrong or
    stale, worst case is a slightly off thumbnail/heading on the card.
    Written with --write whenever missing, or always with --force.

  - description: is NOT freely written even with --write. It's the one
    shared_link: field util/check_fragments.py mechanically re-verifies
    forever after (must appear verbatim in the URL's rendered body text —
    see that script's docstring). An <meta property="og:description">
    tag has no guarantee of matching the *visible* page text (meta tags
    aren't rendered), so writing whatever a site's og:description happens
    to say would often just hand check_fragments.py's next run an
    immediate, guaranteed MISMATCH — worse than leaving description:
    unset, since it reads as sourced text a reader could trust. This
    script only ever writes description: when (a) --write-description is
    passed AND (b) the fetched text is independently confirmed to appear
    verbatim in the same page's body text (description_verifies()) — the
    exact check check_fragments.py itself will run on it. --force
    overrides that confirmation and writes it anyway, for a human who's
    looked at the mismatch and decided to record it pending a manual fix.

Frontmatter is rewritten via a full python-frontmatter round-trip rather
than raw-text splicing. Unlike org pages (util/reorder_frontmatter.py),
blog posts have no canonical field order to preserve, so there's nothing
splicing buys here that's worth its bug surface — check_rss.py's,
scrape_news.py's, and review_orgs.py's hand-rolled line-splice writers all
turned out to have duplicate-key or silent-drop bugs from exactly that
kind of state machine (see 2026-08 CI incident / tests/test_frontmatter_
writers.py). A full round-trip reformats the rest of the post's
frontmatter — acceptable for a --write-gated, review-before-merge script,
same tradeoff check_fragments.py's own YAML fallback already accepts.

A URL that comes back 403/429 is recorded as BLOCKED and skipped entirely
— no request at all — on every subsequent run of this script (or of
check_fragments.py / check_event_urls.py — all three share the same cache
file and "blocked"/"blocked_since" fields) until --no-cache forces a
recheck. Retrying a site that's already told us no, every run, is wasted
traffic that produces no new information.

Usage:
    python util/fetch_shared_link_previews.py                       # report only, all posts with shared_link: url
    python util/fetch_shared_link_previews.py --post 2026-08-16-habermas-machine-ai-mediation
    python util/fetch_shared_link_previews.py --write                # write missing title:/image:
    python util/fetch_shared_link_previews.py --write --write-description  # also attempt description: (only when it verifies)
    python util/fetch_shared_link_previews.py --write --force         # overwrite existing title:/image: too
    python util/fetch_shared_link_previews.py --no-cache              # recheck URLs already confirmed BLOCKED
    python util/fetch_shared_link_previews.py --timeout 15

Requirements: python-frontmatter, requests (util/requirements.txt)
"""

import argparse
import glob
import html
import os
import sys
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

sys.path.insert(0, os.path.dirname(__file__))

try:
    import frontmatter
    import requests
except ImportError as e:
    print(f"Missing dependency: {e.name} — pip install python-frontmatter requests")
    sys.exit(1)

import check_fragments as cf  # noqa: E402 — reuses _fetch_page_text for description verification
from text_fragment import count_occurrences  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
POSTS_DIR = os.path.join(DOCS_DIR, "blog", "posts")
USER_AGENT = "DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)"

# YouTube's watch page reliably redirects a scripted fetch to a Google
# bot-check interstitial (302 -> google.com/sorry, confirmed 2026-08-23) —
# the generic oEmbed-discovery-via-page-HTML path below never finds
# anything for this host, silently returning a blank "- YouTube" title/no
# image rather than an error. YouTube's oEmbed REST endpoint itself isn't
# blocked, so these hosts are fetched directly (fetch_youtube_oembed())
# instead — same "use the API, not scraped page HTML" principle CLAUDE.md
# documents for Wikipedia.
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _youtube_watch_url(url):
    """Normalise a youtu.be short link to the youtube.com/watch?v= form
    YouTube's oEmbed endpoint expects in its url= param."""
    parsed = urlparse(url)
    if parsed.netloc.lower() == "youtu.be":
        return f"https://www.youtube.com/watch?v={parsed.path.lstrip('/')}"
    return url


def fetch_youtube_oembed(url, timeout=10, session=None):
    """Fetch title/thumbnail_url directly from YouTube's oEmbed endpoint.
    No description field exists in an oEmbed response — same limitation
    fetch_preview() already documents for the generic oEmbed-bonus path."""
    session = session or requests
    oembed_url = f"https://www.youtube.com/oembed?url={quote(_youtube_watch_url(url), safe='')}&format=json"

    if not robots_allowed(oembed_url, timeout=timeout, session=session):
        return {"error": "ROBOTS_DISALLOWED"}

    try:
        r = session.get(oembed_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        return {"error": f"HTTP_{status}" if status else "NETWORK_ERROR"}
    except requests.RequestException:
        return {"error": "NETWORK_ERROR"}
    except ValueError:
        return {"error": "PARSE_ERROR"}

    result = {}
    if data.get("title"):
        result["title"] = data["title"]
    if data.get("thumbnail_url"):
        result["image"] = data["thumbnail_url"]
    return result


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
    return rp.can_fetch(USER_AGENT, url)


class _MetaExtractor(HTMLParser):
    """Pulls og:*/name=description meta tags, <title>, and an oEmbed
    discovery link out of raw HTML. Stdlib html.parser, not a full DOM
    parser dependency — sufficient for scanning <head> meta/link/title
    tags, matching scrape_news.py's _NewsParser precedent."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og = {}
        self.meta_description = None
        self.oembed_url = None
        self.title = None
        self._in_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            prop = attrs.get("property", "")
            name = attrs.get("name", "")
            content = attrs.get("content")
            if prop.startswith("og:") and content:
                self.og[prop[3:]] = content
            elif name == "description" and content and self.meta_description is None:
                self.meta_description = content
        elif tag == "link" and attrs.get("type") == "application/json+oembed":
            self.oembed_url = attrs.get("href")
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)

    def finalize(self):
        if self._title_parts and self.title is None:
            self.title = "".join(self._title_parts).strip()


def fetch_preview(url, timeout=10, session=None):
    """Fetch `url` and return a dict with whatever of title/description/
    image could be found, or {'error': ...} on failure. Prefers Open
    Graph tags; falls back to <title>/meta name="description". When the
    page advertises an oEmbed endpoint, its title/thumbnail_url take
    priority over og:title/og:image (video platforms like YouTube publish
    a proper oEmbed response with a cleaner thumbnail than og:image often
    gives; oEmbed has no description field, so that's OG-only). YouTube
    hosts skip straight to fetch_youtube_oembed() — see that function's
    docstring for why the generic page-scrape path never works there."""
    session = session or requests

    if urlparse(url).netloc.lower() in _YOUTUBE_HOSTS:
        return fetch_youtube_oembed(url, timeout=timeout, session=session)

    if not robots_allowed(url, timeout=timeout, session=session):
        return {"error": "ROBOTS_DISALLOWED"}

    try:
        r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        # "HTTP_403"/"HTTP_429" format matches check_fragments.py's own
        # error strings (cf.BLOCKED_ERRORS) — this script shares that
        # module's cache/"blocked" field, so the format has to line up.
        return {"error": f"HTTP_{status}" if status else "NETWORK_ERROR"}
    except requests.RequestException:
        return {"error": "NETWORK_ERROR"}

    parser = _MetaExtractor()
    try:
        parser.feed(r.text)
    except Exception:
        return {"error": "PARSE_ERROR"}
    parser.finalize()

    result = {}
    title = parser.og.get("title") or parser.title
    if title:
        result["title"] = html.unescape(title).strip()
    description = parser.og.get("description") or parser.meta_description
    if description:
        result["description"] = html.unescape(description).strip()
    image = parser.og.get("image")
    if image:
        result["image"] = urljoin(url, image)

    if parser.oembed_url:
        try:
            oembed_url = urljoin(url, parser.oembed_url)
            r2 = session.get(oembed_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            r2.raise_for_status()
            data = r2.json()
            if data.get("title"):
                result["title"] = data["title"]
            if data.get("thumbnail_url"):
                result["image"] = data["thumbnail_url"]
        except Exception:
            pass  # oEmbed is a bonus, not required — OG fields above still stand

    return result


def fetch_preview_cached(url, timeout, session, cache, use_cache=True):
    """Wraps fetch_preview() with the same shared "blocked" cache
    check_fragments.py/check_event_urls.py use (docs/data/event-evidence-
    cache.json). A URL already confirmed BLOCKED is skipped entirely —
    no request at all — until use_cache=False forces a recheck. Returns
    (found_dict, skipped), where skipped=True means this was answered
    from cache without any network call."""
    entry = cache.get(url, {}) if use_cache else {}
    if entry.get("blocked"):
        return {"error": entry["blocked"]}, True

    found = fetch_preview(url, timeout=timeout, session=session)

    if found.get("error") in cf.BLOCKED_ERRORS:
        prior = cache.get(url, {})
        cache[url] = {**prior, "blocked": found["error"],
                      "blocked_since": prior.get("blocked_since", cf.date.today().isoformat())}
    elif "error" not in found and url in cache:
        cache[url] = {k: v for k, v in cache[url].items()
                      if k not in ("blocked", "blocked_since")}
        if not cache[url]:
            del cache[url]

    return found, False


def description_verifies(url, description, timeout=15):
    """True if `description` appears verbatim (whitespace-normalised) in
    url's rendered body text — the exact check util/check_fragments.py's
    mechanical verifier runs on shared_link.description: forever after.
    Checked here BEFORE ever auto-writing it: writing a value we already
    know would fail that check defeats the point of the field being
    mechanically verified at all."""
    text, _resp, error = cf._fetch_page_text(url, {"User-Agent": USER_AGENT})
    if error or text is None:
        return False
    return count_occurrences(text, description) > 0


def write_shared_link_preview(path, found, force=False, write_description=False):
    """Fill in missing shared_link: fields from `found`. Never overwrites
    an existing value unless force=True. description: is only ever
    considered when write_description=True (caller has already decided —
    see description_verifies() and --force in main()).

    Returns True if the file was changed."""
    post = frontmatter.load(path)
    link = post.metadata.get("shared_link")
    if not isinstance(link, dict) or not link.get("url"):
        return False

    changed = False
    if found.get("title") and (force or not link.get("title")):
        link["title"] = found["title"]
        changed = True
    if found.get("image") and (force or not link.get("image")):
        link["image"] = found["image"]
        changed = True
    if write_description and found.get("description") and (force or not link.get("description")):
        link["description"] = found["description"]
        changed = True

    if not changed:
        return False

    post.metadata["shared_link"] = link
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
    return True


def load_posts(post_filter=None):
    posts = []
    for path in sorted(glob.glob(os.path.join(POSTS_DIR, "*.md"))):
        post = frontmatter.load(path)
        link = post.metadata.get("shared_link")
        if not isinstance(link, dict) or not link.get("url"):
            continue
        slug = os.path.basename(path)[:-3]
        if post_filter and slug not in post_filter:
            continue
        posts.append({"path": path, "slug": slug, "link": link})
    return posts


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Open Graph / oEmbed previews for blog posts' shared_link: url")
    parser.add_argument("--post", action="append",
                        help="Only check one post by filename slug (repeatable)")
    parser.add_argument("--write", action="store_true",
                        help="Write findings to frontmatter (default: report only)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing title:/image: values, and (with "
                             "--write-description) write description: even when it "
                             "doesn't verify against the live page body text")
    parser.add_argument("--write-description", action="store_true",
                        help="Also attempt description:, but only when it's confirmed to "
                             "appear verbatim in the page body text (the same check "
                             "util/check_fragments.py runs on it forever after). Off by "
                             "default even with --write.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Recheck URLs already confirmed BLOCKED on a prior run instead "
                             "of skipping them")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    posts = load_posts(args.post)
    if not posts:
        scope = f" matching --post {args.post}" if args.post else ""
        print(f"No blog posts with shared_link: url found{scope}.")
        return 0

    session = requests.Session()
    cache = cf.load_evidence()
    written = 0
    for i, post in enumerate(posts, 1):
        slug = post["slug"]
        url = post["link"]["url"]
        print(f"  [{i:3d}/{len(posts)}] {slug} … ", end="", flush=True)

        found, skipped = fetch_preview_cached(
            url, timeout=args.timeout, session=session, cache=cache, use_cache=not args.no_cache)
        if "error" in found:
            if skipped:
                since = cache.get(url, {}).get("blocked_since", "?")
                print(f"STILL BLOCKED (confirmed since {since} — skipped, "
                      f"pass --no-cache to recheck)")
            else:
                print(found["error"])
            continue

        got = [k for k in ("title", "description", "image") if found.get(k)]
        print("found: " + (", ".join(got) if got else "nothing"))

        write_description = False
        if args.write_description and found.get("description"):
            if description_verifies(url, found["description"], timeout=args.timeout):
                write_description = True
            elif args.force:
                write_description = True
                print("               description doesn't verify against page body text "
                      "— writing anyway (--force)")
            else:
                print("               description found but doesn't verify against page "
                      "body text — not writing (pass --force to write anyway)")

        if args.write:
            if write_shared_link_preview(post["path"], found, force=args.force,
                                          write_description=write_description):
                written += 1
                print("               written")

    cf.save_evidence(cache)

    print()
    if args.write:
        print(f"{len(posts)} post(s) checked, {written} updated")
    else:
        print(f"{len(posts)} post(s) checked (dry run — pass --write to persist)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
