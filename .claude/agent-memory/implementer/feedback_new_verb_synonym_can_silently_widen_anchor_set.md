---
name: new-verb-synonym-can-silently-widen-anchor-set
description: Adding a short verb synonym to audio-adapter's command vocabulary can flip an existing pinned adversarial-sentence test by widening VERB_ANCHOR_WORDS -- measure the fuzzy ratio before adding, don't discover it via a failing test
metadata:
  type: feedback
---

When adding a new token/phrasing to `audio-adapter/src/vocabulary.py`, every phrasing's **first
word** is automatically picked up into `command_matcher._derive_verb_anchor_words()`
(`VERB_ANCHOR_WORDS`), which is deliberately permissive (`VERB_FLOOR = 0.5`, a fuzzy
`difflib.SequenceMatcher` ratio). A short, common-letter word added as a verb synonym can cross
that floor against an ordinary English word already exercised by a pinned adversarial-sentence
test (e.g. `test_non_command_speech_enqueues_with_null_token`, `"the tanks are on the ridge"`) --
measured case: adding `"attack"` as an `engage` synonym (BL-14 Stage 5, per the spec's own
"engage/attack/attack-run") made `difflib.SequenceMatcher(None, "tanks", "attack").ratio() ==
0.545`, just over the floor, flipping that sentence's `verb_anchored` from `False` (falls through
to free speech, correct) to `True, token=None` ("say again", a real behaviour change -- the
`_phrase_match_ratio` stage still correctly resolves `token=None` either way, but `verb_anchored`
is part of `MatchResult`'s own public contract and the caller's disposition differs on it).

**Why:** `_derive_verb_anchor_words` is a strict superset by design (the module's own docstring
says so -- it has picked up `full`/`what`/`hey`/`never` etc. before), so this is not a bug in the
mechanism; it is an inevitable side effect of vocabulary growth that the design accepts in
general but that the project's own rule against modifying pinned tests without permission does
not let an implementer paper over silently.

**How to apply:** before adding a new phrasing whose first word is a short/common word, run
`difflib.SequenceMatcher(None, candidate, new_word).ratio()` against a few ordinary nouns likely
to appear in free speech (not just against existing vocabulary words) and against
`VERB_FLOOR`/`MATCH_FLOOR`. If it crosses the floor against something a pinned test already
exercises, do not add the phrasing and do not edit the test -- flag the gap explicitly in
`implementation.md` (what collided, the measured ratio, which pinned test it would break) and
leave the synonym out, matching this project's "existing tests must be rewritten rather than
extended -> escalate" rule. Confirmed working fix: keep the single canonical verb (`engage`) and
log the dropped synonym (`attack`/`attack-run`) as a named gap rather than silently narrowing
scope.
