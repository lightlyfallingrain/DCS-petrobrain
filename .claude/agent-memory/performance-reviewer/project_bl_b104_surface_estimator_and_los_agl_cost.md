---
name: project-bl-b104-surface-estimator-and-los-agl-cost
description: Measured per-call costs of body-layer's hash-seeded perception estimators (surface_range_estimate 3.9us, perturbed_bearing_range 2.3us, surface_domain 0.14us) and the BL-B104 LOS-hook AGL addition shape -- use before flagging a new per-cluster estimator draw as a risk
metadata:
  type: project
---

Measured 2026-10-30 on `feature/bl-b104-ground-contacts-on-ground` (tip 0c2a1792). Each value is
the mean of 20 000 calls on the body-layer venv:

- `perception.estimation.surface_range_estimate`: **3.9 µs** (three sha256-seeded Box-Muller
  draws plus trig)
- `perturbed_bearing_range`: **2.3 µs**
- `perception.domain.surface_domain`: **0.14 µs**

So one deterministic `_deterministic_unit_gaussian_pair` draw costs roughly 0.7–1 µs. A new
per-cluster or per-candidate draw is negligible against the 1.0 s poll unless it runs per pair
(O(n²)).

**Why:** without these numbers, a reviewer is tempted to flag "sha256 per look" as a hot-path
cost. It isn't one at realistic cluster counts (tens).

**How to apply:**
- The LOS Hook (`petrobrain-line-of-sight-hook.lua`) now makes one `land.getHeight` per wedge
  candidate. The cap is 128 per poll, and the call sits beside two raycasts per candidate.
- Its cost was not measured in DCS. `bridge_call_ms` on the wire is the instrument for that.
  Check it before claiming the hook got slower or faster.
- Harness note: to benchmark body-layer `src/` from a worktree with the main checkout's venv, set
  `PYTHONPATH=../world-model/src` (perception imports `coordinates`) and assert that
  `module.__file__` resolves into the worktree.

Related: [[project_9k113_search_and_choose_look_scaling]], [[project_report_query_enrichment_dominates]]
