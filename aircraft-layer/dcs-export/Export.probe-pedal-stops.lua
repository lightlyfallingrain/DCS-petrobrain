--[[
PEDAL-STOPS / SPUU-52 PROBE -- not the production script. Testing aid.

Context: DCS World video game add-on (Mi-24P / Petrobrain). Nothing here controls real
hardware; "SPUU-52", "adjustable stops" and "channel B" are simulated Mi-24P cockpit systems.

Spec: aircraft-layer/research/2026-11-28-mi24p-pedal-stops.md, "Possible Approaches".

IDENTIFICATION (2026-11-28, user direction + body-layer/config/effectors-raw/mi-24p.toml):
the real aircraft's adjustable pedal-stops system is СПУУ-52 ("ПОДВИЖНЫЕ УПОРЫ",
control unit БУ-32) -- a separate device from the САУ/AFCS panel (SAU channel B is
the ALTITUDE channel, not the stops; an earlier draft of the research note above
got this wrong before the real device was found). Device 19 (`SPUU_52`) has four
elements:
  - SPUU-ON-OFF-PTR  cmd 3010 arg 270  "SPUU Power ON/OFF"        persistent switch
  - SPUU-OFF-PTR     cmd 3001 arg 275  "SPUU OFF" (acts like a switch, per the
                      raw dump's own curator note)                persistent switch
  - SPUU-KNOB-PTR    cmd 3003 arg 276  "SPUU Adjustment Knob"      continuous 0..1
  - SPUU-CONTROL-PTR cmds 3007/3006 arg 277 "P/NONE/T" switch      springloaded 3-pos
This probe drives all four directly (device 19) while the pilot holds full RIGHT
pedal, to settle which one (if any) moves the measured cap (stops on ~-0.569,
stops off ~-0.676, both from docs/acceptance/2026-11-28-sortie-feedback.md) and
what SPUU-KNOB-PTR/SPUU-CONTROL-PTR do, if anything, while SPUU is powered on.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the production
Export.lua afterwards. Petrovich does not run while this is deployed.
Log: Logs\aircraft_layer_probe_pedal_stops.log

FLIGHT: air start (warm unit), straight and level first; the actual test is a
hover or low-speed (<=50 km/h) full-right-pedal hold, same regime as the
2026-11-18 sortie that measured the stops cap. SAU H/K/T channels should be OFF
(not under test here); SPUU starts however the mission/`seat-pilot.md` leaves it
(power ON, per the current curated sequence).

CONTROL: pilot-seat ICS half-press (arg 738, same convention as
Export.probe-flight-axes.lua) ends the current step and performs the next step's
write, if any, then starts logging the new step. A full (radio) press jumps
straight to the DONE step, stopping anything running and restoring SPUU power ON.

STEPS, in order (hold full RIGHT pedal through every step):
  0  BASELINE        no write. SPUU however the mission left it. Half-press
                     once steady.
  1  POWER-OFF       set SPUU-ON-OFF-PTR (270) to 0 -- expected to reproduce
                     the wider, ~-0.676 cap if this is the mechanism.
  2  POWER-ON        set SPUU-ON-OFF-PTR (270) back to 1 -- expected to
                     restore the ~-0.569 cap.
  3  OFF-BUTTON-ON   set SPUU-OFF-PTR (275) to 1, power left ON.
  4  OFF-BUTTON-OFF  set SPUU-OFF-PTR (275) back to 0.
  5  KNOB-0.0        set SPUU-KNOB-PTR (276) to 0.0, SWITCH (277) at NONE.
  6  KNOB-0.5        set SPUU-KNOB-PTR (276) to 0.5.
  7  KNOB-1.0        set SPUU-KNOB-PTR (276) to 1.0.
  8  KNOB-RESET      set SPUU-KNOB-PTR (276) back to 0.0.
  9  SWITCH-P        pulse SPUU-CONTROL-PTR (277) toward "P" (cmd 3006, switchUp).
  10 SWITCH-NONE-A   pulse back toward centre (cmd 3007, switchDown) once.
  11 SWITCH-T        pulse SPUU-CONTROL-PTR (277) toward "T" (cmd 3007, switchDown).
  12 SWITCH-NONE-B   pulse back toward centre (cmd 3006, switchUp) once.
  13 DONE            set SPUU-ON-OFF-PTR (270) back to 1 (restore); no other write.

Each step's START writes once and logs an EDGE line with arg 1103 (pilot pedal)
and args 270/275/276/277 (every SPUU arg) immediately before and after. A "set"
step (persistent switch/axis) writes once and holds; a "pulse" step (the
springloaded P/NONE/T switch) presses then releases 150 ms later, since DCS
springs it back visually but the logical value needs an explicit release write
(same pattern as Export.probe-flight-axes.lua's B2 pedal writes). While a step
is running, one ROW is logged every 0.2 s: model time, step id, arg 1103, arg
270, arg 275, arg 276, arg 277, IAS (km/h), AGL (m) -- so the cap and any SPUU
arg movement can be read directly off the log without a reduction script.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_pedal_stops.log"

-- ---------------------------------------------------------------- constants
local DEV_SPUU = 19
local CMD_POWER = 3010
local CMD_OFF_BUTTON = 3001
local CMD_KNOB = 3003
local CMD_SWITCH_DOWN = 3007  -- SPUU_52 "switchDown" (toward T, by the cmd/name pairing in the raw dump)
local CMD_SWITCH_UP = 3006    -- SPUU_52 "switchUp" (toward P)

local ARG_PEDALS = 1103
local ARG_POWER = 270
local ARG_OFF_BUTTON = 275
local ARG_KNOB = 276
local ARG_SWITCH = 277

local ARG_PILOT_PTT = 738
local PRESS_MIN = 0.3
local FULL_PRESS_MIN = 0.75

local PULSE_RELEASE_S = 0.15
local ROW_PERIOD_S = 0.2
local FLUSH_S = 0.5

local STEPS = {
    { id = "BASELINE", say = "hold full RIGHT pedal, SPUU as the mission left it; half-press when steady" },
    { id = "POWER-OFF", kind = "set", cmd = CMD_POWER, value = 0.0, say = "SPUU power OFF (270=0); watch for the wider cap" },
    { id = "POWER-ON", kind = "set", cmd = CMD_POWER, value = 1.0, say = "SPUU power ON (270=1); watch for the cap returning" },
    { id = "OFF-BUTTON-ON", kind = "set", cmd = CMD_OFF_BUTTON, value = 1.0, say = "SPUU OFF-button pressed (275=1), power left ON" },
    { id = "OFF-BUTTON-OFF", kind = "set", cmd = CMD_OFF_BUTTON, value = 0.0, say = "SPUU OFF-button released (275=0)" },
    { id = "KNOB-0.0", kind = "set", cmd = CMD_KNOB, value = 0.0, say = "SPUU knob to 0.0 (276), switch at NONE" },
    { id = "KNOB-0.5", kind = "set", cmd = CMD_KNOB, value = 0.5, say = "SPUU knob to 0.5" },
    { id = "KNOB-1.0", kind = "set", cmd = CMD_KNOB, value = 1.0, say = "SPUU knob to 1.0" },
    { id = "KNOB-RESET", kind = "set", cmd = CMD_KNOB, value = 0.0, say = "SPUU knob back to 0.0" },
    { id = "SWITCH-P", kind = "pulse", cmd = CMD_SWITCH_UP, say = "SPUU P/NONE/T switch pulsed toward P" },
    { id = "SWITCH-NONE-A", kind = "pulse", cmd = CMD_SWITCH_DOWN, say = "SPUU switch pulsed back toward NONE" },
    { id = "SWITCH-T", kind = "pulse", cmd = CMD_SWITCH_DOWN, say = "SPUU P/NONE/T switch pulsed toward T" },
    { id = "SWITCH-NONE-B", kind = "pulse", cmd = CMD_SWITCH_UP, say = "SPUU switch pulsed back toward NONE" },
    { id = "DONE", kind = "set", cmd = CMD_POWER, value = 1.0, say = "restore SPUU power ON; all steps done; restore the production Export.lua" },
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

local function fmt(v)
    if type(v) ~= "number" then return "nil" end
    return string.format("%.5g", v)
end

local function read_arg(n)
    local ok, v = pcall(function() return GetDevice(0):get_argument_value(n) end)
    if ok and type(v) == "number" then return v end
    return nil
end

local function clickable(cmd, value)
    local ok, err = pcall(function()
        GetDevice(DEV_SPUU):performClickableAction(cmd, value)
    end)
    log(string.format("  write performClickableAction(dev=%d, cmd=%d, %s): ok=%s err=%s",
        DEV_SPUU, cmd, fmt(value), tostring(ok), tostring(err)))
end

local function snapshot()
    return string.format("a1103=%s a270=%s a275=%s a276=%s a277=%s ias_kmh=%s agl=%s",
        fmt(read_arg(ARG_PEDALS)), fmt(read_arg(ARG_POWER)), fmt(read_arg(ARG_OFF_BUTTON)),
        fmt(read_arg(ARG_KNOB)), fmt(read_arg(ARG_SWITCH)),
        fmt((call(LoGetIndicatedAirSpeed) or 0) * 3.6), fmt(call(LoGetAltitudeAboveGroundLevel)))
end

-- ---------------------------------------------------------------- state
local started = false
local next_index = 1
local step = nil      -- {def=, t0=}
local last_row_t = nil
local trigger = { peak = 0.0, pressed = false }
local pending_release = nil   -- {t=, cmd=} for a "pulse" step's release write

local function start_step(t)
    local def = STEPS[next_index]
    if def == nil then
        log(string.format("t=%.3f all steps done; restore the production Export.lua", t))
        step = nil
        return
    end
    next_index = next_index + 1
    step = { def = def, t0 = t }
    log(string.format("t=%.3f START %s (%s)", t, def.id, def.say))
    if def.kind == "set" then
        log("  BEFORE " .. snapshot())
        clickable(def.cmd, def.value)
    elseif def.kind == "pulse" then
        log("  BEFORE " .. snapshot())
        clickable(def.cmd, 1)
        pending_release = { t = t + PULSE_RELEASE_S, cmd = def.cmd }
    end
    last_row_t = nil
end

local function end_step(t)
    if step == nil then return end
    log(string.format("t=%.3f END %s AFTER %s", t, step.def.id, snapshot()))
    step = nil
end

local function poll_trigger(t)
    local v = read_arg(ARG_PILOT_PTT)
    if v == nil then return end
    if v >= PRESS_MIN then
        trigger.pressed = true
        if v > trigger.peak then trigger.peak = v end
        return
    end
    if not trigger.pressed then return end
    local peak = trigger.peak
    trigger.pressed, trigger.peak = false, 0.0
    if peak >= FULL_PRESS_MIN then
        -- Full press: jump straight to DONE (restores SPUU power ON).
        end_step(t)
        next_index = #STEPS
        start_step(t)
        return
    end
    -- Half-press: end whatever is running, then start the next step.
    end_step(t)
    start_step(t)
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("PEDAL-STOPS / SPUU-52 PROBE " .. os.date("%Y-%m-%d %H:%M:%S"))
    log("  video game add-on (DCS World, Mi-24P) -- no real hardware involved")
    log(string.format("  device=%d power_arg=%d off_button_arg=%d knob_arg=%d switch_arg=%d",
        DEV_SPUU, ARG_POWER, ARG_OFF_BUTTON, ARG_KNOB, ARG_SWITCH))
    log("  pilot ICS half-press: end current step, start next. Full press: jump to DONE.")
    log("  ROW t step a1103 a270 a275 a276 a277 ias_kmh agl")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("pedal-stops probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportBeforeNextFrame()
    if not started then return end
    local ok, err = pcall(function()
        local t = LoGetModelTime()
        if type(t) ~= "number" then return end
        if step == nil and next_index == 1 then
            start_step(t)
        end
        if pending_release ~= nil and t >= pending_release.t then
            clickable(pending_release.cmd, 0)
            pending_release = nil
        end
        poll_trigger(t)
        if step ~= nil and (last_row_t == nil or t - last_row_t >= ROW_PERIOD_S) then
            last_row_t = t
            log(string.format("ROW %.3f %s %s", t, step.def.id, snapshot()))
        end
        flush(t)
    end)
    if not ok then log("frame error: " .. tostring(err)) end
end
