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

---

### Re-review (2026-11-27)

Base: `fix/mode2-recovery-wake` tip `ae53dc2c` — reviewed on a local branch `b139-rereview` cut
from that exact sha (the worktree named in the dispatch, `DCS-petrobrain-recoverywake`, was not
touched). Diff against the reviewed commit `d998bfe6` is exactly one file,
`aircraft-layer/tests/test_ai_pilot_wheel_lua.py`, adding `TestAiPilotGoalWakeKick` (5 tests, +208
lines, no production code touched).

**Coverage against the four scenario groups the required fix asked for** — all four present, plus
one the fix didn't explicitly ask for but the debug report's edge-case list implies:

- (a) altitude, matching value, `wake=true` → forces DOWN, then converges —
  `test_altitude_wake_forces_a_down_hold_then_converges_to_the_exact_target`. Covered, including
  the hand-off once `ordinary_dir` becomes non-nil.
- (b) DOWN produces no change within `AI_PILOT_WAKE_KICK_TIMEOUT_S` → falls back to UP → both fail
  → gives up —  `test_altitude_wake_falls_back_to_up_then_gives_up_without_holding_forever`.
  Covered, including the mid-timeout "still held" assertion.
- (c) the same for the speed tap variant, exactly-once-per-direction —
  `test_speed_wake_taps_down_once_then_up_once_not_once_per_tick`. Covered, using `press_log` to
  distinguish "tapped once" from "tapped every tick."
- (d) `wake=false` at a matching value still settles with zero presses —
  `test_altitude_wake_false_at_target_presses_nothing`. Covered.
- Bonus: `test_altitude_wake_already_off_target_skips_the_kick_entirely` — the *ordinary* case
  (never a forced DOWN when genuinely off-target), deliberately using a below-target value so a
  wrongly-forced DOWN is distinguishable from the correct UP. Good choice of fixture value; this
  is exactly the kind of case a lazier test (matching value only) would have missed.

**Verified by running the tests, not just reading them.** `pytest -k WakeKick` → 5 passed. Full
`aircraft-layer` suite → 1078 passed (1073 before + 5 new), `ruff format --check`, `ruff check`,
`mypy src` (strict) all clean, `luac5.1 -p` clean on every `.lua` file in `dcs-export/`.

**Verified by mutation, per the standing "verify by mutation" habit** — three mutations against
`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`, each reverted immediately after
(confirmed byte-identical via `diff` against a pre-mutation backup; `git status --porcelain` clean
throughout):

1. Disabled the "already off target → skip the kick" early return in
   `ai_pilot_wake_kick_direction_hold` (force DOWN unconditionally). Caught by 2 tests:
   `test_altitude_wake_forces_a_down_hold_then_converges_to_the_exact_target` and
   `test_altitude_wake_already_off_target_skips_the_kick_entirely`.
2. Removed the give-up branch in the same function (holds UP forever instead of releasing). Caught
   by `test_altitude_wake_falls_back_to_up_then_gives_up_without_holding_forever` (asserts
   `hold_cmd_final == "nil"`).
3. Removed the `"wait"` state in `ai_pilot_wake_kick_direction_tap` (re-taps every tick instead of
   waiting one `AI_PILOT_WAKE_KICK_TIMEOUT_S` window). Caught by
   `test_speed_wake_taps_down_once_then_up_once_not_once_per_tick` (the `press_log` string gains a
   duplicate tap).

All three mutations were caught by exactly the test the scenario mapping above predicted, and no
mutation produced a false pass. The required fix is satisfied: the wake-kick mechanism itself —
DOWN-then-UP fallback, give-up, the off-target skip, and the discrete-tap-not-every-tick
distinction — is now exercised by real Lua execution, not constant-parity checks.

**No new findings.** Nothing else in the diff to flag — it is additive test-only, no production
Lua or Python touched, no new tuning constant, no new comment to prune, no new float parsed from
outside the process.

#### Verdict (re-review)

**APPROVED.** The required fix from the first pass is closed. BL-B140 was never in question. Ready
for DoD; branch to name in any test card remains `fix/mode2-recovery-wake`, still `#needs-flight`
on both `BL-B139.md` and `BL-B140.md` per the original review (no Windows/DCS reachable from this
environment).

#### Review Confidence (re-review)

Full read of the diff. Ran the real test suite (not just inspected it), ran the full
`aircraft-layer` format/lint/type/test commands, and ran three targeted mutations against the
actual Lua implementation to confirm each test fails for the reason its docstring claims rather
than trivially. Did not re-review BL-B140 or the rest of the already-approved production diff —
out of scope for this re-review, which was dispatched specifically against the one test-file diff.
