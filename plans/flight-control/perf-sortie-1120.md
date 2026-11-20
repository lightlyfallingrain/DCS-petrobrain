### Performance Review

Batch `fix/bl16-sortie-1120`, base `98174b54`, tip `b59aa99e`. Scope: the law's new break-bias
unwind/turn-coordination-pedal terms and unpark seed (`flight_control.lua`), `ai_pilot_wheel.lua`'s
retuned tolerances/CBTM-ends-on-latest-command handler, the new `reset` command path
(`Export.lua`/`commands.lua`/`core.lua`/`api/server.py`/`command_sender.py`), and body-layer's
`_resolve_command_reset` + `rules.gates` check. No hard real-time budget applies yet (Petrobrain
Runtime has not started); the relevant bars here are "no per-request allocation on a per-frame
hot path" and "don't let a per-poll addition become a hidden loop."

### Findings

#### `run_flight_control`'s existing per-frame `GetDevice(0)` closure tally — not grown by this batch
- **Location:** `flight_control.lua`'s `axis_magnitude`/`capture_from_seat`/`read_axis`
  (`update_live_seat_tracking`, called unconditionally every `LuaExportBeforeNextFrame`).
- **Risk:** this is the pre-existing, already-tracked finding from `plans/flight-control/perf-m1-m2.md`
  (6 fresh `GetDevice(0)` lookups + closures, every frame, forever) and the memory file
  `project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy.md`. Checked this batch's diff specifically
  for growth against that named threshold ("if a fourth such function is added... re-open this
  finding") — this batch adds no new per-frame caller of `read_axis`/`GetDevice(0)`. The new
  `held_targets()` read (unpark seed) fires once per take, not per frame; the new slip-ball reads
  (`SLIP_BALL_ARGS.pilot`/`.operator`) and `LoGetSlipBallPosition` are inside `push_flight_control_state`,
  gated at 5 Hz, not the per-frame path. The threshold is not retriggered by this batch.
- **Action:** MONITOR (carry the existing perf-m1-m2.md recommendation — cache `local device0 =
  GetDevice(0)` once per frame pair when this file is next touched for its own reasons — forward,
  not reopened here).

#### `law_update`/`law_init_at_take`'s per-frame full-state table clone — unchanged shape, two more fields
- **Location:** `flight_control.lua:726-728` (`law_update`'s `next_state = {}` + `for k,v in
  pairs(state) do next_state[k] = v end`), same pattern in `law_init_at_take`. This batch adds
  `break_pedal_bias_accum` and `turn_coord_pedal` to the ~30-field state table cloned every active
  frame.
- **Risk:** none credible at this scale. The clone-and-return shape is a deliberate, plan-mandated
  trade-off (pure functions over an explicit state table so the toy-plant harness can drive them
  with no DCS mock) — already in place before this batch, already accepted by `perf-m1-m2.md`'s
  own review of the law. Two more scalar fields on a ~30-field table clone, once per active frame,
  is not a measurable addition to an already-accepted cost; DCS mode-1 is single-aircraft,
  single-player, and this never scales with contact count, world size, or mission length.
- **Action:** MONITOR (no new action; noted so a future reviewer sees this batch's addition was
  checked against the existing accepted baseline rather than assumed clean).

#### New break-bias/turn-coordination-pedal arithmetic in `law_update` — plain scalar ops, no new calls
- **Location:** `flight_control.lua:918-987` (`d_t_y`/`break_bias`/`break_pedal_bias_accum`
  tracking, `turn_coord_pedal` overlay).
- **Risk:** none. Every addition is arithmetic on numbers already computed this frame (`c_dot`,
  `r_d`, `state.rate_override_deg_s`) — no new table allocation, no new DCS API call, no closure.
- **Action:** none.

#### `push_flight_control_state`'s 5 Hz slip-ball readout — three new DCS reads, correctly gated
- **Location:** `flight_control.lua`, `push_flight_control_state` (new `slip_ball_pilot_raw`/
  `slip_ball_operator_raw`/`slip_ball_lo_api` reads, two via a fresh `safe_call(function() ... end)`
  closure each).
- **Risk:** negligible. This status push already runs at the existing 5 Hz export gate
  (`core.tick_due`, confirmed in `Export.lua:385-455`) alongside the other `push_*` status lines —
  three extra reads and two small closures at 5 Hz, in every `fc_mode` (not per-DCS-frame), is the
  same cost class `perf-m1-m2.md` already cleared for this status line's siblings. Matches the task
  brief's own framing exactly (three more values at the 5 Hz push).
- **Action:** none.

#### `ai_pilot_wheel.lua`'s CBTM-ends-on-latest-command handler — event-driven, not per-frame
- **Location:** `ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command`, new `elseif` branch ending an
  open CBTM episode (one `safe_call(function() GetDevice(30):performClickableAction(...) end)`).
- **Risk:** none. Runs only when an inbound `ai_pilot_goal` command arrives while a CBTM action is
  open — an event, not a per-frame or even 5 Hz tick. The retuned tolerance constants
  (`AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M = 0.5`, `AI_PILOT_HEADING_TOLERANCE_DEG` tightened to `0.5`)
  change how long a hold-and-poll loop keeps pressing, not its per-tick cost — each tick is still
  one comparison, same as before.
- **Action:** none.

#### Body-layer `_resolve_command_reset` + `rules.gates._require_controls` — O(1) per poll
- **Location:** `body-layer/src/body.py:_resolve_command_reset` (called once per poll, before
  `_apply_ai_pilot_wheel_goal`/`_apply_flight_control`), `body-layer/src/rules/gates.py`'s new
  `commands_ready` check.
- **Risk:** none. A handful of field comparisons, one bounded-resend gate (`time.monotonic()` diff
  against `COMMAND_RESET_RESEND_INTERVAL_S`), and at most one `aircraft_client.write_reset` HTTP
  call per `COMMAND_RESET_RESEND_INTERVAL_S` (2 s) while unconfirmed — no loop over a collection, no
  per-poll allocation beyond the existing dataclass `replace()` pattern already used throughout
  this module and cleared in `perf-m1-m2.md`/`perf-batch-a.md`. Once confirmed (the common case for
  the rest of the process's life) it is a single boolean short-circuit.
- **Action:** none.

#### `/command/reset` HTTP/UDP path (`api/server.py`, `command_sender.py`, `commands.lua`)
- **Location:** new `POST /command/reset` handler, `CommandSender.send_reset`, `commands.lua`'s
  `handle_reset_command`.
- **Risk:** none. Ordinary bounded-shape write path, same cost class as every other `/command/*`
  endpoint already in this codebase (one JSON parse, one bounds check, one UDP send). Not called
  from a hot loop — `_resolve_command_reset` throttles it to at most once every 2 s while
  unconfirmed, and never again once confirmed.
- **Action:** none.

### Verdict
APPROVED
