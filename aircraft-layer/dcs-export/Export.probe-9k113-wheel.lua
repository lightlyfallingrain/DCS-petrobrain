--[[
PETROVICH 9K113 WHEEL-STATE / DITHER / OVERLAY PROBE (AI-latency probe,
run 9) -- not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-22-9k113-ai-latency-probe.md, "Run 9".

WHY
  Runs 6-8: DCS obeys the AI azimuth axis (device 7, 3061, per frame)
  intermittently -- ignored 3 to 100+ s, invisibly; the stick park toggle
  does not restore it (run 8). Prior-art note
  (aircraft-layer/research/2026-10-22-9k113-ai-axis-obedience-prior-art.md):
  ED's own Petrovich AI may be a second writer to the sight while OBSERV
  is on. Three things are tested together:

  - WHEEL STATE: list_indication(10) (Petrovich's AI wheel: OBSERV. OFF /
    WAITING / SEARCHING / TRACKING) is logged on every change, and every
    stall line carries it. Do ignored stretches line up with one state?
  - O  observe: closed-loop tracking between targets 2 deg either side of
    boresight (as run 8), no tricks -> baseline.
  - W  dither (pilot's idea, 2026-10-22: "keep small movement all the
    time, small circle on target"): the same tracking with a small circle
    added (1.5 deg azimuth command, 0.03 elevation, 1 s period), so the
    command never rests -> fewer stalls?
  - V  overlay cheat: on a stall, open DCS Petrovich's AI overlay (ShowMenu,
    device 30, 3001), close it 1.5 s later -> does that reset whatever holds
    the sight?

  Per step: response ratio = path the mark actually moved / path the
  commands asked for (1.0 = fully obeyed, 0 = ignored). Per-policy summary
  at the end.

  Every row logs the ASP-17 mark (565/566/555/556), 898 and 957-962; lamp
  changes are logged the frame they happen.

  Overlay OFF at start. Pilot seat throughout, no 9K113 view, no joystick
  axes bound to the operator's controls. Writes: the AI axis and ShowMenu.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_wheel.log"

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
local WATCH_ARGS = { 565, 566, 555, 556, 898, 957, 958, 959, 960, 961, 962 }

-- Guidance-unit lamps PK_9K113_L1..L14 (lamps.lua:619-632) and the 9K113 board
-- lamps 957-962. Every change is logged the frame it happens, from probe start,
-- so the alignment-done lamp (pilot: L5 "ROLL SYNC TR UNCAGE", likely arg 898)
-- shows its own flip time.
local LAMP_ARGS = {
    { 902, "L1" }, { 901, "L2" }, { 888, "L3" }, { 889, "L4" }, { 898, "L5" },
    { 904, "L6" }, { 900, "L7" }, { 894, "L8" }, { 896, "L9" }, { 897, "L10" },
    { 891, "L11" }, { 892, "L12" }, { 895, "L13" }, { 893, "L14" },
    { 957, "COMPL_ON" }, { 958, "PU_OFF" }, { 959, "CHECK" }, { 960, "READY" },
    { 961, "MSL_EXIST" }, { 962, "LAUNCH_PERM" },
}
local LAMP_EPS = 0.1

local OBSERV_DEBOUNCE_S = 0.5
local START_DELAY_S = 20.0

local function ai(deg) return deg / 60.0 end

-- { mode, cmd, value, hold_s, label, policy }. mode "track" steers the AI
-- azimuth axis in a closed loop on arg 566 toward value; policy is "observe",
-- "recover" or "preempt" (see header). "none" writes nothing.
local MARK_PER_DEG = 0.039     -- 565/566 change per degree of azimuth
local TRACK_GAIN = 3.0         -- command deg per deg of error (rate = cmd / 3 per s)
local TRACK_MAX_DEG = 2.5
local STALL_CMD_DEG = 1.5      -- only judge a stall while commanding at least this
local STALL_WINDOW_S = 0.4
local STALL_MOVE_EPS = 0.003   -- 566 change over the window that counts as moving
local TOGGLE_MIN_GAP_S = 1.0
local DITHER_AZ_DEG = 1.5      -- added azimuth command amplitude in "dither" steps
local DITHER_EL = 0.03         -- elevation command amplitude (0.3 deg/s), 90 deg out of phase
local DITHER_PERIOD_S = 1.0
local OVERLAY_HOLD_S = 1.5     -- overlay open this long, then closed again
local OVERLAY_MIN_GAP_S = 4.0
local DEV_PETROVICH = 30
local CMD_SHOW_MENU = 3001
local WHEEL_INDICATOR_ID = 10
local WHEEL_POLL_S = 0.1

local LEFT, RIGHT, CENTRE = 0.422, 0.578, 0.500   -- 2 deg either side of boresight

local STEPS = {}
local function track(target, hold_s, policy, label)
    STEPS[#STEPS + 1] = { "track", CMD_AI_AZ, target, hold_s, label, policy }
end
local function block(tag, policy, targets)
    for i, tg in ipairs(targets) do
        track(tg, 6.0, policy, string.format("%s %d/%d: track to %.3f (%s)", tag, i, #targets, tg, policy))
    end
end

track(CENTRE, 6.0, "observe", "settle: track to boresight (observe)")
block("O", "observe", { LEFT, RIGHT, LEFT, RIGHT, LEFT })
block("W", "dither", { RIGHT, LEFT, RIGHT, LEFT, RIGHT, LEFT, RIGHT })
block("V", "overlay", { LEFT, RIGHT, LEFT, RIGHT, LEFT })
track(CENTRE, 6.0, "observe", "end: track to boresight (observe)")
STEPS[#STEPS + 1] = { "none", nil, nil, 3.0, "writes stopped" }

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
local lamp_last = {}

local function log_lamp_changes(dt)
    for _, e in ipairs(LAMP_ARGS) do
        local v = read_arg(e[1])
        if type(v) == "number" then
            local prev = lamp_last[e[1]]
            if prev == nil then
                log(string.format("  lamp %d %s = %s (initial) t=%7.3f", e[1], e[2], fmt(v), dt))
                lamp_last[e[1]] = v
            elseif math.abs(v - prev) >= LAMP_EPS then
                local tplus = delay_start and string.format("T+%.1f", dt - delay_start) or "before T+0"
                log(string.format("  lamp %d %s %s -> %s  t=%7.3f  %s", e[1], e[2], fmt(prev), fmt(v), dt, tplus))
                lamp_last[e[1]] = v
            end
        end
    end
end

local frame_dt, prev_t = nil, nil
local hist = {}              -- { {dt, m566}, ... } over the last STALL_WINDOW_S+
local cmd_big_since = nil
local in_stall, stall_t = false, nil
local last_toggle_t, toggles = -1e9, 0
local stats = {}             -- per policy: stalls, stalled_s, resumed, resumed_after_toggle, unresolved

local function stat(policy)
    if stats[policy] == nil then
        stats[policy] = { stalls = 0, stalled_s = 0.0, resumed = 0, after_toggle = 0, lat = {}, unresolved = 0 }
    end
    return stats[policy]
end

local function toggle(dt, why)
    set_quiet(CMD_STICK_PARK, 1.0)
    toggles = toggles + 1
    last_toggle_t = dt
    log(string.format("  >>> TOGGLE #%d SetCommand(%d, 1) t=%7.3f  (%s)", toggles, CMD_STICK_PARK, dt, why))
end

local function close_stall(dt, policy, how)
    local st = stat(policy)
    st.stalled_s = st.stalled_s + (dt - stall_t)
    if how == "resumed" then
        st.resumed = st.resumed + 1
        local since_toggle = dt - last_toggle_t
        if last_toggle_t >= stall_t then
            st.after_toggle = st.after_toggle + 1
            st.lat[#st.lat + 1] = since_toggle
        end
        log(string.format("  <<< RESUMED t=%7.3f after %.2f s stalled%s", dt, dt - stall_t,
            last_toggle_t >= stall_t and string.format(", %.2f s after toggle #%d", since_toggle, toggles) or ""))
    else
        st.unresolved = st.unresolved + 1
        log(string.format("  <<< STALL UNRESOLVED at step end t=%7.3f after %.2f s", dt, dt - stall_t))
    end
    in_stall, stall_t = false, nil
    hist, cmd_big_since = {}, nil   -- judge the next stall on a fresh window
end

local wheel_state, wheel_raw, last_wheel_t = "?", nil, -1e9
local function wheel_poll(dt)
    if (dt - last_wheel_t) < WHEEL_POLL_S then return end
    last_wheel_t = dt
    if type(list_indication) ~= "function" then return end
    local ok, txt = pcall(list_indication, WHEEL_INDICATOR_ID)
    if not ok or type(txt) ~= "string" then return end
    local flat = txt:gsub("%s+", " ")
    if flat == wheel_raw then return end
    wheel_raw = flat
    local st = "other"
    for _, k in ipairs({ "TRACKING", "SEARCHING", "WAITING", "OBSERV" }) do
        if flat:find(k, 1, true) then st = k break end
    end
    local tplus = delay_start and string.format("T+%.1f", dt - delay_start) or "before T+0"
    log(string.format("  ~~~ WHEEL %s -> %s  t=%7.3f %s  | %s", wheel_state, st, dt, tplus, flat:sub(1, 200)))
    wheel_state = st
end

local overlay_presses, overlay_open_t, last_overlay_t = 0, nil, -1e9
local function press_show_menu(dt, why)
    local dev = try("GetDevice(30)", GetDevice, DEV_PETROVICH)
    if dev == nil then return end
    local ok1 = pcall(dev.performClickableAction, dev, CMD_SHOW_MENU, 1)
    local ok2 = pcall(dev.performClickableAction, dev, CMD_SHOW_MENU, 0)
    overlay_presses = overlay_presses + 1
    log(string.format("  >>> ShowMenu PRESS #%d t=%7.3f (%s) ok=%s/%s", overlay_presses, dt, why, tostring(ok1), tostring(ok2)))
end

local path_act, path_exp, last_m = 0.0, 0.0, nil

local function start_step(dt)
    local prev = STEPS[idx - 1]
    if prev ~= nil and prev[1] == "track" then
        log(string.format("  ... S%d response ratio %.2f (moved %.3f of %.3f asked)  wheel=%s",
            idx - 1, path_exp > 0 and path_act / path_exp or 0, path_act, path_exp, wheel_state))
        local st = stat(prev[6])
        st.ratios = st.ratios or {}
        st.ratios[#st.ratios + 1] = path_exp > 0 and path_act / path_exp or 0
    end
    path_act, path_exp, last_m = 0.0, 0.0, nil
    if in_stall and prev ~= nil then close_stall(dt, prev[6] or "none", "unresolved") end
    hist, cmd_big_since = {}, nil
    local r = STEPS[idx]
    if r[1] == "track" and r[6] == "preempt" then toggle(dt, "preempt at target change") end
    log(string.format("=== STEP %d/%d t=%7.3f  %s  (%s %s, %.0f s)",
                      idx, #STEPS, dt, r[5], r[1], fmt(r[3]), r[4]))
    step_start, step_frames, last_dense = dt, 0, -1e9
    step_snap = snapshot_args()
    if r[1] == "park" then
        set_quiet(CMD_STICK_PARK, 1.0)
        log(string.format("  >>> SetCommand(%d, 1) -- Park/Unpark Operators Stick toggle", CMD_STICK_PARK))
    end
end

local function track_frame(dt, r)
        local m = read_arg(566)
        local cmd_deg = 0.0
        if type(m) == "number" then
            local err_deg = (r[3] - m) / MARK_PER_DEG
            cmd_deg = math.max(-TRACK_MAX_DEG, math.min(TRACK_MAX_DEG, TRACK_GAIN * err_deg))
            if last_m ~= nil then path_act = path_act + math.abs(m - last_m) end
            last_m = m
            hist[#hist + 1] = { dt, m }
            while #hist > 1 and hist[2][1] <= dt - STALL_WINDOW_S do table.remove(hist, 1) end
        end
        local loop_deg, el = cmd_deg, 0.0
        if r[6] == "dither" then
            local ph = 2 * math.pi * (dt - step_start) / DITHER_PERIOD_S
            cmd_deg = cmd_deg + DITHER_AZ_DEG * math.sin(ph)
            el = DITHER_EL * math.cos(ph)
        end
        set_quiet(CMD_AI_AZ, ai(cmd_deg))
        set_quiet(CMD_AI_ELEV, el)
        if frame_dt ~= nil then
            -- 0.18 deg is the spec deadzone (0.003 unit); the mark clips at 0.333/0.667.
            local edge = (m ~= nil) and ((m <= 0.334 and cmd_deg < 0) or (m >= 0.666 and cmd_deg > 0))
            if math.abs(cmd_deg) > 0.18 and not edge then
                path_exp = path_exp + math.abs(cmd_deg) / 3.0 * MARK_PER_DEG * frame_dt
            end
        end
        cmd_deg = loop_deg
        if math.abs(cmd_deg) >= STALL_CMD_DEG then
            if cmd_big_since == nil then cmd_big_since = dt end
        else
            cmd_big_since = nil
        end
        local full = #hist >= 2 and hist[1][1] <= dt - STALL_WINDOW_S
        local moving = full and math.abs(hist[#hist][2] - hist[1][2]) > STALL_MOVE_EPS
        local judged = full and cmd_big_since ~= nil and (dt - cmd_big_since) >= STALL_WINDOW_S
        if in_stall and (moving or cmd_big_since == nil) then
            close_stall(dt, r[6], "resumed")
        elseif not in_stall and judged and not moving then
            in_stall, stall_t = true, dt
            stat(r[6]).stalls = stat(r[6]).stalls + 1
            log(string.format("  !!! STALL t=%7.3f  cmd %+.1f deg  566=%s  (%s)  wheel=%s", dt, cmd_deg, fmt(m), r[6], wheel_state))
        end
        if in_stall and r[6] == "overlay" and overlay_open_t == nil
           and (dt - last_overlay_t) >= OVERLAY_MIN_GAP_S then
            press_show_menu(dt, "open overlay on stall")
            overlay_open_t, last_overlay_t = dt, dt
        end
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 WHEEL/DITHER/OVERLAY PROBE (run 9) -- wheel state, dither, overlay cheat")
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
    log("9k113 wheel/dither/overlay probe: stopped.")
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

        log_lamp_changes(dt)
        wheel_poll(dt)
        if overlay_open_t ~= nil and (dt - overlay_open_t) >= OVERLAY_HOLD_S then
            press_show_menu(dt, "close overlay")
            overlay_open_t = nil
        end
        frame_dt = (prev_t ~= nil) and (dt - prev_t) or nil
        prev_t = dt

        if phase ~= "STEPS" and phase ~= "FINISHED" and (dt - last_slow_t) >= 1.0 then
            readback_row(dt, "1s")
            last_slow_t = dt
        end

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format("  OBSERV on at t=%7.3f = T+0. Steps in %.0f s. Go to the PILOT seat and stay there (no 9K113 view).",
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
            elseif r[1] == "track" then
                track_frame(dt, r)
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
                    if in_stall then close_stall(dt, r[6] or "none", "unresolved") end
                    if overlay_presses % 2 == 1 then press_show_menu(dt, "close overlay at end") end
                    log("=== SUMMARY per policy")
                    for _, p in ipairs({ "observe", "dither", "overlay" }) do
                        local st = stat(p)
                        local rs = {}
                        for _, v in ipairs(st.ratios or {}) do rs[#rs + 1] = string.format("%.2f", v) end
                        log(string.format("  %-8s stalls=%d stalled=%.1f s resumed=%d unresolved=%d  response ratios: %s",
                            p, st.stalls, st.stalled_s, st.resumed, st.unresolved, table.concat(rs, " ")))
                    end
                    log(string.format("  ShowMenu presses: %d", overlay_presses))
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
