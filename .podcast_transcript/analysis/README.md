# Podcast transcript analysis

Reference notes derived from the recordings in `.podcast_transcript/`. They're
raw material for future blog posts, wiki pages (org, concept, philosophy) and
fact-checking: **not posts themselves**, so nothing here is trimmed to fit.
A published post has to drop material for length; these files keep it.

They live outside `docs/`, so mkdocs never builds them. The repo is public,
so treat them as world-readable; they add no exposure the committed
transcripts didn't already.

## Index

| Recorded | Recording | Notes | Blog post |
|---|---|---|---|
| 2017-05-19 | Challenges facing the present and future of democracy | [notes](2017-05-19_challenges-facing-democracy.md) | [2017-05-19-podcast](../../docs/blog/posts/2017-05-19-podcast.md) |
| 2017-10-21 | Citizens' Democracy: Nicholas Gruen, Hubertus Hofkirchner, Q&A | [notes](2017-10-21_citizens-democracy.md) | [2017-10-21-podcast](../../docs/blog/posts/2017-10-21-podcast.md) (was filed under 21 Aug; see below) |
| 2019-12-11 | Trust, a concept analysis | [notes](2019-12-11_trust-concept-analysis.md) | [2019-12-11-podcast](../../docs/blog/posts/2019-12-11-podcast.md) |
| 2020-02-11 | Ben Ballingall on Flux and IBDD (main + bonus) | [notes](2020-02-11_flux-party-ben-ballingall.md) | [2020-02-13](../../docs/blog/posts/2020-02-13-podcast.md), [2020-02-29](../../docs/blog/posts/2020-02-29-podcast.md) |
| 2020-02-21 | DOD 2020 Primer | [notes](2020-02-21_dod-2020-primer.md) | [2022-02-24-podcast](../../docs/blog/posts/2022-02-24-podcast.md) |
| 2020-02-25 | Basil's Table: banking on the future | [notes](2020-02-25_basils-table-banking.md) | [2020-02-20-podcast](../../docs/blog/posts/2020-02-20-podcast.md) |
| 2020-03-03 | Isegoria: Nicholas Gruen | [notes](2020-03-03_isegoria-nicholas-gruen.md) | [2020-03-20](../../docs/blog/posts/2020-03-20-podcast.md) |
| 2020-03-27 | Beyond CSR towards economic democracy (co-ops panel) | [notes](2020-03-27_beyond-csr-economic-democracy.md) | [2020-06-20-podcast](../../docs/blog/posts/2020-06-20-podcast.md) |
| 2021-07-20 | Catching up with Adam Jacoby (MiVote) | [notes](2021-07-20_mivote-adam-jacoby.md) | [2021-08-07-podcast](../../docs/blog/posts/2021-08-07-podcast.md) |
| 2021-07-31 | Austin, founder of Write In Stone | [notes](2021-07-31_write-in-stone-austin.md) | [2021-08-08-podcast](../../docs/blog/posts/2021-08-08-podcast.md) |
| 2022-12-06 | Basil's Table: co-operative futures in the tech bros era | [notes](2022-12-06_basils-table-tech-bros.md) | [2023-01-21-podcast](../../docs/blog/posts/2023-01-21-podcast.md) |
| 2026-09-15 | International Day of Democracy panel | [breakdown](2026-09-15_international-day-of-democracy.md) | [recap](../../docs/blog/posts/2026-09-26-international-day-of-democracy-recap.md) |

## How these differ from the IDoD breakdown

The 2026 breakdown was written against a **speaker-labelled, audio-reviewed**
transcript, so its quotes can be used as they stand. Every other recording
here has only the **automated** pod-transcript.com transcript: no speaker
labels, misheard names, the occasional wrong word. So in these notes:

- Speaker attribution is inferred from turn-taking and content, and flagged
  where it's uncertain. Those inferences are now also applied to copies of
  the transcripts: `../*_inferred-speakers.srt`, generated from the editable
  maps in [`../speakers/`](../speakers/README.md). Correct a speaker there,
  not in the notes or the generated `.srt`.
- Every quote needs checking against the audio before it goes into DOD's own
  voice. Fillers are dropped without a mark, `…` marks cuts, `[brackets]`
  mark an obvious correction of the transcript.
- The older posts were mostly drafted from the same automated transcripts
  (2026), so the notes also check each post against its transcript.

## Common structure

