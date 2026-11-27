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
