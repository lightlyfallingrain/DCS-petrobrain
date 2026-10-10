---
name: widens-not-creates-remove-the-mechanism
description: To test an author's "this widens a pre-existing hazard rather than creating one", build the scenario with the new mechanism absent and see whether it still fires.
metadata:
  type: feedback
---

An author defending a behaviour change will often argue the hazard it enables is *pre-existing*.
That claim is checkable in one move and is almost never checked: **construct the failing scenario
with the new mechanism removed entirely.** If it still fires, they are right and scope is settled;
if it goes quiet, the fix created the hazard and "pre-existing" was framing.

**Why:** 2026-10-10, `BL-B47`. The implementer said widening `_is_air_defence` let a repeat callout
churn through `belief.callouts`' one-slot repetition guard, but that this "widens a pre-existing
mechanism rather than creating one" and the real fix was a scheduler change, out of scope. Reading
the loop could not settle it either way. Driving `render_group_disclosure` + `mark_group_spoken` in
`CalloutScheduler.tick`'s own sequence while oscillating a contact in and out of a group on
alternate ticks gave three answers in about ten minutes: one oscillator → one line then silence
(both before and after the fix); the new mechanism plus a second out-of-phase oscillator → 10 lines
in 10 ticks; **and two oscillators of two distinct classes with the new mechanism reverted → the
same 10 lines in 10 ticks.** The third run is the one that mattered: the ratchet predates the
commit, so the fix shipped, and the follow-up got filed against the *real* mechanism rather than
as a narrower item about the fix's own clause.

**How to apply:** for any "widens, not creates" or "bounded in principle" defence of a flagged
hazard —

1. Build the minimal scenario that makes it fire, driving the real call sequence (find the
   production caller and mirror its order; test helpers that mark state by hand will lie — passing
   a stale `differentiated=False` sent my first probe down a full-recomposition branch and produced
   output that looked like a flood and was a fixture bug).
2. Re-run it with the new mechanism reverted. That answers "pre-existing" directly.
3. Report the ingredient count, not just pass/fail: "needs two oscillators of distinct classes"
   versus "needs one plus any arrival" is the actual size of the widening, and it is what makes a
   filed follow-up scoped correctly.

The reverse also holds — if the probe shows the fix *created* the churn, "bounded in principle" is
not safe and the fix should not ship without a bound. Repetition is a defect class this project has
fixed twice and the pilot has complained about directly.

Related: [[project_bl_b47_air_defence_class_level_review]].
