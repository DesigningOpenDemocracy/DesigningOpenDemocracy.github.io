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
