--[[
Petrobrain / sight -- the whole 9K113 sight/servo subsystem: per-frame
DCS-slave servo, the ASP-17 field clip (v3), and the slew-trace debug
log. `AC-B12` (`plans/ac-b12-export-modules/plan.md`): one of the
`dofile`-loaded module chunks `Export.lua` (the loader) composes.
Depends only on `core` (loaded first), read as bare globals (`safe_call`,
`debug_log`, `fmt_num_or_null`). **The largest module by a wide margin**
-- see the plan's own Risks section on the 60-upvalue ceiling, unaffected
by this split (it is per-closure, not per-chunk).
--]]

local M = {}

-- The 9K113's OBSERV switch, arg 886. Still read directly here (not only
-- via the generic watched-args mechanism in `effectors.lua`) because
-- `push_slew_trace` and `run_sight_servo` both need it every frame,
-- faster than the 1 Hz poll the watched-args mechanism serves
-- (`plans/effector-sequences/plan.md` Stage 4, S4.1's per-arg audit).
local ARG_OBSERVE = 886

-- The sight head's own actual-position readback -- args 874 (azimuth) and
-- 876 (elevation), BL-B66 Stage 4b (`plans/9k113-effectors/plan.md`). Not a
-- switch: these are the AI/player slew axes' position feedback, read here
-- for the slew-trace log. Azimuth is calibrated (`arg_874 = (deg/60) *
-- 0.44`, confirmed live on the readback while the *player* axis drove the
-- head -- `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-
-- probe-findings.md` finding 2); elevation's degrees-per-unit is still
-- unmeasured, which is why both are sent raw and the degree conversion
-- (for azimuth only) happens on the body-layer side, never here.
local ARG_SIGHT_AZ = 874
local ARG_SIGHT_ELEV = 876

-- The Л5 gyro-alignment lamp, arg 898 -- `BL-B80` v2 reads this directly
-- (not only via watch_args) because `run_sight_servo` needs it every
-- frame for `sight_mode`'s `caged` -> `free` transition, the same
-- per-frame-reader reasoning as `ARG_OBSERVE` above. 960 (guidance-unit
-- READY) and 962 (launch permission), by contrast, have no per-frame
-- reader in this file -- Stage 4 reads them generically, by number,
-- through `polled.toml`/`watch_args` on the body-layer side.
local ARG_ALIGN_LAMP = 898

-- The 9K113's AI-axis pointing channel (`plans/9k113-sight-pointing/
-- plan.md`, BL-B80 v2) -- device 7 (I9K113), `SetCommand(3061, v)`
-- azimuth / `SetCommand(3060, v)` elevation, raw command units. Settled
-- live (2026-10-21/22 probes): a rate command intermittently obeyed,
-- obeyed reliably only with a per-frame value change always present
-- (dither or flicker, run 11) -- `run_sight_servo` below is this file's
-- per-frame DCS-slave servo.
local DEV_I9K113 = 7
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

-- Per-frame slew telemetry log, BL-B66 Stage 4b (`plans/9k113-effectors/
-- plan.md`) -- "Put logging in so that the slew loop can be adjusted based
-- on data from logs" (user direction, 2026-10-21). Its own flag, separate
-- from `core`'s `DEBUG`: that one's per-frame cost is already paid only on
-- a handful of one-shot dumps and a few throttled sends, while this writes
-- one line **every frame** while OBSERV is on -- a different cost profile
-- that should not be forced on whenever someone wants the ordinary debug
-- log, and should not silently ride along with it either. Touch
-- `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` to enable;
-- output goes to `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log`.
-- Checked once at load time, same as `core`'s `DEBUG`.
local SLEW_DEBUG = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\aircraft_layer_slew_debug.flag", "r")
    if ok and f ~= nil then
        SLEW_DEBUG = true
        f:close()
    end
end

-- Hands-off switch for manual 9K113 calibration: "I can point the 9K113 by
-- hand - Petrovich *must not* write axis values then" (user direction,
-- 2026-10-30; see `plans/9k113-hands-off-switch/implementation.md`). The
-- pilot hand-slews the sight onto ground targets at known depression
-- angles to calibrate `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` (declared
-- below), which this switch exists to protect: `run_sight_servo`'s
-- per-frame write would otherwise fight the hand input. Touch
-- `Saved Games\DCS\Scripts\aircraft_layer_sight_hands_off.flag` to enable.
-- Checked once at load time, same as `SLEW_DEBUG` above -- there is no
-- mid-sortie toggle.
local SIGHT_HANDS_OFF = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\aircraft_layer_sight_hands_off.flag", "r")
    if ok and f ~= nil then
        SIGHT_HANDS_OFF = true
        f:close()
    end
end
if SIGHT_HANDS_OFF then
    debug_log("9K113 hands-off switch is ACTIVE -- run_sight_servo will not write the AI axis")
end

local slew_log_file = nil
local slew_log_buffer = {}

-- Lines are buffered and flushed together rather than one `write`+`flush`
-- per frame -- at DCS's frame rate that is one disk flush every ~8-16ms for
-- the whole time OBSERV is on, which is the "tiny per-frame cost" this
-- entry's own plan asks for. Flushed at least this often so a crash mid-
-- sortie loses at most this many lines, same tradeoff `detection_trace_
-- writer.DEFAULT_FLUSH_EVERY_N_POLLS` makes on the body-layer side.
local SLEW_LOG_FLUSH_EVERY_N_LINES = 25

local function slew_log_flush()
    if #slew_log_buffer == 0 then
        return
    end
    if slew_log_file == nil then
        local ok, f = pcall(io.open, lfs.writedir() .. "Logs\\aircraft_layer_slew_trace.log", "a")
        if not ok or f == nil then
            slew_log_buffer = {} -- can't open the file; drop rather than grow unbounded
            return
        end
        slew_log_file = f
    end
    slew_log_file:write(table.concat(slew_log_buffer))
    slew_log_file:flush()
    slew_log_buffer = {}
end

-- How many seconds of logging to keep *after* OBSERV goes off -- long
-- enough to catch the tail of a slew that was still in progress at the
-- moment OBSERV was switched off, short enough that an idle sortie
-- (OBSERV never touched) never fills the file. Not a tuning constant
-- (root CLAUDE.md's "Behaviour-affecting constants are tunable"): it
-- changes what gets logged, never what Petrovich does.
local SLEW_TRACE_TAIL_S = 5.0
local slew_trace_observ_off_since = nil

-- Writes the AI-axis command every frame -- the proven mechanism from
-- the pointing/dither probes, operating directly on raw command units
-- (`SetCommand` takes `deg/60`-style az, a piecewise-scaled el). This is
-- the only place in this module that calls `SetCommand` on `DEV_I9K113`'s
-- AI axis, so the `SIGHT_HANDS_OFF` guard lives here rather than at either
-- of `run_sight_servo`'s two call sites (the per-frame correction and the
-- OBSERV falling-edge zero write) -- a future third call site is blocked
-- by construction instead of by remembering to repeat the check.
local function sight_point_quiet(az_cmd, elev_cmd)
    if SIGHT_HANDS_OFF then
        return
    end
    local dev = safe_call(function() return GetDevice(DEV_I9K113) end)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, CMD_AI_AZ, az_cmd)
    pcall(dev.SetCommand, dev, CMD_AI_ELEV, elev_cmd)
end

-- Moves `current` toward `target` by at most `rate_per_s * dt`, landing
-- exactly on `target` rather than overshooting once within one step of
-- it. Shared by both axes and both the setpoint's own rate limit and
-- (indirectly, via `belief.sight_head._step_toward`) the body-layer
-- head's identical rate limit -- `test_sight_servo_lua.py` pins the two
-- implementations against each other.
local function sight_rate_limit_step(current, target, rate_per_s, dt)
    local delta = target - current
    local max_step = rate_per_s * dt
    if delta > max_step then
        return current + max_step
    elseif delta < -max_step then
        return current - max_step
    end
    return target
end

-- World-true `(az, el)` -> body-relative `(az, el)` at the given attitude
-- -- the Lua twin of `perception.geometry.world_direction_from_body`'s
-- inverse (i.e. of `body_relative_direction` itself), reused by `belief.
-- sight_head._world_to_body` on the Python side. Pure math, no DCS calls
-- -- `test_sight_servo_lua.py` runs this under `luajit` against Python
-- reference vectors.
local function sight_world_to_body(world_az_deg, world_el_deg, heading_deg, pitch_deg, bank_deg)
    local az_rad = math.rad(world_az_deg)
    local el_rad = math.rad(world_el_deg)
    local north = math.cos(el_rad) * math.cos(az_rad)
    local east = math.cos(el_rad) * math.sin(az_rad)
    local up = math.sin(el_rad)

    local heading_rad = math.rad(heading_deg)
    local forward0 = north * math.cos(heading_rad) + east * math.sin(heading_rad)
    local right0 = -north * math.sin(heading_rad) + east * math.cos(heading_rad)
    local up0 = up

    local pitch_rad = math.rad(pitch_deg)
    local forward1 = forward0 * math.cos(pitch_rad) + up0 * math.sin(pitch_rad)
    local up1 = -forward0 * math.sin(pitch_rad) + up0 * math.cos(pitch_rad)
    local right1 = right0

    local bank_rad = math.rad(bank_deg)
    local right2 = right1 * math.cos(bank_rad) - up1 * math.sin(bank_rad)
    local up2 = right1 * math.sin(bank_rad) + up1 * math.cos(bank_rad)

    local body_az_deg = math.deg(math.atan2(right2, forward1))
    local body_el_deg = math.deg(math.atan2(up2, math.sqrt(forward1 * forward1 + right2 * right2)))
    return body_az_deg, body_el_deg
end

-- Raw mark arg -> body-relative degrees: `(raw - boresight) *
-- deg_per_unit`. Pure affine, calibrated by Flight A's probe (Stage 0) --
-- the defaults here are placeholders pending that flight (plan's
-- "Calibration" section), grouped with the rest of this module's own
-- hand-tuned constants below, not independently sourced.
local function sight_mark_to_body_deg(raw_mark, boresight_mark, deg_per_unit)
    return (raw_mark - boresight_mark) * deg_per_unit
end

-- `BL-B80` v2's per-frame servo constants (`plans/9k113-sight-
-- pointing/plan.md`) -- grouped in one block so a flight-to-flight
-- retune is one diff, per the plan's own Affected Files note. No tuning
-- mechanism outside body-layer (Lua-side constants cannot use `tuning.
-- py`); keep in sync by hand across this file boundary.
--
-- `SERVO_WOBBLE` selects the per-frame value-change mechanism DCS needs
-- to keep obeying the axis (probe run 11, folded in before Stage 4 was
-- built): "dither" (0.6 deg / 8 Hz, confirmed to hold 0.006-0.013 deg
-- RMS, the ATGM-budget-meeting default) or "flicker" (an alternating
-- +-epsilon well below the 0.003-unit deadzone, kept as the alternative
-- -- run 11 measured it leaving 0.04-0.06 deg, outside budget, so it is
-- not the default).
local SERVO_WOBBLE = "dither"
local DITHER_AZ_DEG = 0.6
local DITHER_HZ = 8.0
-- Elevation's dither component, 90 deg out of phase (cosine) -- run 10's
-- own measured ratio (0.03 el-command amplitude at 1.5 deg az amplitude,
-- `Export.probe-9k113-dither.lua`'s `DITHER_EL`/`DITHER_AZ_DEG`).
local DITHER_EL_DEG = DITHER_AZ_DEG * (0.03 / 1.5)
-- Flicker's own amplitude -- run 11: any size in 1e-5..1e-3 kept the axis
-- obeyed; this sits mid-range, still far below the 0.003-unit deadzone.
local FLICKER_EPS = 1.0e-4

-- Proportional gain and feed-forward, Stage 4 (Kp only, I = 0 -- Stage 5
-- adds the integral term only if Flight B misses +-0.02 deg). `FF_GAIN`
-- mirrors the probe's own `TRACK_GAIN` (3 command-deg per deg/s of rate,
-- i.e. a 3-deg command sustains roughly 1 deg/s of obeyed slew).
local KP = 3.0
local FF_GAIN = 3.0
-- `homing`'s capped push toward `field_target` (v3) -- inherits the old
-- open-loop branch's `OPEN_LOOP_SAT_DEG = 6.0` value as a starting point,
-- not re-derived, since its role (bound a transient correction, never
-- sustain one) is unchanged even though open loop itself is gone (v3's
-- "Merged mode" section, `plans/9k113-sight-pointing/plan.md`).
local HOMING_SAT_DEG = 6.0

-- A `sight_target` command older than this is ignored (mode `hold`
-- instead) -- the plan's own stale-target timeout. Extrapolation beyond
-- the goal's own `t_sim` is capped the same way, so a long-dead goal
-- does not run away.
local STALE_TARGET_TIMEOUT_S = 3.0
local EXTRAPOLATION_CAP_S = 2.0

-- Field-of-regard gimbal limits -- same sourced figures as `perception.
-- optics.SIGHT_WIDE_OPTIC` (one source of truth is the Python side; kept
-- in sync by hand here, same cross-file convention as every other
-- Lua-side mirror in this project).
local GIMBAL_AZ_HALF_DEG = 60.0
local GIMBAL_EL_UP_DEG = 20.0
local GIMBAL_EL_DOWN_DEG = -15.0

-- The ASP-17's own readable field (v3) -- what the real sight is actually
-- closed-loop on, not the gimbal limits above (the sortie bug: the old
-- gate checked the setpoint against the gimbal limits while the mark
-- physically cannot exceed this much smaller window). Azimuth is
-- measured (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` line
-- 423) and symmetric. Elevation is measured in flight 2026-10-28
-- (`docs/acceptance/2026-10-28-sortie-feedback.md` §2-4) and is strongly
-- asymmetric about boresight -- not a half-angle at all, so the raw clip
-- readings themselves are the measured facts (top saturates at 1.0;
-- bottom readback limit is 0.278, the clean airborne run -- the ground
-- run's 0.407 was a non-command disturbance partway down and is not
-- used) and the degree bounds (`ASP17_FIELD_EL_UP_DEG`/`ASP17_FIELD_EL_
-- DOWN_DEG`, declared below once `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_
-- EL` exist) are derived from them, so they move together with that
-- calibration rather than drifting out of sync with it.
-- `ASP17_FIELD_MARGIN_DEG` is how far inside this field the mark must sit
-- to be trusted (not the gimbal margin the old `FIELD_MARGIN_DEG` was
-- sized for -- the two are different scales and must not be merged under
-- one name), applied the same way on every bound above, both elevation
-- sides included.
local ASP17_FIELD_AZ_HALF_DEG = 4.3
local ASP17_MARK_EL_RAW_CLIP_UP = 1.0
local ASP17_MARK_EL_RAW_CLIP_DOWN = 0.278
local ASP17_FIELD_MARGIN_DEG = 0.5

