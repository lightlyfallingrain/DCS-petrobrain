### Implementation Summary

Stage A of `BL-B72` (the shared emitter-visibility gate bypass plus the burning-unit emitter) and
`AC-B7` (life fields on the existing mission-telemetry bridge), per `plans/emitter-visibility/plan.md`.
`BL-B73`/`BL-B74`/`AC-B8` (gun fire, SAM launch tail, their transport) are out of scope and untouched.

### Files Changed

**aircraft-layer**

- `dcs-export/petrobrain-mission-telemetry-hook.lua` — added `lifeFields(obj)` (reads
  `getLife()`/`getLife0()` per `pcall`, returns `"life:life0"` or `"nil:nil"`) **inside the
  `VELOCITY_CODE` string**, not as a Hook-local function — `VELOCITY_CODE` executes in the separate
  `"scripting"` mission state via `net.dostring_in`, which cannot see a function defined in the
  Hook's own Lua state. (Caught this while writing it; the first draft defined `lifeFields` as a
  Hook-local function, which would have silently failed at runtime with no local way to verify it.)
  Both live units and static objects get the two trailing fields now.
- `src/schema/unit_velocity.py` — `UnitVelocitySample.life`/`life0: float | None = None`.
  `_parse_entry` now tries the new 6-field shape (`rsplit(":", 5)`) first and falls back to the
  legacy 4-field shape when that doesn't produce exactly 6 parts — backward compatible with a Hook
  predating `AC-B7`, and verified against the one existing colon-in-name test
  (`test_unit_name_containing_colon_is_handled_via_rsplit`), which has exactly 4 colons and
  correctly falls through to the legacy parse. `to_dict()` omits `life`/`life0` keys when `None`,
  keeping the existing `test_to_dict_round_trips_samples` byte-identical.
- No changes needed to `collector/unit_velocity_receiver.py` or `src/api/server.py` — both are
  payload-agnostic / call `to_dict()` straight through.

**body-layer**

