### Review Summary

Branch `fix/mode2-recovery-wake` (`f3bb71c3`, fast-forwarded cleanly from `c0d8af86`, strict
ancestor, clean tree — no `mode2-review` branch was needed). Two debugger-style fixes against
`docs/acceptance/2026-11-27-mode2-recovery-feedback.md`:

1. **BL-B139** — a recovery-only `wake` flag on `POST /command/ai_pilot_goal`, forcing a one-step
   kick (DOWN, fallback UP, then give up) in `Export.lua`'s altitude/speed goal ticks when the
   displayed value already equals the recovery target, so ED's AI pilot actually reacts.
2. **BL-B140** — `nearest_speed_step`'s `>=` against the top real step changed to `>`, so "speed
   250" resolves to 250, not MAX.

Both are scoped correctly (recovery-only for BL-B139 via the sticky `.wake` field keyed off
`ParkedFlightState.align_phase == "recovering"`; ordinary voice goals send `wake=False` and are
provably untouched by `test_an_ordinary_goal_sends_wake_false`). Altitude-then-speed order is
unchanged (Decision 26's `seed_recovery_goal` still seeds `("altitude", "speed")`). All three
`write_ai_pilot_goal` call sites in `body.py` pass the same per-poll `wake` value — checked by
grepping the call sites directly, not the file list, per the standing "parallel treatment" rule.
Wire validation is a strict bool, default `False`, same posture as every other field on this
endpoint; no finite-float concern (not a float field). `goal_seq`/`param`-change bookkeeping
correctly resets the Lua-side wake-kick fields on a param transition (altitude → speed), and
`wake_done_seq` is compared per-`goal_seq` so the promoted speed goal gets its own kick decision.
Interruption paths (break, fresh voice command, takeover, HVRT translate) all route through the
pre-existing `ai_pilot_goal_release_hold()`/param-change reset, which now also clears the
wake-kick fields — reviewed in context, looks correct.

BL-B140's fix is minimal and correct; every caller of `nearest_speed_step`
(`set_parked_speed`, `step_speed`, and `crew_console.set_speed`/`step_speed`) was grepped and
traced — all read the corrected boundary consistently, including the "step down from 250" fix
the commit message claims as a side effect (verified by tracing `step_speed`'s ladder-index
logic, not just taking the claim).

Checks run (both subprojects, `.venv/bin/{ruff,mypy,pytest}` from the main checkout, since this
worktree has no venvs of its own):
- `aircraft-layer`: `ruff format --check`, `ruff check`, `cd aircraft-layer && mypy src` — all
  clean. Full `pytest tests -q -n auto` — **1073 passed**. `luac5.1 -p` on the modified Lua file —
  clean.
- `body-layer`: `ruff format --check`, `ruff check`, `cd body-layer && mypy src` — all clean. Full
  `pytest tests -q -n auto` — **3813 passed, 4 xfailed** (pre-existing xfails, unrelated to this
  branch).

### Required Fixes

- **The wake-kick mechanism itself — the actual new logic that fixes BL-B139 — has no behavioural
  test run against a real Lua interpreter.** This project has an established pattern for exactly
  this (`TestAiPilotGoalTick` in `test_ai_pilot_wheel_lua.py`, e.g.
  `test_altitude_goal_does_not_settle_short_of_the_exact_target`,
  `test_speed_goal_taps_once_per_tick_until_settled`): extract the real function, drive it through
  `handle_ai_pilot_goal_command` + repeated `ai_pilot_goal_tick(t)` calls, and assert on
  `press_log`/`hold_cmd`/`progress`. The diff adds two new functions
  (`ai_pilot_wake_kick_direction_hold`/`_tap`) with several non-trivial branches — DOWN-then-UP
  fallback, give-up after both fail, "already off target" skip, exactly-one-tap-then-wait for
  speed — and wires them into both goal ticks. All of the test changes in
  `test_ai_pilot_wheel_lua.py` are constant-parity/closure-presence checks (confirming the
  function and constant exist), not a single assertion that a `wake=true` message with a
  matching displayed value actually produces a DOWN hold, that the hold releases once the display
  has moved, that a stuck-at-the-floor wheel falls back to UP, or that both failing gives up
  without holding a button forever. This is exactly the class of code this project's own debug
  report (`plans/flight-control/debug-bl-b139.md`, "Edge cases from the task brief") lists as
  deliberately handled — and none of those edge cases are exercised by anything that runs. Add at
  least: (a) altitude, matching value, wake=true → first tick holds DOWN, not `nil`; after the
  displayed value changes, convergence to the exact target as before; (b) altitude, DOWN produces
  no change within `AI_PILOT_WAKE_KICK_TIMEOUT_S` → falls back to UP; both fail → gives up
  (`progress` reaches `"settled"`/`"pressing"` as appropriate, no held button past the timeout);
  (c) the same three for the speed tap variant, including that it taps **exactly once** per
  forced direction, not once per tick; (d) `wake=false` (or absent) with a matching value still
  settles with zero presses, unchanged from before this branch.

### Optional Refinements

- `AI_PILOT_WAKE_KICK_TIMEOUT_S = 1.5` is a plain Lua constant with no tuning-mechanism note. This
  matches existing practice in this same file (`MODE_BLOCKED_RETRY_S`, `AI_PILOT_GOAL_SLICE_S`,
  `HVRT_TRANSLATE_MAX_HOLD_S` are the same shape, untunable, outside body-layer where the loader
  doesn't exist), so not a required fix — just noting it was checked.
- No live-flight verification of either fix is possible from this environment (no Windows/DCS
  reachable) — `#needs-flight` is correctly on both `BL-B139.md` and `BL-B140.md`, and the branch
  name is what the user needs to fly: `fix/mode2-recovery-wake`.

### Verdict

NEEDS REVISION — one required fix (Lua-side behavioural test coverage for the wake-kick
mechanism). BL-B140's fix is simple, correct, and adequately tested as-is; it does not block on
its own, but since both land on the same branch/commit pair reviewed together, the branch overall
needs the BL-B139 test gap closed before DoD.

### Review Confidence

Full read of both commits' diffs, the acceptance doc, both ROADMAP entries, the debug report, and
the relevant sections of `plans/flight-control/plan.md` (Decision 26, the align/recovery state
machine). Traced every `write_ai_pilot_goal`/`nearest_speed_step` call site by hand rather than
trusting the file list or the commit message's own claims. Did not independently drive the Lua
functions by hand to confirm the required fix's premise beyond reading the existing test file's
structure and confirming (via `grep`) that no `wake`-specific assertion exists anywhere in
`test_ai_pilot_wheel_lua.py` — the test-gap finding is itself the kind of claim this role is
expected to verify by mutation/execution rather than reading, and a fuller pass would have written
the missing test and run it red-then-green rather than only locating its absence.
