--[[
Petrobrain / flight_profile -- BL-16 lift-vector law
(`plans/flight-lift-vector/plan.md`): one per-aircraft profile table
holding every loop gain, time constant and estimator window
`flight_control.lua`'s law reads, so a user can retune flying behaviour
by editing data in one place rather than a module-level `local` buried
in the law's own code. `AC-B12` (`plans/ac-b12-export-modules/plan.md`):
one of the `dofile`-loaded module chunks `Export.lua` composes, loaded
BEFORE `flight_control` (it reads `flight_profile.ACTIVE` at call time).

**Stage LV-1** (`plans/flight-lift-vector/plan.md`, "The law, in
words" B-I, the ordinary chain in G): the law now steers a desired 3D
acceleration -- cyclic tilts the lift vector (feed-forward plus a slow
trim learnt from the estimator's own measured acceleration), collective
sets its length (feed-forward from the lift length the desired
acceleration needs, plus an integrator on vertical-acceleration error),
and the pedals fly the slip ball, always (U5 reverted: no deliberate
extra pedal in a turn or break). Every gain below that LV-0 moved
verbatim and LV-1 does not touch is unchanged; the fields LV-1 replaces
or adds are marked below. **No floor, no hand-back** (U1/U8, user:
"remove the limit. Any speed. What does not work, I will bring back and
we fix."): the only thing that protects low speed is the gain schedule
`G(V)` (`schedule_gain_min`/`schedule_full_speed_kmh`) and the envelope
guards that were already here.

**Not yet added** (first needed by LV-2/LV-3, per the plan's own
staging): the break/low-slow-RPM chains in G (height-gives-first order,
the recovery re-seating), the hover regime (`λ` blend, ground-speed
reference, the pedal yaw loop). Adding unused data now risks guessing
ahead of what those stages actually need.

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
    -- ---- Moved from `flight_control.lua`'s own module-level locals
    -- (LV-0), still read by LV-1's shapers (section B, "kept").

    -- Critically-damped-or-overdamped factor for every position/rate
    -- shaper (`a_ref = omega^2*err - 2*zeta*omega*v_ref`) -- zeta>=1 is
    -- what the plan's own formula requires for "no overshoot". Kept at
    -- exactly 1 (critically damped), a judgement call, not a
    -- measurement.
    law_zeta = 1.0,

    -- Shaper bandwidths (rad/s) -- how fast each reference chases its
    -- own goal, before any rate/accel ceiling (itself now scaled by
    -- `schedule_gain_min`/`schedule_full_speed_kmh` below, LV-1
    -- section B) clips it. Owed by M0-E (the deliberate step-response
    -- probe, never flown).
    omega_heading = 0.3,
    omega_alt = 0.5,
    -- LV-1 amendment (2026-11-25, fifth re-fly, `plans/flight-lift-
    -- vector/debug-2026-11-25.md`): raised 0.15 -> 0.5. The fourth
    -- re-fly's own raised caps/gains (B/C/D above) never ran into their
    -- own ceilings because the SPEED SHAPER itself was the bottleneck:
    -- at 0.15 rad/s this critically-damped filter's own acceleration
    -- demand never approached `speed_accel_cap_mps2`, so `a_f_d` only
    -- ever reached ~0.6-1.6 m/s^2 against a 1.9 cap, and settled over
    -- ~22-50 s against the user's own ~20 s figure. 0.5 rad/s lets the
    -- demand saturate the cap within ~1-2 s and hold it through the
    -- cruise, matching the user's own description ("pitch down... in
    -- 1-2s. Keep flying... until speed about 230, then start settling
    -- for 250"). Toy-plant measurement (debug report): settle time
    -- 150->250 drops from ~32-40 s to ~18-28 s depending on the plant's
    -- own pitch-to-accel gain, with no added hunting -- made safe by
    -- `law_update`'s new `dv_ref` braking-distance ceiling (step 1,
    -- speed), without which this same raise causes overshoot/chatter.
    omega_speed = 0.5,

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
    -- tunables) clip the resulting rate, and before LV-1's own
    -- `schedule_gain_min`/`schedule_full_speed_kmh` scale them by
    -- speed. Owed by M0-E.
    alt_accel_cap_mps2 = 1.0,
    -- LV-1 amendment (2026-11-24, fourth re-fly, Q2 "brisk"/E14): raised
    -- 0.5 -> 1.9 -- the user's own acceleration (150->250 km/h in ~20 s,
    -- sustained 1.6-1.9 m/s^2) against `MAX_ACCEL_MPS2` (body-layer,
    -- raised alongside this one so the dv_ref clamp does not sit below
    -- this cap). Reached in full only at/above `schedule_full_speed_
    -- kmh` (150), per the existing gain schedule above -- unchanged at
    -- low speed.
    speed_accel_cap_mps2 = 1.9,

    -- Feedback gains (`a_u,d = w_ref_dot + k_w*(w_ref-w) + k_h*(h_ref-h)`,
    -- `a_f,d = dV_ref_dot + k_v*(V_ref-V)`, section C). Owed by M0-E.
    k_vs_error = 0.3,
    k_alt_error = 0.05,
    k_speed_error = 0.2,

    -- ---- LV-1 (`plans/flight-lift-vector/plan.md`, "The law, in
    -- words" B): the gain schedule `G(V)` -- "about 0.3 at hover, 1.0
    -- from 150 km/h" (first cut; LV-0's card measures the real noise
    -- floor, not this schedule). `schedule_gain_min` is `G` at/below
    -- 0 km/h IAS; `G` rises linearly to 1.0 at `schedule_full_speed_
    -- kmh` and stays there above it. Multiplies the three accel caps
    -- above (`heading_accel_cap_deg_s2`/`alt_accel_cap_mps2`/`speed_
    -- accel_cap_mps2`) every frame -- "defined down to 0... gentlest
    -- value at the low end" (U1/U8: no hand-back, so the schedule is
    -- the only thing that makes LV-1 gentle below 50 km/h).
    schedule_gain_min = 0.3,
    schedule_full_speed_kmh = 150.0,

    -- ---- LV-1 (section D, "Lift-vector direction"): the cyclic's
    -- feed-forward-plus-trim split. `c_theta` is the fraction of the
    -- kinematic fore/aft tilt the feed-forward itself supplies (<=1
    -- per the plan -- "the disc tilt the fuselage needs to balance
    -- drag is unknown, so it is left to theta_i"); the remainder is
    -- learnt by the slow trim loop below. `k_phi_trim`/`k_theta_trim`
    -- give the trim loops a time constant of several seconds -- at
    -- least 3x slower than the estimator lag (~0.2 s) plus the
    -- attitude response, the plan's own stability argument (the toy
    -- plant checks this separation with the plant's gains deliberately
    -- wrong). First cut, owed by a flight.
    -- LV-1 amendment (2026-11-24, fourth re-fly, Finding 4b/Q2): raised
    -- 0.5 -> 0.85, toward the full kinematic tilt -- the user's own
    -- figure ("about atan(a/g), slightly more": ~12 deg of nose-down
    -- for 1.9 m/s^2, against atan(1.9/9.81) ~= 10.9 deg). Leaves theta_i
    -- a smaller but still real residual to learn (the fuselage-trim
    -- unknown, above), rather than reintroducing a model of it -- what
    -- changes is the onset (fast), not the several-second trim time
    -- constant below (unchanged, decision 5/"feedback, not a model").
    c_theta = 0.85,
    k_phi_trim = 0.02,
    k_theta_trim = 0.02,
    -- Anti-windup bound (section H): while the measured attitude is
    -- further than this from its own target (last frame's `phi_d`/
    -- `theta_d`), the trim loop is not following and holds rather than
    -- integrating a trajectory error that is really an attitude-loop
    -- lag.
    trim_hold_attitude_err_deg = 10.0,
    -- Anti-windup bound (section H): `phi_i` stops integrating in the
    -- direction that would push it past this magnitude. Deliberately
    -- tight -- `phi_i` is a secondary trim correction on top of the
    -- kinematic feed-forward `phi_ff`, never the primary driver of a
    -- real turn (a break's own 60-80 deg bank comes from `phi_ff`,
    -- which is not bounded at all). A wide bound lets a transient
    -- (e.g. an unpark mid-turn rolling back to level, where the
    -- measured acceleration lags the desired one for the whole
    -- roll-out) integrate a one-sided bias that never unwinds on its
    -- own once the aircraft settles -- confirmed with the toy plant,
    -- which could not converge within band at `60.0` and does at
    -- `8.0`. There is no longer a standing bank limit to check this
    -- against instead (F-M1).
    phi_i_bound_deg = 8.0,

    -- ---- LV-1 (section G, "Priority under limits", the ordinary
    -- chain): while the lift length is capped (collective saturated,
    -- RPM-floored or blade-stall-margined -- the same `collective_
    -- limited` flag E already computed), the shortfall is handed down
    -- speed, then turn rate, then height (U3). `k_theta_speed_give` is
    -- the extra nose-up rate per unit of capped collective rate
    -- (replaces `K_TILT_FROM_AZ_SATURATED`, "today's idea, now one
    -- entry in a chain"); `speed_give_capacity` is how much shortfall
    -- the pitch channel absorbs alone before turn rate also gives;
    -- `k_phi_give`/`phi_ff_min_scale` shrink the bank feed-forward
    -- once it does. Height gives last, by construction -- nothing
    -- here forces it, the vertical integrator (E) simply stops
    -- tracking once collective cannot rise further. First cut, owed by
    -- the LV-1/LV-2 cards.
    k_theta_speed_give = 0.5,
    speed_give_capacity = 0.05,
    k_phi_give = 4.0,
    phi_ff_min_scale = 0.3,
    -- Sortie 2026-11-20, user, verbatim (section G): "Slowing down is
    -- always pitch back and also less collective" -- a rule for the
    -- speed channel generally, not only while the lift length is
    -- capped: whenever the speed shaper is asking to decelerate
    -- (`a_f,d < 0`), the collective feed-forward/integrator step is
    -- biased down by this gain times the deceleration demand, on top
    -- of (never instead of) the ordinary vertical-error term.
    k_collective_speed_give = 0.1,

    -- ---- LV-1 (section E, "Lift-vector length"): feed-forward from
    -- the lift length the desired acceleration needs, plus an
    -- integrator on vertical-acceleration error (replaces the old `a_z`
    -- feedback-only `K_COLLECTIVE` loop). `k_lift_ff` (K_L) is
    -- deliberately small -- "a nudge, not a model": too small is a
    -- slower settle (the integrator supplies the rest), too large is a
    -- balloon. The LV-1 card's `K_L = 0` row flies the integrator
    -- alone, for comparison. `k_collective` (K_c) is reused from LV-0 --
    -- same field, new role (the vertical-accel-error integrator gain,
    -- section E, rather than the old `a_z`-feedback-error gain it
    -- replaced).
    k_lift_ff = 0.05,
    k_collective = 0.08,
    -- Pedal/RPM/blade-stall collective-rate caps, unchanged from LV-0 --
    -- still the thresholds `collective_limited`'s own flag (E, G) is
    -- computed against.
    pedal_near_limit_margin = 0.1,
    collective_rate_cap_near_pedal_limit = 0.3,
    rotor_rpm_near_floor_margin_pct = 5.0,
    collective_rate_cap_near_rpm_floor = 0.0,
    retreating_blade_stall_margin_kmh = 20.0,
    collective_rate_cap_near_blade_stall = 0.0,

    -- LV-1 amendment (2026-11-24, fourth re-fly, section C/Q1): the
    -- engine-RPM-gated collective-rate schedule, anticipatory above the
    -- reactive rotor-RPM-floor guard above (which stays exactly as it
    -- is, the backstop it was always meant to be). At/above this engine
    -- RPM, a collective increase is capped only by the existing
    -- physical/pedal-margin caps. Set to the user's own level-cruise
    -- reading, not the acceleration one: "in level flight, 170 km/h --
    -- engine RPM steady at ~93%... fast acceleration -- engine RPM
    -- ~98-100%... fast descent at collective full down -- engine RPM
    -- ~74%" (`docs/acceptance/2026-11-24-sortie-feedback.md`) -- the
    -- plan's own correction box names ~93% ("normal cruise output") as
    -- the "-> fast" threshold, not the ~98-100% reading from an
    -- acceleration already under way; **review-lv1-amendment.md,
    -- required fix 2** caught the first cut (97.0) sitting above
    -- ordinary level cruise, which would have tapered every normal
    -- level-flight collective increase to ~83% of nominal the moment
    -- U9 turns this schedule on. Only a further *increase* is ever
    -- gated (decreases, i.e. spooling down, are never the hazard).
    spooled_rpm_pct = 93.0,
    -- The other end of the taper -- the user's own "fast descent at
    -- collective full down" reading ("engine RPM ~74%"), the fully-
    -- spooled-down reference state. Below this, the increase rate
    -- tapers no further than `collective_rate_gentle_min_per_s`.
    engine_rpm_gentle_floor_pct = 74.0,
    -- The gentle minimum collective-increase rate (per second of the
    -- [-1, 1] axis) the taper above reaches at `engine_rpm_gentle_
    -- floor_pct` -- consistent with the user's own "~5 seconds" figure
    -- for a full collective swing starting from a spooled-down state
    -- (1.0 / 5.0 s ~= 0.2/s).
    collective_rate_gentle_min_per_s = 0.2,

    -- Inner tilt loop (section D, kept): `u = T + k_theta*(target-
    -- measured) - k_q*(Euler pitch rate)`, `T` integrating `k_theta_i*
    -- (target-measured)`; same form for roll with `k_phi`/`k_phi_i`/
    -- `k_p`. **LV-1 damps on Euler rates** (`est_euler_rates`, LV-0),
    -- not the body rates `q`/`p` read directly off the gyro -- "What
    -- reading the code turned up": a steady turn's own body pitch rate
    -- `q = psi_dot*sin(phi)` is not zero, so damping on it fights every
    -- coordinated turn. Units unchanged: axis command per degree of
    -- attitude error, and axis command per deg/s of Euler rate. Owed
    -- by M0-E -- the step response this loop closes on was never
    -- measured.
    theta_min_deg = -15.0,
    theta_max_deg = 15.0,
    k_theta = 0.03,
    k_theta_i = 0.015,
    k_q = 0.01,
    k_phi = 0.03,
    k_phi_i = 0.015,
    k_p = 0.01,

    -- ---- LV-1 (section F, "Pedals: fly the slip ball, always"): one
    -- integrator, one target, the ball's own centre -- never a heading
    -- or yaw-rate loop in forward flight (finding 2), and no deliberate
    -- extra pedal in a turn or break (U5 reverted). `k_ball_pedal`
    -- (K_beta) is the ball-centring integrator gain; `k_pedal_from_
    -- collective_rate` (reused from LV-0, unchanged role) is the
    -- torque feed-forward, `rotor_dir` giving its sign ("more
    -- collective -> more right pedal on the Mi-24P" -- user, 2026-11-20
    -- -- is `rotor_dir = +1`); `k_turn_coord_pedal` is a feed-forward
    -- nudge toward the turn at turn entry (same formula LV-0 had,
    -- reframed per F: its only job is to help the ball-centring
    -- integrator catch up, not to hold a deliberate ball offset --
    -- `K_BREAK_PEDAL_BIAS` and its own unwind bookkeeping are gone
    -- entirely, U5).
    --
    -- **Sign convention: positive pedal command = RIGHT pedal.** The
    -- first 2026-11-24 debug pass flipped all three gains to "positive
    -- = left"; the re-fly the same day showed that flip was wrong
    -- (user: "the pedal write is definetely reversed now, so apparently
    -- it was not before" -- the trace drove the command to -0.83 while
    -- the user saw heavy LEFT pedal), so it is reverted here
    -- (`plans/flight-lift-vector/debug-2026-11-24b.md`). The left pedal
    -- the first pass blamed on this loop came from the take itself: the
    -- pedal moves left at the instant of the take, before the law has
    -- changed its output (same debug report, question 1).
    k_ball_pedal = 0.3,
    -- LV-1 amendment (2026-11-24, fourth re-fly, section D/Q5): a
    -- proportional term on top of the integral one above -- the
    -- measured row-4 climb needed a pedal response the pure integrator
    -- could not give fast enough (ball grew to 0.12 over ~15 s before
    -- the integrator caught up). Same order of magnitude as the
    -- integral gain, first cut; added at `law_outputs` only (never
    -- integrated), mirroring `turn_coord_pedal`'s own "position overlay,
    -- recomputed fresh, never itself integrated" shape -- bit-exact at
    -- take is kept by backing its take-instant value out of `t_y`'s own
    -- seed, the same way `u_c_i` backs `u_c_ff` out of the captured
    -- collective.
    k_ball_pedal_p = 0.3,
    -- LV-1 amendment (2026-11-24, fourth re-fly, section D/Q5): raised
    -- 0.25 -> 0.6, the measured ~0.6-per-unit-collective-rate the row-4
    -- climb needed, pending the arg-42/-845 calibration row (U9).
    k_pedal_from_collective_rate = 0.6,
    rotor_dir = 1.0,
    k_turn_coord_pedal = 0.02,
    -- Right pedal is the scarce side (user: "not much right rudder
    -- left") -- the positive command side, so the tight bound is
    -- `pedal_limit_positive`.
    pedal_limit_positive = 0.5,
    pedal_limit_negative = -1.0,

    -- ---- Write bias (output stage, `plans/flight-lift-vector/debug-
    -- 2026-11-24c.md`, finding 1): in flight the pedal write lands a
    -- near-constant offset away from the command -- `arg 1103 ~= 0.32 -
    -- command` at every take of the 2026-11-24 data flight, both seats,
    -- 40-61 m/s, collective 0.26-1.0 (0 on the ground, M0-B; ~0.16 on
    -- probe v2). Cause in DCS unknown. `flight_control.lua` writes
    -- `intended + bias` (command domain, positive = right pedal) so the
    -- pedal sits where the law means it: the seed makes the first frame
    -- of a take bumpless; the bias is then learnt online from
    -- `written - measured` while the write is steady, and kept across
    -- takes for the mission. Only axes listed in `write_bias_seed`
    -- take part; pitch, roll and collective follow their commands with
    -- no offset in the same data, so they are not listed.
    write_bias_seed = { pedals = 0.32 },
    write_bias_bound = 0.5,       -- |bias| never exceeds this
    write_bias_tau_s = 3.0,       -- learning time constant
    write_bias_settle_s = 1.0,    -- write steady this long before learning (pedal 98% settled, M0-B)
    write_bias_settle_band = 0.02, -- "steady" = within this of where it settled

    -- Below this residual turn rate (deg/s), a turn-mode roll-out
    -- counts as "settled" and the law switches internally to heading
    -- mode, holding the heading the roll-out stopped at; also the
    -- threshold below which the turn-entry pedal nudge (F) is zero
    -- rather than a vanishing non-zero value.
    turn_settle_deg_s = 0.3,

    -- ---- Estimator (LV-0). Nothing here changed by LV-1.

    -- Estimator and law update rate (plan, "Update rate, not every
    -- frame", user 2026-11-20 verbatim: "I'd say 30Hz would be plenty").
    -- First cut; LV-0's card measures whether this is too fast/slow for
    -- the noise floor. **Both the estimator's own `LoGet*` reads
    -- (`est_due`) and `law_update` itself (`law_due`) are gated to this
    -- rate, from LV-1 on (review-lv1.md, required fix 1)** -- on
    -- different frames from each other, never the same one; `law_
    -- outputs` still runs and writes every frame.
    law_hz = 30.0,

    -- Which raw telemetry source the estimator differentiates/averages
    -- for world-frame velocity -- `"position"` (least-squares slope of
    -- `LoGetSelfData().Position`) or `"vector"` (running average of
    -- `LoGetVectorVelocity`). `"vector"` for LV-1 on (decided from the
    -- LV-0 sortie trace, main loop, `docs/acceptance/
    -- 2026-11-23-sortie-feedback.md`, "Row (e) answered": same axes and
    -- signs as the position slope across every row the card flew,
    -- including sideslip, with the only offsets (~0.2-0.4 m/s) in the
    -- two steep turns -- the position slope's own centre-of-window lag,
    -- which `LoGetVectorVelocity` does not carry). `"position"` stays
    -- selectable (plan, section A).
    velocity_source = "vector",

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