Each file has, as far as the recording supports: who's who; a timestamped run
of show; a per-speaker breakdown with timestamped quotes (including what the
post left out); a check of the blog post against the transcript; a
transcription-corrections table; a claims-to-check table; threads; and
landscape connections (existing pages, and candidates that haven't been
assessed). Sensitive passages (partisan remarks, personal speculation, lines
that would read badly out of context) are kept and labelled rather than
silently dropped, so a future editor can make the call.

Audience members stay anonymous, as in the IDoD breakdown, even where the
recording names them.

## Handling sensitive material

**Read everyone in the best light.** These are unscripted conversations,
some nearly a decade old, transcribed by machine. People misremember a date
or a party, reach for a name that's nearly right, or say something that
exists but can't easily be found now. A note should say *what the record
shows* and *what a post should do about it*, never that someone lied or
made something up. The same goes for DOD's own older posts: a line that
can't be found in a transcript was most likely a summary that drifted into
quote marks during drafting, or words the automated transcript garbled.

Wording to use: "couldn't be found in the transcript", "differs from the
record", "from memory", "probably meant", "his/her view". Wording to avoid:
"wrong", "made up", "false", "misreported", or any guess at motive.

Every item involving a named public figure, or correcting a speaker, gets
one of four handling labels, so a future post knows what to do:

| Label | Use for | In a post |
|---|---|---|
| **Omit** | Speculation about a named person's private conduct or motives; mocking nicknames; sweeping partisan labels for a government or party | Leave it out. If the point matters, make it without the name |
| **Attribute** | A speaker's opinion or characterisation of a public figure | Only as the speaker's view, in their words, with enough context; consider whether the post needs it at all |
| **Clarify** | A factual slip, misremembered detail, or unconfirmed claim | State the correct record (with a source) in neutral words, or leave the detail out |
| **Fine** | Passing mention, uncontroversial public fact, or checked | No special handling |

### Register

Named public figures and speaker corrections across the archive. "Checked"
means against a source named in the file's claims table or below; anything
else is unchecked.

