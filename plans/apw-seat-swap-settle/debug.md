### Debug Report

### Observed Issue

`ai_pilot_parked_active` (`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`) goes `true`
for a few frames when the player jumps from the pilot seat to the operator seat, even though the
copilot controls are not actually parked (unstowing, not ED's AI flying). Measured live, flight 8,
2026-11-18 (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, "Flight 8"): the
camera reached the operator seat at 17.301 s while arg 852 (operator stick stow) still read 0.963
(stowed, left over from the pilot seat forcing it so). 852 then animated down over ~0.3 s (0.930,
0.893, 0.853, ..., 0.624 at +94 ms). For the first few frames after the seat change the park-rising
check saw `in_operator_seat = true` and `stick_park >= AI_PILOT_PARK_THRESHOLD (0.9)` simultaneously
and raised `ai_pilot_parked_active`/the rising edge, with nobody's AI actually flying.

### Hypothesis

`run_ai_pilot_wheel`'s seat gate (`ai_pilot_update_seat()` then
`ai_pilot_park_rising(ai_pilot_parked_active, in_operator_seat and stick_park or nil)`) reads the
camera-derived seat and arg 852 in the same frame with no settling. The camera flips to the
operator seat the instant the player presses the seat-change key, but arg 852's un-stow animation
(driven by the DCS cockpit model, not by this code) lags behind by up to ~0.3 s. During that lag
the seat reads "operator" (true) while 852 still reads "stowed" (true) for reasons that have
nothing to do with the AI flying -- a transient, not a real park. Root cause: no settle delay
between a seat *change* and trusting arg 852's value against it.

### Evidence

