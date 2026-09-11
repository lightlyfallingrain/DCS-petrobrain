### Implementation Summary

Pure refactor, per plan: moved the point-A-to-point-B LOS algorithm out of
body-layer's `perception/geometry.py` into world-model's `query` package as
an ownship-agnostic primitive over bare `(x, z, alt_m)` tuples, and turned
body-layer's existing `line_of_sight_clear` into a thin wrapper that
converts its own `GeoPosition` observer/target and delegates. No behavior
change, no new callers.

### Files Changed
- `world-model/src/query/line_of_sight.py` (new) — `line_of_sight_clear(conn, theatre, observer, target, *, samples=20) -> bool` with `_DEFAULT_LOS_SAMPLES = 20`; module docstring carries the plan's design notes (tuple-not-dataclass rationale, `geometry/`-package naming collision, why it reads `store.reader.sample_grid` directly instead of `describe_position`).
- `world-model/src/query/__init__.py` — exports `line_of_sight_clear` alongside `describe_position`/`find_place_by_name`.
- `world-model/tests/test_query_line_of_sight.py` (new) — the four moved scenario tests (flat terrain, blocked by ridge, ridge below sightline, missing elevation non-blocking), rewritten against the tuple signature, monkeypatching `query.line_of_sight.sample_grid`. Deliberately not added to the existing `test_geometry.py`, which covers the unrelated `src/geometry/` planar-primitives package (per the plan's explicit naming-trap warning).
- `body-layer/src/perception/geometry.py` — `line_of_sight_clear` now unpacks `GeoPosition` observer/target into `(x, z, alt_m)` tuples and delegates to `query.line_of_sight.line_of_sight_clear` (imported as `_wm_line_of_sight_clear`). Signature/defaults/return type unchanged, so `visibility.py`/`naked_eye_source.py` needed no changes. Module docstring's `sample_grid`-vs-`describe_position` paragraph trimmed to point at the new module instead of re-explaining the reasoning in place.
- `body-layer/tests/test_geometry.py` — the four scenario tests removed and replaced with `test_line_of_sight_clear_delegates_to_world_model_primitive`, which monkeypatches `geometry._wm_line_of_sight_clear` and asserts the correct tuple conversion, argument pass-through (including `samples=20` default), and unchanged return value — mirroring `test_elevation_at_delegates_to_describe_position`'s existing pattern for `elevation_at`.

### Tests Added
- `test_query_line_of_sight.py`'s four scenario tests (world-model) — cover the LOS algorithm itself: clear over flat terrain, blocked by an in-between ridge, a ridge below the sightline not blocking, and missing elevation data treated as non-blocking.
- `test_line_of_sight_clear_delegates_to_world_model_primitive` (body-layer) — covers only the wrapper's `GeoPosition`->tuple conversion and delegation, not the algorithm (now out of scope for this test module).

### Checks
world-model/
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (49 source files)
- pytest -q: pass (256 passed)

body-layer/
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`cd body-layer && mypy src`, per its CLAUDE.md's CWD-only note): pass (29 source files)
- pytest -q: pass (451 passed)

### Notable Discoveries
- None — this was a mechanical move with no surprises. The existing `elevation_at` delegation test in body-layer was a ready-made template for the new wrapper test, and world-model's `query/__init__.py` export list only needed one addition.
