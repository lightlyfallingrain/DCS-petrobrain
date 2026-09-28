---
name: confirm-band-affirmatives-grace-swallow
description: fix/confirm-band-affirmatives (c33739e, 2471542) review outcome — two rounds, over-acceptance then under-acceptance, same root cause
metadata:
  type: project
---

Reviewed `fix/confirm-band-affirmatives` (body-layer) across two rounds, fixing the 2026-09-26
"cancel" -> "confirm?" -> "yes"/"confirm" -> "Unable, no such command." sortie defect.

**Round 1 (`c33739e`)**: widened `_AFFIRM_WORDS`/`_NEGATIVE_WORDS`, raised `CONFIRM_WINDOW_S`
8.0->15.0, added `CONFIRM_LATE_ANSWER_GRACE_S` (20.0). Found by direct reproduction: `classify_
yes_no` matched only the transcript's *first word*, so the widened set (now including "ok"/
"okay"/"correct"/"yeah") let an unrelated fresh utterance ("okay watch that truck at three
o'clock", 5s after an expired confirm) get swallowed as a late answer, returning "Say again?" and
dropping a real tactical report. Also falsified a "cannot collide with any command" safety claim
stated twice (docstring + `todo/todo.md`). NEEDS REVISION.

**Round 2 (`2471542`)**: fixed at the classifier, not the grace branch — `classify_yes_no` now
requires *every* word of the transcript to be an answer word or a closed filler
(`that`/`sir`/`copy`/`please`), refuses mixed answers ("yes no" -> "other"). This was the right
call over my suggested narrower fix (gate only the grace branch on length) because the same
first-word hole existed *inside* the open confirm window too (a pending confirm answered "okay
scan left" would have committed the stale command). Verified the original repro now falls
through correctly.

**But found a new required fix by direct reproduction, in the opposite direction**: the
whole-transcript rule now *rejects* short, plausible elaborated answers that add one word beyond
the closed filler list — `classify_yes_no("yes do it")`, `"affirm execute"`, `"roger wilco"`,
`"yes go ahead"` all return `"other"`. Inside the open window, "other" silently discards the
pending command (Decision 4 Layer 3's existing design) with zero feedback — worse than the
original "Unable" defect for exactly the command class that matters most (cancel). This directly
contradicts the fix's own stated design intent ("a real answer here is one or two words" — "yes
do it" is three, and is a real answer). Recommended a length-based heuristic (first word is an
answer word AND word count small, e.g. <=3-4) instead of "every remaining word must be filler."

**Pattern worth naming**: fixing an over-acceptance bug by narrowing a classifier with a *closed
list* (filler words, in this case) is a natural move, but closed lists have a matching failure
mode in the opposite direction — they reject anything not enumerated, including things the
implementer's own stated design intent says should pass. When reviewing a narrowing fix, always
generate a few short, on-topic (not just adversarial/unrelated) test inputs and run them through
the changed function directly, not just the fix's own tests (which naturally only cover the
inputs the fix was written to handle). Both rounds of this feature were caught the same way:
direct reproduction against the raw classifier/console call, not by reading the diff.

See [[feedback_bounded_magnitude_isnt_optional_severity]] — both findings were flagged Required
because they contradict a stated invariant/design intent, not merely because the worst case was
large.
