### Implementation Summary

BL-16, `plans/flight-desired-state/plan.md`, Stages 1 and 2 — one desired flight state and one
mode authority (`fd_mode`), derived in a new `Export.lua` module (`flight_desired.lua`). Stage 1
ships it as a read-only shadow: the authority derivation, edge seeding/clearing/carrying, and a
receipt-time mirror of today's two goal handlers, pushed on a new `fd_*` status line and read by
nothing. Stage 2 makes the mode authority live: Lua self-arms on a park edge whether coming from
`off` or from an already-flying mode 1 session, the lease moves to its own unnumbered
`flight_lease` op (replacing `flight_control`'s old `"arm"` command), a voice take re-checks
IAS/AGL itself, and body-layer's `CrewConsole.flight_mode()`/`current_crew_state()` read the new
`FlightAuthorityState` mirror instead of `ParkedFlightState.parked_active`/`FlightControlState.
phase`. Mode-change speech (`decide_flight_speech`) replaces `decide_flight_control`'s own
park/unpark/self-release branches.

The coordinator amended the plan mid-task (on `feature/bl16-desired-state`, not merged here,
applied directly): the Stage 1 status line carries both measured headings (`fd_hdg_true_deg`,
`fd_hdg_mag_deg`) instead of one "HSI reference" field, plus a new `fd_hdg_ref` tag naming which
reference last wrote the shadow desired heading (`"true"` from mode 1's own writers, `"overlay"`
from mode 2's). No heading conversion happens in Stage 1 — both numbers are reported as-is, and
the combined test card (`docs/acceptance/2026-11-20-bl16-desired-state-s12-card.md`) is the one
place the two former cards' steps live now.

### Files Changed

**aircraft-layer**
- `dcs-export/Petrobrain/flight_desired.lua` (new) — the mode authority (`fd_mode`/`fd_mode_n`/
  `fd_mode_cause`, derived every tick from `flight_control.mode_info()` and `ai_pilot_wheel.
  is_parked()`), the shadow `desired` table, edge seed/clear/carry handling, the receipt-time
  mirrors (`mirror_m1_goal`/`mirror_m2_goal`) called from the other two modules, and the 5 Hz
  `fd_*` push including both measured headings and `fd_hdg_ref`.
- `dcs-export/Export.lua` — loads `flight_desired` before `ai_pilot_wheel`/`flight_control`; calls
  `flight_desired.tick` after `run_flight_control` (`LuaExportBeforeNextFrame`) and
  `push_flight_desired_state` at 5 Hz; added to `on_stop`; version bumped to `"2026-11-20b"`.
- `dcs-export/Petrobrain/flight_control.lua` — `apply_goal_fields` now also calls `flight_desired.
  mirror_m1_goal`. New `M.mode_info()` read-only getter for `flight_desired` to derive the
  authority from. Stage 2: `cmd == "arm"` removed from `handle_flight_control_command`; a new
  `handle_flight_lease_command` (unnumbered, applies `limits` through a factored-out `apply_
  limits_bounds_checked` helper shared with the ordinary command handler, then refreshes `fc_arm_
  last_t`); `run_flight_control` gains a second self-arm branch (`is_parked and fc_mode == "off"`)
  alongside the existing active/taking one; a voice `"take"` now calls `check_unpark_
  preconditions` before transitioning to `"taking"`, refusing (cause `too_slow`/`on_ground`)
  without touching `fc_mode` on failure; `fc_last_arm_seq` (dead once the lease carries no seq)
  removed; the unpark-take's own `fc_take_seq` is set to `nil` instead of the removed field.
- `dcs-export/Petrobrain/ai_pilot_wheel.lua` — `handle_ai_pilot_goal_command` now also calls
  `flight_desired.mirror_m2_goal`.
- `dcs-export/Petrobrain/commands.lua` — new `flight_lease` op dispatch; `reset` now also calls
  `flight_desired.reset`.
- `src/schema/flight_desired.py` (new) — `FlightDesiredState`, mirroring `FlightControlState`'s
  own shape.
- `src/collector/cache.py` — `FlightDesiredCache`.
- `src/collector/server.py` — `fd_mode`-keyed line routing ahead of the telemetry fallthrough;
  `EXPECTED_EXPORT_VERSION` bumped to match.
- `src/collector/__main__.py` — wires `FlightDesiredCache` into both the collector and the API.
- `src/collector/command_sender.py` — `send_flight_lease`; `send_flight_control`'s own `cmd`
  `Literal` drops `"arm"`.
- `src/api/server.py` — `GET /flight_desired/latest`; `POST /command/flight_lease`;
  `_FLIGHT_CONTROL_VALID_CMDS` drops `"arm"`.
- `tests/test_flight_desired_lua.py` (new), `tests/test_flight_desired_api.py` (new),
  `tests/test_flight_control_lua.py` (updated: every `cmd:"arm"` driver line replaced with
  `handle_flight_lease_command`, with an explicit self-arm tick inserted where the test had none;
  new `TestStage2SelfArmAndLease`/`TestStage2VoiceTakePrecondition` classes),
  `tests/test_flight_control_api.py` (new `TestSendFlightLease`/`TestFlightLeaseCommandEndpoint`,
  an `"arm"`-is-now-invalid test, `_RecordingCommandSender.send_flight_lease`).
- `CLAUDE.md` — the write-path bullets for `flight_lease`/`flight_desired`.

**body-layer**
- `src/belief/flight_authority.py` (new) — `FlightAuthorityState` (single construction site,
  `advance_flight_authority`), `decide_flight_speech` (urgent "You have controls!" only on an
  `fd_mode_n` edge into `"off"` whose cause is not `release`/`stop`/`reset`).
- `src/belief/flight_control.py` — `decide_flight_control`'s park/unpark/self-release branches
  deleted (superseded by `decide_flight_speech`); only the voice-take ack-timeout/confirmation
  branch remains. **Deviation from the plan's literal Stage 2 deletion list**: `FlightControlPhase`/
  `phase`/`unpark_take`/`took_at_sim` are *not* removed from `FlightControlState` this stage — the
  remaining branch still depends on them for the voice-take handshake, which only Stage 3's own
  channel replaces. `phase` now goes stale (stops moving to `"OVERLAY"`) while flying mode 2, which
  is harmless: nothing left reads it for that purpose.
- `src/belief/crew_console.py` — `flight_mode()`/`current_crew_state()`'s `has_controls`/`held_*`
  read `flight_authority_state` instead of `parked_flight_state`/`flight_control_state.phase`.
  New `flight_authority_state` field, `speak_flight_authority_decision` method. `drain_flight_
  control` gained `unparked_from_overlay` (default `False`) — `body.py`'s own report of the
  `fd_mode` m2→m1 edge, replacing the deleted `phase`-transition detection the Decision-32
  break-seed logic used to key off.
- `src/body.py` — refreshes `flight_authority_state` every poll (unconditional, no reset-epoch
  gate in Stages 1-2 per the plan's own scope note), calls `decide_flight_speech` and speaks its
  result, computes `unparked_from_overlay` for `drain_flight_control`. `_apply_flight_control`
  gains an `epoch` parameter and sends the lease unconditionally every call (no longer gated on
  `phase == "OVERLAY" and unpark_take`); its stale-transition guard now reads `crew_console.
  flight_mode() == "overlay"` instead of `state.phase == "OVERLAY"`.
- `src/aircraft_client.py` — `get_flight_desired_latest`, `write_flight_lease`; `write_flight_
  control`'s `cmd` `Literal` drops `"arm"`.
- `tests/test_flight_authority.py` (new).
- `tests/test_flight_control.py` — the five `TestDecideFlightControl` tests pinning the deleted
  branches removed, replaced by two tests pinning the two remaining no-op cases;
  `TestDrainFlightControlSeedsTheBreakTarget` reworked to drive `unparked_from_overlay` directly.
- `tests/test_body_flight_control.py` — `_apply_flight_control` call sites updated for the new
  `epoch` parameter; `_FakeAircraftClient` gained `write_flight_lease`; the two "arm" tests
  replaced by one lease test; the row-11 test now sets `flight_authority_state` to reach the
  `overlay` guard.
- `tests/test_rules_flight_actions.py`, `tests/test_crew_console_rules.py`, `tests/test_body.py` —
  test-fixture helpers (`_console`, `_dispatching_console`, `_flight_console_with_rule`) and
  several direct `flight_control_state`/`parked_flight_state` mutations updated to also set
  `flight_authority_state`, since `has_controls`/`flight_mode()` no longer read the old mirrors.
  This is plan-mandated rework (Stage 2's own `flight_mode`/`has_controls` change), not an
  unrelated test edit.
- `tools/check_rules.py` — the dry-run harness's three scenarios now also set `flight_authority_
  state` (`_authority_for`), so a dry run still reaches the real `_by_mode` action bodies.

### Tests Added

- `aircraft-layer/tests/test_flight_desired_lua.py` — mode derivation (off/taking/m1/m2, m2 wins
  over `fc_mode` when parked, `fd_has_m2=false` when `ai_pilot_wheel` never loaded), edge seeding
  (off→m1 reseeds from measured, off→m2 reseeds from the overlay once readable with HOLD before
  then, m1→off clears, every `fd_mode_cause` value, m2→m1 carries), receipt-time mirrors, reset/
  stop.
- `aircraft-layer/tests/test_flight_desired_api.py` — schema parse/round-trip, cache, collector
  routing ahead of telemetry, `GET /flight_desired/latest`.
- `aircraft-layer/tests/test_flight_control_lua.py` `TestStage2SelfArmAndLease` — no lease means
  no self-arm from off, a stale lease does not self-arm, an out-of-bounds lease message is
  rejected whole (no self-arm), `"arm"` on the old channel is now a no-op.
  `TestStage2VoiceTakePrecondition` — a voice take refuses too-slow/on-ground without changing
  `fc_mode`, and still takes when clear to fly.
- `aircraft-layer/tests/test_flight_control_api.py` `TestSendFlightLease`,
  `TestFlightLeaseCommandEndpoint`, `test_arm_is_no_longer_a_valid_cmd`.
- `body-layer/tests/test_flight_authority.py` — `advance_flight_authority` parse/null-sample, and
  every `decide_flight_speech` case (no edge, each silent cause, each urgent cause).

### Checks

**aircraft-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src`: pass (no issues, 29 source files)
- `pytest tests -q`: pass (1099 passed)
- `luac5.1 -p` on every touched Lua file: pass
- GETGLOBAL sweep on every touched Lua file: clean (only stdlib/DCS APIs and the three
  cross-module globals `flight_control`/`ai_pilot_wheel`/`flight_desired`)

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src`: pass (no issues, 93 source files)
- `pytest tests -q` (full suite, `not slow` plus the `slow`-marked flight scenario tests run
  separately): pass (3711 passed + 5 slow flight scenarios, 27 deselected, 4 xfailed)

### Notable Discoveries

- **The plan's own test-impact list undercounted the blast radius of Stage 2's `flight_mode()`/
  `has_controls` change.** Every test that builds a `CrewConsole` and sets `parked_active=True` (or
  mutates `flight_control_state.phase` directly) to reach the `"overlay"`/`"axes"` dispatch path
  broke — 75 test failures on the first full-suite run, across `test_rules_flight_actions.py`,
  `test_crew_console_rules.py`, `test_body.py`, `test_check_rules_tool.py`, `test_flight_control.py`
  and `test_body_flight_control.py`. None were testing flight-authority logic itself; all were
  testing unrelated action bodies/gates that happen to need `has_controls=True` to reach their own
  code. Fixed by threading the same `parked_active`/`held_*` (or `phase="ACTIVE"`) mapping onto
  `flight_authority_state` in each fixture helper, not by touching the tests' own assertions.
- **`decide_flight_control`'s own `OVERLAY`→`ACTIVE` transition was the only place that fired the
  Decision-32 break-seed logic.** Deleting it (per the plan) silently regresses that behaviour
  unless something else reports the same edge — `drain_flight_control` now takes an explicit
  `unparked_from_overlay` parameter from `body.py`'s own `flight_authority_state` comparison
  instead. This is exactly the "tonight's behaviour keeps working at every stage" discipline the
  plan states; worth flagging since the plan's own Stage 2 bullet list does not mention it.
  `[[BL-16]]`'s own backlog may want a line noting the mechanism moved.
  `FlightControlPhase`/`phase`/`unpark_take`/`took_at_sim` are therefore *not* deleted in this
  stage — see the Files Changed entry for `flight_control.py` above; flagging in case the plan's
  Stage 3 text assumed they already were.
- **The Lua-side self-arm change moved *when* a frame's work happens, not just *what* fc_mode
  transitions exist.** The old `cmd == "arm"` handler set `fc_mode = "armed"` at message receipt,
  before that poll's `run_flight_control` ever ran, so the stowed-capture tracking inside that same
  call already saw `fc_mode == "armed"`. The new self-arm-from-`"off"` branch transitions and
  `return`s inside `run_flight_control` itself, so the frame that self-arms is "spent" and tracking
  only starts the *next* frame. One existing test (`test_captures_the_last_fully_stowed_frame_not_
  the_faded_edge`) needed an extra frame inserted between arming and the simulated fade to still
  pin the right captured value — a timing detail the plan's prose does not mention and a future
  reader of that test file should know about if more self-arm-adjacent tests are added.
- **`handle_flight_lease_command`'s all-or-nothing `limits` rejection was a judgment call**, not
  dictated by the plan: an out-of-bounds field now rejects the *whole* lease (including the
  freshness refresh), rather than refreshing `fc_arm_last_t` regardless. Chosen for consistency
  with `handle_flight_control_command`'s own `AC-B14` posture and pinned by a dedicated test
  (`test_lease_carries_limits_same_as_flight_control_did`).
- **No epoch gating was added to the lease or to `flight_desired`'s own reset**, per the
  coordinator's "nothing else in Stages 1-2 changes" note — `_resolve_command_reset` is untouched,
  and the lease's `epoch` field is carried on the wire but not yet checked against anything. This
  is Stage 3/5 territory per the plan's own section 5.
