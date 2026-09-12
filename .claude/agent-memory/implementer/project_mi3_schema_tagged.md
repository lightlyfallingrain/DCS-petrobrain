---
name: mi3-schema-tagged
description: MI-3 MissionUnderstanding schema/Tagged[T] implementation facts worth knowing before touching mission-interpreter/src/schema or extending its synthetic fixture
metadata:
  type: project
---

MI-3 (`mission-interpreter/src/schema/`) implemented per
`plans/mi3-mission-understanding-schema/plan.md`, done as of 2026-09-12.

- `Unit.skill` breaking-change fan-out was much smaller than the plan feared: exactly one
  construction site (`miz/reader.py`'s `_parse_unit`) — the synthetic fixture is hand-typed Lua
  text, not Python `Unit(...)` calls, and no test constructs `Unit` directly. Grep confirmed this;
  don't assume a plan's stated fan-out risk without grepping first, but also don't over-invest in
  it once grep says otherwise.
- Extending the synthetic fixture's visible-group route from 1 to 3 waypoints (TakeOffGround(10,20)
  -> Turning Point(15,25) -> Land(30,40), needed for `mission_phases` test coverage) broke two
  *existing* MI-2 tests that hardcoded a 1-waypoint assumption: `test_reader.py`'s `(point,) =
  route.points` unpack and `test_enrich.py`'s route-length/describe-position-call-count assertions.
  Both were updated in the same commit as the fixture change — any future fixture-route extension
  should grep `tests/test_reader.py` and `tests/test_enrich.py` for waypoint-count assumptions
  first.
- `mypy --strict` for this subproject only checks `src/` (per `mission-interpreter/CLAUDE.md`
  Commands), not `tests/` — test helpers building `EnrichedMission`/`Group`/`Unit` directly (for
  the zero-/two-Player-unit ownship edge cases) needed zero `type: ignore` scaffolding as a result.
- `Tagged[T]` (`src/schema/tags.py`) is now the one epistemic-tagging mechanism; every top-level
  `MissionUnderstanding` field and every `mission_phases`/`important_locations` *list item* gets
  its own `Tagged[...]`, not the list as a whole. FACT/OBSERVATION were redefined for pre-mission
  use (see `CLAUDE.md`'s Tech-stack bullet) — flagged as an interpretation call on
  `PETROBRAIN_SYSTEM.md`'s "observation == perceived during the mission" wording, not a settled
  fact. MI-4 is expected to reuse `Tagged[T]` rather than reinvent it.
