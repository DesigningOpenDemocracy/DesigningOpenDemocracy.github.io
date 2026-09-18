#!/usr/bin/env python3
"""Regression tests for hooks/sitemap_extras.py and its sitemap template.

MkDocs builds sitemap.xml from `pages` alone, so the data exports the build
generates (organisations.json, events.json, the calendar feed, llms.txt, ...)
were never listed — reachable only by crawling the pages that link them, not
by a tool acting on a search result. The hook supplies the missing URLs as a
Jinja global and docs/overrides/sitemap.xml emits them.

Two failure modes are worth pinning, because neither one breaks the build:

  - An entry for a file the build didn't produce. Nothing errors; the
    sitemap just advertises a 404 to every crawler that reads it. The hook
    guards this by checking docs_dir, so the "missing file is dropped" case
    is tested directly.
  - The hook and the template disagreeing about the global's name. Renaming
    `sitemap_extra_urls` on one side leaves a sitemap that builds cleanly,
    validates as XML, and silently contains none of the data endpoints —
    the same silent-drop shape tests/test_calendar_export.py pins for
    _load_manual_events(). So the template is rendered here against the
    hook's own output rather than trusting the two to stay in step.

Offline, stdlib-only apart from jinja2 (a MkDocs dependency, already
installed by requirements.txt). Run with:

    python -m unittest discover tests
"""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import sitemap_extras as se  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_DIR = os.path.join(REPO_ROOT, "docs", "overrides")
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def make_docs_dir(tmp, relpaths):
    """Create empty files at `relpaths` under `tmp`, as a built docs_dir would hold."""
    for rel in relpaths:
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("x")
    return tmp


class DataEndpointDeclarationTests(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertEqual(
            len(se.DATA_ENDPOINTS),
            len(set(se.DATA_ENDPOINTS)),
            "a duplicated path would emit the same <loc> twice",
        )

    def test_paths_are_docs_dir_relative(self):
        # A leading slash survives into the URL as '//path', which resolves to
        # a different host entirely for anything parsing it as a URL.
        for rel in se.DATA_ENDPOINTS:
            self.assertFalse(rel.startswith("/"), f"{rel!r} must be relative to docs_dir")
            self.assertFalse(rel.startswith("./"), f"{rel!r} must be a plain relative path")

    def test_issue_endpoints_are_declared(self):
        # The two the original report named specifically.
        self.assertIn("data/organisations.json", se.DATA_ENDPOINTS)
        self.assertIn("data/events.json", se.DATA_ENDPOINTS)


class DataEndpointUrlTests(unittest.TestCase):
    def test_present_files_become_absolute_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_docs_dir(tmp, ["llms.txt", "data/organisations.json"])
            urls = se.data_endpoint_urls(tmp, "http://example.org")
            self.assertEqual(
                urls,
                ["http://example.org/llms.txt", "http://example.org/data/organisations.json"],
            )

    def test_missing_files_are_dropped(self):
        """The whole point of checking disk: never advertise a URL that 404s."""
        with tempfile.TemporaryDirectory() as tmp:
            make_docs_dir(tmp, ["data/events.json"])
            urls = se.data_endpoint_urls(tmp, "http://example.org")
            self.assertEqual(urls, ["http://example.org/data/events.json"])

    def test_empty_docs_dir_yields_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(se.data_endpoint_urls(tmp, "http://example.org"), [])

    def test_a_directory_does_not_count_as_an_endpoint(self):
        # docs/data/events/ is a directory of per-org sync caches sitting right
        # next to data/events.json; isfile() must not confuse the two.
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data", "events.json"))
            self.assertEqual(se.data_endpoint_urls(tmp, "http://example.org"), [])

    def test_trailing_slash_on_site_url_is_not_doubled(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_docs_dir(tmp, ["llms.txt"])
            self.assertEqual(
                se.data_endpoint_urls(tmp, "http://example.org/"),
                ["http://example.org/llms.txt"],
            )

    def test_no_site_url_falls_back_to_root_relative(self):
        # Matches what MkDocs' own entries degrade to (page.abs_url) when a
        # site has no site_url configured.
        with tempfile.TemporaryDirectory() as tmp:
            make_docs_dir(tmp, ["llms.txt"])
            self.assertEqual(se.data_endpoint_urls(tmp, ""), ["/llms.txt"])
            self.assertEqual(se.data_endpoint_urls(tmp, None), ["/llms.txt"])


class FakePage:
    def __init__(self, canonical_url, update_date=None, is_link=False):
        self.canonical_url = canonical_url
        self.abs_url = canonical_url
        self.update_date = update_date
        self.is_link = is_link


class FakeFile:
    def __init__(self, page):
        self.page = page


class TemplateContractTests(unittest.TestCase):
    """The template must actually render what the hook computes."""

    def render(self, pages, extra_urls, include_global=True):
        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=False
        )
        ctx = {"pages": [FakeFile(p) for p in pages]}
        if include_global:
            ctx["sitemap_extra_urls"] = extra_urls
        return env.get_template("sitemap.xml").render(**ctx)

    def locs(self, xml):
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, SITEMAP_NS + "urlset")
        return [e.text for e in root.iter(SITEMAP_NS + "loc")]

    def test_hook_output_reaches_the_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_docs_dir(tmp, list(se.DATA_ENDPOINTS))
            urls = se.data_endpoint_urls(tmp, "http://example.org")
        xml = self.render([FakePage("http://example.org/about/", "2026-09-18")], urls)
        locs = self.locs(xml)
        self.assertIn("http://example.org/about/", locs)
        for url in urls:
            self.assertIn(url, locs)
        self.assertEqual(len(locs), 1 + len(se.DATA_ENDPOINTS))

    def test_pages_still_render_without_the_hook(self):
        """An undefined global must degrade to 'no extras', not to a broken build."""
        xml = self.render([FakePage("http://example.org/about/")], None, include_global=False)
        self.assertEqual(self.locs(xml), ["http://example.org/about/"])

    def test_mkdocs_page_loop_is_preserved(self):
        """The upstream behaviours the copied loop is responsible for."""
        pages = [
            FakePage("http://example.org/a/", "2026-01-02"),
            FakePage("http://example.org/skipped/", is_link=True),
            FakePage(None),
        ]
        xml = self.render(pages, [])
        self.assertEqual(self.locs(xml), ["http://example.org/a/"])
        self.assertIn("<lastmod>2026-01-02</lastmod>", xml)

    def test_output_is_well_formed_with_no_pages_and_no_extras(self):
        self.assertEqual(self.locs(self.render([], [])), [])

    def test_urls_are_xml_escaped(self):
        xml = self.render([], ["http://example.org/data/a.json?x=1&y=2"])
        self.assertIn("&amp;", xml)
        self.assertEqual(self.locs(xml), ["http://example.org/data/a.json?x=1&y=2"])


if __name__ == "__main__":
    unittest.main()
