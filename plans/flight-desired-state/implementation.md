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

### Review-fix round, 2026-11-20 (`plans/flight-desired-state/review-s12.md`)

Branch `impl/s12-review-fixes`, cut from `feature/bl16-desired-state` tip `92a06513`. Both
required fixes addressed; both optional refinements left alone (neither was touched by this diff,
and neither is trivial enough to fold in opportunistically — the `held_*` fallback one in
particular touches merge semantics the review itself says is narrow but not zero-risk).

**Required Fix 1 (stale `phase` after a forced self-release).** `body-layer/src/belief/
flight_control.py`'s `decide_flight_control` gets back the pre-Stage-2 state-sync branch — `phase
== "ACTIVE" and lua_mode == "off" and lua_release_reason in ("envelope", "nan", "dead")` →
`phase = "PILOT"`, `pending_take_says`/`took_at_sim` cleared — **without** the speech that branch
used to carry, since `decide_flight_speech` (`belief/flight_authority.py`) already owns the urgent
"You have controls!" line for this exact edge (keyed off `fd_mode`/`fd_mode_cause`, not `phase`).
Restored in the smallest place that keeps `phase` consistent until Stage 3 deletes the field
outright, per the review's own suggested fix. Pinned by
`test_lua_self_release_reconciles_phase_back_to_pilot` (parametrized over `envelope`/`nan`/`dead`)
in `tests/test_flight_control.py`.

**Required Fix 2 (self-arm from `off` was level-triggered, not edge-triggered).**
`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`'s `run_flight_control` gains a park-edge
tracker: `fc_was_parked` (the raw `is_parked()` value from the previous frame, `nil`/unknown
folded into "not parked," never reset by `on_stop`/`reset` — a reset does not change whether the
player is physically parked) and `fc_off_armable_since_edge` (derived: set `true` only on a
genuine rising edge — `not fc_was_parked and is_parked` — while `fc_mode == "off"`, so a lease
that becomes fresh a few frames *after* the edge still gets to arm, which is the ordinary "every
park gives him the overlay" case; cleared on unpark and by `on_stop`/`reset`). The off→armed
self-arm branch now additionally requires `fc_off_armable_since_edge`, closing exactly the
sequence the review drove through `luajit`: self-arm from a park → `reset(epoch)` while still
parked → a fresh lease arrives with no unpark/re-park in between → `fc_mode` now correctly stays
`off` (previously it re-armed the instant the lease caught up, "well before `'too soon'` in
practice," per the review). Pinned by
`test_reset_while_parked_does_not_rearm_until_the_next_park_edge` in
`tests/test_flight_control_lua.py` — the review's own four-step reproduction, verified both ways:
fails against the pre-fix module (`fc_mode == "armed"` at step 2, confirmed by stashing the Lua
diff and re-running), passes with it.

**Files changed, this round:**
- `body-layer/src/belief/flight_control.py` — Required Fix 1 branch restored in
  `decide_flight_control`.
- `body-layer/tests/test_flight_control.py` — `test_lua_self_release_reconciles_phase_back_to_pilot`.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — `fc_was_parked`/`fc_off_armable_
  since_edge` locals, the edge-tracking block at the top of `run_flight_control`, the off→armed
  branch's new `fc_off_armable_since_edge` condition, and `on_stop` clearing the armable flag
  (never `fc_was_parked` itself).
- `aircraft-layer/tests/test_flight_control_lua.py` —
  `test_reset_while_parked_does_not_rearm_until_the_next_park_edge`.

**Checks, this round:**
- aircraft-layer: `ruff format --check`/`ruff check`/`mypy src` pass; `luac5.1 -p` on the touched
  Lua file passes; GETGLOBAL sweep on it is identical before/after the diff (no new global
  reference introduced); full suite `pytest tests -q`: 1100 passed (1099 + the new Lua test).
- body-layer: `ruff format --check`/`ruff check`/`mypy src` pass; full suite (`not slow`):
  3714 passed, 27 deselected, 4 xfailed (3711 + the 3 new parametrized cases); the 27 `slow`-marked
  flight scenario tests were also run (`pytest tests -q -m slow`): 27 passed.

### Stage 3, 2026-11-20 — one channel; mode 1 flies the desired state

Branch `impl/desired-state-s3`, cut from tip `65cbd76a` (the Stage 1-2 re-review's own `APPROVED`
commit). Builds the plan's section 5 numbered `flight` channel, mode 1's "apply desired by stamp",
the heading-reference conversion, and the unpark-carries-`desired` fix (Decision 32/Q4) — the
actual defect this whole plan exists to close (a mid-ramp unpark flying the stale overlay value).

**Scope delivered, matching the plan:**
- **Lua (`flight_desired.lua`)**: `handle_flight_command` — the one op, `{"epoch","seq","until",
  "kind",...}`. Epoch mismatch → ack `epoch`; `seq <= fd_last_seq` → silently dropped (no ack, same
  dedup posture every other channel here already has); a request that passes both is bounds-
  re-checked (`AC-B14`) → `bounds`; checked against `until` → `stale`; `kind=="set"` writes `desired`
  (refused `not_flying` only when `fd_mode=="off"`) with every part it carries stamped with the
  request's own `seq`; `kind=="take"/"release"` call into `flight_control.request_take`/
  `request_release`; the six mode-2-only kinds are refused `wrong_mode` unconditionally (Stage 4's
  own work). `fd_acks` (last 8, `"N:a:m1"`/`"N:r:<reason>"`), `fd_epoch`, `fd_last_seq` ride the
  status line. `reset(epoch)` sets the acceptance epoch/floor; `on_stop` does not (same "seq never
  goes backwards outside an explicit reset" posture `flight_control.lua`'s own `fc_last_cmd_seq`
  used to have). **Stamps are the request's own wire `seq`** for a numbered write, or the current
  `fd_last_seq` floor for a write this module makes on its own initiative (a reseed, a settle
  writeback) — `write_internal`, the one function both `flight_control.lua`'s settle code and `ai_
  pilot_wheel.lua`'s align-read call into. `Stages 1-2's `mirror_m1_goal`/`mirror_m2_goal` receipt-
  time mirrors are deleted outright, replaced by this one path.
  **`HEADING_REF = "true"` is now measured, not a placeholder** — the user's own test flight
  (`explore-notes.md`, "Heading reference measured: true", 2026-11-20) found the AI overlay's held
  course and the HSI both read true heading (DCS status bar "356 deg magnetic, 001 deg true";
  overlay and HSI both ~001). The same flight found `fd_hdg_mag_deg` mislabelled —
  `LoGetMagneticYaw` returns radians, not degrees — fixed in Stage 3b (`flight_desired.lua`'s new
  `wrap360_deg`/`magnetic_yaw_deg`, converting via `math.deg` and wrapping into `[0, 360)` before
  the wire; `belief.flight_authority._as_optional_degrees_0_360` wraps again defensively at
  body-layer's own mirror boundary).
- **Lua (`flight_control.lua`)**: `fc_goal_*`, `fc_last_cmd_seq`, `apply_goal_fields`, and `handle_
  flight_control_command` are deleted outright. `request_take(seq, t)`/`request_release(seq)`
  replace the old `cmd` dispatch (called from `flight_desired.lua`), returning `"accepted_active"`/
  `"pending"`/`{refused=<reason>}` rather than mutating a wire-visible seq. `apply_desired_changes_
  to_law` (called every active, non-paused frame) compares `flight_desired.get()`'s own `stamp_hdg`/
  `stamp_alt`/`stamp_spd` against what this module last applied and calls `law_apply_goal` only for
  the parts that changed — "mode 1 applies desired by stamp". `build_take_seed` replaces the old
  `ai_pilot_wheel.held_targets()` read at `law_init_at_take`: an **unpark** seed is `desired`
  verbatim (converted to true heading); a **voice take**'s seed falls back to the measured-state
  defaults for every part *except* one `desired` stamped strictly after the take's own `seq` (the
  "a set during taking survives the seed" test). A standing break carried into an unpark (`desired.
  turn_rate_deg_s`/`turn_style != "normal"`) is layered onto the freshly-seeded law via one more
  `law_apply_goal` call, immediately after `law_init_at_take` — `law_init_at_take` itself has no
  rate-override field of its own. The roll-out settle (turn→heading) and the break settle (the rate
  override clearing) each call `flight_desired.write_internal` with the settled heading, converted
  back into `HEADING_REF`'s own reference. `fc_goal_*`/`fc_take_seq`/`fc_last_cmd_seq` are dropped
  from the status line entirely — body-layer reads the commanded value from `flight_desired`'s own
  `fd_*` fields now.
