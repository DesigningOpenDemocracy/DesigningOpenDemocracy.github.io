"""hooks/org_cards.py: `<!-- org-card: slug -->` markers in blog posts."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))
import org_cards  # noqa: E402

ORG = """---
title: Example & Co
type: practice
status: {status}
country: AU
website: {website}
logo: /assets/org-logos/example.png
logo_bg: dark
summary: {summary}
---

Body.
"""


class OrgCardTests(unittest.TestCase):
    def setUp(self):
        org_cards._cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, 'organisations'))

    def tearDown(self):
        self.tmp.cleanup()

    def write_org(self, slug, status='active', website='https://example.org', summary='Short.'):
        with open(os.path.join(self.tmp.name, 'organisations', f'{slug}.md'), 'w') as fh:
            fh.write(ORG.format(status=status, website=website, summary=summary))

    def test_marker_becomes_card_with_both_links(self):
        self.write_org('example')
        out = org_cards.expand_markers('Bio.\n\n<!-- org-card: example -->\n\nMore.', self.tmp.name)
        self.assertNotIn('org-card:', out)
        self.assertIn('href="/organisations/example/"', out)
        self.assertIn('href="https://example.org"', out)
        self.assertIn('Example &amp; Co', out)          # escaped
        self.assertIn('org-logo-needs-dark', out)       # logo_bg honoured
        self.assertTrue(out.startswith('Bio.') and out.rstrip().endswith('More.'))

    def test_unknown_slug_fails_loudly(self):
        with self.assertRaises(ValueError):
            org_cards.expand_markers('<!-- org-card: nope -->', self.tmp.name)

    def test_archived_website_and_inactive_status_are_labelled(self):
        self.write_org('gone', status='inactive',
                       website='https://web.archive.org/web/*/https://gone.example/')
        out = org_cards.expand_markers('<!-- org-card: gone -->', self.tmp.name)
        self.assertIn('Website (archived)', out)
        self.assertIn('inactive', out)

    def test_long_summary_trimmed_on_word_boundary(self):
        self.write_org('long', summary=' '.join(['word'] * 200))
        out = org_cards.expand_markers('<!-- org-card: long -->', self.tmp.name)
        summary = out.split('org-card-summary">')[1].split('<')[0]
        self.assertTrue(summary.endswith('word…'))
        self.assertLessEqual(len(summary), org_cards.SUMMARY_CHARS + 1)

    def test_marker_mid_paragraph_is_left_alone(self):
        self.write_org('example')
        text = 'See <!-- org-card: example --> inline.'
        self.assertEqual(org_cards.expand_markers(text, self.tmp.name), text)


if __name__ == '__main__':
    unittest.main()