-- Stall detection (run 8's definition): commanding at least this many
-- degrees of correction for at least this long with the mark moving less
-- than this counts as stalled. Report-only -- no recovery trick has
-- evidence; dither is the remedy and is already always on.
local STALL_CMD_DEG = 1.5
local STALL_WINDOW_S = 0.4
local STALL_MOVE_EPS = 0.003

-- Mark (ASP-17 reticle) calibration. Azimuth: from the dither probe's own
-- measured `MARK_PER_DEG`/boresight. Elevation: fitted 2026-10-30 against
-- DCS AI Petrovich tracking a BMD-1 with the hands-off flag on, truth from
-- the detection trace rotated into the airframe -- 107 samples, -1.7 to
-- -14.5 deg, rms 0.006 deg, linear across the span
-- (`docs/acceptance/2026-10-30-sortie-feedback.md` §3). Replaces the
-- 2026-10-28 gimbal-derived 0.83 / 1/0.037, which put the mark ~25% short
-- in elevation (ATGM cross visibly below the target).
local MARK_BORESIGHT_AZ = 0.500
local MARK_DEG_PER_UNIT_AZ = 1.0 / 0.039
local MARK_BORESIGHT_EL = 0.8333
local MARK_DEG_PER_UNIT_EL = 1.0 / 0.0277

-- Elevation field bounds derived from the raw clip readings
-- (`ASP17_MARK_EL_RAW_CLIP_UP`/`ASP17_MARK_EL_RAW_CLIP_DOWN` above) and
-- this calibration -- declared here rather than beside the other
-- `ASP17_FIELD_*` constants because Lua has no hoisting and this
-- computation needs `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` already
-- defined. With the current calibration this is ~= +6.0/-20.1 deg; the
-- down side lies past the -15 deg gimbal, so only the up side ever clips.
local ASP17_FIELD_EL_UP_DEG = (ASP17_MARK_EL_RAW_CLIP_UP - MARK_BORESIGHT_EL) * MARK_DEG_PER_UNIT_EL
local ASP17_FIELD_EL_DOWN_DEG = (MARK_BORESIGHT_EL - ASP17_MARK_EL_RAW_CLIP_DOWN) * MARK_DEG_PER_UNIT_EL

-- `sight_target`'s own wire bounds (security plan review, required
-- change): a non-finite or out-of-range `t_sim` rejects the whole
-- command, exactly like a non-finite az/el/rate -- `t_sim` feeds
-- `clamp(t - t_sim, 0, cap)` directly in `run_sight_servo`, so an
-- unbounded value there is as dangerous as an unbounded angle.
local SIGHT_GOAL_AZ_BOUND = 360.0
local SIGHT_GOAL_EL_BOUND = 90.0
local SIGHT_GOAL_RATE_BOUND = 30.0

