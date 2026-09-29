#!/usr/bin/env python3
"""
news_checkup.py — list what the landscape's orgs have published since the
last review, so an editor can pick out the few posts that are news.

Landscape News (docs/news.md, hooks/news_export.py) is built only from org
`events:` entries carrying a `notable:` tier. That's deliberate: an org's
own feed is every post it publishes (job ads, newsletters, event reminders,
routine commentary), and no feed carries a signal for which of those
matter. Aggregating feeds into News would flood it. So feeds are an intake
channel, not a source: this script turns them into a short worklist, and a
person (or the heartbeat run, see HEARTBEAT.md) moves anything that clears
the `notable:` bar into the org's `events:` by hand, with a `quote:` or
`note:` taken from the post itself.

Offline. It makes no network requests: the weekly probe
(check_rss.py --update-activity, in .github/workflows/heartbeat-probes.yml)
already downloads every feed, and saves each org's recent posts to
docs/data/feeds/<slug>.json while it's at it (dates, titles and links
only). Reading that cache means a checkup never fetches a feed a second
time, and works in a session with no network.

What it lists, per org, is every saved post published on or after that
org's last review, minus anything already cited as an event `url:` or
`coverage_url:` on any org page (a post recorded on a co-host's page counts
too). Orgs with a `news_page:` but no feed get a line from the last
scrape_news.py run instead; only that page's newest post is known.

--mark-reviewed records each org as reviewed through the date its feed was
last read (activity.rss.checked; activity.scrape.checked for news pages),
in docs/data/news-checkup-state.json. Deliberately not today's date: a post
published after the probe read the feed isn't in the cache yet, and marking
through today would hide it for good once the next probe saved it. Posts
dated on the read day itself come up once more on the next checkup, which
is the safe direction to be wrong in.

Usage:
    python util/news_checkup.py                      # everything since each org's last review
    python util/news_checkup.py --slug decidim        # one org (repeatable)
    python util/news_checkup.py --days 60             # window for orgs never reviewed (default 30)
    python util/news_checkup.py --since 2026-09-01    # ignore review state, list from this date
    python util/news_checkup.py --out worklist.md     # write the worklist to a file
    python util/news_checkup.py --mark-reviewed       # after reviewing: record it, then commit the state file
"""

import argparse
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backoff  # noqa: E402
import news_signals  # noqa: E402

try:
    import frontmatter
except ImportError:
    print("Missing dependency: pip install python-frontmatter")
    sys.exit(1)