- `src/perception/emitters.py` **(new)** — `EmitterKind.BURNING`, `Emitter`, `FIRE_LIFE_FRACTION_MAX`
  (`tuning.real`, status `"judgement"` — `tuning.Status` has no `"assumption"` literal, see the
  constant's own comment), `burning_emitters(raw_objects, samples)`.
- `src/perception/visibility.py` — `check_visibility(..., emitter: Emitter | None = None)`. Gates 3
  (range/size) and 5 (forest) are bypassed only when they would otherwise have rejected the
  candidate; gates 0/1/2/4 (gaze, cockpit mask, optic FOV, terrain LOS) are untouched. Whenever
  either bypass fires, the tier is clamped to `NAKED_EYE_GATING_TIER_NAME`/`NAKED_EYE_PRESENCE_CONFIDENCE`
  and `_achieved_tier` is never called; `VisibilityResult.emitter_kind` records which kind (if any)
  actually bypassed a gate.
- `src/perception/detection_trace.py` — `DetectionTrace.emitter_kind: str | None = None`.
- `src/perception/naked_eye_source.py` — `PROVENANCE_EMITTER_BURNING` and
  `_PROVENANCE_BY_EMITTER_KIND` (declared here, not in `source.py` — see note below). `poll()`
  resolves `emitter_by_object_id = burning_emitters(raw_objects, unit_velocity["samples"])` off the
  already-fetched `/unit_velocity/latest` snapshot, threads `emitter=emitter_by_object_id.get(...)`
  into `check_visibility`, and `_build_observation` sets `PROVENANCE_EMITTER_BURNING` only when
  every cluster member's `emitter_kind` agrees (mixed cluster keeps the ordinary provenance).
- `src/belief/percept.py` — `Percept.provenance: str | None = None`, carried through unchanged by
  `percept_of`.
- `src/belief/events.py` — `CONTACT_BURNING_SEEN`, `burning_event_kind` (fires only on the entering
  transition, never the reverse — no "stopped burning" callout exists).
- `src/belief/contacts.py` — `Contact.is_burning: bool = False` (written directly by `record`/
  `from_percept` from `percept.provenance`, overwritten like `last_class_raw`, not folded) and
  `Contact.last_emitted_burning: bool | None = None`. `ContactStore.tick` gained a block emitting
  `CONTACT_BURNING_SEEN` — deliberately **no** `observable_or_grace` check (unlike the
  `CONTACT_MOTION_CHANGED` block it sits beside), since that check is a historical, pre-comprehensive-fix
  gate and `CalloutScheduler.tick`'s own observability gate already covers every `_TEMPLATED_KINDS`
  member uniformly at speak-time.
- `src/belief/callouts.py` — `CONTACT_BURNING_SEEN` added to `_TEMPLATED_KINDS` only (not
  `_WATCHED_ONLY_KINDS`, not `_OBSERVABILITY_EXEMPT_KINDS`). **Deliberately not routed through
  `belief.threat.envelope_for`** — reuses the existing `callout_priority`/`_DEFAULT_THREAT_BAND`
  tuple unchanged, which is already a flat placeholder (0) for every event today, not a real
  classification-derived band. Burning is "not a threat line" by the plan's own words, so it needs
  no elevated priority lane — Stage B/C's gun-fire/SAM-launch emitters are the ones that will need
  one, per the plan's finding 2.
- `src/belief/speech.py` — `_render_lifecycle_text`'s `CONTACT_BURNING_SEEN` branch: a bespoke
  `f"Something burning, {clock} o'clock."` line (not `_contact_report_text`, whose generic form
  would say "ground, two o'clock, 2.3 kilometres" for a `PRESENCE`-level contact and carry a range
  the accepted wording does not). Returns `None` (speaks nothing) when `relative_now` is absent.
- `config/defaults.toml` — regenerated via `tools/generate_defaults.py --write` for the new
  `FIRE_LIFE_FRACTION_MAX` key.

### Tests Added

- `tests/test_unit_velocity_schema.py` (aircraft-layer, 6 new) — life-field presence/absence/`"nil"`,
  the colon-in-name disambiguation, a malformed life field raising, `to_dict()`'s omit-when-`None`.
- `tests/test_emitters.py` (new, 11) — `burning_emitters` fraction-bracket boundaries, no-samples,
  non-unique `unit_name` collision, malformed entries.
- `tests/test_visibility.py` (10 new) — the regression gate (9 km burning admitted at `lowres`/same
  unit not burning rejected), forest bypass, terrain-LOS/gaze/cockpit-mask non-bypass, "never lowers
  what would already be seen", the default-`None` no-op, and the two detection-trace
  (`emitter_kind`/`threshold_bound="emitter_bypass"`) tests.
- `tests/test_events.py` (5 new) — `burning_event_kind`'s one-directional transition rule.
- `tests/test_contacts_burning.py` (new, 7) — `Contact.record`'s `is_burning` overwrite semantics,
  `ContactStore.tick` emission including the founded-already-burning case, the one-directional
  leaving-transition silence, and the event cooldown.
- `tests/test_speech.py` (3 new) — the accepted wording, the no-range-clause/no-`relative_now`
  silence, auto-acknowledge.
- `tests/test_naked_eye_source.py` (5 new) — end-to-end: burning-at-9km visible, same-unit-healthy
  invisible, burning-behind-terrain invisible, the plan's explicitly-requested group-salience
  non-interaction pin, and "emitter present but unneeded keeps ordinary provenance."

### Checks

**aircraft-layer**
- `ruff format --check .`: pass (pre-existing unrelated finding in `research/2026-10-06-unit-id-join-reduce.py`)
- `ruff check .`: pass (pre-existing unrelated `EXE001` in the same research file)
- `mypy src`: pass (21 source files)
- `pytest -q`: 262 passed

**body-layer**
- `ruff format --check .`: pass (pre-existing unrelated finding in `research/2026-10-05-security-audit.md`,
  the exact file the dispatch prompt said to expect)
- `ruff check .`: pass
- `mypy src`: pass (60 source files)
- `pytest -q`: 1998 passed, 4 xfailed (baseline 1957 passed/4 xfailed + 41 new tests)

Note: `mypy tests` (not part of the mandated command) reports ~150 pre-existing errors across
`test_crew_console.py`, `test_logger.py`, `test_mock_flight_chain.py`, `test_forest.py`,
`test_brain_client.py`, `test_aircraft_client.py`, `test_callouts.py`, `test_speech.py` — none in
lines this feature touched; not investigated further since the documented command is `mypy src`.

### Review Round 2 -- Both Required Fixes

`plans/emitter-visibility/review.md` found two required fixes against the Stage A code above.
Both addressed; nothing else changed.

**Fix 1 -- closed `Percept.emitter_kind` instead of a `Percept.provenance` passthrough.**

- `src/belief/percept.py` -- replaced `Percept.provenance: str | None = None` with
  `Percept.emitter_kind: str | None = None` (one of `perception.emitters.EmitterKind`'s values,
  or `None`). `percept_of` no longer passes `observation.provenance` through; it derives
  `emitter_kind` via a new module-level `_EMITTER_KIND_BY_PROVENANCE: dict[str, str]` mapping
  (`PROVENANCE_EMITTER_BURNING -> EmitterKind.BURNING.value` today), looked up with `dict.get`
  so any `provenance` value not in the mapping -- every non-emitter value, and any future
  `PROVENANCE_*` constant nobody has registered here yet -- resolves to `None`. This is the
  reviewer's own recommended design (review.md fix 1's fourth bullet), chosen over the
  alternative it also offered (adding `Observation.emitter_kind` and having `naked_eye_source.py`
  populate it directly): the mapping approach needed no change to `Observation`'s shape or to any
  of the many existing tests that construct an `Observation` with `provenance=PROVENANCE_EMITTER_
  BURNING` (`test_contacts_burning.py`, `test_speech.py`) -- those tests continue to exercise the
  real production path (`Observation.provenance` -> `percept_of` -> `Contact.is_burning`)
  unchanged, rather than needing to be rewritten to set a new field the old fixtures never knew
  about.
