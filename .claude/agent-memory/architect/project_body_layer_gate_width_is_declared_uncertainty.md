---
name: body-layer-gate-width-is-declared-uncertainty
description: body-layer's association gate width is dominated by the percept's declared position uncertainty, not by elapsed-motion inflation — so changing the growth rate (even to 0) does not change which percepts are ambiguous.
metadata:
  type: project
---

`association_over_time.passes_gate`'s width is the **sum of two covariances**, and in every
geometry measured so far the *declared look uncertainty* term dominates the *elapsed-motion
inflation* term. Measured 2026-10-13
(`plans/bounded-fold-displacement/scratchpad/probe_o2_motion_keyed.py`):

- Incident 2's two fresh infantry percepts have **3 passing gate candidates at a growth rate of
  2.0 m/s and still 3 at 0.0 m/s.** At 20 s unseen the inflation term is 40 m, on top of the
  fixture's 300 m `_FALLBACK_UNCERTAINTY_RADIUS_M`. Removing a 40 m term from a 300 m gate cannot
  un-ambiguate anything.
- `BL-B24`'s shape (two contacts **17 m** apart, reacquired after 120 s): a fresh percept passes
  **both** gates at 0.0 m/s growth, same as at 2.0 m/s. 17 m is far inside any declared look
  precision.

**Why it matters:** this refutes a whole class of plausible-sounding plan claims. Two were put to
this role as hypotheses in one dispatch — that the user's motion-keyed uncertainty direction
(observed-stationary ⇒ ~0 growth) would *reduce how often the within-group ambiguity fold fires*
and would *shrink `BL-B24`*. **Both are false, and both read as obviously true.** The motion-keyed
direction is right on its own terms — it fixes position **staleness** — but it must not be
sequenced as if it also fixed fold frequency or duplicate contacts.

**How to apply:** before claiming any gate-width consequence for a change to a growth rate, half
life or inflation term, print the two covariance terms separately and the resulting
`len(passing)`. The question "does this change which percepts are ambiguous?" is answered by the
candidate count, not by the rate. Same shape as
[[feedback_decompose_a_defect_into_its_terms]]: a comparison has two sides and the named one is
usually the minor term.