| Recording | Item | Label | Notes |
|---|---|---|---|
| 2017-05-19 | Francisco: Kim Jong-un "a dictator", Trump "a populist" | Attribute | Opinion, attributed in the post |
| 2017-10-21 | Gruen: Pauline Hanson "an authentic politician" | Attribute | His view; not a criticism of her |
| 2017-10-21 | Gruen: the 2008 Obama transition's online policy vote ranked marijuana, "the birth certificate" and "alien abductions" top | Clarify | Marijuana topping change.gov's Citizen's Briefing Book is well reported; the other two are his recollection. Use only the marijuana detail, or attribute the rest as his memory |
| 2017-10-21 | Hofkirchner: G!LT won "double" the Communists | Clarify | Roughly level (about 0.96% vs 0.8%) |
| 2019-12-11 | Speculation that Gillard asked Penny Wong to hold the party line on marriage equality | **Omit** | A guess about a private conversation. Brian raised Wong and Andrew Kay made the speculation (both audio-checked). Wong's *public* position at the time is on the record and can be cited instead: Wikipedia's Penny Wong article says she was "an instrumental figure in the legalisation of same-sex marriage in Australia in 2017, reversing her previous endorsement of Labor Party policy that had opposed it" (checked 2026-09-26 via a summarising fetch; confirm the wording on the page before quoting) |
| 2019-12-11 | Johnson's "we've lost the South" | Clarify | Widely repeated, but reported second-hand (Bill Moyers' account) and not firmly documented. "Reportedly", if used at all. Not found in Wikipedia's *Southern strategy* article in this pass; the usual attribution is to Bill Moyers' recollection, unconfirmed here |
| 2019-12-11 | Putin and fake Facebook pages on both extremes | Attribute | Consistent with published findings on Russian social-media operations around 2016; cite a source if a post uses it |
| 2019-12-11 | Wool stockpile and price-control referendums, told from memory | Clarify | See the file's claims table: the party details differ from the record. The party and date details in that table weren't re-checked in this pass (Wikipedia was rate-limiting this environment); confirm before a post relies on them |
| 2020-02-11 | Ben: Clive Palmer's 2019 ads were "idiotic" | Attribute | Opinion about advertising, mild; paraphrase is fine. Spend figure: Wikipedia's United Australia Party article gives "$60 million at the 2019 election" (checked 2026-09-26 via a summarising fetch); some later reports put it higher, unconfirmed here, so Adam's "$87 million" may reflect those. Say "reported at around $60 million" with a source, or leave the figure out |
| 2020-02-11 | Ben: MPs like Cory Bernardi are "able to backstab their party" | Attribute (paraphrase) | "Backstab" is Ben's word for leaving the party one was elected with. The public record: "On 7 February 2017… Bernardi left the Liberal Party to form a separate party, the Australian Conservatives" (Wikipedia, checked 2026-09-26 via a summarising fetch). A post should describe the act neutrally. A second name ("Santafond") is unidentified; don't guess |
| 2020-02-21 | Brian and Alexar on whether MiVote was a party | Clarify | Each remembered part of it; see the file |
| 2020-03-03 | Gruen: Abbott's carbon-price stance "simply isn't a policy" (what he thinks a jury would say) | Attribute | His hypothetical; keep it framed that way |
| 2020-03-03 | Gruen: Alan Jones and Rush Limbaugh treat "anyone who doesn't agree with them" as "a fool" | Attribute | His characterisation of broadcasters; consider omitting names |
| 2020-03-03 | Gruen: the Coalition is "funded by the coal lobby", with his caveat that it's "sort of true on both sides" | Attribute | Only with his both-sides caveat, or omit |
| 2020-03-03 | Gruen: Morrison "said that we should spend less money on bushfire readiness" | **Omit** | Contested characterisation; don't repeat without a source for what was actually said |
| 2020-03-03 | Gruen's characterisation of Kellyanne Conway | **Omit** | Personal remark; his reading of "alternative facts" can be kept without it |
| 2020-03-03 | Gruen: Howard was "trying to gerrymander the system in his own favor" with the 1999 referendum question | Attribute | His view of question design; the post uses the neutral version |
| 2020-03-03 | Gruen's description of the Belgian citizens' council ("two provinces", "50 people") | Clarify | From memory; the post names the actual body |
| 2021-07-20 | Adam: "the Morrison government is basically a fascist government" | **Omit** | Sweeping partisan label. The post leaves it out |
| 2021-07-20 | Adam on the US ("not a democracy… a republic") and China | Attribute | Omit unless a post is about comparative systems, and then with context |
| 2021-07-20 | Adam: Palmer spent "$87 million… in Queensland" | Clarify | Wikipedia's United Australia Party article gives "$60 million at the 2019 election" (checked 2026-09-26 via a summarising fetch); some later reports put it higher, unconfirmed here, so Adam's "$87 million" may reflect those. Say "reported at around $60 million" with a source, or leave the figure out; the campaign was national |
| 2021-07-20 | The "PEG" programme | Clarify | Probably the Global Entrepreneur Programme; see the file |
| 2021-07-31 | A satirical video's nickname for Scott Morrison | **Omit** | Mocking nickname; name the video's subject plainly if needed |
| 2022-12-06 | Jose: AI regurgitates "Putin, Trump and the Kardashians" | Attribute | Rhetorical; quoted in the post with attribution |
| 2022-12-06 | Jose/Alexar on billionaires and Jeff Bezos | Attribute | Their view |
| 2022-12-06 | Bridgette Engeler quote in the post | Clarify | Couldn't be found in the transcript; replaced with her recorded words |
| 2022-12-06 | Post's summary of Jose Ramos's position | Clarify | Now reported as he stated it |

## Blog-post issues found

Found while checking posts against transcripts. Ordered roughly by importance.

**Status (2026-09-26): all addressed in the posts**, at the maintainer's
request, in the same PR as these notes (blog posts are human-owned, so the
edits go through review like any other). Two needed more than a text edit:

- **#1**: now fully fixed. The post is dated 21 October 2017, its old
  21 August URL redirects to the new one, and it keeps a short note that it
  used to be filed under August.
- **#2**: resolved in favour of the recording, and verified against the
  audio (00:49:44 in the Q&A episode). The live notes were taken by ear
  during the talk; both posts now quote the recording and keep the
  live-notes version only as a record.

The same pass also brought every blockquote in these posts into line with the
automated transcript's wording (fillers dropped, `…` for cuts), added a few
passages the posts had dropped, and gave each post a "Detailed notes" link to
its file here. The list below is kept as the record of what was found.

