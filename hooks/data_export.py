"""
data_export.py — MkDocs hook: export org data as CSV, JSON, GeoJSON at build time

Generates docs/data/ during on_pre_build so files are served as static assets:
  /data/organisations.csv      — flat table, all orgs
  /data/organisations.json     — structured, concepts as arrays
  /data/organisations.geojson  — active orgs with coordinates (FeatureCollection)
  /data/org-concepts.csv       — edge list for network / graph analysis
"""

import csv
import datetime
import glob
import json
import os

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
        })
    return orgs


def write_orgs_csv(orgs):
    path = os.path.join(OUT_DIR, "organisations.csv")
    fields = ["slug", "title", "status", "country", "type", "website",
              "summary", "concepts", "latitude", "longitude", "location_name",
              "last_checked"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for o in orgs:
            row = dict(o)
            row["concepts"] = ",".join(o["concepts"])
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
                 if k not in ("latitude", "longitude", "location_name")}
        props["location_name"] = o["location_name"]
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
