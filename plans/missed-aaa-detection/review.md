### Review Summary

Reviewed `fix/los-elevation-tolerance` (tip `4060091`, 3 commits on `main` @ `669ffe9`) against
`plans/missed-aaa-detection/debug.md` (option 1) and this project's invariants. Verified HEAD
matched the expected tip after checking the branch out directly (it was not checked out
elsewhere). The fix is a single module constant (`_TERRAIN_TOLERANCE_M = 12.0`) added to
`world-model/src/query/line_of_sight.py`'s terrain-blocking comparison, applied uniformly to
every interior sample, with two new regression tests and an agent-memory note. Scope matches the
plan exactly — no drift, no unrelated changes (diff stat: 2 source/test files + 2 doc/memory
files).

Both subprojects' full check suites were re-run from scratch, not taken on the implementer's word:

- `world-model`: `ruff format --check` / `ruff check` / `mypy --strict` (62 files) / `pytest` — all
  pass, **473 passed, 3 skipped**, exactly matching the reported baseline.
- `body-layer`: same four commands — all pass, **1313 passed, 4 xfailed**, exactly matching the
  reported baseline.

Cross-subproject blast radius (body-layer via `perception/geometry.py`'s thin wrapper) was checked
directly rather than accepted from the implementer's report: grepped every body-layer test file
touching `line_of_sight`/`sample_grid`/`elevation`. Confirmed every one either monkeypatches
`visibility.line_of_sight_clear` wholesale to a constant `True`/`False`
(`test_visibility.py`, `test_naked_eye_source.py`, `test_emission_pipeline.py`,
`test_detection_trace.py`, `test_vision_calibration.py`), monkeypatches the delegation point itself
(`test_geometry.py`'s `_wm_line_of_sight_clear` delegation test), or runs against
`tests/support/mock_world_model.py`'s flat 50 m elevation plane against 500–700 m ownship/object
altitudes — hundreds of metres of margin, nowhere near the 12 m boundary. The implementer's claim
holds.

Near-target exclusion: `range(1, samples)` already excludes both the observer's and target's own
`t=0`/`t=1` sample points, unchanged by this fix. Debug option 2 (widen that exclusion) is correctly
treated as redundant once a uniform tolerance exists — the reproduced miss's excess terrain reading
occurs at the *interior* sample nearest the target (`i=19` in the new test, not the excluded
endpoint), and a uniform tolerance already covers it without a separate widening mechanism. No odd
interaction between the two found.

### Required Fixes

None.

### Optional Refinements

- **The omniscience-hole guard test's 50 m margin doesn't pin the exact moved boundary** — it only
  proves "well beyond tolerance still blocks," not the `>` (vs. `>=`) semantics at exactly 12.0 m,
  and it would pass identically if `_TERRAIN_TOLERANCE_M` were anywhere from 0 up to ~49 m rather
  than the intended 12.0. The test's own docstring claims the margin is "deliberately close to, not
  far past, the tolerance," which overstates it — 50 m is >4x the 12 m constant. A tighter case
  (e.g. a ridge clearing the sightline by 13–15 m) would exercise the actual boundary and catch a
  miscalibration in that range that today's suite would miss. Separately, the *within-tolerance*
  regression test's actual exercised excess is much smaller than the nominal 11.5 m grid
  overestimate it's framed around — the sightline converges toward the target's own altitude near
  `t=1`, so the sample nearest the target (`i=19`) only sees ~1.5 m of excess, not 11.5 m. This
  matches the debug note's own reproduction faithfully (the interpolation dilution is the real
  mechanism, not a test artifact), but it means neither new test actually pins 12.0 as the specific
  right number — that derivation lives only in the constant's comment. Worth a follow-up test at
  some point, not a blocker: the mechanism is correct and the accepted trade is well-documented.
- The airframe-tactics lapse condition comment is thorough and correctly framed as a real
  condition ("needs revisiting," not an aside) — no change needed, noted as a positive rather than
  a gap.

### Verdict
APPROVED

### Review Confidence
Full read — mechanism diff, both new tests, the constant's comment, the two implementation
commits' split, the cross-subproject grep, and both subprojects' full check suites (re-run, not
accepted from the report).
