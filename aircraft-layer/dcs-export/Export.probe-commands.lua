--[[
BL-6 COMMAND-CHANNEL PROBE -- not the production export script.

Self-contained: does NOT connect to the collector and does not need it running.
It only appends to Logs\aircraft_layer_probe_cmd.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`, fly, then read the log back.

Settles the single question the BL-6 plan is blocked on, and the one the
2026-09-11 command-surface reference leaves open:

  Can an external process MANIPULATE cockpit switches and controls, or only
  read them?

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

-- ASP-17 clickable draw arguments (switch positions), from clickabledata.lua
local ASP_ARGS = {
    [515] = "Range_Auto_Manual", [528] = "Sight_Null",   [529] = "Power",
    [552] = "Range_Value",       [553] = "Manual_Auto",  [554] = "Sync_Async",
    [556] = "Elevation_Delta",   [557] = "Base_Range",   [564] = "Brightness_PM",
    [566] = "Azimuth_Delta",     [567] = "Brightness_NS",[568] = "Backup_Light_PM",
    [569] = "Backup_Light_NS",   [570] = "Control",      [761] = "USR",
    [762] = "USR_check",
}

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

    -- The AI command wheel is TEXT (nine ceStringPoly slots on a 'wheel_text'
    -- controller), unlike the ASP-17's geometry-only controllers -- so unlike
    -- list_indication(2) this one should actually print something. Open the
    -- wheel in-cockpit (LCtrl+V) while this runs.
    if caps.list_indication then
        for _, n in ipairs({IND_AI_WHEEL, IND_HELPERAI, IND_ASP17}) do
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
-- Cosmetic ONLY: crosshair brightness knob (arg 564). No tactical effect,
-- and the original value is restored immediately afterwards.
local function stage_c_write_test()
    log("--- stage C: ASP-17 WRITE test (crosshair brightness, reverts) ---")

    if not caps.performClickableAction then
        log("  performClickableAction unavailable -- CANNOT manipulate switches.")
        return
    end

    local before = read_arg(564)
    log("  arg 564 (Brightness_PM) before = " .. tostring(before))

    local dev = try("GetDevice(ASP_17V)", GetDevice, DEV_ASP_17V)
    if dev == nil then log("  GetDevice returned nil") return end

    local target = 0.75
    if type(before) == "number" and math.abs(before - target) < 0.1 then
        target = 0.25 -- make sure we actually demand a change
    end

    local act = safe_index(dev, "performClickableAction")
    if type(act) ~= "function" then
        log("  performClickableAction missing on this device object")
        return
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
            log("  ==> write did NOT move the argument. Either the call is a")
            log("      no-op from this state, or the value needs a different")
            log("      scale/step for this control type (it is a default_axis).")
        end
        -- restore
        try("restore", act, dev, ASP.Brightness_PM, before)
        log("  restored arg 564 -> " .. tostring(read_arg(564)))
    else
        log("  ==> inconclusive: could not read the argument back.")
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

    local before = try("list_indication", list_indication, IND_HELPERAI)

    local act = safe_index(dev, "performClickableAction")
    if type(act) ~= "function" then
        log("  performClickableAction missing on HELPER_AI device object")
        return
    end
    try("DesignateAttackPoint", act, dev, HAI.DesignateAttackPoint, 1)
    log("  DesignateAttackPoint (3020) issued -- watch the cockpit for any")
    log("  sight slew / Petrovich callout, and compare the dumps below.")

    local after = try("list_indication", list_indication, IND_HELPERAI)
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

    -- staggered so the cockpit is powered up and the log stays readable
    if not stage_b_done and dt > 10.0 then
        stage_b_done = true
        stage_b_baseline()
    elseif not stage_c_done and dt > 20.0 then
        stage_c_done = true
        stage_c_write_test()
    elseif not stage_d_done and dt > 30.0 then
        stage_d_done = true
        stage_d_petrovich()
        log("BL-6 command probe: all stages complete.")
    end
end
