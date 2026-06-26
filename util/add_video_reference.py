#!/usr/bin/env python3
"""
add_video_reference.py — Add a YouTube video to docs/research/video-references.md

Given a YouTube URL, looks up the title and channel via YouTube's oEmbed
endpoint (no API key required), downloads a local copy of the thumbnail to
docs/assets/blog/, and inserts a row into the "Watch list" table in
video-references.md — sorted newest-published first — along with a
matching thumbnail embed in the same order.

oEmbed doesn't expose the publish date or a topic summary, so those are
asked for interactively (topic) or left as "TBD" for manual fill-in (date).
Entries with an unknown ("TBD") date sort to the top.

Usage:
    python util/add_video_reference.py "https://www.youtube.com/watch?v=W5JEJ_L_Zjg"
    python util/add_video_reference.py "https://youtu.be/W5JEJ_L_Zjg" --topic "Anarchist critique of democracy"
    python util/add_video_reference.py "https://www.youtube.com/watch?v=W5JEJ_L_Zjg" --published 2026-06-18

Requirements: requests (util/requirements.txt)
"""

import argparse
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse, parse_qs

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
VIDEO_REFS_PATH = os.path.join(DOCS_DIR, "research", "video-references.md")
THUMB_DIR = os.path.join(DOCS_DIR, "assets", "blog")
TODAY = date.today().isoformat()

TABLE_HEADER = "| Video published | Video | Creator / Channel | Topic |\n|---|---|---|---|\n"
ROW_RE = re.compile(r"^\| (\S+) \| \[(.*?)\]\((\S+?)\) \| (.*?) \| (.*?) \|$")
THUMB_RE = re.compile(r'^<a href="(\S+?)"><img src="(\S+?)" alt="Thumbnail: (.*?)" width="280"></a>$')


def extract_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    if parsed.hostname and "youtube.com" in parsed.hostname:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[-1]
    return None


def fetch_oembed(url):
    resp = requests.get(
        "https://www.youtube.com/oembed",
        params={"url": url, "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def slugify(text):
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]


def download_thumbnail(video_id, slug, date_str):
    filename = f"{date_str}-{slug}-thumb.jpg"
    dest = os.path.join(THUMB_DIR, filename)
    os.makedirs(THUMB_DIR, exist_ok=True)
    # YouTube returns a 200 with a tiny near-blank placeholder image (not a 404)
    # for variants that don't exist for a given video, so filter those out by size.
    MIN_THUMB_BYTES = 5000
    for variant in ("maxresdefault", "hqdefault"):
        thumb_url = f"https://i.ytimg.com/vi/{video_id}/{variant}.jpg"
        resp = requests.get(thumb_url, timeout=10)
        if (
            resp.status_code == 200
            and resp.headers.get("content-type", "").startswith("image")
            and len(resp.content) >= MIN_THUMB_BYTES
        ):
            with open(dest, "wb") as f:
                f.write(resp.content)
            return filename
    return None


def sort_key(date_str):
    # TBD (unknown date) sorts to the top, alongside newest-first ordering.
    return "9999-99-99" if date_str == "TBD" else date_str


def parse_existing_entries(lines):
    entries = []
    for line in lines:
        m = ROW_RE.match(line)
        if m:
            entries.append({
                "date": m.group(1),
                "title": m.group(2),
                "url": m.group(3),
                "channel": m.group(4),
                "topic": m.group(5),
                "thumb_file": None,
            })
    return entries


def parse_existing_thumbs(lines):
    thumbs = {}
    for line in lines:
        m = THUMB_RE.match(line)
        if m:
            thumbs[m.group(1)] = m.group(2).removeprefix("../assets/blog/")
    return thumbs


def render_table(entries):
    rows = [
        f"| {e['date']} | [{e['title']}]({e['url']}) | {e['channel']} | {e['topic']} |"
        for e in entries
    ]
    return TABLE_HEADER + "\n".join(rows) + "\n\n"


def render_thumbs(entries):
    lines = []
    for e in entries:
        if e["thumb_file"]:
            lines.append(
                f'<a href="{e["url"]}"><img src="../assets/blog/{e["thumb_file"]}" '
                f'alt="Thumbnail: {e["title"]}" width="280"></a>'
            )
    return "\n".join(lines) + ("\n" if lines else "")


def update_video_references(new_entry):
    with open(VIDEO_REFS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if TABLE_HEADER not in content:
        print("Could not find the Watch list table header — add this row manually:")
        print(f"| {new_entry['date']} | [{new_entry['title']}]({new_entry['url']}) | "
              f"{new_entry['channel']} | {new_entry['topic']} |")
        return

    before, after = content.split(TABLE_HEADER, 1)
    after_lines = after.split("\n")
    table_lines = []
    for line in after_lines:
        if ROW_RE.match(line):
            table_lines.append(line)
        else:
            break
    rest = "\n".join(after_lines[len(table_lines):]).lstrip("\n")

    entries = parse_existing_entries(table_lines)

    thumb_lines = [l for l in rest.split("\n") if THUMB_RE.match(l)]
    thumbs_by_url = parse_existing_thumbs(thumb_lines)
    for e in entries:
        e["thumb_file"] = thumbs_by_url.get(e["url"])

    entries.append(new_entry)
    entries.sort(key=lambda e: sort_key(e["date"]), reverse=True)

    # Strip old thumbnail block, then re-insert the regenerated one before
    # the "## Possible future" marker.
    rest_no_thumbs = "\n".join(l for l in rest.split("\n") if not THUMB_RE.match(l))

    new_table = render_table(entries)
    new_thumbs = render_thumbs(entries)

    marker = "## Possible future: a recommendation feed"
    if marker in rest_no_thumbs:
        head, tail = rest_no_thumbs.split(marker, 1)
        head = head.rstrip("\n") + "\n\n" + new_thumbs + "\n"
        rest_final = head + marker + tail
    else:
        rest_final = rest_no_thumbs + "\n" + new_thumbs

    content = before + new_table + rest_final
    with open(VIDEO_REFS_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Add a YouTube video to the watch list log")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--topic", default=None, help="One-line topic summary (asked interactively if omitted)")
    parser.add_argument("--published", default=None, help="Video publish date, YYYY-MM-DD (left as TBD if omitted)")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"Could not parse a video ID from: {args.url}")
        sys.exit(1)

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Looking up {watch_url} ...")
    meta = fetch_oembed(watch_url)
    title = meta["title"]
    channel = meta["author_name"]
    print(f"  Title:   {title}")
    print(f"  Channel: {channel}")

    topic = args.topic or input("  Topic (one line): ").strip()
    date_str = args.published or "TBD"

    slug = slugify(title)
    filename = download_thumbnail(video_id, slug, date_str if date_str != "TBD" else TODAY)
    if filename:
        print(f"  Thumbnail saved: docs/assets/blog/{filename}")
    else:
        print("  Warning: could not download a thumbnail.")

    new_entry = {
        "date": date_str,
        "title": title,
        "url": watch_url,
        "channel": channel,
        "topic": topic,
        "thumb_file": filename,
    }
    update_video_references(new_entry)
    print(f"  Inserted into {os.path.relpath(VIDEO_REFS_PATH)}, sorted newest-first")
    if date_str == "TBD":
        print("  Note: publish date left as 'TBD' (sorts to top) — fill it in manually when known")


if __name__ == "__main__":
    main()
