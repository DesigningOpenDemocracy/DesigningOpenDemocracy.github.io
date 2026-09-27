#!/usr/bin/env python3
"""Regression tests for hooks/org_template.py's nav handling.

The org profile pages are left out of SUMMARY.md (so the whole nav tree,
embedded in every page on the site, doesn't carry 170 of them), and the hook
switches the Democracy Landscape section on while each one renders so its tab
stays highlighted. Both halves fail silently: a section that's never switched
on leaves the tab dark on 170 pages, and one that's never switched off
highlights Democracy Landscape on every page built after the first profile.
The build passes either way, so both are pinned here.

Uses MkDocs' own Section class, since the upward propagation of `active` is
the behaviour being relied on. Run with:

    python -m unittest discover tests
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import org_template as ot  # noqa: E402

try:
    from mkdocs.structure.nav import Section
except ImportError:  # pragma: no cover - mkdocs is in requirements.txt
    Section = None


def page(src_uri):
    return types.SimpleNamespace(file=types.SimpleNamespace(src_uri=src_uri), active=False)


class OrgTemplateNavTests(unittest.TestCase):

    def setUp(self):
        if Section is None:
            self.skipTest("mkdocs not installed")
        ot._lit.clear()
        self.directory = page("organisations/index.md")
        self.map = page("map.md")
        self.landscape = Section("Democracy Landscape", [self.directory, self.map])
        self.calendar = page("calendar.md")
        self.news = page("news.md")
        self.cal_news = Section("Calendar & News", [self.calendar, self.news])
        self.nav = types.SimpleNamespace(
            items=[self.cal_news, self.landscape],
            pages=[self.calendar, self.news, self.directory, self.map],
        )

    def render(self, p):
        ot.on_page_context({}, page=p, config={}, nav=self.nav)
        seen = (self.landscape.active, self.cal_news.active)
        ot.on_post_page("", page=p, config={})
        return seen

    def test_finds_the_section_holding_the_directory(self):
        self.assertIs(ot.landscape_section(self.nav.items), self.landscape)
        nested = Section("Outer", [Section("Inner", [page("organisations/index.md")])])
        self.assertEqual(ot.landscape_section([nested]).title, "Inner")
        self.assertIsNone(ot.landscape_section([self.cal_news]))

    def test_org_profile_lights_the_landscape_tab_only_while_rendering(self):
        self.assertEqual(self.render(page("organisations/newdemocracy.md")), (True, False))
        self.assertFalse(self.landscape.active)

    def test_later_pages_are_not_left_highlighted(self):
        self.render(page("organisations/newdemocracy.md"))
        self.assertEqual(self.render(page("research/research.md")), (False, False))

    def test_pages_in_the_nav_are_left_to_mkdocs(self):
        # The directory is in the nav; MkDocs activates its section itself,
        # and the hook must not switch it off after that page renders.
        self.landscape.active = True
        self.render(self.directory)
        self.assertTrue(self.landscape.active)

    def test_other_sections_untouched(self):
        self.assertEqual(self.render(page("concepts/sortition.md")), (False, False))


if __name__ == "__main__":
    unittest.main()