-- The servo's own per-frame state -- `sight_goal_*` is external (set by
-- the `sight_target` command, persists across frames until replaced or
-- OBSERV reads off); the rest is internal, advanced by `run_sight_servo`
-- every frame. All reset to `nil`/`false`/`0` on the OBSERV falling edge
-- and in `M.on_stop` (same "a stale target must never survive" reasoning
-- the v1 state carried).
local sight_goal_az_deg = nil
local sight_goal_el_deg = nil
local sight_goal_rate_az_deg_s = 0.0
local sight_goal_rate_el_deg_s = 0.0
local sight_goal_t_sim = nil
local sight_setpoint_body_az_deg = nil
local sight_setpoint_body_el_deg = nil
local sight_mode = "off"
local sight_mark_body_az_deg = nil
local sight_mark_body_el_deg = nil
local sight_error_az_deg = nil
local sight_error_el_deg = nil
-- v3: the setpoint radially projected onto the inset ASP-17 field --
-- what the closed loop actually tracks, always (`sight_clip_to_field_
-- body_deg`, recomputed fresh every frame). `sight_mark_clipped` is the
-- mark-validity signal (`sight_mark_is_clipped`) driving the `closed`/
-- `homing` split. `sight_prev_field_target_body_*_deg` holds only the
-- previous frame's `field_target` for the feed-forward finite difference
-- (part 3 of the fix) -- never read as a position itself.
local sight_field_target_body_az_deg = nil
local sight_field_target_body_el_deg = nil
local sight_mark_clipped = false
local sight_prev_field_target_body_az_deg = nil
local sight_prev_field_target_body_el_deg = nil
local sight_last_frame_t = nil
local sight_last_write_az_cmd = 0.0
local sight_last_write_el_cmd = 0.0
local sight_flicker_parity = false
local sight_stall_window_start_t = nil
local sight_stall_window_start_mark_az = nil
local sight_stalled = false
local sight_stall_count = 0
-- `docs/acceptance/2026-10-24-sortie-feedback.md` F1: whether OBSERV was
-- on as of the *previous* frame this function ran -- the only state
-- `sight_observ_transition` needs to tell an on->off edge (write the
-- axes to zero once) from every other off frame (write nothing) or an
-- off frame that was never preceded by an on one (also write nothing;
-- there is no stale command to clear). Reset in `M.on_stop`, same
-- "a stale target must never survive" reasoning as the rest of this
-- block.
local sight_was_observ_on = false

