#!/usr/bin/env python3
"""Regression tests for hooks/normalize_tags.py.

The motivating bug: mkdocs-material's tags plugin treats every distinct
tag *string* as its own tag, but slugifies each into the anchor id used on
the tags index. Two spellings of one topic therefore emitted two <h2>
sections sharing one id — and since the plugin sorts case-sensitively,
`Title Case` tags all sorted above `lowercase` ones, putting the halves
far apart. A browser jumps to the first of two duplicate ids, so
/tags/#tag:deliberative-democracy showed one 2021 podcast while the five
pages actually carrying that tag sat further down the page, unreachable by
the link. 18 slugs were split this way across the site.

Offline, stdlib-only apart from pymdownx (already a mkdocs-material
dependency). Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import normalize_tags as nt  # noqa: E402
import tag_links as tl  # noqa: E402


class FakePage:
    def __init__(self, meta):
        self.meta = meta


class NormalizeTagTests(unittest.TestCase):
    def test_case_and_spacing_variants_fold_together(self):
        for variant in ("Deliberative Democracy", "deliberative democracy",
                        "DELIBERATIVE DEMOCRACY", "deliberative-democracy"):
            self.assertEqual(nt.normalize_tag(variant), "deliberative-democracy")

    def test_punctuation_variants_fold_together(self):
        self.assertEqual(
            nt.normalize_tag("Issue-Based Direct Democracy"),
            nt.normalize_tag("Issue-based Direct Democracy"),
        )

    def test_folding_matches_the_anchor_tag_links_builds(self):
        # If these two ever disagree, a tag's chip would link to an anchor
        # that no section on the listing page carries — the failure this
        # hook exists to prevent, in a new form.
        for tag in ("Deliberative Democracy", "MiVote", "888 Co-operative Causeway",
                    "Basil's Table", "pirate party", "AI"):
            self.assertEqual(tl.tag_url(tag), "/tags/#tag:" + nt.normalize_tag(tag))


class OnPageMarkdownTests(unittest.TestCase):
    def _fold(self, tags):
        page = FakePage({"tags": tags})
        nt.on_page_markdown("", page, None, None)
        return page.meta["tags"]

    def test_rewrites_tags_in_place(self):
        self.assertEqual(
            self._fold(["Podcast", "MiVote", "Direct Democracy"]),
            ["podcast", "mivote", "direct-democracy"],
        )

    def test_order_is_preserved(self):
        self.assertEqual(self._fold(["Zebra", "apple", "Mango"]),
                         ["zebra", "apple", "mango"])

    def test_a_page_carrying_both_spellings_is_not_listed_twice(self):
        self.assertEqual(
            self._fold(["Deliberative Democracy", "deliberative-democracy"]),
            ["deliberative-democracy"],
        )

    def test_returns_markdown_unchanged(self):
        # Returning anything but None here would replace the page body.
        self.assertIsNone(nt.on_page_markdown("# Body", FakePage({"tags": ["A"]}), None, None))

    def test_pages_without_tags_are_left_alone(self):
        for meta in ({}, {"tags": []}, {"tags": None}):
            page = FakePage(dict(meta))
            nt.on_page_markdown("", page, None, None)
            self.assertEqual(page.meta, meta)


if __name__ == "__main__":
    unittest.main()
