--[[
PETROVICH SPU-8 INTERCOM READ/WRITE PROBE -- not the production script.

Self-contained; does NOT need the collector. Appends to
Logs\aircraft_layer_probe_spu8.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`; afterwards re-copy the production
`aircraft-layer/dcs-export/Export.lua` from the repository (do not restore a
.backup -- see aircraft-layer/WORKFLOW.md).

Card: docs/acceptance/2026-10-05-spu8-intercom-probe.md
Findings it feeds: aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md

WHAT IS ALREADY KNOWN
  * GetDevice(n):performClickableAction(cmd, value) from Export.lua moves
    cockpit controls (BL-6 wheel effector; the early ASP-17 control).
  * Every control written so far belonged to the pilot's seat.

WHAT THIS PROBE ANSWERS
  1. What get_argument_value really returns for the SPU-8 controls:
       456 pilot Radio/ICS switch      457 pilot SPU-8 volume knob
       376 network switch 2            377 network switch 1
       664 OPERATOR intercom power (crew_member_access = {1})
     Logged on every change, plus a heartbeat every 5 s.
  2. Whether a write to 664 works while the player sits in the PILOT seat:
       SPU-8 is device 55, CMD_SPU8_O_ICS = 3015.
     At t+30 s it writes the OPPOSITE of 664's current value (so a write that
     does nothing cannot look like success), and at t+50 s writes the original
     value back (so a change that happens to coincide cannot look like
     causation). Each write logs 664 before, and 1 s / 5 s after.

TIMELINE (model time from the first exported frame)
  0-30 s   read-only. Click 456 both ways, sweep 457 end to end.
  30 s     WRITE 1: 664 -> opposite.     Hands off the intercom panel.
  50 s     WRITE 2: 664 -> original.     Hands off the intercom panel.
  60 s+    read-only again; "PROBE DONE" is logged. Exit whenever.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_spu8.log"

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
local DEV_SPU8 = 55
local CMD_SPU8_O_ICS = 3015
local ARGS = { 456, 457, 376, 377, 664 }
local ARG_O_ICS = 664

local T_WRITE_1 = 30.0
local T_WRITE_2 = 50.0
local T_DONE = 60.0
local HEARTBEAT_S = 5.0

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function fmt(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.3f", v)
end

local function snapshot()
    local parts = {}
    for _, a in ipairs(ARGS) do
        parts[#parts + 1] = string.format("%d=%s", a, fmt(read_arg(a)))
    end
    return table.concat(parts, " ")
end

local function write_o_ics(value)
    local dev = try("GetDevice(55)", GetDevice, DEV_SPU8)
    if dev == nil then
        log("  write: GetDevice(55) returned nil")
        return
    end
    local fn = safe_index(dev, "performClickableAction")
    if type(fn) ~= "function" then
        log("  write: device 55 has no performClickableAction")
        return
    end
    local ok, err = pcall(fn, dev, CMD_SPU8_O_ICS, value)
    log(string.format("  write performClickableAction(3015, %s): ok=%s err=%s",
                      fmt(value), tostring(ok), tostring(err)))
end

-- ============================================================= driver
local started, t0 = false, nil
local last_snap, last_beat = nil, -1e9
local original_664 = nil
local w1_done, w2_done, done_logged = false, false, false
local checks = {}   -- { at = model_time, label = string }

local function schedule_checks(t, label)
    checks[#checks + 1] = { at = t + 1.0, label = label .. " +1s" }
    checks[#checks + 1] = { at = t + 5.0, label = label .. " +5s" }
end

function LuaExportStart()
    log("")
    log("#########################################################")
    log("SPU-8 INTERCOM READ/WRITE PROBE")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("spu8 probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log("  t=0: read-only phase. Click 456 both ways, sweep 457 end to end.")
        log("  Write 1 at t+" .. T_WRITE_1 .. "s, write 2 at t+" .. T_WRITE_2 .. "s.")
    end
    local dt = t - t0

    local s = snapshot()
    if s ~= last_snap or (dt - last_beat) >= HEARTBEAT_S then
        local tag = (s ~= last_snap) and "~" or "."
        log(string.format("  %s t=%5.1f %s", tag, dt, s))
        last_snap, last_beat = s, dt
    end

    for i = #checks, 1, -1 do
        if dt >= checks[i].at then
            log(string.format("  CHECK %-14s 664=%s", checks[i].label, fmt(read_arg(ARG_O_ICS))))
            table.remove(checks, i)
        end
    end

    if not w1_done and dt >= T_WRITE_1 then
        w1_done = true
        original_664 = read_arg(ARG_O_ICS)
        local target = (type(original_664) == "number" and original_664 > 0.5) and 0 or 1
        log(string.format("  WRITE 1 at t=%.1f: 664 before=%s, writing %d (opposite)",
                          dt, fmt(original_664), target))
        write_o_ics(target)
        schedule_checks(dt, "after write 1")
    end

    if not w2_done and dt >= T_WRITE_2 then
        w2_done = true
        local restore = (type(original_664) == "number" and original_664 > 0.5) and 1 or 0
        log(string.format("  WRITE 2 at t=%.1f: 664 before=%s, writing %d (original)",
                          dt, fmt(read_arg(ARG_O_ICS)), restore))
        write_o_ics(restore)
        schedule_checks(dt, "after write 2")
    end

    if not done_logged and dt >= T_DONE then
        done_logged = true
        log("  PROBE DONE -- exit whenever. Re-copy the production Export.lua afterwards.")
    end
end
