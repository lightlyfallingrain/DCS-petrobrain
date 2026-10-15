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

**Recurred a third time, in a different shape, on `BL-B64` (the 9K113 sight)**: three more
instances in one feature -- a `decide()` branch constructing `OpticState` fresh instead of via
`replace()` and silently dropping new fields on every phase transition (caught by the
implementer's own test); the `phase`/`home_phase` divergence, where the `SIGHTING` dispatch
branch never read `home_phase`, so a pilot's "Observ off" didn't stop the sight for up to 30 s
while the readback said it had (caught only because a reviewer constructed the diverged pair by
hand -- no existing test built it, since every test set both fields consistently from the start);
and a field-of-regard bound declared in Stage 1 with a docstring deferring enforcement to Stage 2,
which then shipped without it (caught by Security executing the scenario). Seven instances across
two features now.

**Recommendation approved by the user (2026-10-15) and now in the Architect role file.** The
user's own words: *"any plan introducing a phase/mode state machine with more than one co-moving
field should name, in the plan, which fields must track which transitions -> good catch, approved,
fix please."* `.claude/agents/architect.md` step 6a (and its Output Format's Co-moving Fields
table) now requires this whenever a plan introduces a phase/mode state machine with two or more
co-moving fields, at least one externally written and at least one internally written; it is also
reflected in `docs/AGENT_ROLES.md`'s Architect section. **If this shape recurs after that step
exists, the gap is the step not firing (Architect skipped it, or the trigger didn't match a real
case), not that the rule is missing** -- check that before writing a fourth memory entry for the
same category.
