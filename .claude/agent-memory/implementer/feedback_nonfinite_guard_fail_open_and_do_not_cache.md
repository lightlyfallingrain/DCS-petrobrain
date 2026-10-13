---
name: nonfinite-guard-fail-open-and-do-not-cache
description: When fixing a math.floor/int()-raises-on-NaN/Inf security finding on a position field, fail open (not occluded/not rejected) to match the gate's existing philosophy, skip caching the non-finite case, and enumerate operands+return paths explicitly in the report even when the review's own enumeration turns out complete.
metadata:
  type: feedback
---

Implemented the forest-occlusion security fix (`plans/forest-occlusion/security-review.md`'s one
required fix, `body-layer/src/perception/forest.py`'s `ForestOcclusion.occluded`) and the shape
generalizes: this is the **second** instance of this exact hazard in one session, after
`belief/position_belief.py`'s `clamp_fold_displacement` (`BL-B58`/`BL-B59`). Likely a recurring
pattern on this project, since `candidate.x/z` (raw `LoGetWorldObjects` ground truth) reaches many
gates and nothing upstream validates finiteness.

**The fix shape:**
1. Guard with `math.isfinite(x) and math.isfinite(z)` *before* any `math.floor`/`int()`/`round()`
   call on the position.
2. **Fail open, not fail closed** — return "not occluded"/"not rejected", matching whatever this
   particular gate already does for its own "unknown" case (here: `None` landcover is not forest,
   Decision 2). Do not invent a new failure posture; find the gate's existing one and mirror it.
3. **Do not cache the non-finite result.** The cache key is usually derived from the same
   `math.floor` call the guard exists to avoid, so computing a cache key for a non-finite input
   defeats the guard. A non-finite input also has no stable "cell" to recur at the way a real
   position does (sensor glitches don't repeat at the same NaN), so there's no steady-state benefit
   to caching it anyway. State this reasoning explicitly in the docstring/report rather than
   silently choosing one way — the task brief for this fix asked for the reasoning either way, not
   just the choice.
4. **No DB query either** — the guard should return before any expensive lookup, which a
   call-count assertion against a monkeypatched DB-reading function proves cheaply.

**How to apply the "enumerate every operand and return path" instruction when the review's own
enumeration already turns out complete.** `clamp_fold_displacement` was a documented case of the
review's enumeration being *wrong* (found incomplete twice: one of two operands, then a skipped
return path). Here it was already complete — `_cache_cell_key` has exactly two operands (`x`, `z`)
and `occluded` has exactly one call site into it, confirmed by `grep -n "math\.\|int(\|round("` +
`grep -n "_cache_cell_key"` over the whole module. **Report the enumeration and its result either
way** — "I checked and it was already complete" is still the answer to "is the guard complete",
not a no-op. Don't let a review that happens to be right train you into skipping the check.

**Test shape that mutation-caught cleanly**: one parametrized test over
`nan`/`inf`/`-inf` × {x alone, z alone} plus one "both bad" case (7 parametrize entries), asserting
`False` returned, no raise, and `call_count == 0` on the DB-reading function. Plus one separate
test asserting the cache dict stays empty after repeated non-finite calls. Removing the guard line
and reverting via `shasum` before/after is the cheap, convincing way to prove these tests are real
(all 7+1 went red with the exact `ValueError`/`OverflowError` the review named, pre-existing tests
in the same file stayed green).

See [[project_forest_occlusion_nonfinite_position_crash]] (security's memory) for the finding
itself and why `belief/position_belief.py` was the precedent that made this "not theoretical."
