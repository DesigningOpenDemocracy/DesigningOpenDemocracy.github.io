# Best-effort speaker labels

The 2017–2022 transcripts were machine-transcribed without speaker
detection. This folder adds speaker labels to **copies** of them, worked out
from context, without touching the originals.

- **`<stem>.txt`**: the speaker map for `../<stem>.srt`. One line per turn:
  `@ <cue number> <Speaker>`. Comments (`#`) record the evidence: who
  introduces whom, who is addressed by name, what a speaker's known topics
  are. A `?` in a name marks an inferred attribution; `[Audience]` and
  `[Unidentified]` are used when there's nothing to go on.
- **`apply.py`**: writes `../<stem>_inferred-speakers.srt` from the map, in the
  same `[Speaker] text` style as the hand-reviewed
  `2026-09-15_…_labeled.srt`. Cue timings are copied unchanged.

```
python speakers/apply.py            # regenerate every labelled copy
python speakers/apply.py --check    # validate the maps and print stats only
```

To correct an attribution (e.g. after listening to the audio), edit the map,
not the generated `.srt`, then re-run `apply.py`. Remove the `?` once a line
is confirmed by ear. The `split` directive (see `apply.py`) handles a turn
change in the middle of a cue; none of the current maps needed one.

## How far to trust them

- **Two-person interviews** (Flux ×2, Isegoria, MiVote, Write In Stone): turn
  boundaries are clear from question and answer; few or no `?`s.
- **Talks with Q&A** (Citizens' Democracy parts 1–3, the 2020 Basil's Table):
  the main speakers are reliable; short interjections and audience turns less so.
- **Free-flowing group discussions** (the 2017 go-round, Trust, the Primer,
  Beyond CSR, the 2022 Basil's Table): expect errors in fast exchanges. The
  Trust episode is the weakest: 385 of its 818 cues carry a `?`.

A label here is a reading of the transcript, not of the audio. Before quoting
anyone in DOD's own voice, check the line by ear; the analysis README lists
the specific lines where that matters most.

Audience members stay anonymous as `[Audience]` even where the recording
names them, matching the convention in `../analysis/`.
