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

---

## Stage 0 — Scope-channel repair (2026-09-09)

Implemented `plans/pb2-contact-memory/plan.md`'s Stage 0 (a) and (b), in their own commits, per
the backlog's requirement that this repair not ride along invisibly.

### Files Changed

- `body-layer/src/perception/association.py` — `_type_match_score` now resolves each
  candidate's `object_type` through `reporting_names.reporting_name_for` and scores against
  **both** the raw type and the resolved reporting name, taking the max. Module docstring's
  "Type-match scoring" algorithm step updated to reference this. Import added:
  `from perception.reporting_names import reporting_name_for`.
- `body-layer/src/perception/hybrid_source.py` — `HybridPerceptionSource.poll()` now reads all
  five HelperAI `*_list_text` leaves (`LIST_TEXT_FIELDS`: `upper_upper_list_text`,
  `upper_list_text`, `middle_list_text`, `lower_list_text`, `lower_lower_list_text`), collapses
  them to the distinct populated texts in that order via the new `_distinct_populated_texts`
  helper, and associates each distinct text against the candidate pool in order, removing the
  claimed candidate before the next leaf is associated. Builds one `Observation` per
  successfully-associated leaf; a leaf that fails to associate is dropped individually
  (`_record_drop`) without blocking the others. `_last_emitted_classification: str | None` was
  renamed `_last_emitted_texts: tuple[str, ...] | None`; debounce now compares the whole distinct-
  text set against the last set that produced at least one `Observation` (mirrors the old
  single-value semantics exactly whenever only one leaf is ever populated, which is why every
  existing on_change test needed no changes). Module docstring rewritten to describe the
  multi-leaf behaviour and cite Finding 6.
- `body-layer/tests/test_association.py` — new `_type_match_score`/`associate()` tests for the
  four real Finding-6 tuples (see table below), plus a regression test confirming the pre-fix
  Ural-truck coincidence still scores nonzero.
- `body-layer/tests/test_hybrid_source.py` — new tests: SA-3 launcher + radar leaves yield two
  `Observation`s (the plan's required acceptance case), Slava cruiser + Tarantul III corvette
  leaves yield two `Observation`s, and a same-text-across-two-leaves case still yields exactly one
  `Observation` (no double-counting a highlighted row plus its own neighbour echo).

### Before/After score table (`_type_match_score`, Finding 6's four real tuples)

| `classification_raw` (HelperAI) | `object_type` (`LoGetWorldObjects`) | old score | new score |
| --- | --- | --- | --- |
| `Slava cruiser` | `MOSCOW` | 0 | 2 |
| `Tarantul III corvette` | `MOLNIYA` | 0 | 3 |
| `SA-3 launcher` | `5p73 s-125 ln` | 0 | 3 |
| `SA-3 Low Blow radar` | `snr s-125 tr` | 0 | 5 |

All four scored 0 before this fix — the type-match step would have contributed nothing to
`associate()`'s decision for any of these real objects, degrading to the plausibility filter
(range/forward-hemisphere) alone. The pre-existing Ural-truck coincidence
(`"Ural truck"` vs `"Ural-4320"`) still scores nonzero (verified by
`test_type_match_score_still_scores_the_ural_truck_coincidence`), so nothing regresses.

### Tests Added

- `test_type_match_score_is_nonzero_for_real_reporting_name_tuples` (parametrized over the four
  Finding-6 tuples) — the score table above.
- `test_type_match_score_still_scores_the_ural_truck_coincidence` — no-regression check.
- `test_sa3_launcher_and_radar_resolve_confidently_against_real_types` — end-to-end `associate()`
  proof that both real SA-3 objects resolve unambiguously once reporting-name scoring is in play.
- `test_sa3_launcher_and_radar_leaves_yield_two_observations` — the plan's required acceptance
  test: `middle_list_text`/`lower_list_text` both `"SA-3 launcher"` (deduped to one text) plus
  `lower_lower_list_text` `"SA-3 Low Blow radar"` yields **two** `Observation`s, each claiming a
  different candidate.
- `test_slava_cruiser_and_tarantul_corvette_leaves_yield_two_observations` — same shape for the
  other Finding-6 tuple.
- `test_repeated_text_across_leaves_is_deduplicated_to_one_observation` — same text on two leaves
  (a highlighted row echoed on a neighbour leaf) does not double-count.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `cd body-layer && mypy src` (per this subproject's CWD-only config-discovery quirk): pass
- `pytest body-layer/tests -q`: 113 passed (was 104 before this stage; all pre-existing tests
  still pass unmodified)

### Notable Discoveries

- The existing `_last_emitted_classification`/debounce mechanism only advanced on a *successful*
  association in the original single-leaf code — a persistently-unassociable detection was
  retried every poll, not silently debounced away. Preserving this exactly (rather than always
  updating the debounce state at the end of `poll()`) required an explicit `if observations:`
  guard before updating `_last_emitted_texts`; getting this wrong would have silently stopped
  retrying a detection that briefly fails to associate (e.g. `LoGetWorldObjects` momentarily
  missing the target) until its text changed. No test in the existing suite would have caught
  this regression — it's a behavior-preservation concern flagged for future stages to be aware of
  if `emit_mode`/debounce semantics change again in Stage 3.
- `reporting_name_for` lookup is case-insensitive and exact-match only (per
  `reporting_names.py`'s own docstring) — the four Finding-6 `object_type` strings matched the
  TSV verbatim (case-insensitively), so no near-miss/fallback behavior was exercised by this
  stage's fixtures. Worth keeping in mind if a future DCS patch renames one of these types.
