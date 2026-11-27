### Debug Report

### Observed Issue

BL-B139 (`docs/acceptance/2026-11-27-mode2-recovery-feedback.md`, user direction
2026-11-27): in mode 2 (Petrovich flying through ED's AI-pilot wheel), recovery from
"align for launch" sets the AI pilot's altitude/speed goals back to the pre-align
snapshot, but ED's AI pilot does not actually fly back to them — it keeps whatever it
was doing at the moment of recovery. User's own words: *"DCS AI needs a alt and speed
change to react... If already at that value, step it down a bit (enough that the
value changes, no more is needed) and then back to desired value."*

### Hypothesis

ED's AI pilot overlay only reacts to a *change* of its displayed set altitude/speed.
`seed_recovery_goal` (`body-layer/src/belief/ai_pilot_wheel.py`) seeds the recovery
goal's target directly from `FlightSnapshot` — the values captured at "align for
launch" time, i.e. exactly what the overlay was already showing before the dive/break
that triggered recovery (altitude/speed are never changed by a break or an alignment
itself). So on the very first goal tick after recovery starts, the held value already
equals the target. `Export.lua`'s `ai_pilot_goal_tick_altitude`/`ai_pilot_goal_tick_speed`
both treat "already matches the target" as "nothing to do" — `ai_pilot_correction_
direction`/`ai_pilot_goal_speed_tap_direction` both return `nil` when the held value is
within tolerance of (or exactly equal to) the target, and the tick immediately reports
`"settled"` without ever opening a hold or issuing a tap. Zero presses reach the wheel,
so ED's AI pilot never registers a change and never starts flying the recovery.

### Evidence

- `body-layer/src/belief/ai_pilot_wheel.py::seed_recovery_goal` (around line 994):
  `altitude_target_m=snapshot.altitude_m`, `speed_target_kmh=snapshot.speed_kmh` — the
  snapshot is exactly the pre-align held values (`capture_flight_snapshot`), which the
  overlay is still displaying when recovery starts (nothing in the align/break/recovery
  path changes the AI's actual altitude/speed set value in between).
- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua::ai_pilot_correction_direction`
  (around line 577, pre-fix): `if math.abs(held_m - target_m) <= tol then return nil end`
  — `nil` means "no press needed." `ai_pilot_goal_tick_altitude` (around line 1046,
  pre-fix): `if dir == nil then ai_pilot_goal_release_hold(); ai_pilot_goal.progress =
  "settled"; return end` — confirmed: a goal whose target already matches the display
  settles with zero presses.
- `ai_pilot_goal_speed_tap_direction` (around line 683, pre-fix): `if held_kmh ==
  target_kmh then return nil end` — same "already matching, nothing to do" shape for the
  discrete speed ladder.
- Both are the *correct* behaviour for an ordinary voice goal (no reason to press
  buttons when nothing needs to change) — the bug is specific to recovery, where the
  "already matching" case is actually the common case, not an edge case.

### Fix Applied

Added a `wake` flag that rides the existing `ai_pilot_goal` wire message
(`POST /command/ai_pilot_goal`), set `true` only while
`ParkedFlightState.align_phase == "recovering"` (`body._apply_ai_pilot_wheel_goal`, all
three send sites) — an ordinary voice goal that happens to already match the held value
is untouched and keeps settling with zero presses, exactly as before.

In `Export.lua`'s `ai_pilot_wheel.lua`:

- `ai_pilot_wake_kick_direction_hold(t, ordinary_dir)` — altitude's own decision. While
  `.wake` is set and the kick hasn't run yet for this `goal_seq`: if the ordinary
  correction direction is already non-`nil` (a real mismatch, or the kick has just taken
  effect), the wake is marked done and the ordinary hold-and-poll loop is left to
  converge back to the exact target unchanged. Otherwise it forces a `DOWN` hold (the
  same physical hold the ordinary correction uses) for up to
  `AI_PILOT_WAKE_KICK_TIMEOUT_S` (1.5 s); once the held value has moved far enough that
  the ordinary direction stops being `nil`, the kick stops and the existing converge-back
  logic takes over — no new "return to target" code was needed, the existing hold-and-
  poll loop already does that. If 1.5 s of holding `DOWN` produces no detectable change
  (the wheel's lower stop), it tries `UP` once; if that also produces nothing, it gives up
  (marks the wake done) rather than holding a button open forever.
- `ai_pilot_wake_kick_direction_tap(t, ordinary_dir)` — speed's own decision, for the
  discrete tap-per-tick ladder: issues **exactly one** tap in the forced direction (never
  a repeated tap per tick, which would walk more than the one step the user asked for),
  then waits (returns `"wait"`, no action, progress stays `"pressing"`) for the next
  tick's readback. Same `DOWN`-then-`UP`-fallback-then-give-up shape as the altitude
  variant, bounded by the same `AI_PILOT_WAKE_KICK_TIMEOUT_S`.
- Both are wired into `ai_pilot_goal_tick_altitude`/`ai_pilot_goal_tick_speed`: the
  ordinary direction is computed first as before, then the wake-kick function is given
  the chance to override it for this tick only. Heading is untouched — recovery
  deliberately excludes heading (Fix 2, "keep aligned heading").
- `handle_ai_pilot_goal_command` parses the new `wake` field (`extract_json_bool_field`,
  a local copy of `flight_control.lua`'s own helper — `core.lua`'s JSON helpers have no
  boolean sibling) and resets the wake-kick bookkeeping (`wake_kick_dir`/
  `wake_kick_started_t`/`wake_kick_tried_up`) whenever `.param` changes, same reasoning as
  the pre-existing `mode_cycle_attempts`/`toggling_reference` reset in that branch.
- `aircraft_client.write_ai_pilot_goal`/`collector.command_sender.send_ai_pilot_goal`/
  `POST /command/ai_pilot_goal` all carry the new `wake: bool` field through, default
  `False`, shape-validated as a strict bool at the API boundary (same posture as every
  other field on this endpoint).

Edge cases from the task brief:

- **Step-down impossible at the wheel's lower stop**: both kick functions try `DOWN`
  first, and if `AI_PILOT_WAKE_KICK_TIMEOUT_S` elapses with no detectable change, they
  try `UP` once as the fallback, then give up (mark the wake done, let the goal settle)
  rather than holding/tapping forever. Chosen over guessing a floor value because neither
  Lua side knows the wheel's real stops (altitude is a continuous hold with no known
  floor constant; speed's full step ladder lives only in body-layer, Lua only knows the
  MAX-sentinel threshold) — detecting "no change happened" is the only thing Lua can
  observe directly.
- **Displayed value already off-target**: the ordinary direction is computed first every
  tick; if it is already non-`nil` the wake is marked done immediately and no kick runs
  at all — the normal path.
- **Recovery interrupted mid-step** (a break, or a fresh voice command, landing while a
  kick is open): both `handle_ai_pilot_goal_command`'s own `param ~= ai_pilot_goal.param`
  branch (any new goal) and the pre-existing F-P7 break-wins logic already release any
  open hold before the new param takes over (`ai_pilot_goal_release_hold()`), and the
  wake-kick fields are reset in the same branch — so a step is never left half-open.

### Verification

- `luac5.1 -p` and the `GETGLOBAL` leaked-name check both pass on the modified Lua file
  (no accidental global reference, no Lua-forbidden `[[...]]` wiki link left in the
  source — the first pass over this fix introduced nine `[[BL-B139]]` references in the
  Lua file and `test_dcs_export_lua_syntax.py::test_no_nested_long_bracket_in_block_
  comment` caught it; all replaced with backticked `` `BL-B139` ``).
- `aircraft-layer`: `ruff format --check`, `ruff check`, `mypy src` all clean; full
  `pytest tests -q` — 1073 passed (includes the real-Lua-interpreter integration tests in
  `test_ai_pilot_wheel_lua.py`, extended with the new functions/constants/fields, and new
  tests in `test_ai_pilot_goal.py` for `wake` forwarding/validation).
- `body-layer`: `ruff format`/`ruff check`, `mypy src` all clean; targeted
  `test_body_ai_pilot_wheel.py`/`test_aircraft_client.py`/`test_ai_pilot_wheel.py` — 172
  passed, including two new assertions (`test_a_recovery_trip_sends_wake_true`/
  `test_an_ordinary_goal_sends_wake_false`) proving the flag is set exactly while
  `align_phase == "recovering"` and never otherwise. Full `pytest tests -q` run in the
  background to cover the whole suite once (see hand-back report for its result).
- Not independently verified live against a running DCS session (no Windows box in this
  environment) — same posture as every other change to this file;
  `#needs-flight` belongs on the roadmap entry.
