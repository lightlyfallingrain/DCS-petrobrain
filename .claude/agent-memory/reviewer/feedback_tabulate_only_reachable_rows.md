---
name: tabulate-only-reachable-rows
description: Before tabulating a defect across a range sweep, check the detectability envelope per row — an unreachable row inflates the severity and can turn an accepted edge into a false required fix.
metadata:
  type: feedback
---

**Before writing a severity table across a range sweep, check each row is reachable.** A row the
unit type cannot occupy does not merely add noise — it sets the headline magnitude, and the reader
(including the user) prices the finding off the worst row.

**Why.** 2026-10-11, BL-12 Stage 0: this role tabulated a cohesion-cap defect at 2/3/5/7 km with
failure probabilities up to ~77 %. The user corrected the premise — infantry (`size_m=1.8`) cannot be
held past **1,406 m** unaided or **3,403 m** under binoculars, and the 9K113 that could see it
further **is not implemented**. The 5 km and 7 km rows described a regime no infantry contact can
occupy, so the finding's real scope was one band under one deliberately-raised optic. The required
fix survived; its magnitude did not, and the decision came back *"we only really need to consider it
at close range"* rather than a retune.

It reaches further than one review. The same 6 km figure in `BL-B48`, the plan amendment and the
round-1 review all came from **a fixture that placed contacts where no optic could see them** —
three documents reasoning from a severity that was an artefact of the fixture, with nobody asking
whether a pilot could be in that scene.

**How to apply.** In body-layer, the envelope is one call, not arithmetic on quoted constants:

```python
visibility.tier_ranges(presence_size_m=…, recognition_extent_m=…,
                       optic=…, group_salient=…)   # keyword is group_salient
```

Run it over **both optics × both salience values** and drop every row beyond the ceiling before
tabulating. Check which optics actually exist first — `vars(optics)` held exactly two `Optic`
instances, and assuming a third is what made the long rows look live. Where a fixture exhibits the
defect, say so: **the detectability envelope belongs in the fixture's own assertions**, or the next
reader inherits the inflated number.

See also [[feedback_clamp_structural_vs_measured_residual]] (a ratio right and an absolute value
wrong), [[feedback_bounded_magnitude_isnt_optional_severity]] (the converse — do not downgrade a
*reachable* bounded risk), and [[project_bl12_stage0_round2_approved]].
