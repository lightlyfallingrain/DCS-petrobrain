--[[
Petrobrain / flight_control -- BL-16 mode 1 (unparked, raw axes):
Petrovich holds the cyclic/collective/pedal axes from where the pilot
left them, overpowering the player's physical stick with a per-frame
write (`LoSetCommand` 2001/2002/2003/2087), the same mechanism the
9K113 sight override already uses (`sight.lua`'s `SERVO_WOBBLE`).
`AC-B12` (`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-
loaded module chunks `Export.lua` (the loader) composes, own 200-local
budget.

`plans/flight-control/plan.md`, "Revised 2026-11-18 -- mode 1 (unparked,
raw axes) re-cut", Stage **M2** (the controller) on top of M1's own seam
and handover: a spoken goal (`cmd="goal"`) is bounds-checked, stored in
the `fc_goal_*` wire-echo locals (unchanged from M1), and now also
drives `fc_law` -- `law_apply_goal`/`law_init_at_take`/`law_update`/
`law_outputs`, a handful of pure functions over an explicit state
table (never the module's own flat locals) so a toy-plant test can
drive them with no DCS mock at all (`plans/flight-control/plan.md`:
"the law above, as pure functions over a state table so luajit can
test them"). Output is the law's own shaped command, still through the
same per-frame write stage M1 built (rate-limit, saturate, the always-
on wobble, `LoSetCommand`) -- at the instant of a take, every law
integrator is solved so the first frame's output equals the captured
value exactly ("the output is continuous at take, bit-exact",
Decision 24), and only diverges from there as the shaper and lift-
vector corrections converge the aircraft onto its goal. **Every gain in
the law is a first-cut placeholder** -- M0-E (the deliberate step-
response probe) was never flown; see the "M2 control law constants"
block below for what each one would want measured and why it is not
yet. M3 (terrain floor) and M4 (SAU) are not built here.

Depends on `core` (loaded first, `safe_call`/`debug_log`/the JSON
extract helpers) and, read-only, `ai_pilot_wheel.is_parked`/`stick_park_
raw` -- never writes into that module's own state. If `ai_pilot_wheel`
itself failed to load, `is_parked()` is unknown and this module never
takes (named in the plan so the Implementer cannot pick the wrong
default): a park/unpark edge can only be detected by comparing against a
known previous state, so "unknown" is treated the same as "stay off",
never as a licence to assume unparked.

**Capture source, corrected after M0-J (flight 9,
`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`)**:
neither a voice take nor an unpark take reads the camera seat
(`ai_pilot_wheel.player_seat`) at all any more -- Decision 25's own
"the player's seat set" wording for a voice take is wrong (the camera
seat can read a seat whose arg set is all zero, while the other seat's
args hold the live inputs, before an explicit handover). A voice take
captures whichever seat's args are actually non-zero, falling back to
the last steady (non-cross-faded) set if both are; an unpark take
captures the pilot set from the last frame `stick_park_raw()` read
fully stowed, tracked continuously while `armed`, since the two arg
sets have already begun a ~1.5 s cross-fade by the time `is_parked()`'s
own edge fires.

**The Mi-24P arg/cmd/sign table below is partly measured, partly still
unverified.** 1100-1103/1110-1113 are read-only cockpit animation args
(not a write channel); `LoSetCommand` 2001/2002/2003/2087 are the real
control-function channel for pitch/roll/pedal/collective, confirmed
against the user's own DCS binding file (scaffold probe `Export.probe-
control-command-hold.lua` v2, flown 2026-11-01, for the mechanism; the
binding file for the exact ids). **M0-B, flown 2026-11-18, confirmed on
a second flight** (`aircraft-layer/research/2026-11-18-bl16-m0-flight-
axes-findings.md`): the pedal write works at `SIGN.pedals = -1.0`, scale
1 -- command 2003 = `-arg 1103` holds the arg exactly at the commanded
value (±0.05/±0.10 both confirmed), arg 1103 reads the full -1..+1
range, and the arg's own response to a step is first-order (not rate-
limited): τ ≈ 0.25 s with the pedal damper on (≈ 0.2 s off), 98-99%
settled by 1 s for every step size tried; the adjustable stops do not
limit the write. Pedal is enabled below on that measurement. **M0-C,
flown 2026-11-18 (flight 5): command 2004 does NOT move the
collective** -- arg 1102 stayed at -0.1728 for 11 s of writes, because
2004 is `Throttle (Collective)`, the engine throttle, not the flight-
control collective axis; the real id is 2087 (`iCommandPlaneCollective`,
the same binding file). **M0-C re-flown (flight 6, 2026-11-18) against
the corrected id: `SIGN.collective = -1.0`, scale 1, same shape as
pedal** (command = `-arg 1102`). Entered below; `FC_AXES_ENABLED.
collective` is kept **false** regardless -- M0-C's sign/scale is now
measured but its step-response lag and VS behaviour are not (the same
two figures M0-B needed before pedal was enabled), so this is a
judgement call extending pedal's own "measure the whole response before
flipping the flag" bar to collective, not a literal reading of the
plan's "sign and scale" wording. Flag this for confirmation at review.
**Flight 6 also measured M0-F (plan, Decision 4): once a write stops,
the arg holds Petrovich's last-commanded value until the player
physically moves that control** -- arg 1102 sat 16+ s with the lever
untouched after `release`. Confirmed for collective; pitch/roll/pedals
are still owed. This matches Decision 4 exactly ("the release jump is
not handled, the pilot matches his controls") and needs no code change
-- `handle_flight_control_command`'s `"release"` branch already just
stops calling `write_outputs()`, it never writes a last value or reads
the physical stick. M0-D (the stirred-control go/no-go) is still owed
for the whole mode -- this module is built and tested ahead of it per
the plan's own instruction, not flown until it passes (U7).
--]]

local M = {}

-- Cockpit draw args per seat: pitch, roll, collective, pedals (read
-- only -- these track the *physical* controls, they are never written).
-- Copied verbatim from the scaffold probe's `SEAT_ARGS` rather than
-- re-guessed.
local SEAT_ARGS = {
    pilot = { pitch = 1100, roll = 1101, collective = 1102, pedals = 1103 },
    operator = { pitch = 1110, roll = 1111, collective = 1112, pedals = 1113 },
}

-- DCS control functions (`Scripts/Export.lua`, `iCommandPlane*`) -- the
-- actual write channel, confirmed against the user's own DCS binding
-- file for all four axes (module header). 2004 ("Throttle (Collective)",
-- the engine throttle) is deliberately not here -- it was tried in M0-C
-- and confirmed to do nothing to the flight-control collective axis;
-- 2087 (`iCommandPlaneCollective`) is the real one.
local CMD = { pitch = 2001, roll = 2002, pedals = 2003, collective = 2087 }

-- command = SIGN * captured-arg. pitch/roll are probe v2's own unverified
-- guesses, flip once M0-E reports; pedals = -1.0 is measured (M0-B,
-- 2026-11-18); collective = -1.0 is measured too (M0-C re-fly, flight 6,
-- 2026-11-18, module header) -- never written while `FC_AXES_ENABLED.
-- collective` is false (its lag/VS response are the still-owed figures).
local SIGN = { pitch = 1.0, roll = 1.0, pedals = -1.0, collective = -1.0 }

-- Per-axis enable flags (plan, M1 bullet: "a per-axis enable flag that
-- defaults off for pedal and collective until M0-B and M0-C" -- each
-- axis gated on its own probe). Pitch/roll are the axes probe v2
-- actually exercised; pedals is enabled on M0-B's own measurement
-- (module header, both sign/scale AND the step-response lag). collective
-- stays disabled: its sign/scale is now measured (flight 6) but its own
-- lag/VS response is not, and pedal's own bar was the whole response,
-- not sign/scale alone -- a judgement call, flagged in the Implementer's
-- report. An unmapped/unmeasured axis is left entirely with the player
-- (safe), never written with a guessed sign/scale.
local FC_AXES_ENABLED = { pitch = true, roll = true, pedals = true, collective = false }

-- `UNPARK_TAKE_ENABLED` -- on by default now that M0-J passes with the
-- last-fully-stowed capture fix below (flight 9). While off, an unpark
-- from `armed` always refuses (`fc_refuse_cause = "disabled"`) and the
-- player keeps the stick, exactly as before M0-J -- kept as a flag, not
-- removed, so a live regression can still be switched off without a
-- redeploy.
local UNPARK_TAKE_ENABLED = true

-- An arg reading at or above this is "fully stowed" -- the threshold
-- the unpark-take capture tracks against (M0-J, flight 9), distinct
-- from `ai_pilot_wheel`'s own, lower `AI_PILOT_PARK_THRESHOLD` (0.9)
-- that decides `is_parked()` itself. The two arg sets are already
-- cross-fading for ~1.5 s by the time the lower threshold's edge fires,
-- so capturing at the edge reads a partly-faded pilot set; this
-- threshold is deliberately close to fully stowed (1.0) so the tracked
-- capture is taken well before the fade starts. Behaviour-affecting (set
-- too low, it reproduces flight 9's mid-fade capture) but this subproject
-- has no `tuning.py`-equivalent loader -- would want the X-T26 mechanism.
local STOWED_THRESHOLD = 0.99

-- Below this, a seat's summed axis magnitude reads as "centred/idle",
-- not "live" -- the voice-take capture rule (M0-J, flight 9) uses it to
-- tell a genuinely-flown seat from one reading exact/near-zero because
-- nobody has requested control there yet. Behaviour-affecting (it picks
-- the seat a take copies from) but this subproject has no
-- `tuning.py`-equivalent loader -- would want the X-T26 mechanism.
local LIVE_SEAT_ZERO_EPS = 0.01

-- The 9K113's own invisibility bound (`plans/9k113-sight-pointing/
-- plan.md`, `SERVO_WOBBLE`), reused here per the plan's own Decision 6
-- REVISED/amended-2026-10-31 instruction: every flight-axis write
-- carries this from the first frame, unconditionally. Behaviour-
-- affecting (a visible twitch would be a real defect) but this
-- subproject has no `tuning.py`-equivalent loader (root `CLAUDE.md`:
-- "outside body-layer the loader does not exist yet") -- would want the
-- X-T26 mechanism if one existed here.
local FLIGHT_WOBBLE = 0.001

-- A pause (or a huge frame-time jump, e.g. a mission load stall) freezes
-- everything except the wobble write itself (plan's own pause row).
local DT_CAP = 2.0

-- Safety margins the envelope check applies on top of the commanded
-- limits -- not behaviour-affecting on their own (they only decide how
-- much slack the self-release gets before firing), so kept as plain
-- Lua locals rather than wire-carried tunables. No bank margin any
-- more (mode-1 batch, F-M1: "remove the 30 degree limit. Set no limit
-- for now" -- there is no standing bank to check a margin against;
-- the rotor envelope, Decision 30, is the real protection in a break).
local ENV_IAS_MARGIN_KMH = 10.0
local ENV_HOLD_S = 3.0

-- Hard-coded startup defaults, overwritten by the first `flight_control`
-- message's own `limits` (every message carries them, per the plan's
-- "Wire" section) -- these only matter for the handful of frames before
-- body-layer's first send, and are deliberately conservative.
local fc_limits = {
    takeover_level_bank_deg = 5.0,
    floor_agl_m = 40.0,
    min_ias_kmh = 80.0,
    max_ias_kmh = 280.0,
    on_ground_agl_threshold_m = 10.0,
    arm_lease_s = 3.0,
    -- M2 additions (plan: "Behaviour constants -- where each lives" --
    -- body-layer `tuning.py`, sent in every message's `limits`). Startup
    -- defaults only, deliberately conservative/narrow until body-layer's
    -- own first send; `belief.flight_control.flight_control_limits`
    -- carries the real (tunable) values. No `max_bank_deg` any more
    -- (mode-1 batch, F-M1).
    max_turn_bank_deg = 20.0,
    max_climb_vs_mps = 5.0,
    max_accel_mps2 = 1.0,
    speed_band_frac = 0.10,
    alt_band_frac = 0.10,
    alt_band_min_m = 10.0,
    turn_rate_band_frac = 0.10,
    heading_band_deg = 5.0,
    -- Mode-1 batch additions (plan, "Revised 2026-11-19", Decisions
    -- 29-31) -- same "conservative startup default, body-layer's own
    -- `tuning.py` carries the real value" posture as the M2 additions
    -- above.
    rotor_rpm_floor_pct = 85.0,
    retreating_blade_stall_ias_kmh = 250.0,
    break_max_height_loss_m = 100.0,
    vrs_ias_threshold_kmh = 50.0,
    vrs_max_descent_mps = 4.0,
}

-- `limits` fields this module actually reads, with the hard hard
-- ceilings `Export.lua` checks a received value against before ever
-- trusting it (the plan's own `AC-B14` lesson: body-layer's own API
-- layer validates too, but this module does not trust that alone).
local FC_LIMIT_BOUNDS = {
    takeover_level_bank_deg = { lo = 0.0, hi = 90.0 },
    floor_agl_m = { lo = 0.0, hi = 2000.0 },
    min_ias_kmh = { lo = 0.0, hi = 500.0 },
    max_ias_kmh = { lo = 0.0, hi = 500.0 },
    on_ground_agl_threshold_m = { lo = 0.0, hi = 100.0 },
    -- security-m1-m2.md Finding B, change-request round: this limit IS
    -- a safety margin (U10's park-then-unpark escape window for a dead
    -- Petrobrain), not a flight-behaviour tuning knob like every other
    -- entry here -- it gets its own tight ceiling rather than sharing
    -- the generous 60 s sanity bound, so any accepted message (LAN or
    -- body-layer's own restart-time resend) can widen the 3 s default
    -- by at most ~3x, never to a full minute. Must match body-layer's
    -- own `tuning.py` `ARM_LEASE_S` `hi` bound exactly, or a legitimate
    -- user override there would be silently rejected whole-message at
    -- this layer instead of applied.
    arm_lease_s = { lo = 0.0, hi = 10.0 },
    -- No `max_bank_deg` entry any more (mode-1 batch, F-M1: "remove the
    -- 30 degree limit") -- removed from the wire entirely, not
    -- widened, so a stale sender's value finds nothing here to accept.
    max_turn_bank_deg = { lo = 0.0, hi = 60.0 },
    max_climb_vs_mps = { lo = 0.0, hi = 20.0 },
    max_accel_mps2 = { lo = 0.0, hi = 10.0 },
    speed_band_frac = { lo = 0.0, hi = 1.0 },
    alt_band_frac = { lo = 0.0, hi = 1.0 },
    alt_band_min_m = { lo = 0.0, hi = 100.0 },
    turn_rate_band_frac = { lo = 0.0, hi = 1.0 },
    heading_band_deg = { lo = 0.0, hi = 90.0 },
    -- Mode-1 batch additions, same hard-ceiling posture as the M2 ones
    -- above.
    rotor_rpm_floor_pct = { lo = 0.0, hi = 100.0 },
    retreating_blade_stall_ias_kmh = { lo = 0.0, hi = 500.0 },
    break_max_height_loss_m = { lo = 0.0, hi = 1000.0 },
    vrs_ias_threshold_kmh = { lo = 0.0, hi = 200.0 },
    vrs_max_descent_mps = { lo = 0.0, hi = 50.0 },
}

--[[ M2 control law constants (plan: "The control law, as a first
implementation should follow it" -- "written against an unmeasured
plant... the gains, limits and signs are placeholders until M0-E and
M0-A give real numbers"). One commented block, per the plan's own
"Behaviour constants" table ("Export.lua, one commented block... how
the loop closes, not what he does. Would want the X-T26 mechanism;
outside body-layer it does not exist"). M0-A (`aircraft-layer/research/
2026-11-18-bl16-m0-flight-axes-findings.md`) measured pedal tau~=0.25s
and collective tau~=0.1s, but gave no step-response data for pitch/
roll/pedal-yaw/collective-vs-VS gain, and M0-E (the deliberate step-
response probe) was never flown -- every gain below is a first-cut
guess sized only so the toy-plant tests show convergence without
ringing, not a measurement. All flagged "owed by M0-E" in the
Implementer's report; Flight M-A and M5 retune them. ]]--

-- Critically-damped-or-overdamped factor for every position/rate
-- shaper (`a_ref = omega^2*err - 2*zeta*omega*v_ref`) -- zeta>=1 is
-- what the plan's own formula requires for "no overshoot" (page 3's
-- S-curve). Kept at exactly 1 (critically damped, the fastest
-- non-overshooting response) rather than over-damped, a judgement
-- call, not a measurement.
local LAW_ZETA = 1.0

-- Shaper bandwidths (rad/s) -- how fast each reference chases its own
-- goal, before any rate/accel ceiling clips it. Owed by M0-E.
local OMEGA_HEADING = 0.3
local OMEGA_ALT = 0.5
local OMEGA_SPEED = 0.15

-- Heading/turn channel's own accel limit is derived from this roll-in
-- time (the plan's own "r_max / T_ROLL") rather than declared directly,
-- so a tighter/looser `max_turn_bank_deg` (body-layer tunable) does not
-- need a matching accel-limit edit here. Owed by M0-E (the airborne
-- yaw/roll response to a pedal/cyclic step was never flown).
local T_ROLL = 2.0
local HEADING_ACCEL_CAP_DEG_S2 = 6.0
-- How hard the law pulls the real heading back onto its own reference
-- path (plan step 2: `r_d = r_ref + k_psi*wrap(psi_ref - psi)`), in
-- deg/s commanded per degree of drift. Owed by M0-E.
local K_HEADING_TRACK = 0.3

-- Altitude/speed channel accel limits, before the commanded `max_
-- climb_vs_mps`/`max_accel_mps2` ceilings (body-layer tunables) clip
-- the resulting rate. Owed by M0-E.
local ALT_ACCEL_CAP_MPS2 = 1.0
local SPEED_ACCEL_CAP_MPS2 = 0.5

-- Plan step 2's own feedback gains (`a_z,d = w_ref_dot + k_w*(w_ref-w) +
-- k_h*(h_ref-h)`, `a_x,d = dV_ref_dot + k_v*(V_ref-V)`). Owed by M0-E.
local K_VS_ERROR = 0.3
local K_ALT_ERROR = 0.05
local K_SPEED_ERROR = 0.2

-- Lift-vector correction gains (plan step 3): collective rate per
-- vertical-accel error (1/s per m/s^2), fore/aft tilt rate per along-
-- track-accel error, and the extra tilt rate step 3 adds once the
-- collective is saturated (same-sign error) -- "the lift vector is the
-- only control if collective is at limit". Owed by M0-E.
local K_COLLECTIVE = 0.08
local K_TILT_FROM_AX = 0.04
local K_TILT_FROM_AZ_SATURATED = 0.03
local THETA_MIN_DEG = -15.0
local THETA_MAX_DEG = 15.0

-- Lateral-tilt kinematic term (plan step 3: `phi_d = atan(V_t*r_d/g) +
-- phi_i`) needs no gain of its own -- it is turn kinematics, not a fit
-- -- but the incremental correction `phi_i` does: `phi_i_dot = K_r*(r_d
-- - r)`. Owed by M0-E.
local K_BANK_INCREMENT = 0.5
local GRAVITY_MPS2 = 9.81

-- Inner tilt loop (plan step 4): `u = T + k_theta*(target-measured) -
-- k_rate*rate`, with `T` integrating `k_theta_i*(target-measured)`.
-- Units: axis command per degree of attitude error, and axis command
-- per deg/s of body rate. Owed by M0-E -- the step response this loop
-- closes on was never measured.
local K_THETA = 0.03
local K_THETA_I = 0.015
local K_Q = 0.01
local K_PHI = 0.03
local K_PHI_I = 0.015
local K_P = 0.01

-- Pedal coordination (plan step 5): `u_y_dot = K_beta*beta + K_cy*u_c_
-- dot`. `K_beta`'s own term is NOT implemented -- `LoGetSlipBallPosition`
-- exists (confirmed in the DCS Control API reference) but its return
-- shape/units were never measured by any probe (M0-A did not read it;
-- `aircraft-layer/research/2026-10-26-bl16-flight-control-desk-recon.md`
-- names this an open item), so guessing a unit conversion here risks a
-- wrong-sign pedal command, worse than omitting the term. The pedal
-- axis therefore runs on the collective-coupling feedforward alone
-- until a probe measures the slip ball. Owed by M0-E and a slip-ball
-- probe both.
local K_PEDAL_FROM_COLLECTIVE_RATE = 0.25
-- The right-pedal limit is smaller than the left one (user: "not much
-- right rudder left"), but which *sign* of the pedal axis is
-- physically "right" was never measured (M0-E) -- this asymmetry is
-- therefore a guess at the magnitude only, applied to the
-- positive-command side; Flight M-A confirms or flips it.
local PEDAL_LIMIT_POSITIVE = 0.5
local PEDAL_LIMIT_NEGATIVE = -1.0
-- While the pedal sits within this margin of its own positive limit, a
-- rising collective command is rate-capped (plan step 5: "a collective
-- increase is rate-limited while the right pedal is near its limit").
local PEDAL_NEAR_LIMIT_MARGIN = 0.1
local COLLECTIVE_RATE_CAP_NEAR_PEDAL_LIMIT = 0.3

-- Rotor RPM floor and retreating blade stall (mode-1 batch, explore-
-- notes 2026-11-18/19) -- "the rotor rpm drop below minimum and
-- retreating blade stall are things to avoid in any Mode 1 state,
-- whatever we are doing... high collective leads to RPM drop... high
-- blade angle and high speed lead to retreating blade stall." Both
-- margins are judgement (how much slack before the cap engages), same
-- class as `ENV_IAS_MARGIN_KMH`/`K_*` above -- the thresholds
-- themselves (the RPM floor, the stall IAS) are the user's own
-- numbers, wire-carried, in `limits` (`ROTOR_RPM_FLOOR_PCT`/
-- `RETREATING_BLADE_STALL_IAS_KMH`, body-layer's `tuning.py`).
local ROTOR_RPM_NEAR_FLOOR_MARGIN_PCT = 5.0
local COLLECTIVE_RATE_CAP_NEAR_RPM_FLOOR = 0.0
local RETREATING_BLADE_STALL_MARGIN_KMH = 20.0
local COLLECTIVE_RATE_CAP_NEAR_BLADE_STALL = 0.0

-- Mode-1 batch, Decision 27's own pedal-into-the-turn bias while a
-- break's rate override is active -- judgement, owed by Flight M-A.
local K_BREAK_PEDAL_BIAS = 0.2

-- Rotor RPM proxy (mode-1 batch, explore-notes 2026-11-18/19, Q-M1-1).
-- "dummy": a fixed stand-in value, the user's own fallback. "arg_
-- proxy": reads the live cockpit draw arg recon found (`aircraft-
-- layer/research/2026-11-19-mi24p-readable-args-recon.md`) via the
-- same `GetDevice(0):get_argument_value` already used for other
-- draw-arg reads in this codebase (`ai_pilot_wheel.lua`'s stick-park
-- read) -- not a new, unverified Lua call pattern, only a new arg id
-- with unconfirmed calibration. One flag flips the source; nothing
-- else in the law changes. Ships with `"dummy"` -- the swap to
-- `"arg_proxy"` is a one-line flip once a flight confirms arg 42
-- tracks rotor RPM and resolves its calibration.
local ROTOR_RPM_SOURCE = "dummy" -- "dummy" | "arg_proxy"
local ROTOR_RPM_ARG_PILOT = 42
local ROTOR_RPM_DUMMY_PCT = 90.0
-- Raw-arg-to-%RPM scale (main-loop amendment 2026-11-19): user, "very
-- likely that is value * 100 = rotor rpm per cent. Unless the dial
-- goes to over 100%, that has to be checked in cockpit." Correct this
-- one constant once the cockpit dial's top mark is confirmed.
local ROTOR_RPM_ARG_SCALE_MAX_PCT = 100.0

local function read_rotor_rpm_pct()
    if ROTOR_RPM_SOURCE == "dummy" then
        return ROTOR_RPM_DUMMY_PCT, true
    end
    local raw = safe_call(function() return GetDevice(0):get_argument_value(ROTOR_RPM_ARG_PILOT) end)
    if type(raw) ~= "number" or raw ~= raw then
        return ROTOR_RPM_DUMMY_PCT, false
    end
    return raw * ROTOR_RPM_ARG_SCALE_MAX_PCT, true -- calibration unconfirmed -- owed by the next flight
end

-- Accelerations are not read from a dedicated sensor (M0-A: `LoGet
-- AccelerationUnits`' own axis-to-body-frame mapping is unconfirmed) --
-- `a_x`/`a_z` are a filtered numerical derivative of IAS/vertical speed
-- instead (plan's own fallback: "filtered dV/dt and dw/dt"). This is
-- the filter's own time constant.
local TAU_ACCEL_FILTER_S = 0.3

-- Output-stage rate limit (axis units per second) -- a defensive cap
-- on how fast any written axis value may move frame to frame, on top
-- of whatever the law's own integrators already produce; not itself
-- behaviour the pilot would tune (it only guards against a shaper bug
-- producing a jump), so kept generous.
local OUTPUT_RATE_LIMIT_PER_S = 4.0

-- Below this residual turn rate (deg/s), `level_off`'s own turn-mode
-- roll-out counts as "settled" and the law switches internally to
-- heading mode, holding the heading the roll-out stopped at (plan:
-- "`level_off` goes through turn mode at 0. When `r_ref` reaches 0,
-- Lua switches to heading mode").
local TURN_SETTLE_DEG_S = 0.3

-- Mode-1 law state, nil whenever `fc_mode` is not "active" (created at
-- `law_init_at_take`, discarded on release/self-release/park). A plain
-- table, not the module's own flat locals, per the plan's own
-- instruction ("the law above, as pure functions over a state table so
-- luajit can test them") -- every function below that reads/writes it
-- takes it as an explicit parameter and returns a new one, so the
-- toy-plant tests can drive it with no DCS mock at all.
local fc_law = nil

local function law_wrap360(deg)
    local r = deg % 360.0
    if r < 0 then r = r + 360.0 end
    return r
end

local function law_wrap180(deg)
    local r = law_wrap360(deg + 180.0) - 180.0
    return r
end

local function law_clamp(v, lo, hi)
    if v < lo then return lo end
    if v > hi then return hi end
    return v
end

-- Turn rate (deg/s) for a coordinated turn at `bank_deg`, at true
-- airspeed `v_t_mps` -- `g*tan(bank)/V`, converted from rad/s to deg/s.
-- Guards a near-zero/absent airspeed (returns 0 -- "no rate" is the
-- safe default, never a division blow-up).
local function law_turn_rate_at_bank(bank_deg, v_t_mps)
    if type(v_t_mps) ~= "number" or v_t_mps < 1.0 then
        return 0.0
    end
    local rate_rad_s = GRAVITY_MPS2 * math.tan(math.rad(bank_deg)) / v_t_mps
    return math.deg(rate_rad_s)
end

-- Stopping-height formula (plan: "Altitude goal = the stopping height,
-- `h + w*|w|/(2*A_v)`, in AGL. So a climb levels off where it naturally
-- stops, rather than reversing back to the height at capture.").
local function law_stopping_height(h, w, max_accel_mps2)
    if max_accel_mps2 <= 0.0 then
        return h
    end
    return h + w * math.abs(w) / (2.0 * max_accel_mps2)
end

--[[ `law_apply_goal(state, goal, limits)` -- Decision 21/the plan's
"Wire" section's own one-shot goal application, called once when a
`goal` command is applied or a take/unpark-take happens (never
re-applied every frame from the wire echo -- that would re-trigger
`level_off`'s own turn-mode request every poll and undo the internal
settle-to-heading transition below). `goal` fields mirror the wire's
own shape (`heading_deg`/`turn`/`alt_m`/`alt_ref`/`ias_kmh`, any subset
present). Returns a new state; never mutates `state` in place (every
`law_*` function in this module follows that convention, so the toy-
plant tests can hold a reference to the state before a call and compare
it against the state after). ]]--
local function law_apply_goal(state, goal, limits)
    local next_state = {}
    for k, v in pairs(state) do next_state[k] = v end

    if goal.turn ~= nil then
        next_state.turn_mode = true
        -- Decision 27/F-M2: "a rate belongs to the command that set
        -- it" -- a continuous turn is a new command too, so any
        -- override still standing from an earlier break is cleared
        -- here, the same way an ordinary heading command clears it
        -- below.
        next_state.rate_override_deg_s = nil
        next_state.break_entry_h_m = nil
        if goal.turn == 0 then
            next_state.turn_goal_deg_s = 0.0
        else
            local sign = goal.turn > 0 and 1.0 or -1.0
            next_state.turn_goal_deg_s =
                sign * law_turn_rate_at_bank(limits.max_turn_bank_deg, state.measured_v_t_mps or 0.0)
        end
    end
    if goal.heading_deg ~= nil then
        next_state.turn_mode = false
        next_state.heading_goal_deg = goal.heading_deg
        -- Decision 27 -- `goal.turn_rate_deg_s` is the break's own
        -- signed rate override, carried on this same message (never
        -- alone: a rate with no heading target is meaningless). `nil`
        -- (every ordinary heading command) clears any override still
        -- standing from an earlier break -- "a rate belongs to the
        -- command that set it" (F-M2). Only when an override is
        -- present does this snapshot the break's own entry height
        -- (Decision 29's own input); an ordinary heading command needs
        -- no height budget of its own.
        next_state.rate_override_deg_s = goal.turn_rate_deg_s
        if goal.turn_rate_deg_s ~= nil then
            next_state.break_entry_h_m = state.h_ref
        else
            next_state.break_entry_h_m = nil
        end
    end
    if goal.alt_m ~= nil then
        next_state.alt_goal_m = goal.alt_m
    end
    if goal.alt_ref ~= nil then
        next_state.alt_goal_ref = goal.alt_ref
    end
    if goal.ias_kmh ~= nil then
        next_state.speed_goal_mps = goal.ias_kmh / 3.6
    end
    return next_state
end

-- `law_init_at_take(measured, limits, command)` -- Decision 24's "At
-- take" section. `command` is the already SIGN-mapped (per `SIGN.*`)
-- captured axis value for every axis, in the same domain the output
-- stage writes (so `law_outputs` on this very state, with zero
-- attitude/rate error, reproduces `command` exactly -- "the output is
-- continuous at take, bit-exact"). Decision 1 REVISED/24 picks heading
-- vs. turn mode from the bank at capture; the altitude goal is the
-- stopping height, never the height at capture (so a climb levels off
-- where it naturally stops); the speed goal is the measured IAS.
local function law_init_at_take(measured, limits, command)
    local heading_mode = math.abs(measured.bank_deg) < limits.takeover_level_bank_deg
    return {
        turn_mode = not heading_mode,
        heading_goal_deg = measured.psi_deg,
        turn_goal_deg_s = measured.r_deg_s,
        psi_ref = measured.psi_deg,
        r_ref = measured.r_deg_s,
        -- `A_v` in the plan's own "h + w*|w|/(2*A_v)" is the channel's
        -- deceleration capability (`ALT_ACCEL_CAP_MPS2`), not the
        -- velocity ceiling `max_climb_vs_mps` -- confirmed a real bug
        -- here by the toy-plant suite, which drove an actual climb
        -- through this formula and found the shaper overshoot-then-
        -- reverse the velocity-ceiling version produces (the wrong
        -- stopping height asks for more deceleration than the channel
        -- can deliver).
        alt_goal_m = law_stopping_height(measured.h_m, measured.w_mps, ALT_ACCEL_CAP_MPS2),
        alt_goal_ref = "agl",
        h_ref = measured.h_m,
        w_ref = measured.w_mps,
        speed_goal_mps = measured.ias_mps,
        v_ref = measured.ias_mps,
        dv_ref = 0.0,
        theta_d = measured.pitch_deg,
        phi_d = measured.bank_deg,
        phi_i = 0.0,
        t_p = command.pitch + K_Q * measured.q_deg_s,
        t_r = command.roll + K_P * measured.p_deg_s,
        t_y = command.pedals,
        u_c = command.collective,
        prev_v_mps = measured.ias_mps,
        prev_w_mps = measured.w_mps,
        a_x_f = 0.0,
        a_z_f = 0.0,
        measured_v_t_mps = measured.v_t_mps,
        in_band_heading = false,
        in_band_altitude = false,
        in_band_speed = false,
        -- Co-moving row B5 (mode-1 batch) -- a fresh activation never
        -- inherits a stale break from a previous session.
        rate_override_deg_s = nil,
        break_entry_h_m = nil,
    }
end

-- `law_update(state, dt, measured, limits)` -- one frame of "The
-- control law" (plan steps 1-5 plus the pedal/collective halves of
-- step 3/5), advancing every shaper reference and integrator. Pure:
-- returns a new state, never mutates `state`. `law_outputs` (below)
-- reads the result out; this function does not itself produce an axis
-- command.
local function law_update(state, dt, measured, limits)
    local next_state = {}
    for k, v in pairs(state) do next_state[k] = v end

    -- Step 1: heading/turn-rate shaper.
    local r_max = law_turn_rate_at_bank(limits.max_turn_bank_deg, measured.v_t_mps)
    if state.turn_mode then
        local r_goal = state.turn_goal_deg_s
        local accel_limit = HEADING_ACCEL_CAP_DEG_S2
        if r_max > 0.0 then
            accel_limit = math.min(HEADING_ACCEL_CAP_DEG_S2, r_max / T_ROLL)
        end
        local dr = law_clamp(r_goal - state.r_ref, -accel_limit * dt, accel_limit * dt)
        next_state.r_ref = state.r_ref + dr
        next_state.psi_ref = law_wrap360(state.psi_ref + next_state.r_ref * dt)
        -- "level_off goes through turn mode at 0. When r_ref reaches 0,
        -- Lua switches to heading mode with psi_goal = psi_ref" --
        -- the stopping point, not the heading at the moment "level off"
        -- was spoken.
        if math.abs(r_goal) < 1e-6 and math.abs(next_state.r_ref) < TURN_SETTLE_DEG_S then
            next_state.turn_mode = false
            next_state.heading_goal_deg = next_state.psi_ref
        end
    else
        -- Decision 27 -- while a break's rate override is active, the
        -- rate ceiling and accel-limit (roll-in time) both come from
        -- it instead of the ordinary `max_turn_bank_deg`-derived rate;
        -- the accel limit uses the same roll-in formula (`r_max /
        -- T_ROLL`) `turn_mode` above already uses, just against the
        -- override's own magnitude.
        local rate_limit = r_max > 0.0 and r_max or 30.0
        local accel_limit = HEADING_ACCEL_CAP_DEG_S2
        if state.rate_override_deg_s ~= nil then
            rate_limit = math.abs(state.rate_override_deg_s)
            accel_limit = rate_limit / T_ROLL
        end
        local err = law_wrap180(state.heading_goal_deg - state.psi_ref)
        local a_ref = OMEGA_HEADING * OMEGA_HEADING * err - 2.0 * LAW_ZETA * OMEGA_HEADING * state.r_ref
        a_ref = law_clamp(a_ref, -accel_limit, accel_limit)
        next_state.r_ref = law_clamp(state.r_ref + a_ref * dt, -rate_limit, rate_limit)
        next_state.psi_ref = law_wrap360(state.psi_ref + next_state.r_ref * dt)
    end
    local r_d = next_state.r_ref + K_HEADING_TRACK * law_wrap180(next_state.psi_ref - measured.psi_deg)

    -- Step 1 (altitude): position+rate shaper towards the AGL-
    -- equivalent goal. A barometric goal is converted every frame via
    -- the currently-measured ASL-AGL offset (plan's own M3 conversion,
    -- applied continuously here rather than once at the goal -- QNH
    -- does not change mid-sortie, so the two are equivalent, and
    -- continuous conversion needs no extra state).
    local alt_goal_agl = state.alt_goal_m
    if state.alt_goal_ref == "baro" then
        alt_goal_agl = state.alt_goal_m - (measured.asl_m - measured.h_m)
    end
    -- Decision 29 -- while a break's rate override is active, the
    -- shaper's own *effective* target is floored at the break's own
    -- height-loss budget below its entry height (never above the
    -- standing `alt_goal_m` itself, which a break never writes -- "a
    -- break replaces only the heading goal"). Stops applying the
    -- instant the break settles (the clearing below).
    if state.rate_override_deg_s ~= nil and state.break_entry_h_m ~= nil then
        local break_floor = math.max(
            limits.floor_agl_m, state.break_entry_h_m - limits.break_max_height_loss_m)
        alt_goal_agl = math.max(alt_goal_agl, break_floor)
    end
    local err_h = alt_goal_agl - state.h_ref
    local a_ref_h = OMEGA_ALT * OMEGA_ALT * err_h - 2.0 * LAW_ZETA * OMEGA_ALT * state.w_ref
    a_ref_h = law_clamp(a_ref_h, -ALT_ACCEL_CAP_MPS2, ALT_ACCEL_CAP_MPS2)
    next_state.w_ref = law_clamp(state.w_ref + a_ref_h * dt, -limits.max_climb_vs_mps, limits.max_climb_vs_mps)
    -- Decision 31 -- vortex ring state, every mode-1 state (not only a
    -- break): below the VRS IAS threshold, the descent-rate reference
    -- is capped regardless of how large the altitude error driving it
    -- is.
    if (measured.ias_mps * 3.6) < limits.vrs_ias_threshold_kmh then
        next_state.w_ref = math.max(next_state.w_ref, -limits.vrs_max_descent_mps)
    end
    next_state.h_ref = state.h_ref + next_state.w_ref * dt

    -- Step 1 (speed).
    local err_v = state.speed_goal_mps - state.v_ref
    local a_ref_v = OMEGA_SPEED * OMEGA_SPEED * err_v - 2.0 * LAW_ZETA * OMEGA_SPEED * state.dv_ref
    a_ref_v = law_clamp(a_ref_v, -SPEED_ACCEL_CAP_MPS2, SPEED_ACCEL_CAP_MPS2)
    next_state.dv_ref = law_clamp(state.dv_ref + a_ref_v * dt, -limits.max_accel_mps2, limits.max_accel_mps2)
    next_state.v_ref = state.v_ref + next_state.dv_ref * dt

    -- Step 2: desired accelerations.
    local a_z_d = a_ref_h + K_VS_ERROR * (next_state.w_ref - measured.w_mps)
        + K_ALT_ERROR * (next_state.h_ref - measured.h_m)
    local a_x_d = a_ref_v + K_SPEED_ERROR * (next_state.v_ref - measured.ias_mps)

    -- Filtered actual accelerations (dV/dt, dw/dt -- plan's own
    -- fallback, `LoGetAccelerationUnits`'s body-frame mapping being
    -- unconfirmed, module header).
    local alpha = math.min(1.0, dt / TAU_ACCEL_FILTER_S)
    local raw_a_z = (measured.w_mps - state.prev_w_mps) / dt
    next_state.a_z_f = state.a_z_f + (raw_a_z - state.a_z_f) * alpha
    local raw_a_x = (measured.ias_mps - state.prev_v_mps) / dt
    next_state.a_x_f = state.a_x_f + (raw_a_x - state.a_x_f) * alpha
    next_state.prev_w_mps = measured.w_mps
    next_state.prev_v_mps = measured.ias_mps

    -- Step 3: lift-vector corrections, incrementally.
    -- Decision 30 -- the rotor-RPM floor and the retreating-blade-
    -- stall margin widen the existing "collective is limited" flag,
    -- reactively, the same shape the pedal-near-limit cap already
    -- uses -- no RPM-vs-collective or stall-vs-collective model, a
    -- feedback cap only.
    local collective_saturated = state.u_c >= 0.999 or state.u_c <= -0.999
    local rotor_rpm_limited = measured.rotor_rpm_pct
        <= (limits.rotor_rpm_floor_pct + ROTOR_RPM_NEAR_FLOOR_MARGIN_PCT)
    local blade_stall_limited = (measured.ias_mps * 3.6)
        >= (limits.retreating_blade_stall_ias_kmh - RETREATING_BLADE_STALL_MARGIN_KMH)
    local collective_limited = collective_saturated or rotor_rpm_limited or blade_stall_limited
    local d_theta = -K_TILT_FROM_AX * (a_x_d - next_state.a_x_f)
    if collective_limited then
        d_theta = d_theta + K_TILT_FROM_AZ_SATURATED * (a_z_d - next_state.a_z_f)
    end
    next_state.theta_d = law_clamp(state.theta_d + d_theta * dt, THETA_MIN_DEG, THETA_MAX_DEG)

    local c_dot = K_COLLECTIVE * (a_z_d - next_state.a_z_f)
    if c_dot > 0.0 then
        if state.t_y >= (PEDAL_LIMIT_POSITIVE - PEDAL_NEAR_LIMIT_MARGIN) then
            c_dot = math.min(c_dot, COLLECTIVE_RATE_CAP_NEAR_PEDAL_LIMIT)
        end
        -- Only a further *increase* is ever capped by either guard --
        -- neither forces collective down, so level flight with
        -- collective already low is untouched.
        if rotor_rpm_limited then
            c_dot = math.min(c_dot, COLLECTIVE_RATE_CAP_NEAR_RPM_FLOOR)
        end
        if blade_stall_limited then
            c_dot = math.min(c_dot, COLLECTIVE_RATE_CAP_NEAR_BLADE_STALL)
        end
    end
    next_state.u_c = law_clamp(state.u_c + c_dot * dt, -1.0, 1.0)

    local phi_kinematic_deg = 0.0
    if measured.v_t_mps > 1.0 then
        phi_kinematic_deg = math.deg(math.atan(measured.v_t_mps * math.rad(r_d) / GRAVITY_MPS2))
    end
    local d_phi_i = K_BANK_INCREMENT * (r_d - measured.r_deg_s)
    next_state.phi_i = state.phi_i + d_phi_i * dt
    -- F-M1 (mode-1 batch): "remove the 30 degree limit. Set no limit
    -- for now" -- no clamp against `limits.max_bank_deg` any more (the
    -- field itself is gone from the wire); a kinematic bank request is
    -- self-limiting (it saturates toward +-90 only as `r_d`/`V_t` grow
    -- large), and the output stage's own `law_clamp(u_roll, -1, 1)`
    -- in `law_outputs` is the real physical ceiling.
    next_state.phi_d = phi_kinematic_deg + next_state.phi_i

    -- Step 4: inner tilt-loop integrators.
    next_state.t_p = state.t_p + K_THETA_I * (next_state.theta_d - measured.pitch_deg) * dt
    next_state.t_r = state.t_r + K_PHI_I * (next_state.phi_d - measured.bank_deg) * dt

    -- Step 5: pedal (collective-coupling feedforward, plus Decision
    -- 27's own pedal-into-the-turn bias while a break's rate override
    -- is active -- no slip-ball feedback, module header).
    local d_t_y = K_PEDAL_FROM_COLLECTIVE_RATE * c_dot
    if state.rate_override_deg_s ~= nil then
        local break_sign = state.rate_override_deg_s > 0.0 and 1.0 or -1.0
        d_t_y = d_t_y + K_BREAK_PEDAL_BIAS * break_sign
    end
    next_state.t_y = law_clamp(state.t_y + d_t_y * dt, PEDAL_LIMIT_NEGATIVE, PEDAL_LIMIT_POSITIVE)

    next_state.measured_v_t_mps = measured.v_t_mps

    -- Status-feed `in_band_*` (A9's only consumers this stage: the
    -- status field, and M4's own settle test).
    next_state.in_band_heading = (not next_state.turn_mode)
        and math.abs(law_wrap180(measured.psi_deg - next_state.heading_goal_deg)) <= limits.heading_band_deg
    local alt_band = math.max(limits.alt_band_frac * math.abs(alt_goal_agl), limits.alt_band_min_m)
    next_state.in_band_altitude = math.abs(measured.h_m - alt_goal_agl) <= alt_band
    local speed_band = limits.speed_band_frac * state.speed_goal_mps
    next_state.in_band_speed = math.abs(measured.ias_mps - state.speed_goal_mps) <= speed_band

    -- Decision 27 -- "settling clears it." Once the heading goal is
    -- actually reached while a break's rate override is still set,
    -- both it and `break_entry_h_m` are cleared this same frame --
    -- without this, a break that finished rolling out long ago would
    -- still be clamping a *later, unrelated* altitude command to the
    -- stale break-floor (Decision 29), a cross-command leak the "a
    -- rate belongs to its own command" rule would otherwise miss once
    -- the command's own goal is *reached* rather than superseded.
    if next_state.in_band_heading and next_state.rate_override_deg_s ~= nil then
        next_state.rate_override_deg_s = nil
        next_state.break_entry_h_m = nil
    end

    return next_state
end

-- `law_outputs(state, measured)` -- reads the four axis commands out
-- of `state`, already in the sign-mapped domain the output stage
-- writes (clamped defensively; `law_update`'s own saturation already
-- keeps `u_c`/`t_y` in range, but the pitch/roll inner-loop terms below
-- are not themselves saturated upstream). Pure, no mutation.
local function law_outputs(state, measured)
    local u_pitch = state.t_p + K_THETA * (state.theta_d - measured.pitch_deg) - K_Q * measured.q_deg_s
    local u_roll = state.t_r + K_PHI * (state.phi_d - measured.bank_deg) - K_P * measured.p_deg_s
    return {
        pitch = law_clamp(u_pitch, -1.0, 1.0),
        roll = law_clamp(u_roll, -1.0, 1.0),
        pedals = law_clamp(state.t_y, -1.0, 1.0),
        collective = law_clamp(state.u_c, -1.0, 1.0),
    }
end

-- `SIGN`-mapped command value for one axis of a raw captured-arg table
-- (`fc_captured`-shaped); `0.0` when that axis was never captured
-- (disabled axes, e.g. collective today) -- internal law state still
-- needs a number for every axis even when nothing will ever be written
-- for it.
local function axis_command(values, axis)
    local v = values[axis]
    if v == nil then
        return 0.0
    end
    return SIGN[axis] * v
end

-- Mode-1 own state. `fc_mode`: "off" | "taking" | "active" | "armed".
local fc_mode = "off"
local fc_take_seq = nil
local fc_pending_take_seq = nil
local fc_take_origin = nil
local fc_goal_seq = nil
local fc_last_cmd_seq = -1
local fc_last_arm_seq = nil
local fc_arm_last_t = nil
local fc_release_reason = nil
local fc_refuse_cause = nil
local fc_takeover_mode = nil

-- The commanded goal, stored verbatim (never shaped -- M2's own job).
-- "A null field means keep yours": each is updated independently.
local fc_goal_heading_deg = nil
local fc_goal_turn = nil
local fc_goal_alt_m = nil
local fc_goal_alt_ref = nil
local fc_goal_ias_kmh = nil

-- The frozen, captured raw per-axis values (`fc_captured.pitch` etc).
local fc_captured = {}

-- M0-J (flight 9) capture fixes -- never consulted as an active control
-- source, only snapshotted at a take.
--
-- The pilot set from the last frame `armed` saw `stick_park_raw() >=
-- STOWED_THRESHOLD` -- the unpark-take's own capture source, tracked
-- continuously while armed (reset to `nil` on entering `armed` fresh
-- and on leaving it, so a stale snapshot from a previous park session
-- never survives into the next one -- the same leak class as `fc_goal_*`
-- across a release/re-take, review-m1.md Required Fix 1).
local fc_last_stowed_pilot_capture = nil

-- The most recent captured values read while exactly one seat's axis
-- magnitude was live and the other read idle -- the voice-take capture
-- rule's fallback for a cross-fade in progress (both seats live at
-- once). Tracked every frame regardless of `fc_mode`, since a take can
-- be commanded on any frame.
local fc_last_steady_values = nil

local fc_wobble_parity = false
local fc_last_frame_t = nil
local fc_env_low_ias_since_t = nil

-- The last *pre-wobble* command written per axis (`pitch`/`roll`/
-- `pedals`/`collective`), used both to rate-limit a fresh law output
-- (`OUTPUT_RATE_LIMIT_PER_S`) and to re-issue an unchanged write on a
-- paused/huge-jump frame without re-running the law (plan's own pause
-- row). Reset to `nil` on every mode change away from active (a stale
-- previous session's command must not seed a later rate limit).
local fc_last_command = nil

local function extract_json_bool_field(json_text, field_name)
    if json_text:match("\"" .. field_name .. "\"%s*:%s*true") then
        return true
    end
    if json_text:match("\"" .. field_name .. "\"%s*:%s*false") then
        return false
    end
    return nil
end

local function read_axis(seat, axis)
    local arg = SEAT_ARGS[seat][axis]
    return safe_call(function() return GetDevice(0):get_argument_value(arg) end)
end

-- Sum of |value| across every *enabled* axis for one seat -- the "which
-- seat is actually being touched" signal Decision 25's finding 5 names:
-- the live seat shows non-zero deflection, the idle one centred/zero.
local function axis_magnitude(seat)
    local total = 0.0
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        if enabled then
            local v = read_axis(seat, axis)
            if type(v) == "number" and v == v then
                total = total + math.abs(v)
            end
        end
    end
    return total
end

-- Reads every enabled axis from one seat's arg set. `nil` on any read
-- failure (NaN or a failed `get_argument_value`) -- the caller decides
-- what that means (stay "taking" and retry, or refuse the unpark take).
local function capture_from_seat(seat)
    local values = {}
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        if enabled then
            local v = read_axis(seat, axis)
            if type(v) ~= "number" or v ~= v then
                return nil
            end
            values[axis] = v
        end
    end
    return values
end

-- Updates `fc_last_steady_values` -- called every frame regardless of
-- `fc_mode` (M0-J, flight 9: a take can land on any frame, so the "last
-- steady" snapshot must already be current by then). A seat is
-- "steady" exactly when its own magnitude reads live and the other
-- seat's reads idle -- during an actual cross-fade both read live at
-- once, and this function leaves the previous snapshot alone rather
-- than overwriting it with a now-ambiguous read.
local function update_live_seat_tracking()
    local mag_pilot = axis_magnitude("pilot")
    local mag_operator = axis_magnitude("operator")
    local pilot_live = mag_pilot > LIVE_SEAT_ZERO_EPS
    local operator_live = mag_operator > LIVE_SEAT_ZERO_EPS
    if pilot_live and not operator_live then
        fc_last_steady_values = capture_from_seat("pilot")
    elseif operator_live and not pilot_live then
        fc_last_steady_values = capture_from_seat("operator")
    end
end

-- The voice-take capture rule (M0-J, flight 9, correcting Decision 25's
-- own "the player's seat set" wording): the camera seat is not read at
-- all -- the operator set can read all-zero while the player sits
-- there, before an explicit handover, with the pilot set holding the
-- live inputs throughout. Captures whichever seat currently reads live
-- and the other idle; if both read live at once (a cross-fade already
-- in progress), uses the last steady snapshot instead of either set's
-- current, partly-faded values; if neither has ever been steady, falls
-- back to the higher-magnitude seat (the old Decision-25 default) so a
-- take is never refused outright on this account.
local function resolve_capture_values()
    local mag_pilot = axis_magnitude("pilot")
    local mag_operator = axis_magnitude("operator")
    local pilot_live = mag_pilot > LIVE_SEAT_ZERO_EPS
    local operator_live = mag_operator > LIVE_SEAT_ZERO_EPS
    if pilot_live and not operator_live then
        return capture_from_seat("pilot")
    end
    if operator_live and not pilot_live then
        return capture_from_seat("operator")
    end
    if pilot_live and operator_live and fc_last_steady_values ~= nil then
        return fc_last_steady_values
    end
    if fc_last_steady_values ~= nil then
        return fc_last_steady_values
    end
    if mag_operator > mag_pilot then
        return capture_from_seat("operator")
    end
    return capture_from_seat("pilot")
end

-- Decision 1 REVISED/24's takeover-mode pick, snapshotted once at take
-- (never recomputed -- there is no shaper to keep it current against).
local function snapshot_takeover_mode()
    local _, bank_rad = safe_call(LoGetADIPitchBankYaw)
    if type(bank_rad) ~= "number" then
        return nil
    end
    local bank_deg = math.abs(math.deg(bank_rad))
    if bank_deg < fc_limits.takeover_level_bank_deg then
        return "heading"
    end
    return "turn"
end

-- The unpark-take's own preconditions (Decision 24's "Lua checks the
-- take preconditions itself... because body-layer is a second away"):
-- IAS, AGL (on-ground floor), no NaN. Returns `true` or `false, cause`.
-- A failed read fails safe (towards "refuse"), mapped onto the two
-- causes the wire already defines rather than inventing a third: an
-- unreadable IAS reads as "too slow" (cannot confirm enough airspeed to
-- fly, so assume not enough), an unreadable AGL as "on ground" (cannot
-- confirm altitude, so assume none). Both are judgement calls -- see
-- `plans/flight-control/implementation.md`.
local function check_unpark_preconditions()
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    if type(ias_mps) ~= "number" or ias_mps ~= ias_mps then
        return false, "too_slow"
    end
    local ias_kmh = ias_mps * 3.6
    if ias_kmh < fc_limits.min_ias_kmh then
        return false, "too_slow"
    end
    local agl = safe_call(LoGetAltitudeAboveGroundLevel)
    if type(agl) ~= "number" or agl ~= agl then
        return false, "on_ground"
    end
    if agl <= fc_limits.on_ground_agl_threshold_m then
        return false, "on_ground"
    end
    return true, nil
end

-- The per-frame envelope check (plan, "Envelope release") -- run only
-- while `fc_mode == "active"`. A failed read is `"nan"`; `"dead"` is
-- reserved for `LoGetSelfData()` itself coming back empty, the
-- established "ownship not healthy" signal this codebase's telemetry
-- feed already relies on (`telemetry.lua`'s own `ok_to_continue` gate) --
-- the closest proxy available to a real weight-on-wheels/death sensor,
-- which does not exist anywhere in this codebase (see `ON_GROUND_AGL_
-- THRESHOLD_M`'s own docstring on body-layer's side for the same gap).
--
-- Takes `measured` -- `read_measured()`'s own result for this frame --
-- instead of reading `LoGetSelfData`/`LoGetIndicatedAirSpeed`/
-- `LoGetADIPitchBankYaw` a second time (perf-m1-m2.md finding 1: both
-- functions independently crossed the Lua->DCS-engine boundary for the
-- same three values, every active frame). `measured.self_data_ok`/
-- `ias_valid`/`bank_valid` are `read_measured`'s own liveness/NaN flags
-- from *before* its fail-soft zeroing -- using `measured.ias_mps`/
-- `bank_deg` directly would silently swallow a bad read as a stale
-- zero instead of this function's own distinct "nan" cause.
local function check_envelope(t, measured)
    if not measured.self_data_ok then
        return false, "dead"
    end
    if not measured.ias_valid or not measured.bank_valid then
        return false, "nan"
    end
    local ias_kmh = measured.ias_mps * 3.6
    if ias_kmh < (fc_limits.min_ias_kmh - ENV_IAS_MARGIN_KMH) then
        if fc_env_low_ias_since_t == nil then
            fc_env_low_ias_since_t = t
        elseif t - fc_env_low_ias_since_t >= ENV_HOLD_S then
            return false, "envelope"
        end
    else
        fc_env_low_ias_since_t = nil
    end
    -- No bank-based release any more (F-M1, mode-1 batch: "remove the
    -- 30 degree limit. Set no limit for now") -- IAS alone governs
    -- release now; the rotor envelope (Decision 30) is the real
    -- protection in a break.
    return true, nil
end

-- Per-axis value-change (always on, from the first write -- Decision 6
-- REVISED), clamped to the `LoSetCommand` range. `command` is already
-- in the sign-mapped domain (`law_outputs`'s own output, or `fc_last_
-- command` re-issued unchanged on a pause/huge-jump frame, `dt=nil`)
-- -- no `SIGN` multiply here any more, M2's law applies it once, at
-- capture (`axis_command`), and carries it through every state field.
-- One flicker parity flip shared by every axis this frame, same
-- reasoning as `sight.lua`'s own `sight_flicker_parity`.
local function write_outputs(command, dt)
    fc_wobble_parity = not fc_wobble_parity
    local wobble_sign = 1.0
    if fc_wobble_parity then wobble_sign = -1.0 end
    local d = FLIGHT_WOBBLE * wobble_sign
    local new_last = {}
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        local target = command[axis]
        if target ~= nil then
            local prev = fc_last_command and fc_last_command[axis]
            local limited = target
            if prev ~= nil and dt ~= nil and dt > 0.0 then
                local max_delta = OUTPUT_RATE_LIMIT_PER_S * dt
                if limited - prev > max_delta then
                    limited = prev + max_delta
                elseif limited - prev < -max_delta then
                    limited = prev - max_delta
                end
            end
            limited = law_clamp(limited, -1.0, 1.0)
            new_last[axis] = limited
            if enabled then
                local value = limited + d
                if value > 1.0 then value = 1.0 end
                if value < -1.0 then value = -1.0 end
                safe_call(function() LoSetCommand(CMD[axis], value) end)
            end
        end
    end
    fc_last_command = new_last
end

-- Current telemetry, gathered once per active frame and handed to
-- every `law_*` function identically (the plan's own "measured
-- inputs" table). Every reader fails soft to 0.0/the previous value's
-- own domain default on a bad read -- a control law that stalls on a
-- single missing sample is worse than one that briefly runs on a stale
-- zero (the envelope check, run separately, is what actually stops the
-- override on real trouble).
--
-- `self_data_ok`/`ias_valid`/`bank_valid` are kept alongside the fail-
-- soft values for `check_envelope`'s own use (perf-m1-m2.md finding
-- 1) -- recorded *before* `ias_mps` is zeroed below, since the law's
-- own "stale zero is fine" tolerance and the envelope's own "a bad
-- read means release" are different policies over the same read.
-- `bank_deg` needs no separate capture: NaN propagates through
-- `math.deg` unchanged, so an invalid `bank_rad` already leaves
-- `bank_deg` NaN rather than zeroed -- `bank_valid` instead records
-- whether the *type* was even a number, which NaN-propagation alone
-- cannot distinguish from a `LoGetADIPitchBankYaw` call that returned
-- nothing at all.
local function read_measured()
    local pitch_rad, bank_rad = safe_call(LoGetADIPitchBankYaw)
    local bank_valid = type(bank_rad) == "number" and bank_rad == bank_rad
    local pitch_deg = (type(pitch_rad) == "number") and math.deg(pitch_rad) or 0.0
    local bank_deg = (type(bank_rad) == "number") and math.deg(bank_rad) or 0.0
    local self_data = safe_call(LoGetSelfData)
    local self_data_ok = type(self_data) == "table"
    local psi_deg = 0.0
    if self_data_ok and type(self_data.Heading) == "number" then
        psi_deg = law_wrap360(math.deg(self_data.Heading))
    end
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    local ias_valid = type(ias_mps) == "number" and ias_mps == ias_mps
    if not ias_valid then ias_mps = 0.0 end
    local v_t_mps = safe_call(LoGetTrueAirSpeed)
    if type(v_t_mps) ~= "number" or v_t_mps ~= v_t_mps then v_t_mps = ias_mps end
    local w_mps = safe_call(LoGetVerticalVelocity)
    if type(w_mps) ~= "number" or w_mps ~= w_mps then w_mps = 0.0 end
    local agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local radar_dist, radar_valid = safe_call(LoGetRadarAltimeter)
    local h_m = agl
    if radar_valid and type(radar_dist) == "number" then h_m = radar_dist end
    if type(h_m) ~= "number" or h_m ~= h_m then h_m = 0.0 end
    local asl_m = safe_call(LoGetAltitudeAboveSeaLevel)
    if type(asl_m) ~= "number" or asl_m ~= asl_m then asl_m = h_m end
    local ang = safe_call(LoGetAngularVelocity)
    local p_deg_s, q_deg_s, r_deg_s = 0.0, 0.0, 0.0
    if type(ang) == "table" then
        -- M0-A (`aircraft-layer/research/2026-11-18-bl16-m0-flight-
        -- axes-findings.md`): x is roll rate (+correlates with d(bank)/
        -- dt directly), z is pitch rate (+correlates with d(pitch)/
        -- dt), y is yaw rate "positive when heading decreases" -- so
        -- the heading-rate sign is the negative of the raw y reading.
        if type(ang.x) == "number" then p_deg_s = math.deg(ang.x) end
        if type(ang.z) == "number" then q_deg_s = math.deg(ang.z) end
        if type(ang.y) == "number" then r_deg_s = -math.deg(ang.y) end
    end
    -- Decision 28's rotor RPM seam. `rotor_rpm_valid = false` (a
    -- failed `arg_proxy` read) does not release the envelope -- it
    -- fails soft to the dummy value, same posture as every other
    -- `read_measured()` field; `law_update`'s own guards just read
    -- `rotor_rpm_pct` and never look at `rotor_rpm_valid` at all.
    local rotor_rpm_pct, rotor_rpm_valid = read_rotor_rpm_pct()
    return {
        pitch_deg = pitch_deg,
        bank_deg = bank_deg,
        psi_deg = psi_deg,
        ias_mps = ias_mps,
        v_t_mps = v_t_mps,
        w_mps = w_mps,
        h_m = h_m,
        asl_m = asl_m,
        p_deg_s = p_deg_s,
        q_deg_s = q_deg_s,
        r_deg_s = r_deg_s,
        self_data_ok = self_data_ok,
        ias_valid = ias_valid,
        bank_valid = bank_valid,
        rotor_rpm_pct = rotor_rpm_pct,
        rotor_rpm_valid = rotor_rpm_valid,
    }
end

local function apply_goal_fields(data)
    local heading_deg = extract_json_number_field(data, "heading_deg")
    local turn = extract_json_number_field(data, "turn")
    local level_off = extract_json_bool_field(data, "level_off")
    local alt_m = extract_json_number_field(data, "alt_m")
    local alt_ref = extract_json_string_field(data, "alt_ref")
    local ias_kmh = extract_json_number_field(data, "ias_kmh")
    -- Decision 27 -- the break's own signed rate override, carried
    -- alongside `heading_deg` only (never alone -- a rate with no
    -- heading target is meaningless, and `law_apply_goal`'s own
    -- `heading_deg ~= nil` branch is the only place this is read).
    local turn_rate_deg_s = extract_json_number_field(data, "turn_rate_deg_s")
    local turn_value = turn
    if level_off == true then
        turn_value = 0
    end
    if heading_deg ~= nil then
        fc_goal_heading_deg = heading_deg
        fc_goal_turn = nil
    end
    if turn_value ~= nil then
        fc_goal_turn = turn_value
        fc_goal_heading_deg = nil
    end
    if alt_m ~= nil then
        fc_goal_alt_m = alt_m
    end
    if alt_ref ~= nil then
        fc_goal_alt_ref = alt_ref
    end
    if ias_kmh ~= nil then
        fc_goal_ias_kmh = ias_kmh
    end
    fc_goal_seq = fc_last_cmd_seq

    -- Decision 21's "Wire"/one-shot goal application -- never re-applied
    -- from the persisted `fc_goal_*` echo every frame (that would
    -- re-trigger `level_off`'s own turn-mode request every poll and
    -- undo the law's own internal settle-to-heading transition).
    -- `fc_law` is `nil` while "taking"/"off"/"armed"; a goal that
    -- arrives before capture completes is still recorded in `fc_goal_*`
    -- above (so the wire echo is correct) but is not applied here --
    -- the law itself only ever sees it once the take completes and
    -- starts fresh from Decision 24's own "At take" values. **A goal
    -- commanded during the one-frame "taking" window is reachable**
    -- (`axes_set_heading`/`axes_set_speed`/`axes_set_altitude` gate on
    -- `has_controls` alone, already true there) -- body-layer now holds
    -- such a goal unsent until it sees this module report `active`,
    -- then sends it fresh (review-m2.md Required Fix 1), rather than
    -- relying on anything here to re-apply it once `fc_law` exists.
    if fc_law ~= nil then
        fc_law = law_apply_goal(fc_law, {
            heading_deg = heading_deg,
            turn = turn_value,
            alt_m = alt_m,
            alt_ref = alt_ref,
            ias_kmh = ias_kmh,
            turn_rate_deg_s = turn_rate_deg_s,
        }, fc_limits)
    end
end

-- `POST /command/flight_control` -> here, via `commands.lua`'s dispatch
-- table, same `(data, t)` shape every other handler in this codebase
-- uses. `{"op": "flight_control", "seq", "cmd", "limits", "goal"}`.
local function handle_flight_control_command(data, t)
    local seq = extract_json_number_field(data, "seq")
    local cmd = extract_json_string_field(data, "cmd")
    if seq == nil or cmd == nil then
        debug_log("ignoring malformed flight_control command (missing seq/cmd)")
        return
    end
    -- "Lua applies a message only when its seq is greater than the last
    -- one applied" -- a stale/duplicate/out-of-order datagram (UDP) is
    -- silently dropped, same posture as `ai_pilot_wheel`'s own `hvrt_
    -- step` dedup.
    if seq <= fc_last_cmd_seq then
        return
    end

    -- `limits` travels in every message (plan's own wire shape) --
    -- every present field is bounds-checked against FC_LIMIT_BOUNDS; an
    -- out-of-bounds value rejects the WHOLE message (the `AC-B14`
    -- lesson: never a partial apply), a field the message omits keeps
    -- its previous value rather than reverting to the startup default.
    local new_limits = {}
    for key, bound in pairs(FC_LIMIT_BOUNDS) do
        local v = extract_json_number_field(data, key)
        if v ~= nil then
            if v < bound.lo or v > bound.hi then
                debug_log("rejecting flight_control message seq=" .. tostring(seq)
                    .. ": limits." .. key .. " out of bounds")
                return
            end
            new_limits[key] = v
        end
    end
    for key, v in pairs(new_limits) do
        fc_limits[key] = v
    end

    fc_last_cmd_seq = seq

    if cmd == "goal" then
        apply_goal_fields(data)
        return
    end
    if cmd == "arm" then
        -- The lease (U10): body-layer re-sends this every poll while he
        -- flies through the overlay with mode 1 armed. From "off", this
        -- is also the only way "armed" is entered (Decision 24's
        -- `off` -> `armed` row); an already-active/taking session
        -- self-arms on the park edge instead (`run_flight_control`
        -- below), never from this handler.
        fc_arm_last_t = t
        fc_last_arm_seq = seq
        if fc_mode == "off" then
            fc_mode = "armed"
        end
        return
    end
    if cmd == "release" then
        fc_mode = "off"
        fc_captured = {}
        fc_release_reason = "stop"
        fc_refuse_cause = nil
        -- Clear every held goal, same as `on_stop` -- otherwise a stale
        -- value from this session survives into the next take and the
        -- HOLD-until-known gates (`rules/gates.py`) see a non-nil
        -- "held" value immediately instead of waiting for a fresh one
        -- (review-m1.md, Required Fix 1).
        fc_goal_heading_deg = nil
        fc_goal_turn = nil
        fc_goal_alt_m = nil
        fc_goal_alt_ref = nil
        fc_goal_ias_kmh = nil
        -- Same reasoning, for the M0-J tracked capture (above): a
        -- release received while `armed` must not leave a stale
        -- snapshot for a later armed session to inherit. M2 adds the
        -- law state and the rate-limit's own last-written memory to
        -- the same leak class -- a later take must start fresh from
        -- `law_init_at_take`, never resume a discarded session's
        -- shaper/integrator state.
        fc_last_stowed_pilot_capture = nil
        fc_law = nil
        fc_last_command = nil
        return
    end
    if cmd == "take" then
        -- A repeated take while already taking/active is an idempotent
        -- no-op -- body-layer's own refusals (overlay flying, on
        -- ground, too slow, attack run) already ran before this was
        -- ever sent (Decision 22); this handler trusts that for a voice
        -- take and does not re-check it.
        if fc_mode == "active" or fc_mode == "taking" then
            return
        end
        fc_mode = "taking"
        fc_pending_take_seq = seq
        fc_take_origin = "voice"
        return
    end
end

-- The output half of an "active" frame -- shared by the ordinary
-- per-frame path below and by a fresh take/unpark-take transition,
-- which must write from the very first frame it is active ("the output
-- is continuous at take, bit-exact" -- Decision 24), never wait for the
-- next call to `run_flight_control`.
local function run_active_frame(t, dt, just_took)
    if not just_took and (dt <= 0 or dt > DT_CAP) then
        -- Paused frame (or a huge jump): rewrite unchanged with wobble,
        -- freezing every shaper reference and integrator (plan's own
        -- pause row: "the last outputs are written again with wobble.
        -- Shapers and integrators are frozen"). `fc_last_command` is
        -- re-issued verbatim (`dt=nil` so `write_outputs` applies no
        -- rate limit -- there is nothing to limit against, the value
        -- is unchanged by construction), `fc_law` untouched. A frame
        -- that just transitioned into "active" is never treated as
        -- paused -- `dt` there measures time since the last frame
        -- `run_flight_control` ran at all, which says nothing about
        -- this take.
        write_outputs(fc_last_command, nil)
        return
    end
    local measured = read_measured()
    local ok, reason = check_envelope(t, measured)
    if not ok then
        fc_mode = "off"
        fc_captured = {}
        fc_release_reason = reason
        fc_refuse_cause = nil
        fc_law = nil
        fc_last_command = nil
        return
    end
    if just_took then
        local command = {
            pitch = axis_command(fc_captured, "pitch"),
            roll = axis_command(fc_captured, "roll"),
            pedals = axis_command(fc_captured, "pedals"),
            collective = axis_command(fc_captured, "collective"),
        }
        fc_law = law_init_at_take(measured, fc_limits, command)
        write_outputs(law_outputs(fc_law, measured), nil)
        return
    end
    fc_law = law_update(fc_law, dt, measured, fc_limits)
    write_outputs(law_outputs(fc_law, measured), dt)
end

-- Every frame, from `LuaExportBeforeNextFrame` (Decision 23).
local function run_flight_control(t)
    local dt = 0.0
    if fc_last_frame_t ~= nil then
        dt = t - fc_last_frame_t
    end
    fc_last_frame_t = t

    -- `is_parked()` unknown (ai_pilot_wheel failed to load) is treated
    -- the same as "stay off" -- never a licence to assume unparked
    -- (module docstring; this is the one place that default is made).
    local is_parked = nil
    if ai_pilot_wheel ~= nil then
        is_parked = safe_call(ai_pilot_wheel.is_parked)
    end

    -- M0-J (flight 9): track the voice-take capture's "last steady"
    -- fallback every frame, regardless of mode -- a take can land on
    -- any frame.
    update_live_seat_tracking()

    -- M0-J (flight 9): while armed (parked), track the unpark-take's
    -- own capture source -- the pilot set from the last frame the stow
    -- arg read fully stowed, before the two sets' cross-fade begins.
    -- Left untouched on every other frame, including the unpark frame
    -- itself (by then the arg has already fallen well below the
    -- threshold), so it keeps the last good snapshot through the fade.
    if fc_mode == "armed" then
        local stowed_raw = nil
        if ai_pilot_wheel ~= nil then
            stowed_raw = safe_call(ai_pilot_wheel.stick_park_raw)
        end
        if type(stowed_raw) == "number" and stowed_raw >= STOWED_THRESHOLD then
            local tracked = capture_from_seat("pilot")
            if tracked ~= nil then
                fc_last_stowed_pilot_capture = tracked
            end
        end
    end

    -- Self-arm on the park edge while he already has the controls
    -- (Decision 24: a mode-1 active/taking Lua goes to armed by itself).
    if is_parked == true and (fc_mode == "active" or fc_mode == "taking") then
        fc_captured = {}
        fc_pending_take_seq = nil
        fc_mode = "armed"
        fc_arm_last_t = t
        -- Fresh armed session: forget whatever the previous one tracked
        -- (the same "stale leak across a session boundary" the `fc_goal_
        -- *` fix above guards against). The unpark-take rebuilds `fc_
        -- law` from scratch at `law_init_at_take` -- never resumes this
        -- session's shaper/integrator state.
        fc_last_stowed_pilot_capture = nil
        fc_law = nil
        fc_last_command = nil
        return
    end

    -- Unpark-take, while armed and the park signal has fallen.
    if is_parked == false and fc_mode == "armed" then
        local lease_fresh = fc_arm_last_t ~= nil
            and (t - fc_arm_last_t) <= fc_limits.arm_lease_s
        if not UNPARK_TAKE_ENABLED then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "disabled"
            fc_last_stowed_pilot_capture = nil
            return
        end
        if not lease_fresh then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "lease"
            fc_last_stowed_pilot_capture = nil
            return
        end
        local ok, cause = check_unpark_preconditions()
        if not ok then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = cause
            fc_last_stowed_pilot_capture = nil
            return
        end
        -- Decision 24, capture source corrected by M0-J (flight 9): the
        -- pilot set (1100-1103) from the last frame it read fully
        -- stowed, tracked above while armed -- never a fresh read at
        -- the edge itself, which is already partway through the two
        -- sets' cross-fade. Falls back to a fresh read only if armed
        -- was entered and exited again before any frame ever reached
        -- the threshold (should not happen outside a test harness).
        local values = fc_last_stowed_pilot_capture
        if values == nil then
            values = capture_from_seat("pilot")
        end
        fc_last_stowed_pilot_capture = nil
        if values == nil then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "on_ground"
            return
        end
        fc_captured = values
        fc_mode = "active"
        fc_take_origin = "unpark"
        fc_take_seq = fc_last_arm_seq
        fc_takeover_mode = snapshot_takeover_mode()
        fc_release_reason = nil
        fc_refuse_cause = nil
        fc_env_low_ias_since_t = nil
        run_active_frame(t, dt, true)
        return
    end

    if fc_mode == "taking" then
        local values = resolve_capture_values()
        if values == nil then
            -- else: stays "taking", retries next frame.
            return
        end
        fc_captured = values
        fc_mode = "active"
        fc_take_seq = fc_pending_take_seq
        fc_pending_take_seq = nil
        fc_takeover_mode = snapshot_takeover_mode()
        fc_release_reason = nil
        fc_refuse_cause = nil
        fc_env_low_ias_since_t = nil
        run_active_frame(t, dt, true)
        return
    end

    if fc_mode == "active" then
        run_active_frame(t, dt, false)
        return
    end

    -- "off" or "armed" with no edge this frame: nothing to write.
end

-- 5 Hz status push, same cadence as every other per-frame feed
-- (`telemetry`/`sight_servo`/`ai_pilot_wheel`). `fc_in_band_*` reads
-- `fc_law`'s own fields (`law_update`'s A9 computation), `null` while
-- `fc_law` is `nil` (off/taking/armed -- nothing to be "in band" of
-- yet). `fc_limit_hit` is still always `false` -- no consumer needs it
-- this stage (A9: the bands feed only `in_band` and M4's settle test).
local function push_flight_control_state(t)
    if client == nil then
        return
    end
    -- `json_escape_string` already returns a quoted literal (`core.
    -- lua`: `return "\"" .. escaped .. "\""`) -- `ai_pilot_wheel.lua`'s
    -- own `push_ai_pilot_wheel_state` wraps its result in a second pair
    -- of quotes (`'"' .. json_escape_string(value) .. '"'`), which
    -- double-quotes every non-null string field on that wire and
    -- produces invalid JSON (confirmed: `json.loads` rejects it) --
    -- found while building this function from the same idiom and
    -- actually running the output through a Lua interpreter, which
    -- nothing exercising that sibling function does today. Not fixed
    -- here (out of scope for this module); see `plans/flight-control/
    -- implementation.md`'s "Mode 1, Stage M1" section.
    local function text_or_null(value)
        if value == nil then
            return "null"
        end
        return json_escape_string(value)
    end
    local function bool_or_null(value)
        if value == nil then
            return "null"
        end
        if value then
            return "true"
        end
        return "false"
    end

    local goal_heading = fc_goal_heading_deg
    if fc_goal_turn ~= nil then
        -- "fc_goal_heading is null in turn mode" (Wire section).
        goal_heading = nil
    end

    local measured_heading = nil
    local self_data = safe_call(LoGetSelfData)
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        measured_heading = math.deg(self_data.Heading)
    end

    -- Plain telemetry passthrough, same reasoning as `measured_heading`
    -- above: `hold_altitude`/`level_flight`/`set_speed`'s "current"
    -- reading needs *something* the instant mode 1 takes, before any
    -- goal has ever been commanded (`fc_goal_altitude`/`fc_goal_speed`
    -- both start null) -- there is no AI pilot here reporting its own
    -- held value the way mode 2's overlay readback does.
    local measured_agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local radar_dist, radar_valid = safe_call(LoGetRadarAltimeter)
    local agl_source = nil
    local measured_altitude = nil
    if radar_valid then
        agl_source = "radar"
        measured_altitude = radar_dist
    elseif measured_agl ~= nil then
        agl_source = "dcs"
        measured_altitude = measured_agl
    end
    local measured_ias_mps = safe_call(LoGetIndicatedAirSpeed)
    local measured_speed = nil
    if type(measured_ias_mps) == "number" then
        measured_speed = measured_ias_mps * 3.6
    end

    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"fc_mode":"' .. fc_mode .. '"'
        .. ',"fc_take_seq":' .. fmt_num_or_null(fc_take_seq)
        .. ',"fc_goal_seq":' .. fmt_num_or_null(fc_goal_seq)
        -- security-m1-m2.md Finding A: echoes the one counter every
        -- `handle_flight_control_command` accept bumps, across every
        -- `cmd` kind, so body-layer can reconcile its own `wire_seq`
        -- against it after a restart (`wire_seq` resets to 0 per
        -- process; this does not, same as `fc_last_cmd_seq` itself
        -- never resetting on `on_stop`) instead of being silently
        -- stuck below it for the rest of the DCS session.
        .. ',"fc_last_cmd_seq":' .. fmt_num_or_null(fc_last_cmd_seq)
        .. ',"fc_take_origin":' .. text_or_null(fc_take_origin)
        .. ',"fc_takeover_mode":' .. text_or_null(fc_takeover_mode)
        .. ',"fc_goal_heading":' .. fmt_num_or_null(goal_heading)
        .. ',"fc_goal_altitude":' .. fmt_num_or_null(fc_goal_alt_m)
        .. ',"fc_goal_altitude_ref":' .. text_or_null(fc_goal_alt_ref)
        .. ',"fc_goal_speed":' .. fmt_num_or_null(fc_goal_ias_kmh)
        .. ',"fc_measured_heading":' .. fmt_num_or_null(measured_heading)
        .. ',"fc_measured_altitude":' .. fmt_num_or_null(measured_altitude)
        .. ',"fc_measured_speed":' .. fmt_num_or_null(measured_speed)
        .. ',"fc_in_band_heading":' .. bool_or_null(fc_law and fc_law.in_band_heading)
        .. ',"fc_in_band_altitude":' .. bool_or_null(fc_law and fc_law.in_band_altitude)
        .. ',"fc_in_band_speed":' .. bool_or_null(fc_law and fc_law.in_band_speed)
        .. ',"fc_agl_source":' .. text_or_null(agl_source)
        .. ',"fc_release_reason":' .. text_or_null(fc_release_reason)
        .. ',"fc_refuse_cause":' .. text_or_null(fc_refuse_cause)
        .. ',"fc_limit_hit":false'
        .. ',"fc_axes_pitch":' .. tostring(FC_AXES_ENABLED.pitch)
        .. ',"fc_axes_roll":' .. tostring(FC_AXES_ENABLED.roll)
        .. ',"fc_axes_pedal":' .. tostring(FC_AXES_ENABLED.pedals)
        .. ',"fc_axes_collective":' .. tostring(FC_AXES_ENABLED.collective) .. '}\n')
    if not ok then
        debug_log("flight-control send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- Mission restart / `LuaExportStop` / ownship death all reset to "off"
-- (Decision, Co-moving row 15) -- `run_flight_control`'s own envelope
-- check already covers a live "dead" edge; this covers the other two.
local function on_stop()
    fc_mode = "off"
    fc_captured = {}
    fc_take_seq = nil
    fc_pending_take_seq = nil
    fc_take_origin = nil
    fc_goal_seq = nil
    fc_last_arm_seq = nil
    fc_arm_last_t = nil
    fc_release_reason = nil
    fc_refuse_cause = nil
    fc_takeover_mode = nil
    fc_goal_heading_deg = nil
    fc_goal_turn = nil
    fc_goal_alt_m = nil
    fc_goal_alt_ref = nil
    fc_goal_ias_kmh = nil
    fc_last_frame_t = nil
    fc_env_low_ias_since_t = nil
    fc_last_stowed_pilot_capture = nil
    fc_last_steady_values = nil
    fc_law = nil
    fc_last_command = nil
    -- `fc_last_cmd_seq` deliberately NOT reset -- a stale, pre-restart
    -- command replayed after a reconnect must still be seen as stale,
    -- same "seq never goes backwards" posture the rest of this module
    -- relies on.
end

M.handle_flight_control_command = handle_flight_control_command
M.run_flight_control = run_flight_control
M.push_flight_control_state = push_flight_control_state
M.on_stop = on_stop

-- The control law's own pure functions, exported for the toy-plant
-- suite (`tests/test_flight_control_law.py`) to call directly -- none
-- of these five reads or writes a module-level local, so a test can
-- drive them with a synthetic state/measured/limits table and no DCS
-- mock at all (the plan's own "as pure functions over a state table
-- so luajit can test them").
M.law_init_at_take = law_init_at_take
M.law_apply_goal = law_apply_goal
M.law_update = law_update
M.law_outputs = law_outputs
M.law_turn_rate_at_bank = law_turn_rate_at_bank

-- Decision 28's rotor RPM seam, exported for the same reason -- a
-- dedicated unit test (`tests/test_flight_control_lua.py`'s own
-- `TestReadRotorRpmPct`) needs to call it directly rather than only
-- indirectly through `read_measured()`/the full per-frame loop.
M.read_rotor_rpm_pct = read_rotor_rpm_pct

return M
