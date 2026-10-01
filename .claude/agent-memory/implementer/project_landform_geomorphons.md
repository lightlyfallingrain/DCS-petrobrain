---
name: landform-geomorphons-implementation
description: WM-B6 geomorphons build — plan cited the wrong spike's min_cells default; junction-walk is order-dependent not explicit pairing; M8 chunk pipeline had no geomorphons equivalent
metadata:
  type: project
---

Implemented `plans/landform-geomorphons/plan.md` (feature/landform-geomorphons, 4ba7c05).
Full numbers and reasoning in `plans/landform-geomorphons/implementation.md` — this memory is
the compressed, reusable lesson.

**A plan's own citation can point at the wrong reference file.** The plan said
`DEFAULT_MIN_LINE_LENGTH_CELLS` should be 3, citing `spike_geomorphons.py`'s naive tracer's
default — but the actual ported reference (`spike_junction_walk.py`'s `polylines()`) defaults to
4. Using 3 gave 448/418 ridge/valley lines against an accepted 312/273; using 4 gave 299/289 —
much closer. Always re-derive a cited default from the actual file being ported, not trust the
plan's citation at face value, even when the plan looks careful.

**A plan's prose description of a mechanism can be an idealization that doesn't match the real
reference code, even when both were "found" during planning.** The plan described the
junction-walk as "pair up incident branches by direction, greedy by smallest angular deviation."
The actual code (verified by porting verbatim and testing on isolated synthetic junctions) is
order-dependent: every degree-!=-2 node (endpoints AND junctions) walks into its own unused
neighbours in iteration order; a junction's edges go to whichever walk reaches them first. On a
real dense skeleton, long approach chains usually win the race before the junction's own loop
turn arrives (producing the continuous crests). On an isolated junction with no approach chain,
it just splits into N stubs. This is only discoverable by testing synthetic fixtures with NO
approach chain (a bare 3-arm or 4-arm junction) — testing only on real dense data hides it.

**When a plan rewrites a shared mechanism, grep for every caller, not just the one the plan
names.** The plan scoped the pipeline's main terrain stage but never mentioned M8's
`add_probe_chunk`, which called the now-deleted `ingest_terrain_chunk`. Found only by grepping
`ingest_terrain_chunk`/`ingest_terrain` across the whole tree before starting, per the
Implementer role's own "treat plan's test-impact list as hypothesis" instruction. Resolved by
removing the chunk-scoped extraction entirely (geomorphons' processing unit — a whole SRTM tile
with km-scale margin — has no sane chunk-sized equivalent) rather than forcing a bad fit.

**Vectorizing a reference pixel-loop algorithm (Zhang-Suen thinning here) must explicitly mask
the array border to match the reference's `range(1, n-1)` loop bounds.** A naive vectorization
using padded shifted-slice neighbours computes a (wrong) removal decision for border pixels the
original algorithm never touches. Caught by testing against a ported bit-for-bit reference on
synthetic masks — the real-data test alone didn't catch it (border mask happened to be empty
there).

See also: [Decouple test fixtures from tuned defaults](feedback_decouple_fixtures_from_tuned_defaults.md),
[Terrain feature probing watershed](project_terrain_feature_probing_watershed.md) (the predecessor
mechanism this replaced).
