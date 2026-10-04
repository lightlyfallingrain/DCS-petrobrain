---
name: landform-relief-gate-review
description: fix/landform-relief-gate (WM-B6 relief gate + decimation fix) reviewed APPROVED clean; how the windowed-vs-whole-polyline regression test was independently verified, and a backwards-worded ROADMAP claim caught by comparing it to the implementer's own agent-memory file.
metadata:
  type: project
---

`fix/landform-relief-gate` fixed two real defects in the geomorphons ridge/valley pipeline (no
relief gate at all — Bekaa floor read as a valley; ~16x-over-dense stored geometry) and, during its
own verification, found and fixed a third bug: the first decimation deviation check compared each
original point against only the one decimated segment a Chaikin support window pointed at, instead
of the whole decimated polyline — safe (never let through a bad decimation) but neutered the fix
(92.5% fallback rate instead of the expected ~37x reduction).

**How I verified the regression test wasn't vacuous**: reconstructed the old windowed check myself
(nearest-segment-per-smoothed-point, `distance_point_segment`) and ran it against the exact
committed fixture (`N35E035.hgt` ridge fragment) from
`test_decimate_for_storage_checks_the_whole_decimated_line_not_one_segment`. It reproduced the
claimed magnitude: ~139.7 m measured (claimed range 70-155 m) vs. true whole-polyline deviation of
~15.9 m (claimed range 15-30 m) on the same points. This is the right way to check a "the old
version would have passed/failed differently" claim — reimplement the old version, don't just read
the new one's test.

**Caught a backwards-worded ROADMAP claim by cross-checking two documents written in the same
commit**: `world-model/ROADMAP.md`'s new entry said the windowed check "understated real deviation
by up to 5x," but the cited numbers (windowed measured 70-155 m > true 15-30 m) mean it
*overstated* deviation — consistent with "safe but neutered the fix" in the same paragraph and with
the implementer's own `.claude/agent-memory/implementer/project_landform_relief_gate_decimation_fix.md`,
which correctly calls the old check "overly conservative." Same author, same commit, two documents
disagreeing on the direction of a bug — worth comparing a roadmap/plan prose claim against the
agent-memory file for the same fix, not just against the code. Flagged as optional (prose only, no
code/test impact).

Also reconfirmed, independently: cache invalidation (constructed a stale `TerrainCacheMeta` missing
the new `min_relief_m`/`decimation_tolerance_fraction` keys → `load_cache_meta` returns `None`;
a mismatched value → `cache_meta_matches` returns `False`) and the `inspect_terrain.py` rewrite
claim (old tool drew raw `comp.points`, never applying smoothing/decimation at all — confirmed by
diff, not by the implementer's say-so). That last one matters beyond this branch: every terrain
render this project judged landforms by before this fix was showing something other than what gets
stored.

See [[landform-geomorphons-perf-fix-round3-approved]] and [[feedback_transform_confidence_verification]]
for the same family of technique (reconstruct the broken version yourself; don't trust a check
passing as proof of the fix's effect).