- **Lua (`ai_pilot_wheel.lua`)**: `mirror_m2_goal` call removed (body-layer's own dual-write,
  below, replaces it). The CBTM `align` press schedules a short delayed read (`ALIGN_READ_DELAY_S`,
  0.1 s — "a few frames" per U6's own answer, not `MODE_READ_SETTLE_S`) that writes the overlay's
  course into `desired.heading_deg` via `flight_desired.write_internal`, so an unpark shortly after
  an align already carries the aligned heading in this stage, even though the new channel's own
  `align` kind is not live until Stage 4.
- **Lua (`commands.lua`)**: `handlers.flight = flight_desired.handle_flight_command` replaces
  `handlers.flight_control`.
- **aircraft-layer (Python)**: `schema/flight_desired.py` gains `epoch`/`last_seq`/`acks`;
  `schema/flight_control.py` drops `take_seq`/`goal_seq`/`last_cmd_seq`/`goal_*` entirely.
  `CommandSender.send_flight`/`POST /command/flight` replace `send_flight_control`/`/command/
  flight_control` (the old path now resolves as any other unknown route, confirmed with a `404`
  test). `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` bumped to `"2026-11-20c"`.
- **body-layer (Python)**: `ConsolePerceptionRunner.command_seq` — the one mission-wide counter
  (preserved across a mission restart, same reasoning as `command_reset_epoch`). `_apply_flight_
  requests` replaces `_apply_flight_control`: sends a pending take/release/set on the numbered
  channel, queues a `PendingTake` (`belief.flight_authority.PendingTake`) for a take using the
  `says` text `CrewConsole.take_controls` recorded; the lease is unchanged. `belief.flight_control.
  take_controls`/`release_controls` are now pure request builders with **no `FlightControlState`
  parameter at all** (no more `phase` to transition); `decide_flight_control`/`FlightControlDecision`
  are deleted outright, replaced by `belief.flight_authority.resolve_pending_take` (matches a
  `PendingTake` against `fd_acks`, same accept/refuse/timeout shape the deleted function had, keyed
  off `fd_acks` instead of polling `fc_take_seq`/`fc_mode`). `FlightControlState` sheds `phase`/
  `take_seq`/`pending_take_says`/`took_at_sim`/`unpark_take`/`wire_seq`/`held_*`/`lua_take_seq`/
  `lua_last_cmd_seq` entirely — it is a read-only diagnostics mirror now (measured telemetry,
  handover-diagnostics fields, A9 bands, slip-ball). `CrewConsole.drain_flight_control` drops the
  Decision-32 break-seed logic (obsolete: Lua's own `build_take_seed` carries a standing break
  through the unpark directly now) and the `flight_control_system_release_pending` ack-timeout
  self-queued release (obsolete: `resolve_pending_take`'s own timeout path covers it, and a late-
  accepted ack is simply not corrected — see the gap noted below). `_axes_current_heading/altitude/
  speed` now read `flight_authority_state`'s own desired-state mirror first, falling back to
  `flight_control_state.measured_*` only when it has nothing yet.
  **`_apply_ai_pilot_wheel_goal`'s own send site gains the plan's own dual-write**: every ordinary
  mode-2 voice goal (heading/altitude/speed) also sends a `set` request on the numbered channel,
  fire-and-forget, alongside the still-live `ai_pilot_goal` send — `desired` stays accurate for a
  later m2→m1 carry even though mode 2 itself does not read `desired` to fly yet (Stage 4). Mode-2
  **breaks** (CBTM) are **not** dual-written this stage — flagged as a gap below.
- `tools/check_rules.py`'s `_authority_for`/`_SCENARIOS` reworked for the split `FlightControlState`
  (diagnostics only)/`FlightAuthorityState` (authority) shapes, and fixes review-s12.md's optional
  refinement 2 in passing (the `"R"`/`"B"` letter is now mapped to `"agl"`/`"baro"` before building
  `FlightAuthorityState.alt_ref`, not passed through verbatim).

### Deviations and judgment calls (read before relying on this stage for anything beyond the plan's own Stage 3 scope)

1. **U1's "wait for Lua" readback deferral is built for the two handover tokens only, not for
   ordinary axes_*/mode-2 `set` commands.** The rule file (`config/rules/flight.lua`) still speaks
   every `heading`/`altitude`/`speed`/`turn`/`break` readback immediately and optimistically, exactly
   as before this plan — the request is sent on the new numbered channel (so the carry/stamp
   mechanics are correct), but nothing waits for its `fd_acks` entry before speaking. Implementing
   the full deferral would mean removing `say(...)` from roughly fifteen rules in `flight.lua` and
   building a generic ack-driven readback renderer matching each rule's own bespoke wording — a
   second, comparably-sized piece of work I judged too large to also get right in this pass without
   risking silent wording regressions across all of them. **This is the single largest gap against
   the plan's own U1/section 3a** and the main thing a follow-up stage (or a dedicated pass on this
   one) should close.
