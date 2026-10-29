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

### Stage 0 — probe sortie (Windows, user flies)

Built per the plan's own Stage 0 description (`plans/bl-b67-atgm-run/plan.md`, "Implementation
Plan" item 0). **Disposable extensions of two existing, already-committed probes — no new probe
files, no pipeline code.** The plan names both files explicitly as "Stage 0 only, disposable
extensions" in its Affected Modules list.

#### Files Changed

- `aircraft-layer/dcs-export/Export.probe-weapons.lua` — extended, not replaced. Added:
  (1) a per-first-seen-Name key dump (`for k in pairs(obj) do … end`) alongside the existing
  count/new-name log, settling Q2's "does a missile object carry any field a rocket object
  doesn't" without guessing a key name in advance; (2) a per-poll `LoGetPayloadInfo()` read
  (`poll_payload`/`format_payload`), logging each station's `name:count` via `LoGetNameByType`
  and `CurrentStation`, for Q1; (3) a per-*frame* (not per-poll) watched-arg readback for 963
  (`SHSCHO-KNOB-PTR`) and 882 (`OP-AIM-RESET-RAD-PTR`), logged only on change, for Q3/Q5's timing;
  (4) a scripted `SWEEP`/`PARK`/`RESET` state machine (`run_knob_script`) that steps the knob
  through all 9 positions via `GetDevice(7):performClickableAction(3038, n * 0.1)` (device 7 =
  `DEV_I9K113`, the same id the production `Export.lua` uses), parks on the first step whose
  `CurrentStation` correlates with a loaded station, then presses Radiation Reset
  (`performClickableAction(3029, 1)` then `0` one second later) — for Q3/Q5; (5) a count-drop
  auto-advance (`maybe_advance_station`) that steps the knob to the next loaded station after a
  launch, so the pilot never has to touch the knob mid-sortie.
- `aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua` — extended, not replaced.
  Added: (1) an `S_EVENT_SHOT` special case in the existing event handler, firing only when the
  initiator is the player — reads `event.weapon:getTypeName()`/`getDesc().category`/`.guidance`/
  `.displayName`/`isExist()` at event time and appends them to that event's queued line, keeping
  the weapon object in a new global, `PB_PROBE_KEPT_WEAPON`, if it exists at launch (same
  Hook-state-global persistence mechanism `petrobrain-firing-events-hook.lua`'s own
  `PB_ACTIVE_FIRING_UNITS` already relies on, cited in the new header note rather than
  re-derived); (2) an `S_EVENT_HIT` special case, appending a marker when `event.weapon` is that
  same kept object; (3) `WEAPON_EXIST_POLL_CODE`/`pollWeaponExist`, a second `dostring_in` round
  trip at 5 Hz (`WEAPON_EXIST_POLL_INTERVAL_S = 0.2`), independent of the existing 1 Hz
  life/event poll, logging `timer.getTime()` (the mission-scripting state's own sim clock, not
  the Hook state's `DCS.getRealTime()`) the first poll it reads `isExist() == false`, with an
  alive/dead edge flag (`weaponWasAlive`) so "gone" logs exactly once.
- `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` (new) — the sortie card.

Both extensions answer every open question (Q1, Q2, Q3, Q5, Q6) the plan's Stage 0 table lists;
Q4 is retired per the plan's own revision (fire-button reading dropped in favour of
`S_EVENT_SHOT`) and was not reintroduced.

#### Deviations From the Plan, and Why

