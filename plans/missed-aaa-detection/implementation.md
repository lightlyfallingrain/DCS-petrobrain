### Implementation Summary

Implements option 1 of `plans/missed-aaa-detection/debug.md`: a global elevation-uncertainty
tolerance on world-model's terrain line-of-sight check (`query.line_of_sight.line_of_sight_clear`).
Terrain now blocks only when it exceeds the sightline altitude by more than 12.0 m, instead of by
any amount at all. 12.0 m is M7's own recorded SRTM-vs-DCS stddev (11.52 m), rounded up.

### Files Changed
- `world-model/src/query/line_of_sight.py` — added `_TERRAIN_TOLERANCE_M = 12.0` module constant
  and changed the blocking comparison from `terrain_m > sightline_alt_m` to
  `terrain_m > sightline_alt_m + _TERRAIN_TOLERANCE_M`. Applied uniformly to every interior sample
  (no separate near-target exclusion widening — debug option 2 is redundant with option 1 and was
  not applied). The constant's comment records: the M7 stddev it derives from and where that was
  measured; that it is a refusal to trust the grid past its own measured precision, not a fudge
  factor; the accepted cost (a target masked by a real ridge clearing the sightline by less than
  12 m becomes visible); that the trade is permanent (any sampled elevation carries error, this
  isn't a stopgap for denser elevation data); what a future per-cell-uncertainty design (fix option
  4) would key on (`grid.provenance`); and — added after coordinator follow-up mid-task — an
  explicit **airframe-tactics lapse condition**: 12 m is acceptable for the Mi-24P because it
  attacks in a run rather than hiding behind terrain and popping up to shoot, per the user's own
  words quoted in the comment. A future Ka-50/Apache/pop-up-and-shoot airframe target would need to
  revisit this number, because that tactic lives exactly inside a margin this size.
  Kept as a module constant, not a parameter — no current caller (body-layer's
  `perception.geometry.line_of_sight_clear`, a thin wrapper) needs to override it.
- `world-model/tests/test_query_line_of_sight.py` — two new regression tests (see below).

### Tests Added
- `test_line_of_sight_clear_when_target_buried_by_grid_error_within_tolerance` — pins the debug
  note's reproduction: a target at DCS-truth altitude under a grid cell overestimating ground
  height by 11.5 m (M7's own stddev), on a close/steep attack-pass geometry, now reads visible
  (previously flipped to blocked at exactly this margin, per the debug repro table).
- `test_line_of_sight_still_blocked_by_a_ridge_well_beyond_tolerance` — a ridge clearing the
  sightline by 50 m (well past the 12 m tolerance, but deliberately not a huge margin like the
  existing 2000 m ridge fixture) still blocks. This is the omniscience-hole guard: it exercises the
  boundary the tolerance actually moved, rather than passing trivially.

### Checks
**world-model/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (62 source files)
- pytest -q: pass (473 passed, 3 skipped)

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (52 source files)
- pytest -q: pass (1313 passed, 4 xfailed) — no regressions, no test behaviour shifted. Checked
  explicitly: every body-layer test touching `line_of_sight_clear`/`sample_grid` near LOS either
  monkeypatches `line_of_sight_clear` itself wholesale (`test_visibility.py`, `test_naked_eye_
  source.py` — always-True/False stubs, tolerance never exercised) or delegates through a
  monkeypatched `_wm_line_of_sight_clear` (`test_geometry.py`'s delegation test) or uses a flat,
  far-below-everything elevation plane (`test_mock_flight_chain.py`'s `mock_world_model.py`
  fixture, 50 m flat vs. real ownship/target altitudes — nowhere near the 12 m boundary). None
  exercise the terrain-sampling loop's margin closely enough for the tolerance to move a result.

### Notable Discoveries
- The task's stated base sha (`f518826`) was the tip of `main`, one commit ahead of this worktree's
  checked-out branch tip (`570dccc`, `feature/group-reporting` — unrelated). Checked out `f518826`
  detached before starting, per the debug note's own "Investigation base" section confirming
  `264bba3` (an ancestor) was clean at dispatch time.
- Per the coordinator's plan review comment: fix option 2 (widen the near-target exclusion) is
  fully redundant with option 1 once a uniform tolerance is in place — the debug note's own
  reproduction table shows the flip happening at samples near the target specifically, which a
  uniform tolerance already covers without a separate exclusion-widening mechanism.
- Confirmed body-layer's `perception/geometry.py::line_of_sight_clear` needed no change — it
  delegates to world-model's function by reference, so the tolerance took effect there automatically
  with zero code change on the body-layer side.
