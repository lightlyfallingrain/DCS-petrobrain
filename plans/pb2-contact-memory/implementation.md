### Implementation Summary

Implemented the "aircraft layer should flag the ownship; body layer filters it out in
detection logic" backlog item (`todo/todo.md` Backlog, lines 81-105) — referred to as PB-2/BL-2
Stage -1 in the task brief. **Note:** `plans/pb2-contact-memory/plan.md` does not exist in the
repo; no plan file at that path was ever written. The full spec for this task lives in
`todo/todo.md`'s Backlog entry, which was read in full and treated as the approved plan.

Added an `is_ownship: bool | None` field to the aircraft-layer's `WorldObjectSample` wire
format, set by `Export.lua` via `LoGetPlayerPlaneId()`, and replaced body-layer's 50 m
proximity-based ownship exclusion (`association.exclude_ownship`,
`OWNSHIP_ECHO_EXCLUSION_RADIUS_M`) with a flag-based filter (`association.filter_ownship`).

### Files Changed

**Aircraft layer:**
- `aircraft-layer/dcs-export/Export.lua` — calls `safe_call(LoGetPlayerPlaneId)` once per poll
  (same pcall-guard pattern as every other export read); `encode_world_objects_line` now takes
  `player_plane_id` and emits `is_ownship` (`true`/`false` by `object_id == player_plane_id`
  comparison, JSON `null` if `LoGetPlayerPlaneId()` itself failed). The object is still sent
  either way.
- `aircraft-layer/src/schema/world_objects.py` — `WorldObjectSample.is_ownship: bool | None`,
  parsed/serialized in `from_dict`/`to_dict`. Tri-state, following the same `T | None` pattern
  `TelemetrySample.altitude_radar_m` already uses in this codebase for a field that's present
  but may be null.
- `aircraft-layer/tests/test_world_objects_schema.py` — new tests for true/false/null/invalid
  `is_ownship` parsing and round-trip.
- `aircraft-layer/tests/test_world_objects_api.py` — updated the one direct `WorldObjectSample(...)`
  construction to supply `is_ownship` (now a required field).
- `aircraft-layer/CLAUDE.md`, `aircraft-layer/WORKFLOW.md` — documented the new field and its
  tri-state contract on `GET /world_objects/latest`.

**Body layer:**
- `body-layer/src/perception/association.py` — `WorldObjectCandidate` gains `is_ownship: bool |
  None`, populated from the wire dict in `from_dict`. `exclude_ownship()` and
  `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` deleted entirely (not deprecated). New `filter_ownship()`
  drops only candidates flagged `is_ownship is True`; `None` and `False` are both kept.
- `body-layer/src/perception/hybrid_source.py`, `naked_eye_source.py` — both call sites switched
  from `exclude_ownship(candidates, ownship_state)` to `filter_ownship(candidates)` (no longer
  need `ownship_state` for this step — geometry is irrelevant now).
- `body-layer/tests/test_association.py` — removed the three `exclude_ownship` proximity tests
  (co-located/outside-radius/at-boundary), replaced with `filter_ownship` tests for
  True/False/None and a "real object co-located with ownship is kept" test proving the
  false-negative window is closed.
- `body-layer/tests/test_hybrid_source.py`, `test_naked_eye_source.py` — `_world_object()`
  helpers gained an `is_ownship` parameter (default `False`); the "ownship echo" fixture tests
  now flag `is_ownship=True` on the echo object instead of relying on a close x/z position.
- `body-layer/tests/test_visibility.py` — `_candidate()` helper updated to supply
  `is_ownship=False` (now a required dataclass field).

### Tests Added
- Aircraft layer: `test_from_json_line_accepts_true_is_ownship`,
  `test_from_json_line_accepts_false_is_ownship`, `test_from_json_line_accepts_null_is_ownship`,
  `test_from_json_line_rejects_non_boolean_is_ownship`, `test_to_dict_round_trips_is_ownship`.
- Body layer: `test_world_object_candidate_from_dict_reads_is_ownship_flag`,
  `test_filter_ownship_drops_a_candidate_flagged_true`,
  `test_filter_ownship_keeps_a_candidate_flagged_false`,
  `test_filter_ownship_keeps_a_candidate_with_unknown_ownship_status`,
  `test_filter_ownship_keeps_a_candidate_even_when_co_located_with_ownship` (proves the old
  false-negative window is closed).

### Checks
- Aircraft layer: `ruff format --check`, `ruff check`, `mypy src`, `pytest` (57 passed) — all pass.
- Body layer: `ruff format --check`, `ruff check`, `mypy src` (run as `cd body-layer && mypy src`
  per this subproject's known CWD-only config-discovery quirk), `pytest` (104 passed) — all pass.

### Notable Discoveries
- No `plans/pb2-contact-memory/plan.md` exists in the repo — the task brief's referenced path is
  stale/incorrect. The real spec for this exact change lives in `todo/todo.md`'s Backlog section
  ("Aircraft layer should flag the ownship..."), which matches the task brief's instructions
  closely enough (same field name suggestion, same "flag don't omit" requirement, same
  `exclude_ownship`/`OWNSHIP_ECHO_EXCLUSION_RADIUS_M` deletion instruction) that it was treated
  as the approved plan. Flagging this for whoever owns `todo/todo.md` next: either a
  `plans/pb2-contact-memory/plan.md` should be written before BL-2 proper starts, or the backlog
  item should be checked off/archived now that it's done.
- `LoGetWorldObjects`'s `pairs()` key was already established (research doc
  `2026-09-07-petrovich-perception-export.md` finding 10, via a pasted forum thread) to be the
  same numeric id space `k` that a poster's own working code iterates with — this is the same
  id space `LoGetPlayerPlaneId()` returns, so the identity comparison in `Export.lua` is a
  same-namespace equality check, not a cross-namespace guess. Not independently re-verified live
  in this task (no DCS access) — see "Live verification" below.
- The `is_ownship` tri-state (not a plain bool) mirrors `TelemetrySample.altitude_radar_m`'s
  existing `float | None` pattern in this same wire format family — confirmed this is the
  established convention for "field is present in every line but may be genuinely unknown" in
  this codebase before choosing it, per the task's instruction to match existing style.

### Live verification still needed (user-only)
Per project convention, I did not fly DCS or run a live sortie. The flag's live correctness —
whether `LoGetPlayerPlaneId()` returns what's expected and actually identifies the same object
`LoGetWorldObjects()` reports for ownship — is unverified by fixtures and can only be confirmed
on a real sortie. Suggested acceptance check: fly a short sortie, hit `GET
/world_objects/latest`, and confirm exactly one object has `is_ownship: true` and it's the
player's own aircraft (by position/type), across both a normal poll and (if easy to force) a
poll where `LoGetPlayerPlaneId()` might plausibly fail (e.g. very early in mission load) to
confirm the `null` path is reachable and body-layer keeps such objects rather than dropping them.