-- Stores the persistent world goal from a `sight_target` command --
-- external state, held across frames, consumed every frame by
-- `run_sight_servo` below. Rejects the *whole* command (no field
-- written) on any malformed, non-finite, or out-of-range field --
-- `az_deg`/`el_deg`/`rate_az_deg_s`/`rate_el_deg_s`/`t_sim` alike, per the
-- security plan review's required change. Extraction moved inside the
-- handler itself (`AC-B12`, normalizing to the `(data, t)` shape every
-- `commands.lua` handler uses) -- same validation/semantics as before,
-- only where the extraction happens moved.
local function handle_sight_target_command(data, t)
    local goal_az_deg = extract_json_number_field(data, "goal_az_deg")
    local goal_el_deg = extract_json_number_field(data, "goal_el_deg")
    local rate_az_deg_s = extract_json_number_field(data, "goal_rate_az_deg_s")
    local rate_el_deg_s = extract_json_number_field(data, "goal_rate_el_deg_s")
    local t_sim = extract_json_number_field(data, "t_sim")
    if goal_az_deg == nil or goal_el_deg == nil or rate_az_deg_s == nil
        or rate_el_deg_s == nil or t_sim == nil then
        debug_log("ignoring malformed sight_target command (missing field)")
        return
    end
    if math.abs(goal_az_deg) > SIGHT_GOAL_AZ_BOUND
        or math.abs(goal_el_deg) > SIGHT_GOAL_EL_BOUND
        or math.abs(rate_az_deg_s) > SIGHT_GOAL_RATE_BOUND
        or math.abs(rate_el_deg_s) > SIGHT_GOAL_RATE_BOUND
        or t_sim < 0 then
        debug_log("ignoring out-of-range sight_target command: goal_az_deg="
            .. tostring(goal_az_deg) .. " goal_el_deg=" .. tostring(goal_el_deg)
            .. " rate_az_deg_s=" .. tostring(rate_az_deg_s)
            .. " rate_el_deg_s=" .. tostring(rate_el_deg_s)
            .. " t_sim=" .. tostring(t_sim))
        return
    end
    sight_goal_az_deg = goal_az_deg
    sight_goal_el_deg = goal_el_deg
    sight_goal_rate_az_deg_s = rate_az_deg_s
    sight_goal_rate_el_deg_s = rate_el_deg_s
    sight_goal_t_sim = t_sim
end

-- `docs/acceptance/2026-10-24-sortie-feedback.md` F1: "when observ is
-- turned OFF, ... write 0 to both axis, but only once. Then stop writing
-- the axis values. We should only write axis values when observ is ON."
-- Pure decision, factored out of `run_sight_servo` so it is testable
-- without a DCS environment (`tests/test_sight_servo_lua.py`): given
-- this frame's `observ_on` and whether OBSERV was on as of the previous
-- frame, returns whether this frame is the one-time on->off edge that
-- must write (0, 0), and the `was_on` value to carry into next frame.
local function sight_observ_transition(observ_on, was_on)
    if observ_on then
        return false, true
    end
    return was_on, false
end

