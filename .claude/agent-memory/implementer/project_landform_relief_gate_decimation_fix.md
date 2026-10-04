---
name: landform-relief-gate-decimation-fix
description: fix/landform-relief-gate -- relief gate + geometry decimation for geomorphons; a windowed deviation-check bug that silently neutered decimation
metadata:
  type: project
---

`WM-B6`'s geomorphons pipeline shipped two real defects against the user's own acceptance
criteria, found by checking the real `syria-full.sqlite` (8.1 GB) against
`plans/terrain-feature-probing/explore-notes.md`: no relief gate (89-92% of ridges/valleys under
50 m relief, Bekaa floor read as a valley) and ~16x-denser-than-DEM-justifies stored geometry
(Chaikin's 4-pass smoothing multiplies point count by exactly 16, never decimated back down).

Fix: `terrain.features.filter_by_relief` (new, `min_relief_m=50.0` — the *floor* of the user's
"maskable-behind" 50-150 m band, chosen deliberately over the band's middle so near-target
masking features in the 50-100 m range survive) and `terrain.features._decimate_for_storage`
(Douglas-Peucker via the already-existing `geometry.simplify_polyline`, same function OSM polygon
simplification already uses). Both are new `TerrainCacheMeta`/`ingest_terrain` knobs;
`EXTRACTOR_VERSION` bumped 1->2.

**The real finding, worth remembering generally**: the first working version of
`_decimate_for_storage` checked each original sampled point against only the *one* decimated
segment a Chaikin support-window happened to point it at (`distance_point_segment`), mirroring
the pattern `_smooth_for_storage`'s own (correct, pre-existing) windowed check uses. This was
wrong — a point near a genuine turn in a traced skeleton line can be far from its "assigned"
segment while sitting close to a *different* decimated segment on the same polyline. Measured on
real `syria-full` SRTM data: the windowed check reported 70-155 m deviations where the true
distance (`distance_point_polyline`, scanning every segment) was 15-30 m. The bug was *safe*
(it never let a bad decimation through — it was overly conservative) but it rejected ~92.5% of
real decimations, so the fix shipped with correct code that did almost nothing.

**Caught by**: not trusting the deviation-cap check passing as proof the feature worked. The
real built output's point-density reduction (36.7x expected from independent sampling) barely
moved (~1.03x) with the buggy check in place. A safety check passing is not the same evidence as
the feature doing its job — measure the actual effect size on real data, not just "no violations
reported."

**Fix**: check every original point against the *whole* decimated polyline, not a windowed
per-segment slice. Still cheap (O(len(original) * len(decimated)), and the decimated line is
always short — nowhere near the O(line_length^2) cost `plans/landform-geomorphons/performance.md`
already ruled out for the *smoothed* line).

See [[verify_rebuild_row_counts]] and [[verify_full_suite_not_just_new_files]] — this is the same
family of lesson: a passing check or a clean diff isn't the same as the real-data behavior being
what you expect. Measure the real number.