- `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, "Flight 8": the exact
  camera-seat/852 timeline quoted above, 852 crossing from 0.963 to 0.624 inside 94 ms, consistent
  with the ~0.3 s stow animation already documented at `AI_PILOT_REFERENCE_TOGGLE_DELAY_S`'s
  neighbourhood in the file and at `SEAT_BOUNDARY_FWD_M`'s own comment.
- `.claude/agent-memory/reviewer/feedback_test_the_reverse_direction_not_just_the_reported_one.md`:
  an earlier pass (`fix/ai-wheel-pilot-seat-gate`) had already flagged that the pilot-to-operator
  direction produces a transient false reading absorbed only incidentally by the pre-existing
  0.5 s reference-toggle delay (`AI_PILOT_REFERENCE_TOGGLE_DELAY_S`) -- i.e. the rising edge still
  fired, `ai_pilot_parked_active` still went briefly `true`, and only the *press* was prevented
  because unpark (seat still reads "operator" is not what stops it -- the animation finishing
  first, before the 0.5 s reference-toggle delay elapsed, is) happened to land before the blind
  reference toggle was due. That is exactly the "false for a few frames" symptom the user reported,
  demonstrated as a pre-fix test (`test_entering_operator_seat_with_stick_still_stowed_presses_nothing`,
  before this change): `stage_at_edge == "toggling_reference"` right after the seat switch, i.e. the
  rising edge did fire.
- Reproduced in the project's own Lua harness (`aircraft-layer/tests/test_ai_pilot_wheel_lua.py`,
  new `test_seat_swap_settle_absorbs_flight8_unstow_animation`): feeding the flight 8 frame
  sequence through `run_ai_pilot_wheel` with the fix in place shows `ai_pilot_parked_active` and
  `ai_pilot_takeover.stage` both staying `nil`/`false` throughout the animation -- no edge at all.

### Fix Applied

`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`:

- New constant `AI_PILOT_SEAT_CHANGE_SETTLE_S = 0.5` (named, commented, citing flight 8 -- Lua has
  no `tuning.py` equivalent in this subproject, root `CLAUDE.md` "Behaviour-affecting constants";
  noted as such rather than improvising a second mechanism). 0.5 s covers the measured ~0.3 s
  animation with margin, matching the reasoning already used for the existing
  `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` (also 0.5 s, also a pilot-quoted "half second").
- New module-level local `ai_pilot_seat_settle_until_t`, reset in `on_stop` (a new mission starts
  with no settle in progress, same as `ai_pilot_player_seat`/`ai_pilot_cam_fwd_m`).
- `ai_pilot_update_seat(t)` now takes the model time and arms the settle window
  (`ai_pilot_seat_settle_until_t = t + AI_PILOT_SEAT_CHANGE_SETTLE_S`) the frame it sees the seat
  cross from a known, *different* seat into `"operator"`. A first-ever reading (previous seat
  `nil`) is not a swap and arms nothing -- it would otherwise delay trusting arg 852 for 0.5 s on
  every mission start for no real transient to absorb.
- `run_ai_pilot_wheel` now calls `ai_pilot_update_seat(t)`, then: while `in_operator_seat` is true
  *and* the settle window is still open, `ai_pilot_parked_active` is held at its previous value and
  no rising edge is produced; once the window closes (or the player is not in the operator seat at
  all), the real value is used exactly as before. Holding at the previous value is correct because
  the previous value, while the player was in the pilot seat, was always forced `false` by the
  existing seat gate -- so holding it keeps the belief correctly "not parked" through the unstow
  animation, then lets the real reading settle the question once the transient has had time to
  resolve.

**Operator -> pilot direction, decided deliberately unchanged:** the settle check is gated on
`in_operator_seat` being *true*. The moment the camera leaves the operator seat,
`in_operator_seat` is `false`, so `settling` is `false` regardless of any still-open settle window,
and the pre-existing immediate behaviour (`in_operator_seat and stick_park or nil` forces the
reading to `nil`, unparking the same frame) applies exactly as before. This is correct, not merely
harmless: that direction has no transient to absorb (852 is never even read in the pilot seat, the
seat gate forces it out), and delaying the unpark would hold a stale "parked" belief -- continuing
the takeover-correction/goal presses -- for up to 0.5 s after the player physically has the pilot
stick back, which is actively worse than the bug being fixed. This also means a player who taps
back to the pilot seat *during* a still-open settle window (hopping operator -> pilot inside the
0.5 s) gets the immediate, correct `false` rather than the held value, because `in_operator_seat`
flips to `false` first.

**Park changes with no seat change (Request Aircraft Control key) are unaffected**: the settle
window is armed only on a detected seat *transition*; pressing the key while the camera does not
move never arms it, so `ai_pilot_park_rising` runs immediately exactly as before. Verified by
`test_request_control_key_with_no_seat_change_is_immediate`.

### Verification

- `luac5.1 -p aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` -- passes.
- `GETGLOBAL` audit (`luac5.1 -l -p ... | grep -oE 'GETGLOBAL.*; [A-Za-z_]+' | awk '{print $NF}' | sort -u`)
  -- every name is a genuine DCS API, Lua stdlib, or a `core.lua`-shared global
  (`client`, `debug_log`, `extract_json_*`, `fmt_num_or_null`, `json_escape_string`,
  `WHEEL_CENTER_BUTTON`, `WHEEL_MENU_BUTTON`); no stray reference to the new names.
- `aircraft-layer/.venv/bin/ruff format --check src tests` -- 81 files already formatted.
- `aircraft-layer/.venv/bin/ruff check src tests` -- all checks passed.
- `cd aircraft-layer && aircraft-layer/.venv/bin/mypy src` -- success, no issues, 27 source files.
- `aircraft-layer/.venv/bin/pytest tests -q` -- 884 passed (full suite, including the updated and
  three new tests in `test_ai_pilot_wheel_lua.py`):
  - `test_entering_operator_seat_with_stick_still_stowed_presses_nothing` (updated): the pre-fix
    behaviour was a real rising edge absorbed only by luck/timing; post-fix, no edge occurs at all.
  - `test_seat_swap_settle_absorbs_flight8_unstow_animation` (new): the exact flight 8 frame
    sequence -- no park edge anywhere in it, nor once the settle window itself has elapsed with the
    player still flying.
  - `test_automatic_handover_parks_after_the_settle_window` (new): 852 stays stowed through the
    whole settle window (DCS's automatic-handover setting) -- the rising edge fires once the delay
    elapses, never during it.
  - `test_request_control_key_with_no_seat_change_is_immediate` (new): no camera move -- immediate
    rising edge, unchanged.
  - The pre-existing reverse-direction tests (`test_switch_to_pilot_seat_mid_hold_releases_without_menu_tap`,
    `test_goal_hold_releases_without_new_press_on_switch_to_pilot_seat`) continue to pass unchanged,
    confirming the operator -> pilot immediate-unpark behaviour was not altered.

**User's direction, verbatim (2026-11-18), the specification this fix implements:**

> "The false park signal -> need a small delay then. The AI overlay is off since I've not pressed
> the 'request control' key. There's two settings in the DCS Mi-24 for AI handover. Eihter AI takes
> control immediately on jump to copilot seat or it only takes control when player presses the
> 'request control' key. I have it on setting where I explicitly set AI control, but it is possible
> that the setting is on automatic control. Therefore, allow that inial small delay so that the
> control either unparks or remains parked, then read state and that determines whether AI has
> controls and therefore if Petrovich has controls."
