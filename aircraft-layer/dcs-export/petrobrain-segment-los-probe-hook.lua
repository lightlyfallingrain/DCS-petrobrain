--[[
Throwaway probe Hook script: can a SEGMENT volume search give us the
building-aware line of sight that `land.isVisible` does not?

**This is a probe, not pipeline code.** Deploy by hand, sit in a mission for
~20 s, read `dcs.log` (prefix `PetrobrainSegLos`), delete the file.

WHERE THIS CAME FROM. `land.isVisible` was shown terrain-only on 2026-09-29 --
40 rays fired deliberately through 40 buildings, 0 blocked
(`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
Finding 12). The user then asked whether *any* DCS call accounts for buildings
and trees. Rather than answer from memory, the API surface was dumped from the
running engine, and it named three things worth testing:

  1. **`world.VolumeType.SEGMENT = 0`.** `world.searchObjects` takes a volume
     and a segment volume is a line. If a segment search along a sightline
     returns the scenery intersecting it, that is building occlusion computed
     by DCS's own intersection test -- and it removes the type-name -> size
     table that is otherwise the one thing standing between us and an
     occluder layer. **This is the cheap win and the main point of this probe.**
  2. **`land.profile`.** A terrain profile along a line, in one call. Our own
     LOS currently spends 20+ `getHeight` calls per sightline; if `profile`
     returns the same information for one call it is a straight upgrade to
     `world-model`'s `line_of_sight_clear`, independent of anything to do with
     buildings.
  3. **`Controller.isTargetDetected` / `getDetectedTargets` / `Controller.
     Detection`.** The AI detection path, which `Scripts/AI/Detection.lua`
     configures with `objects_LOS_test = true` and `trees_LOS_test_T4 = true`
     -- so the engine *can* test trees; only the `land.*` calls do not. Dumped
     here rather than used, because it answers "has this AI detected that
     target", folding skill/alertness/range/reaction time on top of line of
     sight. It is not a clean LOS primitive and must not be treated as one.

WHAT WOULD MAKE THE SEGMENT TEST CONVINCING, since the last round's lesson was
that a positive with no control is worth little:

  - **through a known building** -- segment endpoints derived from a building's
    own reported position, 60 m either side. Expect: the building comes back.
  - **the same length of open ground** -- a segment offset well away from any
    scenery. Expect: nothing comes back.

A hit in the first and a miss in the second is the result. A hit in both means
the search is returning everything near the line rather than what intersects
it, which would be a different (and much less useful) thing -- so the open-
ground control is what tells those two apart.

**Trees are expected to come back empty regardless.** They are not scenery
objects -- six flights of `searchObjects` have never returned one -- so this
probe cannot settle trees, and says so rather than implying otherwise. If
buildings work this way, trees remain OSM landcover's job.

PREREQUISITE: `net.allow_dostring_in = { "scripting" }` in
`Saved Games/DCS/Config/autoexec.cfg`. Already present on this machine.

THROTTLE: one bridge call per 0.25 s, and every step is bounded -- the
expensive call shape is already known (scenery search is superlinear: 126
objects at 300 m cost 1 ms, 590 at 600 m cost 18 ms), so searches here stay
at or below 200 m.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainSegLos"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25
local ABORT_MS = 60.0

local probeX, probeZ = -171265.8281, 25122.6621 -- Mezzeh fallback

local LOCATE_CODE = [[
local ok, unit = pcall(world.getPlayer)
if not ok or unit == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return unit:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
return string.format("OK|%.1f|%.1f", p.x, p.z)
]]

--: The test and its control in one call, so both see identical engine state.
--: Returns a compact line rather than a table: `dostring_in` can only carry
--: one scalar across the Hook boundary.
local function segmentCode()
    return string.format(
        [[
local cx, cz = %f, %f
local okH, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okH or gy == nil then return "ERR|getHeight failed at centre" end

-- 1. find a building to aim through
local target = nil
local okS, err = pcall(function()
    world.searchObjects(Object.Category.SCENERY,
        { id = world.VolumeType.SPHERE,
          params = { point = { x = cx, y = gy, z = cz }, radius = 200 } },
        function(obj)
            if target ~= nil then return false end
            local okP, p = pcall(function() return obj:getPoint() end)
            local okN, n = pcall(function() return obj:getTypeName() end)
            if okP and p then target = { p.x, p.z, okN and tostring(n) or "?" } end
            return true
        end)
end)
if not okS then return "ERR|sphere search: " .. tostring(err) end
if target == nil then return "ERR|no scenery within 200 m" end

-- 2. SEGMENT along a line straight through it
local function segHits(ax, az, ex, ez, ay, ey)
    local hits, names = 0, {}
    local ok, e = pcall(function()
        world.searchObjects(Object.Category.SCENERY,
            { id = world.VolumeType.SEGMENT,
              params = { from = { x = ax, y = ay, z = az },
                         to   = { x = ex, y = ey, z = ez } } },
            function(obj)
                hits = hits + 1
                if #names < 3 then
                    local okN, n = pcall(function() return obj:getTypeName() end)
                    names[#names + 1] = okN and tostring(n) or "?"
                end
                return true
            end)
    end)
    if not ok then return -1, tostring(e) end
    return hits, table.concat(names, ",")
end

local bx, bz, bname = target[1], target[2], target[3]
local dx, dz = bx - cx, bz - cz
local len = math.sqrt(dx * dx + dz * dz)
if len < 1 then dx, dz, len = 1, 0, 1 end
dx, dz = dx / len, dz / len
local ax, az = bx - dx * 60, bz - dz * 60
local ex, ez = bx + dx * 60, bz + dz * 60
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
local okE, ey = pcall(land.getHeight, { x = ex, y = ez })
if not (okA and okE and ay and ey) then return "ERR|endpoint getHeight failed" end

local throughHits, throughNames = segHits(ax, az, ex, ez, ay + 2, ey + 2)

-- 3. CONTROL: same 120 m length, 3 km away, where there should be nothing
local ox, oz = cx + 3000, cz + 3000
local okO, oy = pcall(land.getHeight, { x = ox, y = oz })
local okO2, oy2 = pcall(land.getHeight, { x = ox + 120, y = oz })
local openHits, openNames = -2, "skipped"
if okO and okO2 and oy and oy2 then
    openHits, openNames = segHits(ox, oz, ox + 120, oz, oy + 2, oy2 + 2)
end

-- 4. does land.isVisible agree? (known terrain-only -- included as a
--    same-call reference point, not as a new question)
local okV, vis = pcall(land.isVisible,
    { x = ax, y = ay + 2, z = az }, { x = ex, y = ey + 2, z = ez })

return string.format(
    "target=%%s THROUGH_BUILDING_hits=%%d[%%s] OPEN_GROUND_hits=%%d[%%s] isVisible=%%s",
    bname, throughHits, throughNames, openHits, openNames,
    (okV and tostring(vis) or "ERR"))
]],
        probeX,
        probeZ
    )
end

--: `land.profile` -- shape, length and cost. If this returns the terrain
--: along a line in one call it replaces 20+ `getHeight` calls per sightline
--: in `world-model`'s `line_of_sight_clear`.
local function profileCode()
    return string.format(
        [[
local cx, cz = %f, %f
local okH, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okH or gy == nil then return "ERR|getHeight failed" end
local from = { x = cx, y = gy + 2, z = cz }
local to = { x = cx + 1000, y = gy + 2, z = cz }
local ok, prof = pcall(land.profile, from, to)
if not ok then return "ERR|" .. tostring(prof) end
if type(prof) ~= "table" then return "ERR|returned " .. type(prof) end
local n = #prof
if n == 0 then return "OK|empty table" end
local first, last = prof[1], prof[n]
local function fmt(p)
    if type(p) ~= "table" then return tostring(p) end
    return string.format("(%%.1f,%%.1f,%%.1f)", p.x or -1, p.y or -1, p.z or -1)
end
return string.format("OK|points=%%d spacing~%%.1fm first=%%s last=%%s",
    n, 1000 / math.max(n - 1, 1), fmt(first), fmt(last))
]],
        probeX,
        probeZ
    )
end

local WEATHER_CODE = [[
local ok, w = pcall(function() return world.weather end)
if not ok or type(w) ~= "table" then return "ABSENT" end
local keys = {}
for k, v in pairs(w) do keys[#keys + 1] = tostring(k) .. ":" .. type(v) end
table.sort(keys)
local extra = ""
local okF, fog = pcall(function() return world.weather.getFogThickness() end)
if okF then extra = " getFogThickness()=" .. tostring(fog) end
local okV, vis = pcall(function() return world.weather.getFogVisibilityDistance() end)
if okV then extra = extra .. " getFogVisibilityDistance()=" .. tostring(vis) end
return "OK|" .. table.concat(keys, " ") .. "|" .. extra
]]

local DETECTION_CODE = [[
local ok, d = pcall(function() return Controller.Detection end)
if not ok or type(d) ~= "table" then return "ABSENT" end
local keys = {}
for k, v in pairs(d) do keys[#keys + 1] = tostring(k) .. "=" .. tostring(v) end
table.sort(keys)
return "OK|" .. table.concat(keys, " ")
]]

local petrobrainSegLos = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local stepIndex = 0
local aborted = false

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

--: Built after `locate_ownship` resolves, so every step uses the aircraft's
--: own position rather than a coordinate picked blind.
local function stepsAfterLocate()
    return {
        { "SEGMENT_los", segmentCode() },
        { "land_profile", profileCode() },
        { "world_weather", WEATHER_CODE },
        { "Controller_Detection", DETECTION_CODE },
    }
end

local steps = nil

function petrobrainSegLos.onSimulationStart()
    simulationRunning = true
    startAt = nil
    stepIndex = 0
    steps = nil
    aborted = false
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainSegLos.onSimulationFrame()
    if not simulationRunning or aborted then
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

    local label, code
    if steps == nil then
        label, code = "locate_ownship", LOCATE_CODE
    else
        stepIndex = stepIndex + 1
        local step = steps[stepIndex]
        if step == nil then
            logi("=== segment-LOS probe end ===")
            aborted = true
            return
        end
        label, code = step[1], step[2]
    end

    local t0 = os.clock()
    local ok, result = dostring(code)
    local ms = (os.clock() - t0) * 1000.0

    if not ok then
        logi(label .. ": FAILED " .. tostring(result))
    else
        logi(string.format("%s: ms=%.2f %s", label, ms, tostring(result)))
    end

    if steps == nil then
        local x, z = tostring(result):match("^OK|([%-%d%.]+)|([%-%d%.]+)$")
        if x ~= nil then
            probeX, probeZ = tonumber(x), tonumber(z)
            logi(string.format("centre=%.1f,%.1f (ownship)", probeX, probeZ))
        else
            logi(string.format("falling back to Mezzeh at %.1f,%.1f", probeX, probeZ))
        end
        logi("=== segment-LOS probe start ===")
        steps = stepsAfterLocate()
        stepIndex = 0
    end

    if ms > ABORT_MS then
        logi(string.format("ABORT: %s took %.1f ms (ceiling %.1f)", label, ms, ABORT_MS))
        aborted = true
    end
end

function petrobrainSegLos.onSimulationStop()
    simulationRunning = false
    steps = nil
    stepIndex = 0
end

DCS.setUserCallbacks(petrobrainSegLos)

logi("hook loaded")
