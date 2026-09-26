#!/usr/bin/env python3
"""Apply a best-effort speaker map to an unlabelled .srt transcript.

The original transcript is never modified. For each map file
`speakers/<slug>.txt`, this writes `<slug>_inferred-speakers.srt` next to the
original transcript, prefixing every cue with `[Speaker]` in the same style as
the hand-reviewed 2026-09-15 `_labeled.srt`. Slugs are kept short on purpose:
some filesystems (eCryptfs home folders, notably) cap filenames at ~143 bytes,
and the original transcript names are already close to that.

Map file format (one directive per line; `#` starts a comment):

    source <file>.srt            the original transcript, relative to the
                                 transcript folder (must come first)
    @ <cue> <Speaker>            speaker turn starts at this cue number
    split <cue> | <text> | <Speaker>
                                 turn changes *inside* this cue, at the first
                                 occurrence of <text>; the text before it stays
                                 with the current speaker, <text> onwards goes
                                 to <Speaker>, who stays current afterwards

Cue numbers are the original file's. Directives must be in ascending cue
order. A `?` in a speaker name (e.g. `Andrew Kay?`, `Narrator (Brian Khuu?)`) marks the attribution as uncertain;
it is written into the label as-is. Split cues share their original time
range, divided in proportion to text length.

Usage:
    python speakers/apply.py            # every map in speakers/
    python speakers/apply.py <slug>     # one recording
    python speakers/apply.py --check    # validate maps, report stats, write nothing
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def parse_srt(path):
    cues = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [t.strip() for t in lines[1].split("-->")]
        cues.append({"n": int(lines[0]), "start": start, "end": end, "text": " ".join(lines[2:])})
    return cues


def to_ms(t):
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def from_ms(ms):
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_map(path):
    turns, splits, last, source = {}, {}, 0, None
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("split") else raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("source "):
            if turns or splits or source:
                sys.exit(f"{path.name}:{i}: 'source' must appear once, before any turn")
            source = line[len("source "):].strip()
            continue
        if source is None:
            sys.exit(f"{path.name}:{i}: missing 'source <file>.srt' line")
        if line.startswith("@"):
            m = re.match(r"@\s+(\d+)\s+(.+)$", line)
            if not m:
                sys.exit(f"{path.name}:{i}: bad directive: {raw}")
            n, who = int(m.group(1)), m.group(2).strip()
            if n in splits:
                sys.exit(f"{path.name}:{i}: cue {n} has both @ and split")
            turns[n] = who
        elif line.startswith("split"):
            m = re.match(r"split\s+(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*(#.*)?$", line)
            if not m:
                sys.exit(f"{path.name}:{i}: bad split: {raw}")
            n = int(m.group(1))
            splits.setdefault(n, []).append((m.group(2), m.group(3).strip()))
        else:
            sys.exit(f"{path.name}:{i}: unknown directive: {raw}")
        if n < last:
            sys.exit(f"{path.name}:{i}: cue {n} out of order (after {last})")
        last = n
    if source is None:
        sys.exit(f"{path.name}: missing 'source <file>.srt' line")
    return source, turns, splits


def label(cues, turns, splits, name):
    out, current = [], None
    if cues and cues[0]["n"] not in turns:
        sys.exit(f"{name}: first cue {cues[0]['n']} has no speaker")
    known = {c["n"] for c in cues}
    for n in list(turns) + list(splits):
        if n not in known:
            sys.exit(f"{name}: cue {n} does not exist")
    for c in cues:
        current = turns.get(c["n"], current)
        pieces = [(c["text"], current)]
        for marker, who in splits.get(c["n"], []):
            text, prev = pieces[-1]
            idx = text.find(marker)
            if idx <= 0:
                sys.exit(f"{name}: cue {c['n']}: split text not found (or at start): {marker!r}")
            pieces[-1:] = [(text[:idx].strip(), prev), (text[idx:].strip(), who)]
            current = who
        a, b = to_ms(c["start"]), to_ms(c["end"])
        total = sum(len(t) for t, _ in pieces) or 1
        t0 = a
        for j, (text, who) in enumerate(pieces):
            t1 = b if j == len(pieces) - 1 else t0 + (b - a) * len(text) // total
            out.append((from_ms(t0), from_ms(t1), f"[{who}] {text}"))
            t0 = t1
    return out


def main(argv):
    check = "--check" in argv
    stems = [a for a in argv if not a.startswith("--")]
    maps = [HERE / f"{s}.txt" for s in stems] if stems else sorted(HERE.glob("20*.txt"))
    for mp in maps:
        stem = mp.stem
        source, turns, splits = parse_map(mp)
        src = ROOT / source
        if not src.exists():
            sys.exit(f"{mp.name}: no transcript {source}")
        cues = parse_srt(src)
        out = label(cues, turns, splits, mp.name)
        speakers = {}
        for _, _, t in out:
            who = t[1:t.index("]")]
            speakers[who] = speakers.get(who, 0) + 1
        unsure = sum(v for k, v in speakers.items() if "?" in k)
        print(f"{stem}: {len(cues)} cues -> {len(out)}; {len(turns)} turns, "
              f"{sum(len(v) for v in splits.values())} splits; {unsure} cues uncertain")
        if not check:
            dst = ROOT / f"{stem}_inferred-speakers.srt"
            dst.write_text("\n\n".join(f"{i}\n{s} --> {e}\n{t}" for i, (s, e, t) in enumerate(out, 1)) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