2. **The one consequence of (1): a `set` sent while truly `off` is refused `not_flying` by Lua and
   nothing corrects the spoken (wrong) readback.** In practice `rules/gates.py`'s own HOLD-until-
   known mechanism already keeps this rare (a command during the off→m1 settle window retries
   rather than sending), so this is a narrow window, not a routine case.
3. **A late-accepted ack after body-layer's own take timeout is not specially handled.**
   `resolve_pending_take` drops the pending take at `HANDOVER_ACK_TIMEOUT_S` and never re-checks
   that `seq` if an accept for it later appears in the ring (section 3a names this as a case to
   still speak, "a clock anomaly"). Flagged in `CrewConsole.flight_pending_take`'s own docstring.
4. **Mode-2 breaks (CBTM) are not dual-written onto the numbered channel this stage** — only
   ordinary heading/altitude/speed voice goals are. A break started in mode 2 still works exactly as
   before (unaffected, flies through the old CBTM path), but `desired.turn_rate_deg_s`/`turn_style`
   will not reflect an in-progress mode-2 break the way an ordinary heading goal does, so an unpark
   mid-mode-2-break does not yet get the Decision-32 carry this stage gives a mode-*1* break. Stage
   4 (which rebuilds mode 2 as a `desired`-reading consumer, including the CBTM dispatch) is the
   natural place to close this, rather than half-building a second, temporary wiring path for it now.
