# Review: BL-16 LV-1 debug pass, 2026-11-24 (pedal-sign fix)

Reviewed: `844213f1` (fix) + `d0b4d6cc` (debugger memory) on top of `74c1060b`, on
`feature/bl16-lift-vector-law`. Full read of the diff, `debug-2026-11-24.md`, the two research
notes, and `plans/flight-lift-vector/plan.md`'s section F.

## Summary

The diagnosis itself is sound and well-evidenced: "positive pedal command is physically LEFT, not
right" is established from two genuinely independent facts (the 2026-11-20 calibration's solid,
isolated-input measurement, and this sortie's direct pilot observation), not re-derived from the
same weak correlation that caused the bug — exactly what the new debugger memory
(`feedback_closed_loop_sign_needs_physical_observation.md`) says to check for. The new toy-plant
test (`TestBallCentringPedalSign`) is independently grounded in that same calibration fact
(`K_PHYS > 0` because left/positive-command moves the ball right), not circular, and I confirmed by
mutation that reverting `k_ball_pedal` to `+0.3` makes both new tests fail exactly as claimed.

**But the fix is incomplete.** Flipping the three gains and swapping the two limit magnitudes
correctly fixes the ball-centring loop itself, but the collective-near-pedal-limit *guard*
(`law_update`, the `if state.t_y >= (profile.pedal_limit_positive - profile.pedal_near_limit_margin)
then` line) was not updated to match the new meaning of "scarce side," and no test exercises it at
all — the exact failure mode the task brief flagged as the main risk ("a flip that misses one
consumer").

## Required Fixes

- **The collective-rate-near-pedal-limit guard now protects the wrong side.** In
  `flight_control.lua`'s `law_update` (the section computing `u_c_rate`, just above the Section F
  pedal block):

  ```lua
  if u_c_rate > 0.0 then
      if state.t_y >= (profile.pedal_limit_positive - profile.pedal_near_limit_margin) then
          u_c_rate = math.min(u_c_rate, profile.collective_rate_cap_near_pedal_limit)
      end
      ...
  ```

  Before this fix, `pedal_limit_positive` (`0.5`) *was* the scarce/right side, and increasing
  collective (`u_c_rate > 0`) pushed `t_y` positive via `k_pedal_from_collective_rate *
  u_c_rate * rotor_dir` with `rotor_dir = +1` — the guard checked the side the torque
  feed-forward actually pushed toward. After this fix, `rotor_dir = -1`, so the same `u_c_rate >
  0.0` branch now pushes `d_t_y` **negative** — toward `pedal_limit_negative` (`-0.5`, the new
  scarce side) — but the guard still checks proximity to `pedal_limit_positive` (now `1.0`, the
  new *generous* side). Plan's own stated intent (`plan.md` section F: "the asymmetric pedal
  limits stay ... and a collective increase is still rate-capped near the right limit") is
  violated: the cap no longer engages near the right/scarce limit at all, and instead can engage
  near the abundant left limit, where it is not needed.

  **Confirmed by direct mutation** (toy driver against the real law, not just read): with `t_y =
  -0.42` (0.08 inside the new scarce limit's `pedal_near_limit_margin = 0.1`) and a large positive
  collective demand, `u_c_rate` comes back uncapped (`1.56`, not clamped to
  `collective_rate_cap_near_pedal_limit = 0.3`) and `t_y` moves *further* into the scarce limit
  the same frame. With `t_y = 0.92` (near the new abundant limit, physically the opposite side
  from where the torque feed-forward pushes), the cap *does* engage (`u_c_rate` clamped to
  `0.3`) — i.e. the guard now fires on the side that doesn't need it and stays silent on the side
  that does.

  Fix: either swap which limit the guard checks (`pedal_limit_negative +
  profile.pedal_near_limit_margin`, with the comparison direction flipped to `<=`), or — more
  robust against a future sign change — derive the side from the actual direction
  `k_pedal_from_collective_rate * rotor_dir` pushes rather than hard-coding
  `pedal_limit_positive`. This is player-facing correctness (root `CLAUDE.md`'s "Physical/DCS
  limits respected in code" review item) on a guard whose whole job is to keep collective demand
  from driving pedal into its own saturation — currently it does the opposite of its stated job.

- **Add regression coverage for this guard**, in whichever direction the fix above lands — e.g. a
  toy-plant test that starts `t_y` near `pedal_limit_negative` with `collective_enabled = true` and
  a large positive `u_c_rate` demand, and asserts the rate is capped. Neither test file (`test_
  flight_control_law.py` nor `test_flight_control_lua.py`) exercises
  `collective_rate_cap_near_pedal_limit` at all today, before or after this fix — confirmed by
  grep. This is the same test-gap class the debug pass itself found and fixed for `k_ball_pedal`
  (no test ever drove `measured.ball` away from centre); this guard has the identical gap and was
  missed because the debug pass's own "which term dominated" analysis correctly focused on the
  three *gains*, not on this unrelated guard a few lines above Section F.

## Optional Refinements

- `flight_profile.lua`'s comment for `rotor_dir` states "more collective -> more right pedal on
  the Mi-24P" as flat narrative, with the caveat that this is an unverified physical assumption
  living only in `debug-2026-11-24.md`'s "What remains unproven" section, not beside the claim
  itself. Not a regression (the pre-fix comment carried the same lack of caveat), and the project
  invariant is satisfied — the open question *is* recorded in `research`-adjacent form — but a
  one-line pointer from the comment to that section would save a future reader from re-treating it
  as settled. (Optional.)
- `body-layer/ROADMAP/BL-16.md`'s still-"Open" bullet on ball-centring pedal states the pre-fix
  claim ("positive pedal command = right" "can be settled from DCS's yaw-rate sign convention
  rather than guessed") as the open item's own framing, now known wrong and superseded by this
  debug pass. Not part of this diff and not blocking, but worth a short superseded-marker next
  time that roadmap entry is touched, per the project's "supersession is marked, not deleted"
  convention. (Optional.)
- The new trace fields (`format_trace_line`'s 21 new placeholders) have no direct test coverage of
  their own (field-count match verified by hand and by `luac5.1 -p` + the full suite passing, not
  by a dedicated test). Acceptable as-is: this is a diagnostic/testing aid, not normal-flight
  behaviour, and the existing posture for `fc_debug_estimator_sample_count` is the same. (Optional,
  not required.)

## Checklist evidence

- **Toy-plant sign test independence**: confirmed — `K_PHYS` in the `_BALL_CENTRING_DRIVER` is
  fixed from the calibration fact (left pedal moves ball right), not from the law's own gain sign.
  Mutation-reverted `k_ball_pedal` to `+0.3`/`rotor_dir` to `1.0` and reran
  `TestBallCentringPedalSign`: both tests fail (diverge past their starting error) as the debug
  report claims, then restored cleanly (`git status --porcelain` empty on that file afterward).
- **Every pedal-domain consumer**, grepped across `flight_control.lua` and the whole
  `dcs-export/` tree for `t_y`, `pedal`, `rotor_dir`, `pedal_limit`, `SIGN.pedals`: `SIGN.pedals`
  (command = `-arg`) correctly untouched (never in question); `law_outputs`'s `pedals` output and
  the anti-windup clamp at `(state.t_y >= profile.pedal_limit_positive and d_t_y > 0.0) or (state.t_y
  <= profile.pedal_limit_negative and d_t_y < 0.0)` are symmetric over both limits and correct as
  written; no hover/mode-2 pedal code exists yet (LV-1 is forward-flight-only, confirmed against
  `aircraft-layer/CLAUDE.md`); `ai_pilot_wheel.lua`'s `pedals_park`/arg 952 is an unrelated
  park-detection read, no sign assumption. The one consumer this flip missed is the collective-
  near-pedal-limit guard above.
- **Physical `rotor_dir` reasoning**: correctly flagged by the debugger itself as unproven
  ("What remains unproven"), not asserted as settled fact beyond that. I did not find an
  independent source in this repo for Mi-24P main-rotor rotation sense to confirm or contradict the
  "more collective needs more right pedal" claim either way — this matches the debug pass's own
  stated uncertainty, so no new invariant violation.
- **Trace instrumentation**: `dbg_*` fields are five plain-number assignments per `law_update` call
  (30 Hz, `law_hz`), not per DCS frame; `format_trace_line`'s extra work (`string.format` with the
  new fields) is gated behind `FLIGHT_TRACE_ENABLED` as before. No new Lua globals — `luac5.1 -l -p`
  + the `GETGLOBAL` leak check lists only genuine DCS APIs, stdlib, and the project's own existing
  dofile-composed module names (unchanged list, no new leak). 21 format placeholders match 21
  arguments, by direct count.
- **Checks run this session** (worktree had no venv; symlinked `aircraft-layer/.venv` from the main
  checkout rather than recreating it):
  - `ruff format --check aircraft-layer/src aircraft-layer/tests` — clean (90 files).
  - `ruff check aircraft-layer/src aircraft-layer/tests` — clean.
  - `cd aircraft-layer && .venv/bin/mypy src` — clean, 29 files (no `.py` production code touched
    by this fix).
  - `luac5.1 -p` on every `.lua` file in `dcs-export/` and `dcs-export/Petrobrain/` — clean.
  - `.claude/scripts/fast-tests.sh aircraft-layer` — smoke + 52 targeted files, 998 passed.
  - Full `pytest aircraft-layer/tests -q` not re-run separately; the debug report's own full-suite
    run (1144 passed) plus this session's fast-tests pass is treated as sufficient given the
    required-fix item below will need its own follow-up pass anyway.

## Verdict

**CHANGES REQUIRED** — the pedal-sign fix itself and its new test are correct and well-evidenced,
but the collective-near-pedal-limit guard is a second consumer of the same sign convention that
was missed, and it now silently fails to protect the limit it exists to protect (while guarding
the wrong, abundant side instead). This is a safety-relevant regression on a guard with zero
existing test coverage, not a cosmetic miss — recommend routing the fix through Implementer →
Reviewer (re-review of the fix) per the standing re-entry rule for review-requested changes, then
back to this plan's own test-flight queue.

## Review Confidence

Full read of the diff, the debug report, both cited research notes, and the plan's section F.
Verified the toy-plant test's independence and the guard regression by direct mutation against the
real Lua law (not just by reading), using the existing test harness's `_run`/`_measured` helpers
plus a standalone driver. Did not independently verify the `rotor_dir` physical claim itself (main
rotor rotation sense) — no source for it exists in this repo, and the debug pass already discloses
it as open rather than settled, so there is nothing further for this review to check there.
