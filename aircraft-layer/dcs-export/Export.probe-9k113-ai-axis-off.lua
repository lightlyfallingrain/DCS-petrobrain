--[[
PETROVICH 9K113 AI-AXIS-WITH-OVERLAY-OFF PROBE (AI-latency probe, run 2) --
not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-22-9k113-ai-latency-probe.md, "Run 2".

WHY
  Run 1 found the AI axis (device 7, 3061) held a per-frame target with DCS
  AI Petrovich's overlay OFF -- contradicting 2026-10-21, whose AI-off runs
  only ever wrote once per step. It also found 874/876 echo the PLAYER axis
  input rather than the head position. Run 1 had player-axis writes before
  the AI axis, and its elevation step put the mark off the ASP-17, so the
  pilot could not judge Part B by eye. Run 2: azimuth only, AI axis first,
  never a ShowMenu press. Whether 874 reports the head under the AI axis is
  judged by the pilot's eyes; every row also logs the run-1 candidate
  position args (565/566 az, 555/556 elev), and every step diffs all args.

  P1  AI axis per frame, overlay off, before any player-axis write:
      10 deg L, 10 deg R, then 10 deg L held through TURN 2 (does the sight
      stay 10 deg left of the nose, or keep its world direction?).
  P2  writes stop: does the sight stay or move?
  P3  player axis per frame: short pulses, then axis 0 holds.
  P4  TURN 1, axis 0: does the sight keep its world direction?

START
  Waits for OBSERV (arg 886) on, then START_DELAY_S (gyro alignment, the move
  to the pilot seat). Timeline in the card, T+ from OBSERV on. Writes centre
  on both axes at the end and on any error.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_ai_axis_off.log"

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
local ARG_AZ = 874
local ARG_ELEV = 876
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060
local CMD_PLAYER_AZ = 3026
local CMD_PLAYER_ELEV = 3025

-- Run-1 candidate head-position args, logged in every row.
local WATCH_ARGS = { 565, 566, 555, 556 }

local OBSERV_DEBOUNCE_S = 0.5
local START_DELAY_S = 20.0

local AI_10L = -10.0 / 60.0
local AI_10R = 10.0 / 60.0

-- { mode, cmd, value, hold_s, label }. mode: "ai" re-asserts the AI axis
-- (elevation 0 alongside), "player" re-asserts the player axis, "none" writes
-- nothing at all.
local STEPS = {
    { "ai",     CMD_AI_AZ,     AI_10L, 10.0, "P1 AI az 10 L (overlay OFF) -- mark 10 deg left?" },
    { "ai",     CMD_AI_AZ,     AI_10R, 10.0, "P1 AI az 10 R -- mark 10 deg right?" },
    { "ai",     CMD_AI_AZ,     AI_10L,  5.0, "P1 AI az 10 L -- settle before TURN 2" },
    { "ai",     CMD_AI_AZ,     AI_10L, 20.0, "TURN 2: gentle ~30 deg RIGHT turn, then level; AI holds 10 L" },
    { "none",   nil,           nil,    10.0, "P2 writes stopped -- sight stays or moves?" },
    { "player", CMD_PLAYER_AZ,  0.3,    1.0, "P3 player az +0.3 pulse" },
    { "player", CMD_PLAYER_AZ,  0.0,    9.0, "P3 player az 0 -- holds?" },
    { "player", CMD_PLAYER_AZ, -0.3,    2.0, "P3 player az -0.3 pulse (twice as long)" },
    { "player", CMD_PLAYER_AZ,  0.0,    8.0, "P3 player az 0 -- holds, left of where it started?" },
    { "player", CMD_PLAYER_AZ,  0.0,   20.0, "TURN 1: gentle ~30 deg LEFT turn, then level; axis 0" },
}

local DENSE_FRAMES = 30         -- per-frame rows at each step start
local DENSE_EVERY_S = 0.25      -- then every 0.25 s

-- All-arg diff scans.
local SCAN_MAX_ARG = 3000
local SCAN_EPS = 0.003
local SCAN_LOG_MAX = 80

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

local function snapshot_args()
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    local s = {}
    for a = 0, SCAN_MAX_ARG do
        local ok, v = pcall(fn, mp, a)
        if ok and type(v) == "number" then s[a] = v end
    end
    return s
end

local function log_arg_diff(label, s0, s1)
    if s0 == nil or s1 == nil then
        log("  SCAN " .. label .. ": no snapshot")
        return
    end
    local d = {}
    for a, v1 in pairs(s1) do
        local v0 = s0[a]
        if type(v0) == "number" and math.abs(v1 - v0) > SCAN_EPS then d[#d + 1] = { a, v0, v1 } end
    end
    table.sort(d, function(x, y) return math.abs(x[3] - x[2]) > math.abs(y[3] - y[2]) end)
    log(string.format("  SCAN %s: %d args changed > %.3f", label, #d, SCAN_EPS))
    for i = 1, math.min(#d, SCAN_LOG_MAX) do
        log(string.format("    arg %4d  %s -> %s  (%+.5f)", d[i][1], fmt(d[i][2]), fmt(d[i][3]), d[i][3] - d[i][2]))
    end
end

local function set_quiet(cmd, value)
    local dev = GetDevice(DEV_I9K113)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, cmd, value)
end

local function centre_all()
    set_quiet(CMD_PLAYER_AZ, 0.0)
    set_quiet(CMD_PLAYER_ELEV, 0.0)
    set_quiet(CMD_AI_AZ, 0.0)
    set_quiet(CMD_AI_ELEV, 0.0)
end

local function readback_row(dt, tag)
    local az, el = read_arg(ARG_AZ), read_arg(ARG_ELEV)
    local deg = type(az) == "number" and string.format("%+.1f deg", az / 0.44 * 60) or "?"
    local sd = try("LoGetSelfData", LoGetSelfData)
    local hdg = type(sd) == "table" and safe_index(sd, "Heading") or nil
    local hdg_s = type(hdg) == "number" and string.format("%05.1f", math.deg(hdg) % 360) or "?"
    local w = {}
    for _, a in ipairs(WATCH_ARGS) do w[#w + 1] = string.format("%d=%s", a, fmt(read_arg(a))) end
    log(string.format("  . %s t=%7.3f  874=%s (%s)  876=%s  886=%s  hdg=%s  %s",
                      tag, dt, fmt(az), deg, fmt(el), fmt(read_arg(ARG_OBSERVE)), hdg_s,
                      table.concat(w, " ")))
end

-- ---------------------------------------------------------------- state
local started, t0 = false, nil
local phase = "WAIT_OBSERV"
local observ_on_since = nil
local delay_start = nil
local last_heartbeat_t = -1e9
local last_slow_t = -1e9
local aborted = false

local idx, step_start, step_frames, last_dense = 0, nil, 0, -1e9
local step_snap = nil

local function start_step(dt)
    local r = STEPS[idx]
    log(string.format("=== STEP %d/%d t=%7.3f  %s  (%s %s, %.0f s)",
                      idx, #STEPS, dt, r[5], r[1], fmt(r[3]), r[4]))
    step_start, step_frames, last_dense = dt, 0, -1e9
    step_snap = snapshot_args()
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 AI-AXIS-OFF PROBE (run 2) -- AI axis per frame with the overlay off, then player axis")
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
    log("9k113 ai-axis-off probe: stopped.")
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

        if phase ~= "STEPS" and phase ~= "FINISHED" and (dt - last_slow_t) >= 1.0 then
            readback_row(dt, "1s")
            last_slow_t = dt
        end

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format("  OBSERV on at t=%7.3f = T+0. Steps in %.0f s. Go to the PILOT seat.",
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
            if (dt - last_heartbeat_t) >= 5.0 then
                log(string.format("  . steps in %.0f s", START_DELAY_S - (dt - delay_start)))
                last_heartbeat_t = dt
            end
            if (dt - delay_start) >= START_DELAY_S then
                phase = "STEPS"
                idx = 1
                start_step(dt)
            end
            return
        end

        if phase == "STEPS" then
            local r = STEPS[idx]
            if r[1] == "ai" then
                set_quiet(r[2], r[3])
                set_quiet(CMD_AI_ELEV, 0.0)
            elseif r[1] == "player" then
                set_quiet(r[2], r[3])
            end
            step_frames = step_frames + 1
            if step_frames <= DENSE_FRAMES or (dt - last_dense) >= DENSE_EVERY_S then
                readback_row(dt, "S" .. idx)
                last_dense = dt
            end
            if (dt - step_start) >= r[4] then
                log_arg_diff(string.format("S%d %s, step start -> end", idx, r[5]), step_snap, snapshot_args())
                idx = idx + 1
                if idx > #STEPS then
                    centre_all()
                    log(string.format("=== DONE t=%7.3f. Centre written once; the sight is released.", dt))
                    log("  PROBE DONE. Re-copy the production Export.lua afterwards.")
                    phase = "FINISHED"
                    return
                end
                start_step(dt)
            end
            return
        end
    end)
    if not ok then
        aborted = true
        log("  UNCAUGHT ERROR in frame callback: " .. tostring(err))
        pcall(centre_all)
    end
end