1. **The research note's own Probe 1/2/3 snippets (`aircraft-layer/research/2026-10-29-bl-b67-
   loadout-and-atgm-object-recon.md`, "Reproducible Test") are minimal hand-flown diffs — they
   assume a human reads the knob position and presses the fire-trigger-equivalent cockpit
   controls manually mid-flight.** The plan's own Stage 0 item asks for more: an auto-scripted
   knob sweep/park/reset and a post-launch auto-advance, so one ~10-minute sortie can exercise
   several stations without the pilot operating the SHSCHO knob or the Radiation Reset button by
   hand. Built as the plan's stage text describes (not the research note's simpler snippets),
   since the plan is the higher-precedence governing input per its own header and the research
   note explicitly offers its snippets as a starting point ("minimal diff"), not a ceiling.
2. **`maybe_advance_station`'s "next loaded station" choice assumes the `Stations` array index
   equals the knob step** — exactly Q3's own open question, not resolved by anything in this probe
   itself. Said plainly in both the code comment and the sortie card rather than silently treated
   as settled: if the sweep/park log shows `CurrentStation` after writing step N is *not* N, this
   logic is choosing the wrong next station, and the log (not the auto-advance's own behaviour) is
   the thing to trust when reading the flight back.
3. **No change to `petrobrain-firing-events-hook.lua`** (the production firing-events Hook this
   plan's later stages will extend) — the probe's `S_EVENT_SHOT`/`S_EVENT_HIT` handling lives
   entirely in the *probe* Hook (`petrobrain-damage-events-probe-hook.lua`), per the plan's own
   Affected Modules list naming only the probe file for Stage 0. The production Hook's own
   own-weapon branch is Stage 5 work, gated on this stage's answers, and was not started here.
4. **A single kept-weapon slot (`PB_PROBE_KEPT_WEAPON`), not a small set.** If a second missile is
   fired before the first's `WEAPON_GONE` is logged, the second overwrites the first and the
   first's own impact is never reported by the 5 Hz poll (though its `S_EVENT_HIT`, if any, would
   still be checked against whichever object is current at that moment, so a true positive there
   could attach to the wrong missile). Acceptable for a probe sortie the card scripts as
   "fire one, wait for impact, fire the next" — flagged here rather than silently fixed, since
   fixing it (a small ring of kept weapons) would be solving a problem Stage 0's own card design
   does not create.
5. **No tunables.** Every new constant (`KNOB_STEP_INTERVAL_S`, `KNOB_SETTLE_S`, `RESET_HOLD_S`,
   `WEAPON_EXIST_POLL_INTERVAL_S`) lives in a throwaway probe script outside `body-layer`, where
   the tuning mechanism does not exist (root `CLAUDE.md`'s "Behaviour-affecting constants" section
   says to declare normally outside `body-layer` and flag the fact) — and more specifically, a
   Stage 0 probe is deleted once its questions are answered, so a tunable here would never ship
   and would want the mechanism for no reason. Flagged, not applied.

#### Checks

- `luac5.1 -p` on both edited files: **pass** (`Export.probe-weapons.lua`,
  `petrobrain-damage-events-probe-hook.lua`).
- `GETGLOBAL` check (`aircraft-layer/CLAUDE.md`) on both outer files: **clean** — every name is
  either a genuine DCS API (`GetDevice`, `LoGetModelTime`, `LoGetNameByType`, `LoGetPayloadInfo`,
  `LoGetWorldObjects`, `log`, `net`, `require`) or Lua stdlib (`io`, `lfs`, `pairs`, `pcall`,
  `string`, `table`, `tostring`, `type`). No own-helper name leaked as an accidental global.
- `GETGLOBAL` check on the **extracted** `dostring_in` string literals (`LIFE_CODE`,
  `EVENT_REGISTER_CODE`, `EVENT_POLL_CODE`, `WEAPON_EXIST_POLL_CODE`, pulled out with a small
  throwaway script and checked individually, since `luac -p` on the outer file never looks inside
  a string): **clean**. `PB_PROBE_EVENT_NAMES`/`PB_PROBE_EVENT_QUEUE`/
  `PB_PROBE_HANDLER_REGISTERED`/`PB_PROBE_KEPT_WEAPON` all appear as `GETGLOBAL` reads, which is
  expected and correct here — they are deliberately shared globals across separate `dostring_in`
  calls into the same persistent `"scripting"` state (the file's own pre-existing pattern), not
  an own-helper-referenced-before-its-`local` bug. No name outside that deliberate set and genuine
  DCS globals (`coalition`, `ipairs`, `pairs`, `pcall`, `string`, `table`, `timer`, `tostring`,
  `type`, `world`) appeared.
- No `ruff`/`mypy`/`pytest` run — this stage touches only `.lua` files, no Python.
- No live DCS run performed by this session (no DCS access from this machine, same constraint the
  research note's own header states) — the sortie itself is the user's to fly, per the card.

#### Tests Added

None — per `aircraft-layer/CLAUDE.md`'s own testing section, "`Export.lua` and the live Export.lua
↔ collector↔API path have no automated test"; this applies equally to a disposable probe
extension of it. Correctness here is validated by the live flight, not by a test suite.

#### Required Fix Addressed (Reviewer, `review.md` "BL-B67 Stage 0")

Reviewer flagged that `maybe_advance_station` turned the SHSCHO knob on the **same poll** the
payload count dropped — likely at or immediately after launch, i.e. while the just-fired missile
could still be in flight (plan's own Risks section already names this as unknown whether it
disturbs 9K113 guidance). Fixed per the review's option 1 (delay, not a card-only caveat):

- Added `ADVANCE_DELAY_S = 25.0` (`Export.probe-weapons.lua`), matching the plan's own
  `ATGM_MAX_FLIGHT_S` figure (max Shturm flight ≈ 6,000 m / 345 m/s ≈ 17 s, 25 s margin) — the
  same constant value, reused rather than re-derived, so a missile is always physically down
  before the knob moves.
- `maybe_advance_station` now schedules the knob write for `now + ADVANCE_DELAY_S` on a count-drop
  (using the same `model_time()` gating pattern the SWEEP/PARK/RESET state machine already uses)
  instead of writing it immediately. The next loaded station is picked from `last_station_counts`
  at the moment the delay elapses, not at drop time, so it reflects the freshest counts.
- **A second count-drop on the same parked station while a delay is already pending re-arms the
  deadline from that second drop's own time**, rather than being lost or causing the knob to
  advance twice. This means if a second missile is fired off the same station before the first
  one's 25 s elapses, the knob waits a further 25 s from the *second* shot — the wait always
  outlasts the most recent launch, and exactly one knob write fires per quiescent period.
- Both the scheduling and the actual advance are logged with model time (`ADVANCE scheduled …
  for t=…` / `ADVANCE re-scheduled … (second drop while waiting)` at drop time; `ADVANCED to
  step=N at t=…` when the write actually happens), so the sortie's own log shows the gap between
  shot and knob movement rather than requiring it to be inferred.
- `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` updated (flying-it steps 3–5) to tell the
  pilot the knob moves ~25 s after each launch, not at launch, and to expect the wait to restart
  if a second shot on the same station lands before the first 25 s is up.
- Re-ran `luac5.1 -p` and the `GETGLOBAL` check on the edited file after the fix: both still pass,
  no new global leaked (`GetDevice`, `LoGetModelTime`, `LoGetNameByType`, `LoGetPayloadInfo`,
  `LoGetWorldObjects`, `io`, `lfs`, `pairs`, `pcall`, `string`, `table`, `tostring`, `type` — same
  set as before the fix).

### Stage 3 — `atgm_run.decide` against synthetic events, plus the in-flight hold, plus the
### guidance-ladder floor settle

Implements **Stage 3 only**: the ATGM run's full state machine (`AtgmPhase`: Preparing → Tracking
→ InFlight → Resetting → [Selecting, resolved within the same call] → Tracking/Empty), range
calls, launch/impact detection, failed-launch/count-drop handling, the backstop (Decision N1), and
the missile-family profiles — all against **synthetic `AtgmInputs`**, per the plan's own Stage 3
scope. Also settles the guidance-ladder floor deferral Stages 1-2 flagged (deviation 1 above):
**made**, not deferred further, with reasons below.

**1b check**: confirmed the plan's own test list for Stage 3 before starting — every test it names
either exists now (written here) or is covered by an existing mechanism (the "re-point resets the
latches" case, see Notable Discoveries). Grepped `tests/` for any existing test touching
`atgm_run`/`AtgmPhase`/`hold_routine` before writing new ones: none existed (Stage 1/2 built only
`AtgmRunState(contact_id)`, no `decide`, no tests beyond the Co-moving Fields rows already in
`test_body.py`). No test suite was silently degenerated — full suite run before and after.

#### Files Changed

**Rewritten** (was Stage 1's `contact_id`-only skeleton)
- `body-layer/src/belief/atgm_run.py` — `AtgmPhase` (`str, Enum`); `AtgmRunState` (now carries
  `phase`/`selected_step`/`selected_step_count_last_seen`/`in_flight_since_sim`/`tracked_family`/
  the three range latches/`unconfirmed_drop_since_sim`, all with defaults so the Stage 1
  construction site, `body.py:3746`, is unaffected); `AtgmInputs` (one poll's synthetic inputs);
  `LaunchEvent`/`FailedLaunch` (declared here, not imported from `perception.own_weapons`, which
  Stage 5 has not built); `Fire`/`SelectStation` (`AtgmAction = Fire | SelectStation`; `Fire.
  trigger` is a plain string, not the not-yet-extended `EffectorTrigger` enum); `family_of`
  (loose substring match against `atgm.toml`'s eventual real names); `decide` and its five
  per-phase helpers (`_preparing_tick`, `_tracking_drop_check`, `_in_flight_tick`,
  `_resetting_tick`, `_maybe_range_call`) plus `_resolve_station_selection` (the one shared
  stay-or-cyclic-next rule `_preparing_tick`/`_tracking_drop_check`/`_resetting_tick` all call) and
  `_render_launch_line`. Seven tunables (below).

**Modified**
- `body-layer/src/belief/speech.py` — `render_range_state`, `render_atgm_launch` (plus
  `_ATGM_FAMILY_DISPLAY`), `render_impact`, `render_no_more_missiles`.
- `body-layer/src/belief/attack_run.py` — `decide` gains `guidance_floor: Optic = UNAIDED_OPTIC`,
  threaded straight into `guidance_request_for`'s own `floor=` keyword in place of the hardcoded
  `UNAIDED_OPTIC`. No change to `guidance_request_for` itself — its own docstring already
  anticipated exactly this ("the floor itself was raised since the last request (e.g. an ATGM
  run's own floor/ceiling parameters)").
- `body-layer/src/belief/crew_console.py` — `drain_attack_run` gains `guidance_floor: Optic =
  UNAIDED_OPTIC`, passed straight through to `decide_attack_run`.
- `body-layer/src/body.py` — the `drain_attack_run` call site gains `guidance_floor=(SIGHT_WIDE_
  OPTIC if runner.atgm_run_state is not None else UNAIDED_OPTIC)` — the same granularity `vertical`
  already uses on the line above it, not narrowed to `home_phase is SIGHTING` (reasoning in
  `attack_run.decide`'s own docstring, see Notable Discoveries).
- `body-layer/src/belief/callouts.py` — `CalloutScheduler.tick` gains `hold_routine: bool = False`:
  both the event-candidate loop and the group-disclosure loop skip (never consume) every candidate
  except `CONTACT_FIRING_SEEN` with `targets_ownship`, while `True`. Default `False` is a true
  no-op for every pre-existing caller.
- `body-layer/docs/STRUCTURE.md` — the `atgm_run.py` entry rewritten for Stage 3's actual content
  (Stage 1's entry described a not-yet-built state machine as "Stage 3"; this replaces that
  forward-reference with what Stage 3 actually built), plus the guidance-floor and `hold_routine`
  additions, plus the discovered re-point gap (below).
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the
  seven new `[belief.atgm_run]` entries. Checked the **rendered** file, not the source comments:
  each entry's first sentence (the only one the generator emits) states what the constant does and,
  where applicable, the consequence of getting it wrong (e.g. `ATGM_UNCONFIRMED_DROP_GRACE_S`'s
  "before treating the drop as a jettison/failed launch rather than a shot still leaving the
  rail").

#### Tunables (`belief.atgm_run`, all new this stage)

| Key | Default | Bounds | Status |
|---|---|---|---|
| `SHTURM_SPEED_MPS` | 345.0 | 200–500 | agreed-guess |
| `SHTURM_MAX_RANGE_M` | 5000.0 | 1000–8000 | agreed-guess |
| `ATAKA_SPEED_MPS` | 400.0 | 200–600 | agreed-guess |
| `ATAKA_MAX_RANGE_M` | 6000.0 | 1000–10000 | agreed-guess |
| `ATGM_MIN_RANGE_M` | 400.0 | 0–2000 | agreed-guess |
| `ATGM_UNCONFIRMED_DROP_GRACE_S` | 3.0 | 0.5–10 | judgement |
| `ATGM_MAX_FLIGHT_S` | 25.0 | 10–60 | derived |

No cross-key coupling introduced — each is read independently (`_FAMILY_SPEED_MPS`/`_FAMILY_MAX_
RANGE_M` are plain dicts keyed by `family_of`'s own two return values, not a coupling between the
tunables themselves). All seven are AST literals (`lo=`/`hi=` are plain numeric literals, not
references), confirmed by `generate_defaults.py --write` running clean.

#### Tests Added

**`tests/test_atgm_run.py`** (new, 36 tests) — table-driven against synthetic `AtgmInputs`, no
DCS. Covers every item in the plan's own Stage 3 test list: range calls (out-of-range-then-in-
range once, in-range-says-neither, a second missile in the run says neither, a fresh `AtgmRunState`
has untouched latches — see Notable Discoveries for why "re-point resets the latches" is tested at
this granularity, not end-to-end); launch/impact (out-of-range/inside-min launch says only the
launch line, a second launch while in flight rebases silently to the newest, launch-and-gone in
the same poll gives both lines in order); failure paths (`FailedLaunch` is a true no-op, a count
drop followed by a launch inside the grace window gives no selection before the launch, a count
drop with no launch emptying the last station says "No more missiles.", a partial count drop
clears the timer and stays); the backstop (silent after `ATGM_MAX_FLIGHT_S`, stays `IN_FLIGHT`
before it elapses); Preparing's first selection (waits on `observ_observed`, picks the lowest
loaded step, "No more missiles." with nothing loaded, `EMPTY` is a steady no-op); Resetting's
post-impact resolution (waits on `impact_sequence_running`, stays on the still-loaded station with
no action, cycles to the next loaded station, "No more missiles." with nothing left); `family_of`
(both hint forms, case-insensitivity, unknown names); the launch line (unknown family/unknown
range both say "Missile." with no invented number, the singular "1 second", the plural for every
other count); the two families' own Wikipedia figures, pinned.

**`tests/test_callouts.py`** (3 new) — `hold_routine`'s own mechanism, in the module it lives in:
`test_hold_routine_defers_a_routine_event_and_speaks_it_once_cleared` (also covers the plan's
"hybrid-only contact event" case — the `_observation` fixture's own source **is** the hybrid
channel's, so no second test is needed: the hold gates by event kind, never by source);
`test_hold_routine_still_lets_taking_fire_through` (the one pass-through kind/flag pair, with a
live routine candidate for the *same* contact proven still held); `test_hold_routine_defers_group_
disclosure_too`.

**`tests/test_attack_run.py`** (2 new) — `test_guidance_floor_raises_the_request_even_for_a_near_
target`, `test_guidance_floor_default_is_byte_identical_to_unaided`.

#### Checks

(body-layer only — no other subproject touched)
- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (0 errors, 78 files)
- `pytest tests -q`: pass — 2776 passed, 4 xfailed (was 2735 passed, 4 xfailed before this stage;
  +41 new: 36 in `test_atgm_run.py`, 3 in `test_callouts.py`, 2 in `test_attack_run.py`). Also
  confirmed with `-p no:randomly` after one default-order run flagged
  `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_
  connection_failure` as failing — passed in isolation and passed with ordering fixed, so this is a
  pre-existing test-order-dependent flake (the file was not touched by this stage), not a
  regression; flagged below rather than silently worked around.
- Also updated as a mechanical consequence of the new `drain_attack_run`/`decide_attack_run`
  keyword: 5 pre-existing `spy_drain_attack_run` fixtures in `tests/test_body.py` (Stage 1's own
  convention — their signatures must match the real call site to be valid monkeypatch targets)
  gained `guidance_floor: object = None`. No assertion in any of those tests changed.

#### Notable Discoveries / Deviations From the Plan

1. **The guidance-ladder floor deferral (Stage 1/2's flagged deviation 1) is settled: made, not
   deferred further.** `attack_run.decide` gains `guidance_floor: Optic = UNAIDED_OPTIC`, threaded
   through at the **same granularity `vertical` already uses** (`runner.atgm_run_state is not
   None`), not narrowed to `home_phase is SIGHTING` as the plan's prose literally reads ("While
   `home_phase is SIGHTING` and [the lock] is set... the guidance ladder's floor is `SIGHT_WIDE_
   OPTIC`"). Reasoned explicitly, not silently widened: `BL-B71`'s own ladder is "continuous and
   bidirectional" regardless of tier/phase (that module's own docstring), so gating the floor more
   narrowly than `vertical` would let the ladder request below sight tier during Preparing, then
   visibly jump to `SIGHT_WIDE_OPTIC` the instant `SIGHTING` is reached — a floor change mid-run for
   no behavioural reason the plan never asks for, not a correctness bug either way since nothing
   downstream reads `requested_optic` before a grant exists. No change was needed in `guidance_
   request_for` itself: its own docstring already names exactly this case ("the floor itself was
   raised since the last request (e.g. an ATGM run's own floor/ceiling parameters) -- never hold a
   request below the current floor").
2. **Discovered gap: `body.py`'s re-point handling does not match the plan's own Co-moving Fields
   table, and this stage does not fix it (out of scope — poll-loop wiring, Stage 7's).** The table's
   "engage missiles, ATGM run active, new target" row says `atgm` should **keep** `phase`/
   in-flight/`selected_step` and only reset the range latches + update `contact_id`. The actual
   Stage 1 code (`body.py`'s engage-apply block, `AtgmRunState(contact_id=atgm_contact_id)`) always
   constructs a **wholesale-fresh** state on every `engage … missiles`, including a re-point while
   an ATGM run is already active — which was harmless when `AtgmRunState` carried only `contact_id`
   (Stage 1/2), but is a real latent bug now that `phase`/`in_flight_since_sim`/`selected_step`
   exist: a re-point mid-flight would silently forget the missile is in flight, the moment Stage 7
   wires `decide` into the poll loop. Neither Stage 1's implementation nor its review caught this
   (the review's own "four rows Stage 1 claims" list does not include this one). This is why the
   plan's own "a re-point mid-flight keeps the missile" Stage 3 test is **not** in
   `test_atgm_run.py`: `decide` itself never touches `contact_id` or re-points anything — that
   operation is entirely the caller's (`body.py`'s) job, and there is no `decide`-level behaviour
   to test for it today. Flagged here, in `docs/STRUCTURE.md`'s `atgm_run.py` entry, and restated
   explicitly so Stage 7 does not re-introduce the current (wrong) behaviour unexamined.
3. **"A re-point resets the latches" (plan's own range-calls test) is tested as "a fresh
   `AtgmRunState` has untouched latches at its dataclass defaults," not end-to-end through a
   re-point.** `decide` never constructs an `AtgmRunState` itself except via `replace()` on the one
   it was given — the reset-on-re-point is entirely a construction-site property (the caller
   building fresh), the same shape `attack_run.AttackRunState`'s own re-point reset already has.
   `test_a_fresh_atgm_run_state_has_untouched_range_latches` pins the one thing `decide` can
   promise; the construction-site behaviour itself is (today, incorrectly per point 2 above) Stage
   1's code, not Stage 3's.
4. **`own_feed_fresh` is accepted on `AtgmInputs` but intentionally unused by `decide`'s own
   backstop logic.** Round 8's own wording for Decision N1 — *"after 25 s leave the flight
   silently... by 25 s the missile is physically gone, whatever the feed says"* — reads as the
   25 s flight-elapsed timer being the backstop's **sole** trigger, covering both named causes
   (Hook not loaded, and a genuinely long flight) through the one mechanism, rather than a second,
   earlier trigger keyed on feed staleness specifically. `own_feed_fresh` stays on the dataclass for
   Stage 5's eventual producer and for parity with the plan's own state-param list, but no test
   exercises it changing `decide`'s behaviour, because none should.
5. **The second-launch-while-in-flight case (plan's own test list) needed a flag `decide` could not
   derive from `state`/`inputs` alone.** Both a just-entered and an already-standing `IN_FLIGHT`
   have `in_flight_since_sim is not None`, so `_in_flight_tick` cannot tell "this poll's launch
   already handled by the block above" apart from "a genuine second launch" without help.
   `decide`'s own local `just_launched` flag, passed through as `already_in_flight=not
   just_launched`, is the fix — documented in both functions' docstrings rather than left as an
   unexplained boolean parameter.
6. **Comment pruned, per implementer.md's "prune the comment you are standing next to":**
   `docs/STRUCTURE.md`'s `atgm_run.py` entry's own "the state machine, range latches and tracked
   missile are Stage 3" sentence (Stage 1/2's forward-reference to this stage) was deleted and
   replaced with what Stage 3 actually built, rather than left stale beside the new content — one
   comment block, the one this stage's own edit sits directly beside.
7. **No cross-key tuning coupling** — confirmed by inspection: the seven new tunables are read
   independently (two plain lookup dicts keyed by `family_of`'s return value, not by each other),
   and none of them is asserted against another constant anywhere in `src/`.
