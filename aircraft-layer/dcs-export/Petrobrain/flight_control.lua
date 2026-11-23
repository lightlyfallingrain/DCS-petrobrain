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
and handover. **BL-16 Stage 3** (`plans/flight-desired-state/plan.md`)
replaced the `fc_goal_*` wire-echo locals and the `flight_control` op's
own `cmd="goal"` handler with `apply_desired_changes_to_law`: the goal
now lives in `flight_desired`'s own `desired` table, applied here by
comparing its per-part stamps against what this module last applied --
`law_apply_goal`/`law_init_at_take`/`law_update`/
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
default): a park/unpark edge can only be detected by comparing against
a known previous state, so "unknown" is treated the same as "stay off",
never as a licence to assume unparked. **`held_targets()` is no longer
read here** (BL-16 Stage 3) -- the unpark-take seed comes from `flight_
desired.get()` instead (`build_take_seed`), which is itself seeded from
the overlay by `flight_desired.lua`'s own `reseed_from_overlay` at the
earlier off->m2 edge; `ai_pilot_wheel` stays a dependency only for `is_
parked`/`stick_park_raw`.

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
pedal** (command = `-arg 1102`). Entered below. **`FC_AXES_ENABLED.
collective` is now `true`** (sortie 2026-11-20, `docs/acceptance/
2026-11-20-sortie-feedback.md`, user: "absolutely yes. Now." -- its
step-response lag and VS behaviour are still unmeasured, the same two
figures M0-B needed before pedal was enabled, but the user's own
direction overrides the judgement call that previously kept it off).
**Flight 6 also measured M0-F (plan, Decision 4): once a write stops,
the arg holds Petrovich's last-commanded value until the player
physically moves that control** -- arg 1102 sat 16+ s with the lever
untouched after `release`. Confirmed for collective; pitch/roll/pedals
are still owed. This matches Decision 4 exactly ("the release jump is
not handled, the pilot matches his controls") and needs no code change
-- `request_release`'s own effect already just
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

-- Slip-ball ADI draw args per seat (read-only, same class as `SEAT_ARGS`
-- above -- a gauge, never written). Sourced from `DCS-Skunkworks/dcs-bios`
-- (`aircraft-layer/research/2026-11-20-slip-ball-recon.md` finding (b)),
-- not yet cross-checked against this project's own installed tree.
-- Read-only readout for calibration (sortie 2026-11-20, user: "we need a
-- to read the slip ball ... since it guides pedal adjustmens.") -- the
-- values below feed only the status line, never `law_*`; sign/scale is
-- unmeasured (the recon note's own Reproducible Test).
local SLIP_BALL_ARGS = { pilot = 943, operator = 784 }

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
-- 2026-11-18, module header) and now actually written, per `FC_AXES_
-- ENABLED.collective` below.
local SIGN = { pitch = 1.0, roll = 1.0, pedals = -1.0, collective = -1.0 }

-- Per-axis enable flags (plan, M1 bullet: "a per-axis enable flag that
-- defaults off for pedal and collective until M0-B and M0-C" -- each
-- axis gated on its own probe). Pitch/roll are the axes probe v2
-- actually exercised; pedals is enabled on M0-B's own measurement
-- (module header, both sign/scale AND the step-response lag). **Collective
-- enabled, sortie 2026-11-20** (`docs/acceptance/2026-11-20-sortie-
-- feedback.md`, user: "absolutely yes. Now.") -- sign/scale is measured
-- (flight 6) but its own lag/VS response is still unmeasured (the same
-- bar pedal cleared before being enabled); the user's direction accepts
-- that gap rather than waiting for M0-E. An unmapped/unmeasured axis is
-- left entirely with the player (safe), never written with a guessed
-- sign/scale.
local FC_AXES_ENABLED = { pitch = true, roll = true, pedals = true, collective = true }

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

-- M2 control law constants -- **moved to `flight_profile.lua`'s
-- `PROFILES["Mi-24P"]` table, BL-16 lift-vector law Stage LV-0**
-- (`plans/flight-lift-vector/plan.md`): every gain/time-constant the
-- five pure law functions below read is now a `profile` field, values
-- unchanged (confirmed bit-identical by the toy-plant and whole-module
-- test suites). `flight_profile.lua`'s own header carries what each one
-- is owed/unmeasured against -- not duplicated here. `GRAVITY_MPS2`
-- stays a plain local (physics, not a tunable gain).
local GRAVITY_MPS2 = 9.81

-- Rotor-RPM-floor/retreating-blade-stall margins and the pedal-bias
-- gains (`K_BREAK_PEDAL_BIAS`/`K_TURN_COORD_PEDAL`) -- **moved to
-- `flight_profile.lua`** (LV-0, same move as the block above; the RPM-
-- floor/stall *thresholds* themselves stay wire-carried in `limits`,
-- body-layer's `tuning.py`, a different mechanism from this profile).

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

-- `TAU_ACCEL_FILTER_S` (the `a_x`/`a_z` fallback-derivative filter
-- constant) -- **moved to `flight_profile.lua`** (LV-0).

-- Output-stage rate limit (axis units per second) -- a defensive cap
-- on how fast any written axis value may move frame to frame, on top
-- of whatever the law's own integrators already produce; not itself
-- behaviour the pilot would tune (it only guards against a shaper bug
-- producing a jump), so kept generous.
local OUTPUT_RATE_LIMIT_PER_S = 4.0

-- `TURN_SETTLE_DEG_S` -- **moved to `flight_profile.lua`** (LV-0; read
-- inside `law_update`, a pure function, so it travels with `profile`).

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

--[[ `law_apply_goal(state, goal, limits, profile)` -- Decision 21/the
plan's "Wire" section's own one-shot goal application, called once when
a `goal` command is applied or a take/unpark-take happens (never
re-applied every frame from the wire echo -- that would re-trigger
`level_off`'s own turn-mode request every poll and undo the internal
settle-to-heading transition below). `goal` fields mirror the wire's
own shape (`heading_deg`/`turn`/`alt_m`/`alt_ref`/`ias_kmh`, any subset
present). Returns a new state; never mutates `state` in place (every
`law_*` function in this module follows that convention, so the toy-
plant tests can hold a reference to the state before a call and compare
it against the state after). `profile` (BL-16 lift-vector law, LV-0,
`flight_profile.lua`) carries this function's own gains -- currently
only `law_turn_rate_at_bank` (unchanged signature, reads the plain
`GRAVITY_MPS2` local) is called from here, so `profile` is accepted for
signature consistency with the other four `law_*` functions but not yet
read directly. ]]--
local function law_apply_goal(state, goal, limits, profile)
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
            -- A new break starts its own pedal-bias tally from zero
            -- (same "a rate belongs to the command that set it"
            -- reasoning as `break_entry_h_m` on this line).
            next_state.break_pedal_bias_accum = 0.0
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

-- `law_init_at_take(measured, limits, command, seed, profile)` -- Decision 24's
-- "At take" section. `command` is the already SIGN-mapped (per
-- `SIGN.*`) captured axis value for every axis, in the same domain the
-- output stage writes (so `law_outputs` on this very state, with zero
-- attitude/rate error, reproduces `command` exactly -- "the output is
-- continuous at take, bit-exact").
--
-- `seed` (BL-16 sortie 2026-11-20, `plans/flight-control/debug.md`) is
-- an optional table -- `{heading_deg, alt_m, alt_ref, speed_kmh}`, any
-- subset present -- carrying mode 2's own *set* targets (the AI-wheel
-- overlay's held course/altitude/speed, read live off `ai_pilot_wheel`
-- by the unpark-take call site below; `nil` for every other take,
-- voice included). Decision 24's own "fall back to current measured
-- state when not known" governs every field independently: a field
-- `seed` omits (or that fails `tonumber`) falls back to the bank-at-
-- capture heading/turn-mode heuristic, the stopping-height formula, or
-- the measured IAS, exactly as before `seed` existed.
--
-- The debug report's own finding: without this, an unpark mid-break
-- (still banked, still turning) read that transient bank as "the pilot
-- is deliberately holding a turn" (the bank-at-capture heuristic below,
-- still the right call for a *voice* take, where the player really did
-- just roll into a bank on the raw stick) and held its momentary rate
-- forever, with nothing to roll it back out -- compounding as the
-- mode-2 speed command already in flight kept raising the kinematic
-- bank `phi_kinematic = atan(V_t*r/g)` needs for that same rate, with
-- no corrective pressure the pilot could see. A known mode-2 heading
-- target takes heading mode unconditionally (never turn mode), since
-- the dial is the deliberate state to resume, not the bank the AI
-- wheel happened to be at the instant of the unpark.
local function law_init_at_take(measured, limits, command, seed, profile)
    seed = seed or {}
    local heading_mode = math.abs(measured.bank_deg) < limits.takeover_level_bank_deg
    local heading_goal_deg = measured.psi_deg
    if type(seed.heading_deg) == "number" then
        heading_mode = true
        heading_goal_deg = seed.heading_deg
    end
    -- `A_v` in the plan's own "h + w*|w|/(2*A_v)" is the channel's
    -- deceleration capability (`profile.alt_accel_cap_mps2`), not the
    -- velocity ceiling `max_climb_vs_mps` -- confirmed a real bug
    -- here by the toy-plant suite, which drove an actual climb
    -- through this formula and found the shaper overshoot-then-
    -- reverse the velocity-ceiling version produces (the wrong
    -- stopping height asks for more deceleration than the channel
    -- can deliver).
    local alt_goal_m = law_stopping_height(measured.h_m, measured.w_mps, profile.alt_accel_cap_mps2)
    local alt_goal_ref = "agl"
    if type(seed.alt_m) == "number" then
        alt_goal_m = seed.alt_m
        -- `ai_pilot_wheel`'s own "R"/"B" letters (radar/AGL,
        -- barometric/MSL) map onto this module's own "agl"/"baro" --
        -- any other value (including nil) is read as "agl", the same
        -- default as no seed at all.
        if seed.alt_ref == "B" then
            alt_goal_ref = "baro"
        end
    end
    local speed_goal_mps = measured.ias_mps
    if type(seed.speed_kmh) == "number" then
        speed_goal_mps = seed.speed_kmh / 3.6
    end
    return {
        turn_mode = not heading_mode,
        heading_goal_deg = heading_goal_deg,
        turn_goal_deg_s = measured.r_deg_s,
        psi_ref = measured.psi_deg,
        r_ref = measured.r_deg_s,
        alt_goal_m = alt_goal_m,
        alt_goal_ref = alt_goal_ref,
        h_ref = measured.h_m,
        w_ref = measured.w_mps,
        speed_goal_mps = speed_goal_mps,
        v_ref = measured.ias_mps,
        dv_ref = 0.0,
        theta_d = measured.pitch_deg,
        phi_d = measured.bank_deg,
        phi_i = 0.0,
        t_p = command.pitch + profile.k_q * measured.q_deg_s,
        t_r = command.roll + profile.k_p * measured.p_deg_s,
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
        -- BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) --
        -- the running total of `K_BREAK_PEDAL_BIAS` already folded into
        -- `t_y` for the break currently (or most recently) active, so
        -- it can be unwound exactly once that break settles (step 5,
        -- "settling clears it"). A fresh activation starts clean, same
        -- reasoning as `rate_override_deg_s`/`break_entry_h_m` above.
        break_pedal_bias_accum = 0.0,
        -- Sortie 2026-11-20 -- the turn-coordination pedal overlay
        -- (step 5, `K_TURN_COORD_PEDAL`), zero until the first
        -- `law_update` recomputes it from `r_d`. Unlike `break_pedal_
        -- bias_accum`, this is never accumulated -- see its own
        -- comment in `law_update` for why a position overlay needs no
        -- running total to unwind. Zero here keeps `law_outputs` on
        -- this take state bit-exact (Decision 24): nothing is added
        -- to `t_y` before the first `law_update` frame.
        turn_coord_pedal = 0.0,
    }
