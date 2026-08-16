#!/usr/bin/env python3
"""Regression tests for util/frontmatter_io.py's split_frontmatter().

Offline, stdlib-only — no network, no fixture files needed. Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

from frontmatter_io import split_frontmatter  # noqa: E402


class SplitFrontmatterTests(unittest.TestCase):

    def test_matches_naive_split_on_ordinary_content(self):
        content = "---\ntitle: X\nfoo: bar\n---\n\nBody text here.\n"
        yaml_block, rest = split_frontmatter(content)
        parts = content.split("---", 2)
        self.assertEqual(yaml_block, parts[1])
        self.assertEqual(rest, parts[2])

    def test_round_trips_exactly(self):
        content = "---\ntitle: X\nfoo: bar\n---\n\nBody text here.\n"
        yaml_block, rest = split_frontmatter(content)
        self.assertEqual("---" + yaml_block + "---" + rest, content)

    def test_dash_run_inside_a_value_is_not_mistaken_for_the_delimiter(self):
        # Regression: docs/organisations/participedia.md's activity.rss.url
        # is a real Medium RSS link shaped "...?source=rss-<hex>------<n>" —
        # a legitimate value containing a run of dashes before the actual
        # closing '---'. A naive content.split("---", 2) finds the embedded
        # dashes first, truncating yaml_block mid-value and corrupting the
        # file on the next write (duplicated dashes, broken YAML).
        content = (
            "---\n"
            "title: Participedia\n"
            "activity:\n"
            "  rss:\n"
            "    url: https://x/y?source=rss-4e7f7d842e0a------2\n"
            "last_checked: '2026-06-15'\n"
            "---\n"
            "\n"
            "Body.\n"
        )
        yaml_block, rest = split_frontmatter(content)
        self.assertIn("source=rss-4e7f7d842e0a------2", yaml_block)
        self.assertTrue(yaml_block.rstrip("\n").endswith("last_checked: '2026-06-15'"))
        self.assertEqual(rest, "\n\nBody.\n")
        self.assertEqual("---" + yaml_block + "---" + rest, content)

    def test_no_frontmatter_returns_none(self):
        yaml_block, rest = split_frontmatter("no frontmatter here\n")
        self.assertIsNone(yaml_block)
        self.assertIsNone(rest)

    def test_windows_line_endings(self):
        content = "---\r\ntitle: X\r\n---\r\n\r\nBody.\r\n"
        yaml_block, rest = split_frontmatter(content)
        self.assertIsNotNone(yaml_block)
        self.assertEqual("---" + yaml_block + "---" + rest, content)


if __name__ == "__main__":
    unittest.main()
