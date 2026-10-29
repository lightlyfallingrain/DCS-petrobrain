### Implementation Summary

Implements **Stages 1 and 2 only** of `plans/bl-b67-atgm-run/plan.md` (Mi-24P ATGM attack run).
Stage 1 is the run skeleton: weapon slot read, `AtgmRunState` lifecycle tied to `attack_run_state`,
azimuth-only guidance, "Observ on, wait.", the guidance-unit-not-ready refusal, and the sight lock.
Stage 2 is single-unit aim: `aim_unit_direction` end to end from perception through `seen_world_
direction`/`sight_head`. **Stages 3+ are explicitly not started** (Stage 3 has an open user decision,
N1, and depends on Stage 0's probe sortie for several constants).

### Files Changed

**New**
- `body-layer/src/belief/atgm_run.py` — `AtgmRunState` (Stage 1 only: `contact_id`, nothing else —
  the phase/in-flight/selection machinery is Stage 3's own addition, not built here).

**Modified**
- `body-layer/src/belief/crew_console.py` — `attack_run_weapon` field (reset at `handle_command`'s
  dispatch head, same convention as `attack_run_transition`); `_handle_engage` reads
  `slots.get("weapon")`, gates `"missiles"` synchronously on `self.sight_ready` before any target
  resolution (Decision 3 — "Unable, guidance unit not ready.", nothing started), and sets
  `attack_run_weapon` alongside `attack_run_transition`/`weapon_safety_transition`; new method
  `drain_atgm_engage(now_sim, *, observ_is_on)` — one-shot consumer of `attack_run_weapon`, returns
  the resolved contact id (or `None` for a non-`"missiles"` engage), speaks "Observ on, wait." and
  sets `observ_transition = "on"` only when OBSERV is not already on; `drain_attack_run` gained a
  `vertical: bool = True` keyword, threaded to `attack_run.decide`.
- `body-layer/src/belief/attack_run.py` — `decide(..., vertical: bool = True)`: forces
  `elevation_table` to `()` when `False` (reuses the exact mechanism tier 2's own fail-open
  elevation case already relies on — no second code path). `seen_world_direction(contact, *,
  single_unit: bool = False)`: prefers `percept.aim_unit_direction` over `percept.relative_
  direction` when set, falling back to the centroid when it isn't (never loses the look).
  `_seen_world_offset` gained a `relative: RelativeDirection | None = None` override parameter to
  support this without touching `_tier1_alignment`'s own call (unaffected, no override passed).
- `body-layer/src/belief/optic_policy.py` — `sight_lock_contact_id: str | None = None` threaded
  through `decide` → `_decide_without_guidance` → `_decide_sighting`; new `_decide_sighting_locked`
  pins the look to the named contact (no sweep, no natural end), reached only after the existing
  `sight_steady` check — a forced OBSERV-off still wins over the lock, nothing else does. Holds the
  last aim when the locked contact is momentarily absent from `targets`.
- `body-layer/src/belief/sight_head.py` — `single_unit: bool = False` threaded through
  `advance_sight_head` → `select_sight_goal` → `seen_world_direction`.
- `body-layer/src/belief/speech.py` — `render_observ_on_wait()`.
- `body-layer/src/belief/percept.py` — `Percept.aim_unit_direction: RelativeDirection | None`,
  carried through `percept_of` unchanged (same two-file fence as `relative_direction`).
- `body-layer/src/perception/source.py` — `Observation.aim_unit_direction: RelativeDirection |
  None`.
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource.gaze_centre_
  elevation_deg` (sight_cone's missing elevation sibling, assigned alongside it); `_build_
  observation` computes `aim_unit_direction` under the same `live_los_clear is True` condition
  `relative_direction` needs, and only for a sight-tier optic with a gaze centre available: finds
  the cluster member nearest the gaze centre (body-relative azimuth/elevation distance) and
  computes its own yaw-removed offset the same way the centroid's `relative_direction` is built,
  through the same `perturbed_relative_direction` (σ = 0.0, a no-op).
- `body-layer/src/body.py` — `AtgmRunState` import; `ConsolePerceptionRunner.atgm_run_state: 
  AtgmRunState | None` (one new field, added to `reset_for_new_mission`'s enumerated preserved/
  reset-by-`__init__` list); `_apply_active_gaze` assigns `source.gaze_centre_elevation_deg`
  alongside `source.sight_cone`; `decide_optic` call gains `sight_lock_contact_id`; `advance_sight_
  head` call gains `single_unit`; the engage-apply block constructs/ends `atgm_run_state` alongside
  `attack_run_state` (engage missiles → `drain_atgm_engage` → `AtgmRunState(contact_id=...)` or
  `None`; disengage → both `None`); `drain_attack_run`'s call gains `vertical=runner.atgm_run_state
  is None`, and after that call, `runner.attack_run_state is None` also clears `atgm_run_state` (the
  one place drop-target/cancel/lost-contact all funnel through).

### Tests Added

**`tests/test_crew_console.py`** (7 new, 1 updated)
- `test_engage_missiles_refused_when_guidance_unit_not_ready` — the refusal path starts nothing:
  no transition, no weapon, no task registered.
- `test_engage_missiles_dispatches_when_guidance_unit_ready` — the matching positive case.
- `test_engage_guns_never_gated_on_guidance_unit` — only `"missiles"` is gated.
- `test_drain_atgm_engage_returns_none_without_a_missiles_slot`
- `test_drain_atgm_engage_returns_none_when_no_target_task`
- `test_drain_atgm_engage_speaks_observ_on_wait_when_observ_is_off`
- `test_drain_atgm_engage_is_silent_when_observ_already_on`
- `test_engage_accepts_and_ignores_the_weapon_slot` — updated (Decision 15 superseded): now asserts
  `attack_run_weapon == "rockets"` instead of asserting nothing reads it.

**`tests/test_attack_run.py`** (4 new, 1 updated)
- `test_decide_vertical_false_drops_the_elevation_word` — same geometry, with/without `vertical`.
- `test_decide_vertical_false_still_speaks_lined_up`
- `test_seen_world_direction_single_unit_prefers_aim_unit_direction`
- `test_seen_world_direction_single_unit_falls_back_without_aim_unit_direction`
- grep fence pattern extended to `aim_unit_direction` (updated).

**`tests/test_optic_policy.py`** (4 new, class `TestSightLock`)
- `test_the_lock_pins_the_look_to_the_named_contact`
- `test_the_lock_suppresses_the_dwell_break`
- `test_a_forced_observ_off_still_fires_under_the_lock`
- `test_the_lock_holds_the_last_aim_when_the_contact_drops_out`

**`tests/test_sight_head.py`** (2 new)
- `test_single_unit_prefers_aim_unit_direction_over_the_centroid`
- `test_single_unit_false_is_byte_identical_to_the_centroid_default`

**`tests/test_naked_eye_source.py`** (4 new)
- `test_aim_unit_direction_picks_the_member_nearest_the_gaze_centre` — two-member cluster (5 m
  lateral at 100 m, confirmed clustered via `cluster_candidates` directly before writing the test).
- `test_aim_unit_direction_tracks_the_gaze_centre_across_polls` — "sticky ... as the head moves."
- `test_aim_unit_direction_equals_the_centroid_for_a_single_member_cluster`
- `test_aim_unit_direction_none_without_a_sight_tier_optic`
- `test_reset_for_new_mission_field_coverage_is_complete` — updated bucket set (`gaze_centre_
  elevation_deg` added to the per-poll-overwritten bucket).

**`tests/test_body.py`** (4 new, Co-moving Fields rows via the real threaded poll loop)
- `test_engage_missiles_constructs_atgm_run_state_same_poll_as_attack_run_state`
- `test_engage_without_missiles_ends_a_standing_atgm_run`
- `test_disengage_ends_both_the_attack_run_and_the_atgm_run`
- `test_lost_contact_ends_the_atgm_run_alongside_the_attack_run`
- 2 pre-existing spies (`spy_drain_attack_run` in one test, the F4 scenario's `seen_world_direction`
  lambda) updated to accept the new `vertical`/`single_unit` keywords their signatures now carry.

### Checks

(body-layer only — no other subproject touched)
- `ruff format src tests tools`: pass
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (0 errors, 78 files)
- `pytest tests -q`: pass — 2733 passed, 4 xfailed (was 2708 passed, 4 xfailed before this change;
  +21 new tests, 4 pre-existing fixtures updated for the new keywords, 1 test's assertion/docstring
  updated per Decision 15's supersession)

No tunables added (none are due until Stage 3), so `config/defaults.toml` needed no regeneration —
confirmed by `test_tuning_defaults_toml.py` passing unchanged.

### Notable Discoveries / Deviations From the Plan

1. **The sight-lock floor (`SIGHT_WIDE_OPTIC` as the guidance ladder's minimum) is deferred to Stage
   3, not built here.** The plan's "Keeping the look through launch" section names it, but Stage 1's
   own task list only names `sight_lock_contact_id` in `optic_policy.decide` — it does not mention
   changing `attack_run.decide`'s `guidance_request_for(..., floor=UNAIDED_OPTIC, ...)` call. Without
   it, a locked ATGM run's optic ladder could in principle still evaluate from the naked-eye floor
   on a target close enough not to need a narrower optic yet, rather than always sitting at sight
   tier. This has no effect on any Stage 1/2 test (none of them exercise the ladder's floor), but
   Stage 3 needs to either make this change or explicitly decide it is not needed.
2. **`gaze_centre_elevation_deg`** is a new field on `NakedEyePerceptionSource`, not named in the
   plan's "Affected Modules" list (which only names `aim_unit_direction` and the `OWN_WEAPON_OBJECT_
   NAMES` exclusion for that file). It exists because `perception.association.SightCone` carries
   only `azimuth_deg` — no elevation — so the gaze centre's elevation half needed a second field,
   assigned in `body._apply_active_gaze` from the same `OpticState.actual_aim_elevation_deg` read
   `sight_cone` itself is built from. Flagging because it is a real second per-poll field a future
   reader might not expect from the plan text alone.
3. **The `vertical` override is applied by forcing `elevation_table` to `()`, not by adding a second
   branch in `decide`.** This reuses tier 2's own fail-open mechanism (`_alignment_phrase_for` over
   an empty table already returns no phrase) rather than adding new control flow — flagged per the
   plan's own "flag it rather than inheriting it silently" instruction, since it is still a
   behavioural departure from shipped BL-14, just implemented as data rather than a branch.
4. **Amend-on-merge note carried forward, not applied by this stage**: the plan's "Second-order
   effect" section asks that `plans/attack-run/plan.md` Decision 15 ("the weapon slot — nothing
   reads it yet") be marked `REVISED` once Stage 1 merges. That edit was not made here (the
   Implementer does not own that plan file); it is called out so the merge step / Architect can do
   it per the plan's own instruction.
5. **No cross-key tuning coupling introduced** — this stage adds no tunables at all (Stage 3 adds
   the first ones: `SHTURM_SPEED_MPS` etc.).
6. **Grep-fence enumeration check (implementer.md step 1b)**: confirmed before starting that
   `test_attack_run.py`'s fence test and `test_sight_head.py`'s F2/F3 fence tests exist as named by
   the plan, and found one fixture the plan's own test list did not name — the F4 differential
   scenario's `seen_world_direction` lambda monkeypatch in `test_body.py`, which needed its
   signature widened for `single_unit`. No tests were silently degenerated by this change (verified
   by running the full suite before and after each edit, not just at the end).

### Stage 4 — Aircraft-layer payload feed

Implements **Stage 4 only**: the ownship loadout feed end to end — `Export.lua`'s
`push_payload_state` (`LoGetPayloadInfo()` + `LoGetNameByType()`, read at the 5 Hz export tick,
sent only on change), the collector schema/cache/routing, `GET /payload/latest`, and the
body-layer client method. Stages 1–3 (already merged, see above) and Stages 5–8 are untouched;
this stage does not touch `belief/atgm_run.py` or any belief-layer station/family logic — per the
plan, Stage 4 is safe before Stage 0's probe sortie because Q1 (the Mi-24P confirmation) can only
change the schema's field names, not whether this stage is buildable at all.

**1b check**: confirmed before starting that the plan's own test list for Stage 4 ("parser:
3-/4-segment..." etc.) actually belongs to Stage 5 (the own-weapon channel), not Stage 4 — Stage 4
has no test list of its own in the plan beyond "Run the Lua `GETGLOBAL` bytecode check." Grepped
`aircraft-layer/tests/` for any existing payload/`LoGetPayloadInfo` test before writing new ones:
none existed. No test suite was silently degenerated (full suites run before/after, both green).

#### Files Changed

**New**
- `aircraft-layer/src/schema/payload.py` — `PayloadSample`/`PayloadStation`/`PayloadParseError`.
  `name` is passed through unvalidated (never checked against a known store-name set) and
  `stations` may be an empty tuple — both deliberate, since the research note flags Mi-24P
  applicability as inferred, not probed, and an empty/placeholder reading must parse cleanly
  rather than error.
- `aircraft-layer/tests/test_payload_api.py` — schema/cache/routing/endpoint tests, mirroring
  `test_sight_servo_api.py`'s structure exactly (same class names, same "not an error" posture).
- `aircraft-layer/tests/test_payload_lua.py` — `push_payload_state` run against a real Lua
  interpreter (extraction technique from `test_sight_servo_lua.py`), covering the encode shape, the
  `LoGetNameByType` failure/non-string fallback to `"?"`, the change-gate signature (no resend on
  an unchanged reading; resend on a count/current-station change), and a failed/non-table
  `LoGetPayloadInfo()` call sending nothing.

**Modified**
- `aircraft-layer/dcs-export/Export.lua` — `push_payload_state(t)`, defined below `safe_call`/
  `json_escape_string` per the no-hoisting rule, called from `LuaExportAfterNextFrame` at the same
  point as `push_watched_args_state` (after the telemetry send succeeds). A new module-level
  `payload_last_signature` local holds the change-gate signature (current station + each station's
  resolved name/count; `container` is carried on the line but left out of the signature — see the
  function's own comment for why), reset to `nil` in `LuaExportStop` (the "a stale X must never
  survive" convention every other per-mission feed here follows). `EXPORT_SCRIPT_VERSION` bumped to
  `"2026-10-29"` (additive: an old deployed script just never sends a `"stations"` line).
  **`LoGetPayloadInfo`'s own `Cannon` field is deliberately not sent** — nothing in the plan reads
  it yet (flagged in case a later stage wants it).
- `aircraft-layer/src/schema/__init__.py` — re-exports `PayloadParseError`/`PayloadSample`/
  `PayloadStation`.
- `aircraft-layer/src/collector/cache.py` — `PayloadCache`, same "latest of one" shape as
  `PttCache`.
- `aircraft-layer/src/collector/server.py` — `_handle_line` routes a `"stations"`-keyed line to
  `PayloadCache` ahead of the telemetry fallthrough, same pattern as every other named-key branch;
  `CollectorServer.__init__` gains an optional `payload_cache` param; `EXPECTED_EXPORT_VERSION`
  bumped to `"2026-10-29"` to match `Export.lua`.
- `aircraft-layer/src/collector/__main__.py` — constructs `PayloadCache()`, wires it into both
  `CollectorServer` and `TelemetryAPIServer`.
- `aircraft-layer/src/api/server.py` — `GET /payload/latest` (`_PAYLOAD_LATEST_PATH`,
  `_handle_payload_latest`), wired through `_make_handler`'s dispatch and `TelemetryAPIServer`'s
  constructor/`open()`. Read-only, no write side.
- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.get_payload_latest()`, same
  "ordinary `get_*` read, `None` on an empty cache, raises `AircraftLayerError` on a non-dict/
  transport failure" shape as `get_watched_args_latest`/`get_sight_servo_latest`.

#### Tests Added

**`aircraft-layer/tests/test_payload_api.py`**
- `TestPayloadSample` — parses a line; an empty `stations` array parses cleanly; missing `t`/
  `current_station`; non-array `stations`; a station missing `count`/non-string `name`/non-boolean
  `container`; `to_api_dict` round-trip.
- `TestPayloadCache` — empty until pushed; keeps only the latest.
- `TestCollectorRouting` — a `"stations"` line reaches the cache and is never misparsed as
  telemetry; a collector with no `PayloadCache` drops the line without raising; a malformed line is
  dropped, not raised.
- `TestPayloadLatestEndpoint` — `null` before the first line; serves the latest sample.

**`aircraft-layer/tests/test_payload_lua.py`** (`TestPushPayloadState`)
- Encodes `current_station`/`stations` correctly; a failing/non-string `LoGetNameByType` result
  falls back to `"?"`; an empty `Stations` table encodes an empty array; a failed/non-table
  `LoGetPayloadInfo()` call sends nothing; a missing `CurrentStation` sends nothing; an unchanged
  signature sends only once; a count change or a current-station change (same stations otherwise)
  each resend.

**`body-layer/tests/test_aircraft_client.py`**
- `test_get_payload_latest_returns_parsed_dict`
- `test_get_payload_latest_raises_on_unreachable_host`

#### Checks

(aircraft-layer and body-layer — no other subproject touched)
- `ruff format src tests`: pass (both subprojects)
- `ruff check src tests`: pass (both subprojects)
- `cd aircraft-layer && .venv/bin/mypy src`: pass (0 errors, 26 files)
- `cd body-layer && .venv/bin/mypy src`: pass (0 errors, 78 files)
- `pytest aircraft-layer/tests -q`: pass — 645 passed (was 618 before this stage; +27 new)
- `pytest body-layer/tests -q`: pass — 2735 passed, 4 xfailed (was 2733 passed, 4 xfailed; +2 new)
- Lua: `luac5.1 -p aircraft-layer/dcs-export/Export.lua`: pass. `GETGLOBAL` bytecode check
  (aircraft-layer `CLAUDE.md`): clean — every global the chunk reads is either this project's own
  `DUMPED_*`/`io`/`lfs` pattern (pre-existing), a genuine DCS API (including the two new ones,
  `LoGetPayloadInfo`/`LoGetNameByType`), or Lua stdlib. No own-helper (`push_payload_state`,
  `json_escape_string`, etc.) appears, confirming no hoisting bug was introduced.

No tunables added — Stage 4 introduces no behaviour-affecting constants (the change-gate signature
comparison has no threshold/epsilon, unlike `watched_args_changed`'s numeric one, since station
counts/names/current-station are compared for exact equality, not within a tolerance).

#### Notable Discoveries / Deviations From the Plan

1. **`_extract_lua_function`'s depth-counting (the technique `test_sight_servo_lua.py`
   introduced) does not count `for`/`while` as block openers**, only `function`/`if` — it had never
   needed to, since none of that file's own extracted functions contain a `for` loop.
   `push_payload_state` does (iterating `payload.Stations`), so the unmodified helper truncated the
   extraction at the loop's own closing `end` and produced a syntactically broken script. Fixed in
   `test_payload_lua.py`'s own copy of the helper (duplicated, not imported, per this project's
   convention) by widening the token set to `function|if|for|while|end`; flagged here because
   `test_sight_servo_lua.py`'s copy is unfixed and the same gap would recur for any future function
   there that gains a loop.
