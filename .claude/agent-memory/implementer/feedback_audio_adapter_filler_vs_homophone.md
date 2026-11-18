---
name: audio-adapter-filler-vs-homophone
description: command_matcher.FILLER_WORDS silently eats a word before rule_patterns digit-run parsing ever sees it -- check for this before adding any digit homophone/fuzzy word to a numeric slot
metadata:
  type: feedback
---

In `audio-adapter`, `command_matcher.match_transcript` computes one filler-stripped word list
(`strip_filler(normalize_for_match(text))`) and historically fed it to *both* the legacy pipeline
and `_match_rules`. `FILLER_WORDS` includes `"to"` (the "scan to the right" preposition case,
pinned by `test_filler_words_do_not_cost_a_match`).

**If you add a digit homophone (or any other fuzzy word) to `rule_patterns._consume_digit_run`
(or any numeric slot's own parser) that happens to collide with a `FILLER_WORDS` member, it will
be silently dead in the real pipeline** — `strip_filler` removes the word before the rule's own
digit-run parsing ever runs, even though a direct unit test calling `rule_patterns.match_pattern`
on a hand-built word list (which never goes through `strip_filler`) will pass fine and give false
confidence.

**Why: "to" -> "two"** (`[[BL-B129]]` D3) was measured dead in the integration path despite
passing every `rule_patterns`-level unit test, because the bench evidence ("heading **to** seven
zero") only exercises the real `match_transcript` pipeline, where `"to"` was already gone.

**Fix pattern, generalizable**: give `strip_filler` an optional `preserve: frozenset[str]`
parameter (default empty, so every existing call site is unaffected), and compute a *separate*
word list for rule matching with `preserve=frozenset(<your new fuzzy table>) & FILLER_WORDS`
(derived, not hand-copied, so a future addition that collides is caught automatically). Keep the
legacy pipeline on the plain fully-stripped list — its own pinned filler-forgiveness cases depend
on the word staying gone there.

**Before shipping any matching-layer fix, run it through `match_transcript` end to end, not just
through the lower-level parser directly** — this is the specific instance of "a counterfactual is
evidence only if you ran it" that cost a full implementation round here.
