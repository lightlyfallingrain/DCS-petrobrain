---
name: verify-reviewer-cited-thresholds-against-running-code
description: a review's required-fix prose can cite a numeric window that does not match the running formula -- recompute it yourself before placing a fixture inside it
metadata:
  type: feedback
---

On the `emitter-visibility` Stage A review fix (`BL-B72`), the required fix for the group-salience
non-interaction test (`test_emitter_does_not_widen_group_salience_for_a_non_emitting_neighbour`)
said to place the healthy neighbour "between `RESOLUTION_ANGULAR_RADIUS_RAD`'s and `LOWRES_
ANGULAR_RADIUS_RAD`'s thresholds (~5.4-9.3 km for a 7 m vehicle)". Computing the actual admission
formula directly (`size_m / LOWRES_ANGULAR_RADIUS_RAD * UNAIDED_OPTIC.presence_range_mult` vs the
same with `RESOLUTION_ANGULAR_RADIUS_RAD`) gives **2333.33-5468.75 m**, not 5.4-9.3 km. The "5.4"
half matched (it's `RESOLUTION`'s own range), but the review's other bound did not correspond to
anything in the running code I could find -- possibly a slip citing a different rung from the
calibration research doc.

**Why:** a required fix's prose is a hypothesis about where the code's actual boundary sits, not
the boundary itself. Placing a fixture by the stated numbers alone, without running the formula,
risks placing it outside the real discriminating window -- which is exactly the defect class this
fix exists to repair (a fixture that looks like it tests something but structurally cannot). The
red/green proof is what actually matters, not agreement with the cited numbers.

**How to apply:** when a review names a numeric threshold/window as the reason for a fixture
placement, recompute it from the cited constants and the real formula (one Python one-liner against
the venv) before writing the fixture. If it disagrees with the review's own figure, use the
measured one, and say so explicitly in `implementation.md` rather than silently matching the wrong
number or silently correcting it without comment. Then prove the placement works with an actual
red/green mutation test -- that is the only check that cannot be fooled by either party's arithmetic
error. See also [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]] and the
project CLAUDE.md "When you write 'because X', say what would make X false" guidance -- the same
discipline applies to a number handed to you by someone else's review, not only your own claims.
