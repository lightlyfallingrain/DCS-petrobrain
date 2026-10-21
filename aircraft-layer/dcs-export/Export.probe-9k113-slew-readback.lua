--[[
PETROVICH 9K113 SLEW READBACK PROBE -- not the production script.

Self-contained; does NOT need the collector. Appends to
Logs\aircraft_layer_probe_9k113_slew_readback.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`; afterwards re-copy the production
`aircraft-layer/dcs-export/Export.lua` from the repository (do not restore a
.backup -- see aircraft-layer/WORKFLOW.md).

Card: docs/acceptance/2026-10-21-9k113-slew-readback-probe.md
Feeds: BL-B80 (the slew-loop feedback term).

WHAT IS ALREADY KNOWN (do not re-derive -- this probe only extends it)
  * The player axis is the one Petrovich ever writes: he operates the seat the
    player does not occupy, so the case that matters is player-in-pilot-seat,
    script-writes-from-the-other-seat. (docs/acceptance/
    2026-10-21-bl-b66-effectors-sortie-results.md.) This probe reproduces that
    case: run it while sitting in the PILOT seat, and it does the slewing.
  * 2026-10-17's effector probe wrote the player axis (3025 elev / 3026 az)
    with SetCommand and saw arg 874 move 0 -> 0.165 -> 0.33 across a 3 s hold
    at 0.5 deflection -- but only sampled four times in that hold, so whether
    that is a quantised/lagged readback or genuinely stepped motion is
    unresolved (aircraft-layer/research/
    2026-10-17-9k113-effector-and-slew-probe-findings.md, finding 2). This
    probe logs every frame specifically to settle that.
  * Elevation (876) is sign-inverted relative to its command (3025): a
    positive command drives the argument negative. Azimuth (874/3026) is
    same-sign.
  * `arg_874 = (deg/60) * 0.44` is the confirmed azimuth calibration. No
    equivalent exists yet for elevation (876) -- its gauge is piecewise and
    unmeasured in degrees.

WHAT THIS PROBE ANSWERS
  Does the 9K113 sight-head readback (874 az / 876 elev) track the head
  finely and continuously when the PLAYER slew axis (device 7, SetCommand
  3025 elev / 3026 az) is written by script from the PILOT seat? Specifically:
  plateaus-vs-ramp, the smallest resulting step (via a short pulse write),
  and whether the rate looks consistent across decreasing deflections.

HOW TO FLY IT
  Sit in the PILOT seat. Power the guidance unit and switch OBSERV on by
  hand, the same setup used on 2026-10-21 (GUID PWR arg 885, OBSERV arg 886).
  The probe watches arg 886 and starts the sequence on its own, a few seconds
  after it reads on, and runs once -- azimuth first, full deflection to the
  limits and back, then +-0.5/0.25/0.1/0.05/0.02, then a single short pulse;
  then the same for elevation. Do not touch the slew controls yourself during
  the run. Total runtime from OBSERV-on is about three minutes. Exit after
  the log says PROBE DONE.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_slew_readback.log"

local log_file = nil

-- Human-readable marker lines, timestamped. JSON sample lines use log_raw
-- below instead, with no prefix, so the log stays parseable one-line-per-
-- JSON-object by the same reader triage.py already uses for
-- aircraft_layer_slew_trace.log (non-JSON lines are simply skipped by it).
local function log(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(os.date("%H:%M:%S") .. " " .. tostring(msg) .. "\n")
    log_file:flush()
end

local function log_raw(line)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(line .. "\n")
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

local ARG_AZ = 874
local ARG_ELEV = 876
local ARG_OBSERVE = 886

-- The player (slew) axis -- the one this probe writes. See the header
-- comment: the AI axis (3060/3061) is a separate, position-target channel
-- and is NOT under test here.
local CMD_PLAYER_AZ = 3026     -- left/right, same sign as arg 874
local CMD_PLAYER_ELEV = 3025   -- up/down, sign-inverted against arg 876

-- How long OBSERV must read on, continuously, before the sequence starts --
-- guards against a single noisy frame triggering early.
local OBSERV_DEBOUNCE_S = 0.5
-- Long enough to switch from the copilot seat (where the guidance-unit and
-- OBSERV switches are) back to the pilot seat before the script slews.
local START_DELAY_S = 20.0

-- Full-deflection (+-1.0) steps run until the readback stops changing for
-- this long, or this timeout, whichever comes first -- "reach the
-- mechanical limits" without hard-coding how long that takes.
local FULL_HOLD_SETTLE_S = 1.0
local FULL_HOLD_TIMEOUT_S = 8.0

-- Decreasing-deflection steps hold for a fixed duration instead -- the
-- point there is the shape of the readback at a known deflection, not
-- finding a limit.
local STEP_HOLD_S = 3.0

-- The short-pulse test: the smallest hold this probe can express cleanly
-- against a ~60 Hz frame rate without relying on sub-frame timing.
local PULSE_HOLD_S = 0.1

-- After every step's release (write 0), a fixed settle window before the
-- next one starts -- lets a still-moving head coast to a stop so one step's
-- tail doesn't contaminate the next step's start.
local RELEASE_SETTLE_S = 1.0

-- Smallest change worth calling "moved", for the full-deflection settle
-- detector. Well below the 0.00073 raw-unit step 2026-10-17 inferred from a
-- 0.1 deg/s elevation gauge guess, so it will not mistake sensor noise for a
-- stop -- deliberately permissive; the frame-by-frame JSON log is the real
-- evidence, this is only a "when to stop holding" heuristic.
local MOVED_EPSILON = 0.0002

-- ---------------------------------------------------------------- readers
local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function fmt(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.5f", v)
end

local function fmt_num_or_null(v)
    if type(v) ~= "number" then return "null" end
    return string.format("%.5f", v)
end

-- ---------------------------------------------------------------- writer
local function set_command(dev_id, cmd, value, label)
    local dev = try("GetDevice(" .. dev_id .. ")", GetDevice, dev_id)
    if dev == nil then
        log(string.format("  %s: GetDevice(%d) returned nil", label, dev_id))
        return false
    end
    local fn = safe_index(dev, "SetCommand")
    if type(fn) ~= "function" then
        log(string.format("  %s: device %d has no SetCommand", label, dev_id))
        return false
    end
    local ok, err = pcall(fn, dev, cmd, value)
    log(string.format("  %s: SetCommand(%d, %s) ok=%s err=%s",
                      label, cmd, fmt(value), tostring(ok), tostring(err)))
    return ok
end

-- Writes 0 to both player-axis commands. Called on completion AND on any
-- error -- restoring the axis is more important than finishing the
-- sequence.
local function restore_axes(reason)
    log("  --- RESTORE (" .. tostring(reason) .. "): writing 0 to both player-axis commands")
    set_command(DEV_I9K113, CMD_PLAYER_AZ, 0, "player az -> 0")
    set_command(DEV_I9K113, CMD_PLAYER_ELEV, 0, "player elev -> 0")
end

-- One JSON sample per frame while the sequence is running. Same flat shape
-- as the production Export.lua's push_slew_trace (t/az/elev/observe/
-- slew_cmd_az/slew_cmd_el), on purpose: .claude/skills/sortie-log-triage/
-- scripts/triage.py's slew_report already reads this shape, so pointing
-- --slew at this probe's log file reuses it directly, and the readback-lag
-- section it currently skips (because production always sends null commands)
-- has real data to work with here.
local function log_sample(t, az, elev, observe, cmd_az, cmd_elev)
    log_raw(string.format(
        '{"t":%.3f,"az":%s,"elev":%s,"observe":%s,"slew_cmd_az":%s,"slew_cmd_el":%s}',
        t, fmt_num_or_null(az), fmt_num_or_null(elev), fmt_num_or_null(observe),
        fmt_num_or_null(cmd_az), fmt_num_or_null(cmd_elev)
    ))
end

-- ============================================================= sequence
-- Per axis: full deflection both signs (held to the limit), then five
-- decreasing deflections both signs (held a fixed time), then one short
-- pulse. Azimuth first, then elevation -- the order the card tells the
-- pilot to expect.
local AXES = {
    { name = "az",   cmd = CMD_PLAYER_AZ,   arg = ARG_AZ },
    { name = "elev", cmd = CMD_PLAYER_ELEV, arg = ARG_ELEV },
}

local DEFLECTIONS_STEP = { 0.5, -0.5, 0.25, -0.25, 0.1, -0.1, 0.05, -0.05, 0.02, -0.02 }

-- Built once at load time: a flat list of
-- { axis, value, mode = "full"|"fixed"|"pulse", hold }.
local STEPS = {}
for _, axis in ipairs(AXES) do
    STEPS[#STEPS + 1] = { axis = axis, value =  1.0, mode = "full" }
    STEPS[#STEPS + 1] = { axis = axis, value = -1.0, mode = "full" }
    for _, v in ipairs(DEFLECTIONS_STEP) do
        STEPS[#STEPS + 1] = { axis = axis, value = v, mode = "fixed", hold = STEP_HOLD_S }
    end
    STEPS[#STEPS + 1] = { axis = axis, value = 1.0, mode = "pulse", hold = PULSE_HOLD_S }
end

-- ============================================================= state
-- "WAIT_OBSERV" -> "START_DELAY" -> "HOLDING" / "RELEASING" (per step,
-- cycling through STEPS) -> "DONE" / "ABORTED".
local phase = "WAIT_OBSERV"
local started, t0 = false, nil
local observ_on_since = nil
local sequence_start_t = nil
local step_idx = 0
local step_start_t = nil
local last_arg_value, last_change_t = nil, nil
local last_heartbeat_t = -1e9
local aborted = false

local function current_step()
    return STEPS[step_idx]
end

local function start_step(dt)
    local s = current_step()
    log(string.format("  --- STEP %d/%d t=%6.1f  axis=%s  value=%s  mode=%s",
                      step_idx, #STEPS, dt, s.axis.name, fmt(s.value), s.mode))
    set_command(DEV_I9K113, s.axis.cmd, s.value, s.axis.name .. " -> " .. fmt(s.value))
    step_start_t = dt
    last_arg_value, last_change_t = nil, nil
    phase = "HOLDING"
end

local function advance_to_next_step(dt)
    step_idx = step_idx + 1
    if step_idx > #STEPS then
        phase = "DONE"
        return
    end
    start_step(dt)
end

local function begin_sequence(dt)
    log(string.format("  ================ SEQUENCE START t=%6.1f ================", dt))
    sequence_start_t = dt
    step_idx = 1
    start_step(dt)
end

-- ============================================================= driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 SLEW READBACK PROBE")
    local v = try("LoGetVersionInfo", LoGetVersionInfo)
    if type(v) == "table" then
        -- FileVersion/ProductVersion are TABLES of numbers, not strings --
        -- see the effector probe's own comment on this; every positional
        -- argument number here depends on the build.
        local function ver(x)
            if type(x) ~= "table" then return tostring(x) end
            local p = {}
            for _, n in ipairs(x) do p[#p + 1] = tostring(n) end
            return table.concat(p, ".")
        end
        log("  DCS version: " .. tostring(v.ProductName)
            .. " file=" .. ver(v.FileVersion) .. " product=" .. ver(v.ProductVersion))
    end
    log("  Argument numbers are POSITIONAL -- record the version above.")
    log("  Waiting for OBSERV (arg 886) to read on, set up by hand from the pilot seat.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 slew readback probe: stopped.")
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
            local observ_on = type(observe) == "number" and observe >= 0.5
            if observ_on then
                if observ_on_since == nil then observ_on_since = dt end
            else
                observ_on_since = nil
            end
            if (dt - last_heartbeat_t) >= 2.0 then
                log(string.format("  . t=%6.1f waiting for OBSERV, now=%s", dt, fmt(observe)))
                last_heartbeat_t = dt
            end
            if observ_on_since ~= nil and (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                log(string.format("  OBSERV confirmed on at t=%6.1f -- starting in %.0f s",
                                  dt, START_DELAY_S))
                phase = "START_DELAY"
                observ_on_since = dt -- reuse as the delay's own start marker
            end
            return
        end

        if phase == "START_DELAY" then
            if (dt - last_heartbeat_t) >= 1.0 then
                log(string.format("  . t=%6.1f starting in %.1f s",
                                  dt, START_DELAY_S - (dt - observ_on_since)))
                last_heartbeat_t = dt
            end
            if (dt - observ_on_since) >= START_DELAY_S then
                begin_sequence(dt)
            end
            return
        end

        if phase == "HOLDING" or phase == "RELEASING" then
            local az = read_arg(ARG_AZ)
            local elev = read_arg(ARG_ELEV)
            local observe = read_arg(ARG_OBSERVE)
            local s = current_step()
            local cmd_az, cmd_elev = nil, nil
            if phase == "HOLDING" then
                if s.axis.name == "az" then cmd_az = s.value else cmd_elev = s.value end
            end
            log_sample(dt, az, elev, observe, cmd_az, cmd_elev)

            if phase == "HOLDING" then
                local tracked = read_arg(s.axis.arg)
                if type(tracked) == "number" then
                    if last_arg_value == nil then
                        last_arg_value, last_change_t = tracked, dt
                    elseif math.abs(tracked - last_arg_value) > MOVED_EPSILON then
                        last_arg_value, last_change_t = tracked, dt
                    end
                end
                local held_for = dt - step_start_t
                local done
                if s.mode == "full" then
                    local settled = last_change_t ~= nil and (dt - last_change_t) >= FULL_HOLD_SETTLE_S
                    done = settled or held_for >= FULL_HOLD_TIMEOUT_S
                else
                    done = held_for >= s.hold
                end
                if done then
                    set_command(DEV_I9K113, s.axis.cmd, 0, s.axis.name .. " release")
                    log(string.format("    step %d held %.2fs, releasing  874=%s 876=%s",
                                      step_idx, held_for, fmt(az), fmt(elev)))
                    step_start_t = dt
                    phase = "RELEASING"
                end
            else -- RELEASING
                if (dt - step_start_t) >= RELEASE_SETTLE_S then
                    advance_to_next_step(dt)
                end
            end
            return
        end

        if phase == "DONE" then
            restore_axes("sequence complete")
            log(string.format("  ================ SEQUENCE DONE t=%6.1f ================", dt))
            log("  PROBE DONE -- exit whenever. Re-copy the production Export.lua afterwards.")
            phase = "FINISHED"
            return
        end
        -- phase == "FINISHED": nothing more to do.
    end)

    if not ok then
        aborted = true
        log("  UNCAUGHT ERROR in frame callback: " .. tostring(err))
        pcall(restore_axes, "error")
    end
end
