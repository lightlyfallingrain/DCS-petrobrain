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

**4th occurrence, a related but distinct mechanism (terrain-feature-probing, 2026-10-01):**
`core_fraction` was tuned to 0.1 while the valley geometry-extraction step had a real zigzag defect
— the tuning was unknowingly compensating for that defect, not expressing the intended tradeoff.
Fixing the geometry step changed the sinuosity at that *same* 0.1 value with no retune at all
(3.57 → 1.17), and a proper re-sweep against the fixed geometry then found a materially better
point (0.3) the broken geometry could never have reached. This is not "widening across several
Reviewer rounds because each fix was locally correct" (the pattern above) — it is "a tuning value
settled against a known-defective adjacent step is provisional, and inheriting it across a fix to
that step without re-sweeping is a trap," caught here by `implementation.md`'s own log, not by
Reviewer. Related enough to file alongside this pattern (both are "a tuned parameter's apparent
stability can be an artifact of something else nearby"), different enough to track separately if
it recurs again rather than conflating the two mechanisms.

**5th occurrence, and the first on a *defensive* set rather than a tuning one (`bl11-tick-cost`,
2026-10-06):** `logger._RESOLVE_FAILURES` took rounds 2 through 5 to settle — `OSError` →
`(OSError, ValueError)` → `+RuntimeError` → `+OverflowError` — with every round correct about the
input that motivated it and silent about the next one. Same shape as the word-list rounds, so the
pattern is not specific to tuning constants: **any enumerated set that grows one motivating case at
a time will take several rounds.** Two things finally ended it, both worth copying:

1. **Structural, not enumerative.** Round 5 put *every statement* in the closure under one `try:`
   with a per-statement comment of what each raises, so a fifth call added later is inside the guard
   by default. That is what stops round 6, not a better list.
2. **A counterfactual per entry.** Dropping each type in turn found `OverflowError` had no test at
   all — the argument for it was sound, but an argument is not a guard. This is now a NOTES.md entry.

**Prediction worth checking at the next occurrence:** the per-entry counterfactual is cheap and
would likely have compressed rounds 2–5 into one, because it asks "what else reaches this guard"
instead of "is this case handled". Consider asking for it at *Reviewer round 1* on any guard/set
widening, rather than waiting for the rounds to reveal the gaps.

**Why this matters at DoD stage**: when a plan or fix widens what a fixed set/threshold/window
accepts, do not treat a single review round's approval as strong evidence the widening is safe —
check whether the review log shows the fix was reproduced against a live run of the adjacent
subsystem (not just a hand-picked unit test), and if this pattern recurs a 3rd/4th time, it may be
worth raising at Architect stage (budget explicit adjacent-subsystem probing into the plan itself,
rather than discovering the need for it round-by-round at Reviewer).

See [[project_recurring_plan_test_file_naming]] and [[project_recurring_keyword_table_vocabulary_mismatch]]
for this file's other "raise at an earlier stage once it recurs" entries.