end

-- `law_update(state, dt, measured, limits, profile)` -- one frame of "The
-- control law" (plan steps 1-5 plus the pedal/collective halves of
-- step 3/5), advancing every shaper reference and integrator. Pure:
-- returns a new state, never mutates `state`. `law_outputs` (below)
-- reads the result out; this function does not itself produce an axis
-- command.
local function law_update(state, dt, measured, limits, profile)
    local next_state = {}
    for k, v in pairs(state) do next_state[k] = v end

    -- Step 1: heading/turn-rate shaper.
    local r_max = law_turn_rate_at_bank(limits.max_turn_bank_deg, measured.v_t_mps)
    if state.turn_mode then
        local r_goal = state.turn_goal_deg_s
        local accel_limit = profile.heading_accel_cap_deg_s2
        if r_max > 0.0 then
            accel_limit = math.min(profile.heading_accel_cap_deg_s2, r_max / profile.t_roll)
        end
        local dr = law_clamp(r_goal - state.r_ref, -accel_limit * dt, accel_limit * dt)
        next_state.r_ref = state.r_ref + dr
        next_state.psi_ref = law_wrap360(state.psi_ref + next_state.r_ref * dt)
        -- "level_off goes through turn mode at 0. When r_ref reaches 0,
        -- Lua switches to heading mode with psi_goal = psi_ref" --
        -- the stopping point, not the heading at the moment "level off"
        -- was spoken.
        if math.abs(r_goal) < 1e-6 and math.abs(next_state.r_ref) < profile.turn_settle_deg_s then
            next_state.turn_mode = false
            next_state.heading_goal_deg = next_state.psi_ref
        end
    else
        -- Decision 27 -- while a break's rate override is active, the
        -- rate ceiling and accel-limit (roll-in time) both come from
        -- it instead of the ordinary `max_turn_bank_deg`-derived rate;
        -- the accel limit uses the same roll-in formula (`r_max /
        -- t_roll`) `turn_mode` above already uses, just against the
        -- override's own magnitude.
        local rate_limit = r_max > 0.0 and r_max or 30.0
        local accel_limit = profile.heading_accel_cap_deg_s2
        if state.rate_override_deg_s ~= nil then
            rate_limit = math.abs(state.rate_override_deg_s)
            accel_limit = rate_limit / profile.t_roll
        end
        local err = law_wrap180(state.heading_goal_deg - state.psi_ref)
        local a_ref = profile.omega_heading * profile.omega_heading * err
            - 2.0 * profile.law_zeta * profile.omega_heading * state.r_ref
        a_ref = law_clamp(a_ref, -accel_limit, accel_limit)
        next_state.r_ref = law_clamp(state.r_ref + a_ref * dt, -rate_limit, rate_limit)
        next_state.psi_ref = law_wrap360(state.psi_ref + next_state.r_ref * dt)
    end
    local r_d = next_state.r_ref
        + profile.k_heading_track * law_wrap180(next_state.psi_ref - measured.psi_deg)

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
    local a_ref_h = profile.omega_alt * profile.omega_alt * err_h
        - 2.0 * profile.law_zeta * profile.omega_alt * state.w_ref
    a_ref_h = law_clamp(a_ref_h, -profile.alt_accel_cap_mps2, profile.alt_accel_cap_mps2)
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
    local a_ref_v = profile.omega_speed * profile.omega_speed * err_v
        - 2.0 * profile.law_zeta * profile.omega_speed * state.dv_ref
    a_ref_v = law_clamp(a_ref_v, -profile.speed_accel_cap_mps2, profile.speed_accel_cap_mps2)
    next_state.dv_ref = law_clamp(state.dv_ref + a_ref_v * dt, -limits.max_accel_mps2, limits.max_accel_mps2)
    next_state.v_ref = state.v_ref + next_state.dv_ref * dt

    -- Step 2: desired accelerations.
    local a_z_d = a_ref_h + profile.k_vs_error * (next_state.w_ref - measured.w_mps)
        + profile.k_alt_error * (next_state.h_ref - measured.h_m)
    local a_x_d = a_ref_v + profile.k_speed_error * (next_state.v_ref - measured.ias_mps)

    -- Filtered actual accelerations (dV/dt, dw/dt -- plan's own
    -- fallback, `LoGetAccelerationUnits`'s body-frame mapping being
    -- unconfirmed, module header).
    local alpha = math.min(1.0, dt / profile.tau_accel_filter_s)
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
    --
    -- Altitude/collective split (sortie 2026-11-20, user: "all the axes
    -- are interdependent... use then all to maintain desired state" --
    -- also the steep-break speed-bleed observation that prompted
    -- enabling collective at all): `d_theta` below only ever picks up
    -- `a_z_d` (the altitude channel's own demand) when `collective_
    -- limited` is true -- so collective alone carries 100% of the
    -- altitude error whenever it still has room, and pitch only takes
    -- over the vertical job once collective is maxed/RPM-floored/
    -- stall-margined. This already *is* "favour collective"; it was
    -- already written this way before collective was ever enabled, so
    -- enabling the axis (`FC_AXES_ENABLED.collective` above) is what
    -- makes it take effect on the real aircraft for the first time,
    -- not a change to this split itself.
    local collective_saturated = state.u_c >= 0.999 or state.u_c <= -0.999
    local rotor_rpm_limited = measured.rotor_rpm_pct
        <= (limits.rotor_rpm_floor_pct + profile.rotor_rpm_near_floor_margin_pct)
    local blade_stall_limited = (measured.ias_mps * 3.6)
        >= (limits.retreating_blade_stall_ias_kmh - profile.retreating_blade_stall_margin_kmh)
    local collective_limited = collective_saturated or rotor_rpm_limited or blade_stall_limited
    local d_theta = -profile.k_tilt_from_ax * (a_x_d - next_state.a_x_f)
    if collective_limited then
        d_theta = d_theta + profile.k_tilt_from_az_saturated * (a_z_d - next_state.a_z_f)
    end
    next_state.theta_d = law_clamp(state.theta_d + d_theta * dt, profile.theta_min_deg, profile.theta_max_deg)

    local c_dot = profile.k_collective * (a_z_d - next_state.a_z_f)
    if c_dot > 0.0 then
        if state.t_y >= (profile.pedal_limit_positive - profile.pedal_near_limit_margin) then
            c_dot = math.min(c_dot, profile.collective_rate_cap_near_pedal_limit)
        end
        -- Only a further *increase* is ever capped by either guard --
        -- neither forces collective down, so level flight with
        -- collective already low is untouched.
        if rotor_rpm_limited then
            c_dot = math.min(c_dot, profile.collective_rate_cap_near_rpm_floor)
        end
        if blade_stall_limited then
            c_dot = math.min(c_dot, profile.collective_rate_cap_near_blade_stall)
        end
    end
    next_state.u_c = law_clamp(state.u_c + c_dot * dt, -1.0, 1.0)

    local phi_kinematic_deg = 0.0
    if measured.v_t_mps > 1.0 then
        phi_kinematic_deg = math.deg(math.atan(measured.v_t_mps * math.rad(r_d) / GRAVITY_MPS2))
    end
    local d_phi_i = profile.k_bank_increment * (r_d - measured.r_deg_s)
    next_state.phi_i = state.phi_i + d_phi_i * dt
    -- F-M1 (mode-1 batch): "remove the 30 degree limit. Set no limit
    -- for now" -- no clamp against `limits.max_bank_deg` any more (the
    -- field itself is gone from the wire); a kinematic bank request is
    -- self-limiting (it saturates toward +-90 only as `r_d`/`V_t` grow
    -- large), and the output stage's own `law_clamp(u_roll, -1, 1)`
    -- in `law_outputs` is the real physical ceiling.
    next_state.phi_d = phi_kinematic_deg + next_state.phi_i

    -- Step 4: inner tilt-loop integrators.
    next_state.t_p = state.t_p + profile.k_theta_i * (next_state.theta_d - measured.pitch_deg) * dt
    next_state.t_r = state.t_r + profile.k_phi_i * (next_state.phi_d - measured.bank_deg) * dt

    -- Step 5: pedal (collective-coupling feedforward, Decision 27's own
    -- pedal-into-the-turn bias while a break's rate override is active
    -- -- no slip-ball feedback, module header). The turn-coordination
    -- overlay (`next_state.turn_coord_pedal`, below this integrator) is
    -- a separate, non-integrated term added only at `law_outputs`.
    --
    -- BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`): the
    -- collective-coupling feedforward only applies while the
    -- collective axis is actually written to the aircraft (`measured.
    -- collective_enabled`, set from `FC_AXES_ENABLED.collective` by
    -- `read_measured()`, now `true` by default). While disabled, `u_c`/
    -- `c_dot` above are an internal-only bookkeeping value with no
    -- effect on the real aircraft; feeding that rate into the pedal
    -- instead compounded a genuine altitude-hold tracking error (the
    -- shaper's own `h_ref` marches toward its goal with no real
    -- coupling back from the never-written collective) into a
    -- continuously *ramping* pedal bias with nothing to arrest it --
    -- confirmed with the toy-plant harness: a steady 5 m real/goal
    -- altitude offset alone, held for 20 s with collective disabled,
    -- drove the pedal from -0.001 to -0.101 under the unguarded term.
    -- This never changes pitch/roll's own feedback, only this one
    -- feedforward term. The guard itself is kept (not removed now that
    -- collective defaults on) so the axis can still be switched off
    -- live without this term going unstable again.
    local d_t_y = 0.0
    if measured.collective_enabled then
        d_t_y = profile.k_pedal_from_collective_rate * c_dot
    end
    -- BL-16 sortie 2026-11-20: `break_bias` is tallied separately from
    -- `d_t_y` so it can be unwound exactly once the break settles
    -- (below) -- previously this bias was integrated into `t_y` and
    -- never reversed, leaving a standing pedal offset from the break
    -- indefinitely, including into later, unrelated flight.
    local break_bias = 0.0
    if state.rate_override_deg_s ~= nil then
        local break_sign = state.rate_override_deg_s > 0.0 and 1.0 or -1.0
        break_bias = profile.k_break_pedal_bias * break_sign
    end
    local t_y_before_break_step = state.t_y
    next_state.t_y = law_clamp(
        state.t_y + (d_t_y + break_bias) * dt, profile.pedal_limit_negative, profile.pedal_limit_positive)
    -- Tracks the *actually applied* change to `t_y` (post-saturation),
    -- not the nominal `break_bias * dt` -- the pedal axis saturates
    -- well before a sustained break settles (confirmed with the
    -- toy-plant harness: `K_BREAK_PEDAL_BIAS` alone reaches
    -- `PEDAL_LIMIT_POSITIVE` in 2.5 s), so a nominal tally overshoots
    -- the unwind by whatever the clamp already absorbed. While
    -- `d_t_y` is zero (collective disabled), this accumulator equals
    -- exactly the break's own contribution; once collective is enabled
    -- the two terms share one clamp and are no longer separable
    -- post-saturation -- Flight M-A's own call, same as every other
    -- gain in this step.
    if state.rate_override_deg_s ~= nil then
        next_state.break_pedal_bias_accum =
            (state.break_pedal_bias_accum or 0.0) + (next_state.t_y - t_y_before_break_step)
    else
        next_state.break_pedal_bias_accum = state.break_pedal_bias_accum or 0.0
    end

    -- Sortie 2026-11-20, user: "turn right 50 -> turns but does not use
    -- pedals at all. Use pedals." -- proportional to `r_d` (the same
    -- commanded rate step 1 already computed this frame, above), so an
    -- ordinary turn carries pedal too.
    --
    -- Deliberately a **position overlay, not a rate fed into the `t_y`
    -- integrator** (unlike `d_t_y`/`break_bias` above) -- recomputed
    -- fresh from the *current* `r_d` every frame and added only at
    -- `law_outputs`, never folded into `state.t_y` itself. Trying the
    -- rate-into-the-integrator shape first (toy-plant harness) showed
    -- why that is wrong here: during a sustained ordinary turn `r_d`
    -- stays roughly constant for many seconds, so a rate term integrates
    -- without bound and saturates the pedal axis almost immediately --
    -- appropriate for a break's own short, aggressive `break_bias`
    -- (which is *meant* to pin the pedal hard over), wrong for an
    -- ordinary turn's coordination, which should track the turn rate
    -- itself, not its time integral. A position overlay has no such
    -- accumulation, is exactly zero whenever `r_d` is (so it needs no
    -- separate "unwind" bookkeeping -- it already is the unwind, every
    -- frame), and cannot by itself defeat the take-time pedal-drift fix
    -- above (it adds nothing at `law_init_at_take`, below).
    --
    -- Zero below `profile.turn_settle_deg_s` (step 1's own "effectively
    -- stopped turning" threshold, reused here) rather than a bare `~=
    -- 0.0` check -- a critically-damped heading error asymptotically
    -- approaches zero and never quite bit-exactly reaches it, so a bare
    -- check would leave a vanishingly small but nonzero pedal forever.
    -- Suppressed while a break's rate override is active
    -- (`k_break_pedal_bias` above already supplies a turn-direction
    -- bias for that case) so the two never both feed the same frame --
    -- see `k_turn_coord_pedal`'s own comment for the sign assumption.
    if state.rate_override_deg_s == nil and math.abs(r_d) >= profile.turn_settle_deg_s then
        next_state.turn_coord_pedal = profile.k_turn_coord_pedal * r_d
    else
        next_state.turn_coord_pedal = 0.0
    end

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
        -- BL-16 sortie 2026-11-20: unwind exactly the pedal bias this
        -- break added (`break_pedal_bias_accum`, tallied above) now
        -- that it has settled -- without this the bias stood forever,
        -- carried into whatever the pilot/Petrovich did next.
        next_state.t_y = law_clamp(
            next_state.t_y - next_state.break_pedal_bias_accum,
            profile.pedal_limit_negative, profile.pedal_limit_positive)
        next_state.break_pedal_bias_accum = 0.0
    end

    return next_state
end

-- `law_outputs(state, measured, profile)` -- reads the four axis
-- commands out of `state`, already in the sign-mapped domain the output
-- stage writes (clamped defensively; `law_update`'s own saturation
-- already keeps `u_c`/`t_y` in range, but the pitch/roll inner-loop
-- terms below are not themselves saturated upstream). Pure, no
-- mutation.
--
-- `pedals` adds `state.turn_coord_pedal` (sortie 2026-11-20, step 5) on
-- top of `t_y` -- the one deliberate exception to "every output comes
-- straight from an integrator in `state`": this term is recomputed
-- fresh each `law_update` frame and never itself integrated, so adding
-- it here rather than folding it into `t_y` is what keeps it from
-- needing its own "unwind" bookkeeping (see `law_update`'s own
-- comment). `law_init_at_take` sets it to `0.0`, so Decision 24's
-- bit-exact-at-take guarantee is untouched: calling this on a take
-- state (before any `law_update` has run) adds exactly zero.
local function law_outputs(state, measured, profile)
    local u_pitch = state.t_p + profile.k_theta * (state.theta_d - measured.pitch_deg)
        - profile.k_q * measured.q_deg_s
    local u_roll = state.t_r + profile.k_phi * (state.phi_d - measured.bank_deg)
        - profile.k_p * measured.p_deg_s
    return {
        pitch = law_clamp(u_pitch, -1.0, 1.0),
        roll = law_clamp(u_roll, -1.0, 1.0),
        pedals = law_clamp(state.t_y + (state.turn_coord_pedal or 0.0), -1.0, 1.0),
        collective = law_clamp(state.u_c, -1.0, 1.0),
    }
end

-- `SIGN`-mapped command value for one axis of a raw captured-arg table
-- (`fc_captured`-shaped); `0.0` when that axis was never captured (any
-- axis with its `FC_AXES_ENABLED` flag off) -- internal law state
-- still needs a number for every axis even when nothing will ever be
-- written for it.
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
local fc_arm_last_t = nil

-- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 1,
-- "who reads it") -- which `desired` stamp (the wire request `seq` that
-- last wrote that part, or `flight_desired`'s own internal-write floor)
-- this module has already applied into `fc_law`. `apply_desired_
-- changes_to_law` below compares `flight_desired.get()`'s own stamps
-- against these every active frame and applies only the parts that
-- changed -- "mode 1 applies desired by stamp" (plan, "Affected
-- modules"). `nil` means "nothing applied yet this activation" (cleared
-- on every mode change away from active, same as `fc_last_command`).
local fc_applied_stamp_hdg = nil
local fc_applied_stamp_alt = nil
local fc_applied_stamp_spd = nil

-- The park/unpark edge tracker for the off->armed self-arm clause
-- (Stage 2 review-s12.md Required Fix 2) -- `fc_was_parked` is `is_
-- parked()`'s own raw value from the previous frame, physical state
-- only, never reset by `on_stop`/`reset` (a body-layer restart does not
-- change whether the player is actually parked). `fc_off_armable_
-- since_edge` is the derived "may self-arm from off" window: set true
-- only on a genuine rising edge (`not fc_was_parked and is_parked`)
-- while `fc_mode == "off"`, so a lease that only becomes fresh a few
-- frames after the edge still gets to arm (the ordinary "every park
-- gives him the overlay" case), and cleared on unpark and by `on_stop`/
-- `reset` -- Q6: "after `reset(epoch)` while parked, armed is cleared
-- and nothing re-arms it until the next park edge." Without this, the
-- old level-triggered check (`is_parked == true and fc_mode == "off"`
-- alone) re-armed the instant a fresh lease arrived, even with no
-- unpark/re-park in between, which is exactly what Q6 forbids.
local fc_was_parked = nil
local fc_off_armable_since_edge = false
local fc_release_reason = nil
local fc_refuse_cause = nil
local fc_takeover_mode = nil

-- BL-16 sortie 2026-11-20, `docs/acceptance/2026-11-20-sortie-feedback.
-- md` -- the body-layer process-start reset's own generation counter,
-- echoed on every status line so body-layer can confirm this exact
-- epoch landed. Only ever written by `reset()` below.
local fc_reset_epoch = nil

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
        -- BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) --
        -- `law_update`'s own pedal step reads this to decide whether
        -- the collective-coupling feedforward is meaningful: `FC_AXES_
        -- ENABLED` is a module-level local the law's own pure
        -- functions never read directly (module docstring, "pure
        -- functions over a state table"), so it rides in on `measured`
        -- instead, the same way every other config-derived fact this
        -- loop needs reaches the law.
        collective_enabled = FC_AXES_ENABLED.collective,
    }
end

-- ============================================================
-- BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/
-- plan.md`, section A): the estimator. Runs every frame, in every
-- mode (warm at a take), gated internally to `profile.law_hz` on DCS
-- model time (never wall clock -- user, 2026-11-20: "DCS may be paused
-- by user"). Lives OUTSIDE `fc_law` -- reset by a model-time gap,
-- `on_stop`/`reset`, and the first sample, never by a mode change.
-- Nothing in `law_*` reads its output yet (LV-1's own job) -- it only
-- writes the new `fc_est_*` status fields and the per-frame trace, so
-- it cannot change today's flying behaviour (the "shadow" half of
-- LV-0's "instruments and shadow").
--
-- **Mutates its own state table in place, unlike `law_*`'s "always
-- return a new state" convention** -- a deliberate departure: the ring
-- buffers below are fixed-size, preallocated arrays, and a `law_*`-
-- style full copy every tick would itself be the O(window) allocation
-- this design exists to avoid (perf-plan-review: "ring buffers are
-- fixed size, preallocated once... never a per-frame `table.insert`").
-- Tests call `est_sample`/`est_ring_*` repeatedly on one state table
-- and read the fields back after each call.
-- ============================================================

-- Ring capacity: generous headroom over any window this profile uses
-- today (`w_v_s`/`w_a_s`/`w_a2_s`/`w_b` are all <= 0.2 s; at `law_hz`
-- = 30 that is <= 6 samples) -- fixed, never resized, so a later
-- profile change within this bound needs no code change.
local EST_RING_CAPACITY = 64

-- A fixed-size ring buffer of (t, value) samples plus the incremental
-- least-squares sums (sum_t, sum_t2, sum_v, sum_tv) that let
-- `est_ring_slope`/`est_ring_mean` read the current window's slope/
-- mean in O(1), without ever refitting over the stored samples.
local function est_ring_new()
    local t_arr, v_arr = {}, {}
    for i = 1, EST_RING_CAPACITY do
        t_arr[i] = 0.0
        v_arr[i] = 0.0
    end
    return {
        t = t_arr, v = v_arr, head = 0, count = 0,
        sum_t = 0.0, sum_t2 = 0.0, sum_v = 0.0, sum_tv = 0.0, t0 = nil,
    }
end

-- Re-primes a ring from empty -- used on a `dt > DT_CAP` gap, the
-- first sample ever, and `on_stop`/`reset` (plan, "Reset/priming": "a
-- stall must never produce an acceleration spike").
local function est_ring_reset(ring)
    ring.head = 0
    ring.count = 0
    ring.sum_t = 0.0
    ring.sum_t2 = 0.0
    ring.sum_v = 0.0
    ring.sum_tv = 0.0
    ring.t0 = nil
end

-- Pushes one (t, value) sample and evicts whatever has aged out of
-- `window_s`, updating the incremental sums in O(1) amortized (add the
-- newest sample, subtract each sample that ages out this call -- never
-- a refit over the stored window). `ring.t0` rebases every timestamp
-- to the ring's own first sample so the sums stay well-conditioned
-- over a long mission (model time keeps growing; the sums never see
-- more than `window_s` seconds of absolute magnitude).
local function est_ring_push(ring, t, value, window_s)
    if ring.t0 == nil then
        ring.t0 = t
    end
    local rt = t - ring.t0
    ring.head = (ring.head % EST_RING_CAPACITY) + 1
    ring.t[ring.head] = rt
    ring.v[ring.head] = value
    ring.count = math.min(ring.count + 1, EST_RING_CAPACITY)
    ring.sum_t = ring.sum_t + rt
    ring.sum_t2 = ring.sum_t2 + rt * rt
    ring.sum_v = ring.sum_v + value
    ring.sum_tv = ring.sum_tv + rt * value

    while ring.count > 1 do
        -- The oldest live sample sits `count - 1` slots behind `head`
        -- (`head` itself, 0 back, is the newest): index =
        -- `((head - 1 - (count - 1)) % CAPACITY) + 1`, i.e.
        -- `((head - count) % CAPACITY) + 1`.
        local oldest_idx = ((ring.head - ring.count) % EST_RING_CAPACITY) + 1
        local oldest_t = ring.t[oldest_idx]
        if rt - oldest_t <= window_s then
            break
        end
        ring.sum_t = ring.sum_t - oldest_t
        ring.sum_t2 = ring.sum_t2 - oldest_t * oldest_t
        ring.sum_v = ring.sum_v - ring.v[oldest_idx]
        ring.sum_tv = ring.sum_tv - oldest_t * ring.v[oldest_idx]
        ring.count = ring.count - 1
    end
end

-- Least-squares slope (dv/dt) of the ring's current window -- 0.0 with
-- fewer than 2 samples or a degenerate (zero-span) window.
local function est_ring_slope(ring)
    if ring.count < 2 then
        return 0.0
    end
    local n = ring.count
    local denom = n * ring.sum_t2 - ring.sum_t * ring.sum_t
    if denom == 0.0 then
        return 0.0
    end
    return (n * ring.sum_tv - ring.sum_t * ring.sum_v) / denom
end

-- Running mean of the ring's current window -- 0.0 with no samples.
local function est_ring_mean(ring)
    if ring.count < 1 then
        return 0.0
    end
    return ring.sum_v / ring.count
end

local function est_ring_update_slope(ring, t, value, window_s)
    est_ring_push(ring, t, value, window_s)
    return est_ring_slope(ring)
end

local function est_ring_update_mean(ring, t, value, window_s)
    est_ring_push(ring, t, value, window_s)
    return est_ring_mean(ring)
end

-- Standard kinematic Euler-rate transform from body rates (deg/s,
-- `p`/`q`/`r` already in the project's own roll/pitch/yaw convention --
-- `read_measured()`'s own `p_deg_s`/`q_deg_s`/`r_deg_s`) and attitude
-- (deg) -- the rates an attitude indicator would show, as opposed to
-- the body rates a rate gyro reads, which differ whenever the aircraft
-- is banked (plan's own worked example: a steady 60 deg bank turn
-- reads `q ~= psi_dot*sin(phi)` in body rates, `~= 0` in Euler rates --
-- `TestEulerRateTransform` below pins exactly this). The `cos(theta)`
-- division (near-vertical pitch) is guarded the same fail-soft way the
-- rest of this module guards divisions -- returns `0.0` for `psi_dot`
-- rather than a NaN/inf blow-up.
local function est_euler_rates(p_deg_s, q_deg_s, r_deg_s, phi_deg, theta_deg)
    local p = math.rad(p_deg_s)
    local q = math.rad(q_deg_s)
    local r = math.rad(r_deg_s)
    local phi = math.rad(phi_deg)
    local theta = math.rad(theta_deg)
    local cos_theta = math.cos(theta)
    local tan_theta = math.tan(theta)
    local phi_dot = p + q * math.sin(phi) * tan_theta + r * math.cos(phi) * tan_theta
    local theta_dot = q * math.cos(phi) - r * math.sin(phi)
    local psi_dot = 0.0
    if math.abs(cos_theta) > 1e-3 then
        psi_dot = (q * math.sin(phi) + r * math.cos(phi)) / cos_theta
    end
    return math.deg(phi_dot), math.deg(theta_dot), math.deg(psi_dot)
end

-- Module-level estimator state -- lives for the whole Lua session, not
-- reset by a mode change (it runs in every mode). `est_reset` (below)
-- is the only thing that re-primes it.
local fc_est = {
    sample_t = nil,
    last_law_t = nil,
    rings = {
        pos_n = est_ring_new(), pos_u = est_ring_new(), pos_e = est_ring_new(),
        vec_n = est_ring_new(), vec_u = est_ring_new(), vec_e = est_ring_new(),
        acc1_n = est_ring_new(), acc1_u = est_ring_new(), acc1_e = est_ring_new(),
        acc2_n = est_ring_new(), acc2_u = est_ring_new(), acc2_e = est_ring_new(),
        ball = est_ring_new(),
    },
    v = { n = 0.0, u = 0.0, e = 0.0 },
    v_unselected = { n = 0.0, u = 0.0, e = 0.0 },
    a = { n = 0.0, u = 0.0, e = 0.0, f = 0.0, r = 0.0 },
    euler = { phi_dot = 0.0, theta_dot = 0.0, psi_dot = 0.0 },
    ball = 0.0,
    v_g = 0.0, v_g_f = 0.0, v_g_r = 0.0,
    lambda = 0.0,
}

-- Re-primes every ring and derived field -- `dt > DT_CAP` (pause,
-- stall), `on_stop`/`reset`, and the first sample ever (Co-moving
-- Fields: "estimator ring buffers and running averages... re-primed
-- from the current sample; next `a` is finite and near zero").
local function est_reset(est)
    est.sample_t = nil
    est.last_law_t = nil
    for _, ring in pairs(est.rings) do
        est_ring_reset(ring)
    end
    est.v = { n = 0.0, u = 0.0, e = 0.0 }
    est.v_unselected = { n = 0.0, u = 0.0, e = 0.0 }
    est.a = { n = 0.0, u = 0.0, e = 0.0, f = 0.0, r = 0.0 }
    est.euler = { phi_dot = 0.0, theta_dot = 0.0, psi_dot = 0.0 }
    est.ball = 0.0
    est.v_g = 0.0
    est.v_g_f = 0.0
    est.v_g_r = 0.0
    est.lambda = 0.0
end

-- Cheap pre-check, no `LoGet*` reads -- the caller (`run_flight_
-- control`) calls this BEFORE `read_estimator_raw` so an off-due frame
-- (most of them, at ~140 Hz DCS frames against `law_hz`'s 30) never
-- even builds the raw-reading table (perf-plan-review: "gate the
-- read, not only the use").
local function est_due(est, t, profile)
    return est.last_law_t == nil or (t - est.last_law_t) >= (1.0 / profile.law_hz)
end

-- Separate from `core.lua`'s own `aircraft_layer_debug.flag`/`DEBUG`
-- -- the plan names a distinct flag for this per-frame trace
-- (`aircraft_layer_flight_debug.flag` -> `aircraft_layer_flight_
-- trace.log`), checked far more often than the general debug log.
-- Wrapped in a bare `pcall` (not `core.lua`'s own `safe_call` global --
-- this line runs at module-load time, before `safe_call` is guaranteed
-- to exist as a global in every harness that loads this file whole,
-- e.g. the toy-plant suite, which never mocks a single DCS/cross-
-- module global by design) so a test harness with no `lfs` global
-- never crashes at load time -- `lfs` always exists inside a real DCS
-- process. `pcall` only catches an error raised *inside* the function
-- it is given, and `lfs.writedir()` is evaluated as part of building
-- that function's body here, not as a bare top-level expression, so
-- the index-of-nil error (if any) happens inside the pcall, not
-- before it. Checked once at load time, not per-frame, same posture
-- as `DEBUG`.
local flight_trace_ok, flight_trace_check = pcall(function()
    local f = io.open(lfs.writedir() .. "Scripts\\aircraft_layer_flight_debug.flag", "r")
    if f == nil then
        return false
    end
    f:close()
    return true
end)
local FLIGHT_TRACE_ENABLED = flight_trace_ok and flight_trace_check == true

local flight_trace_file = nil

local function flight_trace_log(line)
    if not FLIGHT_TRACE_ENABLED then
        return
    end
    if flight_trace_file == nil then
        local ok, f = pcall(io.open, lfs.writedir() .. "Logs\\aircraft_layer_flight_trace.log", "a")
        if not ok or f == nil then
            return
        end
        flight_trace_file = f
    end
    flight_trace_file:write(line .. "\n")
end

-- Every `LoGet*` read the estimator needs for one step -- called only
-- when `est_due` says a step is actually due, so an off-due frame
-- costs nothing here. `velocity_source` decides whether the vector-
-- velocity getter is read at all; the trace flag (not passed in,
-- `FLIGHT_TRACE_ENABLED` is a module-level local, same as every other
-- trace-gated read in this function) decides whether the *other*
-- source, and the logged-only channels, are read too (perf-plan-
-- review: the unselected source and the logged-only channels must not
-- cost a read forever once LV-0 settles `velocity_source`).
local function read_estimator_raw(t, velocity_source)
    local self_data = safe_call(LoGetSelfData)
    local pos_n, pos_u, pos_e = 0.0, 0.0, 0.0
    local psi_deg = 0.0
    if type(self_data) == "table" then
        if type(self_data.Position) == "table" then
            local p = self_data.Position
            if type(p.x) == "number" then pos_n = p.x end
            if type(p.y) == "number" then pos_u = p.y end
            if type(p.z) == "number" then pos_e = p.z end
        end
        if type(self_data.Heading) == "number" then
            psi_deg = law_wrap360(math.deg(self_data.Heading))
        end
    end
    local pitch_rad, bank_rad = safe_call(LoGetADIPitchBankYaw)
    local theta_deg = (type(pitch_rad) == "number") and math.deg(pitch_rad) or 0.0
    local phi_deg = (type(bank_rad) == "number") and math.deg(bank_rad) or 0.0
    local ang = safe_call(LoGetAngularVelocity)
    local p_deg_s, q_deg_s, r_deg_s = 0.0, 0.0, 0.0
    if type(ang) == "table" then
        if type(ang.x) == "number" then p_deg_s = math.deg(ang.x) end
        if type(ang.z) == "number" then q_deg_s = math.deg(ang.z) end
        if type(ang.y) == "number" then r_deg_s = -math.deg(ang.y) end
    end
    local ball_raw = safe_call(function() return GetDevice(0):get_argument_value(SLIP_BALL_ARGS.pilot) end)
    if type(ball_raw) ~= "number" or ball_raw ~= ball_raw then
        ball_raw = nil
    end

    local raw = {
        pos_n = pos_n, pos_u = pos_u, pos_e = pos_e,
        psi_deg = psi_deg, phi_deg = phi_deg, theta_deg = theta_deg,
        p_deg_s = p_deg_s, q_deg_s = q_deg_s, r_deg_s = r_deg_s,
        ball_raw = ball_raw,
        vec_n = nil, vec_u = nil, vec_e = nil,
    }

    if velocity_source == "vector" or FLIGHT_TRACE_ENABLED then
        local vv = safe_call(LoGetVectorVelocity)
        if type(vv) == "table" then
            if type(vv.x) == "number" then raw.vec_n = vv.x end
            if type(vv.y) == "number" then raw.vec_u = vv.y end
            if type(vv.z) == "number" then raw.vec_e = vv.z end
        end
    end

    -- Logged only, trace-gated (plan, section A: "Logged only... None
    -- of them closes a loop"). `LoGetAccelerationUnits`'s own return
    -- shape is undocumented (`Sim_ControlAPI.md` lists the name with no
    -- args/results); read defensively the same way `LoGetAngularVelocity`
    -- already is, expecting an `{x,y,z}` table -- a wrong guess here
    -- shows up as an always-nil trace field, never a crash.
    if FLIGHT_TRACE_ENABLED then
        local accel_units = safe_call(LoGetAccelerationUnits)
        if type(accel_units) == "table" then
            raw.accel_units_x = accel_units.x
            raw.accel_units_y = accel_units.y
            raw.accel_units_z = accel_units.z
        end
        raw.aoa = safe_call(LoGetAngleOfAttack)
        raw.aoss = safe_call(LoGetAngleOfSideSlip)
    end

    return raw
end

local function format_trace_line(t, est, raw)
    return string.format(
        "t=%.3f v_n=%.3f v_u=%.3f v_e=%.3f a_f=%.4f a_r=%.4f a_u=%.4f vg=%.3f vgf=%.3f vgr=%.3f "
        .. "phidot=%.3f thetadot=%.3f psidot=%.3f ball=%.4f lambda=%.3f "
        .. "vec_n=%s vec_u=%s vec_e=%s au_x=%s au_y=%s au_z=%s aoa=%s aoss=%s",
        t, est.v.n, est.v.u, est.v.e, est.a.f, est.a.r, est.a.u, est.v_g, est.v_g_f, est.v_g_r,
        est.euler.phi_dot, est.euler.theta_dot, est.euler.psi_dot, est.ball, est.lambda,
        tostring(raw.vec_n), tostring(raw.vec_u), tostring(raw.vec_e),
        tostring(raw.accel_units_x), tostring(raw.accel_units_y), tostring(raw.accel_units_z),
        tostring(raw.aoa), tostring(raw.aoss))
end

-- Runs one estimator step (plan, section A). `raw` is `read_estimator_
-- raw`'s own table -- this function makes no `LoGet*` call of its
-- own. Mutates `est` in place (module header above) and returns
-- whether a step actually ran -- `false` only when the reset/priming
-- branch itself decided there is nothing yet to compute from (never
-- happens in practice since the caller only invokes this when `est_
-- due` already said yes, but kept as an honest return value rather
-- than assuming the caller got it right).
local function est_sample(est, t, raw, profile)
    local dt_since_last = nil
    if est.sample_t ~= nil then
        dt_since_last = t - est.sample_t
    end
    -- Reset/priming (plan, "Reset/priming"): a pause/stall gap, a
    -- clock that went backwards, or the very first sample re-primes
    -- every ring from here rather than differencing across the gap --
    -- "a stall must never produce an acceleration spike."
    if dt_since_last == nil or dt_since_last > DT_CAP or dt_since_last < 0 then
        est_reset(est)
    end
    est.sample_t = t
    est.last_law_t = t

    local selected_n, selected_u, selected_e
    if profile.velocity_source == "vector" and raw.vec_n ~= nil then
        selected_n = est_ring_update_mean(est.rings.vec_n, t, raw.vec_n, profile.w_v_s)
        selected_u = est_ring_update_mean(est.rings.vec_u, t, raw.vec_u, profile.w_v_s)
        selected_e = est_ring_update_mean(est.rings.vec_e, t, raw.vec_e, profile.w_v_s)
        if FLIGHT_TRACE_ENABLED then
            est.v_unselected.n = est_ring_update_slope(est.rings.pos_n, t, raw.pos_n, profile.w_v_s)
            est.v_unselected.u = est_ring_update_slope(est.rings.pos_u, t, raw.pos_u, profile.w_v_s)
            est.v_unselected.e = est_ring_update_slope(est.rings.pos_e, t, raw.pos_e, profile.w_v_s)
        end
    else
        selected_n = est_ring_update_slope(est.rings.pos_n, t, raw.pos_n, profile.w_v_s)
        selected_u = est_ring_update_slope(est.rings.pos_u, t, raw.pos_u, profile.w_v_s)
        selected_e = est_ring_update_slope(est.rings.pos_e, t, raw.pos_e, profile.w_v_s)
        if FLIGHT_TRACE_ENABLED and raw.vec_n ~= nil then
            est.v_unselected.n = est_ring_update_mean(est.rings.vec_n, t, raw.vec_n, profile.w_v_s)
            est.v_unselected.u = est_ring_update_mean(est.rings.vec_u, t, raw.vec_u, profile.w_v_s)
            est.v_unselected.e = est_ring_update_mean(est.rings.vec_e, t, raw.vec_e, profile.w_v_s)
        end
    end
    est.v.n = selected_n
    est.v.u = selected_u
    est.v.e = selected_e

    est.v_g = math.sqrt(est.v.n * est.v.n + est.v.e * est.v.e)
    local psi_rad = math.rad(raw.psi_deg)
    local sin_psi, cos_psi = math.sin(psi_rad), math.cos(psi_rad)
    est.v_g_f = est.v.n * cos_psi + est.v.e * sin_psi
    est.v_g_r = -est.v.n * sin_psi + est.v.e * cos_psi

    -- Acceleration: least-squares slope of `v` over `w_a_s`, then one
    -- more running mean over `w_a2_s` (plan, section A). `a_u` is the
    -- slope of `v_u` directly -- no gravity, no body frame, so it reads
    -- zero in a level turn exactly as the altimeter says.
    local a1_n = est_ring_update_slope(est.rings.acc1_n, t, est.v.n, profile.w_a_s)
    local a1_u = est_ring_update_slope(est.rings.acc1_u, t, est.v.u, profile.w_a_s)
    local a1_e = est_ring_update_slope(est.rings.acc1_e, t, est.v.e, profile.w_a_s)
    est.a.n = est_ring_update_mean(est.rings.acc2_n, t, a1_n, profile.w_a2_s)
    est.a.u = est_ring_update_mean(est.rings.acc2_u, t, a1_u, profile.w_a2_s)
    est.a.e = est_ring_update_mean(est.rings.acc2_e, t, a1_e, profile.w_a2_s)
    est.a.f = est.a.n * cos_psi + est.a.e * sin_psi
    est.a.r = -est.a.n * sin_psi + est.a.e * cos_psi

    local phi_dot, theta_dot, psi_dot = est_euler_rates(
        raw.p_deg_s, raw.q_deg_s, raw.r_deg_s, raw.phi_deg, raw.theta_deg)
    est.euler.phi_dot = phi_dot
    est.euler.theta_dot = theta_dot
    est.euler.psi_dot = psi_dot

    est.ball = est_ring_update_mean(est.rings.ball, t, raw.ball_raw or profile.ball_centre, profile.w_b)

    -- `lambda` -- a trivial first-cut curve (0 at/below 25 km/h, 1
    -- at/above 50 km/h, linear between), reported for the status/card
    -- even though nothing reads it yet (LV-3's own job, which is also
    -- where the blend breakpoints join the profile -- see `flight_
    -- profile.lua`'s header on why they are not there yet). Hard-coded
    -- here rather than in the profile for exactly that reason: this is
    -- a placeholder, not the real schedule.
    local v_g_kmh = est.v_g * 3.6
    if v_g_kmh <= 25.0 then
        est.lambda = 0.0
    elseif v_g_kmh >= 50.0 then
        est.lambda = 1.0
    else
        est.lambda = (v_g_kmh - 25.0) / (50.0 - 25.0)
    end

    return true
end

-- `heading_ref_to_true`/`heading_ref_from_true` -- thin call-throughs to
-- `flight_desired.lua`'s own conversion (that module owns `HEADING_REF`,
-- section 1: "Lua owns the choice"). A missing `flight_desired` (load
-- failure) or a missing/non-finite input is a no-op pass-through --
-- never a reason to crash the law.
local function heading_ref_to_true(ref_heading_deg, measured_true_deg)
    if flight_desired == nil or type(ref_heading_deg) ~= "number" then
        return ref_heading_deg
    end
    local converted = safe_call(
        function() return flight_desired.to_true_heading(ref_heading_deg, measured_true_deg) end)
    if type(converted) ~= "number" then
        return ref_heading_deg
    end
    return converted
end

local function heading_ref_from_true(true_heading_deg, measured_true_deg)
    if flight_desired == nil or type(true_heading_deg) ~= "number" then
        return true_heading_deg
    end
    local converted = safe_call(
        function() return flight_desired.from_true_heading(true_heading_deg, measured_true_deg) end)
    if type(converted) ~= "number" then
        return true_heading_deg
    end
    return converted
end

-- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 1) --
-- "mode 1 applies desired by stamp", replacing `apply_goal_fields`'s own
-- push-at-receipt shape. Called once every active, non-paused,
-- non-just-took frame (`run_active_frame` below): reads `flight_
-- desired.get()` and applies, via `law_apply_goal`, only the parts whose
-- stamp changed since this module last applied them -- "latest wins" by
-- construction, since a newer numbered request always carries a higher
-- stamp than whatever this module last saw. `measured_true_deg` is this
-- frame's own measured heading (`read_measured()`'s `psi_deg`), reused
-- rather than re-read, for the heading-reference conversion.
local function apply_desired_changes_to_law(measured_true_deg)
    if flight_desired == nil or fc_law == nil then
        return
    end
    local desired = safe_call(flight_desired.get)
    if type(desired) ~= "table" then
        return
    end
    local goal = {}
    local changed = false
    if desired.stamp_hdg ~= fc_applied_stamp_hdg then
        fc_applied_stamp_hdg = desired.stamp_hdg
        changed = true
        if desired.hdg_mode == "turn" then
            goal.turn = (desired.turn_dir == nil) and 0 or desired.turn_dir
        elseif desired.hdg_mode == "heading" and type(desired.heading_deg) == "number" then
            goal.heading_deg = heading_ref_to_true(desired.heading_deg, measured_true_deg)
            goal.turn_rate_deg_s = desired.turn_rate_deg_s
        end
    end
    if desired.stamp_alt ~= fc_applied_stamp_alt then
        fc_applied_stamp_alt = desired.stamp_alt
        if type(desired.alt_m) == "number" then
            changed = true
            goal.alt_m = desired.alt_m
            goal.alt_ref = desired.alt_ref
        end
    end
    if desired.stamp_spd ~= fc_applied_stamp_spd then
        fc_applied_stamp_spd = desired.stamp_spd
        if type(desired.ias_kmh) == "number" then
            changed = true
            goal.ias_kmh = desired.ias_kmh
        end
    end
    if changed then
        fc_law = law_apply_goal(fc_law, goal, fc_limits, flight_profile.ACTIVE)
    end
end

-- The take seed (Decision 24/32, Q4, section 2's handover table) --
-- built from `flight_desired.get()`, never from `ai_pilot_wheel.held_
-- targets()` any more (that call site, and the module docstring's own
-- "held_targets()" deletion, were specific to this function). Two
-- shapes:
--
-- - **Unpark** (`fc_take_origin == "unpark"`): carries every part
--   `desired` holds (Decision 32/Q4), converted to true heading, speed/
--   altitude clamped to `fc_limits` (U2, below) since mode 1 cannot fly
--   every value mode 2 can hold -- `desired` itself stays exact, only
--   the seed is clamped. A standing break (`turn_rate_deg_s`/`turn_
--   style ~= "normal"`) is layered on top by the caller via a second
--   `law_apply_goal`, since `law_init_at_take` has no rate-override
--   field of its own.
-- - **Voice take**: the ordinary bank-based/stopping-height/measured
--   defaults (`law_init_at_take`'s own fallback, `seed` fields left
--   `nil`) for every part, **except** one `desired` stamped strictly
--   after this take's own `seq` (`take_seq`) -- a command given in the
--   same breath as "you have controls" (the Stage 3 test: "a set during
--   taking survives the seed").
local function build_take_seed(measured_true_deg)
    if flight_desired == nil then
        return nil
    end
    local desired = safe_call(flight_desired.get)
    if type(desired) ~= "table" then
        return nil
    end
    local seed = {}
    if fc_take_origin == "unpark" then
        if desired.hdg_mode == "heading" and type(desired.heading_deg) == "number" then
            seed.heading_deg = heading_ref_to_true(desired.heading_deg, measured_true_deg)
        end
        if type(desired.alt_m) == "number" then
            -- U2 (`plans/flight-desired-state/plan.md`, section 3,
            -- answered yes): a carried value mode 1 cannot fly exactly
            -- is flown clamped, never fed to the law raw -- `desired`
            -- itself (and `seed`/`desired`'s own return below, which
            -- body-layer's `fd_alt`/`fd_ias` mirror) keeps the exact
            -- commanded value; only the seed fed to `law_init_at_take`
            -- below is clamped, mirroring `belief.flight_control.
            -- clamp_altitude`'s own "agl floor only" rule.
            seed.alt_m = desired.alt_m
            seed.alt_ref = (desired.alt_ref == "baro") and "B" or "R"
            if seed.alt_ref == "R" and seed.alt_m < fc_limits.floor_agl_m then
                seed.alt_m = fc_limits.floor_agl_m
            end
        end
        if type(desired.ias_kmh) == "number" then
            -- Same clamp as above, mirroring `belief.flight_control.
            -- clamp_speed`'s `[min_ias_kmh, max_ias_kmh]` range.
            seed.speed_kmh = desired.ias_kmh
            if seed.speed_kmh < fc_limits.min_ias_kmh then
                seed.speed_kmh = fc_limits.min_ias_kmh
            elseif seed.speed_kmh > fc_limits.max_ias_kmh then
                seed.speed_kmh = fc_limits.max_ias_kmh
            end
        end
        return seed, desired
    end
    local take_seq = fc_take_seq
    if take_seq == nil then
        return seed, desired
    end
    if desired.stamp_hdg ~= nil and desired.stamp_hdg > take_seq
        and desired.hdg_mode == "heading" and type(desired.heading_deg) == "number"
    then
        seed.heading_deg = heading_ref_to_true(desired.heading_deg, measured_true_deg)
    end
    if desired.stamp_alt ~= nil and desired.stamp_alt > take_seq
        and type(desired.alt_m) == "number"
    then
        seed.alt_m = desired.alt_m
        seed.alt_ref = (desired.alt_ref == "baro") and "B" or "R"
    end
    if desired.stamp_spd ~= nil and desired.stamp_spd > take_seq
        and type(desired.ias_kmh) == "number"
    then
        seed.speed_kmh = desired.ias_kmh
    end
    return seed, desired
end

-- `handle_flight_lease_command`'s own bounds check (BL-16 Stage 3: the
-- numbered `flight` op carries no `limits` of its own any more --
-- `limits` travels only on the unnumbered lease now) -- every field
-- present in `data`'s own `limits`-shaped top level is bounds-checked
-- against `FC_LIMIT_BOUNDS`; an out-of-bounds value rejects the WHOLE
-- message (`AC-B14`: never a partial apply), a field the message omits
-- keeps its previous value rather than reverting to the startup
-- default. Returns `true` on success (and has already applied `fc_
-- limits`), `false` on a rejected message (and has applied nothing).
local function apply_limits_bounds_checked(data, log_label)
    local new_limits = {}
    for key, bound in pairs(FC_LIMIT_BOUNDS) do
        local v = extract_json_number_field(data, key)
        if v ~= nil then
            if v < bound.lo or v > bound.hi then
                debug_log("rejecting " .. log_label .. " message: limits." .. key .. " out of bounds")
                return false
            end
            new_limits[key] = v
        end
    end
    for key, v in pairs(new_limits) do
        fc_limits[key] = v
    end
    return true
end

-- Stage 2 (`plans/flight-desired-state/plan.md`, refinement 3) --
-- `{"op":"flight_lease","epoch":E,"limits":{...}}`, unnumbered (no
-- `seq`, never rejected as stale) and sent every poll while body-layer
-- is up -- the one thing it does is refresh `fc_arm_last_t` (the
-- self-arm freshness clock, `run_flight_control`'s own self-arm
-- branches above) and carry the `limits` block, the only wire message
-- on this module that does any more (Stage 3's own numbered `flight`
-- op carries goal/handover fields only, never `limits`). `epoch` is
-- accepted but not yet gated on -- carried only so a future stage can
-- add that check without a wire reshape.
local function handle_flight_lease_command(data, t)
    -- The `AC-B14` lesson: an out-of-bounds `limits` field rejects the
    -- WHOLE message, including the freshness refresh below -- a
    -- malformed lease must not be allowed to keep the self-arm window
    -- open regardless of what it actually asked for.
    if not apply_limits_bounds_checked(data, "flight_lease") then
        return
    end
    fc_arm_last_t = t
end

-- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 5) --
-- called from `flight_desired.handle_flight_command`'s own `kind ==
-- "take"` branch, replacing the old `flight_control` op's `cmd ==
-- "take"`. Returns one of: `"accepted_active"` (already flying mode 1,
-- idempotent -- acked immediately), `"pending"` (off -> taking, not yet
-- resolved -- the caller defers the ack until `flight_desired.tick`
-- sees this module report `active`), or `{refused = <reason>}` (a
-- closed-vocabulary reason, acked immediately, nothing changed).
local function request_take(seq, t)
    if fc_mode == "active" then
        fc_take_seq = seq
        return "accepted_active"
    end
    if fc_mode == "taking" then
        fc_pending_take_seq = seq
        return "pending"
    end
    if fc_mode ~= "off" then
        -- `armed` (flying mode 2) -- "you have controls" said while he
        -- already has them through the overlay does not fit this
        -- table; body-layer's own gate is expected to catch this first
        -- (U9's "Unable, AI overlay." posture), this is the defensive
        -- fallback.
        return { refused = "wrong_mode" }
    end
    -- Stage 2: a voice take re-checks IAS/AGL itself, reusing `check_
    -- unpark_preconditions` (the same function the unpark-take branch
    -- below already calls). A refusal changes nothing (`fc_mode` stays
    -- `off`) -- "an unable never writes the desired state" (Q2). `fc_
    -- refuse_cause` keeps the specific diagnostic (`too_slow`/`on_
    -- ground`) on the status line even though the ack itself always
    -- says the closed-vocabulary `"precondition"` (section 3a).
    local ok, cause = check_unpark_preconditions()
    if not ok then
        fc_release_reason = "refused"
        fc_refuse_cause = cause
        return { refused = "precondition" }
    end
    fc_mode = "taking"
    fc_pending_take_seq = seq
    fc_take_origin = "voice"
    return "pending"
end

-- BL-16 Stage 3, `kind == "release"`'s own call-through, replacing the
-- old `flight_control` op's `cmd == "release"`. Returns `"accepted"` or
-- `{refused = <reason>}`.
local function request_release(seq)
    if fc_mode == "armed" then
        return { refused = "wrong_mode" }
    end
    if fc_mode ~= "active" and fc_mode ~= "taking" then
        return { refused = "not_flying" }
    end
    fc_mode = "off"
    fc_captured = {}
    fc_release_reason = "stop"
    fc_refuse_cause = nil
    fc_pending_take_seq = nil
    fc_take_seq = nil
    -- Same "no stale leak across a session boundary" reasoning as
    -- `on_stop`/the self-arm branches below.
    fc_last_stowed_pilot_capture = nil
    fc_law = nil
    fc_last_command = nil
    fc_applied_stamp_hdg = nil
    fc_applied_stamp_alt = nil
    fc_applied_stamp_spd = nil
    return "accepted"
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
        -- BL-16 Stage 3 -- the seed now comes from `flight_desired`'s
        -- own `desired` table (`build_take_seed` above), never `ai_
        -- pilot_wheel.held_targets()` directly: an unpark carries
        -- `desired` verbatim (Decision 32/Q4), a voice take only the
        -- parts stamped after this take's own seq.
        local seed, desired_at_take = build_take_seed(measured.psi_deg)
        fc_law = law_init_at_take(measured, fc_limits, command, seed, flight_profile.ACTIVE)
        -- A standing break carried into the unpark (`desired.turn_
        -- rate_deg_s`/`turn_style`) has no field of its own on `law_
        -- init_at_take`'s seed -- layered on top via an ordinary `law_
        -- apply_goal` call, the same mechanism a live break command
        -- uses, so the rate override/break-entry-height/pedal-bias
        -- bookkeeping it sets up is identical either way.
        if fc_take_origin == "unpark" and type(desired_at_take) == "table"
            and desired_at_take.turn_rate_deg_s ~= nil
            and desired_at_take.turn_style ~= "normal"
            and seed.heading_deg ~= nil
        then
            fc_law = law_apply_goal(fc_law, {
                heading_deg = seed.heading_deg,
                turn_rate_deg_s = desired_at_take.turn_rate_deg_s,
            }, fc_limits, flight_profile.ACTIVE)
        end
        -- This take's own law state already reflects every part of
        -- `desired` the seed above considered -- record those stamps
        -- now so the very next frame's `apply_desired_changes_to_law`
        -- does not immediately re-apply the thing it was just seeded
        -- with (it would be a no-op in value, but would also clobber
        -- the just-seeded rate-override/break bookkeeping above).
        if type(desired_at_take) == "table" then
            fc_applied_stamp_hdg = desired_at_take.stamp_hdg
            fc_applied_stamp_alt = desired_at_take.stamp_alt
            fc_applied_stamp_spd = desired_at_take.stamp_spd
        end
        write_outputs(law_outputs(fc_law, measured, flight_profile.ACTIVE), nil)
        return
    end
    apply_desired_changes_to_law(measured.psi_deg)
    local prev_turn_mode = fc_law.turn_mode
    local prev_rate_override = fc_law.rate_override_deg_s
    fc_law = law_update(fc_law, dt, measured, fc_limits, flight_profile.ACTIVE)
    -- BL-16 Stage 3 (section 1, "Heading reference" / Co-moving table) --
    -- the roll-out settle (turn -> heading) and the break settle (the
    -- rate override clearing) each write the settled heading back into
    -- `desired`, converted into `HEADING_REF`'s own reference, so a
    -- later unpark (or the status line) reports what the law actually
    -- settled on rather than a stale pre-settle value. Guarded on
    -- `flight_desired` existing, same posture as every other cross-
    -- module call in this file.
    if flight_desired ~= nil then
        if prev_turn_mode and not fc_law.turn_mode then
            safe_call(function()
                flight_desired.write_internal({
                    heading_deg = heading_ref_from_true(fc_law.heading_goal_deg, measured.psi_deg),
                })
            end)
        elseif prev_rate_override ~= nil and fc_law.rate_override_deg_s == nil then
            safe_call(function()
                flight_desired.write_internal({
                    heading_deg = heading_ref_from_true(fc_law.heading_goal_deg, measured.psi_deg),
                    clear_turn_rate = true,
                })
            end)
        end
    end
    write_outputs(law_outputs(fc_law, measured, flight_profile.ACTIVE), dt)
end

-- Every frame, from `LuaExportBeforeNextFrame` (Decision 23).
local function run_flight_control(t)
    local dt = 0.0
    if fc_last_frame_t ~= nil then
        dt = t - fc_last_frame_t
    end
    fc_last_frame_t = t

    -- BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/
    -- plan.md`): the estimator runs here, every frame, in every mode
    -- (so it is warm at a take) -- unlike everything below this point,
    -- which is gated on `fc_mode`. `est_due` is checked BEFORE any of
    -- the estimator's own `LoGet*` reads (`read_estimator_raw`) so an
    -- off-due frame (most of them, at ~140 Hz against `law_hz`'s 30)
    -- costs only the two comparisons inside `est_due` -- the
    -- perf-plan-review's own "gate the read, not only the use."
    local flight_profile_active = flight_profile.ACTIVE
    if est_due(fc_est, t, flight_profile_active) then
        local raw = read_estimator_raw(t, flight_profile_active.velocity_source)
        local ran = est_sample(fc_est, t, raw, flight_profile_active)
        if ran and FLIGHT_TRACE_ENABLED then
            flight_trace_log(format_trace_line(t, fc_est, raw))
        end
    end

    -- `is_parked()` unknown (ai_pilot_wheel failed to load) is treated
    -- the same as "stay off" -- never a licence to assume unparked
    -- (module docstring; this is the one place that default is made).
    local is_parked = nil
    if ai_pilot_wheel ~= nil then
        is_parked = safe_call(ai_pilot_wheel.is_parked)
    end

    -- Required Fix 2 (review-s12.md) -- the off->armed self-arm edge
    -- tracker. A rising edge (not parked last frame, parked this one)
    -- while `fc_mode == "off"` opens the self-arm window; unparking
    -- closes it again. `fc_was_parked` itself is never reset by `on_
    -- stop`/`reset`, so a reset that happens while still parked is not
    -- mistaken for a fresh edge on the very next frame. `is_parked ==
    -- nil` (unknown) is folded into "not parked" here, same as the
    -- module's own "unknown == off" default above.
    local is_parked_now = is_parked == true
    if not is_parked_now then
        fc_off_armable_since_edge = false
    elseif fc_was_parked ~= true and fc_mode == "off" then
        fc_off_armable_since_edge = true
    end
    fc_was_parked = is_parked_now

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

    -- Stage 2 (`plans/flight-desired-state/plan.md`, refinement 3) --
    -- the second self-arm clause: he was `off` (the player flying) and
    -- parks. Every park now gives him the overlay as long as body-
    -- layer's lease is fresh, replacing the old `arm` message's own
    -- `off -> armed` row. Lease NOT fresh (body-layer down, or never
    -- sent one) leaves him `off` -- the player keeps the controls, same
    -- as today when no `arm` had ever arrived. **Edge-triggered, not
    -- level-triggered (review-s12.md Required Fix 2, Q6):**
    -- `fc_off_armable_since_edge` is only true from a genuine park
    -- rising edge onward (set above) and is cleared by `on_stop`/
    -- `reset` -- a reset while still parked leaves `fc_mode == "off"`
    -- and `is_parked == true` indefinitely, which the bare level check
    -- this replaces re-armed the instant a fresh lease next arrived,
    -- with no unpark/re-park having happened.
    if is_parked == true and fc_mode == "off" and fc_off_armable_since_edge then
        local lease_fresh = fc_arm_last_t ~= nil
            and (t - fc_arm_last_t) <= fc_limits.arm_lease_s
        if lease_fresh then
            fc_mode = "armed"
            fc_last_stowed_pilot_capture = nil
            fc_law = nil
            fc_last_command = nil
        end
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
        -- Stage 2 (`plans/flight-desired-state/plan.md`): the `arm`
        -- message (and its own `seq`) is gone -- the lease that self-
        -- arms this session is unnumbered (`handle_flight_lease_
        -- command` below). There is no seq to echo back as `fc_take_
        -- seq`; `decide_flight_control`'s own unpark branch never
        -- compares it against anything (it only *adopts* it when not
        -- nil), so `nil` here is exactly as meaningful as the arm
        -- message's own seq was.
        fc_take_seq = nil
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

    local measured_heading = nil
    local self_data = safe_call(LoGetSelfData)
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        measured_heading = math.deg(self_data.Heading)
    end

    -- Plain telemetry passthrough, same reasoning as `measured_heading`
    -- above: body-layer's own `_axes_current_*` helpers fall back to
    -- this when `flight_authority_state`'s own desired-state mirror
    -- (`fd_alt`/`fd_ias`) has nothing yet -- there is no AI pilot here
    -- reporting its own held value the way mode 2's overlay readback
    -- does.
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

    -- Slip-ball calibration readout (sortie 2026-11-20, `aircraft-layer/
    -- research/2026-11-20-slip-ball-recon.md`) -- read every status push,
    -- in every `fc_mode`, so a pilot-flown calibration flight (Petrovich
    -- never holding the controls) can still read these. Read-only: not
    -- consulted by `law_*` at all yet (sign/scale unmeasured).
    local slip_ball_pilot_raw = safe_call(
        function() return GetDevice(0):get_argument_value(SLIP_BALL_ARGS.pilot) end)
    local slip_ball_operator_raw = safe_call(
        function() return GetDevice(0):get_argument_value(SLIP_BALL_ARGS.operator) end)
    -- Cross-check only (finding (a)'s own unresolved-nil-return risk) --
    -- `LoGetSlipBallPosition` may not exist/return nil on this module;
    -- `safe_call` reports that the same way it reports any other failed
    -- read, as `nil`, which `fmt_num_or_null` already turns into `null`.
    local slip_ball_lo_api = safe_call(LoGetSlipBallPosition)

    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"fc_mode":"' .. fc_mode .. '"'
        -- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`) --
        -- `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq`/`fc_goal_*` are
        -- gone from this line. The ack a take/release/set needs now
        -- rides `flight_desired`'s own `fd_acks` (one numbered channel,
        -- section 5); the commanded heading/altitude/speed Petrovich is
        -- holding is `flight_desired`'s own `fd_*` desired-state fields
        -- (section 1), not a second copy here.
        .. ',"fc_take_origin":' .. text_or_null(fc_take_origin)
        .. ',"fc_takeover_mode":' .. text_or_null(fc_takeover_mode)
        .. ',"fc_measured_heading":' .. fmt_num_or_null(measured_heading)
        .. ',"fc_measured_altitude":' .. fmt_num_or_null(measured_altitude)
        .. ',"fc_measured_speed":' .. fmt_num_or_null(measured_speed)
        .. ',"fc_in_band_heading":' .. bool_or_null(fc_law and fc_law.in_band_heading)
        .. ',"fc_in_band_altitude":' .. bool_or_null(fc_law and fc_law.in_band_altitude)
        .. ',"fc_in_band_speed":' .. bool_or_null(fc_law and fc_law.in_band_speed)
        .. ',"fc_agl_source":' .. text_or_null(agl_source)
        .. ',"fc_release_reason":' .. text_or_null(fc_release_reason)
        .. ',"fc_refuse_cause":' .. text_or_null(fc_refuse_cause)
        .. ',"fc_reset_epoch":' .. fmt_int_or_null(fc_reset_epoch)
        .. ',"fc_limit_hit":false'
        .. ',"fc_axes_pitch":' .. tostring(FC_AXES_ENABLED.pitch)
        .. ',"fc_axes_roll":' .. tostring(FC_AXES_ENABLED.roll)
        .. ',"fc_axes_pedal":' .. tostring(FC_AXES_ENABLED.pedals)
        .. ',"fc_axes_collective":' .. tostring(FC_AXES_ENABLED.collective)
        .. ',"fc_slip_ball_pilot_raw":' .. fmt_num_or_null(slip_ball_pilot_raw)
        .. ',"fc_slip_ball_operator_raw":' .. fmt_num_or_null(slip_ball_operator_raw)
        .. ',"fc_slip_ball_lo_api":' .. fmt_num_or_null(slip_ball_lo_api)
        -- BL-16 lift-vector law, LV-0 (`plans/flight-lift-vector/
        -- plan.md`, Implementation Plan item 1) -- the estimator's own
        -- shadow fields, in every `fc_mode` (the estimator runs
        -- unconditionally, same reasoning as the slip-ball readout
        -- above). Never `null` in practice -- `fc_est`'s fields start
        -- at `0.0` and only ever get overwritten with a finite number
        -- (`fmt_num_or_null` only matters here for a stray NaN).
        .. ',"fc_est_a_f":' .. fmt_num_or_null(fc_est.a.f)
        .. ',"fc_est_a_r":' .. fmt_num_or_null(fc_est.a.r)
        .. ',"fc_est_a_u":' .. fmt_num_or_null(fc_est.a.u)
        .. ',"fc_est_v_g":' .. fmt_num_or_null(fc_est.v_g)
        .. ',"fc_est_v_g_f":' .. fmt_num_or_null(fc_est.v_g_f)
        .. ',"fc_est_phi_dot":' .. fmt_num_or_null(fc_est.euler.phi_dot)
        .. ',"fc_est_theta_dot":' .. fmt_num_or_null(fc_est.euler.theta_dot)
        .. ',"fc_est_psi_dot":' .. fmt_num_or_null(fc_est.euler.psi_dot)
        .. ',"fc_est_ball":' .. fmt_num_or_null(fc_est.ball)
        .. ',"fc_est_lambda":' .. fmt_num_or_null(fc_est.lambda) .. '}\n')
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
    fc_arm_last_t = nil
    -- Required Fix 2 (review-s12.md, Q6) -- the self-arm edge window
    -- itself, not `fc_was_parked` (the raw physical state, which this
    -- reset must NOT touch -- see its own declaration comment above).
    fc_off_armable_since_edge = false
    fc_release_reason = nil
    fc_refuse_cause = nil
    fc_takeover_mode = nil
    fc_last_frame_t = nil
    fc_env_low_ias_since_t = nil
    fc_last_stowed_pilot_capture = nil
    fc_last_steady_values = nil
    fc_law = nil
    fc_last_command = nil
    fc_applied_stamp_hdg = nil
    fc_applied_stamp_alt = nil
    fc_applied_stamp_spd = nil
    -- BL-16 lift-vector law, LV-0 (Co-moving Fields: "estimator ring
    -- buffers and running averages... dt > DT_CAP, mission stop,
    -- reset(epoch), first frame") -- the estimator lives outside `fc_
    -- law` and is never reset by an ordinary mode change (it runs in
    -- every mode), but a mission stop/restart is a genuine discontinuity
    -- the same way a model-time gap inside `est_sample` is.
    est_reset(fc_est)
end

-- Body-layer process-start reset (BL-16 sortie 2026-11-20, `docs/
-- acceptance/2026-11-20-sortie-feedback.md` -- user: "if body layer
-- resets, it could send a reset signal ... then body and collector
-- would match", and on the stick: "yes let go. A service reset is
-- error situation"). Reuses `on_stop` above. **BL-16 Stage 3**: the
-- staleness floor this used to reconcile (`fc_last_cmd_seq`) is gone
-- from this module -- it is `flight_desired`'s own `fd_epoch`/`fd_
-- last_seq` now (one channel, one floor, reset by `commands.lua`'s
-- `handle_reset_command` calling `flight_desired.reset` directly), so
-- this function only clears its own diagnostic echo. Idempotent and
-- safely re-sendable, same posture as every other `reset(epoch)`.
local function reset(epoch)
    on_stop()
    fc_reset_epoch = epoch
end

M.request_take = request_take
M.request_release = request_release
M.handle_flight_lease_command = handle_flight_lease_command
M.run_flight_control = run_flight_control
M.push_flight_control_state = push_flight_control_state
M.on_stop = on_stop
M.reset = reset

-- `plans/flight-desired-state/plan.md`, section 2 -- the one read-only
-- getter `flight_desired.lua` needs to derive `fd_mode`/`fd_mode_cause`
-- without this module's own locals (`dofile`-loaded chunks share no
-- locals, only `_G`/`M`). Same "read-only mirror" posture as `ai_pilot_
-- wheel.lua`'s own `is_parked`/`player_seat`/`held_targets` getters.
M.mode_info = function()
    return {
        mode = fc_mode,
        release_reason = fc_release_reason,
        refuse_cause = fc_refuse_cause,
    }
end

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

-- BL-16 lift-vector law, LV-0 -- the estimator's own ring-buffer math
-- and Euler-rate transform, exported for a dedicated real-Lua suite
-- (`tests/test_flight_control_estimator.py`) to drive directly, no DCS
-- mock needed (none of these read a `LoGet*` global).
M.est_ring_new = est_ring_new
M.est_ring_push = est_ring_push
M.est_ring_slope = est_ring_slope
M.est_ring_mean = est_ring_mean
M.est_euler_rates = est_euler_rates
M.est_reset = est_reset
M.est_sample = est_sample

return M
