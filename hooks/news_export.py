"""
news_export.py — MkDocs hook: build Landscape News, the past-facing
counterpart to the site-wide calendar.

The calendar (hooks/calendar_export.py) projects every org's *future*
`events:` entries into one cross-org list. This hook projects the *recent
past* of the same field, narrowed to what an editor has already flagged as
worth a reader's attention: entries carrying `notable: true` (major) or
`notable: "medium"` (notable), dated within the last NEWS_WINDOW_DAYS.
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
from datetime import date, datetime, timezone
from email.utils import format_datetime

try:
    import frontmatter
except ImportError:
    frontmatter = None

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(HOOKS_DIR, "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
CONCEPTS_DIR = os.path.join(DOCS_DIR, "concepts")
SKIP_FILES = {"index.md"}

# How far back an item stays news. A year is long enough that a quiet
# country's feed isn't permanently empty and short enough that the page
# reads as "what's been happening", not an archive — the org's own page
# already carries its full history.
NEWS_WINDOW_DAYS = 365

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
# The topic gate for orgs that only partly work on democracy is shared
# with the calendar, so the two views can't disagree about what's on topic.
is_democracy_related = _cal.is_democracy_related


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


def _merge_cohost(item, org_ref, country, concepts, tier):
    item["orgs"].append(org_ref)
    if country and country not in item["countries"]:
        item["countries"].append(country)
    item["concepts"] += [c for c in concepts if c not in item["concepts"]]
    if tier is True:
        item["notable"] = True


def collect_news(orgs, today, window_days=NEWS_WINDOW_DAYS, archive_info=None):
    """Recent notable events across every org, newest first.

    An event qualifies when it carries a notable: tier and started before
    `today` but within `window_days` of it. Anything dated today or later is
    the calendar's (calendar_export.py takes date >= today), so an event is
    on exactly one of the two pages at any build.

    Co-hosted events are recorded on each co-host's page, usually under the
    same source URL (DOD's International Day of Democracy panel sits on both
    its own page and 888 Co-operative Causeway's). Two items with the same
    date and URL merge into one, listing every org, rather than reaching a
    subscriber twice. The first org in filename order supplies the title,
    note and quote; the stronger of the tiers wins; countries and concepts
    are the union.

    An off-topic event from a partial-focus org (see is_democracy_related) never
    creates an item, but still joins one as a co-host: if the same event is
    on a democracy-focused org's page it is news regardless, and leaving a
    co-host off would misreport who ran it.
    """
    items = []
    by_key = {}
    held = []
    for slug, m in orgs:
        for entry in m.get("events") or []:
            if not isinstance(entry, dict):
                continue
            tier = _notable_tier(entry)
            if tier is False:
                continue
            d = _parse_date(entry.get("date"))
            if not d or d >= today or (today - d).days > window_days:
                continue
            url = entry.get("url") or ""
            org_title = m.get("title", slug)
            country = entry.get("country") or m.get("country")
            concepts = [c for c in (m.get("concepts") or []) if isinstance(c, str)]
            org_ref = {"slug": slug, "title": org_title}

            key = (d, url) if url else None
            if not is_democracy_related(m, entry):
                if key:
                    held.append((key, org_ref, country, concepts, tier))
                continue
            if key and key in by_key:
                _merge_cohost(by_key[key], org_ref, country, concepts, tier)
                continue

            title = entry.get("title", "Untitled")
            href, archive_url, url_status = _link_for(url, entry.get("quote"), archive_info)
            item = {
                "id": news_guid(d, url, slug, title),
                "date": d,
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
    for key, org_ref, country, concepts, tier in held:
        if key in by_key:
            _merge_cohost(by_key[key], org_ref, country, concepts, tier)
    items.sort(key=lambda i: (-i["date"].toordinal(), i["notable"] is not True, i["org_title"].lower()))
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
    return item["href"] or _abs(site_url, f"/organisations/{item['org_slug']}/")


def _item_title(item):
    # A feed reader shows this line with nothing around it, so it has to say
    # whose news it is — the same "<org>: <title>" shape the calendar's .ics
    # SUMMARY uses. A merged item names its first org; the title of a
    # co-hosted event already names the other.
    return f"{item['org_title']}: {item['title']}"


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
        tail += f' · <a href="{esc(item["href"])}">Source</a>'
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
        ET.SubElement(el, "pubDate").text = _pub_date(item["date"])
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
        feed_items.append({
            "id": item["id"],
            "url": _item_link(item, site_url),
            "title": _item_title(item),
            "content_html": item_html(item, site_url, concept_titles),
            "summary": item.get("notable_reason") or item["title"],
            "date_published": datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat(),
            "tags": _item_categories(item, concept_titles),
            "authors": [{"name": o["title"], "url": _abs(site_url, f"/organisations/{o['slug']}/")}
                        for o in item["orgs"]],
            "_dod": {
                "date": d.isoformat(),
                "end_date": item["end_date"].isoformat() if item.get("end_date") else None,
                "event_title": item["title"],
                "tier": "major" if item["notable"] is True else "medium",
                "notable_reason": item.get("notable_reason"),
                "orgs": [o["slug"] for o in item["orgs"]],
                "countries": item["countries"],
                "concepts": item["concepts"],
                "type": item.get("type"),
                "source_url": item["url"] or None,
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


def _window_phrase():
    return "year" if NEWS_WINDOW_DAYS == 365 else f"{NEWS_WINDOW_DAYS} days"


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
_feeds: dict = {"countries": [], "topics": []}
_concept_titles: dict = {}


def on_pre_build(config):
    if frontmatter is None:
        return
    orgs = load_orgs()
    concept_titles = load_concept_titles()
    items = collect_news(orgs, date.today(), archive_info=_tf.load_archive_info())
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
    env.globals["news_feeds"] = _feeds
    env.globals["news_window_days"] = NEWS_WINDOW_DAYS
    env.filters["topic_label"] = lambda slug: topic_label(slug, _concept_titles)
    return env
