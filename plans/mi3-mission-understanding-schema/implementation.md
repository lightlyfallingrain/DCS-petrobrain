### Implementation Summary

Implemented MI-3 (First Mission Understanding schema, no model synthesis) exactly as scoped in
`plan.md`. Two commits: (1) the `Unit.skill` breaking change + fixture extension, (2) the new
`src/schema/` package and its tests + docs.

### Files Changed

- `mission-interpreter/src/miz/tree.py` — added `skill: str` to `Unit`, docstring explaining the
  `"Player"`/`"Client"` player-slot convention per the investigator's finding.
- `mission-interpreter/src/miz/reader.py` — `_parse_unit` now reads `node.get("skill", "")`.
- `mission-interpreter/tests/fixtures/synthetic_mission.py` — visible group's unit now carries
  `skill = "Player"`; its route was extended from one `"Turning Point"` waypoint to three
  (`TakeOffGround` (10,20) → `Turning Point` (15,25) → `Land` (30,40)) so `mission_phases` mapping
  has real, distinct waypoint types to test against. The four author-only-marker units also got a
  `skill = "Average"` for schema completeness (not load-bearing for any test).
- `mission-interpreter/tests/test_reader.py`, `test_enrich.py` — updated to match the 3-waypoint
  route and new `skill` field (unpacking 3 points instead of 1, updated call-count arithmetic in
  `test_call_count_is_bounded_and_deterministic`, added a `unit.skill == "Player"` assertion).
- `mission-interpreter/src/schema/tags.py` — new: `EpistemicStatus` literal, `Tagged[T]` generic
  wrapper (`value`, `epistemic_status`, `basis`).
- `mission-interpreter/src/schema/understanding.py` — new: `SCHEMA_VERSION = 1`,
  `MissionUnderstanding`, `Ownship`, `MissionPhase`, `ImportantLocation`. Shape only, no logic.
- `mission-interpreter/src/schema/build.py` — new: `build_mission_understanding`, the mechanical
  mapping. `_build_ownship` scans every unit across every coalition/country/group for
  `skill in ("Player", "Client")`; exactly one match resolves `Ownship`/`route` as `FACT`, 0 or ≥2
  resolve both to `UNKNOWN` with a basis string recording the match count. `_build_mission_phases`
  walks the resolved group's route, mapping `type.startswith("TakeOff")` → `DEPARTURE` and
  `type == "Land"` → `RETURN`; any other type (including `"Turning Point"`) emits nothing.
  `_build_important_locations` scans every group and every trigger zone for non-empty
  `world_ref.name_matches`, tagging each `OBSERVATION`.
- `mission-interpreter/tests/test_schema_tags.py` — new: `Tagged` construction + `asdict()` →
  `json.dumps` → `json.loads` round-trip for `int` and `str` payloads, default-`basis` check.
- `mission-interpreter/tests/test_schema_understanding.py` — new: mapping tests (below).
- `mission-interpreter/CLAUDE.md` — added the `Tagged[T]`/FACT-OBSERVATION-redefinition bullets
  under "Tech stack", a `src/schema/` "done" bullet under "Structure", and named the new test files
  under "Testing"/"Structure".
- `mission-interpreter/ROADMAP.md` — marked MI-3 done with a summary paragraph.

### Tests Added

- `test_schema_tags.py`: `Tagged[int]`/`Tagged[str]` JSON round-trip, default `basis == ()`.
- `test_schema_understanding.py`:
  - `test_happy_path_populates_expected_fields` — full pipeline (synthetic fixture → `read_miz` →
    `filter_crew_available` → `enrich_mission` with a fake world-model client) → asserts
    `theatre`/`ownship`/`route`/`mission_phases`/`important_locations` all populated as expected,
    `purpose`/`task`/`known_threats`/`player_intent` all `None`/`()`.
  - `test_zero_player_units_resolves_ownship_and_route_to_unknown` /
    `test_two_player_units_resolves_ownship_and_route_to_unknown` — `EnrichedMission` built directly
    in test code (bypassing the zip/HTTP pipeline, per the plan's suggested approach), proving
    `UNKNOWN` on both edge cardinalities, not a first-match guess.
  - `test_important_locations_only_from_named_matches_not_route_waypoints` — confirms exactly the
    named group + 2 named zones, no waypoint-derived entries.
  - `test_no_tagged_value_is_ever_inference_or_assumption` — the central invariant: recursively
    walks every `Tagged` value reachable from a built `MissionUnderstanding` and asserts none is
    `INFERENCE`/`ASSUMPTION`.
  - `test_mission_understanding_round_trips_through_json` — full `asdict()` → `json.dumps` →
    `json.loads` on the happy-path result.

### Checks

(single touched subproject: `mission-interpreter/`)

- ruff format --check: pass
- ruff check: pass
- mypy --strict (`src`, run with `mission-interpreter` as cwd): pass, 19 source files, no issues
- pytest -q: pass, 41 passed

### Notable Discoveries

- The plan's Risk section warned "the Implementer should grep for `Unit(` before assuming
  `reader.py`/`synthetic_mission.py` are the only two sites" — grepping found exactly one
  construction site (`miz/reader.py`'s `_parse_unit`); the fixture is hand-typed Lua text, not
  Python `Unit(...)` calls, and no test file constructs `Unit` directly. The feared fan-out did not
  materialize; still worth having grepped rather than assuming.
- Extending the synthetic fixture's route from 1 to 3 waypoints (needed for `mission_phases`
  coverage) had a second-order effect the plan didn't call out explicitly: it broke two *existing*
  MI-2 tests (`test_reader.py`'s single-waypoint unpack, `test_enrich.py`'s route-length and
  describe-position call-count assertions). Updated both rather than routing around the shared
  fixture, since the plan's own step 1 already treats "run test_reader/test_filter/test_enrich to
  confirm nothing else broke" as part of this stage's own verification gate.
- `mypy --strict` on `mission-interpreter/src` only (per this subproject's Commands list) does not
  type-check `tests/`, so the zero-/two-Player-unit test helpers building `EnrichedMission`/`Group`/
  `Unit` directly in test code needed no `type: ignore` scaffolding to satisfy a stricter test-side
  contract — confirmed by running mypy and seeing it report only the 19 `src` files.
