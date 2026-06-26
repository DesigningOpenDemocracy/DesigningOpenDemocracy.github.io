#!/usr/bin/env python3
"""
add_video_reference.py — Add a YouTube video to docs/research/video-references.md

Given a YouTube URL, looks up the title and channel via YouTube's oEmbed
endpoint (no API key required), downloads a local copy of the thumbnail to
docs/assets/blog/, and appends a row to the "Watch list" table in
video-references.md.

oEmbed doesn't expose the publish date or a topic summary, so those are
asked for interactively (topic) or left blank for manual fill-in (date).

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
    for variant in ("maxresdefault", "hqdefault"):
        thumb_url = f"https://i.ytimg.com/vi/{video_id}/{variant}.jpg"
        resp = requests.get(thumb_url, timeout=10)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            with open(dest, "wb") as f:
                f.write(resp.content)
            return filename
    return None


def append_row(date_str, video_id, title, channel, topic, watch_url):
    with open(VIDEO_REFS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    row = f"| {date_str} | [{title}]({watch_url}) | {channel} | {topic} |\n"

    marker = "| Video published | Video | Creator / Channel | Topic |\n|---|---|---|---|\n"
    idx = content.find(marker)
    if idx == -1:
        print("Could not find the Watch list table header — paste this row in manually:")
        print(row)
        return False

    insert_at = idx + len(marker)
    content = content[:insert_at] + row + content[insert_at:]

    with open(VIDEO_REFS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def append_thumbnail_embed(slug, filename, watch_url, title):
    if not filename:
        return
    with open(VIDEO_REFS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    marker = "## Possible future: a recommendation feed"
    embed = (
        f'<a href="{watch_url}">'
        f'<img src="../assets/blog/{filename}" alt="Thumbnail: {title}" width="280"></a>\n'
    )
    idx = content.find(marker)
    if idx == -1:
        return
    content = content[:idx] + embed + "\n" + content[idx:]
    with open(VIDEO_REFS_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Add a YouTube video to the watch list log")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--topic", default=None, help="One-line topic summary (asked interactively if omitted)")
    parser.add_argument("--published", default=None, help="Video publish date, YYYY-MM-DD (left blank if omitted)")
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

    added = append_row(date_str, video_id, title, channel, topic, watch_url)
    if added:
        append_thumbnail_embed(slug, filename, watch_url, title)
        print(f"  Row added to {os.path.relpath(VIDEO_REFS_PATH)}")
        if date_str == "TBD":
            print("  Note: publish date left as 'TBD' — fill it in manually, or re-run with --published YYYY-MM-DD")


if __name__ == "__main__":
    main()
