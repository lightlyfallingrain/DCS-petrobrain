--[[
PETROVICH 9K113 SLEW-GATE PROBE (AI-latency probe, run 6) -- not the
production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-22-9k113-ai-latency-probe.md, "Run 6".

WHY
  The AI axis (device 7, 3061/3060, per frame) is a rate command at the
  spec-file rates (20 deg/s az, 10 deg/s elev per unit), but sometimes it is
  ignored. Every time it was ignored, arg 962 (9K113 LAUNCH PERMITTED lamp)
  was lit; in run 5b the axis worked, the sight came back near centre, the
  lamp lit, and every later command was ignored. The lamp is an effect;
  the gate is unknown. Candidate: the operator stick's Park/Unpark toggle
  (Command_StickPark_Ext = 3055 on device 7).

  S1-S9   2.5 deg L/R pulses, twice: reproduce the gate (works, returns to
          centre, then ignored?).
  S10     SetCommand(3055, 1) once -- toggles Park/Unpark.
  S11-S14 the same pulses: does the axis work again?
  S15     SetCommand(3055, 1) once more -- toggles it back.
  S16-S17 one more pulse.
  S18     pilot makes a ~3 deg heading change with the axis at 0: if the
          sight is held at boresight, does the mark stay fixed to the airframe
          (caged) or slide with the heading change (gyro world hold)?
          Boresight is the aircraft's own axis (pilot, 2026-10-22).
  S19-S24 escape attempts: a short 10 deg azimuth pulse, a short elevation
          pulse, then 2.5 deg again -- does a bigger or a different-axis
          command break the hold?

  Pilot, 2026-10-22: the LAUNCH PERMITTED lamp (962) is lit when the sight
  points within ~0.3 deg of boresight (the guidance beam's width), else off.
  So 962 doubles as an at-boresight readback, and every ignored command so
  far happened with the sight at boresight.
  Every row logs the ASP-17 mark (565/566/555/556) and the operator's right
  board lamps 957-962 (962 = LAUNCH PERMITTED).

  Overlay OFF. The only writes are the AI axis and the two 3055 toggles.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_slew_gate.log"

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
local CMD_STICK_PARK = 3055   -- Command_StickPark_Ext, Park/Unpark Operators Stick (toggle)

-- Run-1 candidate head-position args, logged in every row.
local WATCH_ARGS = { 565, 566, 555, 556, 957, 958, 959, 960, 961, 962 }

local OBSERV_DEBOUNCE_S = 0.5
local START_DELAY_S = 20.0

local function ai(deg) return deg / 60.0 end

-- { mode, cmd, value, hold_s, label }. mode: "ai" re-asserts the AI azimuth
-- axis (elevation 0 alongside); "park" sends SetCommand(3055, 1) once at the
-- step start, then holds the AI axis at 0; "none" writes nothing at all.
local STEPS = {
    { "ai",   CMD_AI_AZ, ai(0),    4.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(-2.5), 4.0, "AI az 2.5 L" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(2.5),  4.0, "AI az 2.5 R" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(-2.5), 4.0, "AI az 2.5 L (second)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(2.5),  4.0, "AI az 2.5 R (second)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "park", CMD_AI_AZ, ai(0),    3.0, "STICK PARK TOGGLE #1, then AI az 0" },
    { "ai",   CMD_AI_AZ, ai(-2.5), 4.0, "AI az 2.5 L (after toggle)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(2.5),  4.0, "AI az 2.5 R (after toggle)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "park", CMD_AI_AZ, ai(0),    3.0, "STICK PARK TOGGLE #2 (back), then AI az 0" },
    { "ai",   CMD_AI_AZ, ai(-2.5), 4.0, "AI az 2.5 L (after second toggle)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "ai",   CMD_AI_AZ, ai(0),    8.0, "HDG: gentle ~3 deg heading change, then back; axis 0 (caged to the airframe, or gyro-held?)" },
    { "ai",   CMD_AI_AZ, ai(-10),  0.5, "ESCAPE: AI az 10 L, 0.5 s" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "aie",  CMD_AI_ELEV, -0.1,   1.0, "ESCAPE: AI elev -0.1, 1 s" },
    { "aie",  CMD_AI_ELEV,  0.0,   3.0, "AI elev 0" },
    { "ai",   CMD_AI_AZ, ai(2.5),  4.0, "AI az 2.5 R (after escapes)" },
    { "ai",   CMD_AI_AZ, ai(0),    3.0, "AI az 0" },
    { "none", nil,       nil,      3.0, "writes stopped" },
}

-- Native getter names seen in the module DLLs (2026-09-11), plus guesses.
local CANDIDATE_METHODS = {
    "get_LandPoint", "getLandPoint", "get_land_point", "get_CameraPoint", "getCameraPoint",
    "getCurrentFOV", "get_current_fov", "is9K113Aiming", "isCaged", "isGyroReady",
    "getHelperIsOn", "is_nabl_on", "get_azimuth", "get_elevation", "getAzimuth",
    "getElevation", "get_angles", "get_sight_angles", "get_target_point", "get_aim_point",
}
local ENUM_DEVICES = { 7, 16, 0 }
local MAX_ENUM_KEYS = 200

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

local live_getters = {}     -- { dev_id, name, fn } that returned a value at enumeration

local function compact(v, depth)
    depth = depth or 0
    if type(v) == "number" then return string.format("%.5f", v) end
    if type(v) ~= "table" or depth > 2 then return tostring(v) end
    local p, n = {}, 0
    for k, x in pairs(v) do
        n = n + 1
        if n > 12 then p[#p + 1] = "..." break end
        p[#p + 1] = tostring(k) .. "=" .. compact(x, depth + 1)
    end
    return "{" .. table.concat(p, ",") .. "}"
end

local function call_getter(dev, fn)
    local res = { pcall(fn, dev) }
    if not res[1] then return false, "ERR " .. tostring(res[2]) end
    local out = {}
    for i = 2, #res do out[#out + 1] = compact(res[i]) end
    if #out == 0 then return true, "(no return)" end
    return true, table.concat(out, " | ")
end

local function readback_row(dt, tag)
    local az, el = read_arg(ARG_AZ), read_arg(ARG_ELEV)
    local deg = type(az) == "number" and string.format("%+.1f deg", az / 0.44 * 60) or "?"
    local sd = try("LoGetSelfData", LoGetSelfData)
    local hdg = type(sd) == "table" and safe_index(sd, "Heading") or nil
    local hdg_s = type(hdg) == "number" and string.format("%05.1f", math.deg(hdg) % 360) or "?"
    local w = {}
    for _, a in ipairs(WATCH_ARGS) do w[#w + 1] = string.format("%d=%s", a, fmt(read_arg(a))) end
    local pby = { pcall(LoGetADIPitchBankYaw) }
    local pitch_s = (pby[1] and type(pby[2]) == "number") and string.format("%+.2f", math.deg(pby[2])) or "?"
    local g = {}
    for _, lg in ipairs(live_getters) do
        local dev = GetDevice(lg[1])
        local _, v = call_getter(dev, lg[3])
        g[#g + 1] = string.format("%d:%s=%s", lg[1], lg[2], v)
    end
    log(string.format("  . %s t=%7.3f  874=%s (%s)  876=%s  886=%s  hdg=%s  pitch=%s  %s  %s",
                      tag, dt, fmt(az), deg, fmt(el), fmt(read_arg(ARG_OBSERVE)), hdg_s, pitch_s,
                      table.concat(w, " "), table.concat(g, " ")))
end

local function list_keys(label, t)
    if type(t) ~= "table" then
        log(string.format("    %s: %s (not a table)", label, type(t)))
        return {}
    end
    local keys = {}
    local ok, err = pcall(function()
        for k, v in pairs(t) do
            if #keys >= MAX_ENUM_KEYS then break end
            keys[#keys + 1] = { tostring(k), type(v), v }
        end
    end)
    if not ok then log(string.format("    %s: pairs() failed: %s", label, tostring(err))) end
    table.sort(keys, function(x, y) return x[1] < y[1] end)
    local names = {}
    for _, e in ipairs(keys) do names[#names + 1] = e[1] .. ":" .. e[2] end
    log(string.format("    %s: %d keys  %s", label, #keys, table.concat(names, " ")))
    return keys
end

local function try_method(dev_id, dev, name, fn)
    if type(fn) ~= "function" then return end
    local ok, v = call_getter(dev, fn)
    log(string.format("      call %d:%s() -> %s", dev_id, name, v))
    if ok and v ~= "(no return)" and v ~= "nil" then
        live_getters[#live_getters + 1] = { dev_id, name, fn }
    end
end

local function enumerate_devices()
    log("=== E: device method enumeration")
    for _, dev_id in ipairs(ENUM_DEVICES) do
        local dev = try("GetDevice(" .. dev_id .. ")", GetDevice, dev_id)
        log(string.format("  device %d: %s", dev_id, type(dev)))
        if dev ~= nil then
            local found = {}
            for _, e in ipairs(list_keys("own", dev)) do found[e[1]] = e[3] end
            local mt = getmetatable(dev)
            if mt ~= nil then
                for _, e in ipairs(list_keys("metatable", mt)) do
                    if found[e[1]] == nil then found[e[1]] = e[3] end
                end
                local idx = safe_index(mt, "__index")
                if type(idx) == "table" then
                    for _, e in ipairs(list_keys("__index", idx)) do
                        if found[e[1]] == nil then found[e[1]] = e[3] end
                    end
                end
            else
                log("    metatable: nil")
            end
            -- Call every get*/is* found, then the fixed candidate list (indexed
            -- through the object, so a __index function resolves them too).
            local tried = {}
            for name, v in pairs(found) do
                if type(v) == "function" and (name:sub(1, 3) == "get" or name:sub(1, 2) == "is")
                   and name ~= "get_argument_value" then
                    tried[name] = true
                    try_method(dev_id, dev, name, v)
                end
            end
            for _, name in ipairs(CANDIDATE_METHODS) do
                if not tried[name] then
                    local fn = safe_index(dev, name)
                    if fn ~= nil then
                        try_method(dev_id, dev, name, fn)
                    end
                end
            end
        end
    end
    log(string.format("=== E done: %d live getter(s) will be logged in every row", #live_getters))
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
    if r[1] == "park" then
        set_quiet(CMD_STICK_PARK, 1.0)
        log(string.format("  >>> SetCommand(%d, 1) -- Park/Unpark Operators Stick toggle", CMD_STICK_PARK))
    end
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 SLEW-GATE PROBE (run 6) -- reproduce the gate, try the stick park toggle")
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
    log("9k113 slew-gate probe: stopped.")
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
            if r[1] == "ai" or r[1] == "park" then
                set_quiet(r[2], r[3])
                set_quiet(CMD_AI_ELEV, 0.0)
            elseif r[1] == "aie" then
                set_quiet(r[2], r[3])
                set_quiet(CMD_AI_AZ, 0.0)
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