-- v3 (`plans/9k113-sight-pointing/plan.md`, "v3 -- the real sight never
-- leaves the ASP-17 field"): the setpoint radially projected onto the
-- inset ASP-17 field, per axis independently (the mark is two linear
-- gauges, az 565/566 and el 555/556, not a cone, so this is the standard
-- ray-to-box clip, not a circular one). Elevation's box side is
-- asymmetric (measured 2026-10-28) -- `field_el_up_deg` bounds a positive
-- `set_el_deg`, `field_el_down_deg` (also a positive magnitude) bounds a
-- negative one; azimuth stays symmetric, called with the same half-angle
-- for both sides. `scale == 1.0` when the setpoint is already inside;
-- otherwise the largest scale <= 1 that lands it exactly on the nearer
-- edge, whichever axis (and, for elevation, whichever side) hits its own
-- edge first. Pure math -- `test_sight_servo_lua.py` runs this under
-- `luajit` against a Python reference.
local function sight_clip_to_field_body_deg(set_az_deg, set_el_deg,
        field_az_half_deg, field_el_up_deg, field_el_down_deg)
    local scale = 1.0
    if set_az_deg ~= 0.0 then
        scale = math.min(scale, field_az_half_deg / math.abs(set_az_deg))
    end
    if set_el_deg > 0.0 then
        scale = math.min(scale, field_el_up_deg / set_el_deg)
    elseif set_el_deg < 0.0 then
        scale = math.min(scale, field_el_down_deg / -set_el_deg)
    end
    return set_az_deg * scale, set_el_deg * scale, scale < 1.0
end

-- v3: true when the mark's own raw reading is at or beyond its clip edge
-- (within `margin_deg`) -- the root-cause fix. The old `setpoint_inside_
-- field` gate this replaces checked the *setpoint* against the gimbal
-- limits (60 deg), not the mark against the ASP-17's own ~4.3 deg window,
-- so a setpoint anywhere up to ~58 deg off boresight read as "valid" --
-- see v3's "Root cause". `field_up_deg`/`field_down_deg` let the two
-- sides differ (elevation, measured 2026-10-28, is asymmetric about
-- boresight); a symmetric axis (azimuth) is called with the same value
-- for both. Pure math, one axis at a time; the caller ORs both axes
-- together.
local function sight_mark_is_clipped(mark_raw, boresight_mark, field_up_deg, field_down_deg,
        deg_per_unit, margin_deg)
    local body_deg = (mark_raw - boresight_mark) * deg_per_unit
    if body_deg >= 0.0 then
        return body_deg >= (field_up_deg - margin_deg)
    end
    return -body_deg >= (field_down_deg - margin_deg)
end

-- Every frame, flag-gated: sim time, the sight's own actual-position
-- readback (874/876, raw), OBSERV (886), and the last slew command sent on
-- the player axis (3025/3026) -- always `nil` in this entry, since nothing
-- in this codebase writes that axis yet (BL-B80 is the slew loop
-- itself). The field exists now so BL-B80 only has to start assigning it,
-- never add a new log line format. Logged only while OBSERV is on (or
-- within SLEW_TRACE_TAIL_S of it going off) so an idle sortie's log stays
-- empty -- body-layer's own 1 Hz poll cannot see a slew at all, which is
-- the entire reason this runs here, every frame, rather than there.
--
-- `mark_az_raw`/`mark_el_raw` (566/555, raw -- v3) and `mark_clipped`
-- (v3, computed here with `sight_mark_is_clipped` against the current
-- `ASP17_FIELD_AZ_HALF_DEG`/`ASP17_FIELD_EL_UP_DEG`/`ASP17_FIELD_EL_DOWN_
-- DEG`/`ASP17_FIELD_MARGIN_DEG`) is this per-**frame** log, not the 5 Hz
-- `push_sight_servo_state` line, which is what the 2026-10-28 elevation
-- calibration flight (`docs/acceptance/2026-10-28-sortie-feedback.md`)
-- actually read to find 555's clip edges.
local function push_slew_trace(t)
    if not SLEW_DEBUG then
        return
    end
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5
    if observ_on then
        slew_trace_observ_off_since = nil
    elseif slew_trace_observ_off_since == nil then
        slew_trace_observ_off_since = t
    end
    if slew_trace_observ_off_since ~= nil
        and (t - slew_trace_observ_off_since) > SLEW_TRACE_TAIL_S then
        return
    end
    local az = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_AZ)
    end)
    local elev = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_ELEV)
    end)
    local m566 = safe_call(function() return GetDevice(0):get_argument_value(566) end)
    local m555 = safe_call(function() return GetDevice(0):get_argument_value(555) end)
    local mark_clipped = "null"
    if type(m566) == "number" and type(m555) == "number" then
        local clipped =
            sight_mark_is_clipped(m566, MARK_BORESIGHT_AZ, ASP17_FIELD_AZ_HALF_DEG,
                ASP17_FIELD_AZ_HALF_DEG, MARK_DEG_PER_UNIT_AZ, ASP17_FIELD_MARGIN_DEG)
            or sight_mark_is_clipped(m555, MARK_BORESIGHT_EL, ASP17_FIELD_EL_UP_DEG,
                ASP17_FIELD_EL_DOWN_DEG, MARK_DEG_PER_UNIT_EL, ASP17_FIELD_MARGIN_DEG)
        mark_clipped = tostring(clipped)
    end
    slew_log_buffer[#slew_log_buffer + 1] = string.format(
        '{"t":%.3f,"az":%s,"elev":%s,"observe":%s,"slew_cmd_az":null,"slew_cmd_el":null'
        .. ',"mark_az_raw":%s,"mark_el_raw":%s,"mark_clipped":%s}\n',
        t, fmt_num_or_null(az), fmt_num_or_null(elev), fmt_num_or_null(observe),
        fmt_num_or_null(m566), fmt_num_or_null(m555), mark_clipped
    )
    if #slew_log_buffer >= SLEW_LOG_FLUSH_EVERY_N_LINES then
        slew_log_flush()
    end
end

