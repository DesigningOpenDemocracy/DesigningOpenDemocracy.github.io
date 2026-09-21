#!/usr/bin/env python3
"""Tests for hooks/heartbeat_current.py's metadata line escaping logic."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import heartbeat_current as hc  # noqa: E402


class FakePost:
    def __init__(self, metadata):
        self.metadata = metadata


class HeartbeatCurrentTests(unittest.TestCase):
    def test_meta_block_escapes_html_in_date(self):
        post = FakePost({"date": "2026-09-01 <script>alert('xss')</script>"})
        result = hc._meta_block(post)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", result)
        self.assertNotIn("<script>alert('xss')</script>", result)

    def test_meta_block_escapes_html_in_tags(self):
        post = FakePost({"tags": ["<script>alert('xss')</script>"]})
        result = hc._meta_block(post)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", result)
        self.assertNotIn("<script>alert('xss')</script>", result)

    def test_meta_block_escapes_html_in_ai_assist(self):
        post = FakePost({"ai_assist": 'custom"<script>alert(1)</script>'})
        result = hc._meta_block(post)
        self.assertIn("&quot;", result)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", result)
        self.assertNotIn('custom"<script>', result)


if __name__ == "__main__":
    unittest.main()
