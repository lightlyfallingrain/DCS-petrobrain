# Review: BL-16 LV-3 fix pass (second pass)

Reviewed at `d25bdc0a` (`fix/bl16-flight-epoch-bound`, fast-forwarded from `a29eff71` in this
worktree — strict ancestor, clean tree, `git merge --ff-only d25bdc0a`). Diff under review:
`096e2c3d..d25bdc0a` (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`, three touched
test files, `plans/flight-lift-vector/implementation-lv3.md` "Fix pass" section).

Checked against `plans/flight-lift-vector/review-lv3.md`'s four required fixes (the
`turn_mode` optional finding promoted to a fifth required fix by the main loop) and
`plans/flight-lift-vector/plan.md`'s LV-3 amendment/corrections, U12–U17 answers, and the "LV-3
card rows" section (plan.md line 1977). Memory searched first
(`memory-search.py bl16 lv3`/`turn_mode`) — the one hit
(`plan-aligner/project_bl16_lv3_diagram_not_redrawn_after_correction.md`) is the diagram-text
drift already flagged out of scope by `review-lv3.md`; nothing else indexed yet for this pass.
`gq.sh` not separately queried beyond that — the governing documents (plan, two reviews,
implementation note) were read in full and are the authoritative account here.

### Review Summary

Checks pass clean, run independently (not taken from the implementation note): `ruff format
--check`, `ruff check` (both `src tests`), `mypy --strict src` (0 issues, 29 files), `luac5.1 -p`
on all three touched Lua files, full suite `pytest tests -q -n auto` — **1265 passed**, matching
the note's own figure (was 1254; +11 new tests, exact count confirmed against the diff's new
`def test_*`/parametrize entries).

All five required fixes were verified **by mutation, not by reading the diff and the
implementation note's prose**:

- Reverted the `turn_mode` rate-cap clamp → `TestLv3TurnModeLambdaBlend`'s hover case fails
  (40.03°/s vs. the asserted ≤8.5°/s ceiling) and its mid-blend case fails (3.01° off the expected
  blended cap) — the two blend-sensitive cases the implementer's own note claims go red.
- Zeroed `k_drift_hold` in `flight_profile.lua` → `TestLv3DriftHoldToyPlant` fails (final ground
  speed 5.0 m/s, the uncorrected crosswind, vs. the asserted <1.0).
- Removed the `bank_hold_deg` clear from `test_flight_control_lua.py`'s own `write_internal` mock
  → `TestLv3HeldBankEndWriteBack` fails (`99` instead of `nil`), proving the new test actually
  drives the real `flight_control.lua` orchestration (`request_take`/`run_flight_control`) rather
  than asserting against a tautology.
- The `flight_desired.lua` getters were read directly (`get_lambda`/`get_take_speed_kmh` calls at
  lines 268/305) to confirm `test_flight_desired_lua.py`'s two new tests exercise real production
  code through the mock stub, not a self-contained fixture.

All four come back red for the stated reason and green with the fix restored. This is stronger
evidence than the first review got (which confirmed red only on the `turn_mode` cases).

**`turn_mode` clamp placement is correct.** The rate cap (`rate_cap = lambda*|r_goal| + (1-lambda)
*hover_yaw_rate_max_deg_s`) is applied to `r_goal` *before* the roll-in ramp (`dr =
law_clamp(r_goal_capped - state.r_ref, -accel_limit*dt, accel_limit*dt)`) — read directly at
`flight_control.lua` lines ~969–990 — exactly the ordering the review's finding required. A turn in
progress when λ changes mid-turn sees no discontinuity: `rate_cap` is recomputed fresh every frame
from the current `lambda` (itself continuous, per `law_lambda`'s own linear breakpoint), and the
step from `state.r_ref` toward the (possibly now-lower) `r_goal_capped` is still bounded by
`accel_limit*dt` — a falling cap pulls the target down smoothly, never snaps `r_ref` itself. The
break's own `rate_override_deg_s` path is a separate branch (the `else` clause, two cases below
`turn_mode` in the same `if`/`elseif`/`else`) and is untouched by this diff — confirmed by reading
the full chain (lines 909–1077): the fix is scoped to the `elseif state.turn_mode` branch alone.

The accel-limit (roll-in rate) itself is **not** lambda-blended in the `turn_mode` branch, unlike
the ordinary heading branch where `accel_limit = rate_limit / t_roll` tracks the blended
`rate_limit`. This is noted below as optional, not required — `heading_accel_cap` is already
scaled by `schedule_g` (itself a function of `ias_kmh`, near its floor at low speed regardless of
`lambda`), so the roll-in is already gentle at low speed by a different, pre-existing mechanism;
nothing in the five required-fix tests or the toy-plant probes showed an abrupt roll-in at hover.

**Deferrals name real card rows, and the implementation note corrected the review's own
numbering.** `review-lv3.md`'s required fix 4 said "rows 3, 5 and 6"; cross-checked against
`plan.md`'s actual "LV-3 card rows" list (line 1977 ff.), row 5 is "hover in wind," not
"accelerate 0→150." `implementation-lv3.md`'s own table instead says rows 3, 7 and 6 — row 3
("Stop," 150→0), row 7 ("Away," speed 150 from hover — the accelerate case), row 6 ("Low hover,"
inside ground effect) — which match the plan's real rows exactly. The implementer's correction is
right; the review's own text was the one with the error. No action needed; noted so the discrepancy
isn't mistaken for a future defect.

### Required Fixes

None.

### Optional Refinements

- **`turn_mode`'s roll-in `accel_limit` is not itself lambda-blended**, only the `rate_cap` the
  ramp aims at. Given `schedule_g` already floors `heading_accel_cap` at low `ias_kmh`
  independently of `lambda`, this is very unlikely to produce an abrupt roll-in in practice, but it
  is an asymmetry against the ordinary heading branch's pattern (`accel_limit = rate_limit /
  t_roll`, tracking the blend). Worth a one-line note if `turn_mode` ever becomes a live-card
  concern; not blocking.
- The review-vs-plan card-row numbering mismatch above (`review-lv3.md`'s "rows 3, 5, 6" vs. the
  plan's actual rows 3, 6, 7) is harmless since the implementation note used the correct numbers,
  but worth a one-line correction to `review-lv3.md` itself so a future reader of that file alone
  isn't misdirected to row 5 ("hover in wind").

### Verdict

APPROVED

### Review Confidence

Full read of the diff (all five files) and the governing plan sections (LV-3 amendment, U12–U17,
"LV-3 card rows," Risks). All four required-fix tests independently verified by mutation (code or
mock reverted, test shown red, restored) rather than taken from the implementation note's
disclosure — the `turn_mode` clamp's placement and mid-turn-λ-change behavior were read directly
from `flight_control.lua`, not inferred from the commit message. Checks (`ruff`, `mypy --strict`,
`luac5.1 -p`, full `pytest -n auto`) run independently. Not independently re-derived: the toy
plant's own physical plausibility (weathervane/pedal-yaw/ball gains) and the three explicitly
deferred vertical-dynamics scenarios (Stop, Accelerate, Ground effect) — both already flagged as
out of this pass's scope by the first review and the implementation note, and unchanged by this
fix pass.