-- Export.lua's per-frame DCS-slave servo (`plans/9k113-sight-pointing/
-- plan.md`'s "Export.lua run_sight_servo(t)" design-detail section,
-- extended by v3's "the real sight never leaves the ASP-17 field") --
-- tracks the world goal body-layer last sent, in airframe axes converted
-- fresh every frame, always closed-loop on the ASP-17 mark toward
-- `field_target` (the setpoint clipped into the field), with the
-- per-frame value-change mechanism always on. Called every frame via
-- `M.sight_servo_tick`, before the loader's own 5 Hz export throttle --
-- same reasoning as every other per-frame function in this module.
--
-- `SIGHT_HANDS_OFF` is deliberately **not** checked inside this function:
-- it already sits at Lua 5.1's 60-upvalue ceiling per closure (confirmed
-- live by `luac5.1 -p` -- adding one more upvalue reference here, even a
-- single `if SIGHT_HANDS_OFF then return end`, pushed it to 61 and failed
-- the syntax check outright). `sight_servo_tick` below is the hands-off
-- gate instead -- the one place besides `sight_point_quiet` itself that
-- reads the flag.
local function run_sight_servo(t)
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5

    -- F1 fix: decide the one-time falling-edge zero write *before* any
    -- of this frame's other state is touched, from the previous frame's
    -- `sight_was_observ_on` -- `dt`/`sight_last_frame_t` below are
    -- unrelated to this and must not be read as a proxy for it (a first
    -- frame has `sight_last_frame_t == nil` regardless of OBSERV state).
    local observ_falling_edge, new_was_observ_on = sight_observ_transition(observ_on, sight_was_observ_on)
    sight_was_observ_on = new_was_observ_on

    local dt = 0.0
    if sight_last_frame_t ~= nil then
        dt = t - sight_last_frame_t
    end
    sight_last_frame_t = t

    if not observ_on then
        sight_goal_az_deg = nil
        sight_goal_el_deg = nil
        sight_goal_rate_az_deg_s = 0.0
        sight_goal_rate_el_deg_s = 0.0
        sight_goal_t_sim = nil
        sight_setpoint_body_az_deg = nil
        sight_setpoint_body_el_deg = nil
        sight_mode = "off"
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
        if observ_falling_edge then
            -- F1: the one-time zero write on the on->off edge -- 0 is
            -- centre for both axes at this function's own convention
            -- (`write_az_cmd`/`write_el_cmd` are both 0 at write_az_deg/
            -- write_el_deg == 0), and matches the probe findings that a
            -- centred/no-command axis reads back 0
            -- (`aircraft-layer/research/2026-10-21-9k113-slew-readback-
            -- probe-findings.md`). No further writes happen on any
            -- later off frame -- `observ_falling_edge` is only ever
            -- true on the one frame the edge occurs.
            sight_point_quiet(0.0, 0.0)
            sight_last_write_az_cmd = 0.0
            sight_last_write_el_cmd = 0.0
        end
        return
    end

    local align = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_ALIGN_LAMP)
    end)
    local align_on = type(align) == "number" and align >= 0.5

    if not align_on then
        sight_mode = "caged"
        sight_setpoint_body_az_deg = 0.0
        sight_setpoint_body_el_deg = 0.0
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
        return -- caged: no writes
    end

    if sight_setpoint_body_az_deg == nil then
        -- Entering `free` this frame (from `caged`/`off`) -- seed at
        -- boresight, same as the body-layer head's own seeding.
        sight_setpoint_body_az_deg = 0.0
        sight_setpoint_body_el_deg = 0.0
    end

    local have_goal = sight_goal_az_deg ~= nil and sight_goal_t_sim ~= nil
    local stale = have_goal and (t - sight_goal_t_sim) > STALE_TARGET_TIMEOUT_S

    local u_az, u_el = 0.0, 0.0

    if not have_goal or stale then
        sight_mode = "hold"
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
    else
        local age = t - sight_goal_t_sim
        if age < 0 then age = 0 end
        if age > EXTRAPOLATION_CAP_S then age = EXTRAPOLATION_CAP_S end
        local goal_world_az = sight_goal_az_deg + sight_goal_rate_az_deg_s * age
        local goal_world_el = sight_goal_el_deg + sight_goal_rate_el_deg_s * age

        local heading_deg, pitch_deg, bank_deg = 0.0, 0.0, 0.0
        local self_data = safe_call(LoGetSelfData)
        if type(self_data) == "table" and type(self_data.Heading) == "number" then
            heading_deg = math.deg(self_data.Heading)
        end
        local pitch_rad, bank_rad = safe_call(LoGetADIPitchBankYaw)
        if type(pitch_rad) == "number" then
            pitch_deg = math.deg(pitch_rad)
        end
        if type(bank_rad) == "number" then
            bank_deg = math.deg(bank_rad)
        end

        local goal_body_az, goal_body_el = sight_world_to_body(
            goal_world_az, goal_world_el, heading_deg, pitch_deg, bank_deg)

        sight_setpoint_body_az_deg = sight_rate_limit_step(
            sight_setpoint_body_az_deg, goal_body_az, GIMBAL_AZ_HALF_DEG / 3.0, dt)
        sight_setpoint_body_el_deg = sight_rate_limit_step(
            sight_setpoint_body_el_deg, goal_body_el, GIMBAL_EL_UP_DEG / 2.0, dt)
        sight_setpoint_body_az_deg = math.max(
            -GIMBAL_AZ_HALF_DEG, math.min(GIMBAL_AZ_HALF_DEG, sight_setpoint_body_az_deg))
        sight_setpoint_body_el_deg = math.max(
            GIMBAL_EL_DOWN_DEG, math.min(GIMBAL_EL_UP_DEG, sight_setpoint_body_el_deg))

        -- v3: `field_target` is what the closed loop actually tracks,
        -- always -- the setpoint itself, radially projected onto the
        -- inset ASP-17 field. Recomputed fresh every frame from this
        -- frame's own setpoint (never held across frames), so the real
        -- sight slides continuously along the field edge as the setpoint
        -- moves (pilot's 2026-10-26 clarification). Clipped to the
        -- *margin-reduced* half-angle, not the raw field half-angle, so a
        -- mark that has fully converged onto `field_target` sits inside
        -- (not exactly on) `sight_mark_is_clipped`'s own clip threshold --
        -- the property test below pins this bound.
        local field_target_az, field_target_el, field_clipped =
            sight_clip_to_field_body_deg(sight_setpoint_body_az_deg, sight_setpoint_body_el_deg,
                ASP17_FIELD_AZ_HALF_DEG - ASP17_FIELD_MARGIN_DEG,
                ASP17_FIELD_EL_UP_DEG - ASP17_FIELD_MARGIN_DEG,
                ASP17_FIELD_EL_DOWN_DEG - ASP17_FIELD_MARGIN_DEG)

        -- Part 3 of the fix: feed-forward on `field_target`'s own
        -- per-frame finite difference while sliding along the edge
        -- (`scale < 1.0`, i.e. `field_clipped`) -- the raw goal rate is
        -- the wrong rate there, since `field_target`'s own rate along the
        -- boundary can differ from it in magnitude or sign. Inside the
        -- field the two move identically, so the raw goal rate is used
        -- unchanged (and reconstructing it from a one-frame-late
        -- difference would be no benefit).
        local ff_az, ff_el = sight_goal_rate_az_deg_s, sight_goal_rate_el_deg_s
        if field_clipped and sight_prev_field_target_body_az_deg ~= nil and dt > 0 then
            ff_az = (field_target_az - sight_prev_field_target_body_az_deg) / dt
            ff_el = (field_target_el - sight_prev_field_target_body_el_deg) / dt
        end

        local m566 = safe_call(function() return GetDevice(0):get_argument_value(566) end)
        local m555 = safe_call(function() return GetDevice(0):get_argument_value(555) end)
        local mark_types_ok = type(m566) == "number" and type(m555) == "number"

        local mark_clipped = false
        if mark_types_ok then
            sight_mark_body_az_deg = sight_mark_to_body_deg(m566, MARK_BORESIGHT_AZ, MARK_DEG_PER_UNIT_AZ)
            sight_mark_body_el_deg = sight_mark_to_body_deg(m555, MARK_BORESIGHT_EL, MARK_DEG_PER_UNIT_EL)
            mark_clipped =
                sight_mark_is_clipped(m566, MARK_BORESIGHT_AZ, ASP17_FIELD_AZ_HALF_DEG,
                    ASP17_FIELD_AZ_HALF_DEG, MARK_DEG_PER_UNIT_AZ, ASP17_FIELD_MARGIN_DEG)
                or sight_mark_is_clipped(m555, MARK_BORESIGHT_EL, ASP17_FIELD_EL_UP_DEG,
                    ASP17_FIELD_EL_DOWN_DEG, MARK_DEG_PER_UNIT_EL, ASP17_FIELD_MARGIN_DEG)
        else
            sight_mark_body_az_deg = nil
            sight_mark_body_el_deg = nil
        end

        local e_az, e_el
        if mark_types_ok and not mark_clipped then
            -- `closed`: field_target is inset and the mark reads valid --
            -- the everyday path. No saturation on `u` beyond the write
            -- clamp below: `field_target` already bounds the achievable
            -- error to the field's own size.
            sight_mode = "closed"
            e_az = field_target_az - sight_mark_body_az_deg
            e_el = field_target_el - sight_mark_body_el_deg
            u_az = KP * e_az + FF_GAIN * ff_az
            u_el = KP * e_el + FF_GAIN * ff_el
        else
            -- `homing`: the mark reading itself is invalid (missing, or
            -- at/near its own clip) despite `field_target` being inset --
            -- a transient case (the first frame or two after `caged ->
            -- free`, or a stale real head left pointing from before this
            -- fix deployed), not the everyday path. A clipped mark is a
            -- known half-plane fact (the real sight is beyond that edge,
            -- in that direction); push toward `field_target`, capped at
            -- `HOMING_SAT_DEG` so a stale reading cannot produce a
            -- runaway command the way the old open-loop branch's
            -- unbounded closed-branch error term could.
            sight_mode = "homing"
            if mark_types_ok then
                e_az = field_target_az - sight_mark_body_az_deg
                e_el = field_target_el - sight_mark_body_el_deg
            else
                e_az = field_target_az
                e_el = field_target_el
            end
            u_az = math.max(-HOMING_SAT_DEG, math.min(HOMING_SAT_DEG, KP * e_az + FF_GAIN * ff_az))
            u_el = math.max(-HOMING_SAT_DEG, math.min(HOMING_SAT_DEG, KP * e_el + FF_GAIN * ff_el))
        end
        sight_error_az_deg = e_az
        sight_error_el_deg = e_el
        sight_field_target_body_az_deg = field_target_az
        sight_field_target_body_el_deg = field_target_el
        sight_mark_clipped = mark_clipped or not mark_types_ok
        sight_prev_field_target_body_az_deg = field_target_az
        sight_prev_field_target_body_el_deg = field_target_el

        -- Stall (run 8's definition, point D): commanding a real
        -- correction for `STALL_WINDOW_S` with the mark not moving --
        -- shared by `closed` and `homing` alike (v3: the old open branch
        -- never fed this at all). Gated on actually having a mark to
        -- measure motion from; a missing mark can't be judged stalled or
        -- not, so neither flag changes in that case.
        if mark_types_ok then
            if math.abs(u_az) >= STALL_CMD_DEG or math.abs(u_el) >= STALL_CMD_DEG then
                if sight_stall_window_start_t == nil then
                    sight_stall_window_start_t = t
                    sight_stall_window_start_mark_az = sight_mark_body_az_deg
                elseif t - sight_stall_window_start_t >= STALL_WINDOW_S then
                    local moved = math.abs(sight_mark_body_az_deg - sight_stall_window_start_mark_az)
                    if moved < STALL_MOVE_EPS then
                        if not sight_stalled then
                            sight_stall_count = sight_stall_count + 1
                        end
                        sight_stalled = true
                    else
                        sight_stalled = false
                    end
                    sight_stall_window_start_t = t
                    sight_stall_window_start_mark_az = sight_mark_body_az_deg
                end
            else
                sight_stall_window_start_t = nil
                sight_stalled = false
            end
        else
            sight_stall_window_start_t = nil
            sight_stalled = false
        end
    end

    -- The per-frame value-change mechanism, always on -- "the written
    -- value differs from last frame's" is the whole guarantee this
    -- needs (step 6). One flicker parity flip, shared by both axes this
    -- frame, so the two never drift out of phase (the known flicker-
    -- probe bug this avoids).
    sight_flicker_parity = not sight_flicker_parity
    local wobble_az, wobble_el
    if SERVO_WOBBLE == "flicker" then
        local sign = 1.0
        if sight_flicker_parity then sign = -1.0 end
        wobble_az = FLICKER_EPS * sign
        wobble_el = FLICKER_EPS * sign
    else
        wobble_az = DITHER_AZ_DEG * math.sin(2.0 * math.pi * DITHER_HZ * t)
        wobble_el = DITHER_EL_DEG * math.cos(2.0 * math.pi * DITHER_HZ * t)
    end

    local write_az_deg = u_az + wobble_az
    local write_el_deg = u_el + wobble_el
    if sight_mode == "hold" then
        -- No net motion -- dither/flicker only, atop the last commanded
        -- value, never a fresh correction.
        write_az_deg = sight_last_write_az_cmd * 60.0 + wobble_az
        write_el_deg = wobble_el -- elevation's last raw command is kept below
    end

    local write_az_cmd = write_az_deg / 60.0
    local write_el_cmd
    if write_el_deg >= 0 then
        write_el_cmd = write_el_deg / GIMBAL_EL_UP_DEG
    else
        write_el_cmd = write_el_deg / -GIMBAL_EL_DOWN_DEG
    end
    if sight_mode == "hold" then
        write_el_cmd = sight_last_write_el_cmd + wobble_el / GIMBAL_EL_UP_DEG
    end
    write_az_cmd = math.max(-1.5, math.min(1.5, write_az_cmd))
    write_el_cmd = math.max(-1.5, math.min(1.5, write_el_cmd))

    sight_point_quiet(write_az_cmd, write_el_cmd)
    sight_last_write_az_cmd = write_az_cmd
    sight_last_write_el_cmd = write_el_cmd
end

-- `LuaExportAfterNextFrame`'s single per-frame entry point for the sight
-- servo (`plans/9k113-hands-off-switch/implementation.md`) -- kept as its
-- own small function, separate from `run_sight_servo`, purely to stay off
-- that function's own 60-upvalue ceiling (see its comment above). When
-- `SIGHT_HANDS_OFF` is set, `run_sight_servo` is not called at all --
-- `sight_point_quiet`'s own guard would block the writes either way, but
-- the goal/mark/stall tracking that feeds them would still be meaningless
-- while the pilot is pointing the sight by hand -- and `sight_mode` is set
-- to `"hands_off"` every frame instead, so body-layer's slew trace does
-- not read as normal tracking.
local function sight_servo_tick(t)
    if SIGHT_HANDS_OFF then
        sight_mode = "hands_off"
        return
    end
    run_sight_servo(t)
end

-- Sends `run_sight_servo`'s own status -- mode (`off|caged|hold|homing|
-- closed|hands_off`, v3: `open` renamed `homing`, its meaning changed with
-- it, see v3's "Merged mode"; `hands_off` added by
-- `plans/9k113-hands-off-switch/implementation.md`), setpoint, the
-- mark-derived body direction (or `null` when invalid), error, the stall
-- flag, and (v3) `field_target_*`/`mark_clipped` -- a feed with its own
-- wire key ("servo_mode", a different rate class from the change-gated
-- `watch_args`/`read_args` lines: this one changes every frame under the
-- per-frame wobble). Called once per `LuaExportAfterNextFrame`'s own 5 Hz
-- export throttle, same cadence as the telemetry line.
local function push_sight_servo_state(t)
    if client == nil then
        return
    end
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"servo_mode":"' .. tostring(sight_mode) .. '"'
        .. ',"setpoint_azimuth_deg":' .. fmt_num_or_null(sight_setpoint_body_az_deg)
        .. ',"setpoint_elevation_deg":' .. fmt_num_or_null(sight_setpoint_body_el_deg)
        .. ',"mark_azimuth_deg":' .. fmt_num_or_null(sight_mark_body_az_deg)
        .. ',"mark_elevation_deg":' .. fmt_num_or_null(sight_mark_body_el_deg)
        .. ',"error_azimuth_deg":' .. fmt_num_or_null(sight_error_az_deg)
        .. ',"error_elevation_deg":' .. fmt_num_or_null(sight_error_el_deg)
        .. ',"stalled":' .. tostring(sight_stalled)
        .. ',"stall_count":' .. tostring(sight_stall_count)
        .. ',"field_target_azimuth_deg":' .. fmt_num_or_null(sight_field_target_body_az_deg)
        .. ',"field_target_elevation_deg":' .. fmt_num_or_null(sight_field_target_body_el_deg)
        .. ',"mark_clipped":' .. tostring(sight_mark_clipped) .. '}\n')
    if not ok then
        debug_log("sight-servo send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

local function on_stop()
    -- BL-B66 Stage 4b: flush whatever the slew-trace buffer still holds so
    -- a mission end/restart does not lose up to SLEW_LOG_FLUSH_EVERY_N_
    -- LINES-1 lines (a true no-op when SLEW_DEBUG is off -- the buffer is
    -- then always empty).
    slew_log_flush()
    if slew_log_file then
        slew_log_file:close()
        slew_log_file = nil
    end
    -- `plans/9k113-sight-pointing/plan.md`, BL-B80: a mission end/restart
    -- is not an observed OBSERV falling edge, so `run_sight_servo`'s own
    -- falling-edge reset never runs for it -- reset explicitly here so a
    -- stale goal/servo state never survives into the next mission.
    sight_goal_az_deg = nil
    sight_goal_el_deg = nil
    sight_goal_rate_az_deg_s = 0.0
    sight_goal_rate_el_deg_s = 0.0
    sight_goal_t_sim = nil
    sight_setpoint_body_az_deg = nil
    sight_setpoint_body_el_deg = nil
    sight_mode = "off"
    sight_mark_body_az_deg = nil
    sight_mark_body_el_deg = nil
    sight_error_az_deg = nil
    sight_error_el_deg = nil
    sight_field_target_body_az_deg = nil
    sight_field_target_body_el_deg = nil
    sight_mark_clipped = false
    sight_prev_field_target_body_az_deg = nil
    sight_prev_field_target_body_el_deg = nil
    sight_last_frame_t = nil
    sight_last_write_az_cmd = 0.0
    sight_last_write_el_cmd = 0.0
    sight_stall_window_start_t = nil
    sight_stalled = false
    sight_stall_count = 0
    -- F1 fix: a mission end/restart is not an observed OBSERV falling
    -- edge either (same reasoning as the rest of this block) -- without
    -- this, `sight_was_observ_on` could stay `true` from the sortie
    -- that just ended, so the new sortie's first off frame would wrongly
    -- fire the one-time zero write before OBSERV has even been read
    -- this mission.
    sight_was_observ_on = false
end

M.handle_sight_target_command = handle_sight_target_command
M.push_slew_trace = push_slew_trace
M.sight_servo_tick = sight_servo_tick
M.push_sight_servo_state = push_sight_servo_state
M.on_stop = on_stop

return M
