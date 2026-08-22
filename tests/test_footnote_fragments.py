#!/usr/bin/env python3
"""Regression tests for hooks/footnote_fragments.py's on_page_content():
the #:~:text= fragment injection, the additive Wayback archive-box link,
and — new — the Wikipedia-style primary-link swap once a citation's
url_status is recorded as dead/unfit (see internal-heartbeat/
2026-08-22-citation-archival-design-decisions.md).

Offline — no network, no real evidence cache touched. The archive-info
cache is monkeypatched per test via a temp JSON file. Run with:

    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import footnote_fragments as ff  # noqa: E402
import text_fragment as tf  # noqa: E402


class FakePage:
    pass


class OnPageContentTests(unittest.TestCase):

    def setUp(self):
        self._orig_cache = ff._archive_info_cache
        self._orig_path = tf.ARCHIVE_CACHE_PATH
        self.addCleanup(self._restore)

    def _restore(self):
        ff._archive_info_cache = self._orig_cache
        tf.ARCHIVE_CACHE_PATH = self._orig_path

    def _set_archive_cache(self, data):
        with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        tf.ARCHIVE_CACHE_PATH = path
        ff._archive_info_cache = None  # force a reload from the new path

    def _render(self, markdown_src, html_src):
        page = FakePage()
        ff.on_page_markdown(markdown_src, page, None, None)
        return ff.on_page_content(html_src, page, None, None)

    MARKDOWN = ('[^a]: "quoted text here," [Title](https://example.org/x), '
                'Source.')
    HTML = '<li id="fn:a"><a href="https://example.org/x">Title</a></li>'
    ARCHIVE_URL = "https://web.archive.org/web/20260101000000/https://example.org/x"

    def test_no_archive_info_only_adds_fragment(self):
        self._set_archive_cache({})
        result = self._render(self.MARKDOWN, self.HTML)
        self.assertIn('href="https://example.org/x#:~:text=', result)
        self.assertNotIn("🗃️", result)
        self.assertNotIn("no longer live", result)

    def test_live_archive_is_additive_not_a_swap(self):
        self._set_archive_cache({
            "https://example.org/x": {"archive_url": self.ARCHIVE_URL},
        })
        result = self._render(self.MARKDOWN, self.HTML)
        # Original link keeps its fragment and stays the primary link.
        self.assertIn('<a href="https://example.org/x#:~:text=', result)
        # Archive link is present, additive, unmodified (no fragment logic
        # applied to it in the live case).
        self.assertIn(f'<a href="{self.ARCHIVE_URL}"', result)
        self.assertIn("🗃️", result)
        self.assertNotIn("no longer live", result)

    def test_dead_status_swaps_primary_link_to_archive(self):
        self._set_archive_cache({
            "https://example.org/x": {
                "archive_url": self.ARCHIVE_URL,
                "url_status": "dead",
            },
        })
        result = self._render(self.MARKDOWN, self.HTML)
        # The clickable <a> now points at the archive (with its own
        # #:~:text= fragment, since that's the page verification would
        # actually target once the original is known dead).
        self.assertIn(f'<a href="{self.ARCHIVE_URL}#:~:text=', result)
        # The original url no longer carries a #:~:text= fragment (nothing
        # verified against it as primary), and appears only inside the
        # demoted trailer, not as the link immediately following <li>.
        self.assertNotIn('<a href="https://example.org/x#:~:text=', result)
        self.assertTrue(result.index(self.ARCHIVE_URL) < result.index(
            'https://example.org/x"'))
        # Original is demoted to a plainly-labeled trailer.
        self.assertIn("no longer live", result)
        self.assertIn("https://example.org/x", result)
        # No separate additive 🗃️ box — the archive link isn't second-class
        # here, it's the promoted primary link.
        self.assertNotIn("🗃️", result)

    def test_unfit_status_also_swaps(self):
        self._set_archive_cache({
            "https://example.org/x": {
                "archive_url": self.ARCHIVE_URL,
                "url_status": "unfit",
            },
        })
        result = self._render(self.MARKDOWN, self.HTML)
        self.assertIn(f'<a href="{self.ARCHIVE_URL}#:~:text=', result)
        self.assertIn("no longer live", result)

    def test_url_status_without_archive_url_does_not_swap(self):
        # Flagged dead, but no snapshot recorded yet — nothing to swap to,
        # so behave exactly like the no-archive-info case.
        self._set_archive_cache({
            "https://example.org/x": {"url_status": "dead"},
        })
        result = self._render(self.MARKDOWN, self.HTML)
        self.assertIn('<a href="https://example.org/x#:~:text=', result)
        self.assertNotIn("no longer live", result)
        self.assertNotIn("🗃️", result)

    def test_live_status_behaves_like_no_status(self):
        self._set_archive_cache({
            "https://example.org/x": {
                "archive_url": self.ARCHIVE_URL,
                "url_status": "live",
            },
        })
        result = self._render(self.MARKDOWN, self.HTML)
        self.assertIn('<a href="https://example.org/x#:~:text=', result)
        self.assertIn("🗃️", result)
        self.assertNotIn("no longer live", result)


if __name__ == "__main__":
    unittest.main()
