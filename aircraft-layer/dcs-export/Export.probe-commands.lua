--[[
BL-6 COMMAND-CHANNEL PROBE -- not the production export script.

Self-contained: does NOT connect to the collector and does not need it running.
It only appends to Logs\aircraft_layer_probe_cmd.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`, fly, then read the log back.

Settles the single question the BL-6 plan is blocked on, and the one the
2026-09-11 command-surface reference leaves open:

  Can an external process MANIPULATE cockpit switches and controls, or only
  read them?

Primary target is the 9K113 Raduga-Sh operator sight (device 7) -- the sight
Petrovich actually points at things, and the one with a real read channel:
cockpit draw arguments 874 (azimuth) / 876 (elevation), declared as gauges in
mainpanel_init.lua:1575-1585.

NOTE the slew axes are VELOCITY, not position (Devices_specs/9K113.lua sets
`axis_use_velocity = true`, h_axis_velocity = rad(20)/s, v_axis_velocity =
rad(10)/s). So a slew command sets a RATE: stage E commands a rate, samples
874/876 across frames, then commands zero. Pointing the sight at a bearing
would require closing that loop, which is why the read side matters.

Everything in `aircraft-layer/research/mi24p-command-surface.md` is
enumerated from primary source and is certain. The one unverified link is
whether `GetDevice` / `get_argument_value` / `performClickableAction` exist
inside Export.lua's own Lua state -- they are community-standard (DCS-BIOS,
Helios) but appear in neither Scripts/Export.lua nor API/Sim_ControlAPI.md.

Stages, in increasing order of intrusiveness:
  A  capability census      -- passive, runs once at start
  B  baseline reads         -- passive, ASP-17 args + AI wheel + controls
  C  ASP-17 write test      -- cosmetic only (crosshair brightness), auto-reverts
  D  Petrovich write test   -- OPT-IN, only if the flag file below exists

Stage D is gated because it commands Petrovich for real. To arm it, create an
empty file:  Saved Games\DCS\Scripts\probe_petrovich.flag

Delete this file once BL-6's command question is settled; do not let it drift
into a second production script.

IDs below are for DCS 2.9.29.27278 and are POSITIONAL -- re-derive from
command_defs.lua after any DCS update. See the reference doc's "Fragility".
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_cmd.log"
local FLAG_PATH = lfs.writedir() .. "Scripts\\probe_petrovich.flag"

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

-- Never let a probe crash the export state; every DCS call goes through this.
local function try(label, fn, ...)
    local ok, a, b = pcall(fn, ...)
    if not ok then
        log(string.format("  %-34s ERROR: %s", label, tostring(a)))
        return nil
    end
    return a, b
end

-- Indexing a userdata device object is itself an error if it has no __index
-- metamethod -- so even asking "does :performClickableAction exist" must be
-- protected, or an absent metatable would throw straight out of LuaExportStart
-- and take the whole export state down with it.
local function safe_index(obj, key)
    local ok, v = pcall(function() return obj[key] end)
    if not ok then return nil end
    return v
end

local function type_of_member(obj, key)
    local v = safe_index(obj, key)
    return type(v)
end

-- ---------------------------------------------------------------- constants
local DEV_MAINPANEL = 0
local DEV_I9K113    = 7
local DEV_ASP_17V   = 16
local DEV_HELPER_AI = 30

-- asp_commands, from command_defs.lua (each device's table restarts at 3001)
local ASP = {
    Manual_Auto = 3001, Sync_Async = 3002, Range_Auto_Manual = 3003,
    Range_Value = 3004, Elevation_Delta = 3005, Azimuth_Delta = 3006,
    Sight_Null = 3007, Base_Range = 3008, Control = 3009,
    Brightness_NS = 3010, Brightness_PM = 3011, Power = 3014,
}

-- helperai_commands
local HAI = { ShowMenu = 3001, SelectTarget = 3009, DesignateAttackPoint = 3020 }

-- i9K113_commands. The _AI_AXIS pair is bound to NO input anywhere in the
-- module's Input/ profiles -- they are the internal channel the AI uses to
-- slew this sight, which is exactly what we would want to drive.
local K113 = {
    Command_POWER_PN                        = 3001,
    Command_NABL                            = 3002,  -- observation mode
    Command_VertPos                         = 3019,
    Command_HorizPos                        = 3020,
    Command_ZOOM                            = 3021,
    Command_SIGHT_UP_DOWN_AXIS              = 3025,
    Command_SIGHT_LEFT_RIGHT_AXIS           = 3026,
    Command_SIGHT_ZOOM                      = 3027,
    Command_Aiming                          = 3028,
    Command_STVORKI                         = 3018,  -- sight doors
    Command_Intern_SIGHT_UP_DOWN_AI_AXIS    = 3060,
    Command_Intern_SIGHT_LEFT_RIGHT_AI_AXIS = 3061,
}

-- 9K113 sight pointing angle, as cockpit draw arguments (mainpanel_init.lua).
-- gauge input -1..1 maps to output -0.44..0.44 (az) and -0.75..0/0..1.0 (el),
-- so these are NORMALISED gauge values, not radians -- the true angle lives in
-- native getSightAzimuth()/getSightElevation(), which Lua does not see.
-- Converting to real bearings needs live calibration against a known target.
local K113_ARG_AZIMUTH   = 874
local K113_ARG_ELEVATION = 876

-- 9K113 panel switches -> draw arguments, from clickabledata.lua
local K113_ARGS = {
    [885] = "POWER_PN",    [884] = "Backlight",   [886] = "NABL",
    [887] = "DIAFR_OTKR",  [912] = "OTKL_BLOCK_ARU", [913] = "SSP_VKL",
    [910] = "GENER_EMIT",  [905] = "KONTR_T1_B9", [903] = "WORK_CONTROL",
    [911] = "START_PM",    [899] = "VHOD_BVK_KV", [890] = "Heat_O",
    [871] = "ZOOM",        [872] = "OS",          [873] = "SES",
    [775] = "STVORKI",     [870] = "CHECK_LAMPS", [933] = "0_04",
    [934] = "SWITCHER_IN_OUT", [935] = "COD1_COD2", [931] = "CHECKING",
    [875] = "HIGH_K",      [932] = "TABLO",       [882] = "RadiationReset",
}

-- ASP-17 clickable draw arguments (switch positions), from clickabledata.lua
local ASP_ARGS = {
    [515] = "Range_Auto_Manual", [528] = "Sight_Null",   [529] = "Power",
    [552] = "Range_Value",       [553] = "Manual_Auto",  [554] = "Sync_Async",
    [556] = "Elevation_Delta",   [557] = "Base_Range",   [564] = "Brightness_PM",
    [566] = "Azimuth_Delta",     [567] = "Brightness_NS",[568] = "Backup_Light_PM",
    [569] = "Backup_Light_NS",   [570] = "Control",      [761] = "USR",
    [762] = "USR_check",
}

-- Give the pilot time to settle into level flight before anything runs.
local START_DELAY = 20.0
-- The Mi-24's 9K113 needs ~10s of gyro spin-up after the sight doors open
-- before it can be slewed at all (pilot, 2026-09-11). There is no Lua-readable
-- readiness signal: Ready_9k113 is a mesh element with no value and
-- av9K113::isGyroReady() is native-only. So wait generously.
local GYRO_WAIT   = 20.0

local IND_9K113   = 0   -- cc9K113; has real TEXT elements (Zoom_Val, filters,
                        -- BackLight, ArrowHelper_Val, tips) unlike the ASP-17
local IND_ASP17   = 2   -- list_indication index, 0-based per device_init.lua
local IND_HELPERAI = 6
local IND_AI_WHEEL = 10 -- never yet read by this project

-- ------------------------------------------------------------ stage A
local caps = {}

local function stage_a_capability_census()
    log("=========================================================")
    log("BL-6 COMMAND PROBE -- stage A: capability census")
    log("=========================================================")

    for _, name in ipairs({"GetDevice", "GetIndicator", "list_indication",
                           "list_cockpit_params", "get_param_handle",
                           "LoSetCommand", "LoGetMechInfo", "LoGetSelfData"}) do
        local t = type(_G[name])
        caps[name] = (t == "function")
        log(string.format("  %-22s %s", name, t))
    end

    if not caps.GetDevice then
        log("  !! GetDevice ABSENT -- device-command writes are IMPOSSIBLE from")
        log("     Export.lua state. Stages C/D cannot run. This is the answer.")
        return
    end

    -- What can we actually call on a device object?
    local dev = try("GetDevice(ASP_17V)", GetDevice, DEV_ASP_17V)
    log(string.format("  GetDevice(%d) -> %s", DEV_ASP_17V, type(dev)))
    if type(dev) == "table" or type(dev) == "userdata" then
        for _, m in ipairs({"performClickableAction", "SetCommand",
                            "get_argument_value", "update_arguments"}) do
            log(string.format("    :%-24s %s", m, type_of_member(dev, m)))
        end
        caps.performClickableAction =
            (type_of_member(dev, "performClickableAction") == "function")
        caps.SetCommand = (type_of_member(dev, "SetCommand") == "function")
    end

    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    log(string.format("  GetDevice(0) [mainpanel] -> %s", type(mp)))
    if mp ~= nil and type(mp) ~= "number" then
        caps.get_argument_value =
            (type_of_member(mp, "get_argument_value") == "function")
        log(string.format("    :get_argument_value      %s",
                          type_of_member(mp, "get_argument_value")))
    end
end

-- ------------------------------------------------------------ stage B
local function read_arg(arg)
    if not caps.get_argument_value then return nil end
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function stage_b_baseline()
    log("--- stage B: baseline reads ---")

    log("  ASP-17 switch positions (draw arguments):")
    if caps.get_argument_value then
        for arg, name in pairs(ASP_ARGS) do
            log(string.format("    arg %-4d %-20s = %s", arg, name,
                              tostring(read_arg(arg))))
        end
    else
        log("    get_argument_value unavailable -- switch positions unreadable")
    end

    log("  9K113 sight pointing angle (normalised gauge values, not radians):")
    log(string.format("    arg %d azimuth   = %s", K113_ARG_AZIMUTH,
                      tostring(read_arg(K113_ARG_AZIMUTH))))
    log(string.format("    arg %d elevation = %s", K113_ARG_ELEVATION,
                      tostring(read_arg(K113_ARG_ELEVATION))))

    log("  9K113 panel switch positions:")
    if caps.get_argument_value then
        for arg, name in pairs(K113_ARGS) do
            log(string.format("    arg %-4d %-20s = %s", arg, name,
                              tostring(read_arg(arg))))
        end
    end

    -- The AI command wheel is TEXT (nine ceStringPoly slots on a 'wheel_text'
    -- controller), unlike the ASP-17's geometry-only controllers -- so unlike
    -- list_indication(2) this one should actually print something. Open the
    -- wheel in-cockpit (LCtrl+V) while this runs.
    if caps.list_indication then
        for _, n in ipairs({IND_9K113, IND_AI_WHEEL, IND_HELPERAI, IND_ASP17}) do
            local s = try("list_indication", list_indication, n)
            local body = tostring(s)
            if #body > 1200 then body = body:sub(1, 1200) .. "...<truncated>" end
            log(string.format("  list_indication(%d) [%d bytes]:\n%s",
                              n, #tostring(s), body))
        end
    end

    if caps.LoGetMechInfo then
        local m = try("LoGetMechInfo", LoGetMechInfo)
        if type(m) == "table" and type(m.controlsurfaces) == "table" then
            local cs = m.controlsurfaces
            local function pair(p)
                if type(p) ~= "table" then return tostring(p) end
                return string.format("{%s, %s}", tostring(p.left), tostring(p.right))
            end
            log(string.format("  controlsurfaces: elevator=%s eleron=%s rudder=%s",
                              pair(cs.elevator), pair(cs.eleron), pair(cs.rudder)))
        else
            log("  LoGetMechInfo().controlsurfaces absent/empty (expected for a helo?)")
        end
    end
end

-- ------------------------------------------------------------ stage C
-- Cosmetic ONLY: ASP-17 crosshair brightness knob (arg 564). This exists just
-- to prove the write mechanism end-to-end on a control with no mode gating and
-- no tactical effect, before stage E tries the sight.
local function stage_c_write_test()
    log("--- stage C: write-mechanism proof (ASP-17 brightness, reverts) ---")

    if not caps.performClickableAction then
        log("  performClickableAction unavailable -- CANNOT manipulate switches.")
        return
    end

    local before = read_arg(564)
    log("  arg 564 (Brightness_PM) before = " .. tostring(before))

    local dev = try("GetDevice(ASP_17V)", GetDevice, DEV_ASP_17V)
    if dev == nil then log("  GetDevice returned nil") return end
    local act = safe_index(dev, "performClickableAction")
    if type(act) ~= "function" then
        log("  performClickableAction missing on this device object")
        return
    end

    local target = 0.75
    if type(before) == "number" and math.abs(before - target) < 0.1 then
        target = 0.25
    end

    try("performClickableAction", act, dev, ASP.Brightness_PM, target)
    log(string.format("  performClickableAction(dev=%d, cmd=%d, val=%.2f) issued",
                      DEV_ASP_17V, ASP.Brightness_PM, target))

    local after = read_arg(564)
    log("  arg 564 after = " .. tostring(after))

    if type(before) == "number" and type(after) == "number" then
        if math.abs(after - before) > 0.01 then
            log("  ==> WRITE CONFIRMED: the switch moved. Manipulation works.")
        else
            log("  ==> write did NOT move the argument. Retry with the control's")
            log("      own declared step (0.05 for this default_axis) before")
            log("      concluding writes do not work.")
        end
        try("restore", act, dev, ASP.Brightness_PM, before)
        log("  restored arg 564 -> " .. tostring(read_arg(564)))
    else
        log("  ==> inconclusive: could not read the argument back.")
    end
end

-- ------------------------------------------------------------ stage E
-- THE 9K113 TEST, v2.
--
-- v1 (run 2026-09-11 09:54) produced garbage because the sight was never
-- operational: arg 775 (STVORKI, sight doors) was 0 all flight and the sight's
-- own hint read "OPEN SIGHT DOORS". Azimuth jumped between three quantised
-- values (0 / 0.198 / 0.396), sometimes AGAINST the commanded direction --
-- i.e. we were sampling something other than our own commands.
--
-- Three changes:
--   1. PRECONDITIONS are set up by the probe itself (power, doors, NABL) --
--      we now know performClickableAction works, so don't depend on the pilot
--      remembering. Each one is verified by reading its arg back, and the
--      stage refuses to run if setup fails.
--   2. PER-FRAME SAMPLING across the hold, not just before/after. A smooth
--      monotonic ramp is our velocity command; a jump is somebody else.
--   3. ALTERNATING DIRECTION (+rate, then -rate). If azimuth tracks the sign
--      of the command, causation is established. If it wanders regardless,
--      it is not us.

local K113_ARG_DOORS = 775   -- STVORKI
local stage_d_fired = false

-- v5: CHARACTERISE THE CONTROL LAW.
--
-- Run 4 settled the big questions and overturned one of my conclusions:
--   * BOTH the player axes (3025/3026) and the AI axes (3060/3061) move the
--     sight, bidirectionally, via SetCommand. The AI channel works.
--   * Full gauge range is reachable: azimuth -0.44..+0.44, elevation
--     -0.75..+1.0.
--   * Sign conventions differ: the PLAYER elevation axis is inverted
--     (cmd -1.0 -> arg +1.0) while the AI elevation axis is not
--     (cmd +1.0 -> arg +1.0). Azimuth is same-sign on both.
--   * It is NOT positional. I claimed after run 3 that SetCommand set a
--     position; run 4 disproves that -- commanded +-0.5 reached ~99% of full
--     deflection, and covered the range at the same ~50 deg/s as +-1.0. Run
--     3's instant 0 -> 0.44 was a fast slew into the stop, sampled too
--     coarsely to see.
--
-- So the open question is the control law: given a small command, does the
-- sight SETTLE at a proportional angle (position, with a slow approach) or
-- keep moving until it hits a stop (rate)? That decides whether "look at
-- bearing X" is one write or a closed loop, which is the thing BL-6's
-- effector design actually hinges on.
--
-- Method: from centre, command a SMALL value and sample EVERY FRAME for
-- several seconds. A trace that ramps then flattens short of the stop is
-- positional. A trace that keeps climbing to the stop is a rate.

local HOLD    = 4.0
local SMALL   = {0.02, 0.05, 0.10, 0.25, -0.10}
local AX_CMD  = K113.Command_Intern_SIGHT_LEFT_RIGHT_AI_AXIS  -- preferred effector
local AX_ARG  = K113_ARG_AZIMUTH
local CENTRE_CMD = K113.Command_SIGHT_LEFT_RIGHT_AXIS

local ch = {
    phase = "setup",
    t_phase = 0,
    step = 0,
    samples = {},
    start_val = nil,
}

local function k113_setcmd(cmd, value)
    local dev = try("GetDevice(I9K113)", GetDevice, DEV_I9K113)
    if dev == nil then return false end
    local fn = safe_index(dev, "SetCommand")
    if type(fn) ~= "function" then return false end
    try("SetCommand", fn, dev, cmd, value)
    return true
end

local function k113_send(cmd, value)   -- clickable verb, for panel switches
    local dev = try("GetDevice(I9K113)", GetDevice, DEV_I9K113)
    if dev == nil then return false end
    local fn = safe_index(dev, "performClickableAction")
    if type(fn) ~= "function" then return false end
    try("performClickableAction", fn, dev, cmd, value)
    return true
end

local function k113_set_verified(label, cmd, value, arg, want)
    local before = read_arg(arg)
    if type(before) == "number" and math.abs(before - want) < 0.01 then
        log(string.format("    %-22s arg %d already = %s, leaving alone",
                          label, arg, tostring(before)))
        return true
    end
    k113_send(cmd, value)
    local after = read_arg(arg)
    local ok = (type(after) == "number" and math.abs(after - want) < 0.01)
    log(string.format("    %-22s cmd %d val %.1f : arg %d  %s -> %s  %s",
        label, cmd, value, arg, tostring(before), tostring(after),
        ok and "OK" or "NOT SET"))
    return ok
end

local function stage_e_sight_slew(t)
    if not caps.performClickableAction then return end

    if ch.phase == "setup" then
        log("--- stage E v5: preparing the 9K113 ---")
        log("    POWER_PN (885) = " .. tostring(read_arg(885)))
        local doors_ok = k113_set_verified("open sight doors",
                                           K113.Command_STVORKI, 1,
                                           K113_ARG_DOORS, 1)
        k113_set_verified("observation (NABL)", K113.Command_NABL, 1, 886, 1)
        if not doors_ok then
            log("    !! sight doors shut -- open them in the cockpit. Retrying.")
            ch.phase = "wait_retry"
            ch.t_phase = t
            return
        end
        log("    sight ready. *** DO NOT TOUCH THE SIGHT FROM HERE ON ***")
        log(string.format("    waiting %.0fs for gyro spin-up", GYRO_WAIT))
        if not stage_d_fired then
            stage_d_fired = true
            stage_d_petrovich()
        end
        ch.phase = "gyro_wait"
        ch.t_phase = t

    elseif ch.phase == "wait_retry" then
        if (t - ch.t_phase) > 5.0 then ch.phase = "setup" end

    elseif ch.phase == "gyro_wait" then
        if (t - ch.t_phase) > GYRO_WAIT then
            log(string.format(
                "--- control-law test: %d small commands on cmd %d, %.0fs each ---",
                #SMALL, AX_CMD, HOLD))
            log("    ramp-then-flat short of the stop = POSITION")
            log("    keeps climbing to the stop        = RATE")
            ch.phase = "centre"
            ch.t_phase = t
        end

    elseif ch.phase == "centre" then
        k113_setcmd(CENTRE_CMD, 0.0)
        if (t - ch.t_phase) > 1.5 then
            ch.step = ch.step + 1
            if SMALL[ch.step] == nil then
                ch.phase = "report"
                return
            end
            ch.start_val = read_arg(AX_ARG)
            ch.samples = {}
            log(string.format("--- command %+0.2f, from arg %s ---",
                              SMALL[ch.step], tostring(ch.start_val)))
            ch.phase = "holding"
            ch.t_phase = t
        end

    elseif ch.phase == "holding" then
        k113_setcmd(AX_CMD, SMALL[ch.step])
        local v = read_arg(AX_ARG)
        if type(v) == "number" then
            ch.samples[#ch.samples + 1] =
                string.format("%.2f:%+.4f", t - ch.t_phase, v)
        end
        if (t - ch.t_phase) > HOLD then
            k113_setcmd(AX_CMD, 0.0)
            local final = read_arg(AX_ARG)
            local n = #ch.samples
            log(string.format("    ended at %s after %.1fs (%d samples)%s",
                tostring(final), t - ch.t_phase, n,
                (type(final) == "number" and math.abs(math.abs(final) - 0.44) < 0.005)
                    and "   <- AT THE STOP" or ""))
            local line, step = {}, math.max(1, math.floor(n / 16))
            for i = 1, n, step do line[#line + 1] = ch.samples[i] end
            log("      traj: " .. table.concat(line, " "))
            ch.phase = "centre"
            ch.t_phase = t
        end

    elseif ch.phase == "report" then
        log("=========================================================")
        log("Read the traces above:")
        log("  If a small command flattened out part-way, the axis is a")
        log("  POSITION target and look_at(bearing) is a single write.")
        log("  If every command ran to +-0.44, it is a RATE and look_at needs")
        log("  a closed loop against arg 874 -- which is cheap, since the read")
        log("  side is confirmed working.")
        log("Either way the effector exists: AI axes 3060/3061 via SetCommand.")
        log("=========================================================")
        ch.phase = "done"

    elseif ch.phase == "done" then
    end
end

-- ------------------------------------------------------------ stage D
-- OPT-IN. Commands Petrovich for real. `scan_rad_around_point = 2500` in
-- HelperAI.lua suggests DesignateAttackPoint may make him scan a 2.5km radius
-- around the designated point -- that is the BL-6 hypothesis under test.
local function stage_d_petrovich()
    local f = io.open(FLAG_PATH, "r")
    if f == nil then
        log("--- stage D skipped (no probe_petrovich.flag) ---")
        return
    end
    f:close()

    log("--- stage D: PETROVICH write test (opt-in flag present) ---")
    if not caps.performClickableAction then
        log("  performClickableAction unavailable -- skipping.")
        return
    end
    local dev = try("GetDevice(HELPER_AI)", GetDevice, DEV_HELPER_AI)
    log(string.format("  GetDevice(%d) -> %s", DEV_HELPER_AI, type(dev)))
    if dev == nil then return end
    local act = safe_index(dev, "performClickableAction")
    if type(act) ~= "function" then
        log("  performClickableAction missing on HELPER_AI device object")
        return
    end

    local az0, el0 = k113_angles()
    local before = try("list_indication", list_indication, IND_HELPERAI)

    try("DesignateAttackPoint", act, dev, HAI.DesignateAttackPoint, 1)
    log("  DesignateAttackPoint (3020) issued -- watch the cockpit for any")
    log("  sight slew / Petrovich callout, and compare the dumps below.")

    local after = try("list_indication", list_indication, IND_HELPERAI)
    local az1, el1 = k113_angles()
    log(string.format("  9K113 angle az %s -> %s , el %s -> %s",
        tostring(az0), tostring(az1), tostring(el0), tostring(el1)))
    log("  HelperAI indication BEFORE:\n" .. tostring(before))
    log("  HelperAI indication AFTER:\n" .. tostring(after))
end

-- ------------------------------------------------------------ driver
local started = false
local t0 = nil
local stage_b_done, stage_c_done, stage_d_done = false, false, false

function LuaExportStart()
    log("")
    stage_a_capability_census()
    started = true
end

function LuaExportStop()
    log("BL-6 command probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t)
    return t + 1.0
end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then t0 = t end
    local dt = t - t0

    if not stage_b_done and dt > START_DELAY then
        stage_b_done = true
        stage_b_baseline()
    elseif stage_b_done and not stage_c_done and dt > START_DELAY + 10.0 then
        stage_c_done = true
        stage_c_write_test()
    elseif stage_c_done and not stage_d_done and dt > START_DELAY + 20.0 then
        stage_d_done = true
        stage_d_petrovich()
        log("--- stage E now runs on a repeating cycle. Fly a few cycles OUTSIDE")
        log("    the 9K113 sight view, then ENTER the sight view and fly a few")
        log("    more, so the log shows whether slewing is mode-gated. ---")
    elseif stage_d_done then
        stage_e_sight_slew(t)
    end
end
