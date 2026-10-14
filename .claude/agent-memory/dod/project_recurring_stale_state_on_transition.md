---
name: recurring_stale_state_on_transition
description: BL-14 alone produced four separate "state that should reset on a transition/identity change silently didn't" findings across its review cycle -- a category, not a one-off
metadata:
  type: project
---

`BL-14` (the attack run) accumulated four distinct instances of the same defect shape before it
ever reached DoD, each caught by a different reviewer pass rather than by one systematic check:

1. `drain_attack_run` committed `last_spoken_*` state as if a line had been spoken, even when
   channel occupancy suppressed the print (Reviewer, Stage 4-5 pass).
2. `drop target`/the generic cancel path cancelled the standing task but left
   `runner.attack_run_state` non-`None`, so the gaze claim and the "engaged" flag survived past the
   run's own end (same Reviewer pass).
3. A stale `attack_target` task silently remained "the" active one after re-selecting a different
   target with no intervening cancel -- every reader of "the current target" kept resolving to the
   oldest task, not the one the readback had just confirmed (Security deep analysis).
4. `AttackRunState.last_known_target_alt_m` carried the *previous* target's remembered altitude
   into the *new* target's first tier-2 tick after a mid-run re-point, because the field is
   run-level, not keyed to contact identity (Security fix review, found while verifying fix #3).

**Why this is a category, not bad luck**: every one of the four is the same shape --
some piece of state meant to describe "the current X" has a lifetime that does not actually track
X's identity, and nothing enforces that the two must move together. The fourth was found only
because a reviewer called the pure decision function directly instead of trusting the wrapper
(see `feedback_run_the_card_utterances_through_the_matcher.md`-adjacent lesson: call the thing
that actually decides, not the thing that wraps it).

**Process signal, not just a code pattern**: this recurred four times in one feature's review
cycle alone, caught progressively later each time (Reviewer -> Security -> Security-fix-review).
A cheaper earlier check -- at Architect or Implementer time, asking explicitly "which state here
is scoped to the lifetime of a selected/engaged target, and what resets it when that identity
changes?" -- would plausibly have caught #2-#4 as one audit rather than three separate discoveries.
Worth raising at Architect for any future feature with a "selected/active X" concept (next
candidate: `BL-B62`/`BL-B63`, the group-view/fast-lane work, both of which will have their own
notion of "the current target").
