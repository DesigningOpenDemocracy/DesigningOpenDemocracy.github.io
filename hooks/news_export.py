"""
news_export.py — MkDocs hook: build Landscape News, the past-facing
counterpart to the site-wide calendar.

The calendar (hooks/calendar_export.py) projects every org's *future*
gatherings from `events:` into one cross-org list. This hook projects the
*recent past* of the same field's news (`kind: news` or `kind: launch`, see
EVENT_KINDS in calendar_export.py), narrowed to what an editor has already
flagged as worth a reader's attention: entries carrying `notable: true`
(major) or `notable: "medium"` (notable), dated within the last
NEWS_WINDOW_DAYS. Conferences and meetups are the calendar's, not news; the
only ones here are a major one's heads-up before it starts.
A launch, a handbook's new edition, a leadership change, a flagship
report — the things one organisation in the landscape would want to know
another had done, without reading 170 org pages to find them.

Deliberately not a new data source. There is no `news:` field and no
second place to write an item: an org's own `events:` list is where its
milestones are recorded, sourced and verified (check_event_sourcing.py,
check_fragments.py), and a news item is simply one of those milestones
seen from across the landscape instead of from the org's own page. So
adding news means adding a notable event to the org's page, and an item
carries exactly the sourcing its event does — nothing here can say more
than the timeline it's drawn from. The `notable:` tiers are already
reserved for the small number of events per org worth interrupting a
reader for (see CLAUDE.md), which is exactly the bar a news feed needs;
un-tiered events never appear, and neither does anything older than the
window, since a 2011 founding is history, not news.

Also deliberately not an aggregation of the orgs' own RSS feeds
(`rss_feed:`): those are every post an org publishes, which is the
firehose this page exists to spare readers from. They're an intake
instead: util/news_checkup.py lists what orgs have posted since the last
review, and the few posts that clear the notable: bar are moved into the
org's events: by hand, which is how they reach this page.

Output (all regenerated every build, gitignored):
  - docs/news.xml               — RSS 2.0, every item
  - docs/news-<CC>.xml          — RSS 2.0, one per country in the landscape
  - docs/news-topic-<slug>.xml  — RSS 2.0, one per concept an org carries
  - docs/news.json              — JSON Feed 1.1, every item
  - `news_items` / `news_feeds` / `news_window_days` Jinja globals —
    consumed by docs/overrides/news.html

The per-country and per-topic feeds exist for the same reason the
calendar's per-country .ics files do: a subscribed feed can't be filtered
after the fact by most readers, so a reader who only follows one country
or one topic needs a URL that is already just that. Unlike the calendar's
feeds, one is written for *every* country and topic in the landscape, not
just those with an item right now — news in a given country is rare
(a few items a year), and a subscribed URL that 404s whenever its country
has a quiet year would be worse than an empty channel.
"""

import glob
import html
import importlib.util
import json
import os
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

try:
    import frontmatter
