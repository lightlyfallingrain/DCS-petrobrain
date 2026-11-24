### Review Summary

Reviewed `7204baee..2807730b` (5 commits) on `feature/bl16-lift-vector-law` against `plan.md`'s
"LV-1 amendment" section, `alignment.md`'s last two sections, and `implementation.md`'s "LV-1
amendment" entry, with `docs/acceptance/2026-11-24-sortie-feedback.md` as the source of the
user's own RPM readings and manoeuvre descriptions.

Scope fits the plan: section A (bank-hold take, `hdg_mode = "bank"`, E12 unpark-rate fix),
B (speed-channel feed-forward rebalance), C (engine-RPM-gated collective schedule, corrected from
rotor RPM), D (pedal P-term + raised torque feed-forward) are all built, each inside the module it
plans to live in (Lua law/profile, no body-layer round trip for A, as the plan explicitly argues).
Section F (breaks) correctly deferred to LV-2, recorded only, no code touched. Co-moving Fields
table is honoured exactly — every transition it names (`clear_desired`, both `reseed_from_measured`
branches, `reseed_from_overlay`, `convert_turn_to_heading_for_m2`, both `apply_set` branches,
`law_apply_goal`'s two goal branches) clears `bank_hold_deg`, verified against the diff line by
line, not the file list. Sign conventions hold: the `a_r,d = g·tan(bank_hold_deg)` trig identity
checks out exactly against `law_turn_rate_at_bank`/`law_phi_ff_deg`'s existing formulas (worked by
hand below), the P ball term and torque feed-forward use the same sign/shape as the integral terms
they sit beside, and `LAW_DIR` is unchanged. The −15° level-acceleration pitch cap
(`theta_min_deg`/`theta_max_deg`) is untouched, as it should be. Bit-exactness at take is preserved
by construction (`t_y_p_at_take` backed out of the pedal seed, mirroring `u_c_i`/`u_c_ff`) and
confirmed by a new, targeted test with a non-centred ball — the one case that actually exercises
the new term. `MAX_ACCEL_MPS2`'s rendered `defaults.toml` first sentence is short and factually
correct ("The speed channel's own along-track acceleration ceiling."), and its value (2.0) and
bounds (0.1–5.0) are consistent with the Lua-side raise it is meant to never clamp below.

Both subprojects' checks pass clean in this worktree (venvs built fresh from this task's
instructions, Python 3.12):

- `aircraft-layer`: `ruff format --check` / `ruff check` clean; `mypy src` clean (29 files);
  `.claude/scripts/fast-tests.sh aircraft-layer` — 1173 passed.
- `body-layer`: `ruff format --check` / `ruff check` clean; `mypy src` clean (93 files);
  `.claude/scripts/fast-tests.sh body-layer` — 2968 passed, 4 xfailed (the flaky
  `test_crew_text_poll_loop_survives_a_raising_poll_and_keeps_going` the implementer flagged as
  pre-existing did not even reproduce in this run; not this task's regression either way).

The five implementer-flagged points are judged below (judgment 1–5), followed by two gaps this
review found that were not implementer-flagged (required fixes 1–2).

### Required Fixes

1. **No test exercises the amendment's own production-valued configuration together.**
   `test_flight_control_law.py`'s shared `_PROFILE` baseline keeps `c_theta = 0.5`,
   `speed_accel_cap_mps2 = 0.5`, `k_pedal_from_collective_rate = 0.25` — the pre-amendment values
   — for every test except the ones that locally override one or two fields at a time
   (`TestSpeedChannelIsBrisk` sets `c_theta`/`speed_accel_cap_mps2`; `TestPedalReachesCollectiveStepTarget`
   and `TestBitExactAtTakeWithTheNewPedalProportionalTerm` touch only `k_ball_pedal_p`, which
   happens to be unchanged from its "new field" default). **No single test sets `c_theta = 0.85`,
   `speed_accel_cap_mps2 = 1.9`, and `k_pedal_from_collective_rate = 0.6` together** — grepped
   `test_flight_control_law.py` for `PROFILE\.(c_theta|speed_accel_cap_mps2|k_pedal_from_collective_rate)`:
   only the first two appear, together, in `TestSpeedChannelIsBrisk`; the third never appears as an
   override at all. The gap matters because the sortie's own row-4 climb — the scenario D's raised
   `k_pedal_from_collective_rate` was built to fix — is exactly a simultaneous pitch-change-plus-
   collective-rate event, which is also exactly what the raised `c_theta` changes the onset of; the
   two gains were tuned from the same flight but have never run together in a test. This is
   separate from `implementation.md`'s own flagged gap (the `test_flight_control_lua.py` mirror
   staying pre-amendment) — that one is a different file with a different, narrower purpose
   (whole-module Lua syntax/wiring); this gap is in the file that actually exercises the law's
   physics with local overrides, and it under-covers the amendment's real combined behaviour even
   there. **Fix:** add one scenario (a climb-and-accelerate or at least a speed-change-with-ball-
   offset run) with all three raised values applied together, asserting it neither overshoots nor
   oscillates — the thing the sortie card still has to confirm live, but a toy-plant check of the
   combination costs little and catches an interaction a before-the-fact review of two isolated
   diffs cannot.

