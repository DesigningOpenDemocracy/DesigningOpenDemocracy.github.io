#!/usr/bin/env python3
"""Tests for hooks/podcast_player.py and util/sync_podcast.py's pure parts."""

import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "hooks"))
sys.path.insert(0, os.path.join(HERE, "..", "util"))
import podcast_player as pp  # noqa: E402
import sync_podcast as sp  # noqa: E402


class FakeFile:
    def __init__(self, src_path):
        self.src_path = src_path


class FakePage:
    def __init__(self, meta, src_path="blog/posts/test.md"):
        self.file = FakeFile(src_path)
        self.meta = meta


def render(markdown, meta, **kw):
    return pp.on_page_markdown(markdown, page=FakePage(meta, **kw), config={}, files=[])


EP = {"title": "Ep", "audio": "https://example.org/a.mp3?x=1&y=2", "duration": "27 min"}


class PlayerTests(unittest.TestCase):
    def test_goes_after_more_marker_not_into_excerpt(self):
        out = render("Intro.\n\n<!-- more -->\n\nBody.", {"podcast": [EP]})
        intro, body = out.split("<!-- more -->")
        self.assertNotIn("<audio", intro)
        self.assertIn("<audio", body)

    def test_top_of_post_without_marker(self):
        self.assertTrue(render("Body.", {"podcast": EP}).lstrip().startswith('<div class="podcast-card">'))

    def test_never_preloads_and_escapes_audio_url(self):
        out = render("Body.", {"podcast": [EP]})
        self.assertIn('preload="none"', out)
        self.assertIn("a.mp3?x=1&amp;y=2", out)
        self.assertNotIn("a.mp3?x=1&y=2", out)

    def test_part_titles_only_shown_for_multi_episode_posts(self):
        one = render("Body.", {"podcast": [EP]})
        two = render("Body.", {"podcast": [EP, dict(EP, title="Part 2")]})
        self.assertNotIn("podcast-card-title", one)
        self.assertEqual(two.count("<audio"), 2)
        self.assertIn("Part 2", two)

    def test_ignored_outside_blog_posts_or_without_audio(self):
        self.assertEqual(render("Body.", {"podcast": [EP]}, src_path="concepts/x.md"), "Body.")
        self.assertEqual(render("Body.", {"podcast": [{"title": "no audio"}]}), "Body.")
        self.assertEqual(render("Body.", {}), "Body.")

    def test_clip_plays_a_span_and_download_stays_whole(self):
        out = render("Body.", {"podcast": [dict(EP, start="2:53", end=322)]})
        self.assertIn('a.mp3?x=1&amp;y=2#t=173,322"', out)
        self.assertIn('<a href="https://example.org/a.mp3?x=1&amp;y=2">Download MP3', out)
        self.assertIn("Clip: 2:53–5:22", out)
        self.assertIn("podcast-card-title", out)  # a clip names itself even alone

    def test_unreadable_start_plays_whole_episode(self):
        out = render("Body.", {"podcast": [dict(EP, start="soon")]})
        self.assertNotIn("#t=", out)

    def test_marker_places_card(self):
        out = render("Intro.\n\n<!-- more -->\n\nA\n\n<!-- podcast-player -->\n\nB", {"podcast": [EP]})
        self.assertLess(out.index("\nA\n"), out.index("<audio"))
        self.assertLess(out.index("<audio"), out.index("\nB"))
        self.assertNotIn("podcast-player -->", out)


FEED = b"""<?xml version="1.0"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
<item><title>Newer</title><pubDate>Tue, 20 Oct 2026 11:37:27 GMT</pubDate>
<link>https://example.org/newer</link><enclosure url="https://example.org/n.mp3" type="audio/mpeg"/>
<itunes:duration>01:43:17</itunes:duration></item>
<item><title>Older</title><pubDate>Mon, 23 Dec 2019 10:00:00 GMT</pubDate>
<enclosure url="https://example.org/o.mp3" type="audio/mpeg"/><itunes:duration>1650</itunes:duration></item>
<item><title>No audio</title><pubDate>Mon, 23 Dec 2019 10:00:00 GMT</pubDate></item>
</channel></rss>"""


class SyncTests(unittest.TestCase):
    def test_parse_feed_oldest_first_skips_items_without_audio(self):
        eps = sp.parse_feed(FEED)
        self.assertEqual([e["title"] for e in eps], ["Older", "Newer"])
        self.assertEqual(eps[1]["duration"], "1 hr 43 min")
        self.assertEqual(eps[0]["duration"], "28 min")

    def test_human_duration(self):
        self.assertEqual(sp.human_duration("59:50"), "1 hr")
        self.assertEqual(sp.human_duration("00:20"), "1 min")

    def test_block_inserted_before_closing_fence_and_parses_back(self):
        import frontmatter
        text = "---\ntitle: X\n---\n\nBody --- with dashes\n"
        out = sp.insert_block(text, sp.yaml_block(sp.parse_feed(FEED)))
        meta = frontmatter.loads(out).metadata
        self.assertEqual(meta["title"], "X")
        self.assertEqual([e["audio"] for e in meta["podcast"]],
                         ["https://example.org/o.mp3", "https://example.org/n.mp3"])
        self.assertTrue(out.endswith("\n---\n\nBody --- with dashes\n"))
        render_out = render("Body.", meta)
        self.assertEqual(render_out.count("<audio"), 2)


if __name__ == "__main__":
    unittest.main()
