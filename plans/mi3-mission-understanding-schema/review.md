### Review Summary

Reviewed MI-3 (`feature/mi3-mission-understanding-schema`) against the locked plan
(`plans/mi3-mission-understanding-schema/plan.md`, commit `a3817cd`) and the Implementer's
`implementation.md`. Read every changed file directly (not just the Implementer's summary):
`schema/tags.py`, `schema/understanding.py`, `schema/build.py`, `schema/__init__.py`,
`tests/test_schema_tags.py`, `tests/test_schema_understanding.py`, the `Unit.skill` change in
`miz/tree.py`/`miz/reader.py`, both second-order test fixes in `test_reader.py`/`test_enrich.py`,
and the `CLAUDE.md`/`ROADMAP.md` updates. Also independently ran mission-interpreter's own
format/lint/type/test commands rather than trusting the reported numbers, and independently
grepped for `Unit(` construction sites rather than trusting the Implementer's fan-out claim.

Findings, point by point from the task brief:

1. **No-INFERENCE invariant** — confirmed at the source. Every `Tagged(...)` construction site in
   `build.py` uses only `"FACT"`, `"OBSERVATION"`, or `"UNKNOWN"` (verified by reading all five
   call sites: `theatre`, `_build_ownship`'s two branches, `_build_route`'s two branches,
   `_build_mission_phases`, `_build_important_locations`). `test_no_tagged_value_is_ever_inference_or_assumption`
   builds a real `MissionUnderstanding` via the full pipeline (synthetic fixture → `read_miz` →
   `filter_crew_available` → `enrich_mission`), recursively walks every reachable `Tagged` via
   `_iter_tagged` (which correctly descends into dataclasses and tuples, not just top-level
   fields), and asserts none is `INFERENCE`/`ASSUMPTION` against that real constructed output —
   not a type-level check.

2. **Ownship resolution** — `_build_ownship` scans `unit.skill in _PLAYER_SKILLS` (`("Player",
   "Client")`) across every group returned by `_all_groups` (all coalitions/countries/groups),
   exactly as designed. `test_zero_player_units_resolves_ownship_and_route_to_unknown` and
   `test_two_player_units_resolves_ownship_and_route_to_unknown` each build a real `EnrichedMission`
   directly (via `_bare_group`/`_bare_unit` helpers) with 0 and 2 `Player`-skill units respectively,
   and assert `UNKNOWN` on both `ownship` and `route`, plus the two-match case asserts the `basis`
   string records the count. Genuine edge-case coverage, not trivial-input smoke tests.

3. **`mission_phases` mechanical mapping** — closed match: `point_type.startswith("TakeOff")` →
   `DEPARTURE`, `point_type == "Land"` → `RETURN`, anything else (`name is None`) is skipped via
   `continue`, never force-mapped. The happy-path test's fixture route is `TakeOffGround(10,20)` →
   `Turning Point(15,25)` → `Land(30,40)` and asserts `phase_names == ["DEPARTURE", "RETURN"]` with
   the correct `waypoint_index` (0 and 2, skipping the middle turning point) — confirms the closed
   mapping isn't accidentally fuzzy.

4. **`important_locations` scope-narrowing** — `_build_important_locations` only reads
   `group.world_ref.name_matches` and `zone.world_ref.name_matches`; no route-waypoint or `RoutePoint`
   field is touched anywhere in `build.py`. `test_important_locations_only_from_named_matches_not_route_waypoints`
   explicitly asserts exactly 3 locations (the named group + 2 named zones) with no waypoint-derived
   entries. Confirmed `RoutePoint`/`EnrichedRoutePoint` carry no `name` field that could have been
   reintroduced accidentally.

5. **`Unit.skill` breaking change** — independently grepped `grep -rn "Unit(" mission-interpreter/`
   and found exactly the two sites the Implementer reported: `miz/reader.py`'s `_parse_unit` and
   `tests/test_schema_understanding.py`'s `_bare_unit` helper (added in this same change, not a
   missed pre-existing site). The fan-out fear in the plan's Risks section did not materialize.
   `reader.py`'s `node.get("skill", "")` defaults to empty string, never `None`/crash. Per the
   Implementer's own research note (`research/2026-09-12-player-slot-skill-field.md`), the real
   sample shows every one of 44 `unit[]` entries carries a `skill` field (23 `"Average"`, 20
   `"High"`, 1 `"Player"`) — no observed case of a missing field — so the empty-string default is a
   defensive fallback for a case not yet seen in real data, not a silent-failure risk for the
   documented common case.

