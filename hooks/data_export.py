"""
data_export.py — MkDocs hook: export org data as CSV, JSON, GeoJSON, KML at build time

Generates docs/data/ during on_pre_build so files are served as static assets:
  /data/organisations.csv      — flat table, all orgs
  /data/organisations.json     — structured, concepts as arrays
  /data/organisations.geojson  — orgs with coordinates (FeatureCollection)
  /data/organisations.kml      — orgs with coordinates, colour-coded by status
  /data/org-concepts.csv       — edge list for network / graph analysis
"""

import csv
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from activity_selector import PRIORITY, STALENESS_DAYS, _parse_date

try:
    import frontmatter
except ImportError:
    frontmatter = None

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
ORGS_DIR = os.path.join(DOCS_DIR, "organisations")
OUT_DIR = os.path.join(DOCS_DIR, "data")
SKIP_FILES = {"organisations.md"}


def load_orgs():
    orgs = []
    for path in sorted(glob.glob(os.path.join(ORGS_DIR, "*.md"))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        post = frontmatter.load(path)
        m = post.metadata
        slug = os.path.basename(path)[:-3]
        loc = m.get("location") or {}
        orgs.append({
            "slug": slug,
            "title": m.get("title", slug),
            "status": m.get("status", ""),
            "country": m.get("country", ""),
            "type": m.get("type", ""),
            "website": m.get("website", ""),
            "summary": (m.get("summary") or "").strip().strip('"'),
            "concepts": m.get("concepts") or [],
            "latitude": loc.get("latitude", ""),
            "longitude": loc.get("longitude", ""),
            "location_name": loc.get("name", ""),
            "last_checked": m.get("last_checked", ""),
            "rss_feed": m.get("rss_feed", ""),
            "activity": m.get("activity") or {},
        })
    return orgs


def _best_activity(activity_dict):
    """Return (date_str, method) of the best activity entry, mirroring activity_selector logic."""
    today = datetime.date.today()
    for source in PRIORITY:
        entry = activity_dict.get(source)
        if not entry:
            continue
        d = _parse_date(entry.get("date"))
        if d and (today - d).days <= STALENESS_DAYS.get(source, 365):
            return str(d), source
    # fallback: most recent
    best_date, best_source = None, None
    for source in PRIORITY:
        entry = activity_dict.get(source)
        if not entry:
            continue
        d = _parse_date(entry.get("date"))
        if d and (best_date is None or d > best_date):
            best_date, best_source = d, source
    return (str(best_date), best_source) if best_date else ("", "")


def write_orgs_csv(orgs):
    path = os.path.join(OUT_DIR, "organisations.csv")
    fields = ["slug", "title", "status", "country", "type", "website",
              "summary", "concepts", "latitude", "longitude", "location_name",
              "rss_feed", "activity_date", "activity_method", "last_checked"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for o in orgs:
            row = dict(o)
            row["concepts"] = ",".join(o["concepts"])
            row["activity_date"], row["activity_method"] = _best_activity(o["activity"])
            w.writerow(row)


def write_edge_list_csv(orgs):
    path = os.path.join(OUT_DIR, "org-concepts.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["org_slug", "concept_slug"])
        for o in orgs:
            for c in o["concepts"]:
                w.writerow([o["slug"], c])


def write_orgs_json(orgs, meta):
    path = os.path.join(OUT_DIR, "organisations.json")
    records = []
    for o in orgs:
        r = {k: v for k, v in o.items()
             if k not in ("latitude", "longitude", "location_name")}
        if o["latitude"] != "":
            r["location"] = {
                "latitude": o["latitude"],
                "longitude": o["longitude"],
                "name": o["location_name"],
            }
        else:
            r["location"] = None
        act_date, act_method = _best_activity(o["activity"])
        r["activity_date"] = act_date
        r["activity_method"] = act_method
        records.append(r)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"metadata": meta, "organisations": records}, f,
                  ensure_ascii=False, indent=2)


def write_orgs_geojson(orgs, meta):
    path = os.path.join(OUT_DIR, "organisations.geojson")
    features = []
    for o in orgs:
        if o["latitude"] == "" or o["longitude"] == "":
            continue
        props = {k: v for k, v in o.items()
                 if k not in ("latitude", "longitude", "location_name", "title")}
        props["name"] = o["title"]
        props["location_name"] = o["location_name"]
        concepts_str = ", ".join(o["concepts"]) if o["concepts"] else "—"
        website = o["website"]
        website_html = f'<a href="{website}">{website}</a>' if website else "—"
        props["description"] = (
            f"<b>Status:</b> {o['status']}<br>"
            f"<b>Country:</b> {o['country']}<br>"
            f"<b>Type:</b> {o['type']}<br>"
            f"<b>Website:</b> {website_html}<br>"
            f"<b>Concepts:</b> {concepts_str}<br><br>"
            f"{o['summary']}"
        )
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [o["longitude"], o["latitude"]],
            },
            "properties": props,
        })
    fc = {"type": "FeatureCollection", "metadata": meta, "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)


def _kml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# KML colours: AABBGGRR (alpha, blue, green, red)
KML_STYLES = {
    "active":       ("ff00bb00", "Active"),
    "inactive":     ("ff888888", "Inactive"),
    "deregistered": ("ff0000cc", "Deregistered"),
}
KML_ICON = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"


def write_orgs_kml(orgs, meta):
    path = os.path.join(OUT_DIR, "organisations.kml")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        '  <name>Democracy Landscape</name>',
        f'  <description>Designing Open Democracy — {meta["org_count"]} organisations'
        f' — generated {meta["generated_at"]}</description>',
    ]

    for status, (colour, label) in KML_STYLES.items():
        lines += [
            f'  <Style id="{status}">',
            '    <IconStyle>',
            f'      <color>{colour}</color>',
            '      <scale>1.0</scale>',
            f'      <Icon><href>{KML_ICON}</href></Icon>',
            '    </IconStyle>',
            '  </Style>',
        ]

    for o in orgs:
        if o["latitude"] == "" or o["longitude"] == "":
            continue
        status = o["status"] if o["status"] in KML_STYLES else "inactive"
        concepts_str = _kml_escape(", ".join(o["concepts"])) if o["concepts"] else "—"
        website = o["website"]
        website_html = (f'<a href="{_kml_escape(website)}">{_kml_escape(website)}</a>'
                        if website else "—")
        description = (
            f"<b>Status:</b> {_kml_escape(o['status'])}<br>"
            f"<b>Country:</b> {_kml_escape(o['country'])}<br>"
            f"<b>Type:</b> {_kml_escape(o['type'])}<br>"
            f"<b>Website:</b> {website_html}<br>"
            f"<b>Concepts:</b> {concepts_str}<br><br>"
            f"{_kml_escape(o['summary'])}"
        )
        lines += [
            '  <Placemark>',
            f'    <name>{_kml_escape(o["title"])}</name>',
            f'    <description><![CDATA[{description}]]></description>',
            f'    <styleUrl>#{status}</styleUrl>',
            '    <Point>',
            f'      <coordinates>{o["longitude"]},{o["latitude"]},0</coordinates>',
            '    </Point>',
            '  </Placemark>',
        ]

    lines += ['</Document>', '</kml>']
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def on_pre_build(config):
    if frontmatter is None:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    orgs = load_orgs()
    site_url = (config.get("site_url") or "").rstrip("/")
    meta = {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": site_url or "https://designingopendemocracy.com",
        "org_count": len(orgs),
    }
    write_orgs_csv(orgs)
    write_edge_list_csv(orgs)
    write_orgs_json(orgs, meta)
    write_orgs_geojson(orgs, meta)
    write_orgs_kml(orgs, meta)
