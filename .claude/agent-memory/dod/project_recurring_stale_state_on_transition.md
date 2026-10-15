---
name: recurring_stale_state_on_transition
description: this defect shape -- state that should reset/carry on a transition and doesn't -- has now recurred across two separate features (BL-14's four instances, BL-B64's at least two more); raise it at Architect time for any "mode/phase with more than one field that should move together" feature, not only at Reviewer/Security
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

**Recommendation approved by the user**Recurred again, `BL-B64` (the 9K113 sight), 2026-10-15 -- now a two-feature pattern, not a
one-feature cluster.** At least two more instances of the same shape, in the same project area
(`belief/optic_policy.py`'s phase/mode state machine), caught by two different later roles:

5. `OpticState` is documented as "frozen and replaced rather than mutated," which reads as if
   every transition carries every field forward -- but two phase-entry branches construct
   `OpticState(...)` fresh rather than via `replace()`, so a newly added persistent field
   (`actual_aim_*`) silently reset to its default on exactly those transitions (caught by the
   Implementer's own test, per its own agent-memory note
   `feedback_decide_fresh_dataclass_construction_drops_fields.md`).
6. A pilot's "Observ off" command set `OpticState.home_phase` to `SCANNING`, but `decide()`'s
   `phase is SIGHTING` dispatch never read `home_phase` -- the two fields were assumed to move
   together once `phase` had already entered `SIGHTING`, and nothing enforced that. Found by
   Reviewer Pass 2 via direct reproduction (building the diverged state by hand), not by reading --
   every existing test happened to keep `phase`/`home_phase` in agreement, so the gap was invisible
   at the unit level.

**The category is now confirmed rather than merely suspected**: two unrelated features, both
built around a phase/mode state machine with more than one field that is supposed to move
together, each produced multiple instances of exactly this shape, and in both cases at least one
instance was caught only by a later role (Security or a Reviewer pass doing direct reproduction)
rather than by the Implementer or an earlier Reviewer pass. **Standing recommendation, now with two
data points behind it**: any Architect plan introducing or extending a phase/mode state machine
with more than one piece of state that must move together should name, as an explicit plan
section, every field that must track every other field's transition, and which construction/
dispatch sites are responsible for keeping them in agreement -- rather than leaving it to be
discovered per-field by whichever role happens to build the diverged state first.

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