5. **`TestReleaseClearsHeldGoalsAcrossRetake`'s own test (aircraft-layer) lost most of its original
   assertive power.** `fc_goal_*` (what it checked) is gone from the wire; the replacement test
   confirms only `fc_mode` across a release→retake, not that a stale goal failed to leak — that
   concern now belongs entirely to `flight_desired.lua`'s own `clear_desired()`, already covered by
   `test_flight_desired_lua.py`'s `TestEdgeSeeding`/`TestResetAndStop`. Documented in the test's own
   updated docstring.
6. **Several aircraft-layer tests testing mechanisms this stage deletes were removed outright**,
   not adapted (their own premise no longer exists at the layer they tested): `TestRepeatedTake
   WhileAlreadyFlyingStillAcks`, `TestBadBoundRejectsWholeMessage`, `TestLastCmdSeqEchoSurvivesOn
   Stop`, `test_a_fresh_process_seq_1_is_accepted_after_reset`, `test_unknown_cmd_arm_is_now_a_no_
   op`, `TestSeqFieldsSurviveTheRealSchema` (all `fc_take_seq`/`fc_last_cmd_seq`/`fc_goal_*`-shaped).
   Their replacement coverage lives in `test_flight_desired_lua.py`'s own `TestSetRequest` (epoch/
   seq/stale/bounds refusal, exercised directly against the real `handle_flight_command`).
   Body-layer: `TestDecideFlightControl`, `TestDrainFlightControlSeedsTheBreakTarget`,
   `TestDrainFlightControlSendsReleaseOnAckTimeout` removed the same way (`decide_flight_control`/
   the Decision-32 seed logic/the self-queued release are all deleted production code) — replacement
   coverage is `test_flight_authority.py`'s new `TestResolvePendingTake`/`TestParseAcks` plus the
   `HANDOVER_ACK_TIMEOUT_S >= FLIGHT_REQUEST_ACCEPT_WINDOW_S + 1.0 + 0.2` pin.
7. **The test-impact list the plan itself names undercounted this stage too**, same pattern the
   Stage 1-2 implementer flagged. Not named by the plan but required: `tools/check_rules.py` (the
   dry-run harness needed its own `FlightAuthorityState`/`FlightControlState` split), `test_body_ai_
   pilot_wheel.py`'s `_FakeAircraftClient` (needed a `write_flight` method once the dual-write
   landed), and `test_mission_start_reset.py`'s `_RUNNER_PRESERVE` set (needed `command_seq` added,
   or the mission-restart differential test fails on the new field).

### New behaviour constant

