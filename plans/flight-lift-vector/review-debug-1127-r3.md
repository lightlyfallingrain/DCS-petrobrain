### Review Summary

Re-review of the BL-16 LV-1 deceleration-altitude fix, rounds 1-3 (`plans/flight-lift-vector/
debug-2026-11-27.md`), against `7ab6191555f83d75016bc15494c35e10cf50b130` on
`fix/bl16-flight-epoch-bound`, diffed against the pre-fix baseline `e76762356a3540934a2d9bff7f880
4beb3ed6cc4`. My earlier pass (`review-debug-1127.md`) found round 1 proved its fix against a
stale, pre-amendment speed-loop profile rather than the shipped gains and sent back one required
fix. Round 2 re-ran the scenario on the shipped profile (via `dofile`), found the residual -19.3 m
dip traced to the retreating-blade-stall guard's own threshold, and round 3 corrected that
threshold itself (250 -> 335 km/h, re-based on the DCS V_NE table the user supplied) rather than
loosening the guard's mechanism.

**Base note:** my worktree's HEAD was not an ancestor of the target sha (worktree started on a
housekeeping-merge tip of `main`, the fix branch diverged earlier), so I created a local branch
`bl16-review-r3` directly at `7ab6191555f83d75016bc15494c35e10cf50b130` (same object store, no
network fetch needed) and reviewed from there, per the task's own fallback instruction. I did not
touch `/Users/sg/Code/DCS-petrobrain-epochfix`.

### Checked

1. **Round-1 required fix closed.** `TestDecelerationHoldsAltitude._run_decel_scenario_shipped`
   now loads `flight_profile.lua`'s actual `PROFILES["Mi-24P"]` wholesale via `dofile` — the same
   mechanism `TestAmendmentProductionValuesTogether` uses — rather than the test file's own slower
   `_PROFILE`. `test_shipped_gains_dip_is_bounded_by_the_blade_stall_guard_not_the_old_bug` and
   `..._fully_recovers_once_below_the_blade_stall_margin` both run against shipped gains.

2. **Everything gated on the moved threshold.** The only two places that read
   `retreating_blade_stall_ias_kmh`/`blade_stall_limited` in `flight_control.lua` are the flag's own
   computation (line 1039) and the single guard site (line 1118, caps a *rising* collective only,
   via `collective_rate_cap_near_blade_stall`). No second consumer. `collective_saturated`
   (line 1038) is computed but was already unused before this diff (confirmed against `e7676235`) —
   pre-existing, not introduced by this fix, out of scope here.
   `test_near_retreating_blade_stall_caps_a_rising_collective` was correctly moved from 320 km/h
   (old guard, margin to 230) to still exercise the guard at the new line (margin to 315) — checked
   the test asserts against the new threshold, not stale. Round 3's own comment in
   `flight_profile.lua` corrects a citation it had gotten backwards in round 2 (which direction
   raising collective moves rotor RPM near this envelope edge) against
   `aircraft-layer/research/2026-11-27-mi24p-rotor-engine-limits.md`'s "High side, new" paragraph —
   re-read that paragraph myself; the correction is accurate, and the comment is honest that no
   high-side rotor-overspeed guard is built (deferred to LV-2, not silently dropped).
   `body-layer/config/defaults.toml`'s rendered line for `RETREATING_BLADE_STALL_IAS_KMH`: the
   generator emits only the comment's first sentence ("at or above this IAS, the same
   collective-rate guard caps a further increase, to stay clear of retreating blade stall") —
   unchanged and still accurate, so nothing is lost there; `status: derived` (was `agreed-guess`)
   and `335.0` both correctly rendered, bounds `100.0 .. 400.0` still sensible for this field.

