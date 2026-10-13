---
name: forest-occlusion-gate5-candidate-count-unmeasured
description: forest-occlusion's cost argument rests on how many candidates reach the last gate (terrain-LOS-cleared) per poll, which has never been measured directly -- only bounded indirectly via other sorties' cumulative admission stats and the "earlier gates reject almost everything" finding.
metadata:
  type: project
---

`plans/forest-occlusion/plan.md`'s "Measured cost" section frames the uncached worst case as
"200 candidates x 0.075 ms = 15 ms" and leans on gate ordering (forest is gate 5, last, after
terrain LOS) to argue only a small surviving set ever pays for it. That ordering claim is true and
verified in code (`visibility.py:882`, after the terrain-LOS gate at :872-874) -- but **no sortie
has ever been flown with `GateOutcome.FOREST` in the trace**, so "how many candidates actually
reach gate 5 per poll" is not a number anyone has, only a bound reasoned from two other sorties:

- `body-layer/research/2026-10-05-performance-review.md` finding 3: the whole gate chain through
  terrain LOS costs 2.4 ms/poll (quiet) to 16-25 ms/poll (busy) for **all 440 raw candidates**,
  because "the earlier gates reject almost everything before the LOS query is reached" -- i.e.
  very few of the 440 actually reach the LOS check, let alone survive it.
- `docs/acceptance/2026-10-08-los-statics-population-sortie.md`: across one full sortie
  (280,782 trace rows, 403 distinct objects), only **85/403 (21%) were ever admitted at all**,
  cumulative over the whole flight -- not a per-poll concurrent count, which is necessarily far
  smaller.

Both point the same direction (gate 5's input population is small, nowhere near the 200-candidate
figure used as the plan's worst case), but neither is the actual per-poll number. **This is a
measure-n-before-scaling-by-n gap that the architect's own plan correctly identified as needing
Stage 4** (`plan.md` Risks: "cache hit rate is the one unmeasured term... Stage 4 measures it") --
but Stage 4 should also capture the gate-5 input population directly (a histogram of
"how many candidates per poll reached gate 5" alongside the cache hit/miss counts), not just the
cache hit rate in isolation, because the worst-case arithmetic depends on both.

**Second unverified input found during this review, same class of error as the already-caught
stale "5 Hz" figure:** the cache's hit-rate arithmetic also assumes ground units move at 10 m/s
(`forest.py` docstring: "a 50 m cell at 10 m/s takes 5 s to cross"). That number appears nowhere
else in this codebase or its docs -- it is an architect-authored assumption, not a measurement,
exactly like the 5 Hz poll rate was before the reviewer caught it. It happens to be a plausible
convoy speed, but it has the same epistemic status the bad number had before it was caught. Do
not treat "10 m/s" as checked; Stage 4's flown-trace cache hit rate measurement supersedes needing
this assumption to be right at all, so the fix is "measure the real hit rate," not "verify the
speed guess."

See [[feedback_static_cache_vs_belief_cache_eviction_asymmetry]] (reviewer's memory, same feature)
and the project's own standing lesson, "measure n before scaling anything by n," for the general
pattern this is one more instance of.
