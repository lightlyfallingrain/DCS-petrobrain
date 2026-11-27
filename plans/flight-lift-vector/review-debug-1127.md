### Review Summary

Reviewed `fix/bl16-flight-epoch-bound` @ `3ae73c48` (diff against `e7676235`), the debug fix for
the sixth re-fly's "deceleration leads to descent as well. Should maintain altitude" finding
(`docs/acceptance/2026-11-27-sortie-feedback.md`, `plans/flight-lift-vector/debug-2026-11-27.md`).

**Base note:** my worktree's HEAD (`c0d8af86`, housekeeping-merge tip of `main`) is not an ancestor
of `3ae73c48` — the fix branch diverged before that housekeeping merge, so a `--ff-only` merge was
not available. The commit itself is reachable in this repo's object store (shared `.git`), so I
reviewed it via `git diff`/`git show` against the two commit hashes and ran the touched subproject's
checks from a `git archive 3ae73c48` snapshot in scratch, per the task's fallback instructions. I did
not touch `/Users/sg/Code/DCS-petrobrain-epochfix` (where the branch is actually checked out).

**Mechanism.** The old "slowing down is always pitch back and also less collective" term biased
`c_dot_nominal` — a **rate**, folded into the integrator `state.u_c_i` every frame — so it
accumulated for the whole duration of a commanded deceleration (several seconds) with no bound,
pinning `u_c` at −1.00 and outracing the vertical loop's own `e_u` integrator. The fix moves it to a
bounded, value-level feed-forward nudge (`u_c_speed_give_ff`), recomputed fresh each frame from the
current (capped) `|a_f_d|`, added alongside `u_c_ff` the same way `u_c_ff` already is, with
`next_state.u_c_i` correctly backed out against `u_c_ff_total` so the nudge is never double-counted.
This is the right fix for the mechanism the debugger diagnosed (confirmed by mutation — see below) —
**but the committed test does not prove it holds under the gains that will actually fly**, which is
a required fix.

### Required Fixes

- **`TestDecelerationHoldsAltitude` proves the fix against a stale, pre-amendment speed-loop
  profile, not the shipped one, and the shipped-gain altitude loss is larger than the test's own
  asserted bound.** The test's local `_PROFILE` table (same one `TestSpeedChannelIsBrisk`'s own
  docstring documents as "the deliberate pre-amendment baseline") has `omega_speed = 0.15`,
  `speed_accel_cap_mps2 = 0.5`, `k_speed_error = 0.2`, `c_theta = 0.5` — all slower than the shipped
  `flight_profile.lua` values (`0.5`, `1.9`, `0.3`, `0.90` respectively). The debug report's own
  before/after table (−42.2 m → −9.3 m, "factor of ~4.5") and the committed assertion
  (`assert min_dev > -15.0`) are both computed on this slow profile.

  I re-ran the exact same toy-plant scenario (273→108 km/h decel, no altitude command, 20 s) with
  `PROFILE = flight_profile.PROFILES["Mi-24P"]` loaded directly via `dofile` (the same mechanism
  `TestAmendmentProductionValuesTogether` already uses for exactly this reason — review-debug-1125.md
  required fix 1, "no existing test ran the shipped values together"):

  | | min altitude deviation | final IAS (20 s) | max \|a_f_d\| |
  |---|---|---|---|
  | before fix, shipped gains | **−39.3 m** | 191.4 km/h | 1.97 |
  | after fix, shipped gains | **−19.3 m** | 188.9 km/h | 1.97 |
  | after fix, test's stale `_PROFILE` (committed) | −9.3 m | 224.7 km/h | — |

  The fix is real and in the right direction (≈2× less loss, not the claimed ≈4.5×), but under the
  gains that actually fly, this toy plant still loses **−19.3 m — outside the committed test's own
  "small band" bound of 15 m.** Extending the same run to 120 s shows the altitude *does* recover
  (overshoots to +4.85 m before settling), confirming there is a real `alt_goal_m` position
  reference behind this, not just a rate reference (answers the "is the dip recovered" question) —
  but the dip itself, under shipped gains, is larger than the committed test claims and the debug
  report's own improvement factor is overstated because it is benchmarked on the wrong profile.
  This is the exact failure mode `review-debug-1125.md` already named and fixed once
  (`TestAmendmentProductionValuesTogether`); this new test should have followed that precedent and
  didn't.

  **Fix:** add a shipped-gains variant of `TestDecelerationHoldsAltitude` (override
  `omega_speed`/`speed_accel_cap_mps2`/`k_speed_error`/`c_theta` to the shipped values in the driver,
  same pattern as `TestAmendmentProductionValuesTogether`), and either (a) tighten the fix further so
  it passes a realistic bound under those gains, or (b) if ~19–20 m in a simplified toy plant is
  judged acceptable pending the seventh re-fly, say so explicitly in the debug report and plan.md
  rather than leaving the only committed number describing a scenario that cannot occur in flight.
  Given the user's own routing instinct on this feature (re-fly before committing to a number), I'd
  lean toward re-flying with this fix and comparing against the trace rather than tuning blind
  against the toy plant a second time — recorded as a question for the user, not a unilateral call.

### Optional Refinements