- `src/belief/contacts.py` -- `Contact.record`/`Contact.from_percept` now derive `is_burning` as
  `percept.emitter_kind == EmitterKind.BURNING.value`, not `percept.provenance ==
  PROVENANCE_EMITTER_BURNING`. Import changed from `perception.naked_eye_source.
  PROVENANCE_EMITTER_BURNING` to `perception.emitters.EmitterKind` (the latter is the lower-level,
  canonical home for the enum -- `naked_eye_source.py`'s own provenance constants are a specific
  channel's wiring of it, and `belief/percept.py` is the only place that still needs to know about
  `PROVENANCE_EMITTER_BURNING` directly, for the mapping above).
- `tests/test_percept.py` -- `"provenance"` restored to `_TRUTH_FIELD_NAMES`; the comment block
  explaining the prior removal replaced with one explaining why it stays and what carries the
  signal instead. Added two small unit tests: `test_percept_of_maps_emitter_provenance_to_
  emitter_kind` and `test_percept_of_maps_non_emitter_provenance_to_none`, covering the new
  mapping directly (the existing end-to-end tests in `test_naked_eye_source.py`/
  `test_contacts_burning.py`/`test_speech.py` already covered the integration path, but nothing
  exercised `percept_of`'s mapping as a unit).
- No change was needed to `Observation`, `test_naked_eye_source.py`'s provenance-constant tests,
  `test_speech.py`, or `test_contacts_burning.py` -- all of them already construct/assert
  `Observation.provenance`, which is unchanged; only the belief-side consumer moved.

**Fix 2 -- the group-salience non-interaction test made falsifiable.**

`tests/test_naked_eye_source.py::test_emitter_does_not_widen_group_salience_for_a_non_emitting_
neighbour` placed both the burning unit and the healthy neighbour at 9 km, beyond even `group_
salience.py`'s relaxed `RESOLUTION_ANGULAR_RADIUS_RAD` admission threshold (5468.75 m for a 7 m
vehicle under `UNAIDED_OPTIC`, computed directly: `7.0 / 0.00128 * 1.0`). Moved the healthy
neighbour to 4 km with a 200 m cross-range offset (bearing ~2.86 deg off the burning unit's, far
enough that the two do not cluster into one report): beyond `LOWRES_ANGULAR_RADIUS_RAD`'s own
lone-presence threshold (2333.33 m) but inside the relaxed one, so a candidate wrongly marked
`group_salient` is admitted where a correctly-unflagged one is rejected -- the window the leak
this test guards against would actually open.