2. **`spooled_rpm_pct = 97.0` does not match the plan's own stated threshold (~93%), and the gap
   is not flagged as a deviation.** The plan's correction box says, verbatim: *"At or above normal
   cruise output (~93%) → fast; tapering toward ~74% (fully spooled down) → gentle, ~5 s."* The
   user's own cockpit reading for level cruise, 170 km/h, is engine RPM ~93%. The implementation
   sets `spooled_rpm_pct = 97.0` (`flight_profile.lua`), justified in its own comment by the
   *acceleration* reading ("98-100%"), not the level-cruise reading the plan actually names for
   this threshold. Run the arithmetic: at a steady 93% (ordinary level cruise), once the schedule
   is live, `frac = clamp((93-74)/(97-74), 0, 1) ≈ 0.83` — the collective-increase rate is tapered
   to ~83% of nominal during ordinary level flight, not treated as "fast" the way the plan's own
   number requires. Today this is inert (`ENGINE_RPM_SOURCE = "dummy"` pins `engine_rpm_pct` at
   100, always above any plausible threshold, so nothing narrows yet — confirmed by
   `TestEngineRpmGatedCollectiveSchedule`'s own tests, none of which exercises 93%), so there is no
   live misbehaviour today. But the value that will go live the moment U9's calibration flight
   flips `ENGINE_RPM_SOURCE` to `"arg_proxy"` is not the one the plan specified, and
   `implementation.md`'s "Not built as written, and why" section — which correctly flags the
   `bank_hold_threshold_deg` reuse and the E12 trace gap — says nothing about this one. Root
   `CLAUDE.md`'s own rule applies here directly: *"Departing is allowed; doing it silently is
   not."* **Fix:** either lower `spooled_rpm_pct` to the user's own ~93% level-cruise figure (and
   re-check `TestEngineRpmGatedCollectiveSchedule`'s existing 97/100 test still makes sense once
   the threshold itself moves), or, if 97 is a deliberate conservative choice, say so explicitly in
   `implementation.md`'s deviations section with the reasoning — not left to be discovered the day
   U9's flight turns the schedule on.

### Optional Refinements

