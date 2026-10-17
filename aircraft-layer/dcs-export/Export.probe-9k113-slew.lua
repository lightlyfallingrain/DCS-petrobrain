--[[
PETROVICH 9K113 SLEW PROBE -- not the production script.

Self-contained; does NOT need the collector. Appends to
Logs\aircraft_layer_probe_9k113_slew.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`; afterwards re-copy the production
`aircraft-layer/dcs-export/Export.lua` from the repository (do not restore a
.backup -- see aircraft-layer/WORKFLOW.md).

Card: docs/acceptance/2026-10-17-9k113-slew-probe.md
Follows: docs/acceptance/2026-10-17-9k113-effectors-probe-results.md
Feeds: BL-B66 (body-layer/ROADMAP/BL-B66.md), Decision 1 of
       plans/9k113-effectors/plan.md.

THIS SCRIPT NEVER WRITES A SWITCH. User direction, 2026-10-17, after the first
probe answered the switch question and contaminated everything else:

  "Driving the sight: needs a separate run WITH NO SWITCH FLIPS. I will setup it
   so that OBSERV is ON and can be used id it is possible via code. Set test to
   happen at T+60s"

So there is no performClickableAction call anywhere below -- only reads, and
SetCommand against the sight's own axes. You set the aircraft up by hand.

WHAT IS ALREADY KNOWN
  * performClickableAction moves switches on devices 6 and 7 from the pilot's
    seat -- ANSWERED by the 2026-10-17 effector probe, several switches moved.
  * The AI axis is a POSITION target, measured 2026-09-11 at five points:
    GetDevice(7):SetCommand(3061, az_deg/60) settles <0.25 s, arg_874 = v*0.44.
  * The player axis (3025 up/down, 3026 left/right) accumulates like a held slew
    input. Whether it responds AT ALL outside the sight's own viewport is the
    unresolved gate.
  * Elevation (876/3060) has a piecewise gauge; its degrees-per-unit has never
    been measured, which is why elevation gets its own sweep and staircase here.

WHAT THIS PROBE ANSWERS
  1. Does the AI azimuth axis still behave as measured? Five bearings, ratio and
     settle time per bearing.
  2. What does the AI ELEVATION axis do? Five commanded values against arg 876 --
     the first measurement of that gauge, and the reason it gets equal time.
  3. Read granularity of 874 and 876: the smallest non-zero change observable.
     Measured three ways -- an azimuth staircase, an elevation staircase, and
     your own hand slew. A controller's deadband cannot be finer than this.
  4. Does the player axis move the head at all while NOT in the sight's own
     viewport? 3026 then 3025, held at +-0.5. THIS IS THE DECISION: if it does
     not move, the plan takes the AI position axis and the control loop, the
     deadband, the tuning pair and the BL-B63 dependency all disappear.

TIMELINE (model time from the first exported frame)
     0- 60 s  SETUP   you fly the warm-up by hand, OBSERV ON. Read-only.
    60- 63 s  CHECK   reports the switch state it found; warns if OBSERV is off
    63- 83 s  AZ      AI azimuth at -40/-20/0/+20/+40 deg
    83-103 s  ELEV    AI elevation at -0.50/-0.25/0/+0.25/+0.50
   103-121 s  STAIR   azimuth in steps of 0.002
   121-139 s  STAIR   elevation in steps of 0.002
   139-155 s  PLAYER  player axes held at +-0.5 -- HANDS OFF THE SLEW CONTROLS
   155-195 s  YOURS   slew the sight by hand, slowly: azimuth, then elevation
   195 s      DONE    re-centre the sight, print the summary

HOW TO FLY IT
  Mi-24P on the ground. Set the 9K113 up however you like during the first 60
  seconds -- the probe only watches. Get OBSERV ON before t=60 s; if it is off
  the probe says so and runs anyway, which is itself a useful negative. From
  t=63 s keep your hands off the slew controls until the probe hands them back
  at t=155 s. Exit after the log says PROBE DONE.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_slew.log"

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

-- Read only. Nothing below is ever written -- these are here so the log shows
-- what state you set the aircraft to, and so the summary can say whether
-- OBSERV was actually on when the sight refused (or agreed) to move.
local WATCHED = {
    { arg = 673, label = "SAFE WEAP" },
    { arg = 773, label = "URS PWR  " },
    { arg = 955, label = "SHCHO PWR" },
    { arg = 885, label = "GUID PWR " },
    { arg = 886, label = "OBSERV   " },
    { arg = 963, label = "LNCHR SEL" },
}
local ARG_OBSERV = 886

local ARG_AZ = 874
local ARG_ELEV = 876
local CMD_AI_AZ = 3061         -- position target, value = az_deg / 60
local CMD_AI_ELEV = 3060       -- position target, degrees-per-unit UNMEASURED
local CMD_PLAYER_ELEV = 3025   -- player slew, up/down   -- accumulates
local CMD_PLAYER_AZ = 3026     -- player slew, left/right -- accumulates

-- Phases. T_SETUP is the user's own number: "Set test to happen at T+60s".
local T_SETUP = 60.0
local T_CHECK = T_SETUP
local T_AZ = T_SETUP + 3.0
local BEARINGS_DEG = { -40, -20, 0, 20, 40 }
local BEARING_PERIOD = 4.0
local T_ELEV = T_AZ + BEARING_PERIOD * #BEARINGS_DEG
-- Elevation is commanded in raw axis units, not degrees: the conversion is the
-- unknown. The gimbal is +20/-15 deg, so +-0.5 stays well inside it whatever
-- the scale turns out to be.
local ELEV_VALUES = { -0.5, -0.25, 0, 0.25, 0.5 }
local T_STAIR_AZ = T_ELEV + BEARING_PERIOD * #ELEV_VALUES
local STAIR_STEPS = 12
local STAIR_DELTA = 0.002
local STAIR_PERIOD = 1.5
local T_STAIR_ELEV = T_STAIR_AZ + STAIR_STEPS * STAIR_PERIOD
local T_PLAYER = T_STAIR_ELEV + STAIR_STEPS * STAIR_PERIOD
local PLAYER_HOLD_S = 3.0
local PLAYER_PERIOD = PLAYER_HOLD_S + 0.8
local T_HAND = T_PLAYER + PLAYER_PERIOD * 4 + 1.0
local SLEW_WINDOW_S = 40.0
local T_DONE = T_HAND + SLEW_WINDOW_S

local HEARTBEAT_S = 5.0

-- ---------------------------------------------------------------- readers
local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function fmt(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.5f", v)
end

local function switch_snapshot()
    local parts = {}
    for _, w in ipairs(WATCHED) do
        parts[#parts + 1] = string.format("%d=%s", w.arg, fmt(read_arg(w.arg)))
    end
    return table.concat(parts, " ")
end

local function slew_snapshot()
    return string.format("874=%s 876=%s", fmt(read_arg(ARG_AZ)), fmt(read_arg(ARG_ELEV)))
end

-- ---------------------------------------------------------------- the one writer
local function set_command(cmd, value, label)
    local dev = try("GetDevice(7)", GetDevice, DEV_I9K113)
    if dev == nil then
        log(string.format("  %s: GetDevice(7) returned nil", label))
        return false
    end
    local fn = safe_index(dev, "SetCommand")
    if type(fn) ~= "function" then
        log(string.format("  %s: device 7 has no SetCommand", label))
        return false
    end
    local ok, err = pcall(fn, dev, cmd, value)
    log(string.format("  %s: SetCommand(%d, %s) ok=%s err=%s",
                      label, cmd, fmt(value), tostring(ok), tostring(err)))
    return ok
end

-- ============================================================= state
local started, t0 = false, nil
local last_switches, last_beat = nil, -1e9
local checks = {}
local check_done, hand_open, done_logged = false, false, false
local az_idx, elev_idx, stair_az_idx, stair_elev_idx, player_step = 0, 0, 0, 0, 0
local observ_at_check = nil
local az_results, elev_results = {}, {}
local stair_az, stair_elev = {}, {}
local player_results = {}
local min_delta = { [ARG_AZ] = nil, [ARG_ELEV] = nil }
local last_slew = { [ARG_AZ] = nil, [ARG_ELEV] = nil }

local function after(dt_now, delay, fn)
    checks[#checks + 1] = { at = dt_now + delay, fn = fn }
end

local function track_granularity()
    if done_logged then return end
    for _, arg in ipairs({ ARG_AZ, ARG_ELEV }) do
        local v = read_arg(arg)
        if type(v) == "number" then
            local prev = last_slew[arg]
            if type(prev) == "number" then
                local d = math.abs(v - prev)
                if d > 0 and (min_delta[arg] == nil or d < min_delta[arg]) then
                    min_delta[arg] = d
                end
            end
            last_slew[arg] = v
        end
    end
end

-- ============================================================= phases
local function phase_check(dt)
    observ_at_check = read_arg(ARG_OBSERV)
    log(string.format("  --- SETUP CHECK t=%5.1f", dt))
    for _, w in ipairs(WATCHED) do
        log(string.format("      %s (%d) = %s", w.label, w.arg, fmt(read_arg(w.arg))))
    end
    if type(observ_at_check) == "number" and observ_at_check > 0.5 then
        log("      OBSERV is ON. Hands off the slew controls until t=" .. T_HAND)
    else
        log("      *** OBSERV reads OFF (886 = " .. fmt(observ_at_check) .. "). Running anyway --")
        log("      *** a sight that will not move with OBSERV off is a different finding from")
        log("      *** one that will not move at all. Note which case this run was.")
    end
end

local function az_bearing(dt)
    az_idx = az_idx + 1
    local deg = BEARINGS_DEG[az_idx]
    local value = deg / 60.0
    log(string.format("  --- AI AZ %d/%d t=%5.1f: %+d deg -> value %s (expect 874 = %s)",
                      az_idx, #BEARINGS_DEG, dt, deg, fmt(value), fmt(value * 0.44)))
    set_command(CMD_AI_AZ, value, "AI az")
    for _, d in ipairs({ 0.1, 0.25, 0.5, 1.0, 2.0 }) do
        after(dt, d, function()
            log(string.format("    settle +%.2fs  %s", d, slew_snapshot()))
        end)
    end
    after(dt, 2.0, function()
        local a = read_arg(ARG_AZ)
        az_results[#az_results + 1] = {
            deg = deg, value = value, arg = a,
            ratio = (type(a) == "number" and value ~= 0) and (a / value) or nil,
        }
    end)
end

local function elev_value(dt)
    elev_idx = elev_idx + 1
    local value = ELEV_VALUES[elev_idx]
    log(string.format("  --- AI ELEV %d/%d t=%5.1f: value %s (gauge unmeasured -- this IS the measurement)",
                      elev_idx, #ELEV_VALUES, dt, fmt(value)))
    set_command(CMD_AI_ELEV, value, "AI elev")
    for _, d in ipairs({ 0.1, 0.25, 0.5, 1.0, 2.0 }) do
        after(dt, d, function()
            log(string.format("    settle +%.2fs  %s", d, slew_snapshot()))
        end)
    end
    after(dt, 2.0, function()
        local a = read_arg(ARG_ELEV)
        elev_results[#elev_results + 1] = {
            value = value, arg = a,
            ratio = (type(a) == "number" and value ~= 0) and (a / value) or nil,
        }
    end)
end

local function stair(dt, cmd, idx, into, label)
    local value = STAIR_DELTA * idx
    set_command(cmd, value, string.format("%s stair %02d", label, idx))
    after(dt, 1.0, function()
        local arg = (cmd == CMD_AI_AZ) and read_arg(ARG_AZ) or read_arg(ARG_ELEV)
        into[#into + 1] = { value = value, arg = arg }
        log(string.format("    %s stair %02d  value=%s  arg=%s", label, idx, fmt(value), fmt(arg)))
    end)
end

local PLAYER_STEPS = {
    { cmd = CMD_PLAYER_AZ,   value =  0.5, label = "player az +0.5 (3026)" },
    { cmd = CMD_PLAYER_AZ,   value = -0.5, label = "player az -0.5 (3026)" },
    { cmd = CMD_PLAYER_ELEV, value =  0.5, label = "player elev +0.5 (3025)" },
    { cmd = CMD_PLAYER_ELEV, value = -0.5, label = "player elev -0.5 (3025)" },
}

local function player(dt)
    player_step = player_step + 1
    local p = PLAYER_STEPS[player_step]
    local az0, el0 = read_arg(ARG_AZ), read_arg(ARG_ELEV)
    log(string.format("  --- PLAYER AXIS %d/%d t=%5.1f  %s  before: %s",
                      player_step, #PLAYER_STEPS, dt, p.label, slew_snapshot()))
    set_command(p.cmd, p.value, p.label)
    after(dt, PLAYER_HOLD_S * 0.5, function()
        log(string.format("    mid-hold   %s", slew_snapshot()))
    end)
    after(dt, PLAYER_HOLD_S - 0.2, function()
        log(string.format("    end-hold   %s", slew_snapshot()))
        set_command(p.cmd, 0, p.label .. " release")
    end)
    after(dt, PLAYER_HOLD_S + 0.5, function()
        local az1, el1 = read_arg(ARG_AZ), read_arg(ARG_ELEV)
        local moved = false
        if type(az0) == "number" and type(az1) == "number" and az0 ~= az1 then moved = true end
        if type(el0) == "number" and type(el1) == "number" and el0 ~= el1 then moved = true end
        player_results[#player_results + 1] = { label = p.label, moved = moved }
        log(string.format("    released   %s   moved=%s", slew_snapshot(), tostring(moved)))
    end)
end

local function hand_window(dt)
    hand_open = true
    min_delta[ARG_AZ], min_delta[ARG_ELEV] = nil, nil
    last_slew[ARG_AZ], last_slew[ARG_ELEV] = nil, nil
    log(string.format("  --- HANDS BACK t=%5.1f: slew the sight yourself now, slowly.", dt))
    log(string.format("      Azimuth first, then elevation. %.0f seconds.", SLEW_WINDOW_S))
end

local function summary()
    log("")
    log("  ================= SUMMARY =================")
    log(string.format("  OBSERV (886) at the start of the measured run: %s", fmt(observ_at_check)))
    log("  Q1 AI azimuth -- expect ratio 0.44000 at every bearing")
    for _, b in ipairs(az_results) do
        log(string.format("    %+4d deg  value=%s  874=%s  ratio=%s",
                          b.deg, fmt(b.value), fmt(b.arg), fmt(b.ratio)))
    end
    log("  Q2 AI elevation -- no expectation; this is the first measurement of the gauge")
    for _, e in ipairs(elev_results) do
        log(string.format("    value=%s  876=%s  ratio=%s", fmt(e.value), fmt(e.arg), fmt(e.ratio)))
    end
    log(string.format("  Q3 staircases, step %s", fmt(STAIR_DELTA)))
    local prev = nil
    for _, r in ipairs(stair_az) do
        local moved = (type(r.arg) == "number" and type(prev) == "number" and r.arg ~= prev)
            and string.format("moved by %s", fmt(math.abs(r.arg - prev))) or "same"
        log(string.format("    az   value=%s  874=%s  %s", fmt(r.value), fmt(r.arg), moved))
        prev = r.arg
    end
    prev = nil
    for _, r in ipairs(stair_elev) do
        local moved = (type(r.arg) == "number" and type(prev) == "number" and r.arg ~= prev)
            and string.format("moved by %s", fmt(math.abs(r.arg - prev))) or "same"
        log(string.format("    elev value=%s  876=%s  %s", fmt(r.value), fmt(r.arg), moved))
        prev = r.arg
    end
    log(string.format("  Q3 hand-slew minimum non-zero delta:  874=%s  876=%s",
                      fmt(min_delta[ARG_AZ]), fmt(min_delta[ARG_ELEV])))
    log("  Q4 player axis -- THE DECISION")
    local any = false
    for _, r in ipairs(player_results) do
        log(string.format("    %-24s moved=%s", r.label, tostring(r.moved)))
        if r.moved then any = true end
    end
    if any then
        log("    => the player axis DOES move the head outside the viewport: the rate loop is")
        log("       feasible, and the plan's scope caution applies (own entry, gated on BL-B63).")
    else
        log("    => the player axis does NOT move the head: take the AI position axis. No")
        log("       controller, no deadband, no tuning pair, no BL-B63 dependency.")
    end
    log("  ===========================================")
end

-- ============================================================= driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 SLEW PROBE -- no switch is ever written by this script")
    local v = try("LoGetVersionInfo", LoGetVersionInfo)
    if type(v) == "table" then
        log("  DCS version: " .. tostring(v.ProductName) .. " " .. tostring(v.FileVersion))
    end
    log("  Argument numbers are POSITIONAL -- record the version above.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 slew probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log(string.format("  --- SETUP WINDOW t=  0.0: %.0f seconds. Fly the warm-up by hand,",
                          T_SETUP))
        log("      OBSERV ON. The probe only reads until then.")
        log("      switches: " .. switch_snapshot())
        log("      slew:     " .. slew_snapshot())
    end
    local dt = t - t0

    track_granularity()

    local s = switch_snapshot()
    if s ~= last_switches or (dt - last_beat) >= HEARTBEAT_S then
        local tag = (s ~= last_switches) and "~" or "."
        log(string.format("  %s t=%5.1f %s | %s", tag, dt, s, slew_snapshot()))
        last_switches, last_beat = s, dt
    end

    for i = #checks, 1, -1 do
        if dt >= checks[i].at then
            local fn = checks[i].fn
            table.remove(checks, i)
            fn()
        end
    end

    if not check_done and dt >= T_CHECK then
        check_done = true
        phase_check(dt)
    end

    if check_done and az_idx < #BEARINGS_DEG and dt >= T_AZ + BEARING_PERIOD * az_idx then
        az_bearing(dt)
    end

    if az_idx >= #BEARINGS_DEG and elev_idx < #ELEV_VALUES
       and dt >= T_ELEV + BEARING_PERIOD * elev_idx then
        elev_value(dt)
    end

    if elev_idx >= #ELEV_VALUES and stair_az_idx < STAIR_STEPS
       and dt >= T_STAIR_AZ + STAIR_PERIOD * stair_az_idx then
        stair_az_idx = stair_az_idx + 1
        if stair_az_idx == 1 then
            log(string.format("  --- AZ STAIRCASE t=%5.1f: steps of %s (%.3f deg each)",
                              dt, fmt(STAIR_DELTA), STAIR_DELTA * 60.0))
        end
        stair(dt, CMD_AI_AZ, stair_az_idx, stair_az, "az")
    end

    if stair_az_idx >= STAIR_STEPS and stair_elev_idx < STAIR_STEPS
       and dt >= T_STAIR_ELEV + STAIR_PERIOD * stair_elev_idx then
        stair_elev_idx = stair_elev_idx + 1
        if stair_elev_idx == 1 then
            log(string.format("  --- ELEV STAIRCASE t=%5.1f: steps of %s", dt, fmt(STAIR_DELTA)))
        end
        stair(dt, CMD_AI_ELEV, stair_elev_idx, stair_elev, "elev")
    end

    if stair_elev_idx >= STAIR_STEPS and player_step < #PLAYER_STEPS
       and dt >= T_PLAYER + PLAYER_PERIOD * player_step then
        player(dt)
    end

    if not hand_open and dt >= T_HAND then
        hand_window(dt)
    end

    if not done_logged and dt >= T_DONE then
        done_logged = true
        log(string.format("  --- DONE t=%5.1f: re-centring the sight", dt))
        set_command(CMD_AI_AZ, 0, "AI az -> 0")
        set_command(CMD_AI_ELEV, 0, "AI elev -> 0")
        after(dt, 2.0, function()
            summary()
            log("  PROBE DONE -- exit whenever. Re-copy the production Export.lua afterwards.")
        end)
    end
end
