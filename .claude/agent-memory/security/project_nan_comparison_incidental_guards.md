---
name: project-nan-comparison-incidental-guards
description: body-layer's position_belief.py clamps rely on NaN-comparison semantics (any comparison with NaN is False) as an undocumented safety net -- check this pattern specifically when reviewing new clamps/guards added to that module.
metadata:
  type: project
---

`body-layer/src/belief/position_belief.py`'s `clamp_to_detection_envelope` holds the prior cleanly
when the fused mean is NaN, purely as a side effect of `range_m(...) <= max_range_m` evaluating
`False` for NaN in Python (any comparison with NaN is `False`, never raises). This is not
documented as a NaN guard anywhere in that function's docstring -- it is incidental.

`clamp_fold_displacement` (added by `plans/bounded-fold-displacement/plan.md`, `BL-B58`
option 2 / `BL-B59`) does **not** get the same protection: its own comparison
(`displacement_m <= max_displacement_m`) also evaluates `False` for NaN, but the branch it falls
into then computes `scale = 0.0` and `dx * scale`, which is `NaN * 0.0 = NaN` in IEEE 754 -- so it
writes NaN into the adopted position rather than holding clean. Found 2026-10-13 during that
feature's security deep analysis (`plans/bounded-fold-displacement/security-review.md`); rated
low-probability/low-impact and not blocking, because the one real call site
(`Contact.record`) always runs `clamp_to_detection_envelope` first and that call scrubs NaN before
`clamp_fold_displacement` ever sees it -- but the protection is borrowed from caller ordering, not
a property of the function itself.

**How to apply:** when reviewing any future change to this module (a new clamp, a reordering of
the two existing clamps, a new direct caller of `clamp_fold_displacement` such as a test fixture
or a second call site), check explicitly whether a NaN/non-finite mean is handled by design
(an `math.isfinite` guard) or only by accident (a comparison that happens to be False for NaN
followed by a further false branch). The two existing clamps in this file demonstrate both
outcomes side by side, so they're a fast first place to look.
