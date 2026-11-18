### Review Summary

Reviewed `fix/apw-seat-swap-settle` at `4c1224b0` (base `main` `797f53db`), checked out at
`/Users/sg/Code/DCS-petrobrain-apw-settle`. Bug-fix path (Debugger → Reviewer), no plan.md with
`U<n>` decisions — `plans/apw-seat-swap-settle/debug.md` is the specification, read in full.

Fix: `ai_pilot_wheel.lua`'s pilot→operator seat gate now holds `ai_pilot_parked_active` at its
pre-switch value for a 0.5 s settle window (`AI_PILOT_SEAT_CHANGE_SETTLE_S`) armed only on entry
into the operator seat, absorbing arg 852's ~0.3 s un-stow animation lag (flight 8 measurement).
The operator→pilot direction is deliberately left immediate — no settle window, matching the
pre-existing unconditional `in_operator_seat and stick_park or nil` unpark.

**Correctness against spec.** The user's verbatim direction ("allow that initial small delay so
that the control either unparks or remains parked, then read state...") is satisfied: during the
window the flag holds its prior value (not an invented one), and once the window closes the real
arg 852 reading is trusted — covering both outcomes the user named (settle-and-unpark on real
control, settle-and-park on DCS automatic handover). Verified `test_automatic_handover_parks_
after_the_settle_window` exercises exactly the automatic-handover case the user flagged as the
reason this needs to be a read-after-delay rather than a blanket "ignore the first 0.5 s."

**Judging the asymmetric (operator→pilot immediate) call.** Correct, not merely expedient. Arg 852
is only meaningful while the camera is in the operator seat — the seat gate already forces it to
`nil` the instant `in_operator_seat` goes false, so there is no sensor lag on that side to absorb
(852 is never read as the player retakes the pilot seat). Delaying the unpark would hold a stale
"parked" belief — continuing takeover-correction presses — for up to 0.5 s after the player
physically has the stick back, which is strictly worse than the bug being fixed. The debug report
and the new agent-memory file both state this reasoning plainly, and the existing reverse-direction
tests (`test_switch_to_pilot_seat_mid_hold_releases_without_menu_tap`,
`test_goal_hold_releases_without_new_press_on_switch_to_pilot_seat`) continue to pass unchanged,
confirming no regression there. This is also the exact gap `.claude/agent-memory/reviewer/
feedback_test_the_reverse_direction_not_just_the_reported_one.md` warns about — properly addressed
here, not repeated.

**Every consumer reads the settled flag.** Grepped every read of `ai_pilot_parked_active`,
`in_operator_seat`, `ai_pilot_player_seat`, `ai_pilot_seat_settle_until_t` in the file. The settle
window's effect is confined to the single assignment at the seat gate (`ai_pilot_parked_active =
now_parked`, line ~1132); every downstream consumer (`update_ai_pilot_wheel_overlay`'s `if not
ai_pilot_parked_active`, the status-push JSON field) reads that same settled variable, never
`stick_park`/`in_operator_seat` directly for park state. `in_operator_seat` itself is read
separately (menu-close gating, stick-park gating) for seat *location*, which is orthogonal to park
state and correctly left unaffected by the settle window (e.g. the menu-close-on-seat-leave logic
still fires the instant the camera leaves, as it should).

**No DCS-truth leak / no omniscience.** The settle window holds a *belief* (the previous reading)
rather than reading ahead or inventing a value — consistent with "code owns facts, no omniscience."

**Co-moving state consistency.** `ai_pilot_seat_settle_until_t` is reset in `on_stop` alongside the
other seat-derived locals it is co-moving with (`ai_pilot_player_seat`, `ai_pilot_cam_fwd_m`) — a
new mission starts with no settle in progress, matching the existing convention.

**Interaction with status push / P1/P2/HVRT.** No interaction problem found. The status push reads
`ai_pilot_parked_active` and `ai_pilot_player_seat` independently (diagnostic), both already
correct values at push time. P1/P2 release logic and the HVRT hold-release both run unconditionally
in the `not now_parked` branch exactly as before — the settle window changes only when `now_parked`
*becomes* true/false, not how the unpark branch behaves once it is false, so no new interaction
surface.

**Mutation-checked the main new test.** `test_seat_swap_settle_absorbs_flight8_unstow_animation`
(plus the updated `test_entering_operator_seat_with_stick_still_stowed_presses_nothing` and the new
`test_automatic_handover_parks_after_the_settle_window`) were checked by forcing `settling` to
always `false` (simulating the pre-fix code path) in the checked-out tree and re-running just the
seat-gate tests: 3 of 4 failed exactly as expected (the no-seat-change test correctly stayed green,
since it never touches the settle path). Change reverted immediately after; `git status` on that
tree confirmed clean before and after. This demonstrates the tests actually pin the new behaviour,
not merely exercise it.

**Comment pruning.** `git diff` of the lua file shows no deleted `-` lines except the two one-line
function signatures/bodies that were directly extended in place (`ai_pilot_update_seat()` →
`ai_pilot_update_seat(t)`, the inline `park_rising` call wrapped in the new `if settling`
branch) — no dated fact, verbatim quote, or edge-case description was dropped. The new `#:`-style
comment on `AI_PILOT_SEAT_CHANGE_SETTLE_S` correctly notes aircraft-layer has no `tuning.py`
equivalent, matching root `CLAUDE.md`'s "outside body-layer the loader does not exist" exemption —
no tuning-mechanism gap here.

**Merge overlap with `fix/apw-status-json-quotes`.** That branch (base `main` `797f53db`, same as
this one) touches only the `text_or_null` local function's body inside `push_ai_pilot_wheel_state`
(line ~1372–1378 in the pre-fix file), fixing a double-quoting bug unrelated to the seat gate. No
line-range overlap with this fix's changes (constant declaration ~line 102, module locals ~line
218, `ai_pilot_update_seat` ~line 615, the seat-gate block in `run_ai_pilot_wheel` ~line 1110–1132).
The two branches will merge into `main` without conflict.

**Scope.** Confined to `ai_pilot_wheel.lua`, its test file, `plans/apw-seat-swap-settle/debug.md`,
and one debugger agent-memory file — matches the bug's actual surface, no drift.

### Required Fixes

None.

### Optional Refinements

- None found — the fix is narrowly scoped, the asymmetry is justified and tested from both
  directions, and the settle-window state is fully co-moving with the pre-existing seat-tracking
  locals.

### Verdict
APPROVED

### Review Confidence
Full read — plan/debug report, full diff (lua + tests + agent-memory file), live mutation check of
the three affected new/updated tests, grep of every consumer of the touched state, and a
merge-overlap check against the sibling branch. Checks run from the checked-out branch tree using
the main checkout's venv tools (`ruff format --check`, `ruff check`, `mypy src`, `pytest -q`
884 passed, `luac5.1 -p`) — all green.