`belief.flight_authority.FLIGHT_REQUEST_ACCEPT_WINDOW_S` (1.5, lo=0.5, hi=10.0, `judgement`) — the
plan's own named addition (section "Existing constants checked"). `belief.flight_control.HANDOVER_
ACK_TIMEOUT_S`'s default raised 2.0 → 3.0 per the plan. Both comments were rewritten so the cross-
key coupling between them is stated in the rendered first sentence of each (`config/defaults.toml`
now carries it on both sides) — `test_tuning_comment_renders.py` enforces this and caught two early
drafts that got it wrong.

### Checks, Stage 3

- aircraft-layer: `ruff format --check`/`ruff check` pass; `mypy src` passes (29 source files);
  `luac5.1 -p` passes on every touched Lua file (`flight_desired.lua`, `flight_control.lua`, `ai_
  pilot_wheel.lua`, `commands.lua`, `Export.lua`); the GETGLOBAL sweep on every touched Lua file is
  clean (only stdlib/DCS APIs and the legitimate cross-module globals `ai_pilot_wheel`/`flight_
  control`/`flight_desired`/`client`/`debug_log`); full suite `pytest tests -q`: **1101 passed**.
- body-layer: `ruff format --check`/`ruff check` pass; `mypy src` passes (93 source files); full
  suite (`not slow`, parallel via `pytest-xdist`): **3698 passed, 4 xfailed**; the 27 `slow`-marked
  flight scenario tests also run separately (`pytest tests -q -m slow`): **27 passed**.
- `config/defaults.toml` regenerated (`tools/generate_defaults.py --write`) and committed.

### Stage 3b, 2026-11-20 — the wait-for-Lua readback, for every flight command

Branch `impl/desired-state-s3b`, cut from `feature/bl16-desired-state-s34`'s own tip (`1a95043f`).
Closes Stage 3's own deviation (1): U1's "wait for Lua" now covers every ordinary `flight_
control*` command, not only the two handover tokens.

**Side fix first, own commit**: the user's test flight the same day (`explore-notes.md`, "Heading
reference measured: true") found `HEADING_REF = "true"` genuinely measured (not a placeholder —
the overlay and HSI both read true) and `fd_hdg_mag_deg` mislabelled (`LoGetMagneticYaw` returns
radians). `flight_desired.lua` gained `wrap360_deg`/`magnetic_yaw_deg` (converts via `math.deg`,
wraps into `[0, 360)`, also fixing the same unit bug in the otherwise-dead `update_heading_
variation` path); `belief.flight_authority._as_optional_degrees_0_360` wraps the two heading
mirror fields again defensively at body-layer's own boundary, with a test.

**Shape, matching the plan's own recommendation**: one generic deferred-readback mechanism, not
fifteen rule edits. The rule files are completely unchanged — every `flight.lua` handler still
computes its readback and calls `say(...)` exactly as before. What changed is what happens to
those lines between the handler returning and the console actually speaking them:

1. **`handle_command`'s own tail** (`CrewConsole`) checks, after a `flight_control*`-category
   dispatch (never `flight_handover`, which already defers via its own `PendingTake`/`says`
   mechanism), whether the handler actually queued a numbered-channel transition this call
   (`_flight_control_transition_queued` — only `flight_control_goal_transition` (every mode-1
   command) and `ai_pilot_goal_transition`/`ai_pilot_level_flight_transition` (mode 2's ordinary
   heading/altitude/speed/level-flight voice goals) count, since those are the only one-shots
   `body.py` actually dual-writes onto the `flight` channel this stage). If so, the computed
   `lines` are staged onto `CrewConsole.pending_flight_readback_lines` instead of being printed —
   a local refusal (a gate `hold`/`unable`, or an action's own `RuleUnable`, e.g. "turn left" in
   the AI overlay, align/HVRT in mode 1) never reaches Lua at all and keeps speaking immediately,
   unchanged.
2. **`body.py`'s own wire-send sites** (`_apply_flight_requests`'s `goal_request` block, `_apply_
   ai_pilot_wheel_goal`'s mode-2 dual-write block) claim the staged lines
   (`CrewConsole.take_pending_flight_readback_lines`) right after minting the request's own `seq`,
   and pair them into a `belief.flight_authority.PendingFlightReadback(seq, lines, sent_at_sim)`
   appended to `CrewConsole.pending_flight_readbacks` — one shared FIFO queue for both modes, since
   `fd_acks` is one shared ring.
3. **`drain_flight_control`** resolves that queue every poll via the new `belief.flight_authority.
   resolve_pending_flight_readbacks` (generalising `resolve_pending_take`'s own ack-matching):
   strict FIFO by `seq` (an unresolved front entry blocks every later one, even if its own ack
   already arrived — "ack outcomes in seq order, never arrival order"); accepted speaks every
   line verbatim; refused maps the reason through a small closed table (`wrong_mode` → `AI_
   OVERLAY`, everything else → `NOT_READY`, per 3a's own "no new spoken wording" — no reason
   needed the fallback in practice, since `set` requests never see `wrong_mode`/`bounds` today);
   no ack inside `HANDOVER_ACK_TIMEOUT_S` speaks "Unable, not ready." and drops the entry (3a: "a
   timeout is always the truth" — `Export.lua`'s own `until` deadline makes a late accept
   impossible).
4. **The two suppression/hold rules (3a)**, both in `drain_flight_control`:
   - A request sent while a take is still pending holds its own readback until the take resolves
     — accepted releases the held queue right after "I have controls." (same poll, seq order);
     refused/timed out drops the whole queue unspoken (`self.pending_flight_readbacks = []`).
   - `suppress_accepted_readbacks=True` (passed from `body.py` exactly when `decide_flight_
     speech`'s own forced-off-edge check fired this poll) drops only the *accepted* half of this
     poll's own resolution, never a refusal/timeout — the mode's own urgent "You have controls!"
     is the truth instead.

**Mode 2's HVRT and CBTM are deliberately excluded**, not merely omitted: `_flight_control_
transition_queued` does not check `ai_pilot_hvrt_transition`/`ai_pilot_hvrt_step_transition`/`ai_
pilot_cbtm_transition` at all, because none of the three is dual-written onto the numbered
channel this stage (the Stage 3 implementer's own flagged CBTM gap, extended here to HVRT for the
identical reason — Stage 4 rebuilds mode 2 as a `desired`-reading consumer and is the natural
place to wire both up). Staging a readback for either would mean speaking it never, since no
`fd_acks` entry for it will ever arrive. `TestCbtmActions::test_align_s_readback_is_not_deferred`/
`TestHvrtTranslate::test_the_readback_is_not_deferred` pin this boundary directly, beyond the
pre-existing differential tests that already proved it by passing unchanged.

**A dropped-unsent request's staged readback is not silently lost.** `_apply_flight_requests`'s
own Co-moving row 11 branch (a mode-1 goal action spoken just before a park discards the
transition unsent when `flight_mode() == "overlay"` by send time) now also claims and speaks
"Unable, not ready." for whatever was staged, rather than leaving it to leak into a later,
unrelated dispatch's own claim. This is the one case the generic mechanism could have silently
broken that the Stage 3 code did not need to consider at all.

**D19/U22's own bypass is unaffected by the deferral, by design decision**: when a staged
readback finally speaks (accepted case), `drain_flight_control` still gates `bypass_gate` on
`current_crew_state().has_controls`, the same condition `handle_command`'s own immediate-dispatch
branch already used — the readback is still flight-category speech, it is simply heard a poll or
two later than before. `FlightAuthorityDecision.urgent` stays `False` for every ordinary
flight-channel readback either way (3a names no urgent one; only the handover's own "I/You have
controls." is urgent) — `bypass_gate` and "urgent" are two different things here, and only the
latter is fixed by 3a.

### Deviations and judgment calls, Stage 3b

1. **The late-accepted-ack-after-timeout gap (3a's own "clock anomaly" case, flagged on `flight_
   pending_take` since Stage 3) is not closed here either**, and not by oversight: closing it
   needs a small bounded "recently dropped" watch list (seq → the lines/says that would have been
   spoken) checked against `fd_acks` on every subsequent poll until the ring itself ages the entry
   out, plus the one-shot WARNING log 3a names. That is a second, independent piece of state and
   bookkeeping, not a one-line fix, and the brief's own "close it if it's cheap" qualifier reads
   as permission to skip it when it is not — judged not cheap enough to add safely in this pass
   without risking an unbounded or leaky watch list. Left as a follow-up, same flag as Stage 3's.
2. **The refusal-reason map has one real entry (`wrong_mode`) and a blanket fallback**, not five
   named entries, because `stale`/`epoch`/`not_flying`/`precondition`/`bounds` all reduce to the
   existing `NOT_READY` wording and nothing in `belief.speech._UNABLE_TEMPLATES` distinguishes
   them anyway (3a: "no new spoken wording") — a five-entry table mapping four reasons onto the
   same string would read as more precision than exists. If a future Lua reason needs its own
   wording, it still degrades to `NOT_READY` here rather than crashing, per 3a's own "flags it"
   fallback.
3. **Two commands landing inside the same poll tick is not specially handled.** Each of the two
   one-shot staging fields (`flight_control_goal_transition` for mode 1, the mode-2 goal fields)
   can hold only one pending request at a time; a second `handle_command` dispatch before `body.
   py`'s own send runs would overwrite the first's staged readback. This is not a new risk this
   stage introduces — the pre-existing wire fields had the identical "one pending transition per
   poll" shape before any of this — and voice dispatch is one transcript at a time in practice
   (confirmed against the existing "two commands in one breath" card scenario, which relies on two
   separate utterances reaching two separate polls, not one poll dispatching twice). Flagged for
   completeness, not fixed.

### Tests added, Stage 3b

- `test_flight_authority.py`'s `TestResolvePendingFlightReadbacks` (eleven cases: accepted/
  refused/timeout/still-waiting, seq-order holding a resolved-but-not-front entry, two accepted
  entries speaking in seq order, both suppression-accepted cases) plus a negative-degree wrap test
  under `TestAdvanceFlightAuthority` for the heading-reference side fix.
- `test_body_flight_control.py`: a goal request's staged readback queued against its own sent
  `seq`; no staged readback queues nothing; the overlay-flip-discard case now also speaks "Unable,
  not ready." for a staged readback rather than leaking it.
- `test_body_ai_pilot_wheel.py`: the mode-2 dual-write's own staged readback queued against the
  dual-write's own `seq`.
- `test_rules_flight_actions.py`: the `TestFlightReadbackUrgency` case rewritten for the deferred
  flow (dispatch stages, nothing speaks, then a simulated ack drains and speaks with the same
  bypass); a mode-1 command's readback also defers; the not-flying local refusal is never
  deferred; CBTM's and HVRT's own readbacks are explicitly pinned as never deferred.

### Checks, Stage 3b

- aircraft-layer: `ruff format --check`/`ruff check` pass; `mypy src` passes; `luac5.1 -p` passes
  on `flight_desired.lua`; the GETGLOBAL sweep is clean (only stdlib/DCS APIs and the pre-existing
  cross-module globals); full suite `pytest tests -q`: **1101 passed**.
- body-layer: `ruff format --check`/`ruff check` pass; `mypy src` passes (93 source files); full
  suite (`not slow`, parallel via `pytest-xdist`): **3718 passed, 4 xfailed**; the 27 `slow`-marked
  flight scenario tests also run separately: **27 passed**.
- `tools/check_rules.py`'s dry-run harness: clean, no new failures.

## Review-fix round, 2026-11-20 (`plans/flight-desired-state/review-s3.md`, NEEDS REVISION)

All four required fixes.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`:
  - **Required Fix 1 (U2, the m2→m1 carry)**: `build_take_seed`'s unpark branch now clamps the
    seed it hands `law_init_at_take` to `fc_limits.min_ias_kmh`/`max_ias_kmh` (speed) and
    `fc_limits.floor_agl_m` (altitude, agl ref only) — the same bounds
    `belief.flight_control.clamp_speed`/`clamp_altitude` already enforce body-side. `desired`
    itself (and the `fd_ias`/`fd_alt` wire fields it mirrors) is never touched by this clamp —
    only the value actually fed to the law. Pruned the branch's own "verbatim carry" comment
    (now wrong) to say so.
