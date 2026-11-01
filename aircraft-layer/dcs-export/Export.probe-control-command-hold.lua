--[[
CONTROL-COMMAND HOLD PROBE (BL-16, parked-controls go/no-go, v2) -- not the
production script. Testing aid.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Log: Logs\aircraft_layer_probe_command_hold.log

WHY v2
  v1 (Export.probe-control-axis-hold.lua) wrote cockpit args 1100-1103 /
  1110-1113. Flown 2026-11-01: the args read back as written but the aircraft
  followed the real stick -- those args are animation only. The user then
  confirmed "DCS control axes" means DCS's control functions: LoSetCommand
  2001 pitch / 2002 roll / 2003 rudder / 2004 collective (iCommandPlanePitch
  etc., the same actions the "Flight Control Cyclic ..." bindings drive).

WHAT IT DOES
  ICS (intercom / VOIP) half-press of a stick trigger toggles the hold:
    pilot trigger    (arg 738, 0.5 = ICS) -> saves the pilot's control args
    operator trigger (arg 856, 0.5 = ICS) -> saves the operator's control args
  On start: read cyclic pitch/roll, pedals, collective from that seat's
  cockpit args (these DO track the real controls), save them, and send them
  every frame as LoSetCommand 2001-2004 with an alternating +-0.001 so each
  frame's value differs from the last. Same trigger again stops sending.

  LoSetCommand is global, not per seat: both triggers drive the same flight
  controls, only the saved source differs. In v1's flight the operator args
  read 0.000 throughout while the user sat in the pilot seat, so an operator
  hold from the pilot seat would command centred controls.

  Full press (radio, 1.0) never toggles: a full press transits 0.5 for
  19-32 ms, so the toggle fires on RELEASE and only if the press peaked
  below FULL_PRESS_MIN.

KNOWN LIMITS, read before flying
  - The arg -> command mapping is unverified. SIGN below is a guess (ED's
    comment says 2004 is inverted). If the controls jump at START the sign or
    scale is wrong: the log's readback args show by how much and which way.
  - Collective is OFF (HOLD_COLLECTIVE): arg 1102 sat at +0.108 all v1 flight,
    so its scale (0..1 or -1..1) is unknown and a wrong guess is a big
    collective step. Turn it on once pitch/roll/pedals behave.
  - Mi-24 trim: the stick args may include the trim offset while 2001/2002
    may be raw stick input. A consistent offset at START would show that.
  - Writes come from LuaExportBeforeNextFrame, ED's documented injection
    point (research/2026-10-31-mi24p-park-controls-ai-pilot.md section 6).

LOG
  START/STOP lines with the saved values; while holding, a row every
  ROW_PERIOD_S with the commands sent, both seats' args, pitch/bank.
  A 5 s heartbeat of both trigger args proves the read is alive.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_command_hold.log"

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

-- cockpit draw args per seat: pitch, roll, collective, pedals (read only)
local SEAT_ARGS = {
    pilot = { pitch = 1100, roll = 1101, collective = 1102, pedals = 1103 },
    operator = { pitch = 1110, roll = 1111, collective = 1112, pedals = 1113 },
}

-- DCS control functions (Scripts/Export.lua, iCommandPlane*)
local CMD_PITCH = 2001
local CMD_ROLL = 2002
local CMD_RUDDER = 2003
local CMD_COLLECTIVE = 2004

-- command = SIGN * arg; unverified guesses, flip from the log if wrong
local SIGN = { pitch = 1.0, roll = 1.0, rudder = 1.0, collective = -1.0 }
local HOLD_COLLECTIVE = false

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
local last_sent = nil
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
    log(string.format("t=%8.3f START %s saved p=%s r=%s c=%s y=%s (collective %s) | %s | %s | %s",
        t, seat, fmt(v.pitch), fmt(v.roll), fmt(v.collective), fmt(v.pedals),
        HOLD_COLLECTIVE and "held" or "not held",
        seat_row("pilot"), seat_row("operator"), attitude()))
end

local function stop_hold(t, why)
    if hold == nil then return end
    log(string.format("t=%8.3f STOP %s (%s) after %.1f s | %s | %s | %s",
        t, hold.seat, why, t - hold.t0, seat_row("pilot"), seat_row("operator"), attitude()))
    hold = nil
    last_sent = nil
end

local function send_hold()
    dither_sign = -dither_sign
    local d = DITHER * dither_sign
    local s = {
        pitch = clamp(SIGN.pitch * hold.pitch + d),
        roll = clamp(SIGN.roll * hold.roll + d),
        rudder = clamp(SIGN.rudder * hold.pedals + d),
        collective = nil,
    }
    if HOLD_COLLECTIVE then
        s.collective = clamp(SIGN.collective * hold.collective + d)
    end
    pcall(function()
        LoSetCommand(CMD_PITCH, s.pitch)
        LoSetCommand(CMD_ROLL, s.roll)
        LoSetCommand(CMD_RUDDER, s.rudder)
        if s.collective ~= nil then LoSetCommand(CMD_COLLECTIVE, s.collective) end
    end)
    last_sent = s
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
    log("CONTROL-COMMAND HOLD PROBE -- ICS half-press toggles hold (pilot 738 / operator 856)")
    log(string.format("  sends LoSetCommand 2001-2003%s every frame from BeforeNextFrame, dither +-0.001",
        HOLD_COLLECTIVE and "+2004" or " (collective off)"))
    log(string.format("  SIGN pitch=%+.0f roll=%+.0f rudder=%+.0f collective=%+.0f",
        SIGN.pitch, SIGN.roll, SIGN.rudder, SIGN.collective))
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("command hold probe: stopped.")
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
            send_hold()
            if last_row_t == nil or (t - last_row_t) >= ROW_PERIOD_S then
                last_row_t = t
                local s = last_sent
                log(string.format("t=%8.3f HOLD %s sent p=%s r=%s c=%s y=%s | %s | %s | %s",
                    t, hold.seat, fmt(s.pitch), fmt(s.roll), fmt(s.collective), fmt(s.rudder),
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
