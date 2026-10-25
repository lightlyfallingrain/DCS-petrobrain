---
name: project_wake_word_cancel_interaction
description: AA-B7 wake-word fix bypasses cancel_nevermind retraction for wake-prefixed transmissions -- flagged, judged acceptable, not pinned by a test
metadata:
  type: project
---

`audio-adapter/src/command_matcher.py`'s `opens_with_wake_word` check (AA-B7, 2026-10-25) returns
`verb_anchored=False` immediately on any transcript opening with `[hey, ]petrovich`, before any
other branch -- including the one that would otherwise resolve `cancel_nevermind` from a trailing
"never mind"/"disregard". So `"Petrovich, where are we, never mind"` now routes the *whole*
utterance to the brain as free text; the retraction is never seen by body-layer's
`cancel_nevermind` machinery.

**Why this was judged acceptable, not a required fix**: pre-fix, the same transmission almost
certainly already failed to resolve `cancel_nevermind` too (a 2-word phrase scored by
`_phrase_match_ratio` against a much longer sentence falls well under `MATCH_FLOOR`), so the
observable change is one failure mode (say-again) swapping for another (unobserved retraction),
not a working case regressing. `vocabulary.py`'s "every decision happens at PTT release, with no
exceptions" is a statement about *command* decisions -- a wake-prefixed utterance is, by the
user's own 2026-10-25 decision, never a command attempt, so there is no command decision here for
`cancel_nevermind` to retract.

**Why it's worth remembering**: this interaction was not addressed by the user's decision text and
has no test (`plans/aa-b7-wake-word/review.md`, "Optional Refinements"). If `[[AA-B4]]`
(positional verb anchoring) or any future change to the wake-word branch's position touches
`match_transcript`'s branch order, re-check whether a wake-prefixed "..., never mind" is still
silently absorbed into the brain path, and whether that is still the right call once the brain
side of this route actually exists and can be observed in a live flight.
