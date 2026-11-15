---
name: project-correlated-range-error-gate-and-fold
description: Why a gate-width fix cannot cure a contact fold or split on one bearing, and the cross-optic rule that replaced "never share a field across optics" -- nested optic ladder, gate uncapped, fold capped at sigma_small/sigma_large (BL-B108, revised 2026-10-31)
metadata:
  type: project
---

On 2026-10-31 (`plans/relative-distance-grouping/plan.md`, `BL-B108`), belief's
association gate and fusion still treated every look's along-line range error as independent:
1.0σ redrawn per look plus a 0.4σ object bias, fused as independent.

Under that model **no gate width serves both cases**:
- **Too tight**: one group splits into several contacts.
- **Too wide**: two groups on one bearing fold into one. This is the BL-B104 1 s fold.

**Why:** the user's direction (answer 2) is that a repeat look from the same place gives the same
estimate. Only closing, line-of-sight rotation or a better optic improves it. Relative distance
between things seen together is far more precise than absolute range.

The planned fix:
- Range error is stable, held in smooth noise fields keyed by **look geometry**, not by object id.
- Belief carries a look anchor.
- Gate and fold use one helper (Bar-Shalom–Campo). ρ in the gate is evaluated on the same-object
  **hypothesis** geometry.

**REVISED same day (plan "Amendment 2026-10-31: cross-optic error model"):**
- The original rule "never share one noise field across optics" was wrong in the other
  direction. It made cross-optic looks independent (ρ = 0), and two later fixes then declared a
  belief-side ρ the noise never had.
- **The rule now: a nested optic ladder.** The tightest optic's error is the shared scene-cue
  part, and each coarser optic adds its own independent blur on top. Then
  ρ(o,p) = k_p/k_o = σ_small/σ_large, which is exactly the "no negative weight" boundary.
- **Gate**: uses the model ρ uncapped.
- **Fold**: caps the cross-term at min(along variance of either side). This is also what stops
  closing-fusion extrapolation once the range length scale is long.
- **Gate σ**: the look's σ is rescaled to the hypothesis range too, not only ρ.

**How to apply:**
- On any future duplicate-contact or fold bug on one bearing, check the correlation model before
  touching `GATE_SIGMA_THRESHOLD` or the floor. See [[project-association-gate-fragility]].
- Before adding a correlation between two sensors or optics, derive belief's ρ from the same
  decomposition that generates the noise. One function, read by both.
- An unaided memory against a binocular look has an **irreducible** ±σ_u·√(1−k²) mismatch. Do not
  "fix" a cross-optic fold that is inside it by raising belief ρ: that is the failed fix shape.
- Two distinct tunables are deliberate: `f` (which of two is further, within one look) and `a`
  (is this the thing I saw before, across looks). Do not merge them.
- See [[noise-field-sweeps-need-an-ensemble]] for how to measure any of this.