UTIL_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(UTIL_DIR, "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
FEEDS_DIR = os.path.join(DOCS_DIR, "data", "feeds")
STATE_FILE = os.path.join(DOCS_DIR, "data", "news-checkup-state.json")
SKIP_FILES = {"index.md"}

# How far back to look for an org nobody has reviewed yet. A month is enough
# to catch what's current without the first checkup being a wall of posts.
DEFAULT_DAYS = 30

# A feed the probe hasn't read for this long is flagged: its cache is going
# stale, so "no new posts" may just mean "not read lately". Feeds are read
# monthly (see check_rss.py's FEED_RECHECK_DAYS), so this is a month plus two
# weekly runs of slack. Dormant feeds, read quarterly, aren't flagged.
STALE_READ_DAYS = 45

# A worth-a-look label on more than half of a feed's saved posts is that org's
# usual output, not something that singles one post out: nearly every
# Afrobarometer post is a survey "report". Such a label stays on the post's
# line but doesn't earn it a place in "Start here". Judged over everything
# saved for the feed (up to 180 days), which needs this many posts to mean
# anything.
USUAL_MIN_POSTS = 5

# A feed whose newest post is older than this is listed as dormant, which is
# worth a look at the org's status: it may have moved its posts elsewhere,
# or stopped.
DORMANT_DAYS = 180


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def norm_url(url):
    """Compare URLs loosely enough that the same post matches however it was
    pasted: scheme, a leading www., a trailing slash, the fragment and utm_
    tracking parameters are all ignored."""
    if not url:
        return ""
    parts = urlsplit(str(url).strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = "&".join(p for p in parts.query.split("&")
                     if p and not p.lower().startswith("utm_"))
    return host + parts.path.rstrip("/") + (f"?{query}" if query else "")


def load_orgs(orgs_dir=ORGS_DIR):
    """(active orgs, recorded event URLs across every org page)."""
    orgs, recorded = [], set()
    for path in sorted(glob.glob(os.path.join(orgs_dir, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        slug = os.path.basename(path)[:-3]
        m = frontmatter.load(path).metadata
        for e in m.get("events") or []:
            if isinstance(e, dict):
                for key in ("url", "coverage_url"):
                    if e.get(key):
                        recorded.add(norm_url(e[key]))
        if m.get("status") != "active":
            continue
        activity = m.get("activity") or {}
        orgs.append({
            "slug": slug,
            "title": str(m.get("title") or slug),
            "rss_feed": m.get("rss_feed") or "",
            "news_page": m.get("news_page") or "",
            "rss_read": parse_date((activity.get("rss") or {}).get("checked")),
            "scrape": activity.get("scrape") or {},
        })
    return orgs, recorded


def load_feed_items(slug, feeds_dir=FEEDS_DIR):
    """What the probe has saved about one org's feed (see check_rss.py's
    save_feed_items), or None if there's nothing yet. `read` is whether any
    read has ever succeeded; `failing` is the backoff record while reads are
    failing."""
    path = os.path.join(feeds_dir, f"{slug}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {"latest": data.get("latest"), "items": data.get("items") or [],
            "failing": data.get("failing"), "read": "latest" in data}


def load_state(path=STATE_FILE):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state, path=STATE_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def since_for(slug, state, default_since, override=None):
    if override:
        return override
    return parse_date((state.get(slug) or {}).get("reviewed")) or default_since


def checkup(orgs, recorded, state, today, load_items=load_feed_items,
            default_days=DEFAULT_DAYS, since_override=None):
    """Build the worklist. Pure apart from load_items, so tests can feed it
    fixtures. Orgs that share a feed (a national chapter republishing its
    parent's posts) are one section, not the same posts listed twice."""
    default_since = today - timedelta(days=default_days)
    groups = {}
    for org in orgs:
        if org["rss_feed"]:
            groups.setdefault(org["rss_feed"], []).append(org)

    report = {"today": today, "feeds": [], "quiet": [], "empty": [], "failing": [],
              "uncollected": [], "pages": [], "recorded": 0, "uncovered": 0}

    for feed, members in groups.items():
        since = min(since_for(o["slug"], state, default_since, since_override) for o in members)
        caches = [c for c in (load_items(o["slug"]) for o in members) if c is not None]
        failing = next((c["failing"] for c in caches if c.get("failing")), None)
        if failing:
            # Posts saved from earlier reads are still gone through below, so
            # a feed that breaks doesn't take its unreviewed posts with it.
            report["failing"].append({"orgs": members, "feed": feed, "failing": failing})
        elif not any(c.get("read", True) for c in caches):
            report["uncollected"].append({"orgs": members, "feed": feed})
            continue
        items = {}
        for cache in caches:
            for item in cache["items"]:
                items.setdefault(item.get("url") or f"{item.get('date')}|{item.get('title')}", item)
        latest = max((d for d in (parse_date(c.get("latest")) for c in caches) if d), default=None)
        if latest is None and not failing:
            # Listed nothing on its last read.
            report["empty"].append({"orgs": members, "feed": feed})
        new, recorded_here = [], 0
        for item in items.values():
            d = parse_date(item.get("date"))
            if not d or d < since:
                continue
            if item.get("url") and norm_url(item["url"]) in recorded:
                recorded_here += 1
                continue
            new.append({**item, "date": d})
        new.sort(key=lambda i: (i["date"], i.get("title") or ""), reverse=True)
        report["recorded"] += recorded_here
        reads = [o["rss_read"] for o in members if o["rss_read"]]
        read = max(reads) if reads else None
        section = {"orgs": members, "feed": feed, "since": since, "read": read,
                   "latest": latest,
                   "stale": read is None or (today - read).days >= STALE_READ_DAYS,
                   "usual": usual_labels(list(items.values())),
                   "items": new}
        if new:
            report["feeds"].append(section)
        elif latest is not None and not failing:
            report["quiet"].append(section)

    for org in orgs:
        if org["rss_feed"]:
            continue
        if not org["news_page"]:
            report["uncovered"] += 1
            continue
        scrape = org["scrape"]
        d = parse_date(scrape.get("date"))
        since = since_for(org["slug"], state, default_since, since_override)
        if d and d >= since and not (scrape.get("url") and norm_url(scrape["url"]) in recorded):
            report["pages"].append({
                "org": org, "date": d, "since": since,
                "note": scrape.get("note") or "",
                "url": scrape.get("url") or org["news_page"],
                "read": parse_date(scrape.get("checked")),
            })

    report["feeds"].sort(key=lambda s: (-s["items"][0]["date"].toordinal(), s["orgs"][0]["title"].lower()))
    report["pages"].sort(key=lambda p: (-p["date"].toordinal(), p["org"]["title"].lower()))
    return report


def mark_reviewed(state, report):
    """Record every org in the report as reviewed through the date its feed
    or news page was last read. Never moves a date backwards, and skips any
    org whose source has never been read (there's nothing to have reviewed)."""
    marked = 0

    def advance(slug, through):
        nonlocal marked
        if not through:
            return
        current = parse_date((state.get(slug) or {}).get("reviewed"))
        if current is None or through > current:
            state[slug] = {"reviewed": through.isoformat()}
            marked += 1

    for section in report["feeds"] + report["quiet"]:
        for org in section["orgs"]:
            advance(org["slug"], section["read"])
    for page in report["pages"]:
        advance(page["org"]["slug"], page["read"] or page["date"])
    return marked


def triage(item):
    """(worth_a_look, likely_routine, mentions) for one saved post: the labels
    check_rss.py stored when it read the post (from its title, opening lines
    and full text), plus title-only labels recomputed now, which covers posts
    saved before signals existed and picks up keyword changes without a
    re-read. See util/news_signals.py."""
    worth, routine = news_signals.signals(item.get("title"))
    return (sorted(set(worth) | set(item.get("signals") or [])),
            sorted(set(routine) | set(item.get("routine") or [])),
            sorted(item.get("mentions") or []))


def usual_labels(items):
    """Worth-a-look labels on more than half of a feed's saved posts (see
    USUAL_MIN_POSTS)."""
    if len(items) < USUAL_MIN_POSTS:
        return set()
    counts = {}
    for item in items:
        for label in triage(item)[0]:
            counts[label] = counts.get(label, 0) + 1
    return {label for label, n in counts.items() if n * 2 > len(items)}


def start_here(report):
    """Posts with a worth-a-look signal (other than the feed's usual output)
    or a mention of another Landscape org, and no routine signal, most
    signals first, then newest. A pointer into the per-org lists, which
    still show every post."""
    picks = []
    for s in report["feeds"]:
        usual = s.get("usual") or set()
        for item in s["items"]:
            worth, routine, named = triage(item)
            worth = [w for w in worth if w not in usual]
            if (worth or named) and not routine:
                picks.append((s, item, worth, named))
    picks.sort(key=lambda p: (-(len(p[2]) + len(p[3])), -p[1]["date"].toordinal(),
                              p[0]["orgs"][0]["title"].lower()))
    return picks


def _tags(worth, routine, named):
    parts = []
    if worth:
        parts.append(", ".join(worth))
    if named:
        parts.append("mentions " + ", ".join(named))
    if routine:
        parts.append("likely routine: " + ", ".join(routine))
    return (" · " + " · ".join(parts)) if parts else ""


def _md_text(text):
    return " ".join(str(text or "").split()).replace("[", "\\[").replace("]", "\\]")


def _org_names(orgs):
    return " / ".join(o["title"] for o in orgs)


def render_markdown(report):
    today = report["today"]
    n_items = sum(len(s["items"]) for s in report["feeds"])
    picks = start_here(report)
    n_routine = sum(1 for s in report["feeds"] for i in s["items"] if triage(i)[1])
    out = [
        f"# Landscape news checkup — {today.isoformat()}",
        "",
        "Posts the orgs have published since each was last reviewed, from the feeds "
        "the weekly probe reads. **Most of these are routine and should stay where they "
        "are.** Move a post to Landscape News only if it clears the `notable:` bar "
        "(see CLAUDE.md): add it to that org's `events:` with a tier, a `notable_reason:`, "
        "and a `quote:` or `note:` taken from the post itself. A feed title is a lead, "
        "not a source. Then run `python util/news_checkup.py --mark-reviewed` and commit "
        "`docs/data/news-checkup-state.json`.",
        "",
        f"**{n_items} new post{'s' if n_items != 1 else ''} from {len(report['feeds'])} "
        f"feed{'s' if len(report['feeds']) != 1 else ''}** · "
        f"{len(report['pages'])} news page{'s' if len(report['pages']) != 1 else ''} with a newer post · "
        f"{report['recorded']} already in `events:` (hidden) · "
        f"{len(report['quiet'])} quiet",
        "",
    ]

    if picks:
        out += ["## Start here", "",
                f"{len(picks)} of the {n_items} posts {'carries' if len(picks) == 1 else 'carry'} "
                "a worth-a-look signal (beyond their feed's usual output) or name another "
                f"Landscape org; {n_routine} {'looks' if n_routine == 1 else 'look'} routine. "
                "Signals are keyword matches on each "
                "post's title and opening lines (see `util/news_signals.py`), a hint for where to "
                "start rather than a verdict: a post with none can still be News, and posts in "
                "languages the keyword lists don't cover mostly get none. Every post is still "
                "listed under its org below.", ""]
        for s, item, worth, named in picks:
            title = _md_text(item.get("title")) or "(untitled)"
            line = f"[{title}]({item['url']})" if item.get("url") else title
            out.append(f"- {item['date'].isoformat()} · **{_md_text(_org_names(s['orgs']))}** · "
                       f"{line}{_tags(worth, [], named)}")
        out.append("")

    for s in report["feeds"]:
        pages = ", ".join(f"`docs/organisations/{o['slug']}.md`" for o in s["orgs"])
        read = s["read"].isoformat() if s["read"] else "never"
        warn = f" · ⚠ feed not read for {(today - s['read']).days} days" if s["stale"] and s["read"] else ""
        out += [f"## {_md_text(_org_names(s['orgs']))} — {len(s['items'])} since {s['since'].isoformat()}",
                "", f"{pages} · feed read {read}{warn}", ""]
        if s.get("usual"):
            out += [f"Most of this feed's posts are tagged {', '.join(sorted(s['usual']))}: that's "
                    "its usual output, so the tag alone doesn't put a post in Start here.", ""]
        for item in s["items"]:
            title = _md_text(item.get("title")) or "(untitled)"
            line = f"[{title}]({item['url']})" if item.get("url") else title
            out.append(f"- {item['date'].isoformat()} — {line}{_tags(*triage(item))}")
        out.append("")

    if report["pages"]:
        out += ["## News pages without a feed", "",
                "Only the newest post on each page is known (from the last `scrape_news.py` "
                "run), so open the page to see what else is new.", ""]
        for p in report["pages"]:
            note = f" — {_md_text(p['note'])}" if p["note"] else ""
            out.append(f"- {p['date'].isoformat()} — **{_md_text(p['org']['title'])}**{note} "
                       f"([page]({p['url']}) · `{p['org']['slug']}`)")
        out.append("")

    if report["quiet"]:
        dormant = [s for s in report["quiet"] if (today - s["latest"]).days > DORMANT_DAYS]
        active = [s for s in report["quiet"] if s not in dormant]
        stale = [s for s in active if s["stale"]]
        out += ["## Quiet", ""]
        if active:
            out += ["No new posts: " + ", ".join(
                f"`{o['slug']}`" for s in active for o in s["orgs"]) + ".", ""]
        if dormant:
            out += [f"Nothing posted in {DORMANT_DAYS}+ days, worth a look at the org's `status:` "
                    "or whether it posts somewhere else now: " + ", ".join(
                        f"`{o['slug']}` ({s['latest'].isoformat()})"
                        for s in sorted(dormant, key=lambda s: s["latest"]) for o in s["orgs"]) + ".", ""]
        if stale:
            out += ["Not read by the probe for "
                    f"{STALE_READ_DAYS}+ days, so quiet may only mean unread: " + ", ".join(
                        f"`{o['slug']}`" for s in stale for o in s["orgs"]) + ".", ""]

    if report["empty"]:
        out += ["## Feeds with no posts", "",
                "The feed answered but listed no dated posts on its last read (an empty or "
                "malformed feed, or the site moved its posts elsewhere), so check the "
                "`rss_feed:` URL is still the right one: " + ", ".join(
                    f"`{o['slug']}`" for s in report["empty"] for o in s["orgs"]) + ".", ""]

    if report["failing"]:
        out += ["## Failing feeds", "",
                "The probe couldn't read these. Each is retried on a widening interval "
                "(7, 14, 28, 56, then every 90 days) rather than every week, and a success "
                "clears it. One that keeps failing probably means the `rss_feed:` URL needs "
                "updating or removing.", ""]
        for s in sorted(report["failing"], key=lambda s: str(s["failing"].get("since"))):
            f = s["failing"]
            out.append(f"- `{'`, `'.join(o['slug'] for o in s['orgs'])}` — {f.get('error')} since "
                       f"{f.get('since')}, {f.get('count')} failed read(s), next try "
                       f"{backoff.next_try(f)} ({s['feed']})")
        out.append("")

    if report["uncollected"]:
        out += ["## Not collected yet", "",
                "`rss_feed:` is set but the probe hasn't read the feed yet (added since "
                "the last run). Read it now with "
                "`python util/check_rss.py --update-activity --force --slug <slug>`: " + ", ".join(
                    f"`{o['slug']}`" for s in report["uncollected"] for o in s["orgs"]) + ".", ""]

    if report["uncovered"]:
        out += [f"{report['uncovered']} active orgs have neither `rss_feed:` nor `news_page:`, "
                "so this checkup can't see them. Their news reaches `events:` only through "
                "the heartbeat's staleness queue.", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="List org posts since the last review, for picking Landscape News by hand")
    parser.add_argument("--slug", action="append", metavar="SLUG", help="Only this org (repeatable)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, metavar="N",
                        help=f"Look back N days for orgs never reviewed (default {DEFAULT_DAYS})")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="List from this date for every org, ignoring review state")
    parser.add_argument("--out", metavar="FILE", help="Write the worklist to FILE instead of stdout")
    parser.add_argument("--mark-reviewed", action="store_true",
                        help="Record the listed orgs as reviewed (run after you've been through the list)")
    args = parser.parse_args()

    since = None
    if args.since:
        since = parse_date(args.since)
        if since is None:
            parser.error(f"--since: not a date: {args.since}")

    orgs, recorded = load_orgs()
    if args.slug:
        wanted = set(args.slug)
        unknown = wanted - {o["slug"] for o in orgs}
        if unknown:
            parser.error(f"not an active org: {', '.join(sorted(unknown))}")
        orgs = [o for o in orgs if o["slug"] in wanted]

    state = load_state()
    report = checkup(orgs, recorded, state, date.today(), default_days=args.days, since_override=since)
    text = render_markdown(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        n = sum(len(s["items"]) for s in report["feeds"])
        print(f"{n} new posts from {len(report['feeds'])} feeds, "
              f"{len(report['pages'])} news pages; worklist written to {args.out}")
    else:
        print(text)

    if args.mark_reviewed:
        marked = mark_reviewed(state, report)
        save_state(state)
        print(f"Marked {marked} org(s) reviewed in {os.path.relpath(STATE_FILE)}", file=sys.stderr)


if __name__ == "__main__":
    main()
