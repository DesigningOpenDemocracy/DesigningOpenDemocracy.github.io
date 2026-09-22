#!/usr/bin/env python3
"""Regression tests for hooks/calendar_export.py's _load_manual_events():
that a curated org event's note: and quote: reach the site-wide calendar.

Motivating bug: the hook built its event dict field by field and simply
never read note/quote, so an event's only human-readable description
rendered on the org's own timeline (organisation.html wraps both in a
<details>) and nowhere else. A reader browsing /calendar/ saw a bare
title. Dropping a field here is silent — the calendar still builds — so
the passthrough is pinned rather than left to review.

Offline, stdlib-only apart from the python-frontmatter the hook itself
needs. Run with:

    python -m unittest discover tests
"""

import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import calendar_export as ce  # noqa: E402


ORG_PAGE = """---
title: Example Org
type: advocacy
status: active
events:
- date: '{date}'
  title: A panel on something
  url: https://example.org/event
  note: An editorial paraphrase of what the event is.
  quote: Verbatim sentence from the source page.
- date: '{date}'
  title: An event with no description at all
  url: https://example.org/bare
---

Body.
"""


class ManualEventDescriptionTests(unittest.TestCase):
    """note:/quote: must survive the trip from frontmatter to the calendar."""

    def setUp(self):
        if ce.frontmatter is None:
            self.skipTest("python-frontmatter not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.future = datetime.date.today() + datetime.timedelta(days=30)
        with open(os.path.join(self.tmp.name, "example-org.md"), "w",
                  encoding="utf-8") as f:
            f.write(ORG_PAGE.format(date=self.future.isoformat()))
        self._orig_dir = ce.ORGS_DIR
        ce.ORGS_DIR = self.tmp.name
        self.addCleanup(lambda: setattr(ce, "ORGS_DIR", self._orig_dir))

    def _events(self):
        return ce._load_manual_events(datetime.date.today())

    def test_note_and_quote_reach_the_calendar(self):
        described = next(e for e in self._events()
                         if e["title"] == "A panel on something")
        self.assertEqual(described["note"],
                         "An editorial paraphrase of what the event is.")
        self.assertEqual(described["quote"],
                         "Verbatim sentence from the source page.")

    def test_event_without_them_carries_no_description(self):
        """calendar.html gates the <details> on these being falsy, so an
        undescribed event must not grow an empty disclosure triangle."""
        bare = next(e for e in self._events()
                    if e["title"] == "An event with no description at all")
        self.assertFalse(bare["note"])
        self.assertFalse(bare["quote"])


class CalendarJsonLdEscapingTests(unittest.TestCase):
    """calendar.html's JSON-LD block must safely encode special characters in event fields."""

    def test_jsonld_escaping(self):
        try:
            import jinja2
        except ImportError:
            self.skipTest("jinja2 not installed")

        cal_template_path = os.path.join(
            os.path.dirname(__file__), "..", "docs", "overrides", "calendar.html"
        )
        with open(cal_template_path, encoding="utf-8") as f:
            content = f.read()

        start_idx = content.find('<script type="application/ld+json">')
        end_idx = content.find("</script>", start_idx)
        self.assertNotEqual(start_idx, -1)
        self.assertNotEqual(end_idx, -1)

        snippet = content[start_idx + len('<script type="application/ld+json">'):end_idx]
        env = jinja2.Environment()
        tpl = env.from_string(snippet)

        events = [
            {
                "title": 'Special "Title" & <script>',
                "date": datetime.date(2026, 10, 1),
                "end_date": datetime.date(2026, 10, 2),
                "url": 'https://example.com/test?q="</script><script>alert(1)</script>',
                "location": 'Melbourne "Office"',
                "country": 'AU"</script><script>alert(2)</script>',
                "org_slug": "test-org",
                "org_title": 'Test "Org" & Co.',
            }
        ]

        rendered = tpl.render(calendar_events=events)

        # Must not contain literal </script> inside JSON-LD payload
        self.assertNotIn("</script>", rendered)

        # Must parse cleanly as JSON
        data = json.loads(rendered)
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["name"], 'Special "Title" & <script>')
        self.assertEqual(item["url"], 'https://example.com/test?q="</script><script>alert(1)</script>')
        self.assertEqual(item["location"]["address"]["addressCountry"], 'AU"</script><script>alert(2)</script>')


if __name__ == "__main__":
    unittest.main()