2. **`LoGetNameByType` is modelled here as returning a single string value (or erroring/returning
   non-string), not an `(ok, name)` pair** — the research note's Probe 2 snippet
   (`local okn, nm = pcall(LoGetNameByType, ...)`) wraps the call in `pcall` itself, so `nm` is
   `LoGetNameByType`'s own first and only return value, never a second value from the function
   itself. Worth flagging because an early draft of the Lua test wrongly mocked a two-value return
   and silently exercised the wrong branch (`nm` bound to a boolean, read back as `"?"` by
   coincidence since it is not a string) until the assertion on the resolved name caught it.
3. **`Cannon` (shells remaining) is read by `LoGetPayloadInfo()` but not sent on the wire.** Flagged
   in the plan's own Affected Modules list only implicitly (the schema list names `stations`/
   `current_station`/`t` and nothing else); noted here explicitly since a future stage reaching for
   cannon-shell count will need to add it, not assume it is already there.
4. **The change-gate signature intentionally omits `container`.** A station's `container` flag (DCS
   terminology for a weapon mount that is itself a container, e.g. a rocket pod vs. a bare rail)
   changing independently of that station's name or count was judged not to be a loadout change
   this feed exists to report — flagged per the plan's own "flag it rather than inheriting it
   silently" instruction, since it is a judgment call the plan itself did not make explicitly for
   this new feed. If a future stage needs to react to a `container`-only change, the signature
   needs widening.
5. **No cross-key tuning coupling** — this stage adds no tunables (none were due; Stage 4's own
   task list in the plan names no tunables).
