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

import hashlib
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


class _FootnoteFragmentsTestBase(unittest.TestCase):
    """Shared setup for both test classes below — not itself collected by
    unittest (no test_* methods), so subclassing it doesn't duplicate
    cases the way subclassing OnPageContentTests directly would."""

    def setUp(self):
        self._orig_cache = ff._archive_info_cache
        self._orig_state = ff._state_cache
        self._orig_path = tf.STATE_PATH
        self.addCleanup(self._restore)

    def _restore(self):
        ff._archive_info_cache = self._orig_cache
        ff._state_cache = self._orig_state
        tf.STATE_PATH = self._orig_path

    def _set_archive_cache(self, data):
        with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        tf.STATE_PATH = path
        ff._archive_info_cache = None  # force a reload from the new path
        ff._state_cache = None  # both caches read the same underlying file

    def _render(self, markdown_src, html_src):
        page = FakePage()
        ff.on_page_markdown(markdown_src, page, None, None)
        return ff.on_page_content(html_src, page, None, None)


class OnPageContentTests(_FootnoteFragmentsTestBase):

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


class ProofBadgeTests(_FootnoteFragmentsTestBase):
    """The two "traffic light" badges added 2026-08-24: a grey 'Citation
    only' pill for a footnote with no verbatim quote to check, and a red
    '⚠ Quote drifted' warning for a quoted footnote whose stored
    verification verdict is a MISMATCH. Deliberately separate signals —
    see hooks/footnote_fragments.py's module docstring."""

    QUOTED_MD = ('[^a]: "quoted text here," [Title](https://example.org/x), '
                 'Source.')
    QUOTED_HTML = '<li id="fn:a"><a href="https://example.org/x">Title</a></li>'

    CITATION_ONLY_MD = ('[^a]: [Title](https://example.org/x), Source, '
                         'no quote. <!-- unquoted: legacy: n/a -->')
    CITATION_ONLY_HTML = QUOTED_HTML

    @staticmethod
    def _ev_key():
        return hashlib.sha256(tf.normalize_ws("quoted text here,").encode()).hexdigest()

    def test_citation_only_footnote_gets_grey_badge(self):
        self._set_archive_cache({})
        result = self._render(self.CITATION_ONLY_MD, self.CITATION_ONLY_HTML)
        self.assertIn("proof-citation", result)
        self.assertIn("Citation only", result)
        self.assertNotIn("Quote drifted", result)

    def test_quoted_footnote_with_no_recorded_verdict_gets_no_badge(self):
        self._set_archive_cache({})
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertNotIn("proof-citation", result)
        self.assertNotIn("Quote drifted", result)

    def test_quoted_footnote_with_match_gets_no_badge(self):
        self._set_archive_cache({
            "https://example.org/x": {"evidence": [{"id": self._ev_key(), "verified": True}]},
        })
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertNotIn("proof-citation", result)
        self.assertNotIn("Quote drifted", result)

    def test_quoted_footnote_with_mismatch_gets_warning_badge(self):
        self._set_archive_cache({
            "https://example.org/x": {"evidence": [{"id": self._ev_key(), "verified": False}]},
        })
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertIn("⚠ Quote drifted", result)
        self.assertNotIn("proof-citation", result)

    def test_manual_verified_false_also_warns_when_no_automated_verdict(self):
        self._set_archive_cache({
            "https://example.org/x": {"evidence": [{"id": self._ev_key(), "manual_verified": False}]},
        })
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertIn("⚠ Quote drifted", result)

    def test_automated_verdict_wins_over_stale_manual_verdict(self):
        self._set_archive_cache({
            "https://example.org/x": {"evidence": [
                {"id": self._ev_key(), "verified": True, "manual_verified": False},
            ]},
        })
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertNotIn("Quote drifted", result)

    def test_multi_source_footnote_is_treated_as_citation_only(self):
        md = ('[^a]: [First](https://example.org/a) and '
              '[Second](https://example.org/b), two sources. '
              '<!-- unquoted: multi-source: two links -->')
        html = ('<li id="fn:a"><a href="https://example.org/a">First</a> and '
                '<a href="https://example.org/b">Second</a></li>')
        self._set_archive_cache({})
        result = self._render(md, html)
        self.assertIn("proof-citation", result)

    def test_quoted_footnote_gets_coins_span_with_evidence_pointer(self):
        self._set_archive_cache({})
        result = self._render(self.QUOTED_MD, self.QUOTED_HTML)
        self.assertIn('class="Z3988"', result)
        self.assertIn("rft.atitle=Title", result)
        self.assertIn(
            "evidence_sha256=" + self._ev_key()[:12], result)

    def test_citation_only_footnote_gets_no_coins_span(self):
        self._set_archive_cache({})
        result = self._render(self.CITATION_ONLY_MD, self.CITATION_ONLY_HTML)
        self.assertNotIn("Z3988", result)


if __name__ == "__main__":
    unittest.main()
