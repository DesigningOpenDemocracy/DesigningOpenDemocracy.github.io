"""
robots_check.py — shared robots.txt compliance helper

docs/bot.md — DOD's public bot transparency/opt-out page — tells external
site owners that adding a `Disallow: DOD-Bot` entry to their robots.txt
stops our scripts from fetching their pages. This module is what makes
that actually true across every script that fetches org-cited pages, not
just the ones that happened to implement it first.

Before this existed, the same ~10-line robots.txt-parsing function was
independently copy-pasted into scrape_news.py, check_contact.py, and
check_logo.py (check_contact_deep.py reused check_contact.py's copy via
import) — and four more scripts that fetch external pages (check_rss.py,
check_urls.py, check_fragments.py, check_event_urls.py) had no robots.txt
check at all, silently going against what bot.md promised. This module
gives every one of those seven scripts a single shared implementation
instead of a further-forked eighth copy.

Two entry points:

  - robots_allowed(url, user_agent, timeout=5, session=None) — one-shot
    check for a single URL. Fetches and parses that URL's robots.txt fresh
    every call. Fine for scripts that only ever check one or a handful of
    URLs per domain (check_urls.py, check_fragments.py, check_event_urls.py,
    check_contact.py, check_logo.py).

  - load_robots(base_url, timeout=5, session=None) — fetch and parse
    robots.txt ONCE for a domain, returning the RobotFileParser so callers
    can run many can_fetch() checks against it without refetching. Use this
    instead of robots_allowed() when checking many candidate URLs on the
    same site in a loop — check_rss.py probes ~23 candidate feed paths per
    org, and calling robots_allowed() for each would mean 23 redundant
    robots.txt fetches for a file that doesn't change between them.

An unreachable or missing robots.txt is treated as "allow everything" —
the RobotFileParser ends up with no rules, so can_fetch() returns True for
everything. The alternative (block on any fetch error) would silently stop
probing the moment a site's robots.txt has a transient hiccup, which is a
worse failure mode than the rare case of proceeding against a site that
would have disallowed us. A site that actually wants to block DOD-Bot
serves a reachable robots.txt saying so.
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


def load_robots(base_url, timeout=5, session=None):
    """Fetch and parse base_url's robots.txt once. Returns a RobotFileParser
    — call .can_fetch(user_agent, url) on it for each candidate URL on this
    site, without refetching. A parser with no rules (robots.txt missing or
    unreachable) allows everything."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, timeout=timeout)
        rp.parse(resp.text.splitlines())
    except Exception:
        # A RobotFileParser that never had parse() (or read()) called
        # successfully defaults can_fetch() to False, not True — the
        # opposite of "unreachable robots.txt allows everything" this
        # function promises. allow_all is the actual flag can_fetch()
        # checks first; set it explicitly rather than relying on the
        # parser's un-parsed default state.
        rp.allow_all = True
    return rp


def robots_allowed(url, user_agent, timeout=5, session=None):
    """One-shot check: is user_agent allowed to fetch url per its site's
    robots.txt? Fetches robots.txt fresh every call — for checking many
    URLs on the same domain in a loop, use load_robots() once instead and
    call .can_fetch() yourself."""
    rp = load_robots(url, timeout=timeout, session=session)
    return rp.can_fetch(user_agent, url)
