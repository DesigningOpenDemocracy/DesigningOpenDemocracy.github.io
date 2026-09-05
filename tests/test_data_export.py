import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
HOOKS_DIR = os.path.join(ROOT_DIR, "hooks")
sys.path.insert(0, HOOKS_DIR)

import data_export as de


class TestDataExportGeoJSONEscaping(unittest.TestCase):

    def test_write_orgs_geojson_escapes_html(self):
        orgs = [
            {
                "slug": "test-org",
                "title": "Test <Org> & Co.",
                "status": "active",
                "country": "AU",
                "type": "nonprofit",
                "website": "https://example.org/?a=1&b=2\" '<script>",
                "logo": "",
                "summary": "Summary with <script>alert('xss')</script> & 'quotes'",
                "concepts": ["deliberative-democracy", "concept<tag>"],
                "latitude": -37.8136,
                "longitude": 144.9631,
                "location_name": "Melbourne",
                "last_checked": "2026-01-01",
                "rss_feed": "",
                "ics_feed": "",
                "activity": {},
                "contact_email": "",
                "contact_phone": "",
                "contact_form": "",
                "contact_channels": [],
            }
        ]
        meta = {"generated_at": "2026-01-01T00:00:00Z", "org_count": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_out_dir = de.OUT_DIR
            try:
                de.OUT_DIR = tmpdir
                de.write_orgs_geojson(orgs, meta)
                geojson_file = os.path.join(tmpdir, "organisations.geojson")
                with open(geojson_file, encoding="utf-8") as f:
                    data = json.load(f)

                feature = data["features"][0]
                desc = feature["properties"]["description"]

                self.assertNotIn("<script>", desc)
                self.assertIn("&lt;script&gt;", desc)
                self.assertIn("https://example.org/?a=1&amp;b=2&quot; &#x27;&lt;script&gt;", desc)
                self.assertIn("concept&lt;tag&gt;", desc)
            finally:
                de.OUT_DIR = orig_out_dir


if __name__ == "__main__":
    unittest.main()
