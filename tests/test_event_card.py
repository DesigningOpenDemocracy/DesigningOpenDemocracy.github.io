#!/usr/bin/env python3
"""Tests for hooks/event_card.py's on_page_markdown escaping logic."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import event_card as ec  # noqa: E402


class FakeFile:
    def __init__(self, src_path):
        self.src_path = src_path


class FakePage:
    def __init__(self, src_path, meta):
        self.file = FakeFile(src_path)
        self.meta = meta


class EventCardTests(unittest.TestCase):
    def test_event_card_escapes_when_field(self):
        page = FakePage(
            "blog/posts/test.md",
            {
                "event": {
                    "url": "https://example.org/event",
                    "date": "2026-10-15 <script>alert(1)</script>",
                }
            },
        )
        result = ec.on_page_markdown("Some content", page=page, config={}, files=[])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", result)
        self.assertNotIn("<script>alert(1)</script>", result)


if __name__ == "__main__":
    unittest.main()
