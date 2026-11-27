### Implementation Summary

Implemented the LV-2 amendment (`plan.md`, "LV-2 amendment (2026-11-27)" through the end of the
file, later-wins over the body — `break_max_bank_deg` first cut 60° per the main-loop correction,
not the body text's 65°). Scope: sections B (break bank/rate cap), C (class-aware shortfall,
height gives first), D (break-only 50 m floor beside the unchanged 40 m), the plan's own Tests
list, and a new LV-2 card. Section E (already satisfied, confirmed, no code) and F (both RPM/G-load
items deferred, recorded only) needed no changes; section A/the Design Overview diagrams describe
mechanisms already built and untouched by this pass.

Base: `git rev-parse HEAD` matched the dispatched sha (`8ad90f24`) exactly, on
`fix/bl16-flight-epoch-bound`; that branch is not an ancestor of this worktree's starting point
(`c0d8af86`, this worktree's own merged-to-main history), so per the dispatch instructions I
created `lv2-impl` at `8ad90f24` in this worktree's shared object store and built on it. Harvesting
this amendment onto `feature/bl16-lift-vector-law` is the main loop's job, not this pass's (same
note the plan itself makes about reaching this point via `lv2-plan`).

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — three new tunables after the LV-1
  `collective_speed_give_max_a_f_d_mps2` entry: `break_max_bank_deg` (60.0), `break_floor_agl_m`
  (50.0), `break_height_give_band_m` (30.0). Lua-edited data like every other field in this table
  (module docstring: no `lo`/`hi` bounds enforced here); none travels the wire or enters
  `flight_control.lua`'s `FC_LIMIT_BOUNDS` — confirmed by reading that table in full before adding
  anything, per the plan's own "Tuning constants" note that none of the three overlaps an existing
  key.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`:
  - **Section B** (the heading-rate step's break branch, `law_update`): `rate_limit` is now
    `math.min(math.abs(state.rate_override_deg_s), law_turn_rate_at_bank(profile.break_max_bank_deg,
    measured.v_t_mps))`, not the bare override magnitude — reuses `law_turn_rate_at_bank`, no new
    formula.
  - **Section D** (the altitude shaper's break-floor clamp): `break_floor` is now computed against
    `profile.break_floor_agl_m` (50.0) instead of `limits.floor_agl_m` (40.0, unchanged everywhere
    else) — the one deliberate behaviour change this amendment makes (U11: "only breaks"). Hoisted
    to a `local break_floor = nil` declared just above the `if`, so section C can read the same
    computed value rather than re-deriving the formula (per the plan's own instruction).
  - **Section C** (the shortfall block, `law_update`): a new `effective_shortfall` local, equal to
    `shortfall` outside break class; inside break class (`state.rate_override_deg_s ~= nil and
    break_floor ~= nil`), scaled by `(1 - height_available_frac)` where `height_available_frac =
    clamp(height_margin_m / break_height_give_band_m, 0, 1)` and `height_margin_m = measured.h_m -
    break_floor`. `theta_speed_give`/`phi_scale` now read `effective_shortfall`, not `shortfall`
    directly. Guarded against a non-positive `break_height_give_band_m` (division safety, the
    boundary-float standing rule) — degrades to no height-giving rather than a crash/NaN, mirroring
    `law_turn_rate_at_bank`'s own near-zero-input guard.
  - Two new diagnostic-only fields, `next_state.dbg_shortfall`/`dbg_effective_shortfall` (same
    posture as the existing `dbg_r_d`/`dbg_u_c_rate`) — added so the new tests (and a future flight
    trace) can see the class-aware routing actually engaging, since neither value was observable
    from `state` before this pass.
- `aircraft-layer/tests/test_flight_control_law.py` — three new tunables added to the shared
  `_PROFILE` table (shipped values: 60.0/50.0/30.0 — every pre-existing break scenario in this file
  reaches a bank well under 60° and a floor well below 200 m, so these do not change any
  pre-existing assertion; confirmed by running the full file, not assumed) and three new test
  classes (below).

### Tests Added

- `TestLV2BreakBankRateCap` (shipped `flight_profile.lua` via `dofile`, per
  `feedback_toy_plant_test_profile_must_match_shipped_values.md` — this amendment's own cap number
  is exactly what's under test):
  - `test_cap_binds_at_250_kmh_clamping_an_inherited_38_deg_s_down_to_the_bank_cap` — seeds
    `state.r_ref` at 38°/s (via `law_init_at_take`'s own `seed.r_deg_s`→`r_ref` path, the same
    technique `TestUnparkMidTurnRateNeverSlammedToTheOrdinaryCeiling` uses), applies a break goal,
    runs one `law_update` frame at 250 km/h, and asserts `r_ref` lands exactly on
    `law_turn_rate_at_bank(60°, v_t)` (~14.02°/s) — the hard clamp binding.
  - `test_cap_does_not_bind_below_88_kmh_leaving_the_seeded_rate_untouched` — same seed at 70 km/h,
    where the bank-derived rate (~50°/s) exceeds the override's own 40°/s ceiling, so neither
    ceiling touches the seeded 38°/s in one frame.
  - Isolates the clamp itself from the full closed-loop toy plant's own unrelated slowness —
    `TestBreakTurnChannel`'s docstring already measured that the heading-mode shaper never drives
    the realized rate anywhere near 40°/s for a bare 90° step error, so neither the old ceiling nor
    this amendment's cap is observable through bank/rate growth in that scenario; probed directly
    before writing these tests (not assumed).
- `TestLV2HeightGivesFirst` (shipped profile via `dofile`):
  - `test_height_to_spare_suppresses_pitch_back_and_bank_easing` — entry height 150 m
    (`break_floor` = 50, margin 100 m, 10× the band) with the rotor-RPM-warning guard forcing a real
    `shortfall` (~0.49) via a large climb demand: asserts `effective_shortfall < 1e-6` and
    `theta_i == 0.0` across 10 frames.
  - `test_near_the_break_floor_engages_at_pre_amendment_strength` — same mechanism at entry height
    50 m (margin 0): `effective_shortfall == shortfall` and `theta_i` grows.
  - `test_bank_feed_forward_is_steeper_with_height_to_spare_than_near_the_floor` — the bank-side
    comparison: `phi_d` after 10 frames is more than 2× steeper with height to spare.
- `TestLV2BreakFloorIsBreakOnly::test_break_floor_converges_near_the_new_50m_floor_not_the_old_40m`
  — entry height 120 m, `break_max_height_loss_m` unchanged (100): the old code would have floored
  at `max(40, 20) = 40`; this asserts convergence to ~50, not ~40.

**Counterfactuals run** (not assumed): reverted each of the three mechanisms in turn (the bank-cap
`min()`, the section-C `if` guard via `if false and ...`, and the `profile.break_floor_agl_m` →
`limits.floor_agl_m` swap), confirmed the corresponding new test(s) fail red for the stated reason,
then restored and confirmed green again. All three are reported below with the exact failure.

### Checks

**aircraft-layer/** (only subproject touched):

- `ruff format --check aircraft-layer/src aircraft-layer/tests`: pass (one reformat applied to the
  new test file before the final check — ruff's own preferred wrapping of a chained `.replace()`
  call).
- `ruff check aircraft-layer/src aircraft-layer/tests`: pass.
- `cd aircraft-layer && .venv/bin/mypy src`: pass, no issues (29 source files).
- `cd aircraft-layer && .venv/bin/mypy tests/test_flight_control_law.py`: pass, no issues.
- `luac5.1 -p` on both changed `.lua` files: pass (no output).
- `pytest aircraft-layer/tests/test_flight_control_law.py -v`: 75 passed, every test confirmed by
  exact name in unfiltered output (no `-k`).
- `pytest aircraft-layer/tests -q` (full subproject suite, not just the touched file): 1190 passed
  in ~113 s.

### Before/After Numbers (toy plant, shipped gains)

- **Bank/rate cap** (seeded `r_ref` = 38°/s, one frame):
  - 250 km/h: before (no cap) → stays ~38°/s (only the old 40°/s ceiling would ever apply, and 38
    is already under it). After → clamped to 14.02°/s (`law_turn_rate_at_bank(60°, 69.4 m/s)`).
  - 70 km/h: unaffected either way (~37.27°/s) — the bank-derived limit (50.07°/s) exceeds the old
    40°/s ceiling at this speed, so the cap never binds here; this is the card's own "below ~88
    km/h the cap does not bind" row.
- **Height gives first** (entry 150 m, rotor-RPM-warning-forced shortfall, 10 frames / 0.5 s):
  - Before (no class-aware routing, i.e. the pre-amendment always-full-`shortfall` behaviour,
    reproduced by the mutation above): `theta_i` = 0.1005° (nonzero, growing), `phi_d` = 4.298°.
  - After: `theta_i` = 0.0 (exactly, every frame), `phi_d` = 14.282° — more than 3× the bank, zero
    pitch-back, for the same raw `shortfall` (~0.485, unchanged by this amendment — only its
    routing changed).
  - Entry 50 m (at the floor) is unchanged from before either way: `theta_i` grows, `phi_d` =
    4.298° — the class-aware routing degrades to the old behaviour once height runs out, by
    construction.
- **Floor** (entry 120 m AGL, `break_max_height_loss_m` = 100, both unchanged):
  - Before (`limits.floor_agl_m` = 40): `max(40, 20) = 40`; toy-plant `h_ref` converges to ~43.06 m.
  - After (`profile.break_floor_agl_m` = 50): `max(50, 20) = 50`; converges to ~51.39 m.

### Notable Discoveries

- **`TestBreakTurnChannel`'s own documented limitation (placeholder `omega_heading` = 0.3 damps the
  realized rate far below any ceiling for a 90° step) applies equally to this amendment's cap** —
  confirmed by probing the full closed-loop toy plant at 120/180/250 km/h before writing any test:
  peak `|r_ref|` never exceeded ~9.96°/s at any of those speeds regardless of where the bank cap or
  the old 40°/s ceiling sat, so neither can be exercised through bank/rate growth in that scenario.
  The new cap tests instead seed `state.r_ref` directly (an already-established technique in this
  file, `TestUnparkMidTurnRateNeverSlammedToTheOrdinaryCeiling`) to isolate the one-frame clamp from
  this unrelated, pre-existing shaper slowness. Flagging for whoever eventually retunes
  `omega_heading`/`t_roll` (Flight M-A, per the plan's own note): once that happens, the full
  closed-loop toy plant may start exercising this cap too, which is fine — these seeded tests do not
  depend on it not happening, they only do not *require* it.
- **The engine-RPM-gated collective schedule (LV-1 amendment, section C) does not produce a large
  enough `shortfall` on its own** to exercise section C's height-gives mechanism at the shipped
  `k_collective` (0.08) against the shipped `alt_accel_cap_mps2` (1.9) — the nominal collective rate
  a saturated climb demand produces (~0.15/s) never approaches even the gentlest taper floor
  (`collective_rate_gentle_min_per_s`, 0.2/s), so `TestLV2HeightGivesFirst` instead uses the rotor-
  RPM-warning guard (`collective_ease_rate_near_rpm_warning`, -0.3) to force a real, reproducible
  shortfall — a different one of the "already capped" guards section C's own plan prose names, not
  a contrived mechanism. Noted in case a future break-roll-in flight trace shows the real engine-RPM
  schedule producing a comparably large shortfall in practice; this amendment's own fix (the
  routing, section C) does not care which guard produced the shortfall.
- **Both new profile constants (`break_floor_agl_m`, `break_height_give_band_m`) feed a division**
  (`height_margin_m / break_height_give_band_m`) that is not itself wire-received or bounds-checked
  (per `flight_profile.lua`'s own module docstring, unlike `FC_LIMIT_BOUNDS`) — guarded at the one
  place it actually matters (a non-positive band degrades to no height-giving, never a crash or a
  propagated NaN/Infinity) rather than auditing every profile constant's own finiteness, which this
  module has never done for any of its ~60 other fields. Said plainly here per the standing
  boundary-float rule, rather than silently matching the module's existing (unguarded) convention.

---

## Fix pass (2026-11-27, `review-lv2.md` required fix 1)

**Base**: dispatched at `7d63ecd2` on `fix/bl16-flight-epoch-bound` (branch `lv2-fix`, created in
this worktree's own object store — `lv2-fix` is not an ancestor of this worktree's starting point
`c0d8af86`, same situation `lv2-impl`/`lv2-plan` were each in). Harvesting onto
`feature/bl16-lift-vector-law` is the main loop's job.

**Finding**: `review-lv2.md` — the break's bank/rate cap (section B above) was built and tested
correctly in isolation, but as shipped it had almost nothing to cap: the `a_ref` formula feeding
`r_ref` toward the cap reused the *ordinary* `omega_heading` (0.3), and a critically-damped 2nd-
order step response's own peak rate (`err·ω/e`) is independent of any ceiling above it — so a bare
90° break error only ever drove the rate to ~9.95°/s at every speed, never reaching `break_max_
bank_deg`'s own cap (~14-29°/s at 120-250 km/h). The plan's "Effect, by speed" paragraph, the
`flight_profile.lua` comment and the card's own expectation line all stated the cap-bound numbers
as if this always happened.

### Fix

One new tunable, `break_omega_heading` (`flight_profile.lua`, first cut **1.0 rad/s**), read only
when `state.rate_override_deg_s ~= nil` (`flight_control.lua`'s heading-rate step, the same
`if`/`else` section B's own `rate_limit`/`accel_limit` selection already branches on) — a local
`omega_heading` now holds `profile.break_omega_heading` for a break, `profile.omega_heading`
(unchanged, 0.3) otherwise, and both the `a_ref` formula's two `omega_heading` terms read that
local instead of `profile.omega_heading` directly. `zeta` is shared and unchanged — the shaper's
own reference (`r_ref`/`psi_ref`) stays critically damped at the new bandwidth too (confirmed
numerically: a bare 90°/180° step through the idealized shaper alone, no plant lag, shows exactly
zero overshoot at `omega=1.0`, independent of the cap).

**1.0 rad/s, not a rounder or larger number, because**: its own natural (unclamped) peak rate for
a 90° error is `90·1.0/e ≈ 33.1°/s`, which exceeds every card speed's bank-derived cap (14.0-
29.2°/s at 250/120 km/h) — so the cap binds (97% at 120 km/h, fully at 180/250 km/h) rather than
being inert, without choosing a needlessly large bandwidth. No `tuning.py`-equivalent exists
outside body-layer (root `CLAUDE.md`); this is Lua-edited data like every other `flight_profile.lua`
field, not wire-received, so the standing boundary-float rule has no parse boundary to attach to
here (same posture `break_max_bank_deg`/`break_floor_agl_m`/`break_height_give_band_m` already
have, per the review's own note on those three).

**Cross-key coupling, flagged per the standing tuning-constants note**: `break_omega_heading`
interacts with `t_roll` (the roll-in accel limit, `rate_limit/t_roll`) and with `break_max_bank_deg`
itself — raising `break_omega_heading` further without also checking `t_roll` would make the
`a_ref` formula saturate the accel limit even harder and sooner (already true at 1.0: the initial
`a_ref` for a 90° error, ~90 deg/s², is well above the ~10-15 deg/s² accel limit at every card
speed, so the roll-in is accel-limited, not shaper-limited, from the first frame). Not guarded in
code (no per-pair invariant exists for this table, same as the rest of `flight_profile.lua`), said
here per the project's own "say so even if you do not guard it" rule.

### Known residual — found by toy-plant measurement, not assumed, not fixed

Running the fix through the project's own closed-loop toy plant (bank lag via a first-order filter
on `phi_d`, the same plant `TestBreakTurnChannel`/`_BREAK_PLANT_DRIVER` already use, **not** the
idealized shaper-only model above) shows the real heading overshoots the break's own target: ~5.4-
5.5° for a 90° break, ~6.9-10.1° for a 180° break-away, at 120/180/250 km/h — a single overshoot-
and-settle (confirmed by zero-crossing count: never more than one reversal of the heading error's
sign), not sustained oscillation. This is because the real bank cannot reverse instantly once the
shaper starts decelerating; it is a property of flying the turn *faster* (present at any `break_
omega_heading` above ~0.5 in a sweep I ran before settling on 1.0, growing with the bandwidth), not
a defect this fix introduces into the shaper itself (which, per the idealized check above, has zero
overshoot by construction). **Not addressed by this fix pass** — would need a lookahead/
anticipation term ahead of the deceleration phase, a separate mechanism outside this one-constant
fix's scope. Flagged on the LV-2 card's own watch line and the plan's own fix-pass section for a
live read against these measured figures; worth a look if a future stage wants to tighten roll-out
precision further.

### Before/After, toy-plant, shipped profile (closed loop through the real heading error)

| speed | before (90° break) | after (90° break) | ordinary 90° turn (unaffected) | after (180° break-away) |
|---|---|---|---|---|
| 120 km/h | peak bank ~33.6°, 90%-turn ~12.9 s (pre-fix, reproduced via a one-off `break_omega_heading=0.3` run for this table only) | peak bank ~56.2°, 90%-turn ~5.4 s, overshoot ~5.5° | peak bank ~22.8°, 90%-turn ~15.4 s, overshoot none | peak bank ~64.2°, overshoot ~10.1° |
| 180 km/h | peak bank ~45.0°, 90%-turn ~12.9 s | peak bank ~62.7°, 90%-turn ~6.2 s, overshoot ~5.4° | peak bank ~22.9°, 90%-turn ~20.9 s, overshoot none | peak bank ~64.2°, overshoot ~8.9° |
| 250 km/h | peak bank ~54.4°, 90%-turn ~12.9 s | peak bank ~64.2°, 90%-turn ~7.3 s, overshoot ~5.4° | peak bank ~22.9°, 90%-turn ~28.1 s, overshoot none | peak bank ~64.2°, overshoot ~6.9° |

"Before" column measured by temporarily setting `break_omega_heading` back to 0.3 (the old,
unintentional, shared value) in a scratch run against the shipped law, for this table only — not a
counterfactual kept in the repo. The ordinary-turn column is bit-identical before and after this
fix (confirmed by the full pre-existing regression suite, unmodified, still green, plus a new
pinned regression test), since `omega_heading` is read unchanged whenever `state.rate_override_
deg_s` is nil.

### Files Changed (this fix pass)

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — one new tunable,
  `break_omega_heading` (1.0), with its own comment covering the finding, the choice of 1.0, and
  the known residual; the adjacent `break_max_bank_deg` comment's stale "~32/21/15°/s" figure
  corrected to the real, now-measured toy-plant numbers.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — `law_update`'s heading-rate step
  (section B's own `if state.rate_override_deg_s ~= nil` branch): a local `omega_heading` now
  selects `profile.break_omega_heading` for a break, read by the `a_ref` formula in place of
  `profile.omega_heading` directly; the `else` (ordinary) path is untouched.
- `aircraft-layer/tests/test_flight_control_law.py`:
  - `_PROFILE`'s shared table gains `break_omega_heading = 1.0`, with a comment.
  - `TestLV2BreakBankRateCap::test_cap_does_not_bind_below_88_kmh_leaving_the_rate_free_to_move`
    (renamed from `..._leaving_the_seeded_rate_untouched`) — the old assertion ("close to the
    seeded 38") was a proxy for "not clamped" that depended on the *old*, unintentionally slow
    shaper barely moving the seed in one frame; with the fix that proxy no longer holds (the
    shaper's own pull is the point of the fix), so the assertion now checks the real property
    (strictly between both ceilings, exact one-frame value derived from the unclamped `a_ref`).
  - `TestBreakTurnChannel`'s and `TestLV2BreakBankRateCap`'s own class docstrings updated — both
    quoted the pre-fix "~10 deg/s, never approaching any ceiling" finding as current-tense; now
    marked superseded, with the real measured numbers and a pointer to why the seeded-`r_ref`
    technique in the latter class still isolates something useful even though the full closed
    loop can now also exercise the cap.
  - New `TestLV2BreakShaperBandwidth` (13 tests): cap binds through the real heading error (not a
    seeded `r_ref`) at 120/180/250 km/h; break faster than an ordinary turn at the same speed, at
    every card speed; 90° break and 180° break-away each settle with no sustained oscillation
    (bounded, documented overshoot, at most 2 zero-crossings); one pinned bit-identical regression
    for the ordinary (non-break) case.

### Tests Added (this fix pass)

- `TestLV2BreakShaperBandwidth::test_cap_binds_through_the_real_heading_error_not_a_seeded_r_ref`
  (×3 speeds) — closed-loop toy plant (bank lag included), asserts peak bank lands close to the 60°
  cap (>55°, <70°), not the ~22-23° an ordinary turn's own 20° ceiling would give.
- `TestLV2BreakShaperBandwidth::test_break_is_faster_than_an_ordinary_turn_at_the_same_speed`
  (×3 speeds) — time-to-90%-of-turn for a break is under half the ordinary case's, at every speed;
  this is the property `review-lv2.md` found to be FALSE as first shipped (both converged on the
  same shaper-limited peak).
- `TestLV2BreakShaperBandwidth::test_90_degree_break_settles_with_no_sustained_oscillation` /
  `..._180_degree_break_away_...` (×3 speeds each) — at most 2 zero-crossings of the heading error
  (one overshoot-and-settle, never ringing), overshoot bounded generously (15°/25°) above the
  measured figures, not re-asserting the measured number as a magic constant.
- `TestLV2BreakShaperBandwidth::test_ordinary_heading_change_is_bit_identical_to_before_this_fix_pass`
  — pins the ordinary-turn closed-loop result (max bank, overshoot, 90%-turn time, zero-crossings)
  against this fix pass's own measured values, so a future change that accidentally reads `break_
  omega_heading` for the ordinary case fails this test instead of passing it silently.

**Counterfactual run** (not assumed): commented out the `omega_heading = profile.break_omega_
heading` line (reverting to the pre-fix, always-`profile.omega_heading` behaviour), re-ran
`TestLV2BreakShaperBandwidth` — 11 of 13 tests failed red for the stated reason (cap-binds, faster-
than-ordinary, and both no-sustained-oscillation tests all failed; the ordinary-unchanged test and
one 180°-break-away speed's overshoot-bound check still passed, since a reverted shaper still
produces *some* overshoot-free, if much slower, motion). Restored the line, confirmed the file's
own checksum matched the pre-mutation checksum exactly, and the full suite green again (88/88).

### Checks (this fix pass)

**aircraft-layer/** (only subproject touched):

- `ruff format --check aircraft-layer/src aircraft-layer/tests`: pass.
- `ruff check aircraft-layer/src aircraft-layer/tests`: pass.
- `cd aircraft-layer && .venv/bin/mypy src`: pass, no issues.
- `cd aircraft-layer && .venv/bin/mypy tests/test_flight_control_law.py`: pass, no issues.
- `for f in aircraft-layer/dcs-export/*.lua; do luac5.1 -p "$f"; done` and the `Petrobrain/*.lua`
  files individually: pass (no output).
- `pytest aircraft-layer/tests/test_flight_control_law.py -v`: 88 passed, every test confirmed by
  exact name in unfiltered output (no `-k`).
- `pytest aircraft-layer/tests -q` (full subproject suite): pass, see handback report for the
  tail/count.

### Notable Discoveries (this fix pass)

- **The idealized shaper (no plant lag) and the realistic toy plant (with the project's own
  standard first-order bank lag) disagree on "no overshoot"** — the first has zero overshoot by
  the critically-damped design itself, independent of bandwidth; the second shows a bounded,
  growing-with-bandwidth overshoot that only becomes visible once the turn is fast enough to
  expose the lag. Both are real properties of different parts of the system (the control law's own
  reference trajectory vs. the aircraft's physical response to it) — worth keeping distinct in any
  future retune, rather than citing one toy-plant run as "the" overshoot figure for the whole
  mechanism.
- **A first draft of the closed-loop measurement for the 180° break-away case produced a
  nonsensical ~180° "overshoot"** from tracking the wrapped `psi_deg` directly through an exact-
  antipodal goal (`law_wrap180(180)` deterministically resolves to -180, so the aircraft turns the
  "long way" through 359°→270°→181°→180°, and a naive `psi - goal` comparison reads the wraparound
  as an enormous overshoot). Fixed by tracking the signed cumulative turn (`sum(r·dt)`, never
  wrapped) instead — flagging in case a future test over this same law hits the identical trap.