except ImportError:
    frontmatter = None

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(HOOKS_DIR, "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
POSTS_DIR = os.path.join(DOCS_DIR, "blog", "posts")

# The org a DOD blog post is attributed to on News (its logo, country and
# topics), since a post isn't any org's events: entry. See collect_blog_news.
DOD_SLUG = "designing-open-democracy"
SKIP_FILES = {"index.md"}

# How far back an item stays news. Three months keeps the page reading as
# "what's been happening" rather than an archive; the org's own page already
# carries its full history. It was a year until 2026-09, which put items
# eleven months old on a page called News. A quiet country's feed may now
# go empty for a while, but a feed reader keeps the items it has already
# seen, and the feed URL itself still exists (see feed_slices).
NEWS_WINDOW_DAYS = 90

# How many days before it starts an event is announced in News, by tier.
# Only major events are announced ahead: News is what happened, and a
# heads-up is only worth a place there for the rare flagship-scale event a
# reader would plan around. Everything else waits for the calendar. A tier
# missing from this map (or set to 0) is never announced; adding
# "medium": 7 would give notable events a week's notice. An announced
# event stays in News while it runs and after it ends, as one item with
# one guid, so a feed reader sees it once, when it's announced.
ANNOUNCE_DAYS = {True: 30}

# A major event can ask for more (or less) notice than its tier's default
# with its own `announce_days:` (an international conference people need to
# book travel for might want 90). Capped at a year: further out than that,
# it's the calendar's job, not a news item. Only honoured on a tier
# ANNOUNCE_DAYS lists, so a notable event can't opt itself in, and the
# archive (which passes an empty map) never announces anything.
# util/check_event_sourcing.py fails the build on a value outside this
# range, since the hook otherwise falls back to the default without a word.
MAX_ANNOUNCE_DAYS = 365


def valid_announce_days(value):
    """An `announce_days:` value the hook will honour: a whole number of days
    from 1 to MAX_ANNOUNCE_DAYS. (`true` is excluded explicitly: YAML makes
    it a bool, and Python counts a bool as an int.)"""
    return (isinstance(value, int) and not isinstance(value, bool)
            and 1 <= value <= MAX_ANNOUNCE_DAYS)


def announce_lead(entry, tier, announce_days):
    """Days of notice an event gets in News, or None if it isn't announced."""
    default = announce_days.get(tier) if tier is not False else None
    if not default:
        return None
    own = entry.get("announce_days")
    return own if valid_announce_days(own) else default

TIER_LABELS = {True: "Major", "medium": "Notable"}

ATOM_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM_NS)

# Feed file names are built from these, so anything else is refused rather
# than written into a path.
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The calendar hook owns the country-name map and the notable-tier and date
# parsing rules; the news surface has to agree with it on all three, so it
# imports them rather than keeping a second copy (the same reason
# util/check_elections.py loads it). text_fragment derives #:~:text= links
# and reads the Wayback/url_status record, as it does for org timelines.
_cal = _load_module("_news_calendar_export", os.path.join(HOOKS_DIR, "calendar_export.py"))
_tf = _load_module("_news_text_fragment", os.path.join(HOOKS_DIR, "..", "util", "text_fragment.py"))

COUNTRY_NAMES = _cal._COUNTRY_NAMES
_notable_tier = _cal._notable_tier
_parse_date = _cal._parse_date
_is_current = _cal._is_current
_event_kind = _cal._event_kind
NEWS_KINDS = _cal.NEWS_KINDS


def country_name(code):
    return COUNTRY_NAMES.get(code, code or "")


def topic_label(slug, concept_titles):
    return concept_titles.get(slug) or slug.replace("-", " ").title()


