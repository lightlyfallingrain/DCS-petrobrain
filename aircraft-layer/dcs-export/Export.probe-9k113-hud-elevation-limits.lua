--[[
PETROVICH 9K113 HUD ELEVATION LIMITS PROBE -- not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md.

WHY (plan.md v3, "Elevation - measure in flight", ANSWERED 2026-10-26)
  The ASP-17 HUD field's azimuth clip is measured (565/566, ~+-4.3 deg,
  docs/acceptance/2026-10-22-9k113-ai-latency-probe.md line 423). Its
  elevation clip (555/556) never has been.

SIMPLIFIED PER USER, 2026-10-27 (plans/9k113-hud-elevation-limits-probe/
implementation.md has the full "Simplified per user, 2026-10-27" section
and the superseded v1 stall-margin design it replaces). One pass per
direction, no cycles, no travel-plausibility check, no phase timeout:

  wait OBSERV (886) on -> wait 15 s (gyro sync) -> slew one elevation
  direction (wobble always on) until raw 555 stops changing for ~1 s ->
  reverse briefly: if 555 moves again, that was the true edge (record
  it); if it does not move, it was a momentary command stall (DCS
  intermittently ignoring the axis), not an edge, so resume pushing the
  same way and look again -> once confirmed, do the same thing in the
  other direction -> stop writing.

  Stall handling IS the wobble: this probe reuses, unmodified in shape,
  the per-frame dither Export.lua's run_sight_servo already applies to
  the same AI axis in production (SERVO_WOBBLE == "dither" branch,
  DITHER_AZ_DEG/DITHER_HZ/DITHER_EL_DEG, Export.lua ~line 1197) -- the
  thing that keeps DCS obeying the axis at all. No separate travel-vs-
  elapsed-time plausibility math is needed: a plateau that is actually
  a stall un-sticks itself the moment the commanded direction reverses,
  because reversing is a large, unambiguous value change next to the
  stall's own frozen value -- the dither no longer has to do that job
  alone during the stall window, the deliberate reversal does.

  Which signed elevation command is visually "up" on the glass has never
  been nailed down in this project. Per-frame rows are labelled by
  command sign (`SEEK_POS`/`CHECK_POS`/`SEEK_NEG`/`CHECK_NEG`), not by
  "up"/"down" -- only the two summary lines use "UP"/"DOWN", naming the
  first and second direction commanded, not a confirmed visual
  direction. The test card asks the pilot which one they saw rise.

  Overlay OFF. Pilot seat throughout, no 9K113 view, no operator axes
  bound. The only writes are the AI elevation axis (seek/check command)
  and a matching AI azimuth write carrying only the shared dither, so
  both axes see the same per-frame value-change DCS needs.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_hud_elevation_limits.log"

local log_file = nil

local function log(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(os.date("%H:%M:%S") .. " " .. tostring(msg) .. "\n")
    log_file:flush()
end

local function try(label, fn, ...)
    local ok, a = pcall(fn, ...)
    if not ok then
        log(string.format("  %-26s ERROR: %s", label, tostring(a)))
        return nil
    end
    return a
end

local function safe_index(obj, key)
    local ok, v = pcall(function() return obj[key] end)
    if not ok then return nil end
    return v
end

-- ---------------------------------------------------------------- constants
local DEV_MAINPANEL = 0
local DEV_I9K113 = 7
local ARG_OBSERVE = 886
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

-- Mark pair (ASP-17 crosshair): 565/566 horizontal, 555/556 vertical
-- (docs/acceptance/2026-10-22-9k113-ai-latency-probe.md). 555 is the
-- measurement; 556 is logged alongside it so a divergence would be seen.
local ARG_AZ2 = 566
local ARG_EL, ARG_EL2 = 555, 556

local OBSERV_DEBOUNCE_S = 0.5

--: fixed gyro-sync wait after OBSERV comes on, per user direction
--: ("just wait 15 s on timer") -- not gated on a lamp, kept as a plain
--: timer for simplicity.
local START_DELAY_S = 15.0

--: AI-axis elevation command unit, open loop. Devices_specs/9K113.lua:
--: v_axis_velocity = 10 deg/s, so commanded rate = EL_RATE_CMD * 10 deg/s.
--: 0.05 -> 0.5 deg/s: comfortably above the 0.003-unit command deadzone
--: (Export.lua's own FLICKER_EPS comment), slow enough that one frame's
--: 555 step stays small. At MARK_DEG_PER_UNIT_EL's placeholder scale
--: (1/0.039, shared with azimuth's measured value, plans/9k113-sight-
--: pointing/plan.md line 588) and an assumed ~60 fps, one frame commands
--: ~0.0083 deg (~0.0083 * 0.039 =~ 0.00033 raw 555 units) -- see
--: implementation.md for the full resolution note.
local EL_RATE_CMD = 0.05

--: dither amplitude/rate/phase-offset, copied unmodified from production
--: Export.lua's run_sight_servo (SERVO_WOBBLE == "dither" branch, ~line
--: 1197) -- the proven per-frame value-change mechanism that keeps DCS
--: obeying this axis at all; not reinvented here. GIMBAL_EL_UP_DEG is
--: production's own degrees->raw-command scale for the elevation axis
--: (same file, ~line 1233), reused only for that unit conversion -- the
--: gimbal limits themselves are nowhere near the HUD field and are not
--: checked by this probe (user direction).
local DITHER_AZ_DEG = 0.6
local DITHER_HZ = 8.0
local DITHER_EL_DEG = DITHER_AZ_DEG * (0.03 / 1.5)
local GIMBAL_EL_UP_DEG = 20.0

--: a window of this many seconds with 555 flat to within PLATEAU_EPS,
--: while still commanding motion, counts as "stopped" -- user direction
--: ("short no-change window, e.g. ~1 s").
local PLATEAU_WINDOW_S = 1.0

--: how long the probe reverses command direction before deciding whether
--: the plateau just found was a true edge (555 moves again) or a
--: momentary command stall (555 stays put) -- user direction ("reverse
--: briefly"). The reversal ends the moment 555 moves, so this is only the
--: give-up time: by the time the 1 s flat window fills, the head is already
--: ~0.5 deg past the clip, and a 1 s reversal at the same rate would only
--: just bring it back to the edge (2026-10-28 flight data: clip reached at
--: t=44.3 s, plateau detected at 44.98 s).
local REVERSE_CHECK_S = 10.0

--: raw 555 units. The flat-window/no-movement threshold, shared by both
--: checks above: comfortably above the dither's own per-frame amplitude
--: on this axis (DITHER_EL_DEG / GIMBAL_EL_UP_DEG =~ 0.0006) and well
--: below one second of real motion at EL_RATE_CMD's rate (EL_RATE_CMD *
--: 10 deg/s * 0.039 units/deg =~ 0.0195 units/s).
local PLATEAU_EPS = 0.003

-- ---------------------------------------------------------------- helpers
local function fmt(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.5f", v)
end

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function set_quiet(cmd, value)
    local dev = GetDevice(DEV_I9K113)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, cmd, value)
end

-- Same dither shape as production run_sight_servo's SERVO_WOBBLE ==
-- "dither" branch: az sine / el cosine (90 deg out of phase), in degrees,
-- converted to the same raw command units CMD_AI_AZ/CMD_AI_ELEV take.
local function wobble(t)
    local wobble_az_deg = DITHER_AZ_DEG * math.sin(2.0 * math.pi * DITHER_HZ * t)
    local wobble_el_deg = DITHER_EL_DEG * math.cos(2.0 * math.pi * DITHER_HZ * t)
    return wobble_az_deg / 60.0, wobble_el_deg / GIMBAL_EL_UP_DEG
end

-- Writes both AI axes every frame: elevation carries the seek/check
-- command, azimuth carries only the shared dither.
local function write_axes(el_cmd, t)
    local w_az, w_el = wobble(t)
    set_quiet(CMD_AI_AZ, w_az)
    set_quiet(CMD_AI_ELEV, el_cmd + w_el)
end

local function log_row(dt, phase_label, el_cmd)
    log(string.format(
        "  . t=%8.3f phase=%-10s cmd=%+.5f  555=%s 556=%s 566=%s 886=%s",
        dt, phase_label, el_cmd,
        fmt(read_arg(ARG_EL)), fmt(read_arg(ARG_EL2)), fmt(read_arg(ARG_AZ2)), fmt(read_arg(ARG_OBSERVE))))
end

-- ---------------------------------------------------------------- state
local started, t0 = false, nil
local phase = "WAIT_OBSERV"
local observ_on_since = nil
local delay_start = nil
local aborted = false

-- Rolling window of recent {t, 555} samples, reset at the start of every
-- SEEK attempt; cleared whenever a seek (re)starts.
local hist = {}
local plateau_value = nil
-- Set when a plateau candidate is found and the reverse check begins;
-- check_ref is that candidate's 555 value.
local check_start = nil
local check_ref = nil

local edge_pos_555 = nil
local edge_neg_555 = nil

local function push_hist(t, m)
    hist[#hist + 1] = { t, m }
    -- Keep the newest sample that is at least PLATEAU_WINDOW_S old, so the
    -- history always spans the full window. Trimming on hist[1] (the old
    -- form) dropped exactly that sample, window_flat's span test could never
    -- pass, and the 2026-10-28 run pushed into the top clip (555 = 1.00000
    -- from t=45 s) for 70 s without ever seeing a plateau.
    while #hist > 2 and hist[2][1] <= t - PLATEAU_WINDOW_S do table.remove(hist, 1) end
end

local function window_flat(t)
    if #hist < 2 or hist[1][1] > t - PLATEAU_WINDOW_S then return false, nil, nil end
    local lo, hi = 1e9, -1e9
    for _, s in ipairs(hist) do
        lo = math.min(lo, s[2])
        hi = math.max(hi, s[2])
    end
    return (hi - lo) <= PLATEAU_EPS, lo, hi
end

local function start_seek(dt, sign, label)
    hist = {}
    plateau_value = nil
    log(string.format("=== %s  t=%7.3f  el_cmd=%+.5f", label, dt, sign * EL_RATE_CMD))
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 HUD ELEVATION LIMITS PROBE (simplified)")
    local v = try("LoGetVersionInfo", LoGetVersionInfo)
    if type(v) == "table" then
        local function ver(x)
            if type(x) ~= "table" then return tostring(x) end
            local p = {}
            for _, n in ipairs(x) do p[#p + 1] = tostring(n) end
            return table.concat(p, ".")
        end
        log("  DCS version: file=" .. ver(v.FileVersion) .. " product=" .. ver(v.ProductVersion))
    end
    log("  DCS AI Petrovich overlay must stay OFF throughout. Waiting for OBSERV (arg 886) on.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 hud elevation limits probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started or aborted then return end
    local ok, err = pcall(function()
        local t = try("LoGetModelTime", LoGetModelTime)
        if type(t) ~= "number" then return end
        if t0 == nil then t0 = t end
        local dt = t - t0

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format(
                        "  OBSERV on at t=%7.3f = T+0. Waiting %.0f s (gyro sync). Go to the PILOT seat.",
                        observ_on_since, START_DELAY_S))
                    phase = "DELAY"
                    delay_start = observ_on_since
                end
            else
                observ_on_since = nil
            end
            return
        end

        if phase == "DELAY" then
            if (dt - delay_start) >= START_DELAY_S then
                phase = "SEEK_POS"
                start_seek(dt, 1.0, "SEEK_POS")
            end
            return
        end

        if phase == "SEEK_POS" or phase == "SEEK_NEG" then
            local sign = (phase == "SEEK_POS") and 1.0 or -1.0
            local el_cmd = sign * EL_RATE_CMD
            write_axes(el_cmd, t)
            local m = read_arg(ARG_EL)
            log_row(dt, phase, el_cmd)
            if type(m) == "number" then
                push_hist(dt, m)
                local flat, lo, hi = window_flat(dt)
                if flat then
                    plateau_value = (lo + hi) / 2
                    check_ref = plateau_value
                    check_start = dt
                    phase = (phase == "SEEK_POS") and "CHECK_POS" or "CHECK_NEG"
                    log(string.format(
                        "  ... %s: plateau candidate 555=%.5f at t=%.3f, reversing to check",
                        phase, plateau_value, dt))
                end
            end
            return
        end

        if phase == "CHECK_POS" or phase == "CHECK_NEG" then
            local seek_sign = (phase == "CHECK_POS") and 1.0 or -1.0
            local el_cmd = -seek_sign * EL_RATE_CMD
            write_axes(el_cmd, t)
            local m = read_arg(ARG_EL)
            log_row(dt, phase, el_cmd)
            if type(m) == "number" and math.abs(m - check_ref) > PLATEAU_EPS then
                if phase == "CHECK_POS" then
                    edge_pos_555 = check_ref
                    log(string.format("EDGE UP 555=%.5f", edge_pos_555))
                    phase = "SEEK_NEG"
                    start_seek(dt, -1.0, "SEEK_NEG")
                else
                    edge_neg_555 = check_ref
                    log(string.format("EDGE DOWN 555=%.5f", edge_neg_555))
                    log(string.format("PROBE DONE up=%.5f down=%.5f", edge_pos_555, edge_neg_555))
                    phase = "DONE"
                end
                return
            end
            if (dt - check_start) >= REVERSE_CHECK_S then
                log(string.format(
                    "  ... %s: stall, not an edge (555 held at %.5f through the reverse check) -- resuming seek",
                    phase, check_ref))
                if phase == "CHECK_POS" then
                    phase = "SEEK_POS"
                    start_seek(dt, 1.0, "SEEK_POS")
                else
                    phase = "SEEK_NEG"
                    start_seek(dt, -1.0, "SEEK_NEG")
                end
            end
            return
        end

        -- phase == "DONE": no further writes.
    end)
    if not ok then
        aborted = true
        log("  UNCAUGHT ERROR in frame callback: " .. tostring(err))
    end
end
