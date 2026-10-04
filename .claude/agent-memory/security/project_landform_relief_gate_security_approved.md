---
name: landform-relief-gate-security-approved
description: WM relief-gate/decimation fix verified fail-closed cache invalidation and correct decimation deviation-check direction; APPROVED 2026-10-04.
metadata:
  type: project
---

`fix/landform-relief-gate` (tip `01a36c3`) added a relief gate (`filter_by_relief`, 50 m default)
and Douglas-Peucker decimation (`_decimate_for_storage`) to the geomorphons ridge/valley pipeline,
plus two new `TerrainCacheMeta` knobs and `EXTRACTOR_VERSION` 1→2.

Independently verified (not just re-reading the Reviewer's claim):

- Cache fail-closed: `reader.load_cache_meta` returns `None` on the first missing `META_FIELDS`
  key, so a v1 cache (no `min_relief_m`/`decimation_tolerance_fraction` rows at all) always forces
  a full rebuild. `cache_meta_matches` is exact per-field equality over
  `_INVALIDATION_KEY_FIELDS`, no partial match. `EXTRACTOR_VERSION` bump is redundant
  belt-and-suspenders on top of this, confirmed by reading the code rather than the comment.
- `_decimate_for_storage`'s deviation check is checked in the safe direction: it checks every
  *original* sampled point against the *whole* decimated polyline and only accepts the decimation
  if all points stay within `cap_m`; otherwise falls back to the unmodified smoothed geometry. The
  tip commit (`01a36c3`, "the deviation check overstated, it did not understate") was a ROADMAP
  wording fix only — no code changed in that commit.
- Douglas-Peucker is worst-case O(n²); confirmed via a direct adversarial zig-zag test
  (5000 points, no reduction, ~2.3s). Not a finding: this is offline, build-time, SRTM-DEM-derived
  input on the user's own single-player machine, not adversarial/external input, and Chaikin
  smoothing upstream structurally damps the kind of alternation that triggers the worst case.

No new dependency (`pyproject.toml` diff against `main` empty; decimation reused the existing
`geometry.simplify_polyline`).

See [[project_terrain_cache_resumable_fail_closed_approved]] for the prior WM-B6 cache
fail-closed pattern this extends, and [[project_store_writer_fail_closed_geometry_guard]] for the
project's established "fail-closed on bad geometry" convention this fix is consistent with.