Note the review's own prose cited this window as "~5.4-9.3 km"; measuring it directly from the
running code (`LOWRES_ANGULAR_RADIUS_RAD`/`RESOLUTION_ANGULAR_RADIUS_RAD`, `UNAIDED_OPTIC.
presence_range_mult`, size_m=7.0) gives 2333.33-5468.75 m instead -- the "5.4" half matches, the
other bound does not. Flagging this rather than reproducing the stated numbers uncritically,
per this role's falsifiability discipline; the window used above is the one verified by running
the real admission formula and by the red/green proof below, not the one quoted in review.md.

**Red/green proof**, run against `src/perception/naked_eye_source.py`'s `salient_ids =
group_salient_ids(...)` call site (the exact shape of the plan's own Risks-section leak, "one AAA
gun makes a whole convoy visible"):

- Checksum before mutating: `5b2b4286225d0f738ea4a6df585157a418b4da2b`.
- Mutation: `if emitter_by_object_id: salient_ids = frozenset(c.object_id for c in candidates)`
  inserted immediately after the real `group_salient_ids` call.
- `pytest -q tests/test_naked_eye_source.py -k test_emitter_does_not_widen_group_salience -v` ->
  **FAILED**: `assert len(observations) == 1` with `AssertionError: assert 2 == 1` -- the healthy
  neighbour was wrongly admitted as its own second observation.
- Mutation reverted; checksum after: `5b2b4286225d0f738ea4a6df585157a418b4da2b` (identical to
  before -- confirmed by checksum, not by eye).
- Same command re-run -> **PASSED**.

### Notable Discoveries

1. **A real pre-existing test conflicted with the plan's own design, and had to be changed.**
   `test_percept.py::test_percept_has_no_truth_carrying_field` asserted `"provenance"` must **never**
   be a `Percept` field name, listing it alongside genuine DCS-truth fields (`derived_world_position`,
   `contact_id`, `t_wall`). The plan explicitly requires `Observation.provenance` to cross into
   belief (`Contact.is_burning` has no other sanctioned way to learn it). `provenance` is not a
   truth field by this project's own definition — it's a channel's honest statement about itself,
   same footing as `classification_level`/`count_bucket`, both already on `Percept`. Removed it from
   the test's `_TRUTH_FIELD_NAMES` set with a comment explaining why, rather than leaving the
   feature broken or silently working around the boundary. Flagging this per role instructions
   rather than treating it as routine.
2. **The plan names `source.py` as `PROVENANCE_EMITTER_*`'s home, but its sibling constant
   `PROVENANCE_VISIBILITY_FILTER_ONLY` actually lives in `naked_eye_source.py`**, not `source.py` —
   confirmed by `grep`, not assumed. Declared `PROVENANCE_EMITTER_BURNING` beside its real sibling
   instead of where the plan said, with a comment noting the discrepancy for whoever adds
   `PROVENANCE_EMITTER_FIRING`/`_LAUNCH_SMOKE` in `BL-B73`/`BL-B74`.
3. **The Lua life-field helper almost shipped as a Hook-local function**, which would have been a
   silent no-op at runtime (`VELOCITY_CODE` executes in the separate `"scripting"` mission state via
   `net.dostring_in`, with no visibility into the Hook's own Lua state) — the exact class of defect
   this project's "DCS debug logging preemptive" lesson exists to catch, except this one has no log
   line to catch it with; only re-reading `petrobrain-f10-commands-hook.lua`'s own header (which
   states its snippets must be self-contained strings) caught it before it reached a sortie.
4. **128-sightline-cap exposure (per the dispatch prompt's request to state this explicitly):**
   Stage A is not newly exposed to `MAX_SIGHTLINES_PER_CALL = 128`'s nearest-first truncation in any
   way Stage B/C are not. A burning unit's emitter bypass only ever fires at gates 3/5
   (range/size, forest); gate 4 (terrain LOS) is completely unchanged and still consults
   `candidate.live_los_clear`, which is `None` (fail-closed reject) for any candidate the Hook's
   128-cap truncated out of this poll's wedge query — exactly the same exposure every existing
   far candidate already has today, with or without this feature. Stage A does not change which
   candidates are inside or outside that cap; it only changes what happens to a candidate already
   inside it. The mitigation the plan names (splicing emitter ids into the LOS call's sort key) is
   correctly scoped to Stage B, because that is where emitters genuinely need to appear at ranges a
   nearest-first 128-cap would otherwise drop for the *first* time — Stage A's own test
   (`test_a_burning_unit_at_9km_becomes_visible`) only works at all because the test's fake LOS
   client answers for every unit unconditionally, which is also true of the real Hook whenever the
   candidate pool is under 128.
5. **`FIRE_LIFE_FRACTION_MAX`'s cross-key relationship worth naming**: none found. It is a standalone
   fraction with its own `lo`/`hi` bound equal to the measured bracket; it is not compared against or
   ordered relative to any other tuning constant in this codebase.

---

## Stage B — `AC-B8`/`BL-B73` (gun fire, the event channel)

Implements `AC-B8` (the production firing-event Hook + collector-side `EmitterTracker`) and `BL-B73`
(gun fire makes its firer visible), per `plans/emitter-visibility/plan.md` Stage B. `BL-B74` (the
SAM smoke trail) is not built — only its wire/schema seam (`FiringRawEvent.x`/`z`, `S_EVENT_SHOT`
accepted on the wire but not acted on by `EmitterTracker`).

### Files Changed

**aircraft-layer**

- `dcs-export/petrobrain-firing-events-hook.lua` **(new)** — productionises
  `petrobrain-damage-events-probe-hook.lua`'s event-handler pattern: registers `world.
  addEventHandler` once, filters to five kinds (`S_EVENT_SHOOTING_START`/`_END`, `S_EVENT_SHOT`,
  `S_EVENT_DEAD`, `S_EVENT_CRASH`), resolves `targets_ownship` (vs. `world.getPlayer()`) and
  `S_EVENT_SHOT`'s frozen position Hook-side, drains the queue at 1 Hz. Also maintains
  `PB_ACTIVE_FIRING_UNITS`, a real-time name set updated directly inside the event handler (not
  waiting for the collector) — this is the 128-sightline-cap mitigation's data source, read by
  `petrobrain-line-of-sight-hook.lua` via the shared `"scripting"`-state global, the same mechanism
  `PB_F10_QUEUE` already proves persists across `dostring_in` calls.
- `dcs-export/petrobrain-line-of-sight-hook.lua` — the `MAX_SIGHTLINES_PER_CALL` mitigation named in
  the plan's Risks section: `candidates` is sorted by `(not firing, rangeM)` instead of `rangeM`
  alone, so a currently-firing unit is never truncated by the nearest-first cap regardless of range.
  `PB_ACTIVE_FIRING_UNITS or {}` is a true no-op when the firing-events Hook is not loaded.
- `src/schema/firing.py` **(new)** — `FiringRawEvent`/`FiringEventBatch`, wire parsing. `x`/`z` are
  parsed and carried (the `BL-B74` seam) but nothing in this stage's collector logic reads them for
  anything but passthrough.
- `src/collector/firing_receiver.py` **(new)** — `EmitterTracker` (the latch/watchdog state machine:
  `FIRING_MIN_VISIBLE_S=1.5`, `FIRING_WATCHDOG_S=10.0`, both plain module constants — **this
  subproject has no `tuning.*` loader**, flagged per role instructions as behaviour-affecting and a
  candidate for that mechanism if aircraft-layer grows one) and `FiringEventsReceiver` (the UDP
  receiver, mirroring `LineOfSightReceiver`'s shape). Mission-restart detection: `dcs_model_time_s`
  regressing by more than `_RESTART_TOLERANCE_S=0.5` clears all tracked state.
- `src/api/server.py` — `GET /firing/latest` → `EmitterTracker.snapshot()`. Never JSON `null` — see
  that endpoint's own docstring for why there is no "cache empty" state distinct from "nothing is
  firing right now".
- `src/collector/__main__.py` — wires `EmitterTracker`/`FiringEventsReceiver` the same way as every
  other Hook-to-collector feed; `--firing-host`/`--firing-port` CLI flags, port 7798 (the next
  sequential loopback port after `command_sender.LOOK_DIRECTION_DEFAULT_PORT`'s 7797).
- Tests: `tests/test_firing_schema.py` (13 new), `tests/test_firing_receiver.py` (17 new — latch,
  watchdog, death semantics, mission restart, targets_ownship, plus three real-loopback-socket
  receiver tests), `tests/test_line_of_sight_hook_lua.py` (+2, static guards on the sort-key splice).

**body-layer**

- `src/perception/emitters.py` — `EmitterKind.FIRING`/`.LAUNCH_SMOKE` added (the latter never
  produced this stage); `Emitter.targets_ownship: bool = False` added. New `firing_emitters(
  raw_objects, firing_active)` (same join/collision shape as `burning_emitters`) and
  `resolve_emitters(raw_objects, unit_velocity_samples, firing_active)` — the plan's single merge
  point: `FIRING` wins over `BURNING` for the same unit (implemented as `burning.update(firing)`).
- `src/perception/naked_eye_source.py` — `get_firing_latest()` call (independently-degradable,
  `AircraftLayerError` → `None`, same posture as velocity/LOS), `_resolve_firing_active` (skew check
  against `FIRING_MAX_AGE_S`, a new `tuning.real` constant, default 3.0s matching `LOS_MAX_AGE_S`),
  `naked_eye_source.poll()` now calls `resolve_emitters` instead of `burning_emitters` directly.
  `PROVENANCE_EMITTER_FIRING`/`PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP` (two values, not one — see
  "the targets_ownship fold is a second level deeper" below). `_build_observation` threads a new
  `targets_ownship_by_object_id` dict alongside `emitter_kind_by_object_id` and resolves the
  cluster's provenance one level deeper for `FIRING`: `PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP`
  only when every member agrees `targets_ownship=True`, else the plain `PROVENANCE_EMITTER_FIRING`.
- `src/aircraft_client.py` — `get_firing_latest()`, following `get_line_of_sight_latest`'s exact
  shape except it never returns `None` on a populated cache (mirrors `/firing/latest`'s own
  contract).
- `src/belief/percept.py` — `_EMITTER_KIND_BY_PROVENANCE` gains both `FIRING` provenance values (both
  map to the same `EmitterKind.FIRING.value` — which one it was crosses separately).
  `Percept.targets_ownship: bool = False`, derived via a new closed set,
  `_TARGETS_OWNSHIP_PROVENANCE = frozenset({PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP})` — the same
  "closed mapping, not a passthrough" pattern Stage A's review established, applied one bit deeper.
  `test_percept.py`'s forbidden-set test needed no change.
- `src/belief/contacts.py` — `Contact.is_firing`/`firing_targets_ownship`/`last_emitted_firing`, the
  direct siblings of `is_burning`/`last_emitted_burning` (same overwrite-not-fold posture).
  `ContactStore.tick` gained a `CONTACT_FIRING_SEEN` block mirroring the burning one, no
  `observable_or_grace` check for the same reason.
- `src/belief/events.py` — `CONTACT_FIRING_SEEN`, `firing_event_kind` (one-directional, mirrors
  `burning_event_kind`), `Event.targets_ownship: bool = False`.
- `src/belief/callouts.py` — `CONTACT_FIRING_SEEN` added to `_TEMPLATED_KINDS` only. `callout_
  priority` gains the one kind-specific branch in this function: `CONTACT_FIRING_SEEN` resolves to
  `_FIRING_TARGETS_OWNSHIP_THREAT_BAND` (-2) or `_FIRING_THREAT_BAND` (-1) instead of
  `_DEFAULT_THREAT_BAND` (0) — both strictly more urgent (lower sorts first), independent of
  classification, per the plan's finding 2.
- `src/belief/speech.py` — `_render_lifecycle_text`'s `CONTACT_FIRING_SEEN` branch: `"Taking fire,
  {clock} o'clock."` when `event.targets_ownship`, else `"Something firing, {clock} o'clock, far."` —
  the accepted wording verbatim, including the literal trailing "far". No range clause either form;
  silent when there is no current bearing (same rule `CONTACT_BURNING_SEEN` already follows).
