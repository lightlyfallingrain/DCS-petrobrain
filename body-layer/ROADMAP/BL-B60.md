# BL-B60 — A misclassified fast mover is now tracked worse than before the fold-displacement bound

- [ ] **`plans/bounded-fold-displacement`'s fold-displacement bound (`[[BL-B58]]` option 2 /
  `[[BL-B59]]`) reads a contact's believed `plausible_speed_mps` as the ceiling on how far a fold
  may move its position. A unit that is genuinely moving faster than its believed class's speed
  row — the stated case being a misclassification, e.g. believed infantry that is actually
  something faster — is now tracked *worse* than it was before the bound existed, because the
  bound caps the fold at a rate below the unit's real speed and the position lags further behind
  with every repeat fold.** #status/open Measured by the Architect pass on `BL-B58`/`BL-B59`
  during `plans/bounded-fold-displacement/plan.md` §2b, filed as its own entry by the DoD pass
  2026-10-13 (`plans/bounded-fold-displacement/dod-check.md`) rather than left living only in the
  plan text.

  **The measurement** (`plans/bounded-fold-displacement/scratchpad/probe_o2_motion.py`, two
  infantry 200 m apart, genuinely translating, every look ambiguous):

  | truth speed | t=40 baseline (unbounded) | t=40 under the bound (k=1) |
  |---|---|---|
  | 2.0 m/s (= the believed class's own rate) | 12.5 m | **12.5 m — byte-identical** |
  | 8.0 m/s (4× the believed class rate — a misclassified unit) | 49.8 m | **104.2 m — worse** |

  **Why this is accepted rather than fixed here.** `plans/bounded-fold-displacement/plan.md` §10
  states it as the bound's one measured regression and a stated, not resolved, risk: the bound is
  exactly neutral when the association and the believed class are both right (the common case,
  confirmed byte-identical to baseline), and the cost falls specifically on the case where the
  belief itself is wrong. Two mitigations are already in place, not new ones this entry proposes:
  Stage 3.5's admission gate stays load-bearing at a 3× looser bound, which is this project's
  existing safety net for exactly an uncalibrated `_PLAUSIBLE_SPEED_MPS` row; and the
  classification fold itself should correct a wrong class belief over time, at which point
  `growth_rate_mps` re-resolves to the right row and the bound stops being wrong.

  **Why it is worth its own entry rather than living only in the plan.** It is a real, measured,
  reproducible, currently-unmitigated-beyond-the-two-items-above defect with a clear trigger (a
  misclassified fast mover under repeat ambiguous folds), not a hypothetical. This project's own
  convention files a defect of this shape its own entry (compare `[[BL-B57]]`, a comparably narrow
  gap in the same speed table) rather than trusting it to survive only as a risk paragraph in a
  plan nobody re-reads once the feature merges.

  **No fix proposed here.** The real fix is calibrating `_PLAUSIBLE_SPEED_MPS` against measured
  DCS unit speeds rather than stated assumptions (the table's own docstring already says so), or
  widening the bound's own table resolution so a sustained large unclamped residual over several
  consecutive folds is itself evidence the believed class is wrong and should trigger a
  re-classification nudge rather than a continued clamp at the wrong rate. Neither is scoped or
  decided; this entry exists so the risk is findable and trackable rather than requiring someone
  to have read `bounded-fold-displacement/plan.md` §2b/§10 to know it exists.

  **What would surface it on a sortie**: a fast-moving unit (e.g. a truck column moving at speed,
  or any unit the naked-eye channel's own classification holds at a slower class than it actually
  is) that is repeatedly folded within a group and whose position visibly lags well behind its
  true location — more than the pre-bound behaviour would have shown. Watch for this specifically,
  not generically, the first time this branch flies.

  Related: [[BL-B58]] (the absorption half the same bound fixes), [[BL-B59]] (the eviction half),
  [[BL-B51]] (the one-table rule this bound is built to honour, which is why there is no second
  copy of the speed table to fix in isolation).
