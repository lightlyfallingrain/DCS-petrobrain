---
name: project_pb2_placeholder_constants
description: Known-placeholder tuning constants in belief/association_over_time.py, not yet calibrated
metadata:
  type: project
---

`body-layer/src/belief/association_over_time.py` has two constants explicitly declared
placeholders, documented as such in the code itself (not just implementation.md) as of Stage 1:

- `SCOPE_UNCERTAINTY_M = 300.0` — flat uncertainty radius for the scope/hybrid perception channel
  (it has no bucket/quantisation structure to derive an honest figure from, unlike naked-eye).
- `GATE_GROWTH_RATE_MPS = 20.0` — generic ground-vehicle order-of-magnitude speed (72 km/h) used
  as the spatial gate's elapsed-time growth term; not derived from any specific unit's real speed.

**Why:** the plan explicitly says not to overthink these now — "use a reasonable fixed uncertainty
and say so plainly in a comment... this gets revisited," revisit once real sessions show whether
contacts gate too tightly/loosely.

**How to apply:** do not treat these as tuned values in a future review; confirm they're still
flagged `Final` + docstring-placeholder if touched, and expect Stage 6 (live acceptance) or a later
calibration pass to be the place these get real numbers, not an unannounced change.

See also [[project_pb2_belief_invariants]].