def load_orgs(orgs_dir=ORGS_DIR):
    """[(slug, metadata)] for every org page, in filename order — which is
    also what decides the primary org of a merged item (see collect_news)."""
    if frontmatter is None:
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(orgs_dir, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        out.append((os.path.basename(path)[:-3], frontmatter.load(path).metadata))
    return out


def load_concept_titles(concepts_dir=CONCEPTS_DIR):
    if frontmatter is None:
        return {}
    titles = {}
    for path in glob.glob(os.path.join(concepts_dir, "*.md")):
        if os.path.basename(path) in SKIP_FILES:
            continue
        title = frontmatter.load(path).metadata.get("title")
        if title:
            titles[os.path.basename(path)[:-3]] = str(title)
    return titles


def news_guid(d, url, slug, title):
    """A stable id for one news item, the same in every feed it appears in.

    Keyed on date + source URL where there is one, not on the title: titles
    get reworded (tense, a typo) far more often than a citation changes, and
    a changed id reaches every subscriber as a brand-new item. It also keeps
    a co-hosted item's id the same when a second co-host's page later adds
    the same event and it merges in. Without a URL, the org and title are
    all there is to key on."""
    key = f"dod-news:{d.isoformat()}:{url}" if url else f"dod-news:{slug}:{d.isoformat()}:{title}"
    return "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _link_for(url, quote, archive_info):
    """(href, archive_url, url_status) — the same link rule organisation.html
    applies to a timeline entry: the source with a #:~:text= fragment built
    from the quote, or the Wayback snapshot instead once a human has recorded
    the original as dead or unfit."""
    if not url:
        return None, None, None
    info = (archive_info or {}).get(url) or {}
    archive_url = info.get("archive_url")
    url_status = info.get("url_status")
    if url_status in ("dead", "unfit") and archive_url:
        return archive_url, archive_url, url_status
    return _tf.with_fragment(url, quote), archive_url, url_status


def collect_news(orgs, today, window_days=NEWS_WINDOW_DAYS, archive_info=None, notable_only=True,
                 announce_days=None, kinds=NEWS_KINDS):
    """Recent notable events across every org, newest first.

    An event qualifies when it carries a notable: tier, has ended (on its
    end_date where there is one) before `today`, and started within
    `window_days` of it. Anything still running or ahead is the calendar's
    (calendar_export._is_current), so an event is on exactly one of the two
    pages at any build.

    Co-hosted events are recorded on each co-host's page, usually under the
    same source URL (DOD's International Day of Democracy panel sits on both
    its own page and 888 Co-operative Causeway's). Two items with the same
    date and URL merge into one, listing every org, rather than reaching a
    subscriber twice. The first org in filename order supplies the title,
    note and quote; the stronger of the tiers wins; countries and concepts
    are the union.

    The exception is an announcement: a tier listed in `announce_days`
    (ANNOUNCE_DAYS by default: major events, 30 days, or the event's own
    `announce_days:`) enters News that many days before it starts, marked `upcoming`, and so for that stretch is on
    both News and the calendar. Its `announced` date is what the feeds
    publish it under.

    The Landscape Archive (/archive/) is the same view with the limits off:
    window_days=None for no cut-off and notable_only=False for every
    curated event, so the two pages can't disagree about what an item says
    or where it links. It passes announce_days={}, since it's a record of
    what has happened, and kinds=None, since it records gatherings too.

    `kinds` is which event kinds (calendar_export.EVENT_KINDS) count once
    they've happened: news and launches, not gatherings. A conference is
    the calendar's; once it's over it's history, not news. The one place a
    gathering reaches News is the announcement above, and it leaves again
    when it ends. A `news` item is never announced ahead: a report due out
    next month is news the day it's out.
    """
    if announce_days is None:
        announce_days = ANNOUNCE_DAYS
    items = []
    by_key = {}
    for slug, m in orgs:
        for entry in m.get("events") or []:
            if not isinstance(entry, dict):
                continue
            tier = _notable_tier(entry)
            if tier is False and notable_only:
                continue
            d = _parse_date(entry.get("date"))
            if not d:
                continue
            # The calendar keeps an event until it has ended
            # (calendar_export._is_current), so news normally starts where
            # that stops; only an announced tier comes in earlier.
            upcoming = _is_current(d, _parse_date(entry.get("end_date")), today)
            kind = _event_kind(entry)
            if upcoming:
                if kind == "news":
                    continue
                lead = announce_lead(entry, tier, announce_days)
                if not lead or (d - today).days > lead:
                    continue
                announced = d - timedelta(days=lead)
            else:
                if kinds is not None and kind not in kinds:
                    continue
                if window_days is not None and (today - d).days > window_days:
                    continue
                announced = d
            url = entry.get("url") or ""
            org_title = m.get("title", slug)
            country = entry.get("country") or m.get("country")
            concepts = [c for c in (m.get("concepts") or []) if isinstance(c, str)]
            org_ref = {"slug": slug, "title": org_title}

            key = (d, url) if url else None
            if key and key in by_key:
                item = by_key[key]
                item["orgs"].append(org_ref)
                if country and country not in item["countries"]:
                    item["countries"].append(country)
                item["concepts"] += [c for c in concepts if c not in item["concepts"]]
                if tier is True:
                    item["notable"] = True
                continue

            title = entry.get("title", "Untitled")
            href, archive_url, url_status = _link_for(url, entry.get("quote"), archive_info)
            item = {
                "id": news_guid(d, url, slug, title),
                "date": d,
                "upcoming": upcoming,
                "ongoing": upcoming and d <= today,
                "announced": announced,
                "end_date": _parse_date(entry.get("end_date")),
                "title": title,
                "url": url,
                "href": href,
                "archive_url": archive_url,
                "url_status": url_status,
                "source": entry.get("source"),
                "note": entry.get("note"),
                "quote": entry.get("quote"),
                "notable": tier,
                "notable_reason": entry.get("notable_reason"),
                "kind": kind,
                "type": entry.get("type"),
                "location": entry.get("location"),
                "coverage_url": entry.get("coverage_url"),
                "proof_warning": bool(entry.get("proof_warning")),
                "org_slug": slug,
                "org_title": org_title,
                "logo": m.get("logo"),
                "logo_bg": m.get("logo_bg"),
                "orgs": [org_ref],
                "country": country,
                "countries": [country] if country else [],
                "concepts": list(concepts),
            }
            items.append(item)
            if key:
                by_key[key] = item
    return sort_items(items)


def sort_items(items):
    """Announcements first, soonest first; then what has happened, newest
    first, majors ahead of notables on the same day."""
    items.sort(key=lambda i: (not i["upcoming"],
                              i["date"].toordinal() if i["upcoming"] else -i["date"].toordinal(),
                              i["notable"] is not True, i["org_title"].lower()))
    return items


try:
    from pymdownx.slugs import slugify as _pymdownx_slugify
    _post_slugify = _pymdownx_slugify(case="lower")
except ImportError:  # pragma: no cover - pymdownx ships with mkdocs-material
    _post_slugify = None


def post_title(meta, content=""):
    """A post's title as the blog plugin reads it: `title:`, else the
    first `# ` heading in the body (several older posts carry only that)."""
    if meta.get("title"):
        return str(meta["title"])
    for line in (content or "").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def post_url(meta, content=""):
    """The path the Material blog plugin publishes a post at, with its
    defaults as this site uses them: post_url_format "{date}/{slug}", date
    as yyyy/MM/dd, and the slug from `slug:` or else the title through
    pymdownx's slugify(case="lower") with "-" (material/plugins/blog/
    config.py). Worked out here rather than read off the built page because
    News writes its feeds in on_pre_build, before the plugin has assigned
    any URLs. tests/test_news_export.py pins it against real post URLs; if
    mkdocs.yml ever sets post_url_format or post_slugify, change this too."""
    d = _post_date(meta)
    title = post_title(meta, content)
    if not d or not (meta.get("slug") or (title and _post_slugify)):
        return None
    slug = meta.get("slug") or _post_slugify(title, "-")
    return f"/blog/{d.year:04d}/{d.month:02d}/{d.day:02d}/{slug}/"


def _post_date(meta):
    d = meta.get("date")
    if isinstance(d, dict):  # the blog plugin's `date: {created: ...}` form
        d = d.get("created")
    if isinstance(d, datetime):
        d = d.date()
    return _parse_date(d)


# `news:` on a blog post: true for a notable item, "major" for a major one.
POST_NEWS_TIERS = {True: "medium", "major": True}


def post_countries(meta, default):
    """The countries a News-flagged post is filed under: its
    `news_countries:` (one ISO 3166-1 alpha-2 code or a list), else DOD's
    own country. They drive the country filter and the per-country feeds,
    so a post about Taiwan belongs in Taiwan's feed, not Australia's just
    because DOD is Australian. An unknown code fails the build, since the
    item would otherwise vanish from the feed its author meant it for."""
    raw = meta.get("news_countries")
    if raw is None:
        return [default] if default else []
    codes = [raw] if isinstance(raw, str) else list(raw or [])
    out = []
    for c in codes:
        code = str(c).strip().upper()
        if code not in COUNTRY_NAMES:
            raise ValueError(
                f"news_countries: {c!r} on blog post {meta.get('title')!r} is not a country "
                f"code hooks/calendar_export.py knows (ISO 3166-1 alpha-2, e.g. AU, TW)")
        if code not in out:
            out.append(code)
    return out


def collect_blog_news(orgs, today, posts_dir=POSTS_DIR, window_days=NEWS_WINDOW_DAYS):
    """DOD's own blog posts that opted into News with `news:` in their
    frontmatter, as News items attributed to DOD.

    A post isn't an org's events: entry: the maintainer's call (2026-09-30)
    when the recap of DOD's International Day of Democracy panel was first
    written up as a DOD event to get it onto News. A writeup isn't something
    that happened to DOD; it's something DOD published. So the post opts in
    itself, and the item comes from the post: its title, its `summary:` as
    the lede, and a link to it. Drafts never appear, and the same window
    applies as for org news (window_days=None for the Archive). Blog posts have no notable: tier of their own,
    so `news: true` reads as notable and `news: major` as major, and are
    filed under DOD's country unless `news_countries:` says otherwise (see
    post_countries)."""
    if frontmatter is None or not os.path.isdir(posts_dir):
        return []
    dod = dict(orgs).get(DOD_SLUG, {})
    org_title = dod.get("title", "Designing Open Democracy")
    country = dod.get("country")
    concepts = [c for c in (dod.get("concepts") or []) if isinstance(c, str)]
    items = []
    for path in sorted(glob.glob(os.path.join(posts_dir, "*.md"))):
        post = frontmatter.load(path)
        meta = post.metadata
        flag = meta.get("news")
        if meta.get("draft") or flag not in POST_NEWS_TIERS:
            continue
        d = _post_date(meta)
        url = post_url(meta, post.content)
        if not d or not url or d > today or (window_days is not None and (today - d).days > window_days):
            continue
        title = post_title(meta, post.content)
        countries = post_countries(meta, country)
        items.append({
            "id": news_guid(d, url, DOD_SLUG, title),
            "date": d, "upcoming": False, "ongoing": False, "announced": d, "end_date": None,
            "title": title, "url": url, "href": url,
            "archive_url": None, "url_status": None, "source": None,
            "note": meta.get("summary"), "quote": None,
            "notable": POST_NEWS_TIERS[flag], "notable_reason": "From the DOD blog",
            "kind": "post", "type": None, "location": None, "coverage_url": None,
            "proof_warning": False,
            "org_slug": DOD_SLUG, "org_title": org_title,
            "logo": dod.get("logo"), "logo_bg": dod.get("logo_bg"),
            "orgs": [{"slug": DOD_SLUG, "title": org_title}],
            "country": countries[0] if countries else None, "countries": countries,
            "concepts": list(concepts),
        })
    return items


def feed_slices(orgs, items, concept_titles):
    """Every country and topic that gets its own feed, with its current item
    count — countries from any org page (or event override), topics from any
    org's concepts: list."""
    countries, topics = set(), set()
    for _slug, m in orgs:
        if m.get("country"):
            countries.add(str(m["country"]))
        for e in m.get("events") or []:
            if isinstance(e, dict) and e.get("country"):
                countries.add(str(e["country"]))
        for c in m.get("concepts") or []:
            if isinstance(c, str):
                topics.add(c)
    for i in items:
        countries.update(i["countries"])
        topics.update(i["concepts"])
    country_rows = [
        {"code": c, "name": country_name(c),
         "count": sum(1 for i in items if c in i["countries"])}
        for c in countries if _COUNTRY_RE.match(c)
    ]
    topic_rows = [
        {"slug": t, "label": topic_label(t, concept_titles),
         "count": sum(1 for i in items if t in i["concepts"])}
        for t in topics if _TOPIC_RE.match(t)
    ]
    country_rows.sort(key=lambda r: r["name"].lower())
    topic_rows.sort(key=lambda r: r["label"].lower())
    return {"countries": country_rows, "topics": topic_rows}


def _abs(site_url, path):
    return f"{site_url}{path}" if path.startswith("/") else path


def _item_link(item, site_url):
    """Where a feed item points: the source itself, falling back to the org's
    Landscape profile for an event cited by `source:` (a book, testimony)
    with no URL to open."""
    # A DOD blog post's href is site-relative, so it goes through _abs too.
    return _abs(site_url, item["href"]) if item["href"] else _abs(site_url, f"/organisations/{item['org_slug']}/")


def _item_title(item):
    # A feed reader shows this line with nothing around it, so it has to say
    # whose news it is — the same "<org>: <title>" shape the calendar's .ics
    # SUMMARY uses. A merged item names its first org; the title of a
    # co-hosted event already names the other.
    title = f"{item['org_title']}: {item['title']}"
    if item.get("upcoming"):
        # The line a feed reader shows has to say it hasn't happened yet.
        title += f" (coming up {_day_label(item['date'])})"
    return title


def _day_label(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def _item_categories(item, concept_titles):
    cats = [TIER_LABELS[item["notable"]]]
    cats += [country_name(c) for c in item["countries"]]
    if item.get("type"):
        cats.append(str(item["type"]))
    cats += [topic_label(c, concept_titles) for c in item["concepts"]]
    return cats


def item_html(item, site_url, concept_titles):
    """The item body shared by the RSS description and JSON Feed content_html."""
    esc = html.escape
    parts = []
    lead = f"<strong>{TIER_LABELS[item['notable']]}</strong>"
    if item.get("upcoming"):
        lead += f" · coming up {esc(_day_label(item['date']))}"
    if item.get("notable_reason"):
        lead += f" — {esc(str(item['notable_reason']))}"
    parts.append(f"<p>{lead}</p>")
    if item.get("note"):
        parts.append(f"<p>{esc(str(item['note']))}</p>")
    if item.get("quote"):
        parts.append(f"<blockquote>{esc(str(item['quote']))}</blockquote>")
    if item.get("proof_warning"):
        parts.append("<p><em>Sourcing not yet confirmed — check the source before relying on this.</em></p>")
    links = []
    for org in item["orgs"]:
        profile = _abs(site_url, f"/organisations/{org['slug']}/")
        links.append(f'<a href="{esc(profile)}">{esc(org["title"])}</a>')
    tail = "Landscape profile: " + ", ".join(links)
    if item.get("href"):
        tail += f' · <a href="{esc(_abs(site_url, item["href"]))}">{"Read the post" if item.get("kind") == "post" else "Source"}</a>'
    elif item.get("source"):
        tail += f" · Cited: {esc(str(item['source']))}"
    parts.append(f"<p>{tail}</p>")
    facets = [country_name(c) for c in item["countries"]]
    facets += [topic_label(c, concept_titles) for c in item["concepts"]]
    if facets:
        parts.append(f"<p><small>{esc(' · '.join(facets))}</small></p>")
    return "\n".join(parts)


def _pub_date(d):
    return format_datetime(datetime(d.year, d.month, d.day, tzinfo=timezone.utc))


def render_rss(items, *, title, description, page_url, feed_url, site_url, concept_titles):
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = title
    ET.SubElement(ch, "link").text = page_url
    ET.SubElement(ch, "description").text = description
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, f"{{{ATOM_NS}}}link",
                  {"href": feed_url, "rel": "self", "type": "application/rss+xml"})
    image = ET.SubElement(ch, "image")
    ET.SubElement(image, "url").text = _abs(site_url, "/assets/dodlogo_transparent.png")
    ET.SubElement(image, "title").text = title
    ET.SubElement(image, "link").text = page_url
    for item in items:
        el = ET.SubElement(ch, "item")
        ET.SubElement(el, "title").text = _item_title(item)
        ET.SubElement(el, "link").text = _item_link(item, site_url)
        ET.SubElement(el, "guid", {"isPermaLink": "false"}).text = item["id"]
        ET.SubElement(el, "pubDate").text = _pub_date(item.get("announced") or item["date"])
        ET.SubElement(el, "description").text = item_html(item, site_url, concept_titles)
        for cat in _item_categories(item, concept_titles):
            ET.SubElement(el, "category").text = cat
    ET.indent(rss)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def render_json_feed(items, *, page_url, feed_url, site_url, concept_titles):
    """JSON Feed 1.1 (https://www.jsonfeed.org/version/1.1/). The `_dod`
    object on each item is a JSON Feed extension (any key starting with an
    underscore): the structured fields the RSS categories flatten into text,
    for anyone filtering the feed themselves."""
    feed_items = []
    for item in items:
        d = item["date"]
        pub = item.get("announced") or d
        feed_items.append({
            "id": item["id"],
            "url": _item_link(item, site_url),
            "title": _item_title(item),
            "content_html": item_html(item, site_url, concept_titles),
            "summary": item.get("notable_reason") or item["title"],
            "date_published": datetime(pub.year, pub.month, pub.day, tzinfo=timezone.utc).isoformat(),
            "tags": _item_categories(item, concept_titles),
            "authors": [{"name": o["title"], "url": _abs(site_url, f"/organisations/{o['slug']}/")}
                        for o in item["orgs"]],
            "_dod": {
                "date": d.isoformat(),
                "end_date": item["end_date"].isoformat() if item.get("end_date") else None,
                "upcoming": bool(item.get("upcoming")),
                "event_title": item["title"],
                "tier": "major" if item["notable"] is True else "medium",
                "notable_reason": item.get("notable_reason"),
                "orgs": [o["slug"] for o in item["orgs"]],
                "countries": item["countries"],
                "concepts": item["concepts"],
                "type": item.get("type"),
                "source_url": _abs(site_url, item["url"]) if item["url"] else None,
                "source": item.get("source"),
                "note": item.get("note"),
                "quote": item.get("quote"),
            },
        })
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Designing Open Democracy — Landscape News",
        "home_page_url": page_url,
        "feed_url": feed_url,
        "description": _description(),
        "icon": _abs(site_url, "/assets/dodlogo_transparent.png"),
        "language": "en",
        "items": feed_items,
    }
    return json.dumps(feed, ensure_ascii=False, indent=2) + "\n"


