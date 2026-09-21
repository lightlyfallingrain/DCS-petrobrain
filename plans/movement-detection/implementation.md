### Implementation Summary

All five stages (0-4) of `plans/movement-detection/plan.md` implemented and tested. Baseline was
887 passed, 4 xfailed in body-layer; final is 929 passed, 4 xfailed (0 regressions). aircraft-layer
baseline behavior preserved; final is 159 passed (up from 143, 16 new tests for the unit-velocity
channel).

**Stage 0 benchmark result:** parse→join→gate over 300 synthetic units, through the exact functions
`NakedEyePerceptionSource.poll` calls, measured ~1 ms median (`body-layer/tests/
test_motion_benchmark.py`, asserts a generous 500 ms ceiling as a regression guard, not a precision
timing tool). Confirms the plan's expectation that this cost is irrelevant next to
`check_visibility`'s own. Stage 0 parts 1-2 (bridge call overhead, in-state `getVelocity()` loop
cost) are not Mac-answerable — they self-measure on the next live sortie via the Hook's own
`os.clock()`/`dcs.log` logging, per the plan's design.

### Files Changed

**aircraft-layer (Stage 1 — velocity transport)**
- `aircraft-layer/src/schema/unit_velocity.py` — new. `UnitVelocitySample`/`UnitVelocitySnapshot`,
  parsing the Hook's compact `"<count>|<t_sim>|<name>:<vx>:<vy>:<vz>;..."` wire string.
