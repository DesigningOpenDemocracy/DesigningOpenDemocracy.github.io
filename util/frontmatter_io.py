"""Shared helper for splitting a markdown file into (yaml_block, rest).

Several scripts (check_rss.py, scrape_news.py, record_dod.py, review_orgs.py)
edit org frontmatter with raw text surgery rather than a full YAML
re-serialization, to avoid reformatting parts of the file they didn't touch.
That requires locating the frontmatter's closing '---' delimiter.

A naive `content.split("---", 2)` breaks whenever any frontmatter *value*
contains a run of 3+ dashes before the real closing delimiter — which is not
a hypothetical: Medium's RSS post links legitimately look like
`...?source=rss-<hex>------<n>`. The naive split finds that embedded run
first, truncates the frontmatter mid-value, and pushes the remainder of the
file (including the real closing delimiter and the page body) into `rest`.
Writing "---" + yaml_block + "---" + rest back out then duplicates the
dashes and produces invalid YAML — see the regression test for a captured
real-world example (docs/organisations/participedia.md's rss activity url).

This only treats '---' as a delimiter when it's alone on its own line,
matching how python-frontmatter (and therefore mkdocs) actually parses the
file, so a value containing inline dashes can never be mistaken for the
boundary.
"""

import re

# Opening delimiter, then the shortest run of lines up to a line that is
# exactly '---' on its own. The closing delimiter's own line terminator is
# captured separately so `rest` can be reconstructed byte-for-byte.
_FRONTMATTER_RE = re.compile(r"^---(\r?\n)(.*?\n)---(\r?\n)", re.DOTALL)


def split_frontmatter(content):
    """Split `content` into (yaml_block, rest) at the frontmatter boundary.

    Mirrors the shape of `content.split("---", 2)[1:]` used previously —
    yaml_block is the text between the delimiters (with a leading newline),
    and `"---" + yaml_block + "---" + rest` reconstructs `content` exactly —
    but locates the closing delimiter as a whole line instead of a bare
    substring, so a dash run inside a value can't be mistaken for it.

    Returns (None, None) if `content` doesn't start with a '---' frontmatter
    block.
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, None
    yaml_block = m.group(1) + m.group(2)
    # rest starts right after the closing '---' itself (group 3 is its line
    # terminator) so "---" + yaml_block + "---" + rest reconstructs `content`.
    rest = content[m.start(3):]
    return yaml_block, rest


def write_rss_feed(path, feed_url):
    """Write rss_feed: to org frontmatter if not already present.

    Inserts after the website: line when present, otherwise before news_page:.
    Returns False (no write) if rss_feed: already exists in the file. Field
    order is left to reorder_frontmatter.py, which the pre-commit hook and
    the probe cron both run after writers like this one. Shared by
    scrape_news.py --update-rss and check_rss.py --update-activity, which
    records a feed its discovery probe finds so it isn't rediscovered from
    scratch on every run.
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    yaml_block, rest = split_frontmatter(content)
    if yaml_block is None:
        return False
    if re.search(r'^rss_feed\s*:', yaml_block, re.MULTILINE):
        return False
    for pattern in (r'^(website\s*:.*\n)', r'^(news_page\s*:.*\n)'):
        m = re.search(pattern, yaml_block, re.MULTILINE)
        if m:
            yaml_block = yaml_block[:m.end()] + f"rss_feed: {feed_url}\n" + yaml_block[m.end():]
            break
    else:
        yaml_block = yaml_block.rstrip("\n") + f"\nrss_feed: {feed_url}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + yaml_block + "---" + rest)
    return True