- `config/defaults.toml` — regenerated via `tools/generate_defaults.py --write` for `FIRING_MAX_AGE_S`.
- Fixture update (regression, not a feature change): every `FakeAircraftClient`/
  `FakeConsoleAircraftClient` across `test_naked_eye_source.py`, `test_detection_trace.py`,
  `test_emission_pipeline.py`, `test_player_bubble.py`, `test_logger.py` gained a `get_firing_latest`
  method (the new unconditional call site in `naked_eye_source.poll()` broke all five without it —
  caught by running the full suite, not just the new tests, per role instructions).
- Tests (each `+n` counted via `git diff --cached <file> | grep -cE '^\+def test_'`, not estimated):
  `tests/test_emitters.py` (+9: `firing_emitters`, `resolve_emitters` precedence/merge),
  `tests/test_percept.py` (+4: both `FIRING` provenance values → `FIRING` kind, `targets_ownship`
  mapping), `tests/test_events.py` (+5: `firing_event_kind`'s one-directional transition),
  `tests/test_contacts_firing.py` **(new, 10)**: `record`/`from_percept` assignment, `ContactStore.
  tick` emission including founded-already-firing, `targets_ownship` carried onto the `Event`, the
  one-directional leaving-transition silence, the event cooldown — direct mirror of
  `test_contacts_burning.py`. `tests/test_callouts.py` (+3: priority ordering — firing outranks even
  `priority`-attention ordinary events, targeting-ownship outranks not-targeting, both outrank
  default). `tests/test_speech.py` (+4: both wordings, no-range-clause silence, auto-acknowledge).
  `tests/test_naked_eye_source.py` (+6, end to end): 9 km firing-admitted, same-unit-not-firing
  invisible, firing-behind-terrain invisible, targets_ownship provenance, firing-wins-over-burning
  precedence, stale-firing-snapshot discarded. Total: 9+4+5+10+3+4+6 = 41, matching the suite delta
  (2041 − 2000) exactly.

### Checks

**aircraft-layer**
- `ruff format --check .`: pass (pre-existing unrelated finding in
  `research/2026-10-06-unit-id-join-reduce.py`, the exact file the dispatch said to expect)
- `ruff check .`: pass
- `mypy src`: pass (23 source files)
- `pytest -q`: 291 passed (baseline 262 + 29 new: `test_firing_schema.py` 12 + `test_firing_receiver.
  py` 15 + `test_line_of_sight_hook_lua.py` +2 = 29; each counted via `--collect-only` on its own
  file, not inferred, and the unfiltered `pytest -q` total confirmed against 262+29=291)

**body-layer**
- `ruff format --check .`: pass (pre-existing unrelated finding in
  `research/2026-10-05-security-audit.md`, the exact file the dispatch said to expect)
- `ruff check .`: pass
- `mypy src`: pass (60 source files)
- `pytest -q`: 2041 passed, 4 xfailed (baseline 2000 passed/4 xfailed + 41 new)

### Demonstration (pasted from a live run, not predicted)

```
tests/test_naked_eye_source.py::test_a_unit_firing_beyond_naked_eye_range_becomes_visible PASSED
tests/test_naked_eye_source.py::test_the_same_unit_not_firing_is_not_visible PASSED
tests/test_naked_eye_source.py::test_a_unit_firing_behind_terrain_stays_invisible PASSED
tests/test_naked_eye_source.py::test_a_unit_firing_at_ownship_sets_the_targets_ownship_provenance PASSED
tests/test_naked_eye_source.py::test_firing_wins_over_burning_for_the_same_unit PASSED
tests/test_naked_eye_source.py::test_a_stale_firing_snapshot_is_discarded PASSED
tests/test_contacts_firing.py (10 tests) PASSED
tests/test_speech.py::test_route_event_contact_firing_seen_not_targeting_says_something_firing_far PASSED
tests/test_speech.py::test_route_event_contact_firing_seen_targeting_ownship_says_taking_fire PASSED
```

A burst shorter than one poll (`START`+`END` in the same drained batch) is demonstrated at the layer
that actually owns the latch — `collector.firing_receiver`'s
`test_a_sub_poll_burst_start_and_end_in_the_same_batch_survives_one_poll` — not at body-layer, which
only ever consumes whatever `EmitterTracker.snapshot()` already decided.

### The 128-sightline-cap mitigation — how verified

No DCS process is available to this agent, so this is **not** a live-sortie measurement — the same
limitation `test_line_of_sight_hook_lua.py`'s own module docstring already states for every test in
that file. Verified three ways:

1. **Lua syntax**: the whole file, the body below its header comment (the header's own `[[ID]]` link
   markup trips `luac5.1`'s "nesting of `[[...]]` is deprecated" on *every* Hook script in this
   codebase that uses that markup, including pre-existing production files — confirmed by running
   `luac5.1 -p` against `petrobrain-mission-telemetry-hook.lua` unmodified and seeing the identical
   error, so this is a harmless pre-existing artifact, not a regression), and each embedded
   `dostring_in` snippet extracted and compiled separately (`EVENT_REGISTER_CODE`, `EVENT_POLL_CODE`,
   and the reconstructed `LOS_CODE` chunk with its spliced prefix) — all compile clean.
2. **Self-containment**: `EVENT_REGISTER_CODE`'s helpers (`safeName`, `targetsOwnship`,
   `initiatorPosition`, the `onEvent` handler itself) are defined *inside* the snippet string, not as
   Hook-local functions — confirmed by reading the file, the exact class of defect this project's own
   agent-memory note (`feedback_lua_dostring_in_snippet_must_be_self_contained.md`) warns about.
