#!/usr/bin/env python3
"""
world_news.py — a filtered worklist of world news about how people are
governed, for the heartbeat's "Read the room" step (HEARTBEAT.md step 5).

Why: until 2026-10, every scheduled heartbeat run skipped that step, which
was written as open-ended web searching ("citizens' assembly announced
2026"...). Open searches are slow, expensive in tokens, rank results by
someone else's algorithm, and mostly surface evergreen explainers. This reads
a fixed, deliberately mixed list of publishers' own feeds
(util/world_news_sources.yml: wires, regional outlets on every continent, a
few non-English, and governance trackers) and keeps only the headlines that
mention a governance mechanism, so a run reads tens of lines, not hundreds of
articles.

The filter is a vocabulary, not the word "democracy". "Democracy" alone is
both too broad (op-eds, and the US Democratic Party) and too narrow (a story
about a citizens' assembly or a postponed election often never uses it). So
headlines are matched against named mechanisms and events, grouped under
labels (deliberative, participatory, electoral system, direct democracy,
constitutional, backsliding, integrity, civic space), in English plus common
Spanish, French, Portuguese and German forms. A match on the bare word
"democracy" counts only as a weak signal: such a story is listed when two or
more outlets carry it, and otherwise only counted.

The same story from several outlets is grouped into one line ("covered by 3:
BBC, Al Jazeera, Dawn"), and stories carried by more than one source come
first: independent pickup across regions is a better notability signal than
any keyword. A story naming a Landscape org is flagged too, since that's a
candidate for the org's own `events:` (and so for Landscape News).

Matches are leads, not sources (CLAUDE.md): open the article, and cite the
primary source where there is one.

State lives in docs/data/world-news.json (committed, not published): per
source, the validators for conditional GET, when it was last read and a
backoff.py failure record; the matching headlines (title, link, date,
source, labels; never article text) for WORLD_KEEP_DAYS; and the time
through which someone last reviewed the list. A source is read at most every
SOURCE_RECHECK_HOURS, so several heartbeat runs in a day don't re-ask anyone.

Usage:
    python util/world_news.py                  # read due sources, print new matches
    python util/world_news.py --offline        # no network: list what's stored
    python util/world_news.py --out FILE       # write the worklist to FILE
    python util/world_news.py --mark-reviewed  # after reviewing; commit the state file
    python util/world_news.py --days 14        # window when nothing was reviewed yet
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

UTIL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, UTIL_DIR)
import backoff  # noqa: E402
import news_signals  # noqa: E402

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml")
    sys.exit(1)

DOCS_DIR = os.path.join(UTIL_DIR, "..", "docs")
SOURCES_FILE = os.path.join(UTIL_DIR, "world_news_sources.yml")
STATE_FILE = os.path.join(DOCS_DIR, "data", "world-news.json")

# A source is read at most this often. The heartbeat can run several times a
# day; news feeds list a day or more of items, so a daily read misses little.
SOURCE_RECHECK_HOURS = 20
# Matching headlines kept, and the cap per file. A month is longer than a
# review should ever lag.
WORLD_KEEP_DAYS = 45
WORLD_ITEMS_MAX = 600
# Window for the first checkup, when nothing has been reviewed yet.
DEFAULT_DAYS = 7
# Two headlines are the same story when they share at least this share of
# their significant words (and at least SAME_STORY_MIN_WORDS of them).
SAME_STORY_JACCARD = 0.4
SAME_STORY_MIN_WORDS = 3

# label -> patterns (regex, case-insensitive, whole words). Specific
# mechanisms and events only; see the module docstring for why not just
# "democracy".
LABELS = {
    "deliberative": [
        r"citizens'? (assembly|assemblies|jury|juries|panel|panels|council)",
        r"people'?s assembly", r"deliberative (democracy|poll(ing)?|process)", r"mini-?publics?",
        r"sortition", r"selected by lot(tery)?", r"democratic lottery",
        r"asambleas? ciudadanas?", r"convention citoyenne", r"assembl[eé]e citoyenne",
        r"assembleias? (cidadãs?|de cidadãos)", r"bürgerr(a|ä)te?",
    ],
    "participatory": [
        r"participatory (budget(ing)?|democracy|planning)", r"presupuestos? participativos?",
        r"orçamentos? participativos?", r"budgets? participatifs?", r"e-?petitions?",
        r"citizens'? initiatives?", r"iniciativa (popular|ciudadana)", r"open government",
        r"public consultation", r"civic tech",
    ],
    "electoral system": [
        r"electoral (reform|system|law|bill|commission|boundaries|roll)",
        r"voting (system|reform|age|rights)", r"proportional representation",
        r"ranked[- ]choice", r"preferential voting", r"mixed[- ]member", r"first[- ]past[- ]the[- ]post",
        r"compulsory voting", r"votes? at 16", r"redistricting", r"gerrymander(ing|ed)?",
        r"voter (suppression|registration|id)", r"electoral fraud", r"vote[- ]rigging",
        r"reformas? electoral(es)?", r"r[ée]formes? [ée]lectorales?", r"reformas? eleitora(l|is)",
        r"wahlrechtsreform",
    ],
    "direct democracy": [
        r"referendums?", r"referenda", r"plebiscites?", r"recall (election|vote|referendum)",
        r"r[eé]f[eé]r[eé]ndums?", r"plebiscitos?", r"revocatorias?", r"consulta popular",
        r"volksabstimmung", r"volksentscheid",
    ],
    "constitutional": [
        r"constitutional (amendment|reform|change|court|convention|crisis|referendum|review)",
        r"new constitution", r"constitution(al)? (rewrite|overhaul)", r"constituent assembly",
        r"reformas? constitucional(es)?", r"asamblea constituyente", r"assembl[ée]e constituante",
        r"constituinte", r"verfassungs(gericht|reform|änderung)",
    ],
    "backsliding": [
        r"coup", r"coup d'[ée]tat", r"golpe de estado", r"martial law", r"state of emergency",
        r"elections? (postponed|delayed|annulled|cancell?ed|suspended|scrapped)",
        r"(postpones?|delays?|annuls?|cancels?|suspends?) (the )?elections?",
        r"(dissolves?|dissolved|dissolution of) (the )?(parliament|national assembly|legislature|congress)",
        r"term limits?", r"third term", r"foreign agents? (law|bill)", r"press freedom",
        r"internet shutdowns?", r"opposition (leader|figure|party)s? (arrested|jailed|detained|banned)",
        r"(ban|bans|banned|banning) (the )?opposition", r"crackdown on (protest|dissent|opposition|civil society|journalists)",
        r"impeach(ment|ed)?", r"democratic backsliding", r"autocra(cy|tic|tisation|tization)",
        r"authoritarian(ism)?",
    ],
    "integrity": [
        r"lobbying", r"lobbyists?", r"political donations?", r"donations? (cap|caps|reform|disclosure)",
        r"campaign finance", r"dark money", r"(anti-?corruption|integrity) (commission|agency|body|watchdog)",
        r"whistle-?blowers?", r"freedom of information", r"transparency (law|bill|register)",
        r"conflicts? of interest", r"ombudsman",
    ],
    "civic space": [
        r"right to protest", r"(anti-?protest|protest) (law|laws|bill|ban)", r"civic space",
        r"civil society (law|bill|groups?|organisations?|organizations?)", r"ngo (law|bill)",
        r"freedom of (assembly|association|expression)",
    ],
}
# Weak: counted, and listed only when several outlets carry the story.
WEAK_LABEL = "democracy (general)"
WEAK_PATTERNS = [r"democracy", r"democratic", r"undemocratic", r"democracia", r"démocratie", r"demokratie"]
# "Democratic Party", "Democrats" and their like are a party name, not the topic.
WEAK_EXCLUDE = re.compile(r"\bDemocratic (Party|National Committee|Republic of the Congo|primary)\b|\bDemocrats?\b")


def _compile(pats):
    return re.compile(r"(?<!\w)(?:" + "|".join(pats) + r")(?!\w)", re.IGNORECASE)


_LABELS = {label: _compile(pats) for label, pats in LABELS.items()}
_WEAK = _compile(WEAK_PATTERNS)


def labels_for(title, lede=""):
    """Sorted labels for a headline (and its feed excerpt's opening). The
    weak label only when no specific one matched."""
    text = news_signals._straight(f"{title or ''}\n{lede or ''}")
    found = sorted(label for label, rx in _LABELS.items() if rx.search(text))
    if not found and _WEAK.search(WEAK_EXCLUDE.sub(" ", text)):
        found = [WEAK_LABEL]
    return found


# --- same-story grouping -----------------------------------------------------

_STOP = set("""a an the and or but of in on at to for from by with as is are was were be been
has have had will would could should may might says said say after over under into about
amid new not no its it this that these those their his her they them than then who what
when where why how more most less much many very just also up out off before during""".split())


def _words(title):
    words = re.findall(r"[^\W\d_]+", news_signals._straight(title or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOP}


def group_stories(items):
    """Group headlines that look like the same story across outlets. Greedy
    and order-dependent, which is fine for a worklist: items are visited
    newest first and each joins the first group it overlaps enough."""
    groups = []
    for item in sorted(items, key=lambda i: (str(i["date"]), i.get("title") or ""), reverse=True):
        words = _words(item.get("title"))
        for g in groups:
            shared = len(words & g["words"])
            union = len(words | g["words"]) or 1
            if shared >= SAME_STORY_MIN_WORDS and shared / union >= SAME_STORY_JACCARD:
                g["items"].append(item)
                g["words"] |= words
                break
        else:
            groups.append({"items": [item], "words": set(words)})
    stories = []
    for g in groups:
        its = g["items"]
        labels = sorted({label for i in its for label in i.get("labels") or []})
        if len(labels) > 1 and WEAK_LABEL in labels:
            labels.remove(WEAK_LABEL)
        stories.append({
            "items": its,
            "sources": list(dict.fromkeys(i["source"] for i in its)),
            "regions": sorted({i.get("region") for i in its if i.get("region")}),
            "labels": labels,
            "mentions": sorted({m for i in its for m in i.get("mentions") or []}),
            "date": max(str(i["date"]) for i in its),
        })
    return stories


def rank(stories):
    """Several outlets first, then a Landscape mention, then the number of
    labels, then newest."""
    stories = sorted(stories, key=lambda s: s["date"], reverse=True)
    return sorted(stories, key=lambda s: (-len(s["sources"]), -bool(s["mentions"]), -len(s["labels"])))


# --- state ---------------------------------------------------------------------

def load_sources(path=SOURCES_FILE):
    with open(path, encoding="utf-8") as f:
        sources = yaml.safe_load(f) or []
    names = [s["name"] for s in sources]
    if len(names) != len(set(names)):
        raise ValueError("duplicate source name in " + path)
    return sources


def load_state(path=STATE_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("sources", {})
    data.setdefault("items", [])
    return data


def save_state(state, path=STATE_FILE):
    ordered = {"reviewed": state.get("reviewed"), "sources": dict(sorted(state["sources"].items())),
               "items": state["items"]}
    text = json.dumps(ordered, indent=1, ensure_ascii=False) + "\n"
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def source_due(record, now):
    """(due, why) for one source's state record."""
    failing = (record or {}).get("failing")
    if failing and backoff.backing_off(failing, now.date()):
        return False, f"failing ({failing.get('error')}), next try {backoff.next_try(failing)}"
    read = _parse_dt((record or {}).get("read"))
    if read and now - read < timedelta(hours=SOURCE_RECHECK_HOURS):
        return False, f"read {int((now - read).total_seconds() // 3600)}h ago"
    return True, ""


def merge_matches(state, source, entries, now, names=(), clean_url=None):
    """Add the entries that match the vocabulary to state["items"] (keyed by
    link), each stamped with when this run first saw it. Returns how many were
    new."""
    by_url = {i["url"]: i for i in state["items"] if i.get("url")}
    added = 0
    for e in entries:
        url = (e.get("link") or "").strip()
        if clean_url:
            url = clean_url(url)
        if not url or url in by_url:
            continue
        lede = news_signals.lede(news_signals._plain(e.get("summary_html")))
        labels = labels_for(e.get("title"), lede)
        if not labels:
            continue
        item = {"date": e["published"].isoformat(), "seen": now.isoformat(),
                "title": " ".join((e.get("title") or "").split()), "url": url,
                "source": source["name"], "region": source.get("region"), "labels": labels}
        named = news_signals.mentions(f"{e.get('title') or ''}\n{lede}", names) if names else []
        if named:
            item["mentions"] = named
        by_url[url] = item
        added += 1
    cutoff = (now.date() - timedelta(days=WORLD_KEEP_DAYS)).isoformat()
    kept = [i for i in by_url.values() if str(i.get("date", "")) >= cutoff]
    kept.sort(key=lambda i: (str(i["date"]), i["url"]), reverse=True)
    state["items"] = kept[:WORLD_ITEMS_MAX]
    return added


def fetch_sources(state, sources, now, session=None, names=()):
    """Read every due source once. Returns a summary list of
    (name, status, detail)."""
    import check_rss as cr
    from robots_check import robots_allowed
    import requests

    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = cr.DOD_USER_AGENT
    summary = []
    for src in sources:
        rec = state["sources"].setdefault(src["name"], {})
        due, why = source_due(rec, now)
        if not due:
            summary.append((src["name"], "skipped", why))
            continue
        if not robots_allowed(src["url"], cr.DOD_USER_AGENT, timeout=10, session=session):
            rec["failing"] = backoff.record_failure(rec.get("failing"), "ROBOTS_DISALLOWED", now.date())
            summary.append((src["name"], "failing", "robots.txt disallows"))
            continue
        res = cr.fetch_feed(src["url"], timeout=15, session=session, validators=rec.get("fetch"))
        if res["status"] == "error":
            rec["failing"] = backoff.record_failure(rec.get("failing"), res["error"], now.date())
            summary.append((src["name"], "failing", res["error"]))
            continue
        rec.pop("failing", None)
        rec["read"] = now.isoformat()
        if res["status"] == "not_modified":
            summary.append((src["name"], "unchanged", ""))
        else:
            if res.get("validators"):
                rec["fetch"] = res["validators"]
            else:
                rec.pop("fetch", None)
            added = merge_matches(state, src, res["entries"], now, names, cr.strip_tracking)
            summary.append((src["name"], "read", f"{len(res['entries'])} items, {added} new matches"))
        time.sleep(0.3)
    return summary


# --- worklist ------------------------------------------------------------------

def pending(state, now, default_days=DEFAULT_DAYS):
    """Items first seen after the last review. When nothing has been
    reviewed yet, items dated within the last default_days instead, since a
    first read stamps everything in every feed as just seen."""
    reviewed = _parse_dt(state.get("reviewed"))
    if reviewed is None:
        cutoff = (now.date() - timedelta(days=default_days)).isoformat()
        return [i for i in state["items"] if str(i.get("date", "")) >= cutoff]
    return [i for i in state["items"] if (_parse_dt(i.get("seen")) or now) > reviewed]


def render(state, now, summary=(), default_days=DEFAULT_DAYS):
    items = pending(state, now, default_days)
    stories = rank(group_stories(items))
    shown = [s for s in stories if s["labels"] != [WEAK_LABEL] or len(s["sources"]) > 1]
    weak_only = len(stories) - len(shown)
    multi = [s for s in shown if len(s["sources"]) > 1]
    single = [s for s in shown if len(s["sources"]) == 1]
    since = state.get("reviewed") or f"the last {default_days} days"
    out = [f"# World news worklist — {now.date().isoformat()}", "",
           f"Headlines about how people are governed, from {len(state['sources']) or 'no'} "
           f"publishers' feeds (util/world_news_sources.yml), new since {since}. Each line is a "
           "lead, not a source: open it and cite the primary source. Then run "
           "`python util/world_news.py --mark-reviewed` and commit `docs/data/world-news.json`.", "",
           f"**{len(shown)} stor{'y' if len(shown) == 1 else 'ies'}** ({len(multi)} carried by "
           f"more than one outlet) from {len(items)} matching headlines"
           + (f" · {weak_only} more matched only the word \"democracy\" in one outlet (not listed)"
              if weak_only else ""), ""]

    def line(s):
        first = s["items"][0]
        more = ""
        if len(s["sources"]) > 1:
            more = f" — covered by {len(s['sources'])}: {', '.join(s['sources'][:5])}"
            if len(s["sources"]) > 5:
                more += f" +{len(s['sources']) - 5}"
        else:
            more = f" — {first['source']}"
        tags = ", ".join(s["labels"])
        if s["mentions"]:
            tags += " · **names " + ", ".join(s["mentions"]) + "**"
        return f"- {s['date']} · {tags} · [{_md(first['title'])}]({first['url']}){more}"

    if multi:
        out += ["## Carried by several outlets", ""] + [line(s) for s in multi] + [""]
    if single:
        out += ["## One outlet", ""] + [line(s) for s in single] + [""]
    failing = [(n, d) for n, st, d in summary if st == "failing"]
    if not summary:
        failing = [(n, r["failing"].get("error")) for n, r in state["sources"].items() if r.get("failing")]
    if failing:
        out += ["Failing sources (backing off; drop or replace one that keeps failing): "
                + ", ".join(f"{n} ({d})" for n, d in failing) + ".", ""]
    return "\n".join(out)


def _md(text):
    return " ".join(str(text or "").split()).replace("[", "\\[").replace("]", "\\]")


def main():
    parser = argparse.ArgumentParser(description="Filtered world news worklist for the heartbeat")
    parser.add_argument("--offline", action="store_true", help="Don't read any feed; list what's stored")
    parser.add_argument("--out", metavar="FILE", help="Write the worklist to FILE instead of stdout")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, metavar="N",
                        help=f"Window when nothing has been reviewed yet (default {DEFAULT_DAYS})")
    parser.add_argument("--mark-reviewed", action="store_true",
                        help="Record everything listed as reviewed (run after going through it)")
    args = parser.parse_args()

    now = _now()
    state = load_state()
    summary = []
    if not args.offline:
        names = news_signals.landscape_names()
        summary = fetch_sources(state, load_sources(), now, names=names)
        for name, status, detail in summary:
            if status != "skipped":
                print(f"  {status:9} {name}{': ' + detail if detail else ''}", file=sys.stderr)
    text = render(state, now, summary, args.days)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Worklist written to {args.out}", file=sys.stderr)
    else:
        print(text)
    if args.mark_reviewed:
        # Through the newest item this run has seen, never "now": an item a
        # later run stamps with an earlier clock can't be skipped this way.
        seen = [d for d in (_parse_dt(i.get("seen")) for i in state["items"]) if d]
        if seen:
            state["reviewed"] = max(seen).isoformat()
    save_state(state)


if __name__ == "__main__":
    main()
