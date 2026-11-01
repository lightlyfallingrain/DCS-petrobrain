--[[
CONTROL-AXIS HOLD PROBE (BL-16, parked-controls go/no-go) -- not the
production script. Testing aid.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Log: Logs\aircraft_layer_probe_axis_hold.log

WHAT IT DOES (user spec, 2026-11-01)
  ICS (intercom / VOIP) half-press of a stick trigger toggles the hold:
    pilot trigger    (arg 738, 0.5 = ICS) -> reads pilot control args
    operator trigger (arg 856, 0.5 = ICS) -> reads operator control args
  On start: read cyclic pitch/roll, pedals, collective from that seat's
  cockpit args, save them, and write them back to the SAME seat's DCS
  control args every frame (set_argument_value), with an alternating +-0.001
  so each frame's value differs from the last (the 9K113 override only won
  with a changing value). Same trigger again stops the writes.

  User, 2026-11-01: "It has to be the DCS control axises, not joystick
  axises" -- so no LoSetCommand 2001-2004 (the joystick input commands).

  Full press (radio, 1.0) never toggles: a full press transits 0.5 for
  19-32 ms, so the toggle fires on RELEASE and only if the press peaked
  below FULL_PRESS_MIN.

KNOWN LIMITS, read before flying
  - Args 1100-1103 / 1110-1113 are created as CreateSimpleConnectedGauge
    (mainpanel_init.lua), i.e. -1..1 cockpit draw values. Whether writing
    them reaches the flight model or only moves the animation is exactly
    what this probe answers: watch the aircraft, and the log's pitch/bank
    and the other seat's args. Only one seat is held at a time; starting
    the other re-reads and replaces.
  - Writes come from LuaExportBeforeNextFrame, ED's documented injection
    point (research/2026-10-31-mi24p-park-controls-ai-pilot.md section 6).

LOG
  START/STOP lines with the saved values; while holding, a row every
  ROW_PERIOD_S with both seats' args, the values written, pitch/bank.
  A 5 s heartbeat of both trigger args proves the read is alive.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_axis_hold.log"

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

-- ---------------------------------------------------------------- constants
local ARG_PILOT_PTT = 738
local ARG_OPERATOR_PTT = 856

local PRESS_MIN = 0.3         -- above this the trigger counts as pressed
local FULL_PRESS_MIN = 0.75   -- a press peaking at or above this was radio, not ICS

-- cockpit draw args per seat: pitch, roll, collective, pedals
local SEAT_ARGS = {
    pilot = { pitch = 1100, roll = 1101, collective = 1102, pedals = 1103 },
    operator = { pitch = 1110, roll = 1111, collective = 1112, pedals = 1113 },
}

local DITHER = 0.001
local ROW_PERIOD_S = 0.25
local HEARTBEAT_S = 5.0

-- ---------------------------------------------------------------- state
local started = false
local triggers = {
    pilot = { arg = ARG_PILOT_PTT, peak = 0.0, pressed = false },
    operator = { arg = ARG_OPERATOR_PTT, peak = 0.0, pressed = false },
}
local hold = nil              -- {seat=, pitch=, roll=, collective=, pedals=, t0=}
local dither_sign = 1.0
local last_written = nil
local last_row_t = nil
local last_heartbeat_t = nil

local function read_arg(n)
    local ok, v = pcall(function() return GetDevice(0):get_argument_value(n) end)
    if ok and type(v) == "number" then return v end
    return nil
end

local function clamp(v)
    if v > 1.0 then return 1.0 end
    if v < -1.0 then return -1.0 end
    return v
end

local function fmt(v)
    if type(v) ~= "number" then return "  nil " end
    return string.format("%+.3f", v)
end

local function seat_row(seat)
    local a = SEAT_ARGS[seat]
    return string.format("%s p=%s r=%s c=%s y=%s", seat,
        fmt(read_arg(a.pitch)), fmt(read_arg(a.roll)),
        fmt(read_arg(a.collective)), fmt(read_arg(a.pedals)))
end

local function attitude()
    local ok, p, b = pcall(LoGetADIPitchBankYaw)
    if ok and type(p) == "number" and type(b) == "number" then
        return string.format("pitch=%+.1f bank=%+.1f", math.deg(p), math.deg(b))
    end
    return "pitch=nil bank=nil"
end

-- ---------------------------------------------------------------- hold
local function start_hold(seat, t)
    local a = SEAT_ARGS[seat]
    local v = {
        pitch = read_arg(a.pitch), roll = read_arg(a.roll),
        collective = read_arg(a.collective), pedals = read_arg(a.pedals),
    }
    if v.pitch == nil or v.roll == nil or v.collective == nil or v.pedals == nil then
        log(string.format("t=%8.3f START %s refused: an arg read failed (%s)", t, seat, seat_row(seat)))
        return
    end
    hold = { seat = seat, pitch = v.pitch, roll = v.roll, collective = v.collective,
             pedals = v.pedals, t0 = t }
    last_row_t = nil
    log(string.format("t=%8.3f START %s saved p=%s r=%s c=%s y=%s | %s | %s | %s",
        t, seat, fmt(v.pitch), fmt(v.roll), fmt(v.collective), fmt(v.pedals),
        seat_row("pilot"), seat_row("operator"), attitude()))
end

local function stop_hold(t, why)
    if hold == nil then return end
    log(string.format("t=%8.3f STOP %s (%s) after %.1f s | %s | %s | %s",
        t, hold.seat, why, t - hold.t0, seat_row("pilot"), seat_row("operator"), attitude()))
    hold = nil
    last_written = nil
end

local function write_hold()
    dither_sign = -dither_sign
    local d = DITHER * dither_sign
    local a = SEAT_ARGS[hold.seat]
    local w = {
        pitch = clamp(hold.pitch + d),
        roll = clamp(hold.roll + d),
        rudder = clamp(hold.pedals + d),
        collective = clamp(hold.collective + d),
    }
    pcall(function()
        local dev = GetDevice(0)
        dev:set_argument_value(a.pitch, w.pitch)
        dev:set_argument_value(a.roll, w.roll)
        dev:set_argument_value(a.collective, w.collective)
        dev:set_argument_value(a.pedals, w.rudder)
    end)
    last_written = w
end

-- ---------------------------------------------------------------- trigger
-- Toggle on release of a press that peaked in the ICS band.
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
        log(string.format("t=%8.3f %s trigger full press (peak %.2f), ignored", t, seat, peak))
        return
    end
    if hold ~= nil and hold.seat == seat then
        stop_hold(t, "ICS " .. seat)
    else
        if hold ~= nil then stop_hold(t, "replaced by " .. seat) end
        start_hold(seat, t)
    end
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("CONTROL-AXIS HOLD PROBE -- ICS half-press toggles hold (pilot 738 / operator 856)")
    log("  writes the held seat's control args 1100-1103 / 1110-1113 every frame from BeforeNextFrame, dither +-0.001")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("axis hold probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportBeforeNextFrame()
    if not started then return end
    local ok, err = pcall(function()
        local t = LoGetModelTime()
        if type(t) ~= "number" then return end

        poll_trigger("pilot", t)
        poll_trigger("operator", t)

        if hold ~= nil then
            write_hold()
            if last_row_t == nil or (t - last_row_t) >= ROW_PERIOD_S then
                last_row_t = t
                local w = last_written
                log(string.format("t=%8.3f HOLD %s wrote p=%s r=%s c=%s y=%s | %s | %s | %s",
                    t, hold.seat, fmt(w.pitch), fmt(w.roll), fmt(w.collective), fmt(w.rudder),
                    seat_row("pilot"), seat_row("operator"), attitude()))
            end
        end

        if last_heartbeat_t == nil or (t - last_heartbeat_t) >= HEARTBEAT_S then
            last_heartbeat_t = t
            log(string.format("t=%8.3f alive ptt pilot=%s operator=%s hold=%s",
                t, fmt(read_arg(ARG_PILOT_PTT)), fmt(read_arg(ARG_OPERATOR_PTT)),
                hold and hold.seat or "off"))
        end
    end)
    if not ok then log("frame error: " .. tostring(err)) end
end
