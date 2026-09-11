### Review Summary

Reviewed commits `77fcd58` (move algorithm into world-model), `c24553a`
(body-layer wrapper + test rewrite), `ab493c0` (implementation log) against
the locked plan (`5ad922e`).

Verified directly, not just by trusting the implementation log:

1. **Behavior preservation** — diffed the pre-move algorithm body (old
   `body-layer/src/perception/geometry.py::line_of_sight_clear`, via
   `git show 77fcd58^:...`) against the new
   `world-model/src/query/line_of_sight.py`. The sampling loop
   (`for i in range(1, samples): t = i/samples; ...; if terrain_m is None:
   continue; ...; if terrain_m > sightline_alt_m: return False`) is
   byte-for-byte identical logic, only the observer/target access changed
   from `.x/.z/.alt_m` attribute access to unpacked tuple locals.
   `_DEFAULT_LOS_SAMPLES = 20` default preserved exactly. No rewrite-while-
   moving occurred.
2. **Callers unaffected** — `git diff --stat 5ad922e ab493c0` and
   `git log 5ad922e..ab493c0 -- .../visibility.py .../naked_eye_source.py`
   both confirm zero changes to either caller. The wrapper's signature
   (`(conn, theatre, observer, target, *, samples=20) -> bool`) is
   identical to the original's.
3. **Test migration** — all four scenario tests (flat, blocked-by-ridge,
   ridge-below-sightline, missing-elevation) reappear in
   `world-model/tests/test_query_line_of_sight.py` with unchanged fixture
   values and assertions, only the observer/target literals changed from
   `GeoPosition(...)` to bare tuples. Confirmed removed (not duplicated) in
   `body-layer/tests/test_geometry.py` via the commit diff. The one
   remaining body-layer test
   (`test_line_of_sight_clear_delegates_to_world_model_primitive`)
   monkeypatches `geometry._wm_line_of_sight_clear` (the real import
   binding, not a mock of some other seam) and asserts on the converted
   tuple args and pass-through `samples=20` — a genuine delegation check,
   consistent with `test_elevation_at_delegates_to_describe_position`'s
   existing pattern in the same file.
4. **Module placement** — lands in `world-model/src/query/line_of_sight.py`
   as planned, not the unrelated `world-model/src/geometry/` package. New
   module's docstring explicitly calls out that same naming trap so a
   future reader won't conflate the two. `query/__init__.py` exports
   `line_of_sight_clear` alongside `describe_position`/`find_place_by_name`
   correctly.
5. **Docstring/rationale preserved** — the `sample_grid`-not-
   `describe_position` reasoning is restated in full in the new module's
   docstring (not just referenced), and body-layer's module docstring was
   correctly trimmed to point at it instead of duplicating.
6. **Scope** — `git diff --stat 5ad922e ab493c0` touches exactly the plan's
   Affected Modules list (5 code/test files + the implementation log), no
   extra files.

Invariants: module independence preserved — the new
`from query.line_of_sight import line_of_sight_clear as _wm_line_of_sight_clear`
import is the same in-process seam shape body-layer already uses for
`describe_position`, not a new/different coupling. No DCS-installation
writes, no new dependencies, no unverified-DCS-internals claims introduced
(this moves already-verified logic, matching the plan's own "Risks &
Unknowns" note that investigator wasn't needed).

Ran both subprojects' full check suites myself rather than trusting the
implementation log's reported numbers:
- world-model: `ruff format --check`, `ruff check`, `mypy src` (49 files),
  `pytest -q` — all pass, 256 passed, matching the log.
- body-layer: `ruff format --check`, `ruff check`, `cd body-layer && mypy
  src` (29 files), `pytest -q` — all pass, 451 passed, matching the log.

### Required Fixes
- `body-layer/CLAUDE.md`'s Structure section (lines ~132-138, the
  `src/perception/geometry.py` entry) still describes
  `line_of_sight_clear` as directly calling `store.reader.sample_grid` for
  its own sampling loop, and states the sample_grid-vs-describe_position
  deviation as living in *this* module. Both are now false —
  `line_of_sight_clear` is a thin wrapper delegating to
  `query.line_of_sight.line_of_sight_clear`, and the deviation/sampling
  logic now lives in world-model. The plan's Affected Modules list didn't
  call out a CLAUDE.md update, but this is exactly the kind of drift root
  CLAUDE.md's own module-responsibility framing exists to prevent — a
  future reader trusting this Structure entry would misdescribe where the
  LOS algorithm and its documented deviation actually live. Needs a short
  edit pointing at the new wrapper relationship (mirroring how the
  `elevation_at`/`describe_position` line above it is already phrased).

### Optional Refinements
- None identified — the refactor is otherwise mechanical and matches the
  plan closely enough that no further cleanup is warranted.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — read the actual pre/post algorithm bodies via git show (not
just the implementation log's claim), read all three commits' full diffs,
and independently ran both subprojects' format/lint/type/test commands
rather than trusting the reported 256+451 passing.
