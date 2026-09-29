"""
news_signals.py — triage hints for the news checkup: which of an org's posts
look worth opening, and which look routine.

The checkup (util/news_checkup.py) lists every post an org has published since
the last review, and most of them are job ads, newsletters, petitions and
routine commentary. A title alone often can't tell those apart from the rare
post that belongs on Landscape News. These are keyword matches on the post's
title and its opening lines, grouped under labels that follow the
`notable_reason:` categories editors have actually used for News items
(launches, reports, leadership changes, court wins, flagship conferences,
citizens' assemblies, awards...), plus a "likely routine" set and any other
Landscape org the post names.

They are hints for where to start, not a verdict: a keyword can't tell a
flagship report from a passing mention of one, a post with no signal can
still be News, and posts in languages the lists don't cover mostly get none.
The reviewer opens the post either way.

Only the labels are stored (in docs/data/feeds/<slug>.json, by check_rss.py
at read time, when the post's text is in memory). The post text itself is
never kept, for the same reason the citation cache stores hashes rather than
page bodies: the labels and names are our words, the posts are theirs.
"""

import glob
import os
import re
import sys

try:
    import frontmatter
except ImportError:  # only landscape_names() needs it
    frontmatter = None

UTIL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, UTIL_DIR)
from text_fragment import _PARAGRAPH_DELIM, html_to_text  # noqa: E402
ORGS_DIR = os.path.join(UTIL_DIR, "..", "docs", "organisations")

# How much of a post's opening text the keyword signals look at. The whole
# body mentions "report" or "election" in passing far too often in this
# landscape to mean anything; the opening lines (usually the feed's own
# excerpt) say what the post is about.
LEDE_CHARS = 400

# Label -> patterns, matched case-insensitively on whole words against the
# title and lede. English first, with a few common Spanish, French,
# Portuguese and German forms for the categories that most often make News.
WORTH_A_LOOK = {
    "launch": [
        r"launch(es|ed|ing)?", r"unveil(s|ed)?", r"introducing", r"now live", r"goes live",
        r"lanza(miento|mos)?", r"lancement", r"lança(mento)?", r"startet",
    ],
    "publication": [
        r"report", r"handbook", r"index", r"white paper", r"policy brief", r"study",
        r"survey", r"findings", r"research paper", r"publishe[sd]", r"new book",
        r"informe", r"rapport", r"relatório", r"bericht", r"studie",
    ],
    "leadership change": [
        r"appoint(s|ed|ment)", r"steps? down", r"stepping down", r"resign(s|ed|ation)?",
        r"new (ceo|chair|chairperson|president|director|executive director|secretary[- ]general|leader)",
        r"farewell", r"successor", r"nombra(do|miento)", r"nommé(e)?",
    ],
    "organisational change": [
        r"merger", r"merge[sd]?", r"rename[sd]?", r"rebrand(s|ed|ing)?", r"new name",
        r"wound up", r"winding up", r"deregister(ed)?", r"clos(es|ing) (down|its doors)",
        r"founded", r"anniversary", r"restructur(e|es|ed|ing)",
    ],
    "legal or legislative": [
        r"court", r"ruling", r"judg(e)?ment", r"verdict", r"tribunal", r"lawsuit",
        r"legislation", r"bill (passed|passes)", r"passes (the )?bill", r"new law",
        r"inquiry", r"sentencia", r"décision",
    ],
    "election or referendum": [
        r"referend(um|a)", r"election results?", r"wins? \d+ seats",
        r"(re-?)?elected (as|to|president|chair|leader)", r"re-?elected",
        r"electoral reform", r"election observation", r"plebiscit(e|o)",
    ],
    "flagship event": [
        r"conference", r"summit", r"festival", r"convention", r"symposium", r"congress",
        r"annual general meeting", r"AGM", r"general assembly", r"global forum",
        r"congreso", r"cumbre", r"sommet", r"kongress",
    ],
    "deliberative process": [
        r"citizens'? ?(assembl(y|ies)|jur(y|ies)|panels?|councils?|forums?)",
        r"people'?s assembl(y|ies)", r"mini-?publics?", r"sortition",
        r"deliberative (polls?|process(es)?|democracy)",
        r"asambleas? ciudadanas?", r"conventions? citoyennes?", r"bürgerräte|bürgerrat",
    ],
    "award or recognition": [
        r"award(s|ed)?", r"prize", r"winner", r"recogni[sz]ed", r"honou?red",
        r"premio", r"prix", r"preis",
    ],
    "mobilisation": [
        r"protest(s|ers)?", r"rall(y|ies)", r"mobili[sz]ation", r"general strike",
        r"manifestaci[oó]n",
    ],
    "death": [
        r"passed away", r"obituary", r"in memoriam", r"remembering",
        # The Australian obituary form, "Vale Jane Smith". Case-sensitive,
        # since "vale" is an everyday word in Spanish.
        r"(?-i:Vale [A-Z]\w*)",
        r"has died", r"dies at",
    ],
    "funding": [
        r"grant", r"funding (boost|awarded|announced)", r"receives? funding",
    ],
}

