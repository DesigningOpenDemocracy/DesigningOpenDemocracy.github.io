#!/usr/bin/env python3
"""Regression tests for util/fetch_shared_link_previews.py: the
_MetaExtractor HTML parsing, fetch_preview()'s OG/oEmbed preference
logic, description_verifies(), and write_shared_link_preview()'s
never-overwrite-unless-forced / never-write-description-unless-asked
behaviour.

Offline — no real network calls. fetch_preview() and description_verifies()
are exercised against a fake requests session / a monkeypatched
check_fragments._fetch_page_text rather than the network. Run with:

    python -m unittest discover tests
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import fetch_shared_link_previews as fsp  # noqa: E402


class MetaExtractorTests(unittest.TestCase):

    def _parse(self, html_text):
        parser = fsp._MetaExtractor()
        parser.feed(html_text)
        parser.finalize()
        return parser

    def test_extracts_og_tags(self):
        html_text = (
            "<html><head>"
            '<meta property="og:title" content="A Paper">'
            '<meta property="og:description" content="The abstract.">'
            '<meta property="og:image" content="https://example.org/thumb.jpg">'
            "</head><body></body></html>"
        )
        parser = self._parse(html_text)
        self.assertEqual(parser.og.get("title"), "A Paper")
        self.assertEqual(parser.og.get("description"), "The abstract.")
        self.assertEqual(parser.og.get("image"), "https://example.org/thumb.jpg")

    def test_falls_back_to_title_tag_and_meta_description(self):
        html_text = (
            "<html><head><title>Fallback Title</title>"
            '<meta name="description" content="Fallback description.">'
            "</head><body></body></html>"
        )
        parser = self._parse(html_text)
        self.assertIsNone(parser.og.get("title"))
        self.assertEqual(parser.title, "Fallback Title")
        self.assertEqual(parser.meta_description, "Fallback description.")

    def test_finds_oembed_discovery_link(self):
        html_text = (
            "<html><head>"
            '<link rel="alternate" type="application/json+oembed" '
            'href="https://example.org/oembed?url=x">'
            "</head><body></body></html>"
        )
        parser = self._parse(html_text)
        self.assertEqual(parser.oembed_url, "https://example.org/oembed?url=x")

    def test_no_meta_tags_yields_nothing(self):
        parser = self._parse("<html><head></head><body>Hi</body></html>")
        self.assertEqual(parser.og, {})
        self.assertIsNone(parser.meta_description)
        self.assertIsNone(parser.oembed_url)


class _FakeResponse:
    def __init__(self, text="", json_data=None, status_code=200):
        self.text = text
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            resp = mock.Mock(status_code=self.status_code)
            raise requests.HTTPError(response=resp)

    def json(self):
        return self._json


class _FakeSession:
    """Maps exact URLs to canned _FakeResponse objects."""

    def __init__(self, responses):
        self.responses = responses

    def get(self, url, headers=None, timeout=None):
        if url not in self.responses:
            raise AssertionError(f"unexpected fetch: {url}")
        return self.responses[url]


class FetchPreviewTests(unittest.TestCase):

    def test_prefers_og_tags_over_fallbacks(self):
        html_text = (
            "<html><head><title>Fallback</title>"
            '<meta name="description" content="Fallback desc.">'
            '<meta property="og:title" content="OG Title">'
            '<meta property="og:description" content="OG description.">'
            '<meta property="og:image" content="https://example.org/img.jpg">'
            "</head></html>"
        )
        session = _FakeSession({"https://example.org/page": _FakeResponse(html_text)})
        with mock.patch.object(fsp, "robots_allowed", return_value=True):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result["title"], "OG Title")
        self.assertEqual(result["description"], "OG description.")
        self.assertEqual(result["image"], "https://example.org/img.jpg")

    def test_oembed_title_and_thumbnail_override_og(self):
        html_text = (
            "<html><head>"
            '<meta property="og:title" content="OG Title">'
            '<meta property="og:image" content="https://example.org/og.jpg">'
            '<link type="application/json+oembed" href="https://example.org/oembed">'
            "</head></html>"
        )
        session = _FakeSession({
            "https://example.org/page": _FakeResponse(html_text),
            "https://example.org/oembed": _FakeResponse(
                json_data={"title": "oEmbed Title", "thumbnail_url": "https://example.org/thumb.jpg"}
            ),
        })
        with mock.patch.object(fsp, "robots_allowed", return_value=True):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result["title"], "oEmbed Title")
        self.assertEqual(result["image"], "https://example.org/thumb.jpg")

    def test_relative_og_image_resolved_against_page_url(self):
        html_text = '<html><head><meta property="og:image" content="/thumb.jpg"></head></html>'
        session = _FakeSession({"https://example.org/page": _FakeResponse(html_text)})
        with mock.patch.object(fsp, "robots_allowed", return_value=True):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result["image"], "https://example.org/thumb.jpg")

    def test_blocked_status_reported_as_blocked(self):
        session = _FakeSession({"https://example.org/page": _FakeResponse(status_code=403)})
        with mock.patch.object(fsp, "robots_allowed", return_value=True):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result, {"error": "BLOCKED"})

    def test_robots_disallowed_skips_fetch_entirely(self):
        session = _FakeSession({})  # any .get() call would raise AssertionError
        with mock.patch.object(fsp, "robots_allowed", return_value=False):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result, {"error": "ROBOTS_DISALLOWED"})

    def test_broken_oembed_endpoint_does_not_lose_og_fields(self):
        html_text = (
            "<html><head>"
            '<meta property="og:title" content="OG Title">'
            '<link type="application/json+oembed" href="https://example.org/oembed">'
            "</head></html>"
        )
        session = _FakeSession({
            "https://example.org/page": _FakeResponse(html_text),
            "https://example.org/oembed": _FakeResponse(status_code=500),
        })
        with mock.patch.object(fsp, "robots_allowed", return_value=True):
            result = fsp.fetch_preview("https://example.org/page", session=session)
        self.assertEqual(result["title"], "OG Title")  # oEmbed failure doesn't clobber it


class DescriptionVerifiesTests(unittest.TestCase):

    def test_true_when_description_present_in_page_text(self):
        with mock.patch.object(fsp.cf, "_fetch_page_text",
                                return_value=("Some page text with the abstract in it.", None, None)):
            self.assertTrue(fsp.description_verifies("https://x", "the abstract"))

    def test_false_when_description_absent_from_page_text(self):
        with mock.patch.object(fsp.cf, "_fetch_page_text",
                                return_value=("Unrelated page text.", None, None)):
            self.assertFalse(fsp.description_verifies("https://x", "the abstract"))

    def test_false_on_fetch_error(self):
        with mock.patch.object(fsp.cf, "_fetch_page_text",
                                return_value=(None, None, "NETWORK_ERROR")):
            self.assertFalse(fsp.description_verifies("https://x", "the abstract"))


class WriteSharedLinkPreviewTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _make_post(self, name, shared_link_yaml):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "---\ntitle: Test Post\ndate: 2026-01-01\n"
                "authors:\n  - Claude\nshared_link:\n" + shared_link_yaml +
                "---\n\nBody.\n"
            )
        return path

    def test_fills_missing_title_and_image(self):
        path = self._make_post("a.md", "  url: https://example.org/paper\n")
        found = {"title": "Fetched Title", "image": "https://example.org/img.jpg"}
        self.assertTrue(fsp.write_shared_link_preview(path, found))

        import frontmatter
        post = frontmatter.load(path)
        self.assertEqual(post.metadata["shared_link"]["title"], "Fetched Title")
        self.assertEqual(post.metadata["shared_link"]["image"], "https://example.org/img.jpg")

    def test_does_not_overwrite_existing_title_without_force(self):
        path = self._make_post(
            "b.md", "  url: https://example.org/paper\n  title: Manual Title\n")
        found = {"title": "Fetched Title"}
        changed = fsp.write_shared_link_preview(path, found, force=False)
        self.assertFalse(changed)

        import frontmatter
        post = frontmatter.load(path)
        self.assertEqual(post.metadata["shared_link"]["title"], "Manual Title")

    def test_force_overwrites_existing_title(self):
        path = self._make_post(
            "c.md", "  url: https://example.org/paper\n  title: Manual Title\n")
        found = {"title": "Fetched Title"}
        self.assertTrue(fsp.write_shared_link_preview(path, found, force=True))

        import frontmatter
        post = frontmatter.load(path)
        self.assertEqual(post.metadata["shared_link"]["title"], "Fetched Title")

    def test_description_not_written_without_write_description_flag(self):
        path = self._make_post("d.md", "  url: https://example.org/paper\n")
        found = {"description": "The abstract."}
        changed = fsp.write_shared_link_preview(path, found, write_description=False)
        self.assertFalse(changed)

    def test_description_written_when_write_description_flag_set(self):
        path = self._make_post("e.md", "  url: https://example.org/paper\n")
        found = {"description": "The abstract."}
        self.assertTrue(fsp.write_shared_link_preview(path, found, write_description=True))

        import frontmatter
        post = frontmatter.load(path)
        self.assertEqual(post.metadata["shared_link"]["description"], "The abstract.")

    def test_no_shared_link_field_returns_false(self):
        path = os.path.join(self.tmpdir, "f.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: No Link\ndate: 2026-01-01\n---\n\nBody.\n")
        self.assertFalse(fsp.write_shared_link_preview(path, {"title": "X"}))


if __name__ == "__main__":
    unittest.main()
