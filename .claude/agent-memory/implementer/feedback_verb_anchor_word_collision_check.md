---
name: audio-adapter-verb-anchor-collision-check
description: before adding any new voice-command phrase to audio-adapter/src/vocabulary.py, check whether its first word collides with an existing adversarial sentence at or above command_matcher.VERB_FLOOR -- VERB_ANCHOR_WORDS has no override list by design
metadata:
  type: feedback
---

`audio-adapter/src/command_matcher.py`'s `VERB_ANCHOR_WORDS` is strictly
derived from the first word of every phrase in `vocabulary.PHRASES` --
deliberately, with no hand-curated exclusion list (the module's own
docstring explains why: a hand list drifts out of sync with the table).
That means **adding any new phrase can turn its first word into a false
verb-anchor against an existing pinned adversarial sentence**, and nothing
stops it at write time -- only running the test suite catches it.

**Measured case:** adding `"weapons armed"`/`"weapons safe"`
(`BL-B66`) made `"weapons"` a verb-anchor word.
`difflib.SequenceMatcher(None, "tanks", "weapons").ratio() == 0.5`, exactly
`VERB_FLOOR`, so the reviewer's own adversarial sentence ("the tanks are on
the ridge") in `tests/test_transcribe_api.py` flipped from
`verb_anchored=False` to `True` (but `token` stayed `None` -- the
phrase-sequence score, the module's actual defence, still rejects it). This
is the *same* collision class `vocabulary.py`'s own comment already
documents for `engage`'s rejected `"attack"` synonym
(`ratio("tanks", "attack") == 0.545`) -- but that case had a substitute
word available and could just be left out; `"weapons"` did not (the
phrase was the user's own locked wording), so it went in anyway with the
collision flagged rather than silently absorbed.

**How to apply before adding a phrase:** compute
`difflib.SequenceMatcher(None, w, new_first_word).ratio()` for every word in
the existing adversarial-sentence fixtures (`test_command_matcher.py`'s
`test_lowering_verb_floor_does_not_reopen_the_false_positives` and
`test_filler_stripping_does_not_reopen_the_false_positives`), not just eyeball
it. If a ratio lands at or above `VERB_FLOOR` (0.5): check whether `token`
still resolves `None` end to end (it usually will -- the phrase-sequence
score is the real defence) before concluding the phrase is unsafe to add; if
it does, the only thing that needs updating is any test asserting the
*intermediate* `verb_anchored` flag specifically, not the token outcome.
Flag the collision explicitly in the vocabulary comment and the commit,
the way the `engage`/`attack` precedent already does -- do not silently
absorb a pinned-test fix.