6. **Second-order test fixes** — read both diffs directly. `test_reader.py`'s update unpacks all
   three route points and asserts each one's `type`/`x`/`y` individually (`takeoff`/`turning`/
   `land`), strictly more assertion surface than the single-point version it replaced — not a
   loosened check. `test_enrich.py`'s update asserts `world_ref.position` for all three waypoints
   (previously only one) and updates the calibrated call-count arithmetic (4→6, with the reasoning
   spelled out in a comment) to match the new fixture shape — again a genuine adaptation, not a
   relaxed assertion.

7. **Schema round-trip** — `test_mission_understanding_round_trips_through_json` does the real
   `asdict()` → `json.dumps()` → `json.loads()` chain and checks representative fields survive.
   Manually reasoned through the `Generic[T]`/`asdict()` interaction: `Tagged` is a concrete
   `@dataclass(frozen=True, slots=True)`, and `dataclasses.asdict()` operates on the runtime
   instance's `__dataclass_fields__`, which exist independently of the `Generic[T]` parameterization
   — `Generic` only affects static type-checking, not runtime dataclass machinery — so this is not
   a case where the claim needed to be taken on faith; it holds for the structural reason stated in
   `tags.py`'s docstring. The test exercises this against the real happy-path output, not a
   synthetic minimal case.

8. **`CLAUDE.md`/`ROADMAP.md` updates** — both accurately describe what was built, including the
   FACT/OBSERVATION redefinition and the `Tagged[T]` rationale (matches the plan's own framing,
   not a rewritten narrative), and correctly mark `src/schema/` "done" while leaving `src/synth/`
   as still-future. `ROADMAP.md`'s MI-3 entry closes with the required "does this change what's
   next" line per this project's Milestone Completion rule.

**Verification run independently** (not trusted from the report): `ruff format --check` (25 files
already formatted), `ruff check` (all checks passed), `mypy mission-interpreter/src` (success, 19
source files), `pytest mission-interpreter/tests -q` (41 passed) — all from repo root using
mission-interpreter's own venv, matching the Implementer's reported numbers exactly.

**Scope check**: `git diff main...feature/mi3-mission-understanding-schema --stat` shows only
`mission-interpreter/` files, `plans/mi3-mission-understanding-schema/`,
`plans/mission-interpreter/plan.md` (roadmap-adjacent parent-plan note), and `.claude/agent-memory/
architect/` entries recording the MI-3 `Tagged[T]` pattern and validation-note precedent for future
planning — no `world-model/` or `body-layer/` changes, no MI-4 model-synthesis work. Nothing in
`schema/understanding.py` populates `purpose`/`task`/`known_threats`/`player_intent` — all remain
`None`/`()` as designed, confirmed both in code and in the happy-path test's explicit assertions.

### Required Fixes

None.

### Optional Refinements

- `_build_ownship`'s `matches` list scans every unit in every group unconditionally even after
  finding a second match — for real mission sizes this is irrelevant (bounded, small lists), so
  this is a non-issue in practice, flagging only for completeness (optional, no action needed).
- The working tree currently carries two uncommitted implementer-memory files
  (`.claude/agent-memory/implementer/project_mi3_schema_tagged.md`, modified
  `MEMORY.md`) unrelated to this review — not part of the reviewed diff and not blocking, but worth
  the Implementer/DoD noting before declaring the branch's working tree clean per this project's
  Definition of Done (optional bookkeeping, not a code issue).

### Verdict
APPROVED

### Review Confidence
Full read — every changed file in `mission-interpreter/` was read directly (not summarized from
the Implementer's report), all eight brief-specified checks were verified against source and test
code, and format/lint/type/test commands were rerun independently rather than trusted from the
implementation log.