WINDOW_PHRASES = {90: "three months", 365: "year"}


def _window_phrase():
    return WINDOW_PHRASES.get(NEWS_WINDOW_DAYS, f"{NEWS_WINDOW_DAYS} days")


def _description(scope=""):
    who = f"organisations {scope}" if scope else "organisations"
    return (f"Major and notable news from {who} across the Democracy Landscape, "
            f"over the past {_window_phrase()}. Drawn from each organisation's "
            "curated, sourced timeline — not a firehose.")


def _write_if_changed(path, content):
    """Leave a file's mtime alone when its content hasn't changed: nearly all
    ~100 feeds are identical from one build to the next, and rewriting them
    anyway is churn for `mkdocs serve`'s file watcher."""
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def write_feeds(items, slices, out_dir, site_url, concept_titles):
    page_url = _abs(site_url, "/news/")
    _write_if_changed(os.path.join(out_dir, "news.xml"), render_rss(
        items, title="Designing Open Democracy — Landscape News",
        description=_description(), page_url=page_url,
        feed_url=_abs(site_url, "/news.xml"), site_url=site_url,
        concept_titles=concept_titles))
    _write_if_changed(os.path.join(out_dir, "news.json"), render_json_feed(
        items, page_url=page_url, feed_url=_abs(site_url, "/news.json"),
        site_url=site_url, concept_titles=concept_titles))
    for row in slices["countries"]:
        code = row["code"]
        _write_if_changed(os.path.join(out_dir, f"news-{code}.xml"), render_rss(
            [i for i in items if code in i["countries"]],
            title=f"Designing Open Democracy — Landscape News: {row['name']}",
            description=_description(f"in {row['name']}"),
            page_url=f"{page_url}?country={code}",
            feed_url=_abs(site_url, f"/news-{code}.xml"), site_url=site_url,
            concept_titles=concept_titles))
    for row in slices["topics"]:
        slug = row["slug"]
        _write_if_changed(os.path.join(out_dir, f"news-topic-{slug}.xml"), render_rss(
            [i for i in items if slug in i["concepts"]],
            title=f"Designing Open Democracy — Landscape News: {row['label']}",
            description=_description(f"working on {row['label']}"),
            page_url=f"{page_url}?topic={slug}",
            feed_url=_abs(site_url, f"/news-topic-{slug}.xml"), site_url=site_url,
            concept_titles=concept_titles))


