---
name: project-osm-landcover-optimization-minor-fixes
description: osm-landcover-optimization (Stages 0-8) reviewed APPROVED WITH MINOR FIXES — ROADMAP entry missing, hole/outer-ring topology unchecked after independent simplification
metadata:
  type: project
---

Reviewed 2026-09-13, commit `26d4e4c` (review commits `18b724e`, then re-derived independently and
re-committed at `ed9b6fb`/`2bf71ab` after a fork-related session restart lost the first pass's
context — both independent passes converged on the same two substantive findings below, which is
itself useful signal that they're real). Everything the plan claimed checked out on direct reading
(not just trusting implementation.md): D3 ring/hole pipeline order, D5 coastline sign convention
(independently verified against real Latakia-coast geography, not just internal self-consistency),
tags-filter drift test genuinely derived from classifier constants (not a hand-copied table),
streaming/cache bounds, and consumer contracts across body-layer/mission-interpreter
(mission-interpreter reads the API JSON via `.get()`, not attribute access, so schema changes can't
break it — worth remembering as a reason MI checks were legitimately skipped, not just "didn't get
to it").

Three required fixes found (final verdict: APPROVED WITH MINOR FIXES):
1. **`world-model/ROADMAP.md` had zero entry for the milestone** — plan's own Stage 8 explicitly
   required one, implementation.md's Stage 8 file list silently omitted it. Worth grepping
   `git diff <base>..HEAD -- <subproject>/ROADMAP.md` directly on every review from now on rather
   than trusting the implementer's "Files Changed" list — a step can be planned and simply not
   land, with the implementation summary never mentioning the gap either.
2. **No containment check that a hole stays inside its outer ring after each is independently
   Douglas-Peucker-simplified.** Real, bounded risk (~2×tolerance worst case, here ~60m, dominated
   by this pipeline's 1300m `position_uncertainty_m`), no crash risk, real Stage 6 data (15 real
   kept holes) showed no anomaly — but explicitly one of the review brief's "look hard at" items,
   and the *only* silent (uncounted) drop/anomaly path in a module whose own docstring promises
   "never a silent drop." Pattern to watch for elsewhere: independent geometric transforms applied
   to logically-related rings/features with no cross-check afterward. **Self-correction note**: on
   the second pass I first wrote this up as merely "optional" (bounded magnitude, no observed
   anomaly), then on re-reading my own draft caught that it violates this exact module's own stated
   invariant ("never a silent drop") and upgraded it to required before committing — bounded
   magnitude affects the fix's cost/urgency, not whether a stated invariant was actually violated;
   don't conflate the two when assigning severity.
3. **Stale docstring** (`store/reader.py`'s `nearest_feature`) still described the removed
   `nearest_road_osm` field as if it were live — minor, but ironic given the plan's own stated
   reason for removing the field outright rather than leaving it always-`None` was exactly to avoid
   inviting confusion like this.

See [[feedback_verify_pipeline_wiring_not_just_module]] — same spirit here: verify the *plan's own
required deliverables list* landed, not just that the code that did land is correct.