- `test_altitude_deviation_stays_small_through_a_large_decel` alone does not catch a sign flip on
  `u_c_speed_give_ff` (mutated it to `+profile.k_collective_speed_give * capped_decel` and the test
  still passed, because adding collective during a decel only helps altitude). The class as a whole
  does catch it — `test_speed_give_nudge_still_reduces_collective_below_the_vertical_term_alone` goes
  red on the same mutation — so this is not a coverage gap, just worth noting for anyone reading the
  altitude test in isolation. (Optional — no action needed.)

### Checklist evidence

- **Mutation check (old rate-bias restored):** reverted `flight_control.lua` to the pre-fix
  `c_dot_nominal` bias (keeping the new `collective_speed_give_max_a_f_d_mps2` field unused, as it
  would be if someone reverted just the logic) and re-ran `TestDecelerationHoldsAltitude` —
  **goes red** (`assert -42.235772 > -15.0`), confirming the test is exercising real behaviour, not
  a tautology.
- **Sign-flip mutation:** see Optional Refinements above — caught by the class, not by the headline
  test alone.
- **Speed-change rate (Q2):** `flight_profile.lua`'s speed-loop fields (`omega_speed`,
  `speed_accel_cap_mps2`, `k_speed_error`, `c_theta`) are untouched by this diff — only the
  collective-channel speed-give term and its new cap changed. The accepted "decent rate, good" decel
  rate is unaffected by this fix, confirmed by the shipped-gains re-run above showing the same final
  IAS (~189–191 km/h) before and after.
- **Finite-float standing rule (Q5):** `collective_speed_give_max_a_f_d_mps2` is a Lua-authored
  profile literal compiled directly into `flight_profile.lua`, not a value crossing a wire/JSON/Hook
  boundary — the standing rule (`implementer.md`/`reviewer.md`, 2026-11-25) is explicitly scoped to
  values parsed from outside the process, so this constant is correctly exempt, same trust level
  every other loop constant in this file already has (the module's own header says so). No
  violation.
- **Comment pruning:** the section-E comment above `c_dot_nominal`/`u_c_candidate` and the
  `flight_profile.lua` comment above `k_collective_speed_give` were both updated, not deleted — the
  dated verbatim user quote ("Sortie 2026-11-20... Slowing down is always pitch back and also less
  collective") is preserved in both files; nothing durable was lost. The `next_state.u_c_i` comment
  was correctly extended to explain the `u_c_ff_total` bookkeeping. No boundary case moved into a
  test and vanished from a comment — n/a here, no such case existed before.
- **Plan ledger:** the 60 km/h left-yaw item the user routed to the slow-speed stage is recorded as
  a plan.md addition under the existing LV-3 bullet, with the user's verbatim words carried over —
  correctly deferred to a named stage, not dropped. Not a full Architect plan with `U<n>` ids, so I
  read this by hand rather than running the ledger script.
- **Scope fit:** confined to `flight_control.lua`/`flight_profile.lua` (aircraft-layer) plus tests
  and the debug/plan docs. No coordinate math, no DCS-install writes, no GIS provenance concerns —
  not applicable to this fix.
- **Tuning mechanism:** not applicable — aircraft-layer has no `tuning.py`-equivalent loader; the new
  constant is an ordinary Lua profile literal, correctly not routed through a mechanism that doesn't
  exist outside body-layer.
- **Checks, re-run from a clean `git archive 3ae73c48` snapshot** (`/Users/sg/Code/DCS-petrobrain/
  aircraft-layer/.venv/bin/{ruff,mypy,pytest}`, run from inside the snapshot's own `aircraft-layer/`):
  `ruff format --check` clean, `ruff check` clean, `mypy src` clean (29 files), full
  `pytest tests -q`: **1182 passed** — matches the debug report's own claimed numbers exactly.
- **`luac5.1`/Lua parse:** not independently re-run (no `luac5.1` on this machine; `luajit` ran the
  driver scripts above without syntax errors, which is the same evidence `test_file_parses_without_a
  _lua_interpreter_too` already carries in the suite).

### Verdict

NEEDS REVISION — one required fix (the altitude-hold test benchmarks against a stale, non-shipped
profile and understates the real altitude loss; under shipped gains the toy plant still loses ~19 m,
outside the test's own asserted bound). The mechanism/fix direction is correct and the project has
an established pattern for closing this exact gap (`TestAmendmentProductionValuesTogether`,
review-debug-1125.md). Recommend this re-enters the Debugger/Implementer loop: either tighten the
fix against shipped gains, or make an explicit, user-visible call that ~19–20 m in the toy plant is
acceptable pending the seventh re-fly — not a silent gap between what the test proves and what will
fly.

### Review Confidence

Full read of the diff, plan addition, debug report and sortie feedback. Verified empirically, not
just by reading: re-ran the toy-plant scenario against shipped `flight_profile.lua` values (before
and after the fix) and via two mutations (old rate-bias restored; sign flip) against the committed
test file, from a clean `git archive` snapshot with the actual aircraft-layer venv. Did not re-fly
the aircraft (not available to this role) and did not re-run `luac5.1` specifically (not installed
here; `luajit` parsing stood in for it, same as the suite's own fallback).
