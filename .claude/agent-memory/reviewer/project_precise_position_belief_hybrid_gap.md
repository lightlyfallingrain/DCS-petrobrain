---
name: precise-position-belief-hybrid-gap
description: precise-position-belief (stages 3-5, feature/binocular-optic) NEEDS REVISION — hybrid_source.py never got Stage 2's perturbation, so it still hands belief exact ground truth behind a cosmetic 300m band
metadata:
  type: project
---

Reviewed `plans/precise-position-belief/plan.md` stages 1-5 (commits `311d3d3`..`9ea9bce`, merged
via `feature/binocular-optic`). The covariance math, 2D Mahalanobis gate, `Contact.position`
refactor, and the `enrichment._terrain_aware_world_position` fix are all solid — verified by
hand-recomputing two of the tests' own numeric claims (the 900m two-isotropic-sides gate radius,
the down/cross gate-directionality geometry), not just reading docstrings.

**The one required finding: `perception/hybrid_source.py` was never updated to perturb.** The
plan's own diagnosis calls this channel "today's real omniscience hole... the strongest evidence
for the design," and Decision 2 recommends extending Stage 2's perturbation to it — but only
Stage 1's mechanical `PositionUncertainty(sigma_cross_m=300, sigma_down_m=300)` declaration
landed there (confirmed: `hybrid_source.py` still writes `bearing_deg=result.bearing_deg,
range_m=result.range_m` straight from ground-truth-derived `perception.association.associate`
output — no `perturbed_bearing_range` call anywhere in the file). Nowhere — not the plan file, not
either implementer's commit message, not `implementation.md`, not `ROADMAP.md` (which has *no*
entry for this milestone at all) — records Decision 2 as answered or deferred. It just silently
didn't happen. A heavily-observed scope-channel contact converges on exact truth with a cosmetic
uncertainty band, which is precisely the failure mode the plan exists to prevent, on the channel
the user actually flies with.

**Technique note for future reviews of a multi-channel perception change**: when a plan's Affected
Modules section lists two sibling source files needing "the same treatment," grep each one
directly for the new mechanism's own call site (here: `perturbed_bearing_range` or
`perception.estimation` import) rather than trusting that a shared Stage number implies both were
touched — the git history here showed only one file was ever modified after the mechanism landed,
which a diff-by-stage review would have caught immediately but a file-list check does not.

See [[m10-junction-review]] and [[group-detectability-roadmap-lag]] for prior missing-ROADMAP-entry
findings — this project's implementers repeatedly skip that step; check for it every review.
