---
name: project-correlated-range-error-gate-and-fold
description: Why a gate-width fix cannot cure a contact fold or split on one bearing. The independent-looks error model is the cause, and the fix is a correlated error with gate and fold sharing one innovation covariance (BL-B106, 2026-10-31)
metadata:
  type: project
---

On 2026-10-31 (`plans/relative-distance-grouping/plan.md`, `BL-B106`), belief's
association gate and fusion still treated every look's along-line range error as independent:
1.0σ redrawn per look plus a 0.4σ object bias, fused as independent.

Under that model **no gate width serves both cases**:
- **Too tight**: one group splits into several contacts.
- **Too wide**: two groups on one bearing fold into one. This is the BL-B104 1 s fold.

**Why:** the user's direction (answer 2) is that a repeat look from the same place gives the same
estimate. Only closing, line-of-sight rotation or a better optic improves it. Relative distance
between things seen together is far more precise than absolute range.

The planned fix has three parts:
- Range error is stable, held in smooth noise fields keyed by **look geometry**, not by object id
  (so membership churn cannot jump it), with per-optic seeds.
- Belief carries a look anchor on `PositionEstimate`.
- Gate and fold share **one** innovation covariance, using Bar-Shalom–Campo fusion of correlated
  estimates. ρ in the gate is evaluated on the same-object **hypothesis** geometry.

**How to apply:**
- Any future duplicate-contact or fold bug on one bearing: check the correlation model before
  touching `GATE_SIGMA_THRESHOLD` or the floor. See [[project-association-gate-fragility]].
- Never share one noise field across optics. Fusing two fully correlated estimates of unequal σ
  extrapolates past both and recovers truth, which is omniscience by arithmetic.
- Two distinct tunables are deliberate: `f` (which of two is further, within one look) and `a`
  (is this the thing I saw before, across looks). Do not merge them.
