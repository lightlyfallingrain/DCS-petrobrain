--[[
FLIGHT-AXES PROBE, SORTIE 1 (BL-16 mode 1, rows M0-A..M0-D) -- not the
production script. Testing aid.

Spec: plans/flight-control/plan.md, "Revised 2026-11-18 -- mode 1", stage M0.
Scaffold: Export.probe-control-command-hold.lua (probe v2, 2026-11-01).

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Petrobrain does not run while this is
deployed. Log: Logs\aircraft_layer_probe_flight_axes.log

FLIGHT: air start, straight and level, ~150 km/h, ~200 m AGL, flat ground,
controls NOT parked, player in either seat.

CONTROL: an ICS half-press (pilot trigger arg 738 or operator trigger arg
856, 0.5) is the only input. A full (radio) press is ignored.
  - Idle -> a half-press starts the next segment.
  - A read segment (A*, B1, C1) -> a half-press ends it.
  - A write segment (B2, C2, D*) runs its own schedule and ends itself;
    a half-press during one STOPS WRITING at once (abort).
  The seat whose trigger was pressed is the seat whose control args are
  captured for writing.

SEGMENTS, in order:
  A1 level 60 s | A2 20 deg bank turns both ways | A3 5 m/s climb and
  descend 100 m | A4 150 -> 220 km/h and back      (read only; note the HSI
                                                    heading at each press)
  B1 sweep pedals full left -> full right           (read only)
  B2 feet off: 2003 = captured, +-0.05, +-0.10, 3 s each   (write)
  C1 sweep collective low -> high                   (read only)
  C2 2004 = captured, then +0.02 / -0.02, 2 s each  (write; auto-abort)
  D1 hold every enabled axis 30 s while the pilot stirs stick, pedals,
     collective ~10 s each, dither 1e-3            (write)
  D2 same, dither 1e-4                              (write)

B2 and C2 decide, in flight, whether D also holds the pedals / collective:
  pedals     if the pedal arg stayed within PEDAL_HOLD_TOL of each command;
  collective if C2 finished without an abort.
Pitch and roll are always held in D (probe v2 proved them).

C2 AUTO-ABORT (stops writing 2004 at once, logged with the reason):
  |VS| > C2_ABORT_VS; the arg jumps > C2_JUMP_TOL from captured in the first
  0.5 s (sign or scale wrong); or on the first step the arg moves against
  the command (sign wrong).

LOG: one row per frame during a segment, one per 0.1 s when idle; a dump of
every getter's table at start; a per-segment SUMMARY of how often each
value changed per second (the "updates every frame?" check).
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_flight_axes.log"

-- ---------------------------------------------------------------- constants
local ARG_PILOT_PTT = 738
local ARG_OPERATOR_PTT = 856
local PRESS_MIN = 0.3
local FULL_PRESS_MIN = 0.75

local SEAT_ARGS = {
    pilot = { pitch = 1100, roll = 1101, collective = 1102, pedals = 1103 },
    operator = { pitch = 1110, roll = 1111, collective = 1112, pedals = 1113 },
}
local ARG_STICK_PARK = 852
local ARG_PEDALS_PARK = 952

local CMD = { pitch = 2001, roll = 2002, pedals = 2003, collective = 2004 }
-- command = SIGN * arg. pitch/roll proven +1 (probe v2); pedals unproven;
-- collective -1 from ED's comment. B2/C2 test these.
local SIGN = { pitch = 1.0, roll = 1.0, pedals = 1.0, collective = -1.0 }

local B2_STEPS = { 0.0, 0.05, -0.05, 0.10, -0.10, 0.0 }
local B2_STEP_S = 3.0
local PEDAL_SETTLE_S = 0.5
local PEDAL_HOLD_TOL = 0.02

local C2_STEPS = { { 0.0, 3.0 }, { 0.02, 2.0 }, { 0.0, 2.0 }, { -0.02, 2.0 }, { 0.0, 2.0 } }
local C2_ABORT_VS = 8.0
local C2_JUMP_TOL = 0.05
local C2_SIGN_CHECK_S = 1.0
local C2_SIGN_MIN_MOVE = 0.005

local D_HOLD_S = 30.0
local DITHER_D1 = 1e-3
local DITHER_D2 = 1e-4
local IDLE_ROW_S = 0.1
local FLUSH_S = 0.5

-- Camera seat, copied from Petrobrain/ai_pilot_wheel.lua (Views.lua eye x:
-- pilot 3.15 m, operator 4.65 m).
local SEAT_BOUNDARY_FWD_M = 4.1
local SEAT_CAMERA_MIN_FWD_M = 2.0
local SEAT_CAMERA_MAX_FWD_M = 7.0
local SEAT_CAMERA_MAX_OFFAXIS_M = 1.5

local SEGMENTS = {
    { id = "A1", kind = "read", say = "60 s straight and level; note HSI heading" },
    { id = "A2", kind = "read", say = "20 deg bank turns both ways; note HSI heading" },
    { id = "A3", kind = "read", say = "5 m/s climb 100 m, then descend 100 m" },
    { id = "A4", kind = "read", say = "accelerate 150 -> 220 km/h and back; note HSI heading" },
    { id = "B1", kind = "read", say = "sweep pedals slowly full left -> full right -> centre" },
    { id = "B2", kind = "pedals", say = "feet OFF the pedals; probe writes 2003" },
    { id = "C1", kind = "read", say = "sweep collective slowly low -> high -> back" },
    { id = "C2", kind = "collective", say = "hand OFF the collective; probe writes 2004" },
    { id = "D1", kind = "hold", dither = DITHER_D1, say = "stir stick 10 s, pedals 10 s, collective 10 s" },
    { id = "D2", kind = "hold", dither = DITHER_D2, say = "same again, smaller dither" },
}

-- ---------------------------------------------------------------- logging
local log_file = nil
local last_flush_t = nil

local function log(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(tostring(msg) .. "\n")
end

local function flush(t)
    if log_file ~= nil and (last_flush_t == nil or t - last_flush_t >= FLUSH_S) then
        log_file:flush()
        last_flush_t = t
    end
end

local function call(f, ...)
    if type(f) ~= "function" then return nil end
    local ok, v = pcall(f, ...)
    if ok then return v end
    return nil
end

local function dump(name, v, depth, indent)
    indent = indent or "  "
    if type(v) ~= "table" then
        log(indent .. name .. " = " .. tostring(v))
        return
    end
    log(indent .. name .. " = {")
    if depth > 0 then
        for k, x in pairs(v) do dump(tostring(k), x, depth - 1, indent .. "  ") end
    end
    log(indent .. "}")
end

local function fmt(v)
    if type(v) ~= "number" then return "nil" end
    return string.format("%.5g", v)
end

-- ---------------------------------------------------------------- reads
local function read_arg(n)
    local ok, v = pcall(function() return GetDevice(0):get_argument_value(n) end)
    if ok and type(v) == "number" then return v end
    return nil
end

local player_seat = nil

local function update_seat()
    local cam = call(LoGetCameraPosition)
    local sd = call(LoGetSelfData)
    if type(cam) ~= "table" or type(cam.p) ~= "table" or type(sd) ~= "table" then return end
    local pos = sd.Position
    local own = type(pos) == "table" and (pos.p or pos) or nil
    local hdg, pitch = sd.Heading, call(LoGetADIPitchBankYaw)
    if type(own) ~= "table" or type(hdg) ~= "number" then return end
    if type(pitch) ~= "number" then pitch = 0.0 end
    local dx, dy, dz = cam.p.x - own.x, cam.p.y - own.y, cam.p.z - own.z
    local cp = math.cos(pitch)
    local fwd = dx * cp * math.cos(hdg) + dy * math.sin(pitch) + dz * cp * math.sin(hdg)
    local off_sq = dx * dx + dy * dy + dz * dz - fwd * fwd
    if fwd < SEAT_CAMERA_MIN_FWD_M or fwd > SEAT_CAMERA_MAX_FWD_M
        or off_sq > SEAT_CAMERA_MAX_OFFAXIS_M * SEAT_CAMERA_MAX_OFFAXIS_M then
        return
    end
    player_seat = fwd >= SEAT_BOUNDARY_FWD_M and "operator" or "pilot"
end

-- Every scalar a controller might close on, by name. Order fixes the row layout.
local FIELD_NAMES = {
    "adi_pitch", "adi_bank", "adi_yaw", "sd_heading", "mag_yaw", "ias", "tas", "vs",
    "agl", "asl", "radalt", "wx", "wy", "wz", "ax", "ay", "az", "vx", "vy", "vz",
    "p_pitch", "p_roll", "p_coll", "p_ped", "o_pitch", "o_roll", "o_coll", "o_ped",
    "a852", "a952",
}

local function sample()
    local s = {}
    local p, b, y = nil, nil, nil
    if type(LoGetADIPitchBankYaw) == "function" then
        local ok, pp, bb, yy = pcall(LoGetADIPitchBankYaw)
        if ok then p, b, y = pp, bb, yy end
    end
    s.adi_pitch, s.adi_bank, s.adi_yaw = p, b, y
    local sd = call(LoGetSelfData)
    s.sd_heading = type(sd) == "table" and sd.Heading or nil
    s.mag_yaw = call(LoGetMagneticYaw)
    s.ias = call(LoGetIndicatedAirSpeed)
    s.tas = call(LoGetTrueAirSpeed)
    s.vs = call(LoGetVerticalVelocity)
    s.agl = call(LoGetAltitudeAboveGroundLevel)
    s.asl = call(LoGetAltitudeAboveSeaLevel)
    s.radalt = call(LoGetRadarAltimeter)
    local w = call(LoGetAngularVelocity)
    if type(w) == "table" then s.wx, s.wy, s.wz = w.x, w.y, w.z end
    local a = call(LoGetAccelerationUnits)
    if type(a) == "table" then s.ax, s.ay, s.az = a.x, a.y, a.z end
    local v = call(LoGetVectorVelocity)
    if type(v) == "table" then s.vx, s.vy, s.vz = v.x, v.y, v.z end
    local pa, oa = SEAT_ARGS.pilot, SEAT_ARGS.operator
    s.p_pitch, s.p_roll = read_arg(pa.pitch), read_arg(pa.roll)
    s.p_coll, s.p_ped = read_arg(pa.collective), read_arg(pa.pedals)
    s.o_pitch, s.o_roll = read_arg(oa.pitch), read_arg(oa.roll)
    s.o_coll, s.o_ped = read_arg(oa.collective), read_arg(oa.pedals)
    s.a852, s.a952 = read_arg(ARG_STICK_PARK), read_arg(ARG_PEDALS_PARK)
    return s
end

-- ---------------------------------------------------------------- state
local started = false
local triggers = {
    pilot = { arg = ARG_PILOT_PTT, peak = 0.0, pressed = false },
    operator = { arg = ARG_OPERATOR_PTT, peak = 0.0, pressed = false },
}
local next_index = 1
local seg = nil       -- {def=, seat=, t0=, captured=, sent=, ...}
local last_t = nil
local last_idle_row_t = nil
local dither_sign = 1.0
local stats = nil     -- per-segment change counts
local hold_pedals, hold_collective = false, false
local b2_worst = 0.0

local function header()
    local cols = { "t", "dt", "seg", "seat", "cmd_p", "cmd_r", "cmd_y", "cmd_c" }
    for _, n in ipairs(FIELD_NAMES) do cols[#cols + 1] = n end
    log("ROW_COLUMNS " .. table.concat(cols, " "))
end

local function row(t, dt, s)
    local sent = seg and seg.sent or {}
    local out = {
        string.format("%.3f", t), fmt(dt), seg and seg.def.id or "idle", player_seat or "nil",
        fmt(sent.pitch), fmt(sent.roll), fmt(sent.pedals), fmt(sent.collective),
    }
    for _, n in ipairs(FIELD_NAMES) do out[#out + 1] = fmt(s[n]) end
    log("ROW " .. table.concat(out, " "))
end

local function count_changes(s)
    if stats == nil then return end
    for _, n in ipairs(FIELD_NAMES) do
        local v = s[n]
        if v ~= nil and v ~= stats.prev[n] then stats.changes[n] = (stats.changes[n] or 0) + 1 end
        stats.prev[n] = v
    end
    stats.frames = stats.frames + 1
end

local function summary(t)
    if stats == nil or seg == nil then return end
    local dur = t - seg.t0
    if dur <= 0 then return end
    local parts = {}
    for _, n in ipairs(FIELD_NAMES) do
        parts[#parts + 1] = string.format("%s=%.1f", n, (stats.changes[n] or 0) / dur)
    end
    log(string.format("SUMMARY %s %.1f s, %d frames (%.1f/s), changes per second: %s",
        seg.def.id, dur, stats.frames, stats.frames / dur, table.concat(parts, " ")))
end

local function clamp(v)
    if v > 1.0 then return 1.0 end
    if v < -1.0 then return -1.0 end
    return v
end

-- ---------------------------------------------------------------- segments
local function end_segment(t, why)
    if seg == nil then return end
    summary(t)
    if seg.def.id == "B2" and why == "done" then
        hold_pedals = b2_worst <= PEDAL_HOLD_TOL
        log(string.format("B2 RESULT worst |arg - command| = %.4f -> D holds pedals: %s",
            b2_worst, tostring(hold_pedals)))
    elseif seg.def.id == "C2" then
        hold_collective = why == "done"
        log("C2 RESULT -> D holds collective: " .. tostring(hold_collective))
    end
    log(string.format("t=%.3f END %s (%s)", t, seg.def.id, why))
    seg, stats = nil, nil
end

local function start_segment(t, seat)
    local def = SEGMENTS[next_index]
    if def == nil then
        log(string.format("t=%.3f all segments done; restore the production Export.lua", t))
        return
    end
    next_index = next_index + 1
    local a = SEAT_ARGS[seat]
    seg = {
        def = def, seat = seat, t0 = t, sent = {},
        captured = {
            pitch = read_arg(a.pitch), roll = read_arg(a.roll),
            pedals = read_arg(a.pedals), collective = read_arg(a.collective),
        },
    }
    stats = { changes = {}, prev = {}, frames = 0 }
    if def.id == "B2" then b2_worst = 0.0 end
    local c = seg.captured
    log(string.format("t=%.3f START %s (%s) seat=%s player_seat=%s captured p=%s r=%s y=%s c=%s | D will hold pedals=%s collective=%s",
        t, def.id, def.say, seat, player_seat or "nil", fmt(c.pitch), fmt(c.roll), fmt(c.pedals),
        fmt(c.collective), tostring(hold_pedals), tostring(hold_collective)))
    for _, axis in ipairs({ "pitch", "roll", "pedals", "collective" }) do
        if def.kind ~= "read" and c[axis] == nil then
            log("  capture failed for " .. axis .. "; segment not written")
            end_segment(t, "capture failed")
            return
        end
    end
end

-- Returns the commands to send this frame (axis -> value), or nil when the
-- segment's own schedule has finished.
local function schedule(t, s)
    local def, c, el = seg.def, seg.captured, t - seg.t0
    if def.kind == "pedals" then
        local i = math.floor(el / B2_STEP_S) + 1
        if i > #B2_STEPS then return nil end
        local cmd = clamp(SIGN.pedals * c.pedals + B2_STEPS[i])
        local arg = seg.seat == "pilot" and s.p_ped or s.o_ped
        if arg ~= nil and el - (i - 1) * B2_STEP_S >= PEDAL_SETTLE_S then
            local err = math.abs(arg - cmd / SIGN.pedals)
            if err > b2_worst then b2_worst = err end
        end
        return { pedals = cmd }
    elseif def.kind == "collective" then
        local acc, step = 0.0, nil
        for _, st in ipairs(C2_STEPS) do
            if el < acc + st[2] then step = st break end
            acc = acc + st[2]
        end
        if step == nil then return nil end
        local arg = seg.seat == "pilot" and s.p_coll or s.o_coll
        if s.vs ~= nil and math.abs(s.vs) > C2_ABORT_VS then return false, "|VS| > " .. C2_ABORT_VS end
        if arg ~= nil and el < 0.5 and math.abs(arg - c.collective) > C2_JUMP_TOL then
            return false, string.format("jump at capture: arg %s vs captured %s (sign or scale wrong)",
                fmt(arg), fmt(c.collective))
        end
        local first_step_end = C2_STEPS[1][2] + C2_SIGN_CHECK_S
        if arg ~= nil and seg.c2_checked == nil and el >= first_step_end then
            seg.c2_checked = true
            local moved = arg - c.collective
            local expected = C2_STEPS[2][1] / SIGN.collective
            if math.abs(moved) >= C2_SIGN_MIN_MOVE and moved * expected < 0 then
                return false, string.format("arg moved %s against command (expected sign of %s): SIGN.collective wrong",
                    fmt(moved), fmt(expected))
            end
        end
        return { collective = clamp(SIGN.collective * c.collective + step[1]) }
    elseif def.kind == "hold" then
        if el >= D_HOLD_S then return nil end
        dither_sign = -dither_sign
        local d = def.dither * dither_sign
        local out = {
            pitch = clamp(SIGN.pitch * c.pitch + d),
            roll = clamp(SIGN.roll * c.roll + d),
        }
        if hold_pedals then out.pedals = clamp(SIGN.pedals * c.pedals + d) end
        if hold_collective then out.collective = clamp(SIGN.collective * c.collective + d) end
        return out
    end
    return {}
end

local function send(cmds)
    pcall(function()
        for axis, v in pairs(cmds) do LoSetCommand(CMD[axis], v) end
    end)
end

-- ---------------------------------------------------------------- trigger
local function poll_trigger(seat, t)
    local tr = triggers[seat]
    local v = read_arg(tr.arg)
    if v == nil then return end
    if v >= PRESS_MIN then
        tr.pressed = true
        if v > tr.peak then tr.peak = v end
        return
    end
    if not tr.pressed then return end
    local peak = tr.peak
    tr.pressed, tr.peak = false, 0.0
    if peak >= FULL_PRESS_MIN then
        log(string.format("t=%.3f %s trigger full press (peak %.2f), ignored", t, seat, peak))
        return
    end
    if seg ~= nil then
        end_segment(t, seg.def.kind == "read" and "done" or "ABORTED by ICS press")
    else
        start_segment(t, seat)
    end
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("FLIGHT-AXES PROBE, SORTIE 1 (M0-A..M0-D) " .. os.date("%Y-%m-%d %H:%M:%S"))
    log(string.format("  SIGN pitch=%+.0f roll=%+.0f pedals=%+.0f collective=%+.0f",
        SIGN.pitch, SIGN.roll, SIGN.pedals, SIGN.collective))
    log("  ICS half-press: idle -> start next segment; read segment -> end; write segment -> ABORT")
    log("#########################################################")
    log("GETTER DUMP")
    dump("LoGetSelfData", call(LoGetSelfData), 3)
    dump("LoGetAngularVelocity", call(LoGetAngularVelocity), 1)
    dump("LoGetAccelerationUnits", call(LoGetAccelerationUnits), 1)
    dump("LoGetVectorVelocity", call(LoGetVectorVelocity), 1)
    dump("LoGetCameraPosition", call(LoGetCameraPosition), 2)
    for _, n in ipairs({ "LoGetMagneticYaw", "LoGetIndicatedAirSpeed", "LoGetTrueAirSpeed",
        "LoGetVerticalVelocity", "LoGetAltitudeAboveGroundLevel", "LoGetAltitudeAboveSeaLevel",
        "LoGetRadarAltimeter" }) do
        local f = _G[n]
        log(string.format("  %s: %s -> %s", n, type(f), tostring(call(f))))
    end
    header()
    started = true
end

function LuaExportStop()
    log("flight-axes probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportBeforeNextFrame()
    if not started then return end
    local ok, err = pcall(function()
        local t = LoGetModelTime()
        if type(t) ~= "number" then return end
        local dt = last_t and (t - last_t) or nil
        last_t = t
        update_seat()
        poll_trigger("pilot", t)
        poll_trigger("operator", t)
        local s = sample()
        if seg ~= nil and seg.def.kind ~= "read" then
            local cmds, why = schedule(t, s)
            if cmds == nil then
                end_segment(t, "done")
            elseif cmds == false then
                end_segment(t, "AUTO-ABORT: " .. why)
            else
                send(cmds)
                seg.sent = cmds
            end
        end
        if seg ~= nil then
            count_changes(s)
            row(t, dt, s)
        elseif last_idle_row_t == nil or t - last_idle_row_t >= IDLE_ROW_S then
            last_idle_row_t = t
            row(t, dt, s)
        end
        flush(t)
    end)
    if not ok then log("frame error: " .. tostring(err)) end
end
