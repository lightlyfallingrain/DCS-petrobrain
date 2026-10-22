--[[
PETROVICH 9K113 AI-LATENCY PROBE -- not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-22-9k113-ai-latency-probe.md.

WHAT THIS PROBE ANSWERS
  Part A -- does the PLAYER slew axis (device 7, SetCommand 3026 az / 3025
  elev) steer the sight when it is re-asserted EVERY FRAME, with DCS AI
  Petrovich OFF? The 2026-10-21 readback runs wrote it once per step and saw
  only a 4-6 frame blip. If it steers, BL-B80 might not need the overlay --
  but only if something still says where the sight points. 874/876 are the
  sight head's own gauge args (Sight9K113_Azimuth/Elevation); with his AI
  off they have read 0, but no run has shown them reading 0 while the head
  was actually off-centre. Part A answers it: the pilot's eyes on the ASP-17
  mark against 874/876 in this log. Each step also diffs every cockpit arg
  (0..SCAN_MAX_ARG) from its start to its end, in case another arg tracks
  the head when 874/876 do not.

  Part B -- latency from a ShowMenu press (device 30, cmd 3001, his AI ON)
  until the AI-axis readback obeys a target re-asserted every frame. Sets
  BL-B80's AI-off detector timeout and re-press interval. The first press is
  also bracketed by an all-arg diff: centre -> 20 deg left with 874 as known
  truth, which lists every arg that moves with the head. Cross-read against
  Part A's diffs.

  Part C -- with the target still held, the pilot closes the overlay by hand
  (his AI-menu key). The probe detects it from the readback, presses ShowMenu
  itself and measures the recovery, up to MAX_RECOVERIES times.

START
  Waits for OBSERV (arg 886) on, then START_DELAY_S (covers the ~10 s gyro
  alignment and the move to the pilot seat). Timeline in the card, T+ from
  OBSERV on. Writes centre on both axes at the end and on any error.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_ai_latency.log"

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
local DEV_PETROVICH = 30
local ARG_OBSERVE = 886
local ARG_AZ = 874
local ARG_ELEV = 876
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060
local CMD_PLAYER_AZ = 3026     -- left/right, same sign as arg 874
local CMD_PLAYER_ELEV = 3025   -- up/down, sign-inverted against arg 876
local CMD_SHOW_MENU = 3001

local OBSERV_DEBOUNCE_S = 0.5
local START_DELAY_S = 20.0

-- Part A schedule, player axis, re-asserted every frame. { cmd, value, hold_s, label }.
local PART_A = {
    { CMD_PLAYER_AZ,   0.5, 10.0, "player az +0.5 (RIGHT?)" },
    { CMD_PLAYER_AZ,   0.0,  5.0, "player az 0 (does it stay or return?)" },
    { CMD_PLAYER_AZ,  -0.5, 10.0, "player az -0.5 (LEFT?)" },
    { CMD_PLAYER_AZ,   0.0,  5.0, "player az 0" },
    { CMD_PLAYER_ELEV, 0.5, 10.0, "player elev +0.5 (DOWN? sign-inverted)" },
    { CMD_PLAYER_ELEV, 0.0,  5.0, "player elev 0" },
    -- Flown in the air: the gyro holds the sight's world direction while the airframe turns. Does 874
    -- (airframe-relative?) change during a turn with his AI off? Heading is in every row.
    { CMD_PLAYER_AZ,   0.0, 15.0, "TURN 1: pilot makes a gentle ~30 deg turn, axis 0" },
}

-- Part B/C: AI-axis target, 20 deg left, re-asserted every frame.
local TARGET_AZ_DEG = -20.0
local TARGET_AZ_VALUE = TARGET_AZ_DEG / 60.0
local TARGET_AZ_ARG = TARGET_AZ_VALUE * 0.44   -- -0.14667
local OBEY_TOL = 0.005                         -- arg units, ~0.7 deg
local PART_B_CHECK_S = 2.0      -- re-assert this long before pressing, in case his AI is already on
local PART_B_HOLD_S = 20.0      -- from the press to the start of Part C
local PART_C_S = 60.0
local DETECT_S = 0.2            -- readback near 0 this long => his AI is off
local NEAR_ZERO = 0.01
local MIN_REPRESS_S = 3.0
local MAX_RECOVERIES = 3
local LATENCY_GIVE_UP_S = 10.0

-- All-arg diff scans: which cockpit args move with the sight head?
local SCAN_MAX_ARG = 3000
local SCAN_EPS = 0.003
local SCAN_LOG_MAX = 80

local READBACK_EVERY_S = 1.0
local DENSE_FRAMES = 30         -- per-frame readback rows at each Part A step start
local DENSE_EVERY_S = 0.25      -- then every 0.25 s within Part A

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

local function press_show_menu(dt, why)
    local dev = try("GetDevice(30)", GetDevice, DEV_PETROVICH)
    if dev == nil then return false end
    local ok1 = pcall(dev.performClickableAction, dev, CMD_SHOW_MENU, 1)
    local ok2 = pcall(dev.performClickableAction, dev, CMD_SHOW_MENU, 0)
    log(string.format("  >>> ShowMenu PRESS t=%7.3f (%s) ok=%s/%s", dt, why, tostring(ok1), tostring(ok2)))
    return ok1 and ok2
end

local function readback_row(dt, tag)
    local az, el = read_arg(ARG_AZ), read_arg(ARG_ELEV)
    local deg = type(az) == "number" and string.format("%+.1f deg", az / 0.44 * 60) or "?"
    local sd = try("LoGetSelfData", LoGetSelfData)
    local hdg = type(sd) == "table" and safe_index(sd, "Heading") or nil
    local hdg_s = type(hdg) == "number" and string.format("%05.1f", math.deg(hdg) % 360) or "?"
    log(string.format("  . %s t=%7.3f  874=%s (%s)  876=%s  886=%s  hdg=%s",
                      tag, dt, fmt(az), deg, fmt(el), fmt(read_arg(ARG_OBSERVE)), hdg_s))
end

local function obeys(az)
    return type(az) == "number" and math.abs(az - TARGET_AZ_ARG) <= OBEY_TOL
end

local function near_zero(az)
    return type(az) == "number" and math.abs(az) <= NEAR_ZERO
end

-- ---------------------------------------------------------------- state
local started, t0 = false, nil
local phase = "WAIT_OBSERV"
local observ_on_since = nil
local delay_start = nil
local last_heartbeat_t = -1e9
local last_readback_t = -1e9
local aborted = false

local a_idx, a_start, a_frames, a_last_dense = 0, nil, 0, -1e9
local a_snap = nil
local b_snap = nil           -- at the Part B press; diffed once the readback obeys

local b_start = nil
local press_t = nil          -- last ShowMenu press awaiting the readback to obey
local latencies = {}
local c_start = nil
local zero_since = nil
local last_press_t = -1e9
local recoveries = 0

local function start_a_row(dt)
    local r = PART_A[a_idx]
    log(string.format("=== PART A %d/%d t=%7.3f  %s  SetCommand(%d, %s) every frame, %.0f s",
                      a_idx, #PART_A, dt, r[4], r[1], fmt(r[2]), r[3]))
    a_start, a_frames, a_last_dense = dt, 0, -1e9
    a_snap = snapshot_args()
end

local function finish(dt)
    centre_all()
    log(string.format("=== DONE t=%7.3f. Latencies (press -> 874 obeys):", dt))
    for i, l in ipairs(latencies) do
        log(string.format("    %d: %s", i, l))
    end
    log("  PROBE DONE -- his AI is probably still ON; turn it off whenever. Re-copy the production Export.lua afterwards.")
    phase = "FINISHED"
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 AI-LATENCY PROBE -- player axis per frame, then ShowMenu latency")
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
    log("  DCS AI Petrovich must be OFF. Waiting for OBSERV (arg 886) on.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 ai-latency probe: stopped.")
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

        if phase ~= "PART_A" and (dt - last_readback_t) >= READBACK_EVERY_S then
            readback_row(dt, "1s")
            last_readback_t = dt
        end

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format("  OBSERV on at t=%7.3f = T+0. Part A in %.0f s. Go to the PILOT seat.",
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
                log(string.format("  . Part A in %.0f s", START_DELAY_S - (dt - delay_start)))
                last_heartbeat_t = dt
            end
            if (dt - delay_start) >= START_DELAY_S then
                phase = "PART_A"
                a_idx = 1
                start_a_row(dt)
            end
            return
        end

        if phase == "PART_A" then
            local r = PART_A[a_idx]
            set_quiet(r[1], r[2])
            a_frames = a_frames + 1
            if a_frames <= DENSE_FRAMES or (dt - a_last_dense) >= DENSE_EVERY_S then
                readback_row(dt, "A")
                a_last_dense = dt
            end
            if (dt - a_start) >= r[3] then
                log_arg_diff(string.format("A%d %s, step start -> end", a_idx, r[4]), a_snap, snapshot_args())
                a_idx = a_idx + 1
                if a_idx > #PART_A then
                    centre_all()
                    log(string.format("=== PART B t=%7.3f  AI target %+.0f deg re-asserted every frame; checking %.0f s before pressing ShowMenu",
                                      dt, TARGET_AZ_DEG, PART_B_CHECK_S))
                    phase = "PART_B_CHECK"
                    b_start = dt
                    return
                end
                start_a_row(dt)
            end
            return
        end

        -- Parts B and C: AI-axis target held every frame.
        if phase == "PART_B_CHECK" or phase == "PART_B" or phase == "PART_C" then
            set_quiet(CMD_AI_AZ, TARGET_AZ_VALUE)
            set_quiet(CMD_AI_ELEV, 0.0)
        end
        local az = read_arg(ARG_AZ)

        -- A press awaiting its effect: log every frame until 874 obeys.
        if press_t ~= nil then
            readback_row(dt, "L")
            if obeys(az) then
                local l = string.format("%.3f s (press t=%.3f)", dt - press_t, press_t)
                latencies[#latencies + 1] = l
                log("  <<< READBACK OBEYS after " .. l)
                if b_snap ~= nil then
                    log_arg_diff("B press -> obeys (head centre -> 20 deg L, 874 = truth)", b_snap, snapshot_args())
                    b_snap = nil
                end
                press_t = nil
            elseif (dt - press_t) >= LATENCY_GIVE_UP_S then
                local l = string.format("NO OBEY within %.0f s (press t=%.3f)", LATENCY_GIVE_UP_S, press_t)
                latencies[#latencies + 1] = l
                log("  <<< " .. l)
                press_t = nil
            end
        end

        if phase == "PART_B_CHECK" then
            if (dt - b_start) >= PART_B_CHECK_S then
                if obeys(az) then
                    log("  his AI is already ON (readback obeys) -- NOT pressing. Part B latency not measured.")
                    latencies[#latencies + 1] = "B skipped: AI already on"
                else
                    b_snap = snapshot_args()
                    press_show_menu(dt, "Part B: turn his AI on")
                    press_t, last_press_t = dt, dt
                end
                phase = "PART_B"
                b_start = dt
            end
            return
        end

        if phase == "PART_B" then
            if (dt - b_start) >= PART_B_HOLD_S then
                log(string.format("=== PART C t=%7.3f  close the overlay by hand (his AI-menu key); the probe reopens it. %.0f s, up to %d times",
                                  dt, PART_C_S, MAX_RECOVERIES))
                phase = "PART_C"
                c_start = dt
                zero_since = nil
            end
            return
        end

        if phase == "PART_C" then
            if press_t == nil then
                if near_zero(az) then
                    if zero_since == nil then
                        zero_since = dt
                        log(string.format("  ... readback near 0 from t=%7.3f", dt))
                    end
                    if (dt - zero_since) >= DETECT_S and (dt - last_press_t) >= MIN_REPRESS_S
                       and recoveries < MAX_RECOVERIES then
                        recoveries = recoveries + 1
                        press_show_menu(dt, string.format("Part C recovery %d, zero for %.3f s", recoveries, dt - zero_since))
                        press_t, last_press_t = dt, dt
                        zero_since = nil
                    end
                else
                    zero_since = nil
                end
            end
            if (dt - c_start) >= PART_C_S and press_t == nil then
                finish(dt)
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
