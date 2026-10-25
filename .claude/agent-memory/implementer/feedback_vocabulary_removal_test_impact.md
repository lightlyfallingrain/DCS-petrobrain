---
name: vocabulary-removal-test-impact
description: removing a phrasing from one PHRASES token can silently re-anchor an existing pinned mishearing test onto a *new* token via another branch's VERB_FLOOR match -- check, don't assume unaffected
type: feedback
---

When a plan removes a phrasing from `audio-adapter/src/vocabulary.py`'s
`PHRASES` (e.g. `"look ahead"` dropped from `PHRASES["scan_ahead"]` so
`look` stops aliasing `scan`, `BL-B89` Stage 2), re-run every existing
pinned mishearing/fuzzy-match test end to end before assuming it still
holds — don't just grep for the removed literal string.

**Why:** `command_matcher.py`'s slotted branches (`follow`/`report`/
`select_target`/`point`/...) each fuzzy-match the heard verb against their
own small verb set at `VERB_FLOOR` (0.5), *before* the generic phrase table
is ever reached. Removing a phrasing from the generic table does not
remove the word itself from being a plausible mishearing target of a
*different* branch's verb. `test_walk_ahead_matches_end_to_end` pinned
`"walk ahead"` (a measured `ratio("walk","look")=0.5` mishearing)
resolving to `scan_ahead` via the now-removed `"look ahead"` phrasing.
After removing it, `"walk"` still clears `VERB_FLOOR` against `point`'s own
`"look"` verb (added by the same plan) at the identical 0.5 — the test
started asserting the *old*, now-wrong token.

This is the "missing entry" class the implementer role's own guidance
warns about: the plan's Tests section named every new-token case, but not
this interaction with a *pre-existing* test the vocabulary change silently
invalidates. The fix (update the test, with the new resolution explained)
was correct and intended by the plan's own direction (`look` must stop
aliasing `scan`) — but it would not have been caught without actually
running the full suite and reading the failure, not just reasoning about
it.

**How to apply:** whenever a plan removes or moves a `PHRASES` entry,
before declaring "unaffected," run the full `audio-adapter` test suite and
read every failure's own assertion, not just whether it passes/fails count
matches. A fuzzy matcher's failure surface moves when *any* phrasing moves,
not only the one token whose table changed.