LIKELY_ROUTINE = {
    "job ad": [
        r"we'?re hiring", r"hiring", r"job", r"vacanc(y|ies)", r"looking for an?",
        r"recruiting", r"join (our|the) team", r"internship", r"position available",
        r"convocatoria",
    ],
    "fundraising": [
        r"donate", r"donation", r"fundrais(er|ing)", r"giving day",
        r"(winter|tax|end of year|christmas|emergency|fundraising) appeal",
        r"appeal for (support|donations|funds)",
        r"support (our|us)", r"become a (member|supporter)",
    ],
    "newsletter or roundup": [
        r"newsletter", r"bulletin", r"digest", r"round-?up", r"monthly update",
        r"weekly update", r"news update", r"in the polls", r"this week in",
        r"boletín", r"lettre d'information",
    ],
    "petition": [
        r"petition", r"sign (the|our)", r"עצומה",
    ],
    "event reminder": [
        r"reminder", r"last chance", r"register now", r"save the date", r"tickets",
        r"webinar",
    ],
    "podcast or video episode": [
        r"episode", r"ep\. ?\d+",
    ],
}


def _compile(table):
    return {label: re.compile(r"(?<!\w)(?:" + "|".join(pats) + r")(?!\w)", re.IGNORECASE)
            for label, pats in table.items()}


_WORTH = _compile(WORTH_A_LOOK)
_ROUTINE = _compile(LIKELY_ROUTINE)


_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def _straight(text):
    """Curly apostrophes as straight ones, so "Citizens’ Assemblies" matches
    the patterns and names above the way "Citizens' Assemblies" does."""
    return (text or "").translate(_APOSTROPHES)


def lede(text, limit=LEDE_CHARS):
    """The first `limit` characters of a post's plain text, whitespace
    collapsed."""
    return " ".join((text or "").split())[:limit]


def signals(title, lede_text=""):
    """(worth_a_look, likely_routine): sorted label lists for one post."""
    haystack = _straight(f"{title or ''}\n{lede_text or ''}")
    worth = sorted(label for label, rx in _WORTH.items() if rx.search(haystack))
    routine = sorted(label for label, rx in _ROUTINE.items() if rx.search(haystack))
    return worth, routine


def _names_for(title):
    """The forms of an org's title worth matching in someone else's post:
    the title without a parenthetical or an em-dash subtitle, if at least
    two words long. One-word names ("Involve", "Memorial") are ordinary
    words, so they'd match everywhere; they're left out."""
    base = re.sub(r"\s*\([^)]*\)", "", str(title or "")).split(" — ")[0].strip()
    return [base] if len(base.split()) >= 2 else []


def landscape_names(orgs_dir=ORGS_DIR):
    """[(slug, [names], rss_feed)] for every org page, for mentions()."""
    if frontmatter is None:
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(orgs_dir, "*.md"))):
        if os.path.basename(path) == "index.md":
            continue
        meta = frontmatter.load(path).metadata
        out.append((os.path.basename(path)[:-3], _names_for(meta.get("title")),
                    meta.get("rss_feed") or ""))
    return out


def _plain(html):
    if not html:
        return ""
    return " ".join(html_to_text(html).replace(_PARAGRAPH_DELIM, " ").split())


def annotate(entries, names=(), exclude=()):
    """Set `signals`, `routine` and `mentions` on each parsed feed entry
    (check_rss.parse_feed_entries output), from its title, the opening of its
    excerpt (or body, when there's no excerpt) and, for mentions, its full
    text. The text is read here and not kept."""
    for e in entries:
        summary = _plain(e.get("summary_html"))
        body = _plain(e.get("body_html"))
        e["signals"], e["routine"] = signals(e.get("title"), lede(summary or body))
        e["mentions"] = mentions(f"{e.get('title') or ''}\n{body or summary}", names, exclude)
    return entries


def mentions(text, names, exclude=()):
    """Other Landscape orgs a post names, matched case-sensitively as whole
    phrases (so "Democracy Club" the org, not "a democracy club"). `names`
    is landscape_names() output; `exclude` is slugs to skip, typically the
    orgs the feed belongs to."""
    if not text:
        return []
    text = _straight(text)
    found = []
    for slug, forms, _feed in names:
        if slug in exclude:
            continue
        for name in forms:
            if re.search(r"(?<!\w)" + re.escape(_straight(name)) + r"(?!\w)", text):
                found.append(name)
                break
    return sorted(set(found))
