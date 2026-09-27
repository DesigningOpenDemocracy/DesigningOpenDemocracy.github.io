"""
org_types.py — MkDocs hook: one shared grouping of org `type:` values into
display categories (icon + label), for the Democracy Map's type filter and the
type icon shown on the Democracy Landscape pages.

Why this exists. `type:` is free text in org frontmatter, and the corpus has
grown to ~20 distinct values (`research`, `ngo`, `civic tech`, `think-tank`,
`network`, ...). Before this hook, three templates each carried their own
type→emoji table (home.html's map, organisation.html, organisations.html),
none of which agreed with the others and none of which covered the values
actually in use: every `ngo`, `network`, `foundation`, `think-tank` and
`civic tech` (with a space — the tables only knew `civic_tech`) org fell
through to the generic 🏛️. On the map that hardly mattered, because 156 of
158 mapped orgs render their logo instead of an emoji — which left the map's
"Organisation type" legend describing icons nobody could see. The legend is
now a filter (see home.html), and a filter needs every org to land in a real
category, so the grouping has to be complete and has to live in one place.

The categories are deliberately coarse — ten rows is about what fits in a map
overlay — and a type that isn't listed falls into "Other" rather than
breaking anything. tests/test_org_types.py fails when an org page uses a type
that isn't listed here, so a new value gets a deliberate home instead of
silently joining "Other".

knowledge-graph.html keeps its own, finer-grained per-type emoji on purpose:
there the icon *is* the node's type label, not a category.
"""

import re

# Order is display order in the map filter.
CATEGORIES = (
    {
        "key": "research",
        "icon": "🔬",
        "label": "Research & think tanks",
        "types": ("research", "education", "think-tank"),
    },
    {
        "key": "advocacy",
        "icon": "📢",
        "label": "Advocacy & campaigns",
        "types": ("advocacy", "campaign"),
    },
    {
        "key": "civil-society",
        "icon": "🌐",
        "label": "NGOs & networks",
        "types": ("ngo", "civil-society", "network"),
    },
    {
        "key": "civic-tech",
        "icon": "💻",
        "label": "Civic tech & platforms",
        "types": ("platform", "civic-tech"),
    },
    {
        "key": "practice",
        "icon": "🤝",
        "label": "Practitioners & co-ops",
        "types": ("practice", "cooperative", "consultancy"),
    },
    {
        "key": "philanthropy",
        "icon": "💰",
        "label": "Foundations & philanthropy",
        "types": ("philanthropy", "foundation"),
    },
    {
        "key": "political",
        "icon": "🗳️",
        "label": "Parties & movements",
        "types": ("party", "political-party", "political-movement", "movement"),
    },
    {
        "key": "governance",
        "icon": "⚖️",
        "label": "Government & governance",
        "types": ("government", "governance"),
    },
    {
        "key": "media",
        "icon": "📺",
        "label": "Media",
        "types": ("media",),
    },
)

OTHER = {"key": "other", "icon": "🏛️", "label": "Other", "types": ()}

ALL_CATEGORIES = CATEGORIES + (OTHER,)

_BY_TYPE = {t: c for c in CATEGORIES for t in c["types"]}


def normalize_type(value):
    """Fold a raw `type:` value to the hyphenated form CATEGORIES lists.

    The corpus writes the same type several ways — `civic tech`,
    `civic_tech`, `political_party`, `political-party` — so matching is on
    lowercase with runs of spaces/underscores/hyphens collapsed to one hyphen.
    """
    if not value:
        return ""
    return re.sub(r"[\s_-]+", "-", str(value).strip().lower()).strip("-")


def category_for(value):
    """The category dict a raw `type:` value belongs to (OTHER if unlisted)."""
    return _BY_TYPE.get(normalize_type(value), OTHER)


def on_env(env, config, files):
    env.globals["org_type_categories"] = [
        {k: c[k] for k in ("key", "icon", "label")} for c in ALL_CATEGORIES
    ]
    env.filters["org_type_category"] = lambda v: category_for(v)["key"]
    env.filters["org_type_icon"] = lambda v: category_for(v)["icon"]
    return env
