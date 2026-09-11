### Goal
Move the point-A-to-point-B line-of-sight *algorithm* currently living in
`body-layer/src/perception/geometry.py`'s `line_of_sight_clear` into
world-model's `query` package as an ownship-agnostic primitive, with
body-layer's existing ownship-to-contact LOS check becoming a thin wrapper
around it — a pure refactor, no behavior change, no new callers.

### Affected Modules / Files
- `world-model/src/query/line_of_sight.py` (new) — the moved algorithm:
  `line_of_sight_clear(conn, theatre, observer, target, *, samples=20) -> bool`,
  where `observer`/`target` are `tuple[float, float, float]` = `(x, z, alt_m)`
  in DCS-native coordinates. Uses `store.reader.sample_grid` directly for
  the same reason the original did (see "Design notes" below) — a
  documented deviation from `describe_position`, restated in this module's
  own docstring now that it lives next to `describe_position` rather than
  across a subproject boundary.
- `world-model/src/query/__init__.py` — export `line_of_sight_clear` from
  the new module, alongside `describe_position`/`find_place_by_name`.
- `world-model/tests/test_query_line_of_sight.py` (new) — the four LOS
  scenario tests moved from body-layer (flat terrain, blocked by ridge,
  ridge below sightline, missing elevation treated as non-blocking),
  monkeypatching `store.reader.sample_grid` the same way the originals did.
  **Not** `world-model/tests/test_geometry.py` — that file already exists
  and covers the unrelated `world-model/src/geometry/` package (pure 2D
  planar primitives, no I/O); same word, different subject, see Risks.
- `body-layer/src/perception/geometry.py` — `line_of_sight_clear` becomes a
  thin wrapper: unpacks `GeoPosition` observer/target into
  `(x, z, alt_m)` tuples and delegates to
  `query.line_of_sight.line_of_sight_clear`. Signature, defaults
  (`samples: int = 20`), and return type unchanged, so every existing
  caller (`visibility.py`, `naked_eye_source.py`) needs zero changes.
  Module docstring's `sample_grid`-vs-`describe_position` paragraph is
  trimmed to note the algorithm now lives in world-model; the reasoning
  itself moves to the new module's docstring, not duplicated in both
  places.
- `body-layer/tests/test_geometry.py` — the four `line_of_sight_clear`
  scenario tests are removed (they now live in world-model, against the
  real algorithm) and replaced with one thin-wrapper test: monkeypatch
  `query.line_of_sight.line_of_sight_clear` and assert body-layer's
  `geometry.line_of_sight_clear` calls it with the correctly-converted
  `(x, z, alt_m)` tuples and returns its result unchanged. This mirrors
  how `elevation_at` (the sibling function that already calls
  `describe_position`) is tested today — a thin-wrapper test, not a
  re-verification of world-model's own logic.

### Design notes
- **Point representation: plain `tuple[float, float, float]`, not a new
  dataclass.** World-model's existing `geometry/` package already
  represents 2D points as bare `tuple[float, float]` (`Point`), and
  `describe.describe_position` takes bare `x, z` floats rather than a
  point object. A 3-tuple `(x, z, alt_m)` extends that established
  tuple convention rather than introducing a `GeoPosition`-style
  dataclass into world-model — `GeoPosition` itself stays body-layer-only
  (it also carries semantics like being "the observer's/target's own
  ground position" that are a body-layer framing, not a world-model one).
  This is a local, reversible choice per AGENTS.md's escalation
  guidance — noted here rather than escalated.
- **Naming collision to watch**: world-model already has a top-level
  `src/geometry/` package (pure planar math, explicitly "no I/O" per its
  own docstring) that is *unrelated* to body-layer's
  `perception/geometry.py` (which does do I/O, and is what's being
  partially moved here). The new LOS primitive cannot go into
  `world-model/src/geometry/` — it needs `sample_grid` reads, which
  would violate that package's own no-I/O contract — so it goes into
  `query/` instead, next to `describe_position`, which already mixes
  read I/O with the store. Flagged explicitly so a future reader doesn't
  conflate the two "geometry" modules or try to "fix" the LOS primitive
  into the wrong package.
- **The `sample_grid`-not-`describe_position` optimization still
  applies**, and more cleanly than before: `line_of_sight_clear` samples a
  dozen-plus interior points per call, and `describe_position` computes
  road/settlement/navaid joins irrelevant to a bare elevation read on every
  one of them. That reasoning was originally documented in body-layer
  because the deviation crossed a subproject boundary and needed
  justifying to a body-layer reader who might not know `describe_position`'s
  own cost. Now that the algorithm lives inside world-model itself, the
  same reasoning still holds (repeated per-sample joins are still wasted
  work) — it's restated as an internal note in `query/line_of_sight.py`'s
  docstring pointing at `describe.py`'s own docstring (which already notes
  `elevation.dcs_m` is itself built on `sample_grid`), not dropped.

### Implementation Plan
1. Create `world-model/src/query/line_of_sight.py` with the moved
   `line_of_sight_clear` (tuple-based signature), `_DEFAULT_LOS_SAMPLES`
   constant, and a module docstring carrying the design notes above.
   Export it from `query/__init__.py`.
2. Move the four LOS scenario tests to
   `world-model/tests/test_query_line_of_sight.py`, rewritten against the
   tuple signature and monkeypatching `store.reader.sample_grid` at its
   world-model import site. Run world-model's full check suite.
3. Rewrite `body-layer/src/perception/geometry.py`'s `line_of_sight_clear`
   as a thin wrapper (import `from query.line_of_sight import
   line_of_sight_clear as _wm_line_of_sight_clear` or equivalent; convert
   `GeoPosition` -> tuple; delegate). Trim the module docstring's
   `sample_grid`-vs-`describe_position` paragraph to point at the new
   module instead of re-explaining the reasoning in place.
4. Replace the four moved tests in `body-layer/tests/test_geometry.py`
   with the one thin-wrapper delegation test. Run body-layer's full check
   suite (`cd body-layer && mypy src`, per its CLAUDE.md's CWD-only mypy
   note).
5. Run both subprojects' format/lint/type/test commands one more time
   together (root CLAUDE.md's Verification section: a cross-subproject
   change needs each touched subproject's own commands run) before
   handoff to Reviewer.

### Risks & Unknowns
- Test coverage must not silently shrink during the move — the four
  scenario tests need to reappear intact in world-model, not be
  paraphrased or dropped. Reviewer should diff old-vs-new test bodies,
  not just check that "some LOS tests exist."
- The `test_geometry.py` name already exists in `world-model/tests/` for
  an unrelated package — using a distinctly-named new test file
  (`test_query_line_of_sight.py`) avoids a same-named-but-different-subject
  collision, but a careless implementer could be tempted to add LOS tests
  into the existing `test_geometry.py` by pattern-matching the filename
  alone. Called out explicitly to prevent that.
- No unverified DCS-internals claim is introduced by this refactor (it
  moves existing, already-verified logic) — investigator is not needed.

### Second-order effect
This establishes world-model's `query` package as the home for
ownship-agnostic, point-A-to-point-B spatial primitives (not just
position-to-description lookups), which is exactly the shape a future
Mission Interpreter or a future brain-layer tool would need for
"can unit A see position/unit B" questions that have nothing to do with
the player's own aircraft — it doesn't unblock any specific upcoming
milestone yet, but it removes an architectural obstacle (the algorithm
being trapped inside body-layer's ownship-shaped call site) that would
otherwise have to be paid down later as a larger, riskier refactor once a
second consumer actually shows up.