3. **Static guard, committed**: `test_candidate_sort_reads_the_active_firing_units_global` /
   `test_los_code_prefix_still_sorts_nearest_first_within_each_group` assert the comparator actually
   consults `firingUnits[a.name]`/`firingUnits[b.name]` for both sides before falling back to
   `a.rangeM < b.rangeM` — a guard against the mechanism silently regressing to range-only sorting,
   not a behavioural proof (no Lua test harness exists in this repo for that).

**This is not independently re-verifiable on a live sortie by this agent** — flagged for DoD/the user
per the role's own instructions on claims that cannot be falsified without a live DCS process.

### Notable Discoveries, Stage B

6. **`callout_priority`'s existing "threat_band is a disposable placeholder" design made the
   required fix a one-branch addition, not a redesign.** Because `_DEFAULT_THREAT_BAND` was already
   a flat constant with no real assessment behind it, adding a kind-specific override for exactly one
   `EventKind` (`CONTACT_FIRING_SEEN`) composes cleanly with the plan's own placeholder note — the
   two new bands (`_FIRING_THREAT_BAND=-1`, `_FIRING_TARGETS_OWNSHIP_THREAT_BAND=-2`) are plain module
   constants, not `tuning.real`, because they are an ordinal relationship to `_DEFAULT_THREAT_BAND`
   (must stay strictly below it) rather than an independently tunable lever — same judgement
   `_DEFAULT_THREAT_BAND` itself already received (it too is a bare constant, not tuned). Flagging
   this judgement call explicitly per role instructions rather than silently deciding it.
7. **The `targets_ownship` boundary crossing needed its own closed set, not a widened `EmitterKind`
   mapping.** `_EMITTER_KIND_BY_PROVENANCE` answers "which kind"; `targets_ownship` is a second,
   independent bit that only `FIRING` ever uses. Folding it into the kind mapping (e.g. a fourth
   `EmitterKind` value for "firing at us") would have been a fabricated taxonomy — the *kind* of
   emitter is the same, only the target differs — so a parallel `_TARGETS_OWNSHIP_PROVENANCE`
   frozenset, read independently by `percept_of`, was the design that stayed faithful to "which kind"
   meaning only that.
8. **The event-handler-side name set (`PB_ACTIVE_FIRING_UNITS`) needed no new transport because two
   Hook scripts already share one Lua state.** This was not obvious from the plan text alone (which
   named the mitigation but not its mechanism) — found by rereading `petrobrain-f10-commands-hook.
   lua`'s own header, which already documents that `PB_F10_QUEUE` persists across `dostring_in` calls
   in the `"scripting"` state. The same persistence lets a *second* Hook script's own `dostring_in`
   call read a global the *first* Hook script's handler wrote, with no collector round trip and no
   new wire format.
