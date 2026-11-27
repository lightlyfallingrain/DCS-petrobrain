# Review: BL-16 lift-vector law, Stage LV-3 (low speed and hover)

Reviewed at `b1e99283` (`fix/bl16-flight-epoch-bound`, fast-forwarded from `a29eff71`). Diff under
review: `78a6f3fd..b1e99283` (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`,
`flight_desired.lua`, `flight_profile.lua`, the three touched test files, and
`plans/flight-lift-vector/implementation-lv3.md`).

Checked against `plans/flight-lift-vector/plan.md` "LV-3 amendment (2026-11-27)" through the end
— with the "Corrected 2026-11-28" notes under sections C and E, and the "Answered 2026-11-28"
U12–U17 block, taken as overriding the earlier text — `explore-notes.md`'s "LV-3 explore" and
"LV-3 diagram review corrections", and `alignment.md`'s LV-3 plan check. Reviewer memory searched
first (`memory-search.py`); the relevant prior entries are the toy-plant/test-profile-drift and
mock-harness-fidelity lessons this amendment's own implementer memory
(`feedback_mock_position_gap_silently_changes_regime.md`) already restates.

### Review Summary

Checks pass clean: `ruff format --check`, `ruff check`, `mypy --strict` (0 issues, 29 files),
`luac5.1 -p` on all three touched Lua files, and the full suite (`pytest tests -q -n auto`,
1254 passed, run twice per the implementer's own report, reproduced here once). The U13 pedal-range
change, the upvalue/module-local budget claims, and the `k_yaw_damp = 0` bit-exact comparison
against the pinned 120 km/h figures were independently verified against the code and the live
`luac5.1 -l` output (not just the implementer's narrative) and all check out.

The mechanism itself (`law_lambda`, the regime-aware blends in sections A–G, the hover pedal band
corrected to bind only during a commanded heading change, U13's full pedal range) is built as the
corrected plan specifies, and the diagram-vs-correction text drift `alignment.md` already flagged
is plan-text hygiene, not a code defect — out of this review's scope.

The real findings are a cluster of **test coverage gaps against the plan's own Tests section**,
one of them covering code with literally zero test exposure (`flight_desired.lua`'s two LV-3
changes), and a **narrower-than-first-read `turn_mode` gap** investigated directly with a Lua
probe rather than left as a readback of the implementer's own disclosure.

### Required Fixes

1. **`flight_desired.lua`'s two LV-3 changes are completely untested.** `test_flight_desired_lua.py`
   was not touched by this commit at all. Its `flight_control` mock stub (around line 126) still
   has no `get_lambda`/`get_take_speed_kmh` entries — `safe_call` on a missing field returns `nil`
   unconditionally, so `reseed_from_measured`'s new hover take-rule mirror
   (`not (lambda ~= nil and lambda <= 0.0)`) and its new `V_m`-from-`get_take_speed_kmh` speed seed
   are both permanently dead code as far as this test file is concerned. A regression in either
   path — the override firing when it should not, the override never firing, `ias_kmh` silently
   reverting to bare IAS — would pass every existing test silently. Add the two mock functions to
   the stub and at least one test per path (a banked-at-hover reseed holding heading, not bank; a
   reseed at a blended speed picking up `V_m` rather than bare IAS).

2. **The held-bank-end write-back (`run_active_frame`'s new `elseif prev_bank_hold ~= nil and
   fc_law.bank_hold_deg == nil` branch) and `write_internal`'s own new `desired.bank_hold_deg = nil`
   clear (finding 6) have no test anywhere that exercises the real code.** The plan's own Tests
   section says explicitly: *"`test_flight_control_lua.py` checks the write-back and
   `desired.bank_hold_deg == nil`."* That did not happen. `test_flight_control_lua.py`'s own
   `flight_desired` stand-in (its hand-written `write_internal` mock, ~line 410) does not even
   implement the clear — it has no `bank_hold_deg` field in its mock `desired` table at all — so
   even an integration-style check through that harness could not currently catch a regression
   here. `TestLv3HeldBankEndsAtHover` (in `test_flight_control_law.py`) only exercises
   `law_update`'s own internal `bank_hold_deg`/`turn_mode` transition; it never reaches
   `run_active_frame` or `flight_desired.write_internal`. Add the write-back assertion the plan
   promised, against either the real `flight_desired.lua` (preferred, since the mock in
   `test_flight_control_lua.py` is a second, drifting copy of this logic) or at minimum update that
   mock to clear `bank_hold_deg` the same way and assert it.

3. **No closed-loop test exists for the drift-hold mechanism** (`a_r_d`'s `k_drift_hold` blend,
   section B), despite the plan's own Tests list requiring it by name: *"Speed 0 in a 5 m/s
   crosswind: ground speed settles under 1 m/s; heading held by pedal; bank carries the drift
   hold."* This is new, player-visible behaviour — crosswind hold at hover — with zero test
   coverage of any kind, unit or toy-plant. Add at least a toy-plant-style closed loop (the
   existing `TestLv3RunawayToyPlant` driver is the template) showing the mechanism actually damps
   a lateral ground-speed component toward near-zero under a sustained lateral disturbance, with
   heading held by the yaw loop rather than the bank.

4. **`implementation-lv3.md` discloses none of the above three gaps, nor five further items the
   plan's own Tests section lists that were not built**: "Stop 150 → 0" (altitude in band through
   a deceleration to hover), "Accelerate 0 → 150", the hover heading-change test at 90° and in both
   directions (only one 45° direction is covered, by `TestLv3HoverPedalBand`), "Band does not cut
   the lead" (a collective step during an active heading change moving the pedal past the band),
   "Ground effect and transitional lift", and "Take at 20 km/h: bit-exact... `speed_goal_mps` is
   `V_m`" (only the λ=0/λ=1 boundary cases are tested by `TestLv3TakeRuleAtHover`, never an
   interpolated-λ take). The first three ("Stop"/"Accelerate"/ground-effect) need a toy plant with
   vertical/altitude dynamics the current one does not model at all (it is horizontal-only, by
   construction, per the module docstring above `_LV3_RUNAWAY_DRIVER`) — building that is a
   materially bigger effort, and is reasonably left to the live card's rows 3, 5 and 6, **provided
   it is written down as left to the card rather than silently absent.** The implementation note's
   "Checks" section currently reads as if the plan's Tests list was satisfied; it was not, and DoD
   and the card author need this gap in writing to know what the unit/toy-plant layer has and has
   not verified before relying on it. Required: amend `implementation-lv3.md` (or the equivalent
   record this review becomes) with the list above, split into "deferred to the live card" (the
   three vertical-dynamics items) and "should be added here, cheaply, before merge" (the
   90°-both-directions hover test, the band-does-not-cut-the-lead test, and the interpolated-λ
   bit-exact take test — none of these need new toy-plant machinery, only a new scenario against
   the existing pure-Lua unit-test harness).

### Optional Refinements

- **`turn_mode` (continuous "turn left/right" with no degrees spoken) is not lambda-blended** —
  confirmed directly, not just taken on the implementer's own disclosure. Investigated with a
  throwaway Lua probe (`law_apply_goal(state, {turn = 1}, ...)` at 2 m/s ground speed, 20° max
  bank): `turn_goal_deg_s` comes back ≈ 102 °/s, because `law_turn_rate_at_bank` is speed-inverse
  and nothing scales it down for a low-speed continuous-turn command the way the ordinary heading
  branch's `omega_heading`/`rate_limit` are scaled for every other heading-type command below
  80 km/h. **This reads more severe than it is**, for two structural reasons worth recording: (a)
  `a_r_d` (the channel that actually drives bank) blends toward the drift-hold term as λ falls
  *regardless of which branch set `r_d`*, so a continuous-turn command cannot bank the aircraft at
  low λ any more than a heading command can — the "do not bank to turn to heading, use pedals" rule
  stays structurally enforced; (b) `law_turn_rate_at_bank` returns `0.0` outright below 1 m/s true
  airspeed, so at genuine hover `turn_goal_deg_s` itself degenerates to ~0, not 102°/s — the large
  number only appears in the narrow blend band (roughly 1 m/s up to `lambda_hover_kmh`) where V_t is
  small but nonzero. A 10-second probe run with the demanded rate tracked by the yaw-rate integrator
  did not show the pedal output saturating in that window, but the probe is not a substitute for a
  real test and was not run long enough or adversarially enough to rule out a slower build-up. The
  genuine, narrower gap is that a continuous turn command in the 25–80 km/h blend band does not get
  the "below 80 km/h, gentler" treatment every other heading-type command gets there — a
  consistency/quality miss, not the hover bank-violation it first looks like. Recommend: note this
  explicitly as a known limitation (plan Risks, or a backlog item under BL-16), and consider
  blending `turn_mode`'s own `omega`/`rate_limit`/`accel_limit` the same way the ordinary branch's
  are blended two cases above it in the same `if`/`elseif` chain — the mechanism already exists and
  this would be a small, local change. Not blocking, given (a) and (b) above.
- A test with λ strictly between 0 and 1 (take at 20 km/h, per the plan's own Tests list) would add
  real confidence beyond the two boundary points (λ=0, λ=1) every current LV-3 test uses — the
  interpolation itself is currently exercised only by `TestLv3LambdaHelper`'s helper-level
  breakpoint test, never through a full `law_init_at_take`/`law_update` pass.
- The toy plant's weathervane/ball/pedal-yaw gains are an explicitly-disclosed first cut that does
  not reach the plan's own illustrative "<10°" sideslip figure (17.8° achieved, vs. 31.2° for the
  LV-2 gate). The test asserts a meaningful relative bound (`< 0.6 ×` the LV-2 figure) rather than
  the illustrative absolute number, which is the right call given the plant is admittedly a first
  cut tuned only to reproduce the failure shape — not asserting a number the author knows the model
  cannot honestly support is the correct posture here, not a defect. Worth a one-line note on the
  LV-3 card that live sideslip may exceed the plan's illustrative figure.

### Review Confidence

Full read of the diff and the governing plan sections (C, E's corrected text, D, F, G, the
Tests/Co-moving-Fields/Risks sections). Checks (`ruff`, `mypy --strict`, `luac5.1 -p`, full
`pytest` suite) run independently, not taken from the implementer's report. The `turn_mode` finding
was independently verified with a throwaway Lua probe against the real `law_apply_goal`/
`law_update`, not left as a readback of the implementer's own disclosure — though that probe's own
coverage (one scenario, 10 s, one set of gains) is itself partial, noted above. Test-gap findings
were confirmed by grepping the actual test files for the plan's own named scenarios, not inferred
from the implementation note's "Tests Added" list. Not independently re-derived: the toy plant's
own physical plausibility (weathervane/pedal-yaw/ball gains), which the implementer's own
Notable Discoveries section already flags as a first cut.
