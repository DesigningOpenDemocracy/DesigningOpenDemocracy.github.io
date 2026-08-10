# Lessons from event sourcing infrastructure build (Aug 2026)

Session covered commits `3417133` through `4578104` — building mandatory
event sourcing, confidence scoring, proof_level, fragments, quotes, notes,
and CI gating from near-scratch (95 of 228 events had no source URL).

## What worked

1. **Hard gates with override fields.** Requiring `url:`/`source:` on every
   event (exit 1 in CI) was the right posture — zero manual policing needed.
   Adding `proof_warning: true` as an override for the secondary gate
   (fragment/quote/note) kept the gate honest without grinding work to a halt
   on stubborn citations.

2. **Wikipedia fragments (`#:~:text=`).** Worth the effort — 67 events now
   carry mechanically verifiable evidence that browsers highlight on click.
   The fragment text MUST be exact from the Wikipedia article, not
   agent-summarized (see pitfalls below).

3. **`proof_level` as a single derived field.** The hardening pass
   (`59ba590`, `730a7fa`) made it always derived from `confidence_score()`,
   so stored and computed values can't drift. `--recalculate` handles the
   "signals changed" case. The UI shows it as a colored badge (green/amber/red).

4. **`quote:` field as mechanical proof alternative to fragments.**
   A `quote:` contains exact source text, mechanically verified by
   `check_fragments.py` (substring match with whitespace normalization).
   Lower friction than URL-encoded fragments, same trust level.

5. **`note:` vs `quote:` distinction.** `note:` = editorial paraphrase
   (your summary, third person). `quote:` = exact source text (verifiable).
   Bare first-person quotes in notes are confusing — a reader can't tell who
   "I" or "we" is. If you're going to quote, use `quote:`. If you're going
   to summarize, use third person.

## Pitfalls

1. **`frontmatter.dump()` scrambles YAML field ordering.** Python
   `frontmatter` library writes fields in alphabetical order, destroying the
   canonical org page ordering. Always follow a `frontmatter.dump()` with
   `reorder_frontmatter.py`. The pre-commit hook catches this on commit,
   but scripts that write org pages should reorder inline. The linter's
   `--calculate` path now calls `_reorder_file()` after writing.

2. **Parallel agents writing to the same file set.** Running multiple task
   agents that each read-then-write org pages produces race conditions. An
   agent's `post = frontmatter.load(path)` captures a snapshot at load time;
   by the time it writes back with `frontmatter.dump(post, path)`, another
   agent's writes to the same file are overwritten. We lost ~40 notes this
   way during the note backfill batch (noticed after the hard gate still
   showed events we'd supposedly documented).

   **Mitigation:** Either serialize agent writes (one batch at a time), or
   design agents to target non-overlapping file sets.

3. **Fragment text must be verbatim from the source.** Agents generated
   fragments from their summaries of Wikipedia text rather than exact
   extracts — "created by Colin Megill" vs the article's "founded by Colin
   Megill", "Kongra Star founded 2005" vs "founded in 2005 under the name of
   Yekîtiya Star". The browser `#:~:text=` feature does exact string matching;
   a single word difference means the text won't highlight. Always use the
   Wikipedia API (`prop=extracts`) to get the exact text, then verify with
   `check_fragments.py`.

4. **YAML quoting for `quote:` values.** Any `quote:` containing a colon,
   quote mark, or other YAML-sensitive character needs explicit quoting:
   `quote: "text with: colon"`. A bare colon in a quote value produces a
   "mapping values are not allowed here" parse error. Added YAML validation
   to the pre-push checks after hitting this 8 times.

5. **Non-Wikipedia quote matching is fragile.** Fetching a page and
   stripping HTML tags with regex `re.sub(r"<[^>]+>", " ", content)` loses
   text in `<title>`, `<meta>`, and `<script>` tags — which is fine for body
   content but means quotes from meta-sourced claims won't match. Non-ASCII
   text (French, Spanish, Japanese) adds encoding edge cases. The
   whitespace normalization (`" ".join(text.split())`) fixed some but not
   all mismatches. For non-Wikipedia pages, `note:` (editorial) is currently
   more reliable than `quote:` (mechanical).

6. **Wikipedia rate-limiting.** `check_fragments.py` fetches 67+ Wikipedia
   extracts per run with 0.5s delay. Wikipedia throttles after ~20 requests,
   producing "API error" false positives. The tool now separates API errors
   from real mismatches in its output, so a rate-limited run doesn't look
   like a content crisis. Weekly cron is fine; would not work as a per-push
   CI gate.

## Current state and backlog

- **228 events, 0 unsourced, 0 no-proof** — hard gate passes.
- **67 high proof** (fragments), **158 medium** (notes/specific URLs),
  **3 low** (source-only or homepage).
- **56 proof_warning** events — have URLs but no fragment/quote/note.
  These show ⚠ in the UI. Each needs a real quote or fragment.
- **22 quote mismatches** in `check_fragments.py` — mostly non-ASCII text
  or Wayback Machine pages where the cached content differs from current.
  Not blocking (weekly cron only), but worth investigating per org.

## For the next bot that tackles this

- Read [CLAUDE.md](../CLAUDE.md) sections on events, proof_level, note vs
  fragment.
- The `check_fragments.py` mismatches will need per-page investigation —
  fetch the actual page, see what's different, fix the quote.
- The `proof_warning` backlog is grind work: fetch each event's URL, find
  confirming text, add as `quote:` or fragment. Batch 10-15 per run.
- Never use `frontmatter.dump()` without following it with the reorder
  function. Better yet, use `yaml.dump` directly with `sort_keys=False` and
  a canonical-order-aware Dumper (see `reorder_frontmatter.py` for the
  pattern).
- Never run parallel agents that write to the same org files. Either
  serialize writes or use non-overlapping file sets.
- When adding `#:~:text=` fragments, always get the exact text from the
  Wikipedia API (`prop=extracts`), not from your own summary. Verify with
  `check_fragments.py`.
- The CI design is deliberate: per-push checks are local-only (no network),
  weekly cron does the network-dependent work (fragment checking, URL
  liveness, RSS probes). Don't move network tools into the per-push CI.
