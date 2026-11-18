--[[
FLIGHT-AXES PROBE, SORTIE 1 (BL-16 mode 1, rows M0-A..M0-D and M0-J) -- not
the production script. Testing aid.

Spec: plans/flight-control/plan.md, "Revised 2026-11-18 -- mode 1", stage M0,
including "M0 changes, amended 2026-11-18 for U5 and the seat rule".
Scaffold: Export.probe-control-command-hold.lua (probe v2, 2026-11-01).

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Petrobrain does not run while this is
deployed. Log: Logs\aircraft_layer_probe_flight_axes.log

FLIGHT: air start, straight and level, ~150 km/h, ~200 m AGL, flat ground.

CONTROL: an ICS half-press (pilot trigger arg 738 or operator trigger arg
856, 0.5) steps through segments. A full (radio) press SKIPS to the next
phase (A -> B -> C -> D -> Bo -> Co -> Do -> J), stopping anything running;
the next half-press then starts that phase's first segment. Both act on
release, so a full press never also counts as a half-press.
  - Idle -> a half-press starts the next segment.
  - A read segment -> a half-press ends it.
  - A write segment runs its own schedule and ends itself; a half-press
    during one STOPS WRITING at once (abort).
  The seat whose trigger was pressed is the seat whose control args are
  captured for writing.

SEGMENTS, in order:
  Pilot seat, controls unparked:
    A1 level 60 s | A2 20 deg bank turns both ways | A3 5 m/s climb and
    descend 100 m | A4 150 -> 220 km/h and back   (read; note HSI heading)
    B1 sweep pedals                                 (read)
    B2 feet off: 2003 = captured, +-0.05, +-0.10, 3 s each   (write)
    C1 sweep collective                             (read)
    C2 2004 = captured, then +0.02 / -0.02, 2 s each  (write; auto-abort)
    D1 hold all enabled axes 30 s while the pilot stirs, dither 1e-3 (write)
    D2 same, dither 1e-4                            (write)
  Operator seat, copilot controls UNPARKED (amendment change 1):
    B1o B2o C1o C2o D1o D2o -- the same, from the front seat
  Operator seat, park and unpark while writing (amendment change 2, M0-J):
    J1 hold; the user parks (Request Aircraft Control) -> writing stops on
       the parked_active rising edge; ~20 s later the user unparks -> on
       the falling edge the probe captures the PILOT set 1100-1103 in that
       frame and holds it 10 s
    J2 the same, capturing the SUM of both arg sets at the edge
    J3 hold; park; then swap operator -> pilot while parked -> on the
       falling edge capture as J1 and hold 10 s

Each pass's B2 / C2 decide whether that pass's D also holds pedals /
collective (pedals: arg within PEDAL_HOLD_TOL of each command; collective:
C2 finished without an abort). The operator pass's results carry into J.

C2 AUTO-ABORT: |VS| > C2_ABORT_VS; the arg jumps > C2_JUMP_TOL from captured
in the first 0.5 s; or on the first step the arg moves against the command.

parked_active is computed exactly as production does (Petrobrain/
ai_pilot_wheel.lua): arg 852 >= 0.9 AND the camera seat is the operator's.
Every frame is logged from 1 s before to 3 s after any change in
parked_active or the camera seat, whatever is running (amendment change 4).

LOG: ROW lines (columns in ROW_COLUMNS), one per frame during a segment or
an edge window, one per 0.1 s otherwise; EDGE lines; a getter dump at
start; a per-segment SUMMARY of how often each value changed per second.
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
local AI_PILOT_PARK_THRESHOLD = 0.9   -- production's value

local CMD = { pitch = 2001, roll = 2002, pedals = 2003, collective = 2004 }
-- command = SIGN * arg. pitch/roll proven +1 (probe v2); pedals proven -1
-- (flight 3 B2, 2026-11-18: 2003 = +0.05 held arg 1103 at -0.050 exactly);
-- collective -1 from ED's comment, C2 tests it.
local SIGN = { pitch = 1.0, roll = 1.0, pedals = -1.0, collective = -1.0 }

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
local J_DITHER = 1e-3
local J_WAIT_S = 120.0       -- give up on a J row if no park/unpark by then
local J_HOLD_AFTER_S = 10.0  -- hold this long after the unpark capture

local IDLE_ROW_S = 0.1
local EDGE_PRE_S = 1.0
local EDGE_POST_S = 3.0
local FLUSH_S = 0.5

-- Copied from Petrobrain/ai_pilot_wheel.lua (do not re-derive).
local SEAT_BOUNDARY_FWD_M = 4.1
local SEAT_CAMERA_MIN_FWD_M = 2.0
local SEAT_CAMERA_MAX_FWD_M = 7.0
local SEAT_CAMERA_MAX_OFFAXIS_M = 1.5

local SEGMENTS = {
    { id = "A1", kind = "read", say = "pilot seat: 60 s straight and level; note HSI heading" },
    { id = "A2", kind = "read", say = "20 deg bank turns both ways; note HSI heading" },
    { id = "A3", kind = "read", say = "5 m/s climb 100 m, then descend 100 m" },
    { id = "A4", kind = "read", say = "accelerate 150 -> 220 km/h and back; note HSI heading" },
    { id = "B1", kind = "read", pass_start = true, say = "sweep pedals slowly full left -> full right -> centre" },
    { id = "B2", kind = "pedals", say = "feet OFF the pedals; probe writes 2003" },
    { id = "C1", kind = "read", say = "sweep collective slowly low -> high -> back" },
    { id = "C2", kind = "collective", say = "hand OFF the collective; probe writes 2004" },
    { id = "D1", kind = "hold", dither = DITHER_D1, say = "stir stick 10 s, pedals 10 s, collective 10 s" },
    { id = "D2", kind = "hold", dither = DITHER_D2, say = "same again, smaller dither" },
    { id = "B1o", kind = "read", pass_start = true, say = "OPERATOR seat, copilot controls unparked: sweep pedals" },
    { id = "B2o", kind = "pedals", say = "feet OFF the pedals; probe writes 2003" },
    { id = "C1o", kind = "read", say = "sweep collective slowly low -> high -> back" },
    { id = "C2o", kind = "collective", say = "hand OFF the collective; probe writes 2004" },
    { id = "D1o", kind = "hold", dither = DITHER_D1, say = "stir stick 10 s, pedals 10 s, collective 10 s" },
    { id = "D2o", kind = "hold", dither = DITHER_D2, say = "same again, smaller dither" },
    { id = "J1", kind = "park", capture = "pilot", say = "operator seat: park, ~20 s, unpark" },
    { id = "J2", kind = "park", capture = "sum", say = "operator seat: park, ~20 s, unpark" },
    { id = "J3", kind = "park", capture = "pilot", say = "operator seat: park, then swap to the PILOT seat" },
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

-- Verbatim from Petrobrain/ai_pilot_wheel.lua.
local function ai_pilot_seat_from_camera(cam_p, own_p, heading_rad, pitch_rad)
    if type(cam_p) ~= "table" or type(own_p) ~= "table" or type(heading_rad) ~= "number" then
        return nil, nil
    end
    if type(cam_p.x) ~= "number" or type(cam_p.y) ~= "number" or type(cam_p.z) ~= "number"
        or type(own_p.x) ~= "number" or type(own_p.y) ~= "number" or type(own_p.z) ~= "number" then
        return nil, nil
    end
    if type(pitch_rad) ~= "number" then
        pitch_rad = 0.0
    end
    local dx, dy, dz = cam_p.x - own_p.x, cam_p.y - own_p.y, cam_p.z - own_p.z
    local cp = math.cos(pitch_rad)
    local fwd = dx * cp * math.cos(heading_rad) + dy * math.sin(pitch_rad) + dz * cp * math.sin(heading_rad)
    local offaxis_sq = dx * dx + dy * dy + dz * dz - fwd * fwd
    if fwd < SEAT_CAMERA_MIN_FWD_M or fwd > SEAT_CAMERA_MAX_FWD_M
        or offaxis_sq > SEAT_CAMERA_MAX_OFFAXIS_M * SEAT_CAMERA_MAX_OFFAXIS_M then
        return nil, fwd
    end
    if fwd >= SEAT_BOUNDARY_FWD_M then
        return "operator", fwd
    end
    return "pilot", fwd
end

local player_seat = nil
local cam_fwd_m = nil
local parked_active = false

local function update_seat_and_park()
    local cam = call(LoGetCameraPosition)
    local sd = call(LoGetSelfData)
    local cam_p = type(cam) == "table" and cam.p or nil
    local own_p, heading = nil, nil
    if type(sd) == "table" then
        local pos = sd.Position
        own_p = type(pos) == "table" and (pos.p or pos) or nil
        heading = sd.Heading
    end
    local seat, fwd = ai_pilot_seat_from_camera(cam_p, own_p, heading, call(LoGetADIPitchBankYaw))
    cam_fwd_m = fwd
    if seat ~= nil then player_seat = seat end
    local stick_park = read_arg(ARG_STICK_PARK)
    parked_active = player_seat == "operator" and stick_park ~= nil
        and stick_park >= AI_PILOT_PARK_THRESHOLD
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
    if type(LoGetADIPitchBankYaw) == "function" then
        local ok, p, b, y = pcall(LoGetADIPitchBankYaw)
        if ok then s.adi_pitch, s.adi_bank, s.adi_yaw = p, b, y end
    end
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
local prev_parked, prev_seat = nil, nil
local edge_until_t = nil
local pre_rows = {}   -- {t=, line=} for the last EDGE_PRE_S, idle only

local function header()
    local cols = { "t", "dt", "seg", "seat", "parked", "cmd_p", "cmd_r", "cmd_y", "cmd_c" }
    for _, n in ipairs(FIELD_NAMES) do cols[#cols + 1] = n end
    log("ROW_COLUMNS " .. table.concat(cols, " "))
end

local function format_row(t, dt, s)
    local sent = seg and seg.sent or {}
    local out = {
        string.format("%.3f", t), fmt(dt), seg and seg.def.id or "idle", player_seat or "nil",
        parked_active and "1" or "0",
        fmt(sent.pitch), fmt(sent.roll), fmt(sent.pedals), fmt(sent.collective),
    }
    for _, n in ipairs(FIELD_NAMES) do out[#out + 1] = fmt(s[n]) end
    return "ROW " .. table.concat(out, " ")
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

local function capture_from(seat_name)
    local a = SEAT_ARGS[seat_name]
    return {
        pitch = read_arg(a.pitch), roll = read_arg(a.roll),
        pedals = read_arg(a.pedals), collective = read_arg(a.collective),
    }
end

local function capture_sum()
    local p, o = capture_from("pilot"), capture_from("operator")
    local out = {}
    for _, axis in ipairs({ "pitch", "roll", "pedals", "collective" }) do
        if p[axis] ~= nil and o[axis] ~= nil then out[axis] = p[axis] + o[axis] end
    end
    return out
end

local function captured_text(c)
    return string.format("p=%s r=%s y=%s c=%s", fmt(c.pitch), fmt(c.roll), fmt(c.pedals), fmt(c.collective))
end

-- ---------------------------------------------------------------- segments
local function end_segment(t, why)
    if seg == nil then return end
    summary(t)
    local kind = seg.def.kind
    if kind == "pedals" and why == "done" then
        hold_pedals = b2_worst <= PEDAL_HOLD_TOL
        log(string.format("%s RESULT worst |arg - command| = %.4f -> D holds pedals: %s",
            seg.def.id, b2_worst, tostring(hold_pedals)))
    elseif kind == "collective" then
        hold_collective = why == "done"
        log(string.format("%s RESULT -> D holds collective: %s", seg.def.id, tostring(hold_collective)))
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
    if def.pass_start then hold_pedals, hold_collective = false, false end
    seg = { def = def, seat = seat, t0 = t, sent = {}, captured = capture_from(seat), phase = "holding" }
    stats = { changes = {}, prev = {}, frames = 0 }
    if def.kind == "pedals" then b2_worst = 0.0 end
    log(string.format("t=%.3f START %s (%s) trigger_seat=%s camera_seat=%s parked=%s captured %s | holds pedals=%s collective=%s",
        t, def.id, def.say, seat, player_seat or "nil", tostring(parked_active),
        captured_text(seg.captured), tostring(hold_pedals), tostring(hold_collective)))
    if player_seat ~= nil and player_seat ~= seat then
        log("  WARNING: trigger seat and camera seat differ")
    end
    if def.kind ~= "read" then
        for _, axis in ipairs({ "pitch", "roll", "pedals", "collective" }) do
            if seg.captured[axis] == nil then
                log("  capture failed for " .. axis .. "; segment not written")
                end_segment(t, "capture failed")
                return
            end
        end
    end
end

local function hold_cmds(c, d)
    local out = {
        pitch = clamp(SIGN.pitch * c.pitch + d),
        roll = clamp(SIGN.roll * c.roll + d),
    }
    if hold_pedals and c.pedals ~= nil then out.pedals = clamp(SIGN.pedals * c.pedals + d) end
    if hold_collective and c.collective ~= nil then out.collective = clamp(SIGN.collective * c.collective + d) end
    return out
end

-- Returns the commands to send this frame (axis -> value; {} = send
-- nothing), nil when the schedule has finished, or false plus a reason to
-- abort.
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
        if arg ~= nil and seg.c2_checked == nil and el >= C2_STEPS[1][2] + C2_SIGN_CHECK_S then
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
        return hold_cmds(c, def.dither * dither_sign)
    elseif def.kind == "park" then
        -- holding -> (parked_active rises) parked -> (falls) taken -> done
        if seg.phase == "holding" then
            if parked_active then
                seg.phase, seg.phase_t = "parked", t
                log(string.format("t=%.3f %s PARK seen: writing stopped", t, def.id))
                return {}
            end
            if el >= J_WAIT_S then return false, "no park within " .. J_WAIT_S .. " s" end
        elseif seg.phase == "parked" then
            if not parked_active then
                seg.captured = def.capture == "sum" and capture_sum() or capture_from("pilot")
                seg.phase, seg.phase_t = "taken", t
                log(string.format("t=%.3f %s UNPARK seen (camera_seat=%s): captured %s from %s, holding",
                    t, def.id, player_seat or "nil", captured_text(seg.captured), def.capture))
                if seg.captured.pitch == nil or seg.captured.roll == nil then
                    return false, "unpark capture failed"
                end
            elseif t - seg.phase_t >= J_WAIT_S then
                return false, "no unpark within " .. J_WAIT_S .. " s"
            else
                return {}
            end
        elseif seg.phase == "taken" and t - seg.phase_t >= J_HOLD_AFTER_S then
            return nil
        end
        dither_sign = -dither_sign
        return hold_cmds(seg.captured, J_DITHER * dither_sign)
    end
    return {}
end

local function send(cmds)
    pcall(function()
        for axis, v in pairs(cmds) do LoSetCommand(CMD[axis], v) end
    end)
end

-- ---------------------------------------------------------------- trigger
-- A phase is a segment id without its digits: A1..A4 -> "A", B1o/B2o -> "Bo".
local function phase_of(def)
    return (def.id:gsub("%d", ""))
end

-- Full (radio) press: stop any running segment (writes stop at once) and
-- point at the first segment of the next phase. Nothing starts until the
-- next ICS half-press. (User, 2026-11-18: "radio trigger (full press) moves
-- to next probe phase, e.g. A > B".)
local function skip_phase(t, seat, peak)
    local from = seg and seg.def or SEGMENTS[next_index]
    if seg ~= nil then end_segment(t, "skipped by radio press") end
    if from == nil then
        log(string.format("t=%.3f %s radio press (peak %.2f): no segments left", t, seat, peak))
        return
    end
    local phase = phase_of(from)
    local i = next_index
    while SEGMENTS[i] ~= nil and phase_of(SEGMENTS[i]) == phase do i = i + 1 end
    next_index = i
    local nxt = SEGMENTS[next_index]
    log(string.format("t=%.3f %s radio press (peak %.2f): SKIP phase %s -> next is %s",
        t, seat, peak, phase, nxt and nxt.id or "(none, all done)"))
end

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
    -- Both presses act on release, so the ICS step a full press passes
    -- through on its way down never counts as a half-press.
    if peak >= FULL_PRESS_MIN then
        skip_phase(t, seat, peak)
        return
    end
    if seg ~= nil then
        end_segment(t, seg.def.kind == "read" and "done" or "ABORTED by ICS press")
    else
        start_segment(t, seat)
    end
end

-- ---------------------------------------------------------------- edges
local function watch_edges(t)
    if prev_parked ~= nil and (parked_active ~= prev_parked or player_seat ~= prev_seat) then
        log(string.format("t=%.3f EDGE parked %s -> %s, camera_seat %s -> %s (cam_fwd_m=%s)",
            t, tostring(prev_parked), tostring(parked_active), prev_seat or "nil",
            player_seat or "nil", fmt(cam_fwd_m)))
        for _, r in ipairs(pre_rows) do log(r.line .. " PRE") end
        pre_rows = {}
        edge_until_t = t + EDGE_POST_S
    end
    prev_parked, prev_seat = parked_active, player_seat
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("FLIGHT-AXES PROBE, SORTIE 1 (M0-A..D, both seats, M0-J) " .. os.date("%Y-%m-%d %H:%M:%S"))
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
        update_seat_and_park()
        watch_edges(t)
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
        local line = format_row(t, dt, s)
        if seg ~= nil then
            count_changes(s)
            log(line)
        elseif edge_until_t ~= nil and t <= edge_until_t then
            log(line)
        else
            pre_rows[#pre_rows + 1] = { t = t, line = line }
            while #pre_rows > 0 and t - pre_rows[1].t > EDGE_PRE_S do table.remove(pre_rows, 1) end
            if last_idle_row_t == nil or t - last_idle_row_t >= IDLE_ROW_S then
                last_idle_row_t = t
                log(line)
            end
        end
        flush(t)
    end)
    if not ok then log("frame error: " .. tostring(err)) end
end
