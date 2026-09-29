--[[
Throwaway probe Hook script: dump the ACTUAL Mission Scripting API surface.

**This is a probe, not pipeline code.** Deploy by hand, sit in a mission for
~10 s, read `dcs.log`, delete the file.

WHY THIS EXISTS. The user asked, 2026-09-29, after `land.isVisible` was shown
terrain-only (`aircraft-layer/research/2026-09-29-bridge-terrain-probe-
results.md` Finding 12): *"is there any DCS function call that would give us
LOS with buildings and trees taken into account?"*

That cannot be answered from the install. Every one of these functions is
native -- `grep` across `Scripts/` and `MissionEditor/` finds no definition of
`land.isVisible`, `world.searchObjects` or `Controller.isTargetDetected`, only
`ScriptingSystem.lua`'s `class(SceneryObject, Object)`. It also should not be
answered from memory or from the Hoggit wiki, which documents what someone
wrote down, not what this build exposes.

So: **ask the running engine what it has.** `pairs()` over the API tables is
the only authoritative source, it costs nothing, and it turns "I think there
might be" into a list.

THE TWO CANDIDATES THIS IS LOOKING FOR, and why each could work where
`land.isVisible` does not:

1. **`world.VolumeType.SEGMENT`** (if it exists). `world.searchObjects` takes
   a volume, and a *segment* volume is a line. Searching a segment along a
   sightline would return the scenery objects that intersect it -- which is
   building occlusion done by DCS's own intersection test, with no
   type-name -> size table needed. `searchObjects` is already proven to work
   and to cost ~8 us/object at 300 m. This would be the cheap win.
2. **`Controller.isTargetDetected`** (if exposed). This is the **AI detection
   path**, and `Scripts/AI/Detection.lua` configures exactly that path with
   `objects_LOS_test = true` and `trees_LOS_test_T4 = true`. So the engine
   demonstrably *can* test trees and buildings for line of sight -- the
   finding was only that the `land.*` scripting calls do not. If an AI unit
   can be asked, that capability is reachable.

   Caveat worth stating before anyone gets excited: `isTargetDetected` answers
   "has this AI detected that target", which folds in skill, alertness, range
   and reaction time on top of line of sight. It is not a clean LOS primitive
   and would need care -- but it is the only known route to the engine's own
   tree-aware occlusion.

Also dumped, because the cost of looking is one table walk each: `land` (is
there a `profile`? a seabed variant?), `Object.Category`, `coalition`, and the
`Unit`/`Group`/`Controller`/`Airbase` method tables.

PREREQUISITE: `Saved Games/DCS/Config/autoexec.cfg` must contain
`net.allow_dostring_in = { "scripting" }`. Already present on this machine.

THROTTLE: one bridge call per 0.25 s, same discipline as the terrain probe --
these are table walks, not engine work, so cost is not a concern, but the
habit is cheap to keep. Output is prefixed `PetrobrainApiProbe`.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainApiProbe"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25

--: Returns a sorted, comma-joined list of a global table's keys, tagging
--: each with its Lua type so a function is distinguishable from a nested
--: table or an enum value. `%s` is the expression to walk.
local function dumpTable(expr)
    return string.format(
        [[
local ok, t = pcall(function() return %s end)
if not ok or type(t) ~= "table" then
    return "ABSENT|" .. tostring(ok and type(t) or t)
end
local keys = {}
for k, v in pairs(t) do
    local tv = type(v)
    if tv == "number" or tv == "string" or tv == "boolean" then
        keys[#keys + 1] = tostring(k) .. "=" .. tostring(v)
    else
        keys[#keys + 1] = tostring(k) .. ":" .. tv
    end
end
table.sort(keys)
return "OK|" .. tostring(#keys) .. "|" .. table.concat(keys, " ")
]],
        expr
    )
end

--: The method table of a live instance, reached through its metatable --
--: `Unit`, `Controller` and friends expose their methods there rather than
--: on a global of the same name, so `dumpTable("Controller")` alone would
--: miss them.
local function dumpMethods(expr, label)
    return string.format(
        [[
local ok, obj = pcall(function() return %s end)
if not ok or obj == nil then return "ABSENT|%s|" .. tostring(obj) end
local mt = getmetatable(obj)
local src = mt and (mt.__index or mt) or obj
if type(src) ~= "table" then return "ABSENT|%s|metatable " .. type(src) end
local keys = {}
for k, v in pairs(src) do
    keys[#keys + 1] = tostring(k) .. ":" .. type(v)
end
table.sort(keys)
return "OK|%s|" .. tostring(#keys) .. "|" .. table.concat(keys, " ")
]],
        expr,
        label,
        label,
        label
    )
end

local STEPS = {
    { "land", dumpTable("land") },
    { "world", dumpTable("world") },
    { "world.VolumeType", dumpTable("world.VolumeType") },
    { "Object.Category", dumpTable("Object.Category") },
    { "Object_methods", dumpMethods("world.getPlayer()", "Object") },
    { "Unit_methods", dumpMethods("world.getPlayer()", "Unit") },
    { "Group_methods", dumpMethods("world.getPlayer():getGroup()", "Group") },
    {
        "Controller_methods",
        dumpMethods("world.getPlayer():getGroup():getController()", "Controller"),
    },
    { "coalition", dumpTable("coalition") },
    { "Airbase", dumpTable("Airbase") },
    { "Spot", dumpTable("Spot") },
    { "AI", dumpTable("AI") },
}

local petrobrainApiProbe = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local stepIndex = 0

local function logi(message)
    log.write(LOG_PREFIX, log.INFO, message)
end

local function dostring(code)
    local callOk, result, success = pcall(net.dostring_in, "scripting", code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

function petrobrainApiProbe.onSimulationStart()
    simulationRunning = true
    startAt = nil
    stepIndex = 0
    logi("loaded, will dump the API surface " .. START_DELAY_S .. "s after sim start")
end

function petrobrainApiProbe.onSimulationFrame()
    if not simulationRunning or stepIndex > #STEPS then
        return
    end
    local now = DCS.getRealTime()
    if startAt == nil then
        startAt = now + START_DELAY_S
        return
    end
    if now < startAt or now < nextCallAt then
        return
    end
    nextCallAt = now + TICK_INTERVAL_S

    if stepIndex == 0 then
        logi("=== API surface probe start ===")
    end

    stepIndex = stepIndex + 1
    local step = STEPS[stepIndex]
    if step == nil then
        logi("=== API surface probe end ===")
        stepIndex = #STEPS + 1
        return
    end

    local t0 = os.clock()
    local ok, result = dostring(step[2])
    local ms = (os.clock() - t0) * 1000.0
    if not ok then
        logi(step[1] .. ": FAILED " .. tostring(result))
    else
        logi(string.format("%s: ms=%.2f %s", step[1], ms, tostring(result)))
    end
end

function petrobrainApiProbe.onSimulationStop()
    simulationRunning = false
    stepIndex = 0
end

DCS.setUserCallbacks(petrobrainApiProbe)

logi("hook loaded")