1. **The Citizens' Democracy event was 21 October 2017, not 21 August.**
   Meetup's own event page (243645818) says 2017-10-21 18:30; all three audio
   intros say 21 October; Hofkirchner reports the 15 October 2017 Austrian
   election result. The post's `date:`, heading and prose all say 21 August,
   and its `link:` frontmatter points at the May 2017 meetup. The transcript
   files were renamed to `2017-10-21_…` in this pass; the post's `date:` feeds
   its URL, so changing it is a human call. The Write In Stone post also links
   to it as the "2017" event. [Details](2017-10-21_citizens-democracy.md#the-event-date-is-21-october-2017-not-21-august)
2. **The Gruen line DOD quotes may be misheard.** The 2017 post and the
   [Taiwan post](../../docs/blog/posts/2026-05-25-taiwan-digital-democracy.md)
   (twice) quote "the considered opinion of the people amounts to nothing
   unless you consider it properly". The automated transcript has "…unless
   people respect it and pay it legitimacy". Listen before quoting again.
3. **2022 Basil's Table post:** a quote attributed to Bridgette Engeler
   couldn't be found in the transcript (most likely a summary that ended up in
   quote marks during drafting), and the post summarised Jose Ramos's position
   as "not a left critique", where he states plainly that he's a socialist and
   that the left is right about equity. [Details](2022-12-06_basils-table-tech-bros.md#checking-the-blog-post-against-the-transcript)
4. **Flux main post:** says it was recorded "a few weeks after" the 2020
   Primer (the Primer was ten days *later*), and that the Fed Square encounter
   was "a few days" earlier (it was the same day). Also names a member of the
   public.
5. **2020 Primer post:** "Bank the Table" should be Bang the Table; "Adam
   Jacobi" should be Jacoby; "Centre for Living Festival" is the Sustainable
   Living Festival; "SUP" is SOUP; the Trust episode is called the "following"
   episode but came before. The recorded "MiVote wasn't a party" correction
   conflicts with DOD's own MiVote page.
6. **2017 post:** says both speakers cited the "what is the EU?" Google spike
   (only Hofkirchner did); "GI!LT" should be G!LT; "Ian Walker" is Iain Walker.
7. **MiVote post:** "Jamie Skeller" is Jamie Skella (as the Horizon State page
   has it); the UK programme described as "PEG… Department of Prime Minister
   and Cabinet" is probably the Global Entrepreneur Programme; the federal-MP
   trial was planned, not "underway"; the 60% figure needs an approval-voting
   caveat.
8. **Trust post:** the feedback-loop quote is stitched from several sentences
   and two speakers; "first episode of the DOD podcast" should be the first
   *recorded* for it (the intro calls it part one of a two-part series on
   trust, and no part two exists here).
9. **Beyond CSR post:** Stocksy is Canadian, not US; Mondragon's size and
   ranking are Antony's 2020 figures stated as fact.
10. **Basil's Table 2020 post:** repeats Rowan Dowland's "brand only since
    2017" alongside the 2015 rename.
11. **Write In Stone post:** "a decade building the tool" — the company was
    founded in 2017, four years before.

## Threads across the archive

The connections no single recording makes. Each file's own Threads section
has the detail.

1. **Nicholas Gruen, 2017 → 2020 → 2026.** The same spine throughout
   (Schumpeter's division of labour, elections as aristocratic, the jury as
   model, the carbon-price repeal as worked example, "we're part of the
   problem"), with the standing assembly moving from a designed chamber *in*
   Parliament (2017) to a crowdfunded body that needs no permission (2020) to
   "don't ask for any permission. Just run it" (2026). His carbon-repeal cost
   rises from $10bn a year (2017) to "$12… may be $15 billion" (2026). See the
   [2017 notes](2017-10-21_citizens-democracy.md#gruen-across-the-archive).
2. **Specialisation vs representativeness.** Gruen samples; Hofkirchner
   samples after screening by prediction record; Flux rewards specialists
   through delegation; MiVote asks everyone, with information packs and a
   60% bar. Four positions on one axis, all argued on DOD recordings.
3. **Supermajorities.** Gruen's "10 out of 12" and "60 or 65 percent",
   MiVote's 60% rule, the 2026 panel's ~80% "folk wisdom". Arrived at
   independently from very different models.
4. **The question matters as much as the answer.** Hofkirchner on the Greek
   referendum (2017), Ben Ballingall's "who wrote the question?" (Feb 2020),
   Gruen on Brexit vs the 1999 republic model (Mar 2020).
5. **Why reformers can't unite.** Alexar's identity diagnosis (Trust, 2019),
   his foundation proposal (Primer, 2020), Adam Jacoby on growing too fast and
   trusting the wrong partner (2021). DOD's own reason for existing.
6. **Blockchain and voting tech.** "Trust the mathematics" and "trust but
   verify" (2019), Flux's "you can't prove us wrong" (2020), MiVote's creator
   calling the Horizon State spin-out his worst decision (2021).
7. **Co-operatives as schools of democracy.** Antony's ownership-plus-democracy
   (2019), Rowan Dowland's "bigger, but not better" (2020), Red Gum's rotating
   board roles and Mondragon's ecosystem (2020), co-housing meetings and
   "practise to become human" (2022), and the IDoD panel (2026).
8. **"Isn't there an app for that?"** Antony asks it in 2022 and 2026; Gruen
   mocks "it's all about the app" in 2017; Hofkirchner builds an app designed
   to slow people down; Austin builds one to show the research behind the
   story.
9. **Trust in information.** Brian's information overload (2017), tribal
   epistemology (2019), Pomerantsev and trolls (2020), Write In Stone's audit
   trails (2021), Loab and "CI" (2022). Parallel to DOD's own
   machine-verifiable citation work.

## Follow-ups this pass surfaced

Not done here; listed so they aren't lost.

- **Org pages** that these recordings could source (`events:` or prose):
  MiVote's founding story and 2021 UK move; Prediki/G!LT's 2017 campaign;
  Flux's WA 2021 expectations; Co-operative Bonds, Earthworker (Red Gum),
  bHive (Villages launch), 888 (both Basil's Tables); DOD itself (the 2020
  Primer, the 2020 programme, and a session with Hofkirchner around
  30 July 2021).
- **Concept pages** the archive keeps reaching for: deliberative polling,
  platform co-operatives, the commons / community land trusts, co-housing,
  approval voting.
- **Candidates for assessment** are listed per file. Check
  [`orgs-not-included.md`](../../internal-heartbeat/orgs-not-included.md)
  first; Forensic Architecture, for one, has already been assessed and
  excluded.
- **Audio review: spot-checks, not full passes.** Full speaker labelling of
  these older recordings isn't worth the effort: four are two-person
  interviews where attribution is already reliable, and the rest are
  mostly paraphrased in their posts. A handful of specific lines do matter,
  and each one needs only a minute or two of listening. Timestamps are
  from the podcast cuts, i.e. the `.srt` files:

  | Recording | Timestamp | What to settle | Why it matters |
  |---|---|---|---|
  | 2017-10-21 part 3 (Q&A) | 00:49:44 | Gruen: "…unless people respect it and pay it legitimacy" (recording) vs "…unless you consider it properly" (live notes, taken by ear). **Verified 2026-09-26**: the recording's wording is correct word for word (cues 416–418) | Done |
  | 2019-12-11 Trust | 00:39:42–00:41:52 | Who speculates about Gillard and Penny Wong. **Checked 2026-09-26**: Brian raises Wong (00:38:42); Andrew Kay makes the speculation | Done. Marked *omit* in the register either way |
  | 2019-12-11 Trust | 00:41:52 and 01:22:19 | Who introduces tribal epistemology; who says the feedback-loop lines. **Checked 2026-09-26**: Andrew Kay (00:42:33) and Alexar Pendashteh (01:24:00) | Done |
  | 2022-12-06 Basil's Table | 00:03:12 and 00:15:42 | Is "Jacques" José Ramos, or a different person? | Affects who told the shoelace story |
  | 2017-05-19 go-round | 00:13:06 | Is the closing speaker Kevin or David? | The post names Kevin as the likely speaker |
  | 2020-03-27 Beyond CSR | 00:59:49 | Is the "systems thinker" Andrew Downing? | The post names him |

  The misquote in the 2022 post (Bridgette) needs no audio: the words aren't
  in the transcript, so the fix is to quote what she did say.

## For future recordings

What made the IDoD panel easy to analyse, and worth making the default:

1. **Get a speaker-labelled transcript at the start**, from a tool that does
   diarisation (the IDoD file came in as `…_labeled.srt`). Name it
   `<event-date>_<name>_labeled.srt`, alongside the audio-derived plain
   transcript if one exists.
2. **Do one hand pass against the audio** before any quoting: speaker labels,
   names and terms, and anything likely to be quoted. Commit it as its own
   commit (as `2412ad4` was for IDoD), so the diff shows what the review
   changed.
3. **Then write the breakdown** in this folder, and only then the recap post.
   The breakdown keeps everything; the post selects from it.
4. **Record the event date** in the transcript README table, with where it came
   from (the event page, not the post's publish date; see the 2017 date error).
