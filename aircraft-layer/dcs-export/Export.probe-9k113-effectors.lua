--[[
PETROVICH 9K113 EFFECTOR PROBE -- not the production script.

Self-contained; does NOT need the collector. Appends to
Logs\aircraft_layer_probe_9k113_effectors.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`; afterwards re-copy the production
`aircraft-layer/dcs-export/Export.lua` from the repository (do not restore a
.backup -- see aircraft-layer/WORKFLOW.md).

Brief: plans/9k113-effectors/plan.md, "Probe brief -- for the user's Windows box"
Card: docs/acceptance/2026-10-17-9k113-effectors-probe.md
Feeds: BL-B66 (body-layer/ROADMAP/BL-B66.md), Decision 1 of the plan.

WHAT IS ALREADY KNOWN (do not re-derive -- this probe only extends it)
  * performClickableAction writes work on devices 30 and 55 (BL-6 wheel, SPU-8).
    Devices 6 (WEAP_SYS) and 7 (I9K113) have NEVER been written to.
  * The AI axis is a POSITION target, measured 2026-09-11 at five points:
    GetDevice(7):SetCommand(3061, az_deg/60) settles <0.25 s, arg_874 = v*0.44.
  * The player axis (3025 up/down, 3026 left/right) accumulates like a held
    slew input. Whether it responds AT ALL outside the sight's own viewport is
    unverified -- that is question 4b, and it decides Decision 1.
  * Elevation (876/3060) has a piecewise gauge; its degrees-per-unit is
    unmeasured. That is why question 2 weights elevation over azimuth.

WHAT THIS PROBE ANSWERS
  1. Can performClickableAction move the warm-up switches?
       673 WEAP_SYS cmd 3020  SAFETY SWITCHES ARMAMENT CIRCUITS
       955 WEAP_SYS cmd 3030  SHCHO PWR          (starts the real warm-up)
       885 I9K113   cmd 3001  GUID.UNIT POWER
       886 I9K113   cmd 3002  OBSERV. (NABL)
       963 WEAP_SYS cmd 3038  launch-station selector (9-position)
     Each is written to the OPPOSITE of its current value (a write that does
     nothing cannot look like success), read back at +1 s and +3 s, and
     RESTORED at the end of the run. 963 is stepped by one detent, not toggled.
  2. Read granularity of args 874 (az) / 876 (elev): the smallest non-zero
     change observable. Measured twice -- by an AI-axis staircase in steps of
     0.002, and by you slewing the sight by hand in phase F. A controller's
     deadband cannot be finer than this number.
  3. Does list_indication reach the READY lamp? Index 8 (ccGunnersCPanel,
     owned by WEAP_SYS, never tried) and the 9K113's own index 0. Full dumps,
     taken before power, with power on, and with OBSERV on.
  4a. Does the AI axis still behave as measured? Five bearings, ratio and
      settle time reported per bearing.
  4b. Does the player axis move the head at all while NOT in the sight's
      viewport? 3026 then 3025 held at +-0.5 for 3 s each, arg watched.

TIMELINE (model time from the first exported frame)
     0- 15 s  A  read-only baseline + list_indication(8)/(0) with no power
    15- 55 s  B  the five switch writes, one every 8 s, read back each time
    55- 67 s  C  list_indication(8)/(0) again, now powered and OBSERV on
    67-100 s  D  AI-axis bearings (4a) then the 0.002 staircase (2)
   100-118 s  E  player-axis test (4b) -- DO NOT touch the slew controls here
   118-158 s  F  YOUR SLEW WINDOW: slew the sight by hand, slowly, both axes
   158 s      G  restore every switch and the AI axis, print the summary
  About three minutes from the first exported frame.

HOW TO FLY IT
  Cold or hot start, on the ground, Mi-24P, operator seat reachable. Sit in the
  PILOT seat for the whole run -- every write here is aimed at the OPERATOR's
  panels, and whether that works cross-seat is half of question 1. Do not touch
  any 9K113 switch yourself before phase G. In phase F only, slew the sight by
  hand as slowly as you can, azimuth first, then elevation. Exit after the log
  says PROBE DONE; the probe restores what it changed, but check the switches.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_effectors.log"

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
local DEV_WEAP_SYS = 6
local DEV_I9K113 = 7

-- Switches under test: {arg, device, command, label, kind}
--   kind "toggle" -> written to the opposite of its current value
--   kind "detent" -> stepped by one detent and stepped back
local SWITCHES = {
    { arg = 673, dev = DEV_WEAP_SYS, cmd = 3020, label = "SAFE WEAP  (673)", kind = "toggle" },
    { arg = 955, dev = DEV_WEAP_SYS, cmd = 3030, label = "SHCHO PWR  (955)", kind = "toggle" },
    { arg = 885, dev = DEV_I9K113,   cmd = 3001, label = "GUID PWR   (885)", kind = "toggle" },
    { arg = 886, dev = DEV_I9K113,   cmd = 3002, label = "OBSERV     (886)", kind = "toggle" },
    { arg = 963, dev = DEV_WEAP_SYS, cmd = 3038, label = "LNCHR SEL  (963)", kind = "detent" },
}
local DETENT_STEP = 0.1

-- Slew readback and the two write channels.
local ARG_AZ = 874
local ARG_ELEV = 876
local CMD_AI_AZ = 3061         -- position target, value = az_deg / 60
local CMD_AI_ELEV = 3060       -- position target, degrees-per-unit unmeasured
local CMD_PLAYER_ELEV = 3025   -- player slew, up/down   -- accumulates
local CMD_PLAYER_AZ = 3026     -- player slew, left/right -- accumulates

local IND_GUNNERS_PANEL = 8    -- ccGunnersCPanel, owned by WEAP_SYS, never tried
local IND_9K113 = 0            -- the sight's own text channel
local IND_MAX_BYTES = 3000

-- Phase A: baseline -------------------------------------------------------
local T_B_START = 15.0         -- first switch write
local SWITCH_PERIOD = 8.0      -- one switch every 8 s
local T_C = T_B_START + SWITCH_PERIOD * #SWITCHES   -- 55 s: powered dumps
local T_D = T_C + 12.0                              -- 67 s -> rounded below
-- Phase D: AI axis
local BEARINGS_DEG = { -40, -20, 0, 20, 40 }
local BEARING_PERIOD = 3.0
local T_STAIR = T_D + BEARING_PERIOD * #BEARINGS_DEG
local STAIR_STEPS = 12
local STAIR_DELTA = 0.002      -- AI-axis units; 1 unit = 60 deg azimuth
local STAIR_PERIOD = 1.5
-- Phase E: player axis
local T_E = T_STAIR + STAIR_STEPS * STAIR_PERIOD
local PLAYER_HOLD_S = 3.0
local PLAYER_SETTLE_S = 3.0
-- Phase F: the user's own slew window
local T_F = T_E + (PLAYER_HOLD_S + 0.8) * 4 + PLAYER_SETTLE_S
local SLEW_WINDOW_S = 40.0
local T_G = T_F + SLEW_WINDOW_S

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
    for _, s in ipairs(SWITCHES) do
        parts[#parts + 1] = string.format("%d=%s", s.arg, fmt(read_arg(s.arg)))
    end
    return table.concat(parts, " ")
end

local function slew_snapshot()
    return string.format("874=%s 876=%s", fmt(read_arg(ARG_AZ)), fmt(read_arg(ARG_ELEV)))
end

local function dump_indication(idx, tag)
    if type(list_indication) ~= "function" then
        log("  list_indication is not a function in this environment")
        return
    end
    local raw = try("list_indication", list_indication, idx)
    if raw == nil then
        log(string.format("  IND(%d) %s: call failed", idx, tag))
        return
    end
    raw = tostring(raw)
    log(string.format("  IND(%d) %s: %d bytes", idx, tag, #raw))
    if #raw == 0 then
        log("    <empty>")
        return
    end
    if #raw > IND_MAX_BYTES then raw = raw:sub(1, IND_MAX_BYTES) .. "\n...<truncated>" end
    log(raw)
end

-- ---------------------------------------------------------------- writers
local function click(dev_id, cmd, value, label)
    local dev = try("GetDevice(" .. dev_id .. ")", GetDevice, dev_id)
    if dev == nil then
        log(string.format("  %s: GetDevice(%d) returned nil", label, dev_id))
        return false
    end
    local fn = safe_index(dev, "performClickableAction")
    if type(fn) ~= "function" then
        log(string.format("  %s: device %d has no performClickableAction", label, dev_id))
        return false
    end
    local ok, err = pcall(fn, dev, cmd, value)
    log(string.format("  %s: performClickableAction(%d, %s) ok=%s err=%s",
                      label, cmd, fmt(value), tostring(ok), tostring(err)))
    return ok
end

local function set_command(dev_id, cmd, value, label)
    local dev = try("GetDevice(" .. dev_id .. ")", GetDevice, dev_id)
    if dev == nil then
        log(string.format("  %s: GetDevice(%d) returned nil", label, dev_id))
        return false
    end
    local fn = safe_index(dev, "SetCommand")
    if type(fn) ~= "function" then
        log(string.format("  %s: device %d has no SetCommand", label, dev_id))
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
local originals = {}            -- arg -> value read before the first write
local written = {}              -- arg -> value we asked for
local finals = {}               -- arg -> value read 3 s after the write, BEFORE restore
local switch_idx = 0            -- how many switches have been written
local phase_c_done, stair_done, done_logged = false, false, false
local bearing_idx, stair_idx = 0, 0
local player_step = 0
local checks = {}               -- deferred read-backs: { at, fn }
local min_delta = { [ARG_AZ] = nil, [ARG_ELEV] = nil }
local last_slew = { [ARG_AZ] = nil, [ARG_ELEV] = nil }
local slew_window_open, phase_f_done = false, false
local bearing_results = {}      -- { deg, value, arg_at_settle, ratio }
local stair_results = {}        -- { value, arg }

local function after(dt_now, delay, fn)
    checks[#checks + 1] = { at = dt_now + delay, fn = fn }
end

-- Track the finest non-zero change seen on each slew argument. Phase D's
-- staircase and phase F's hand slew both feed this; the phases are logged
-- separately so a number can be attributed to one of them.
local function track_granularity()
    -- Phase G's restore slams the sight back to zero; that jump is not a
    -- granularity sample and would otherwise be the smallest-delta answer.
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
local function phase_b_write(dt)
    switch_idx = switch_idx + 1
    local s = SWITCHES[switch_idx]
    local before = read_arg(s.arg)
    originals[s.arg] = before
    local target
    if s.kind == "detent" then
        if type(before) == "number" and before > 0.5 then
            target = before - DETENT_STEP
        elseif type(before) == "number" then
            target = before + DETENT_STEP
        else
            target = DETENT_STEP
        end
    else
        target = (type(before) == "number" and before > 0.5) and 0 or 1
    end
    written[s.arg] = target
    log(string.format("  WRITE %d/%d t=%5.1f  %s  before=%s  target=%s",
                      switch_idx, #SWITCHES, dt, s.label, fmt(before), fmt(target)))
    click(s.dev, s.cmd, target, s.label)
    after(dt, 1.0, function()
        log(string.format("    CHECK %s +1s  now=%s", s.label, fmt(read_arg(s.arg))))
    end)
    after(dt, 3.0, function()
        finals[s.arg] = read_arg(s.arg)
        log(string.format("    CHECK %s +3s  now=%s  (all: %s)",
                          s.label, fmt(finals[s.arg]), switch_snapshot()))
    end)
end

local function phase_c(dt)
    log(string.format("  --- PHASE C t=%5.1f: indications with power on and OBSERV commanded", dt))
    log("      (if the writes in phase B failed, these dumps are the UNPOWERED case -- say so)")
    dump_indication(IND_GUNNERS_PANEL, "powered")
    dump_indication(IND_9K113, "powered")
end

local function phase_d_bearing(dt)
    bearing_idx = bearing_idx + 1
    local deg = BEARINGS_DEG[bearing_idx]
    local value = deg / 60.0
    log(string.format("  --- AI AZ bearing %d/%d t=%5.1f: %d deg -> value %s (expect arg 874 = %s)",
                      bearing_idx, #BEARINGS_DEG, dt, deg, fmt(value), fmt(value * 0.44)))
    set_command(DEV_I9K113, CMD_AI_AZ, value, "AI az")
    for _, d in ipairs({ 0.1, 0.25, 0.5, 1.0 }) do
        after(dt, d, function()
            log(string.format("    settle +%.2fs  %s", d, slew_snapshot()))
        end)
    end
    after(dt, 1.0, function()
        local a = read_arg(ARG_AZ)
        local ratio = nil
        if type(a) == "number" and value ~= 0 then ratio = a / value end
        bearing_results[#bearing_results + 1] = {
            deg = deg, value = value, arg = a, ratio = ratio,
        }
    end)
end

local function phase_d_stair(dt)
    if stair_idx == 0 then
        log(string.format("  --- STAIRCASE t=%5.1f: AI az in steps of %s (one step = %.3f deg)",
                          dt, fmt(STAIR_DELTA), STAIR_DELTA * 60.0))
        log("      the smallest step that moves arg 874 is its read granularity")
    end
    stair_idx = stair_idx + 1
    local value = STAIR_DELTA * stair_idx
    set_command(DEV_I9K113, CMD_AI_AZ, value, string.format("stair %02d", stair_idx))
    after(dt, 1.0, function()
        local a = read_arg(ARG_AZ)
        stair_results[#stair_results + 1] = { value = value, arg = a }
        log(string.format("    stair %02d  value=%s  874=%s", stair_idx, fmt(value), fmt(a)))
    end)
end

-- Phase E: four held player-axis commands. Each logs the argument before, at
-- the end of the hold, and after release -- an accumulating axis should walk
-- the argument during the hold and leave it where it stopped.
local PLAYER_STEPS = {
    { cmd = CMD_PLAYER_AZ,   value =  0.5, label = "player az +0.5 (3026)" },
    { cmd = CMD_PLAYER_AZ,   value = -0.5, label = "player az -0.5 (3026)" },
    { cmd = CMD_PLAYER_ELEV, value =  0.5, label = "player elev +0.5 (3025)" },
    { cmd = CMD_PLAYER_ELEV, value = -0.5, label = "player elev -0.5 (3025)" },
}

local function phase_e_step(dt)
    player_step = player_step + 1
    local p = PLAYER_STEPS[player_step]
    log(string.format("  --- PLAYER AXIS %d/%d t=%5.1f  %s  before: %s",
                      player_step, #PLAYER_STEPS, dt, p.label, slew_snapshot()))
    set_command(DEV_I9K113, p.cmd, p.value, p.label)
    after(dt, PLAYER_HOLD_S * 0.5, function()
        log(string.format("    mid-hold   %s", slew_snapshot()))
    end)
    after(dt, PLAYER_HOLD_S - 0.2, function()
        log(string.format("    end-hold   %s", slew_snapshot()))
        set_command(DEV_I9K113, p.cmd, 0, p.label .. " release")
    end)
    after(dt, PLAYER_HOLD_S + 0.5, function()
        log(string.format("    released   %s", slew_snapshot()))
    end)
end

local function phase_f_open(dt)
    slew_window_open, phase_f_done = true, true
    min_delta[ARG_AZ], min_delta[ARG_ELEV] = nil, nil
    last_slew[ARG_AZ], last_slew[ARG_ELEV] = nil, nil
    log(string.format("  --- PHASE F t=%5.1f: SLEW THE SIGHT BY HAND NOW, slowly.", dt))
    log(string.format("      Azimuth first, then elevation. %.0f seconds.", SLEW_WINDOW_S))
end

local function restore_all(dt)
    log(string.format("  --- PHASE G t=%5.1f: restoring", dt))
    set_command(DEV_I9K113, CMD_AI_AZ, 0, "AI az -> 0")
    set_command(DEV_I9K113, CMD_AI_ELEV, 0, "AI elev -> 0")
    for i = #SWITCHES, 1, -1 do
        local s = SWITCHES[i]
        local orig = originals[s.arg]
        if type(orig) == "number" then
            click(s.dev, s.cmd, orig, "restore " .. s.label)
        end
    end
    after(dt, 2.0, function()
        log("    after restore: " .. switch_snapshot())
    end)
end

local function summary()
    log("")
    log("  ================= SUMMARY =================")
    log("  Q1 switch writes (compare before/target/final -- final==target means the write took)")
    for _, s in ipairs(SWITCHES) do
        log(string.format("    %s  before=%s  target=%s  final=%s",
                          s.label, fmt(originals[s.arg]), fmt(written[s.arg]), fmt(finals[s.arg])))
    end
    log("  Q4a AI azimuth -- expect ratio 0.44000 at every bearing")
    for _, b in ipairs(bearing_results) do
        log(string.format("    %+4d deg  value=%s  874=%s  ratio=%s",
                          b.deg, fmt(b.value), fmt(b.arg), fmt(b.ratio)))
    end
    log(string.format("  Q2 read granularity, staircase of %s (= %.3f deg per step)",
                      fmt(STAIR_DELTA), STAIR_DELTA * 60.0))
    local prev = nil
    for _, r in ipairs(stair_results) do
        local moved = "same"
        if type(r.arg) == "number" and type(prev) == "number" and r.arg ~= prev then
            moved = string.format("moved by %s", fmt(math.abs(r.arg - prev)))
        end
        log(string.format("    value=%s  874=%s  %s", fmt(r.value), fmt(r.arg), moved))
        prev = r.arg
    end
    log(string.format("  Q2 hand-slew minimum non-zero delta:  874=%s  876=%s",
                      fmt(min_delta[ARG_AZ]), fmt(min_delta[ARG_ELEV])))
    log("  Q3: read the IND(8) / IND(0) dumps above -- unpowered vs powered.")
    log("  Q4b: did any 874/876 value move during PHASE E? If not, the player")
    log("       axis is unusable as an effector and Decision 1 takes the AI axis.")
    log("  ===========================================")
end

-- ============================================================= driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 EFFECTOR PROBE")
    local v = try("LoGetVersionInfo", LoGetVersionInfo)
    if type(v) == "table" then
        -- FileVersion/ProductVersion are TABLES of numbers, not strings: the
        -- 2026-10-17 runs logged "DCS table: 000001E9..." and lost the build
        -- number, which every positional argument number here depends on.
        local function ver(x)
            if type(x) ~= "table" then return tostring(x) end
            local p = {}
            for _, n in ipairs(x) do p[#p + 1] = tostring(n) end
            return table.concat(p, ".")
        end
        log("  DCS version: " .. tostring(v.ProductName)
            .. " file=" .. ver(v.FileVersion) .. " product=" .. ver(v.ProductVersion))
    end
    log("  Argument numbers are POSITIONAL -- record the version above.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 effector probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log("  --- PHASE A t=  0.0: read-only baseline, hands off everything.")
        log("      switches: " .. switch_snapshot())
        log("      slew:     " .. slew_snapshot())
        dump_indication(IND_GUNNERS_PANEL, "unpowered")
        dump_indication(IND_9K113, "unpowered")
    end
    local dt = t - t0

    -- Granularity sampling runs every frame; phase D and F read it separately.
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

    if switch_idx < #SWITCHES and dt >= T_B_START + SWITCH_PERIOD * switch_idx then
        phase_b_write(dt)
    end

    if not phase_c_done and dt >= T_C then
        phase_c_done = true
        phase_c(dt)
    end

    if phase_c_done and bearing_idx < #BEARINGS_DEG
       and dt >= T_D + BEARING_PERIOD * bearing_idx then
        phase_d_bearing(dt)
    end

    if not stair_done and bearing_idx >= #BEARINGS_DEG
       and dt >= T_STAIR + STAIR_PERIOD * stair_idx then
        if stair_idx >= STAIR_STEPS then
            stair_done = true
            log(string.format("  staircase done; hand-slew granularity resets at t=%.0f", T_F))
        else
            phase_d_stair(dt)
        end
    end

    if stair_done and player_step < #PLAYER_STEPS
       and dt >= T_E + (PLAYER_HOLD_S + 0.8) * player_step then
        phase_e_step(dt)
    end

    if not phase_f_done and dt >= T_F then
        phase_f_open(dt)
    end

    if not done_logged and dt >= T_G then
        done_logged = true
        slew_window_open = false
        restore_all(dt)
        after(dt, 3.0, function()
            summary()
            log("  PROBE DONE -- exit whenever. Re-copy the production Export.lua afterwards.")
        end)
    end
end
