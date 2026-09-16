# Folio event follow-up: two measurement orgs, two speaker orgs, and a shelved commentary angle

**Status: mostly shipped.** The org pages described below were added directly (not
parked) — see "What shipped" at the bottom. This note exists for the one thing that
*wasn't* shipped: a possible public World-commentary item, held back only because
this month's `docs/heartbeat/posts/2026-09-sync.md` already carries its three "In
the world" items.

## What was asked

The user forwarded a Folio Collective event page and, separately, a Folio email
invite for the same event — "Should we celebrate democracy today — or reimagine it
for tomorrow?" (24 Sep 2026, virtual, 9–10pm AEST). That event was added to
[`docs/organisations/folio-collective.md`](../docs/organisations/folio-collective.md)'s
`events:` list (merged PR, branch `claude/democracy-celebration-reimagining-7imwbp`).

The user then pointed out the event page's own text cites two measurement projects
by name — V-Dem Institute's *Democracy Report 2026* and the Economist Intelligence
Unit's *Democracy Index 2025* — and asked what to do with them. Given the go-ahead
("Both": add as tracked orgs *and* note the contrast as heartbeat commentary), and a
follow-up nudge to also consider the two Conversation Leaders' own organisations
(Lisa Witter: Apolitical, Better Politics Foundation; Josh Lerner: People Powered,
Participatory Budgeting Project — the latter two already existed in the Landscape).

## What shipped

Six org-page edits, all on the same branch as the Folio event addition, each with
mechanically-verified `quote:`/footnote evidence (`check_fragments.py --no-cache`
green across all of them) and `check_event_sourcing.py`/`reorder_frontmatter.py`/
`check_footnote_quotes.py` all clean:

- **New:** [`v-dem-institute.md`](../docs/organisations/v-dem-institute.md) — `type: research`, founding (2014) + Democracy Report 2026 events.
- **New:** [`economist-intelligence-unit.md`](../docs/organisations/economist-intelligence-unit.md) — `type: research`, first Democracy Index (2006) + Democracy Index 2025 events.
- **New:** [`apolitical.md`](../docs/organisations/apolitical.md) — `type: platform`, 2017 public launch event.
- **New:** [`better-politics-foundation.md`](../docs/organisations/better-politics-foundation.md) — `type: foundation`, no dated events (nothing solidly dateable found on its own site — see below), prose-only.
- **Updated:** [`people-powered.md`](../docs/organisations/people-powered.md) — added its 2019/2020 founding events (previously had none), a "Key people" section on Josh Lerner, `related_orgs: [participatory-budgeting-project]`, and corrected contact (email/phone were missing, only a webform was recorded).
- **Updated:** [`participatory-budgeting-project.md`](../docs/organisations/participatory-budgeting-project.md) — reciprocal `related_orgs: [people-powered]` plus one sentence on the PBP→People Powered lineage.

**Judgment call worth recording:** V-Dem and EIU are measurement/monitoring bodies,
not governance-design orgs — the accountability framework's "not a human rights
observatory" carve-out (`docs/projects/accountability-framework/index.md`, "What
this means in practice") is about exactly this shape of concern. The precedent that
settled it: [Afrobarometer](../docs/organisations/afrobarometer.md) is already
tracked as a pure survey-research network with no direct engagement/advocacy
component, and [Israel Democracy Institute](../docs/organisations/israel-democracy-institute.md)
is tracked as `type: research` despite its flagship product also being an index.
Both V-Dem and EIU sit squarely inside that existing precedent, so this wasn't
escalated as a fresh framework question — noted here mainly so a future session
doesn't have to re-derive the reasoning from scratch.

**Better Politics Foundation has no `events:`.** Its `/about` page currently
serves obvious Wix placeholder content (fake staff names "Michael Greenberg" /
"Sheril La Pez", placeholder phone `123-456-7890`, `info@apoliticalfo.com`) — a
site still mid-migration from its old "Apolitical Foundation" branding, consistent
with Folio's own bio copy calling it "formerly, Apolitical Foundation." The
homepage itself has real content (used for the page's prose + footnotes), but
nothing with a solid date. Worth a re-check in a few months once the site migration
presumably finishes — the placeholder `/about` page is the tell.

## What's still open: a shelved World-commentary angle

Folio's own framing of the two reports is a real contrast worth a reader's
attention: V-Dem's *Democracy Report 2026* ("Unraveling The Democratic Era?")
leads with acceleration — "Democratic backsliding is now happening in
well-established democracies" ([press release](https://www.v-dem.net/news/press-release-democratic-backsliding-reaches-western-democracies-with-us-decline-unprecedented/),
17 Mar 2026) — while EIU's *Democracy Index 2025* leads with stabilisation —
"Following eight years of decline, 2025 marks a stabilisation of democracy scores
that suggests an end to the global democratic recession"
([PR Newswire](https://www.prnewswire.com/news-releases/eiu-democracy-index-2025-democracy-stabilises-after-eight-years-of-decline-302734863.html),
7 Apr 2026) — both citing the same US decline as their clearest outlier. That's a
genuine "two credible measurement projects, two different headlines, same country
flagged both ways" story, and it's nonpartisan on its face (it's about measurement
methodology and framing, not a policy position).

It wasn't added to this month's public sync post because that post already has
its three "In the world" items (Niger, Missouri, Guinea-Bissau) and CLAUDE.md caps
World commentary at 1–3 per post. It also wasn't force-fit into "Framework notes"
since it isn't friction with applying the framework — it's a world-affairs item
like the other three, just a later find.

**For a future heartbeat pass:** if this angle still reads as newsworthy, it can go
straight into World commentary using the two quotes above (already
mechanically-verified against their live sources as part of shipping the org pages,
so no re-fetching needed) — just check first whether V-Dem/EIU have published
anything newer that would date this contrast by the time it runs.