3. **Shipped-gain toy-plant numbers, 150->60 km/h decel and 150->250 km/h accel — not covered by
   any committed test, run directly against both commits:**

   | scenario | commit | min altitude dev | max altitude dev | time to converge | final IAS |
   |---|---|---|---|---|---|
   | decel 150->60 | `e7676235` (pre-fix) | **-41.3 m** | +9.0 m | 19.95 s | 59.25 km/h |
   | decel 150->60 | `7ab6191` (round 3) | **-4.4 m** | +3.3 m | 19.00 s | 59.34 km/h |
   | accel 150->250 | `e7676235` (pre-fix) | -3.0 m | +0.03 m | 20.40 s | 250.73 km/h |
   | accel 150->250 | `7ab6191` (round 3) | -0.2 m | +0.07 m | 20.40 s | 250.73 km/h |

   **The accepted speed-change rate is unchanged**: convergence time (20.40 s) and final speed
   (250.73 km/h) for the 150->250 acceleration are bit-identical between the two commits — the fix
   touches only the `a_f_d < 0.0` branch, and acceleration keeps `a_f_d >= 0.0` for nearly the whole
   run. The small altitude-dip difference on the accel scenario (-3.0 m -> -0.2 m) is a real,
   welcome side effect, not a regression: near convergence the plant briefly overshoots the target
   and `a_f_d` flips negative for a moment to correct it, which is enough to trip the old unbounded
   integrator bug for that brief window; the new bounded nudge handles it the same way it handles
   the main decel. It does not touch the accel channel's own dynamics.

   The 150->60 decel (the user's own named command speed from the sortie feedback, not just an
   arbitrary round number) shows the same order-of-magnitude improvement round 2/3 already measured
   on the 273->108 km/h scenario: -41.3 m -> -4.4 m, comfortably inside the -5.0 m bound the
   committed shipped-gain tests use for the larger decel. No separate test commits this 150->60
   figure, but nothing in the law is airspeed-specific beyond the blade-stall guard (inactive here,
   150/60 km/h is far below the 315 km/h line) and the rotor-RPM warning (not engaged at either
   speed in this run), so I read this as confirming coverage rather than finding a gap — not a
   required fix, since `TestDecelerationHoldsAltitude`'s existing 273->108 scenario already
   exercises the same mechanism at a harder operating point.

4. **Mutation, both directions, run and reverted (file restored, `git status --porcelain` clean
   before continuing):**
   - Reverted `flight_control.lua`'s fix to the old rate-bias mechanism (biasing `c_dot_nominal`
     again instead of the bounded value-level nudge): 3 tests go red
     (`test_altitude_deviation_stays_small_through_a_large_decel` and both shipped-gain
     `TestDecelerationHoldsAltitude` tests), with the shipped-gain scenario's min deviation back at
     -36.0 m.
   - Reverted the test file's own `_LIMITS.retreating_blade_stall_ias_kmh` from 335.0 to 250.0 (the
     round-3 threshold fix): the same two shipped-gain tests go red (-19.3 m against a -5.0 m
     bound) — confirms the guard's threshold, not just its mechanism, is what the committed
     assertions actually depend on.

5. **Finite-float standing rule.** Both new values in this diff —
   `RETREATING_BLADE_STALL_IAS_KMH` (335.0, a changed value at an *existing* tuning-boundary field,
   not a newly introduced one) and `collective_speed_give_max_a_f_d_mps2` (3.0, a new field) — are
   not boundary floats in the rule's own sense (wire/HTTP JSON/Hook payload/`tuning.toml`
   parse). `RETREATING_BLADE_STALL_IAS_KMH` resolves through `tuning.real()`, whose existing
   `lo <= value <= hi` range check already rejects `NaN`/`Infinity` as "out of range" by
   construction (Python's `NaN` comparisons are always `False`, and `Infinity` fails any finite
   `hi` bound) — no gap, and not new to this diff. `collective_speed_give_max_a_f_d_mps2` is a
   hardcoded Lua literal in `flight_profile.lua`, `dofile`-loaded from a file this repo ships, the
   same trust level as every other gain in that table — not parsed from outside the process. No
   finding here.

### Required Fixes

None.

### Optional Refinements

- A committed test for the 150->60 km/h decel specifically (the user's own named command speed)
  would close the gap between "the mechanism is exercised at 273->108" and "the exact speed the
  user flew is covered" — cheap to add from the harness already in `TestDecelerationHoldsAltitude`,
  and would have caught the full magnitude of the pre-fix bug (-41.3 m, worse than the -39.3 m the
  committed 273->108 scenario shows) directly rather than by extrapolation. Not required: the
  mechanism and the guard are airspeed-general, and the committed scenario already demonstrates the
  fix at a harder point on the same curve.

### Verdict

APPROVED

### Review Confidence

Full read of the round 1-3 diff, `aircraft-layer/CLAUDE.md`'s flight-control section, the research
doc, and the acceptance feedback. Ran the full `aircraft-layer` test suite (1184 passed),
`body-layer/tests/test_flight_control.py` (20 passed), `ruff format --check`/`ruff check`/`mypy
--strict` clean on both subprojects, Lua syntax check clean. Independently ran (not from any
committed test) the 150->60 decel and 150->250 accel toy-plant scenarios against the shipped
profile on both the target commit and the pre-fix baseline, and ran both required mutations
(old rate-bias mechanism restored; threshold reverted to 250) confirming the committed tests go
red on each, then confirmed the working tree was restored clean before writing this report.
