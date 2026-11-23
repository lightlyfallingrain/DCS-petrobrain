--[[
Petrobrain / flight_profile -- BL-16 lift-vector law, Stage **LV-0**
(`plans/flight-lift-vector/plan.md`): one per-aircraft profile table
holding every loop gain, time constant and estimator window
`flight_control.lua`'s law reads, so a user can retune flying behaviour
by editing data in one place rather than a module-level `local` buried
in the law's own code. `AC-B12` (`plans/ac-b12-export-modules/plan.md`):
one of the `dofile`-loaded module chunks `Export.lua` composes, loaded
BEFORE `flight_control` (it reads `flight_profile.ACTIVE` at call time).

**LV-0 scope**: every constant below that the five "pure" law functions
(`law_apply_goal`/`law_init_at_take`/`law_update`/`law_outputs`/
`law_turn_rate_at_bank`) already read was moved here **verbatim, values
unchanged** -- `tests/test_flight_control_law.py`'s toy-plant suite
and `tests/test_flight_control_lua.py`'s whole-module harness both
confirm bit-identical law output before and after this move. The
estimator fields (`law_hz`, `velocity_source`, the running-average
windows, the ball calibration) are new for LV-0's own estimator, which
runs in parallel and writes only new status fields -- nothing in
`law_update` reads them yet, so they cannot change today's flying
behaviour. **Not yet added** (first needed by LV-1/LV-2/LV-3, per the
plan's own staging): the regime blend speeds (25/50 km/h), the gain
schedule `G(V)` breakpoints, the per-manoeuvre priority orders (G), and
`rotor_dir`. Adding unused data now risks guessing ahead of what those
stages actually need.

Behaviour-affecting (every field here changes what Petrovich does), but
this subproject has no `tuning.py`-equivalent loader (root `CLAUDE.md`:
"outside body-layer the loader does not exist yet") -- would want the
X-T26 mechanism if one existed here. `lo`/`hi` bounds are not enforced
on this table at all (unlike `flight_control.lua`'s own `fc_limits`,
which IS wire-received and bounds-checked, `FC_LIMIT_BOUNDS`) -- this
is Lua-edited data, the same trust level every loop constant in this
codebase has had until now.

**Selection**: `M.ACTIVE = M.PROFILES["Mi-24P"]`. Selecting by
`LoGetSelfData().Name` is a one-line change once a second profile
exists (plan, "Affected Modules") -- not built now, since there is only
one aircraft.
--]]

local M = {}

M.PROFILES = {}

M.PROFILES["Mi-24P"] = {
    -- ---- Moved from `flight_control.lua`'s own module-level locals,
    -- values unchanged (LV-0). Every field below is read by one or more
    -- of the five pure law functions, which now take `profile` as an
    -- explicit trailing parameter.

    -- Critically-damped-or-overdamped factor for every position/rate
    -- shaper (`a_ref = omega^2*err - 2*zeta*omega*v_ref`) -- zeta>=1 is
    -- what the plan's own formula requires for "no overshoot". Kept at
    -- exactly 1 (critically damped), a judgement call, not a
    -- measurement.
    law_zeta = 1.0,

    -- Shaper bandwidths (rad/s) -- how fast each reference chases its
    -- own goal, before any rate/accel ceiling clips it. Owed by M0-E
    -- (the deliberate step-response probe, never flown).
    omega_heading = 0.3,
    omega_alt = 0.5,
    omega_speed = 0.15,

    -- Heading/turn channel's own accel limit is derived from this
    -- roll-in time (`r_max / T_ROLL`) rather than declared directly, so
    -- a tighter/looser `max_turn_bank_deg` (body-layer tunable, on the
    -- wire) does not need a matching accel-limit edit here. Owed by
    -- M0-E.
    t_roll = 2.0,
    heading_accel_cap_deg_s2 = 6.0,
    -- How hard the law pulls the real heading back onto its own
    -- reference path (`r_d = r_ref + k_psi*wrap(psi_ref - psi)`), in
    -- deg/s commanded per degree of drift. Owed by M0-E.
    k_heading_track = 0.3,

    -- Altitude/speed channel accel limits, before the commanded
    -- `max_climb_vs_mps`/`max_accel_mps2` ceilings (body-layer
    -- tunables) clip the resulting rate. Owed by M0-E.
    alt_accel_cap_mps2 = 1.0,
    speed_accel_cap_mps2 = 0.5,

    -- Feedback gains (`a_z,d = w_ref_dot + k_w*(w_ref-w) + k_h*(h_ref-h)`,
    -- `a_x,d = dV_ref_dot + k_v*(V_ref-V)`). Owed by M0-E.
    k_vs_error = 0.3,
    k_alt_error = 0.05,
    k_speed_error = 0.2,

    -- Lift-vector correction gains: collective rate per vertical-accel
    -- error (1/s per m/s^2), fore/aft tilt rate per along-track-accel
    -- error, and the extra tilt rate added once the collective is
    -- saturated. Owed by M0-E.
    k_collective = 0.08,
    k_tilt_from_ax = 0.04,
    k_tilt_from_az_saturated = 0.03,
    theta_min_deg = -15.0,
    theta_max_deg = 15.0,

    -- Lateral-tilt incremental correction gain (`phi_i_dot =
    -- K_r*(r_d - r)`) -- the kinematic term itself needs no gain, only
    -- this trim. Owed by M0-E.
    k_bank_increment = 0.5,

    -- Inner tilt loop: `u = T + k_theta*(target-measured) -
    -- k_rate*rate`, `T` integrating `k_theta_i*(target-measured)`.
    -- Units: axis command per degree of attitude error, and axis
    -- command per deg/s of body rate. Owed by M0-E -- the step
    -- response this loop closes on was never measured.
    k_theta = 0.03,
    k_theta_i = 0.015,
    k_q = 0.01,
    k_phi = 0.03,
    k_phi_i = 0.015,
    k_p = 0.01,

    -- Pedal coordination feedforward: `u_y_dot = K_cy*u_c_dot` (no
    -- slip-ball feedback term yet -- LV-1's own job). Sign check
    -- (sortie 2026-11-20): more collective eats further into the
    -- already-scarce right pedal margin on the Mi-24P; the sign below
    -- assumes positive command = right, the same unmeasured guess
    -- `pedal_limit_positive`'s own asymmetry already makes.
    k_pedal_from_collective_rate = 0.25,
    -- Right pedal is the scarce side (user: "not much right rudder
    -- left"); which *sign* of the axis is physically "right" was never
    -- measured (M0-E) -- magnitude only, applied to the positive side.
    pedal_limit_positive = 0.5,
    pedal_limit_negative = -1.0,
    -- While the pedal sits within this margin of its own positive
    -- limit, a rising collective command is rate-capped.
    pedal_near_limit_margin = 0.1,
    collective_rate_cap_near_pedal_limit = 0.3,

    -- Rotor RPM floor / retreating blade stall margins -- how much
    -- slack before the cap engages (the thresholds themselves are
    -- wire-carried body-layer tunables, `fc_limits.rotor_rpm_floor_pct`/
    -- `retreating_blade_stall_ias_kmh`).
    rotor_rpm_near_floor_margin_pct = 5.0,
    collective_rate_cap_near_rpm_floor = 0.0,
    retreating_blade_stall_margin_kmh = 20.0,
    collective_rate_cap_near_blade_stall = 0.0,

    -- Pedal-into-the-turn bias while a break's rate override is active
    -- -- judgement, owed by a flight.
    k_break_pedal_bias = 0.2,

    -- Turn-coordination pedal, proportional to the commanded turn rate
    -- `r_d` (sortie 2026-11-20: "turns but does not use pedals at all.
    -- Use pedals."). Sign assumption unmeasured (same positive-is-right
    -- convention as `pedal_limit_positive`'s asymmetry); applied only
    -- while no break override is active.
    k_turn_coord_pedal = 0.02,

    -- `a_x`/`a_z` fallback filter time constant (`LoGetAccelerationUnits`'
    -- own axis-to-body-frame mapping being unconfirmed) -- a filtered
    -- numerical derivative of IAS/vertical speed. LV-1 replaces this
    -- channel with the estimator's own acceleration; kept here
    -- unchanged for LV-0's bit-identical law output.
    tau_accel_filter_s = 0.3,

    -- Below this residual turn rate (deg/s), a turn-mode roll-out
    -- counts as "settled" and the law switches internally to heading
    -- mode, holding the heading the roll-out stopped at.
    turn_settle_deg_s = 0.3,

    -- ---- New for LV-0's estimator. Nothing in `law_update` reads these
    -- yet -- they cannot change today's flying behaviour; they govern
    -- only the shadow estimator and its status/trace output.

    -- Estimator and law update rate (plan, "Update rate, not every
    -- frame", user 2026-11-20 verbatim: "I'd say 30Hz would be plenty").
    -- First cut; LV-0's card measures whether this is too fast/slow for
    -- the noise floor.
    law_hz = 30.0,

    -- Which raw telemetry source the estimator differentiates/averages
    -- for world-frame velocity -- `"position"` (least-squares slope of
    -- `LoGetSelfData().Position`) or `"vector"` (running average of
    -- `LoGetVectorVelocity`). `"position"` is the default until LV-0's
    -- card row (e) confirms `LoGetVectorVelocity` matches `dP/dt` on
    -- all three axes (plan, section A).
    velocity_source = "position",

    -- Running-average window lengths (seconds), chosen as multiples of
    -- the blade-pass period so vibration falls in the average's null
    -- (plan, section A) -- first cut; LV-0's trace measures the real
    -- spectrum before LV-1 relies on them.
    w_v_s = 0.1,
    w_a_s = 0.2,
    w_a2_s = 0.1,
    -- Ball running-average window -- same order of magnitude as the
    -- acceleration window (`w_a_s`), since the ball's own update rate
    -- is in the same ballpark as the control args (~25 Hz) and the
    -- same vibration-averaging reasoning applies; no separate
    -- measurement exists yet (plan Risks: "the ball arg's own update
    -- rate is unknown").
    w_b = 0.2,

    -- Slip-ball calibration (2026-11-20 calibration flight,
    -- `aircraft-layer/research/2026-11-20-slip-ball-recon.md`): centred
    -- reads about +0.03, usable range is roughly +-0.5 (full pedal
    -- reached -0.38/+0.51), not +-1.
    ball_centre = 0.03,
    ball_usable_range = 0.5,
}

M.ACTIVE = M.PROFILES["Mi-24P"]

return M