_items: list = []
_archive: list = []
_feeds: dict = {"countries": [], "topics": []}
_concept_titles: dict = {}


def on_pre_build(config):
    if frontmatter is None:
        return
    orgs = load_orgs()
    concept_titles = load_concept_titles()
    archive_info = _tf.load_archive_info()
    items = sort_items(collect_news(orgs, date.today(), archive_info=archive_info)
                       + collect_blog_news(orgs, date.today()))
    # No feed for the archive: it's for browsing and search, and every
    # notable item in it already went out on /news.xml in its time.
    _archive[:] = collect_news(orgs, date.today(), window_days=None,
                               archive_info=archive_info, notable_only=False,
                               announce_days={}, kinds=None)
    # DOD's own flagged posts belong in the record too, so an older one
    # (outside News' window) still has a place in the cross-org views.
    _archive[:] = sort_items(_archive + collect_blog_news(orgs, date.today(), window_days=None))
    slices = feed_slices(orgs, items, concept_titles)
    site_url = (config.get("site_url") or "").rstrip("/")
    write_feeds(items, slices, DOCS_DIR, site_url, concept_titles)

    _items[:] = items
    _feeds.clear()
    _feeds.update(slices)
    _concept_titles.clear()
    _concept_titles.update(concept_titles)


def on_env(env, config, files):
    env.globals["news_items"] = _items
    env.globals["archive_items"] = _archive
    env.globals["news_feeds"] = _feeds
    env.globals["news_window_days"] = NEWS_WINDOW_DAYS
    env.globals["news_window_phrase"] = _window_phrase()
    env.filters["topic_label"] = lambda slug: topic_label(slug, _concept_titles)
    return env


_lit: list = []


def on_page_context(context, *, page, config, nav):
    """Keep the News tab highlighted on /archive/.

    The archive is deliberately left out of the nav (mkdocs.yml's
    not_in_nav) rather than made a twelfth tab, so nothing in the nav is
    active while it renders and every tab would sit dark. It is the long
    tail of Landscape News, so the News page is switched on for the render
    and off again after (on_post_page) — the same thing hooks/org_template.py
    does for org profiles under the Democracy Landscape tab. The switch-off
    matters as much, or the tab stays lit on every page built afterwards."""
    if page.file.src_uri == "archive.md":
        for item in nav.pages:
            if item.file.src_uri == "news.md" and not item.active:
                item.active = True
                _lit.append(item)
    return context


def on_post_page(output, *, page, config):
    while _lit:
        _lit.pop().active = False
    return output
