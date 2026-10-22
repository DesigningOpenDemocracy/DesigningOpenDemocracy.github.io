#!/usr/bin/env python3
"""
sync_podcast.py — link blog posts to their episodes in the DOD podcast feed.

The network half of the podcast: frontmatter field (see CLAUDE.md's
"Convention — podcast"). hooks/podcast_player.py renders the player at build
time and never fetches anything; this script reads the Anchor feed once and
writes each episode's MP3 address, duration and episode page into the post's
own frontmatter, which is all the build reads.

Two modes:

  python util/sync_podcast.py
      Report: every episode in the feed, and which post (if any) already
      plays it. An episode with no post is a new release waiting to be
      linked. Writes nothing.

  python util/sync_podcast.py --post 2020-03-20-podcast --episode Isegoria
      Write podcast: into that post for the episode(s) whose title contains
      the given text (case-insensitive; an exact title beats a partial
      match). --episode is repeatable, for a
      talk released in parts; the episodes are written in feed order,
      oldest first. Refuses if the post already has podcast: set, and
      refuses if a --episode matches no episode or more than one.

The field is inserted as raw text just before the closing '---', so the rest
of the post's frontmatter is left byte-for-byte as it was.
"""

import argparse
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import frontmatter

FEED_URL = 'https://anchor.fm/s/39cd9860/podcast/rss'
POSTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'blog', 'posts')
USER_AGENT = 'DOD-Bot/1.0 (+https://www.designingopendemocracy.com/bot/)'
ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'


def fetch_feed(source):
    if os.path.exists(source):
        with open(source, 'rb') as f:
            return f.read()
    req = urllib.request.Request(source, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def human_duration(raw):
    """'01:43:17' / '43:17' / '6197' -> '1 hr 43 min' / '43 min'."""
    if not raw:
        return ''
    try:
        parts = [int(p) for p in raw.strip().split(':')]
    except ValueError:
        return raw.strip()
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    hours, mins = secs // 3600, round(secs % 3600 / 60)
    if mins == 60:
        hours, mins = hours + 1, 0
    if hours:
        return f'{hours} hr {mins} min' if mins else f'{hours} hr'
    return f'{max(mins, 1)} min'


def parse_feed(data):
    """Episodes, oldest first: {title, date, audio, duration, url}."""
    root = ET.fromstring(data)
    eps = []
    for item in root.iter('item'):
        enc = item.find('enclosure')
        if enc is None or not enc.get('url'):
            continue
        pub = item.findtext('pubDate')
        eps.append({
            'title': (item.findtext('title') or '').strip(),
            'date': parsedate_to_datetime(pub).date().isoformat() if pub else '',
            'audio': enc.get('url'),
            'duration': human_duration(item.findtext(ITUNES + 'duration')),
            'url': (item.findtext('link') or '').strip(),
        })
    eps.sort(key=lambda e: e['date'])
    return eps


def post_path(slug):
    name = slug if slug.endswith('.md') else slug + '.md'
    return os.path.join(POSTS_DIR, os.path.basename(name))


def linked_audio():
    """audio URL -> post filename, for every post with podcast: set."""
    found = {}
    for name in sorted(os.listdir(POSTS_DIR)):
        if not name.endswith('.md'):
            continue
        meta = frontmatter.load(os.path.join(POSTS_DIR, name)).metadata
        value = meta.get('podcast')
        for ep in value if isinstance(value, list) else [value]:
            if isinstance(ep, dict) and ep.get('audio'):
                found[ep['audio']] = name
    return found


def yaml_block(eps):
    lines = ['podcast:']
    for ep in eps:
        lines.append(f'  - title: {json.dumps(ep["title"], ensure_ascii=False)}')
        lines.append(f'    audio: {json.dumps(ep["audio"])}')
        if ep['duration']:
            lines.append(f'    duration: {json.dumps(ep["duration"])}')
        if ep['url']:
            lines.append(f'    url: {json.dumps(ep["url"])}')
    return '\n'.join(lines) + '\n'


def insert_block(text, block):
    """Insert block before the frontmatter's closing '---'."""
    if not text.startswith('---\n'):
        raise ValueError('no frontmatter')
    end = text.find('\n---\n', 3)
    if end == -1:
        raise ValueError('unterminated frontmatter')
    return text[:end + 1] + block + text[end + 1:]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--feed', default=FEED_URL, help='feed URL or local file')
    ap.add_argument('--post', help='post filename (with or without .md)')
    ap.add_argument('--episode', action='append', default=[],
                    help='text in the episode title (repeatable)')
    args = ap.parse_args()

    eps = parse_feed(fetch_feed(args.feed))

    if not args.post:
        linked = linked_audio()
        unlinked = 0
        for ep in eps:
            post = linked.get(ep['audio'])
            if not post:
                unlinked += 1
            print(f'{ep["date"]}  {ep["title"][:70]:<70}  {post or "NOT LINKED"}')
        print(f'\n{len(eps)} episodes, {unlinked} not linked from any post.')
        return 0

    if not args.episode:
        ap.error('--post needs at least one --episode')
    chosen = []
    for needle in args.episode:
        hits = [e for e in eps if needle.lower() in e['title'].lower()]
        # An exact title wins, or a part-one title could never be picked
        # when a "(Bonus Content) <same title>" episode also exists.
        exact = [e for e in hits if e['title'].lower() == needle.lower()]
        hits = exact or hits
        if len(hits) != 1:
            names = ', '.join(repr(e['title']) for e in hits) or 'none'
            print(f'--episode {needle!r} matched {len(hits)} episodes ({names})', file=sys.stderr)
            return 1
        if hits[0] not in chosen:
            chosen.append(hits[0])
    chosen.sort(key=lambda e: e['date'])

    path = post_path(args.post)
    if not os.path.exists(path):
        print(f'no such post: {path}', file=sys.stderr)
        return 1
    if frontmatter.load(path).metadata.get('podcast'):
        print(f'{os.path.basename(path)} already has podcast: set; edit it by hand', file=sys.stderr)
        return 1
    with open(path, encoding='utf-8') as f:
        text = f.read()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(insert_block(text, yaml_block(chosen)))
    for ep in chosen:
        print(f'{os.path.basename(path)}: linked {ep["title"]!r}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
