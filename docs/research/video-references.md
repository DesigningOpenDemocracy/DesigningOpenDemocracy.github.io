---
title: Video References
---

A running log of individual videos (YouTube essays, talks, podcasts) that have informed DOD discussion or been cited in a blog post or concept page. This tracks **specific videos**, not the creators or channels behind them — a creator gets a row here for each video referenced, not a dedicated page, unless their body of work warrants a full [organisation](../organisations/organisations.md) entry in its own right.

This is a citation log, not an endorsement list. Inclusion means a video was substantive enough to reference or respond to — not agreement with its argument.

| Date logged | Video | Creator / Channel | Topic | Referenced in | Thumbnail backup |
|---|---|---|---|---|---|
| 2026-06-26 | [We Need To Rethink Democracy](https://www.youtube.com/watch?v=W5JEJ_L_Zjg) | Andrewism | Anarchist critique of democracy as a category | [Anarchist critique of democracy](../blog/posts/2026-06-26-anarchist-critique-of-democracy.md) | [local copy](../assets/blog/2026-06-26-we-need-to-rethink-democracy-thumb.jpg) |

Thumbnails are saved locally under `docs/assets/blog/` (named `<date>-<slug>-thumb.jpg`) rather than hotlinked, so the reference survives if a video is taken down. Only the thumbnail is kept, not the video itself, and it's credited and linked back to the source.

## Watch list

Videos flagged as worth checking out but not (yet) discussed or cited in any DOD post. No "referenced in" link because there isn't one yet — these are bookmarks, not citations.

Add an entry with `util/add_video_reference.py` instead of editing this file by hand — it looks up the title/channel, downloads a local thumbnail to `docs/assets/blog/`, and appends both the table row and the thumbnail embed below:

```
python util/add_video_reference.py "https://www.youtube.com/watch?v=VIDEO_ID" --topic "One-line topic" --published 2026-06-18
```

`--topic` and `--published` are optional and will be asked for / left as `TBD` if omitted — fill in the date manually afterward if you don't have it handy.

| Video published | Video | Creator / Channel | Topic |
|---|---|---|---|
| 2020-11-02 | [Simulating alternate voting systems](https://www.youtube.com/watch?v=yhO6jfHPFQU) | Primer | Simulates how different voting systems (FPTP, approval, IRV, etc.) behave under the same electorate |
| 2018-06-26 | [The Rules of Society (Extra Politics, Part 4)](https://www.youtube.com/watch?v=gK1dZ67MLjY) | Extra History (Extra Credits) | Why political systems need stable, game-design-like rules to function |
| 2020-11-03 | [Supreme Court Chaos — How to Fix Governmental Exploits with Warhammer 40K](https://www.youtube.com/watch?v=8TRyN0mpczQ) | Extra History (Extra Credits) | Exploits/loopholes in the US political system, framed as game-design bugs |

If one of these gets discussed or cited in a post, move its row up into the main table above.

<a href="https://www.youtube.com/watch?v=yhO6jfHPFQU"><img src="../assets/blog/2020-11-02-simulating-alternate-voting-systems-thumb.jpg" alt="Thumbnail: Simulating alternate voting systems" width="280"></a>
<a href="https://www.youtube.com/watch?v=gK1dZ67MLjY"><img src="../assets/blog/2018-06-26-the-rules-of-society-thumb.jpg" alt="Thumbnail: The Rules of Society" width="280"></a>
<a href="https://www.youtube.com/watch?v=8TRyN0mpczQ"><img src="../assets/blog/2020-11-03-supreme-court-chaos-thumb.jpg" alt="Thumbnail: Supreme Court Chaos" width="280"></a>

## Possible future: a recommendation feed

Worth considering separately from this log: a lighter-weight way to surface interesting videos/articles to DOD members as they're found, rather than only retroactively logging things already cited in a post. That's closer to social-media sharing than to blogging or citation-tracking, and would need its own format (a Discord/mailing-list digest? a dated links page? something else?) rather than overloading this log or the blog. Noted here as a gap, not yet designed.
