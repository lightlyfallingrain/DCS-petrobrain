-- petrobrain-f10-probe-hook.lua -- THROWAWAY recon probe, not pipeline code.
--
-- Question (aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md): can a
-- Hook-state script put its own item into the F10 radio menu, and get told when the
-- player selects it, without per-mission authoring?
--
-- Deploy: copy to Saved Games\DCS\Scripts\Hooks\. Remove after the probe run.
-- Output: every line goes to Saved Games\DCS\Logs\dcs.log tagged PB-F10-PROBE.
--
-- Routes probed (all pcall-wrapped; a failure is data, not a crash):
--   R0  what is visible from Hook state at all (net.dostring_in, a_do_script,
--       RadioCommandDialogsPanel, missionCommands).
--   R1  DIRECT: insert {name, command={perform=...}} into RadioCommandDialogsPanel's
--       live menuOther table (static read of Scripts/UI/RadioCommandDialogPanel/
--       RadioCommandDialogsPanel.lua: getDataParameter returns data[...] by reference;
--       onDialogCommand calls command:perform(parameters)). Only works if that module
--       lives in the same Lua state as Hooks -- autoexec.lua loads it into "globalL".
--   R2  BRIDGE: net.dostring_in("mission", ...) without the autoexec.cfg opt-in, to
--       record whether 2.9.29 refuses it, and if not, register via a_do_script.
--   R3  a_do_script called directly from Hook state (Sim_ControlAPI.md line 323 note).
--   R4  onShowRadioMenu / onRadioCommand payloads, logged for the record.

local DCS = require("DCS")

local TAG = "PB-F10-PROBE"
local probe = {}

local function logi(msg)
    log.write(TAG, log.INFO, msg)
end

local function describe(value, depth)
    depth = depth or 0
    if type(value) ~= "table" or depth >= 2 then
        return type(value) .. ":" .. tostring(value)
    end
    local parts = {}
    local n = 0
    for k, v in pairs(value) do
        n = n + 1
        if n > 20 then
            table.insert(parts, "...")
            break
        end
        table.insert(parts, tostring(k) .. "=" .. describe(v, depth + 1))
    end
    return "{" .. table.concat(parts, ", ") .. "}"
end

local function try(label, fn)
    local ok, a, b = pcall(fn)
    logi(label .. " -> ok=" .. tostring(ok) .. " a=" .. describe(a) .. " b=" .. describe(b))
    return ok, a
end

-- R0 -------------------------------------------------------------------------------------
logi("R0 loaded")
logi("R0 type(net)=" .. type(net) .. " type(net.dostring_in)=" .. type(net and net.dostring_in))
logi("R0 type(a_do_script)=" .. type(a_do_script))
logi("R0 type(missionCommands)=" .. type(missionCommands))
logi("R0 type(RadioCommandDialogsPanel)=" .. type(RadioCommandDialogsPanel))
logi("R0 type(_G.RadioCommandDialogsPanel)=" .. type(_G and _G.RadioCommandDialogsPanel))
logi(
    "R0 package.loaded.RadioCommandDialogsPanel="
        .. type(package and package.loaded and package.loaded["RadioCommandDialogsPanel"])
)

-- R1 -------------------------------------------------------------------------------------
local DIRECT_NAME = "PB probe: direct"

local function findPanel()
    -- Deliberately no require(): that would load a fresh, never-rendered copy into this
    -- state and give a false positive.
    return RadioCommandDialogsPanel
        or (_G and _G.RadioCommandDialogsPanel)
        or (package and package.loaded and package.loaded["RadioCommandDialogsPanel"])
end

local function insertDirect(when)
    try("R1 insert@" .. when, function()
        local panel = findPanel()
        if type(panel) ~= "table" then
            return "panel not reachable", type(panel)
        end
        local menuOther = panel.getDataParameter("menuOther")
        local items = menuOther.submenu.items
        for _, item in ipairs(items) do
            if item.name == DIRECT_NAME then
                return "already present", #items
            end
        end
        table.insert(items, {
            name = DIRECT_NAME,
            command = {
                perform = function(self, parameters)
                    logi("R1 DIRECT perform FIRED params=" .. describe(parameters))
                end,
            },
        })
        return "inserted", #items
    end)
end

-- R2 / R3 --------------------------------------------------------------------------------
local BRIDGED_REGISTER = [[a_do_script("missionCommands.addCommand('PB probe: bridged', nil, ]]
    .. [[function() env.info('PB-F10-PROBE R2 BRIDGED callback FIRED') end)")]]

local function probeBridges()
    try("R2 dostring_in(mission, return tostring(missionCommands))", function()
        return net.dostring_in("mission", "return tostring(missionCommands)")
    end)
    try("R2 dostring_in(mission, return tostring(a_do_script))", function()
        return net.dostring_in("mission", "return tostring(a_do_script)")
    end)
    try("R2 dostring_in(mission, register via a_do_script)", function()
        return net.dostring_in("mission", BRIDGED_REGISTER)
    end)
    try("R3 a_do_script direct register", function()
        return a_do_script(
            "missionCommands.addCommand('PB probe: a_do_script', nil, "
                .. "function() env.info('PB-F10-PROBE R3 A_DO_SCRIPT callback FIRED') end)"
        )
    end)
end

-- Callbacks ------------------------------------------------------------------------------
function probe.onSimulationStart()
    logi("onSimulationStart")
    insertDirect("onSimulationStart")
    probeBridges()
end

function probe.onShowRadioMenu(a_h)
    logi("R4 onShowRadioMenu a_h=" .. describe(a_h))
    -- Re-insert in case initialize()/clearSomeMenu() reset the table after mission start.
    insertDirect("onShowRadioMenu")
end

function probe.onRadioCommand(command_message)
    logi("R4 onRadioCommand msg=" .. describe(command_message))
end

function probe.onSimulationStop()
    logi("onSimulationStop")
end

DCS.setUserCallbacks(probe)
logi("R0 callbacks set")