- **(implementer's judgment 2, E12 fix)** Reasoning through the fix by hand: `rate_limit` is
  floored at `abs(state.r_ref)` each frame, which only ever pegs the ceiling to the *previous*
  frame's rate — it cannot let the magnitude increase beyond what was already inherited, and the
  heading-error term's damping component (`-2·ζ·ω·r_ref` inside `a_ref`) drives `r_ref` toward the
  heading-converged equilibrium regardless of the ceiling. So this cannot leave an excessive rate
  standing indefinitely: magnitude is non-increasing frame over frame and decays through the
  critically-damped dynamics as `psi_ref` converges on `heading_goal_deg`. Not a risk. The one gap
  is that `TestUnparkMidTurnRateNeverSlammedToTheOrdinaryCeiling` only checks frame one (rate
  changes by <1°/s); a second assertion a few seconds further into the same driver — rate has
  decayed back under the ordinary ceiling — would close the "flagged, not fully traced" note the
  plan and implementation both carry, more cheaply than reopening the fourth re-fly's own trace.
  Optional because the math already shows it is safe; this would only make that visible in the
  test itself.
- **(implementer's judgment 1, `TAKEOVER_LEVEL_BANK_DEG` reuse)** No fix needed — confirmed the
  value (5.0) matches the plan's own first-cut figure, the reuse is justified in both the plan
  text and `implementation.md`, and it is the right call under root `CLAUDE.md`'s "do not reinvent
  the wheel": a second, Lua-only threshold next to an existing wire-tunable one stating the exact
  same rule would have been the thing to flag, not this.
- **(implementer's judgment 3, rewritten tests)** No fix needed — correctly flagged per the
  escalation rule, and the rewrite is the amendment's own stated intent (E11/finding 2 retire the
  old mechanism these tests pinned), not an incidental change. `TestBitExactAtTake` itself (the
  guarantee, not the mechanism) was left alone, which is the right line to hold.
- **(implementer's judgment 4, stale `test_flight_control_lua.py` mirror)** Covered in substance by
  Required Fix 1 above — the three stale values (`c_theta`, `speed_accel_cap_mps2`,
  `k_pedal_from_collective_rate`) are confirmed inert for that file's own existing scenarios
  (checked the grep for non-centred `slip_ball_*_raw` and non-default `engine_rpm_pct` myself; both
  absent, matching the implementer's claim). Leaving that one file's mirror stale is acceptable
  given the effort/blast-radius tradeoff stated; the combined-values gap it points at is covered by
  Required Fix 1 using the other test file instead, which is the right place for it.
- **U10 (E12's fix) is not named by its ID in `implementation.md`**, only addressed in substance
  (the root-cause writeup is exactly U10's content). `.claude/scripts/accepted-items-ledger.sh
  plans/flight-lift-vector` flags this, along with U1–U4/U6/U7 from the base LV-1 plan (pre-dating
  this amendment, out of this review's scope and presumably settled in the prior `review-lv1.md`
  pass — not re-litigated here). Adding the literal string "U10" next to the E12 writeup would make
  the ledger script's job mechanical instead of requiring a by-hand read; low cost, no functional
  effect.
- **Cross-subproject coupling, `MAX_ACCEL_MPS2` (body-layer) vs `speed_accel_cap_mps2`
  (`flight_profile.lua`).** The plan and implementation both state the invariant in prose ("raised
  alongside this one so the dv_ref clamp does not sit below it") but nothing enforces it
  mechanically — the two live in different languages/processes, and no existing mechanism in this
  project asserts such a coupling across the Lua/Python boundary. Not asking for one to be
  invented here; flagging only because a future edit to either side, in isolation, would silently
  reopen the gap the plan closed.
- **Brisk take-with-a-speed-gap** (plan section I's superseded sentence) is exercised only via an
  ordinary post-take speed command (`TestSpeedChannelIsBrisk`), not via `seed.speed_kmh` at
  `law_init_at_take` itself (the actual unpark-with-a-standing-speed-goal path,
  `flight_control.lua` line ~700). The code path is provably the same either way (`state.
  speed_goal_mps` feeds the same shaper regardless of how it was set, confirmed by reading the
  code, not assumed) so this is a low-value gap, not a required one.

### Verdict

CHANGES REQUESTED — two required fixes above (test coverage for the amendment's combined
production values; the `spooled_rpm_pct` figure vs. the plan's own ~93% threshold, or an explicit
flagged deviation). Everything else in the amendment — the bank-hold take mechanism, the E12 fix,
the pedal P-term, the Co-moving Fields table, sign conventions, bit-exactness, and the rendered
`defaults.toml` — holds up against the plan and the project's invariants.

### Review Confidence

Full read of the diff (`git diff 7204baee..2807730b`, all touched files), `plan.md`'s amendment
section and the base plan's section I it supersedes, both `alignment.md` sections in scope,
`implementation.md`'s amendment entry, and the sortie feedback's RPM/manoeuvre text. Hand-verified
the `a_r,d = g·tan(bank_hold_deg)` trig identity and the E12 rate-ceiling's non-increasing-magnitude
argument by working the formulas rather than trusting the comments describing them. Ran both
subprojects' format/lint/type/fast-test commands from freshly built venvs in this worktree (no
pre-existing `.venv` was present to inherit). Did not re-run a live DCS session — no acceptance
testing exists outside a live sortie, per this role's own scope; the branch to fly, once the two
required fixes land, is `feature/bl16-lift-vector-law`.