- `aircraft-layer/src/schema/world_objects.py` — `WorldObjectSample.unit_name: str | None`, the
  join key (`LoGetWorldObjects`'s own `UnitName`).
- `aircraft-layer/src/schema/__init__.py` — re-exports the three new `unit_velocity` names.
- `aircraft-layer/src/collector/unit_velocity_receiver.py` — new. `UnitVelocityReceiver`, a UDP
  listener on port 7795, mirroring `f10_command_receiver.py`'s open/serve_forever/close shape.
- `aircraft-layer/src/collector/cache.py` — `UnitVelocityCache`, single-slot "latest" cache.
- `aircraft-layer/src/collector/__main__.py` — wires the receiver + cache into the collector
  process, `--unit-velocity-host`/`--unit-velocity-port` flags.
- `aircraft-layer/src/api/server.py` — `GET /unit_velocity/latest`.
- `aircraft-layer/src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bumped to `2026-09-22b`.
- `aircraft-layer/dcs-export/Export.lua` — `unit_name` added to the world-objects wire line;
  `EXPORT_SCRIPT_VERSION` bumped to match.
- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` — new. Third Hook script,
  polls `Object.getVelocity()` for every unit/static via `net.dostring_in("scripting", ...)` at
  1 Hz, stamps sim time **inside the scripting state** via `timer.getTime()` (never
  `DCS.getRealTime()` — the plan's sharpest replay-determinism risk), self-measures
  `bridge_call_ms` via `os.clock()`, logs `unit_count`/`bridge_call_ms` to `dcs.log` every poll,
  forwards one JSON datagram per poll to the new receiver.
- `aircraft-layer/tests/test_unit_velocity_schema.py`, `test_unit_velocity_cache.py`,
  `test_unit_velocity_receiver.py`, `test_unit_velocity_api.py` — new, mirroring the F10 channel's
  own four-file test split.
- `aircraft-layer/tests/test_world_objects_schema.py` — `unit_name` parse/round-trip tests added.
- `aircraft-layer/ROADMAP.md` — new Status entry.

**body-layer — perception (Stage 2 — the gate)**
- `body-layer/src/perception/motion.py` — new. `Vec3`, `MOTION_ANGULAR_THRESHOLD_RAD_S`,
  `MOTION_VELOCITY_MAX_SKEW_S`, `apparent_angular_rate_rad_s`, `evaluate_motion_gate`,
  `is_apparently_moving`. Pure, no `belief/` import — the velocity vector never leaves this module.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate.velocity: Vec3 | None`,
  `from_dict` gains a `velocity=` keyword (an already-resolved `{"vx","vy","vz"}` dict).
- `body-layer/src/perception/source.py` — `Observation.apparent_motion: bool | None = None`.
- `body-layer/src/perception/naked_eye_source.py` — `_resolve_velocity_by_object_id` (the
  `unit_name` join, skew bound, same-poll uniqueness-collision handling), the motion gate run
  per gate-admitted candidate, `motion_by_object_id` threaded through `_build_observations`/
  `_build_observation` the same way `confidence_by_object_id` already is, cluster-level
  `apparent_motion` aggregated by "identical keeps, disagreement degrades to `None`" (the same
  rule `Cluster`'s aggregate classification already follows). The `get_unit_velocity_latest()` call
  is wrapped in `try/except AircraftLayerError` — the feed must be independently degradable
  (Decision 2), so a stale collector or a missing `autoexec.cfg` opt-in degrades to "motion
  unknown everywhere," never a crashed poll.
- `body-layer/src/perception/detection_trace.py` — `DetectionTrace` gains five optional motion
  fields (`motion_speed_mps`, `motion_perp_speed_mps`, `motion_angular_rate_rad_s`,
  `motion_threshold_rad_s`, `motion_skew_s`, `apparent_motion`) and `DetectionTraceCollector.
  annotate_motion`, so a movement-gate negative is inspectable in a BL-9 trace, not silent.
- `body-layer/src/aircraft_client.py` — `get_unit_velocity_latest()`.
- `body-layer/tests/test_motion.py` — the roadmap's 3-row sanity table reproduced verbatim, the
  constant-bearing blind-spot pin (deliberately `False`, documented as a feature), a non-axis-
  aligned angular-formula test (project rule), early-out-vs-full-computation field population.
- `body-layer/tests/test_motion_benchmark.py` — Stage 0 part 3.
- `body-layer/tests/test_naked_eye_source.py`, `test_detection_trace.py`, `test_emission_pipeline.py`,
  `test_logger.py` — fake `AircraftLayerClient` doubles gained `get_unit_velocity_latest`.

**body-layer — belief (Stage 3 — state and event)**
- `body-layer/src/belief/motion.py` — new. `MotionBelief`, `fold_motion` — asymmetric
  promote-on-one-observation / demote-only-after-`MOTION_STOP_CONFIRM_S`-of-continuous-sub-threshold
  rule. `Contact.motion` is `None`-able for the contact's *whole life* (unlike
  classification/cardinality), since only the naked-eye channel supplies motion evidence at all.
- `body-layer/src/belief/decay.py` — `MOTION_HALF_LIFE_S` (already declared, unconsumed since BL-2)
  now consumed by `motion_confidence_at`; `MOTION_STOP_CONFIRM_S` (5.0s, uncalibrated placeholder)
  added.
- `body-layer/src/belief/contacts.py` — `Contact.motion`/`motion_pending_stop_since_sim`/
  `last_emitted_motion`; folded in `record()`/`from_percept()`; compared in `tick()` between
  cardinality and attention (lifecycle → classification → cardinality → motion → attention).
- `body-layer/src/belief/events.py` — `CONTACT_MOTION_CHANGED` added to `EventKind`,
  `motion_event_kind` — **see Notable Discoveries below, this one does not follow the other four
  kinds' "previous is None means first tick" convention, by necessity, not oversight.**
- `body-layer/src/belief/percept.py` — `Percept.apparent_motion`, threaded through `percept_of`.
- `body-layer/tests/test_belief_motion.py` — `fold_motion` unit tests (promote-fast, demote-slow
  with the confirm window, `None` holds both belief and countdown, a `True` mid-countdown cancels
  the demotion, reinforcement).
- `body-layer/tests/test_contacts_motion.py` — end-to-end `ingest`/`tick` integration: founding with
  no evidence stays `None`, one `True` promotes immediately, demotion needs the full confirm
  window not one observation, `None` never demotes/promotes, cooldown suppresses emission without
  losing the transition.
- `body-layer/tests/test_events.py`, `test_decay.py` — `motion_event_kind`/`motion_confidence_at`
  unit tests.

**body-layer — reporting (Stage 4)**
- `body-layer/src/belief/tools.py` — `_motion_facts` (`facts["motion"] = {state, confidence}`,
  omitted entirely when `Contact.motion is None`, the module's absent-not-null convention).
- `body-layer/src/belief/console.py` — `_SHOW_FACT_KEYS` gains `"motion"`.
- `body-layer/src/belief/speech.py` — `_contact_report_text` appends `", moving"` only when
  `facts["motion"]["state"] == "moving"` — one clause, trimmable, "stopped" stays the unremarked
  default (mirrors the semantic-fragment/count-clause precedent of only stating what's notable).
- `body-layer/tests/test_tools_motion.py` — new. `facts["motion"]` shape, omission, confidence decay.
- `body-layer/tests/test_speech.py` — moving-clause present/absent tests.

**Docs**
- `body-layer/ROADMAP.md` — Movement detection entry updated `[>]` → `[~]`, implementation summary
  and Stage 0 benchmark number appended, live-acceptance items named explicitly (the Hook's own
  self-measurement, the `timer.getTime()`/`LoGetModelTime()` clock-identity assumption).
- `docs/concept/STATE_TRANSITIONS.md` — "None of this exists yet" replaced: `moving/stopped` is
  built; the other three behaviour-change rows are not.

### Tests Added
See the per-file breakdown above — 42 new body-layer tests, 16 new aircraft-layer tests, plus
`unit_name` coverage added to the existing `test_world_objects_schema.py`.

### Checks
(world-model/ untouched, not run)

**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (17 source files)
- pytest: 159 passed (was 143 before this work)
- `luac5.1 -p` on `Export.lua` and `petrobrain-mission-telemetry-hook.lua`: pass

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (43 source files)
- pytest: 929 passed, 4 xfailed (was 887 passed, 4 xfailed before this work — 0 regressions)

### Notable Discoveries

1. **The test-impact list check (role step 1b) caught real, unlisted breakage.** The plan named no
   test files at all as impacted (it's a from-scratch feature, not a refactor), but adding an
   unconditional `get_unit_velocity_latest()` call inside `NakedEyePerceptionSource.poll` broke six
   pre-existing tests across four files (`test_detection_trace.py`, `test_emission_pipeline.py`,
   `test_logger.py`, `test_mock_flight_chain.py`) whose hand-rolled fake `AircraftLayerClient`
   doubles didn't implement the new method. Two of the six were HTTP 404s against a real mock server
   lacking the route (fixed by making the call independently degradable per Decision 2 — wrapping it
   in `try/except AircraftLayerError`, which is also the *correct* production behavior for an
   aircraft-layer instance without the `autoexec.cfg` opt-in or a pre-Stage-1 collector, not just a
   test fix); four were `AttributeError`s from fakes missing the method entirely (fixed by adding
   `get_unit_velocity_latest() -> None` to each double).

2. **`motion_event_kind`'s first design had a real bug, caught by the plan's own promote-on-one-
   observation test requirement, not by inspection.** The first draft copied the other four event
   kinds' "`previous is None` means this is the contact's first tick, suppress the event" rule
   verbatim. That rule is sound for `Certainty`/`ClassificationBelief`/`Attention`/cardinality's
   `(lo, hi)` because those are *always* established the instant a contact is founded — `previous is
   None` only ever coincides with tick #1. `Contact.motion` is different by design (per the plan:
   only the naked-eye channel supplies motion evidence, so a contact can go many ticks with `motion
   is None`), so `previous is None` most often means "motion was just established for the first
   time," not "tick #1" — and the copied rule silently swallowed that exact transition, the one this
   whole milestone exists to report. Caught by
   `test_contacts_motion.py::test_tick_emits_contact_motion_changed_after_promotion`, which the
   plan's own "promote on one observation" acceptance criterion required writing. Fixed by dropping
   the `previous is None` suppression for this kind specifically (`current is None` is the only
   no-event case now) — documented at length in `motion_event_kind`'s own docstring since it's a
   deliberate departure from every sibling function in the same file, not an inconsistency to
   "clean up" later.

3. **Plan wording vs. actual filenames**: the plan's Affected Modules section names
   `body-layer/src/belief/tool_api.py` — no such file exists; the brain-facing query API lives in
   `belief/tools.py`. Treated as the plan's own naming slip and implemented against the real file.

4. **The wire format for the compact-string return from `dostring_in` and the JSON envelope around
   it were both left unspecified by the plan** (it names the two general shapes -
   "`dostring_in` can only return simple values" and "one JSON datagram per poll" - but not the
   exact framing). Implemented as `"<unit_count>|<t_sim>|<name>:<vx>:<vy>:<vz>;..."` for the
   in-state return (mirroring the F10 hook's own comma-joined single-string precedent) wrapped in
   `{"payload": "...", "bridge_call_ms": <float>}` for the UDP datagram — a design choice, not a
   plan-stated requirement, recorded here so a future reader doesn't mistake it for one.
