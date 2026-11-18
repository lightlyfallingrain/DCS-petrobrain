---
name: audio-adapter-global-normalize-fold-danger
description: a global word-level fold in vocabulary.normalize_for_match reaches every pipeline (verb anchor, phrase table, legacy slot parsers) at once -- a fold meant for one narrow bug can silently widen a different, pre-existing fuzzy collision to ordinary free speech
metadata:
  type: feedback
---

`vocabulary.normalize_for_match`'s output feeds `command_matcher.match_transcript`'s `verb`
(`words[0]`), the HVRT bare-word shortcut, every legacy slotted parser, and the phrase table. A
fold added there for one specific bug (`[[BL-B129]]` D4: "alright" → "right", to fix a single
bare-word bench clip) is **not scoped to that clip** — it changes the first word of every sentence
that happens to contain the folded phrase, anywhere in it.

**Measured consequence**: `command_matcher._HVRT_BARE_WORD_TOKENS`'s own comment already documents
a pre-existing fuzzy collision, `SequenceMatcher("right", "sight") == 0.8`, guarded today only by
the HVRT shortcut's own `len(words) == 1` check. A global `normalize_for_match` fold of
"alright"/"all right" → "right" turns the *first word* of any sentence beginning with "alright"
into "right", which reaches that same 0.8 collision through the *generic* verb-anchor path (no
`len == 1` guard there) — "alright then let's go" resolved to `point` before this was caught and
reverted.

**The fix that worked**: scope the alias to the *exact* bare-word transcript (a dict keyed by the
whole word tuple: `{("alright",): "right", ("all", "right"): "right"}`), consulted only at the one
call site (the HVRT shortcut) that already had the narrow guard. Zero new false-positive surface,
verified directly against several free-speech sentences containing "alright"/"all right".

**General lesson**: before adding *any* word-level fold to `normalize_for_match` (as opposed to a
scoped alias at one specific call site), check what else reads its output as a first-word anchor
or an anywhere-in-sentence slot scan, and run the fold against ordinary sentences containing the
folded word, not just the one clip it was meant to fix. A global fold's blast radius is every
consumer of `normalize_for_match`, not the matching branch you had in mind.
