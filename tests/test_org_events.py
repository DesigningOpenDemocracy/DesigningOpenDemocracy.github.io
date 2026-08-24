#!/usr/bin/env python3
"""Regression tests for hooks/org_events.py's _coins_for_event(): the
COinS <span class="Z3988"> emitted for an org event with a url:, and its
evidence_sha256 pointer when the event also carries a quote:. See
Appendix E of internal-heartbeat/machine-verifiable-citation.md.

Offline, stdlib-only. Run with:

    python -m unittest discover tests
"""

import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import org_events as oe  # noqa: E402
import text_fragment as tf  # noqa: E402


class CoinsForEventTests(unittest.TestCase):

    def test_event_without_url_gets_no_span(self):
        self.assertEqual(oe._coins_for_event({"title": "Founded"}), "")

    def test_event_with_url_but_no_quote_gets_span_without_evidence_pointer(self):
        result = oe._coins_for_event({
            "title": "Founded", "url": "https://example.org/x", "date": "2020-01-01",
        })
        self.assertIn('class="Z3988"', result)
        self.assertIn("rft.atitle=Founded", result)
        self.assertIn("rft.date=2020-01-01", result)
        self.assertNotIn("evidence_sha256", result)

    def test_event_with_quote_gets_evidence_pointer(self):
        quote = "The organisation was founded in 2020."
        result = oe._coins_for_event({
            "title": "Founded", "url": "https://example.org/x",
            "date": "2020-01-01", "quote": quote,
        })
        expected_id = hashlib.sha256(tf.normalize_ws(quote).encode("utf-8")).hexdigest()
        self.assertIn(
            "evidence_sha256=" + expected_id[:tf.EVIDENCE_SHA256_PREFIX_LEN], result)


if __name__ == "__main__":
    unittest.main()
