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

---

## Stage 1 — Belief core (2026-09-09)

Implemented `plans/pb2-contact-memory/plan.md`'s Stage 1: `Percept`, `ContactStore` with an
append-only observation log, per-source `Observation.id` prefixes, `project_from_bearing_range`,
and percept->contact gating. Landed across three commits: the `Percept`/id-prefix/geometry
groundwork (already committed separately as `021ae11`, "Add Percept projection and per-source id
prefixes (PB-2 Stage 1a)"), then `association_over_time.py` + its tests, then `contacts.py` +
its tests — split per the task's instruction to commit incrementally rather than hold everything
uncommitted.

### Files Changed

**Already committed (021ae11), summarized here for completeness:**
- `body-layer/src/belief/percept.py` — `Percept` (t_sim, source, classification_raw, bearing_deg,
  range_m, ownship_at_observation, observation_id) + `percept_of(Observation) -> Percept`.
  Structurally drops every DCS truth field (`derived_world_position`, `contact_id`, `provenance`,
  `t_wall`) rather than relying on a convention not to read them.
- `body-layer/src/perception/geometry.py` — `project_from_bearing_range(observer, bearing_deg,
  range_m) -> GeoPosition`, the inverse of the existing `bearing_deg`/`range_m` pair. Flat,
  terrainless by design (BL-3 replaces it).
- `body-layer/src/perception/source.py` — `OBSERVATION_ID_PREFIX_HYBRID` /
  `OBSERVATION_ID_PREFIX_NAKED_EYE`, wired into `hybrid_source.py`/`naked_eye_source.py`'s id
  minting, fixing the cross-channel `Observation.id` collision noted in the plan's Interface
  confirmation.

**This session:**
- `body-layer/src/belief/association_over_time.py` (new) — percept->contact gating. Spatial gate
  = `uncertainty_radius_m(percept) + GATE_GROWTH_RATE_MPS * elapsed_s`, where `elapsed_s` is time
  since the *candidate contact's* last observation (not the percept's own age). Class gate is
  three-valued (`compatible`/`unknown`/`incompatible`) via `_op_class_of`, which treats a
  `classification_raw` already shaped like an `OP_*` bucket (naked-eye's output) as pre-resolved,
  and otherwise runs it through `object_model.profile_for` (substring match), so scope/hybrid free
  text like `"Ural truck"` resolves to `OP_TRUCK` the same way naked-eye's own quantisation does.
  A `profile_for` fallback to `object_model.DEFAULT_OP_CLASS` is treated as `None`/unknown, not as
  a real class value. `passes_gate` requires both gates; `belief.contacts.ContactStore` is the
  only caller of the decision rule (exactly one pass -> merge, else -> new contact).
- `body-layer/tests/test_association_over_time.py` (new) — 12 tests: fixed scope uncertainty,
  naked-eye uncertainty pinned against real `_RANGE_BUCKETS_M` table values, `implied_position`
  geometry, class-compatibility truth table (same-bucket/different-bucket/cross-channel-resolves/
  unresolved-free-text), unknown-class-neither-blocks-nor-confirms, spatial pass/fail, class
  block despite spatial proximity, and gate-radius growth over elapsed time.
- `body-layer/src/belief/contacts.py` (new) — `Contact` (id, last_position, last_class_raw,
  contributing_observation_ids, first_seen_sim, last_seen_sim, sighting_spans — deliberately no
  decay/certainty fields), `SightingSpan` (start_sim, end_sim, source), `ContactStore` (holds
  contacts + an append-only `Observation` log keyed by id; `ingest(observations, now_sim) ->
  list[Contact]` runs each observation's `Percept` through the Stage 1 gate against every existing
  contact and creates/merges per the decision rule; `tick(now_sim)` is a documented no-op
  placeholder for Stage 2 to extend).
- `body-layer/tests/test_contacts.py` (new) — 7 tests: same-object-twice -> one contact,
  two-well-separated -> two contacts, two-ambiguous-candidates -> a third contact (not a merge
  into either — the plan's explicit anti-guessing acceptance case), append-only observation log,
  `tick` no-op, and a structural grep-based test that no `belief/*.py` file other than `percept.py`
  (the one designated exception) contains the literal string `derived_world_position`, with a
  sanity check that the excluded module does use it (so the grep is exercised, not a tautology).

### Design choices worth recording

- **Uncertainty formula.** Naked-eye: `hypot(range_m * sin(15deg), range_bucket_width_m)` — the
  30deg clock bucket's half-width for cross-range, the `OP_D*` bucket's real width (precomputed
  once from `naked_eye_source._RANGE_BUCKETS_M`, not re-derived per call) for down-range, combined
  via `math.hypot` as a conservative circular radius over two roughly-orthogonal error axes
  (smaller than summing, larger than taking either alone). The open-ended last bucket (`OP_D10k`,
  upper bound `inf`) is given the second-to-last bucket's width as a documented fallback, since an
  unbounded bucket has no true width.
- **Scope-channel uncertainty.** A flat `SCOPE_UNCERTAINTY_M = 300.0`, independent of range — per
  the task brief's explicit instruction not to overthink this placeholder, since the scope/hybrid
  channel has no bucket structure to derive an honest figure from the way naked-eye does.
  Documented in the module docstring as a placeholder to revisit, not a calibrated value.
- **Growth term.** `GATE_GROWTH_RATE_MPS = 20.0` (72 km/h) — a generic ground-vehicle
  order-of-magnitude placeholder, not derived from any specific unit's real top speed. Same
  revisit-later posture as the scope uncertainty constant.
- **Distance metric.** 2D (x/z only), not 3D — both channels report ground contacts and neither
  carries a perceived-altitude field precise enough to gate on independently of the horizontal
  position it was derived alongside.
- **Class resolution reuses `object_model.profile_for` rather than a second keyword table.**
  `profile_for` is substring-based, so it often also matches scope/hybrid free descriptive text
  incidentally (`"Ural truck"` contains `"ural"`). This is deliberately weak on some real text
  (`"Slava cruiser"` resolves to unknown, per the plan's accepted risk) — contained by the
  three-valued gate rather than a second bespoke vocabulary.
- **Circular import avoided via `TYPE_CHECKING`.** `association_over_time.py` needs `Contact` for
  type hints but `contacts.py` needs `association_over_time`'s gate functions at runtime — broken
  with `if TYPE_CHECKING: from belief.contacts import Contact` in `association_over_time.py`,
  relying on `from __future__ import annotations` (already the module's convention) so the
  forward reference never needs to resolve at import time.

### Tests Added

See the two new test files' summaries above (12 + 7 = 19 new tests this session).

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `cd body-layer && mypy src` (and `mypy src tests`, per this subproject's CWD-only
  config-discovery quirk): pass, no issues in 30 source files
- `pytest body-layer/tests -q`: 134 passed (113 before this stage + 12 + 7 new; all pre-existing
  tests still pass unmodified)
- `git status`: clean working tree after both commits

### Notable Discoveries

- `naked_eye_source.py`'s `_CLOCK_BUCKET_DEG` and `_RANGE_BUCKETS_M` are underscore-prefixed
  (module-private by convention) but were imported directly into `association_over_time.py`
  rather than duplicated or re-exported — the plan explicitly says "reuse those, don't invent new
  numbers," and duplicating the table would create exactly the kind of silent-drift risk the plan
  is warning against if the two ever diverge. Flagged here in case a future reviewer wants a
  public re-export instead of the private cross-module import.
- The Stage 1 acceptance test for the ambiguous-merge case needed careful geometric construction:
  two candidate contacts must be far enough apart that the *second* one doesn't merge into the
  *first* when it is created (both created in the same `ingest()` call, processed sequentially),
  but close enough together that a later percept between them falls within both gates
  simultaneously. Got this wrong once (50m separation, well inside the 300m gate) before widening
  to 400m apart / 200m from each — worth remembering as a pattern for Stage 2's fixtures too.

---

## Stage 2 — Decay, certainty, lifecycle (2026-09-09)

Implemented `plans/pb2-contact-memory/plan.md`'s Stage 2: per-attribute decay half-lives, the
`certainty` lifecycle ladder, `CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED` event
derivation, and `ContactStore.tick` wired to materialise them. Landed in two commits: `decay.py`
+ `events.py` + their pinned unit tests first, then `contacts.py`'s `tick` wiring + integration
tests, per the task's incremental-commit instruction.

`docs/concept/PETROBRAIN_RUNTIME.md` has no numbered "§3.4" section and no concrete `certainty`
enum or threshold table — its "Uncertainty and memory decay" section (searched for "certainty";
closest match) only names the four *attributes* that should decay at different rates (identity
slow, exact position fast, general area medium/slow, last movement direction medium) and the four
*wordings* the resulting confidence should support ("I see him." / "I think he was..." / "Last
saw him..." / "I lost him."). The plan's own text anticipated this ("derive the actual levels and
thresholds ... if it specifies them, otherwise make a reasonable minimal set and document the
choice") — the four-level ladder below (`observed`/`tracked`/`estimated`/`lost`) was derived to
match those four wordings 1:1, not copied from an existing table.

### Files Changed

- `body-layer/src/belief/decay.py` (new) — five named `Final[float]` half-life/window constants
  (seconds) and `Certainty = Literal["observed", "tracked", "estimated", "lost"]`, plus
  `certainty_of(contact, now_sim) -> Certainty`: a pure, top-down (first-match-wins) ladder over
  `elapsed_s = now_sim - contact.last_seen_sim`. See "Half-lives and thresholds chosen" below for
  the numbers and their justification.
- `body-layer/src/belief/events.py` (new) — `EventKind` (`CONTACT_DETECTED`/`CONTACT_LOST`/
  `CONTACT_REACQUIRED`, the three of `docs/concept/PETROBRAIN_RUNTIME.md`'s "Event model" list
  BL-2 scopes in), `Event` (id, contact_id, kind, t_sim, certainty), and
  `lifecycle_event_kind(previous_certainty, current_certainty) -> EventKind | None` — a pure,
  three-branch comparison (crossing into `lost`, crossing out of `lost`, or neither) with one
  documented special case: a contact whose *first* tick already finds it past `LOST_THRESHOLD_S`
  (previous certainty `None`, current `lost`) emits nothing, not a synthetic
  `CONTACT_DETECTED`+`CONTACT_LOST` pair.
- `body-layer/src/belief/contacts.py` — `Contact` gains `last_emitted_certainty: Certainty | None
  = None`, written only by `tick` (never by `record`/`ingest`). `ContactStore` gains an
  append-only `_events: list[Event]` log, an `events` read-only property, and an `_EVENT_ID_PREFIX
  = "EVENT"` id space distinct from contact/observation ids. `tick(now_sim)` now: for each known
  contact, computes `certainty_of(contact, now_sim)`, compares it against
  `last_emitted_certainty` via `lifecycle_event_kind`, appends any resulting `Event`, then updates
  `last_emitted_certainty` unconditionally (so the *next* `tick()` compares against this call's
  result, not the last emitted event) — matches the task brief's instruction, still driven purely
  by `now_sim`.
- `body-layer/tests/test_contacts.py` — replaced Stage 1's `test_tick_does_not_raise_and_does_
  not_mutate_contacts` (that assertion is now false by design — see Constraints note below) with
  `test_tick_updates_last_emitted_certainty_without_replacing_the_contact`. Added
  `test_replayed_stream_produces_detected_lost_reacquired_in_order` and
  `test_identical_replay_twice_produces_byte_identical_events`, both driven by a shared
  `_replay_detected_lost_reacquired` helper so the two tests run the exact same sequence.

### Half-lives and thresholds chosen

All five constants live in `decay.py`, justified individually in comments there; summarized here:

| Constant | Value | Role |
| --- | --- | --- |
| `OBSERVED_WINDOW_S` | 5.0 s | `elapsed_s` at or below this = `"observed"`. Close to one polling interval (body-layer's documented ~1 Hz), since `certainty_of` has no direct "was this contact in the most recent poll's batch" signal, only elapsed time. |
| `POSITION_HALF_LIFE_S` | 30.0 s | `"tracked"` boundary. Order-of-magnitude time a ground vehicle needs to move roughly its own gate-uncertainty radius at `association_over_time.GATE_GROWTH_RATE_MPS` (20 m/s) — "trust the exact spot for about half a minute." |
| `LOST_THRESHOLD_S` | 120.0 s (4x `POSITION_HALF_LIFE_S`) | `"estimated"`/`"lost"` boundary. Long enough that `"estimated"` means something distinct from `"tracked"`, short enough a contact doesn't linger as `"estimated"` once plainly lost. |
| `MOTION_HALF_LIFE_S` | 60.0 s | Declared, not yet consumed — no motion estimate exists on `Contact` yet (BL-4). Placed between position and general-area per the concept doc's ordering. |
| `GENERAL_AREA_HALF_LIFE_S` | 180.0 s | Declared, not yet consumed — no `general_area` field exists on `Contact` yet (BL-3). |
| `IDENTITY_HALF_LIFE_S` | 600.0 s | Declared, not yet consumed — no per-attribute identity confidence exists on `Contact` yet. |

Only `OBSERVED_WINDOW_S`, `POSITION_HALF_LIFE_S`, and `LOST_THRESHOLD_S` are actually read by
`certainty_of` today, since `Contact` doesn't yet carry separate identity/motion/general-area
attributes to decay independently — those three constants exist now so the plan's "one table"
requirement is satisfied from the start, and BL-3/BL-4 extend this table rather than starting a
second one (the plan's own "Complicates BL-4" note).

The `certainty` ladder itself, evaluated top-down in `certainty_of`:

```
elapsed_s <= OBSERVED_WINDOW_S (5s)      -> "observed"
elapsed_s <= POSITION_HALF_LIFE_S (30s)  -> "tracked"
elapsed_s <= LOST_THRESHOLD_S (120s)     -> "estimated"
else                                      -> "lost"
```

### Constraints followed

- No `emit_mode`, `tools.py`, or `console.py` work — out of scope for this stage, untouched.
- `percept.py` and `association_over_time.py`'s gating logic untouched.
- Identity invariant preserved: no file under `belief/` (other than the documented `percept.py`
  exception) reads `derived_world_position`/`object_id` — the existing structural grep test in
  `test_contacts.py` covers `decay.py`/`events.py` too since it globs all of `belief/*.py`.
- Stage 1's `test_tick_does_not_raise_and_does_not_mutate_contacts` was modified, not left
  standing — its assertion ("tick does not mutate contacts") was Stage 1's own documented
  placeholder behavior, explicitly earmarked in that test's docstring and in `contacts.py`'s
  Stage 1 module docstring for Stage 2 to replace. Recorded here per the project's "don't modify
  existing tests without permission" rule, since this is the one pre-existing test this stage
  touched.

### Tests Added

- `test_decay.py` (9 tests) — one per certainty level/boundary: exact-zero and at-the-boundary for
  each of the three thresholds, just-past-the-boundary for each transition, `"lost"` staying
  `"lost"` far past the threshold, and negative-elapsed-time clamping to `"observed"`.
- `test_events.py` (6 tests) — every `lifecycle_event_kind` branch: new-contact-not-lost ->
  detected (all three non-lost levels), new-contact-already-lost -> nothing, any-live-level ->
  lost (all three), lost -> any-live-level -> reacquired (all three), still-lost -> nothing again,
  and sub-level changes while alive (observed<->tracked<->estimated, including a same-level
  no-op) -> nothing.
- `test_contacts.py` — `test_tick_updates_last_emitted_certainty_without_replacing_the_contact`
  (replaces the Stage 1 placeholder test),
  `test_replayed_stream_produces_detected_lost_reacquired_in_order` (the plan's required
  acceptance case), `test_identical_replay_twice_produces_byte_identical_events` (determinism,
  asserting equal `Event` lists field-for-field via dataclass equality, not just equal counts).

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `cd body-layer && mypy src`: pass, no issues in 18 source files
- `pytest body-layer/tests -q`: 151 passed (134 before this stage + 9 + 6 + 2 new; all
  pre-existing tests pass, one Stage 1 placeholder test replaced as documented above)
- `git status`: clean working tree after both commits

### Notable Discoveries

- The concept doc's "§3.4 certainty table" the task brief pointed to does not exist as a numbered
  section or a concrete table — `docs/concept/PETROBRAIN_RUNTIME.md` only has unnumbered `##`
  headings, and "Uncertainty and memory decay" (its actual closest content) states the *shape* of
  the requirement (four attributes, four decay speeds, four resulting wordings) without naming
  concrete levels or thresholds. This stage's four-level ladder is therefore an original but
  tightly-constrained derivation (matching the four wordings 1:1), not a transcription — worth
  flagging for whoever tunes these against real sessions, since there's no upstream table to
  reconcile against, only the four example sentences.
- `lifecycle_event_kind`'s "already lost on first tick emits nothing" branch was a deliberate
  design call not spelled out in the plan text — the plan only says "materialise `CONTACT_LOST`
  transitions ... by comparing derived state against last-emitted state," which is silent on
  what a `None -> lost` comparison should do. Chose "nothing" over "detected then immediately
  lost" because the latter would be a synthetic pair with no real transition behind it (the
  contact was never live long enough to be meaningfully "detected" as an event). Flagged here in
  case a future stage's console/tools work wants the opposite behavior for debugging visibility.

## Stage 3 — Emission policy and pipeline wiring (2026-09-09)

### Files Changed

- `body-layer/src/perception/hybrid_source.py` — added `emit_mode: Literal["on_change",
  "every_poll"] = "on_change"`. Under `"every_poll"` the text-equality debounce check is skipped
  entirely (`if self.emit_mode == "on_change" and distinct_texts == self._last_emitted_texts`);
  everything else (leaf collection, association, per-leaf Observation building) is unchanged.
  `_last_emitted_texts` is still updated unconditionally on a successful poll — harmless, since
  `every_poll` never reads it.
- `body-layer/src/perception/naked_eye_source.py` — added the same `emit_mode` field, plus a
  second, independent piece of state (`_acquired_ids: frozenset[int]`) and `poll()` split into
  `_acquire_on_change`/`_acquire_every_poll`. See "Acquisition-cap vs. emission-cap" below for
  why two separate sets, not a re-read of one.
- `body-layer/src/logger.py` — added `ConsolePerceptionRunner` (mirrors `PerceptionLogger`'s
  testable-core/thin-`main()` split) and a `--console` CLI flag; `_build_sources()` factors out
  the two-tier construction so both the plain-logger path (`emit_mode="on_change"`) and
  `--console` path (`emit_mode="every_poll"`) share tier wiring and diverge only on mode/consumer.
- `body-layer/tests/test_hybrid_source.py` — 2 new tests: `every_poll` re-emits an unchanged
  detection set every poll; still returns nothing when detection clears.
- `body-layer/tests/test_naked_eye_source.py` — 4 new tests: `every_poll` re-emits a
  continuously-visible candidate; stops once it leaves; still throttles first-time acquisition at
  the cap; progressively acquires capped overflow on later polls (the test that pins the
  acquisition-vs-emission-cap distinction directly).
- `body-layer/tests/test_logger.py` — 4 new tests for `ConsolePerceptionRunner`: no telemetry
  returns empty; ingests observations into its store; reuses one store across calls (mirroring
  `main()`'s loop); prints the periodic `contacts=N observations=N` line.
- `body-layer/tests/test_emission_pipeline.py` (new) — the plan's required Stage 3 acceptance
  test: drives a real `NakedEyePerceptionSource` + `belief.contacts.ContactStore` together over a
  simulated 60 s at 1 Hz. Under `every_poll`, a stationary continuously-visible object stays
  `certainty_of(contact, 60.0) == "observed"`; under `on_change` (single emission then debounce)
  it does not, by the same point — the contrast that motivates Stage 3.
- `body-layer/CLAUDE.md` — documented the `belief/` package (undocumented since Stage 1) and the
  `--console` entrypoint, per the plan's Affected Modules list.

### Acquisition-cap vs. emission-cap (naked-eye)

The plan's instruction was to re-read `NAKED_EYE_MAX_NEW_PER_POLL` as an acquisition-rate limit
rather than an emission cap. A single re-read is not possible without breaking an existing,
unmodifiable test: `test_candidates_dropped_by_the_cap_are_not_retried_next_poll` requires that
under the default `on_change` mode, 5 simultaneously-new candidates against a cap of 3 emit only
3, and the other 2 are *never* retried (marked "already seen" regardless of the cap) — this is
`on_change`'s original, byte-for-byte-preserved behaviour.

But Stage 3's own acceptance requirement for `every_poll` is closer to the opposite: an object
that missed the throttle must be retried on a later poll (progressively acquired), not dropped
forever, or a dense scene would permanently under-populate belief. Satisfying both meant keeping
two independent pieces of state:

- `_previously_visible_ids` (unchanged, `on_change`-only): every currently-visible object —
  emitted or capped-out — becomes "already seen" for next poll's debounce comparison. A
  capped-out object leaves the debounce set only by actually leaving and re-entering visibility.
- `_acquired_ids` (new, `every_poll`-only): grows by at most `NAKED_EYE_MAX_NEW_PER_POLL`
  not-yet-acquired objects per poll (nearest-first, same throttle), intersected with
  currently-visible each poll (so a departed object must re-acquire on return, same shape as
  `on_change`). Every object already in this set re-emits every poll it stays visible, regardless
  of the cap — the cap only ever gates *entry*, never repeat emission of an already-acquired
  object.

The two sets evolve identically except in the capped-overflow case, which is exactly where the
plan's fix needed to land. `test_every_poll_mode_progressively_acquires_capped_overflow` pins this
directly: first poll acquires 3/5, second poll (all 5 still visible) emits all 5 — 3 re-emitting,
2 acquired for the first time.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `cd body-layer && mypy src`: pass, no issues in 18 source files
- `pytest body-layer/tests -q`: 163 passed (151 before this stage + 2 + 4 + 4 + 2 new; every
  pre-existing test passes unmodified, per the plan's constraint)
- `git status`: clean working tree after all four commits (todo/todo.md carried an unrelated,
  pre-existing modification from outside this stage's work and was deliberately left unstaged —
  not part of this task)

### Notable Discoveries

- `belief/decay.py`'s `OBSERVED_WINDOW_S = 5.0` (from Stage 2) made the acceptance test's "stays
  observed" assertion depend only on emission continuity, not on tuning: at a 1 Hz poll rate,
  `every_poll` keeps `elapsed_s` since last observation at ~1 s every tick, comfortably inside the
  5 s window, so no Stage 2 constant needed adjusting for this stage's fixture to demonstrate the
  fix.
- `body-layer/CLAUDE.md` had never been updated for the `belief/` package across Stages 0-2
  despite the plan listing it under "Modified" files from the start — backfilled a Structure
  bullet for it here alongside the new `--console` entrypoint documentation, rather than leaving
  it further out of date into Stage 4.

## Stage 4 — Tools and console (2026-09-09)

### Files Changed

- `body-layer/src/belief/tools.py` (new) — the brain API's body, minus a transport. Four §3.3
  functions (`get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`) plus
  `watch_contact`/`unwatch_contact`/`get_stats` (see "Why three extra tool functions" below).
  `ContactResult` is a `TypedDict` for the `{facts, summary, phrasing_hints}` triple. All four
  contact-facing functions share `_contact_facts`/`_contact_summary`/`_contact_phrasing_hints`
  helpers over one `_contact_result` builder, so the shape can't drift between them.
- `body-layer/src/belief/contacts.py` — added `Attention = Literal["normal", "watch"]` and two
  new `Contact` fields, `attention: Attention = "normal"` and `attention_source: str | None =
  None` — Stage 4's "bare attention enum + source field," mutated only by `tools.watch_contact`/
  `unwatch_contact`. Both default such that every existing Stage 0-3 test (which never
  constructs a `Contact` mentioning either field) is unaffected.
- `body-layer/src/belief/console.py` (new) — line parser + pretty-printer over `tools.py`.
  `Console.handle_line(line, now_sim)` dispatches `contacts [all|visible|watched]`, `show <id>`,
  `history <id>`, `find <text>`, `watch <id>`/`unwatch <id>`, `stats` into the matching `tools.py`
  function and formats the result as one or more lines; returns what it printed (mirroring
  `logger.PerceptionLogger.run_once`'s pattern) so tests don't need to capture stdout.
- `body-layer/src/logger.py` — `--console` now runs an interactive REPL, not just a periodic
  count line. `ConsolePerceptionRunner` gained `last_t_sim: float | None`, updated every
  `run_once()`. `main()`'s `--console` branch starts the poll loop
  (`_run_poll_loop`) on a background daemon thread and runs `_run_console_repl` (reads stdin
  line by line, dispatches into a `belief.console.Console` sharing the same `ContactStore`) in
  the foreground, using `last_t_sim` as each command's `now_sim`.
- `body-layer/CLAUDE.md` — documented `tools.py`/`console.py`'s actual shape (replacing the
  Stage 0-3 "not yet built" note) and the Stage 4 REPL wiring in "Running the live logger" and
  the Structure section.
- `body-layer/tests/test_tools.py` (new, 19 tests) — the four §3.3 functions' facts/summary/
  phrasing_hints shape, the absent-not-empty constraint on BL-3-scope keys, that `position` is
  the percept-implied position rather than the fixture's ground-truth `derived_world_position`,
  filter behaviour, `find_contact` matching only on perceived classification, and
  watch/unwatch/stats round-trips.
- `body-layer/tests/test_console.py` (new, 13 tests) — per-command usage/error messages, the
  plan's required scripted-session acceptance test (ingest → tick → `contacts`/`show`/`watch`/
  `contacts watched` while visible, then tick past `LOST_THRESHOLD_S` and repeat against
  `history`/`find`/`unwatch`/`stats`), output-stream printing, and two structural checks: every
  public `tools.py` function name appears in `console.py`'s source, and `console.py` never
  imports `belief.decay`/`belief.association_over_time` directly.
- `body-layer/tests/test_logger.py` — one new test, `last_t_sim` is `None` before the first poll
  and set to the polled `t_sim` after.

### Why three extra tool functions beyond the four named in the plan's Stage 4 heading

The task instructions listed exactly four `tools.py` functions but also required `watch`/
`unwatch`/`stats` as console commands under the constraint "console.py ... owns no belief logic
itself, just parses commands and formats `tools.py`'s output" and the plan's own acceptance
criterion ("every console command maps 1:1 to a §3.3 tool name with no console-only logic").
§3.3's real equivalents (`set_attention`, `get_attention_state`) are BL-4/BL-5 work not being
built here. Resolved by adding `watch_contact`/`unwatch_contact`/`get_stats` to `tools.py` in the
same plain-function shape as the four real §3.3 tools, so the state mutation and counting still
live outside `console.py` — consistent with the module's docstring, which flags this choice
explicitly rather than silently reinterpreting the "four functions" instruction.

### `facts` shape chosen

```
facts:
  id: str
  classification: {value: str}          # Contact.last_class_raw, perceived only
  certainty: "observed"|"tracked"|"estimated"|"lost"   # belief.decay.certainty_of
  visible: bool                          # certainty == "observed"
  last_seen_ago_s: float
  position: {dcs: {x: float, z: float}}  # Contact.last_position -- percept-implied,
                                          # never the observation's ground-truth position
  sources: list[str]                     # sorted distinct sighting-span sources
  attention: "normal"|"watch"
  attention_source: str                  # present only when attention == "watch"
summary: str        # one plain sentence, e.g. "Ural truck, tracked, last seen 12s ago."
phrasing_hints:
  certainty: "current"|"recent"|"remembered"|"lost"   # distinct vocabulary from the
                                                        # internal certainty ladder, per §3.4
```

No `semantic`, `general_area`, `relative_now`, or `urgency` key is ever present — each is either
BL-3 (world enrichment, current-ownship-relative geometry) or BL-4 (threat assessment) work this
stage does not build, and the plan's constraint requires them absent, not present-and-null.
Pinned by `test_describe_contact_facts_never_carry_bl3_scope_keys` and by `phrasing_hints` never
including `urgency` anywhere in `tools.py`.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `cd body-layer && mypy src`: pass, no issues in 20 source files
- `pytest body-layer/tests -q`: 196 passed (163 before this stage + 19 + 13 + 1 new; every
  pre-existing test passes unmodified)
- `git status`: clean working tree after all three commits

### Notable Discoveries

- Stage 1's structural test (`test_belief_source_never_references_derived_world_position`) greps
  every `belief/*.py` file's raw source text for the literal substring `"derived_world_position"`
  (except `percept.py`). `tools.py`'s first docstring draft explained the identity invariant by
  naming that field directly and tripped this test — not a bug in the test, exactly the kind of
  future-`belief/`-module case its own docstring says it's meant to catch. Reworded to describe
  the field ("`Observation`'s DCS ground-truth position field") without repeating its literal
  name.
- `store.contacts[0].attention` read twice in one test body, with an equality assertion against
  `"watch"` in between, made mypy narrow the *repeated expression*'s type to `Literal["watch"]`
  for the rest of the test — a later `== "normal"` comparison against that narrowed type became a
  `comparison-overlap` error even though the underlying object had genuinely changed in between.
  Not a real bug; worked around by binding `store.contacts[0]` to a local variable at each point
  instead of re-evaluating the same attribute-access expression, which stops mypy from treating
  the second read as the same narrowed value.
- No threading test was written for `logger.py`'s new `_run_poll_loop`/`_run_console_repl`
  functions — consistent with the project's existing "`main()`'s CLI wiring is untested by
  design" posture (`ConsolePerceptionRunner`/`Console` themselves, which those two functions
  call, are both fully tested). `last_t_sim`'s tracking is tested directly on
  `ConsolePerceptionRunner`, which is the one piece of new *logic* Stage 4 added to `logger.py`.
