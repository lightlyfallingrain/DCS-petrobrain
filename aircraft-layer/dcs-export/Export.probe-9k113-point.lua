--[[
PETROVICH 9K113 POINTING PROBE -- not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-21-9k113-point-probe.md.

WHAT THIS PROBE ANSWERS
  Does a single AI-axis position write (device 7, SetCommand 3061 azimuth /
  3060 elevation) point the 9K113 sight where it was told, and hold it there?
  Runs 1-5 on 2026-10-21 showed the readback (args 874/876) reads 0 in this
  setup, so the pilot's eyes are the measurement. Each target is written ONCE
  and held 10 s with no re-assertion, moving straight from one target to the
  next (no return to centre in between).

  Azimuth value = degrees / 60 (2026-09-11 calibration, stops at +-60 deg).
  Elevation is written as a raw value: its degree mapping has never been
  measured, so the pilot's estimate is part of the answer.

START
  Waits for OBSERV (arg 886) on, then START_DELAY_S, then runs the schedule
  once. Writes centre (0, 0) at the end and on any error.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_point.log"

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

local OBSERV_DEBOUNCE_S = 0.5
-- Long enough to move from the copilot seat (where the switches are) to the
-- pilot seat before the first write.
local START_DELAY_S = 20.0
local HOLD_S = 10.0

-- { az_deg, elev_value, label }. Each row is held HOLD_S.
local SCHEDULE = {
    {   0, 0.0,  "centre" },
    { -20, 0.0,  "20 deg LEFT" },
    {  20, 0.0,  "20 deg RIGHT" },
    { -40, 0.0,  "40 deg LEFT" },
    {  40, 0.0,  "40 deg RIGHT" },
    { -60, 0.0,  "60 deg LEFT (azimuth stop)" },
    {  60, 0.0,  "60 deg RIGHT (azimuth stop)" },
    {   0, 0.5,  "centre azimuth, elevation +0.5 (UP?)" },
    {   0, -0.5, "centre azimuth, elevation -0.5 (DOWN?)" },
    {  30, 0.25, "30 deg RIGHT, elevation +0.25" },
    {   0, 0.0,  "centre" },
}

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

local function set_command(cmd, value, label)
    local dev = try("GetDevice(7)", GetDevice, DEV_I9K113)
    if dev == nil then return false end
    local fn = safe_index(dev, "SetCommand")
    if type(fn) ~= "function" then
        log("  " .. label .. ": device 7 has no SetCommand")
        return false
    end
    local ok, err = pcall(fn, dev, cmd, value)
    log(string.format("  %s: SetCommand(%d, %s) ok=%s err=%s",
                      label, cmd, fmt(value), tostring(ok), tostring(err)))
    return ok
end

local function point(az_deg, elev_value, label)
    set_command(CMD_AI_AZ, az_deg / 60.0, label .. " az")
    set_command(CMD_AI_ELEV, elev_value, label .. " elev")
end

-- ---------------------------------------------------------------- state
local started, t0 = false, nil
local phase = "WAIT_OBSERV"
local observ_on_since = nil
local delay_start = nil
local row_idx = 0
local row_start = nil
local last_heartbeat_t = -1e9
local aborted = false

-- Run 2: the readback is logged too. Run 1 showed AI-axis writes do nothing
-- while DCS's own AI Petrovich is off; on 2026-09-11 (AI Petrovich on) both the
-- write and 874/876 worked.
local ARG_AZ = 874
local ARG_ELEV = 876
local READBACK_EVERY_S = 1.0
local last_readback_t = -1e9

local function log_readback(dt)
    local az, el = read_arg(ARG_AZ), read_arg(ARG_ELEV)
    local deg = type(az) == "number" and string.format("%+.1f deg", az / 0.44 * 60) or "?"
    log(string.format("  . t=%6.1f  874=%s (%s)  876=%s  886=%s",
                      dt, fmt(az), deg, fmt(el), fmt(read_arg(ARG_OBSERVE))))
end

local function start_row(dt)
    local r = SCHEDULE[row_idx]
    log(string.format("=== TARGET %d/%d t=%6.1f  %s   (az %+d deg, elev %s), holding %.0f s",
                      row_idx, #SCHEDULE, dt, r[3], r[1], fmt(r[2]), HOLD_S))
    point(r[1], r[2], "target " .. row_idx)
    row_start = dt
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 POINTING PROBE -- watch where the sight goes")
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
    log("  Waiting for OBSERV (arg 886) on.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 pointing probe: stopped.")
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

        -- Logged in every phase, including before OBSERV and after the
        -- schedule ends, so whatever DCS AI Petrovich does is captured too.
        if (dt - last_readback_t) >= READBACK_EVERY_S then
            log_readback(dt)
            last_readback_t = dt
        end

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format("  OBSERV on at t=%6.1f -- first target in %.0f s. Go to the PILOT seat.",
                                      dt, START_DELAY_S))
                    phase = "DELAY"
                    delay_start = dt
                end
            else
                observ_on_since = nil
            end
            return
        end

        if phase == "DELAY" then
            if (dt - last_heartbeat_t) >= 5.0 then
                log(string.format("  . first target in %.0f s", START_DELAY_S - (dt - delay_start)))
                last_heartbeat_t = dt
            end
            if (dt - delay_start) >= START_DELAY_S then
                phase = "RUNNING"
                row_idx = 1
                start_row(dt)
            end
            return
        end

        if phase == "RUNNING" then
            if (dt - row_start) >= HOLD_S then
                row_idx = row_idx + 1
                if row_idx > #SCHEDULE then
                    point(0, 0.0, "final centre")
                    log("  PROBE DONE -- exit whenever. Re-copy the production Export.lua afterwards.")
                    phase = "FINISHED"
                    return
                end
                start_row(dt)
            end
        end
    end)
    if not ok then
        aborted = true
        log("  UNCAUGHT ERROR in frame callback: " .. tostring(err))
        pcall(point, 0, 0.0, "error centre")
    end
end
