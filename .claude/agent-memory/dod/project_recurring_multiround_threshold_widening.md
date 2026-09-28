---
name: recurring-multiround-threshold-widening
description: Widening a fixed set/threshold/window (word lists, confidence floors, time windows) tends to take several review rounds, each correct on its motivating case and wrong just outside it
metadata:
  type: project
---

`confirm-band-affirmatives` (2026-09-28) took five Reviewer rounds to safely widen
`_AFFIRM_WORDS`/`_NEGATIVE_WORDS` and `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S`. Each round's
fix was correct about the exact case that motivated it (a real reproduced swallow/collision) and
wrong just outside that case, and every round was actually found by constructing a real transcript
and running it through the live matcher — never by reading the widened set and reasoning about it.

This is the same shape NOTES.md's `ACT_FLOOR`/match_ratio entry and the shutdown-race entry already
describe from earlier features — this is at least the 2nd/3rd occurrence of "verify a
threshold/window widening by running the real adjacent subsystem end to end, not by inspection."

**Why this matters at DoD stage**: when a plan or fix widens what a fixed set/threshold/window
accepts, do not treat a single review round's approval as strong evidence the widening is safe —
check whether the review log shows the fix was reproduced against a live run of the adjacent
subsystem (not just a hand-picked unit test), and if this pattern recurs a 3rd/4th time, it may be
worth raising at Architect stage (budget explicit adjacent-subsystem probing into the plan itself,
rather than discovering the need for it round-by-round at Reviewer).

See [[project_recurring_plan_test_file_naming]] and [[project_recurring_keyword_table_vocabulary_mismatch]]
for this file's other "raise at an earlier stage once it recurs" entries.
