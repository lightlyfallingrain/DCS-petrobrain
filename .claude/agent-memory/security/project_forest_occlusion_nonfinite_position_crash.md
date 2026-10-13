---
name: forest-occlusion-nonfinite-position-crash
description: ForestOcclusion._cache_cell_key's math.floor(x/grid) raises ValueError/OverflowError on a NaN/Inf candidate position, which only the plain (non-console/crew-text) poll loop has no guard against -- required fix, NEEDS FIXES verdict on plans/forest-occlusion.
metadata:
  type: project
---

`body-layer/src/perception/forest.py`'s `ForestOcclusion.occluded(x, z)` calls
`_cache_cell_key`, which does `math.floor(x / grid)` with no finiteness check. Reproduced live:
`math.floor(float('nan')/50.0)` raises `ValueError`, `math.floor(float('inf')/50.0)` raises
`OverflowError`. `candidate.x/z` is raw `LoGetWorldObjects` ground truth with no finiteness
validation anywhere upstream (`aircraft-layer/src/schema/world_objects.py`,
`body-layer/src/perception/association.py` -- grepped, neither validates). Every earlier gate in
`check_visibility`'s chain only does float *arithmetic* on `candidate.x/z` (bearing, range), which
is nan/inf-safe by IEEE-754 accident -- comparisons with NaN are always `False`, never raise. This
new gate is the first point in the whole chain where a non-finite position stops being silently
tolerated.

**Why this is not theoretical on this project specifically**: `belief/position_belief.py`'s
`clamp_fold_displacement` (merged the same session, `BL-B58`/`BL-B59`,
`plans/bounded-fold-displacement/`) added an explicit `math.isfinite` guard for the identical shape
of input one layer downstream (fused belief positions), with the reasoning *"that is caller
ordering, not a property of this function, so the guard is explicit here rather than borrowed."*
The same judgment applies here, one layer further upstream, where nothing has ever clamped the
value -- this is the un-hardened predecessor of the exact hazard the belief layer just got burned by
and fixed.

**Blast radius asymmetry, which is what made this a required fix rather than a note**: the
`--console`/`--crew-text` poll loops each wrap one poll cycle in a broad
`except Exception: logger.exception(...); continue`, so a raise there is logged and the sortie
continues. `main()`'s **plain** path (no `--console`, no `--crew-text` -- the simplest invocation in
the module's own docstring) has `while True: perception_logger.run_once(); ...` with only
`KeyboardInterrupt` caught. An uncaught exception from this gate kills the whole perception logger
process there, on a single malformed position, for the rest of the sortie -- and `--forest-occlusion`
Stage 2's entire purpose is to fly with the flag on.

**How to apply**: any new gate/cache in this detection chain that does integer-converting arithmetic
(`math.floor`, `int()`, `round()` fed into further indexing) on a position field sourced from
`LoGetWorldObjects`-derived ground truth must guard with `math.isfinite` before that conversion --
do not assume upstream validates it, because nothing does, and do not assume the plain poll loop will
catch the raise, because it won't. Treating the non-finite case as "not occluded" (fail open) matches
this gate's own existing philosophy (`None` landcover is not forest) rather than needing a new
failure mode.

See [[feedback_static_cache_vs_belief_cache_eviction_asymmetry]] for the other finding on this same
object (`ForestOcclusion._cache`'s unbounded-by-cell-key dict), which was correctly *not* a required
fix -- a different axis of the same review.