- `body-layer/src/belief/flight_authority.py`: new `decide_carried_value_speech(prev, new)`,
  the announcement half of the same fix. Fires on the same `fd_mode_n` edge `decide_flight_
  speech` watches, only when the edge lands in `m1` with cause `unpark`; compares `new.ias_kmh`/
  `alt_m` against `belief.flight_control.clamp_speed`/`clamp_altitude` and returns one non-urgent
  `FlightAuthorityDecision` per part that differs ("Speed 8 0." for the plan's own worked
  example). A small private `_digit_readback` copies `CrewConsole._digit_readback`'s one-line
  algorithm rather than importing it — `crew_console.py` already imports this module, so the
  reverse import would be circular; flagged here rather than silently duplicating it unremarked.
- `body-layer/src/body.py`: calls `decide_carried_value_speech` right after `decide_flight_
  speech` each poll (section 3a's own speech order: mode-change lines first, then U2's
  carried-value lines) and speaks each returned decision via the existing `speak_flight_
  authority_decision`.
- `docs/acceptance/2026-11-20-bl16-desired-state-s3-card.md`: added step 10, the "speed 0 in m2
  then unpark" scenario the plan's own Stage 3 bullet named but the shipped card omitted.
- `body-layer/CLAUDE.md` (**Required Fix 4**): `flight_control.py`'s module-map entry no longer
  describes the deleted `decide_flight_control` as current — now says what replaced it
  (`belief.flight_authority`'s `decide_flight_speech`/ack-matching) and that `FlightControlState`
  is diagnostics-only.

### Where the U2 clamp lives, and why

**On the Lua side, at `build_take_seed` itself — not at a Python m2→m1 edge handler.** What mode 1
actually *flies* is decided entirely in `flight_control.lua` (the seed fed to `law_init_at_take`);
body-layer has no write path into that value at all, only a read-only mirror of `desired`. So the
clamp has to live where the seed is built, which is also where the review's own alternative
("or at `build_take_seed` itself") pointed. The announcement is necessarily a second, separate
piece in Python (`decide_carried_value_speech`), because only body-layer speaks — it recomputes
the same clamp body-side (reusing the already-existing `clamp_speed`/`clamp_altitude`) against
the mirrored exact `fd_ias`/`fd_alt` values to decide whether to say anything, but it never
*writes* the clamped value anywhere; Lua's own clamp is what actually protects the law. **Q1a
("the desired state keeps the exact value; what's flown is clamped") is why `desired` is never
touched by either half** — the wire's `fd_ias`/`fd_alt` read the same number the pilot said, in
both modes, before and after this fix.

Per the brief: the user has since said the coming lift-vector law will have no minimum speed, so
this clamp is kept deliberately small and tied only to mode 1's *current* `fc_limits.min_ias_kmh`/
`max_ias_kmh`/`floor_agl_m` — four `if`/`elseif` lines in one existing function, no new constant,
no new desired-state rule. Removing it later (when the law itself no longer needs a floor) is a
revert of those four lines plus the Python announcement function, not a redesign.

### Tests Added

- `aircraft-layer/tests/test_flight_control_lua.py`:
  - `TestVoiceTakeSetDuringTakingSurvivesTheSeed` (Required Fix 2) — drives a `set_desired` with
    a `seq` strictly after the take's own `seq` while `fc_mode == "taking"` (before the resolving
    `run_flight_control` call), confirming the law adopts the later-stamped heading rather than
    the measured default; a control case pins `seq == take_seq` (not strictly after) as *not*
    surviving.
  - `TestUnparkTakeSeedClampsToMode1Limits` (Required Fix 1's own Lua-side proof) — "speed 0" and
    "speed 400" carried through an unpark fly `MIN_IAS_KMH`/`MAX_IAS_KMH` respectively (via
    `fc_in_band_speed` against a measured IAS set to the expected clamped value); an in-range
    carry is unaffected. Verified these two fail at this branch's own pre-fix state (`git stash`
    of just this file, re-run, restored by sha) — the in-range control case does not regress.
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`:
  - `TestAlignReadScheduling` (Required Fix 3) — extended `_run_ai_pilot_wheel_integration`'s
    harness with a `flight_desired` mock (`write_internal` call recorder), the `ai_wheel_align_
    read_at_t` local, the `ALIGN_READ_DELAY_S` constant, and the `held_targets`/`run_ai_pilot_
    wheel_with_align_read` functions (additive only — no existing test's call shape changed).
    Drives `ai_pilot_cbtm.action = "align"` directly (same "write the state a real dispatch
    would set" convention `ap_held`/`set_desired` already use elsewhere in this codebase) through
    a real `update_ai_pilot_wheel_overlay` call with `mode_text = "CBTM"`, confirming: the press
    fires and schedules the deferred read; nothing is written before `ALIGN_READ_DELAY_S` elapses;
    the deferred read writes the post-align `course_text` once the deadline passes; a stale/nil
    `course_text` at the deadline writes nothing (but still consumes the deadline, matching the
    "one-shot, never retried" docstring).
- `body-layer/tests/test_flight_authority.py`:
  - `TestDecideCarriedValueSpeech` — no-op cases (no edge, unchanged mode, a park edge, an
    in-range unpark carry, a voice-take edge), the plan's own "speed 0" worked example, a
    ceiling-clamp case, an agl-floor case, baro altitude never floored, both parts carried badly
    in one call, and the digit-spelling format itself (`"Speed 8 0."`).

### Checks

- aircraft-layer: `ruff format --check`/`ruff check` pass (one `ISC004` lint fixed in the new
  test file); `mypy src` clean (29 files); `luac5.1 -p` passes on both touched Lua files; the
  GETGLOBAL sweep on both is clean (stdlib/DCS APIs plus the pre-existing legitimate cross-module
  globals only — no new global leak from the clamp); full suite `pytest tests -q`: **1109
  passed**.
- body-layer: `ruff format --check`/`ruff check` pass; `mypy src` clean (93 files); full suite
  (`not slow`, parallel via `pytest-xdist`): **3728 passed, 4 xfailed**; `slow`-marked tests run
  separately: **27 passed**.

### Notable Discoveries

- `fc_in_band_speed`/`fc_in_band_altitude`/`fc_in_band_heading` all start `false`
  unconditionally at `law_init_at_take` and are only recomputed by the *next* `law_update` call
  (the just-took frame returns before calling it) — a clamp test asserting "in band" needs one
  extra `run_flight_control` call after the take frame, easy to miss (cost three failed first
  drafts here).
- A second stale reference to the deleted `decide_flight_control` survives outside the file this
  review named: `flight_control.lua` lines ~1772 and ~1990 (two comments, one inside `run_active_
  frame`, one inside the unpark-take branch) still name it. Neither is attached to code this
  round touched (the first is adjacent to the seed-building call I did edit, and was pruned along
  with the "verbatim carry" line above; the second is one screen away, inside the unpark
  precondition-refusal branch, which this round did not otherwise touch) — left as found, per
  this role's own "stay local to the block you are editing" rule, but flagged here since it is
  the same defect class Required Fix 4 was about, just outside `body-layer/CLAUDE.md`.
- `docs/STRUCTURE.md` (body-layer) also still names `decide_flight_control` as current (two
  hits) — out of this review's named scope (it named `body-layer/CLAUDE.md` specifically), left
  untouched, flagged for whoever next edits that entry.
