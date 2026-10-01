--[[
Throwaway probe Hook script: do trees block line of sight, tested against two
real vehicles the pilot has placed inside forest?

**This is a probe, not pipeline code.** Deploy, sit ~20 s, read `dcs.log`
(prefix `PetrobrainTreeUnits`), delete.

WHY THIS SUPERSEDES THE PREVIOUS TREE PROBE. That one aimed its rays using
**OSM** forest polygons, and the result -- nothing standing above ground
anywhere in 336 km2 of mapped forest -- carried a weakness I could not remove
from inside the probe: OSM forest is not proof of *DCS* trees. If DCS has no
trees at those coordinates then "nothing found" is vacuous rather than a
negative, and `land.getIP` could not be used to confirm the trees were there
because `getIP` is the call under test. Circular.

**The pilot's setup removes that entirely.** User direction, 2026-10-01:

> *"I'll place two units inside forest, near ownship. One BTR-60 and one
> BTR-70, about 200 m apart, both inside the same forest. Use these units as
> reference."*

Two vehicles, deliberately placed, inside canopy he can see, ~200 m apart. So
the sightline **between them** runs through ~200 m of trees and nothing else --
no terrain to speak of over that distance, no buildings in a forest. If any
scripting call accounts for trees, that line is where it shows. And because
the units are real objects with real positions, the geometry is derived from
ground truth rather than from a polygon that might be wrong.

**It also unlocks the one test previously out of reach.**
`Controller.isTargetDetected` is the AI detection path, the only shipped code
path known to do tree-occluded LOS (`Scripts/AI/Detection.lua` sets
`objects_LOS_test = true` and `trees_LOS_test_T4 = true`, and the user reports
DCS's own AI Petrovich being blocked by trees with the 9K113). Characterising
it needed an AI unit and a target deliberately placed behind cover, which is
mission authoring -- and that is exactly what has now been built. Each BTR's
group controller can be asked about the other.

**One precondition that may not hold, and the probe says so rather than
failing quietly:** `isTargetDetected` is about *enemies*. If both BTRs are on
the same coalition they will never be each other's targets and that half
returns nothing meaningful. The probe reports each unit's coalition
explicitly, so if they need to be put on opposing sides that is visible
immediately rather than inferred from an empty result.

-------------------------------------------------------------------------
WHAT IS MEASURED, AND THE CONTROL
-------------------------------------------------------------------------

Four independent facts per sightline, as in the building test, because no
single one of them identifies a tree:

  1. **terrain-only verdict** -- computed here from `land.getHeight` samples,
     i.e. our own algorithm, the thing we would otherwise ship.
  2. **`land.getIP`** -- `land.getHeight` is read at the intercept's own
     (x, z), and the **delta above local ground** is what counts. A terrain
     hit is ~0 by construction; metres means something is standing there.
  3. **`land.isVisible`** on the same endpoints.
  4. **SEGMENT `searchObjects`** -- known to return buildings. A blocker that
     `getIP` sees while this finds no scenery is, by elimination, not a
     building.

**The control is the same geometry moved to open ground.** The BTR-to-BTR
vector is translated to 205853, 35282 -- a point with no landcover, settlement
or water mapped within 400 m, found from world-model's own store on this box.
Same length, same relative endpoint heights, no trees. If the forest line
differs from its translated twin, the difference is cover and not geometry.
That is the shape that made the building finding believable.

**Prediction, written down before the flight so it cannot be fitted
afterwards:** given `getIP` and `isVisible` have both already been shown
terrain-only across 40 rays through 40 buildings and 336 km2 of forest, the
expected result is that all four facts come back identical in forest and in
the open, and that the only thing distinguishing them is
`Controller.isTargetDetected`. If instead the forest line blocks, then the
earlier negative was an artefact of OSM polygons not matching DCS trees, and
that is worth knowing.

PREREQUISITE: `net.allow_dostring_in = { "scripting" }`. Already present.
THROTTLE: one bridge call per 0.25 s, 60 ms abort ceiling. Costs logged are
**raw call milliseconds with NO baseline subtracted** -- not per-item figures.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainTreeUnits"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25
local ABORT_MS = 60.0

--: Open ground the control geometry is translated to. No landcover,
--: settlement or water mapped within 400 m (world-model store, this box).
local OPEN_X, OPEN_Z = 205853.0, 35282.0

--: Corrected ridge pair -- A crest standing 926 m above the higher endpoint,
--: nothing built within 1200 m. The 2026-09-29 20:09 flight tested this with
--: row/col swapped in the site search and so fired at gentle hills, where DCS
--: reported only a 4 m margin; SEGMENT returned 0 but a 4 m margin against a
--: call that may carry a tolerance proves little. Carried here to finish that
--: question properly: does SEGMENT catch terrain?
local RIDGE_AX, RIDGE_AZ = 341088.0, 167559.0
local RIDGE_BX, RIDGE_BZ = 341088.0, 173559.0

--: Finds the pilot's reference vehicles. Matches on "BTR" in the type name
--: rather than an exact string, because DCS's own type names for these
--: hulls are not worth guessing at from memory -- so every unit found is
--: reported with its exact `getTypeName()`, and the match stays loose.
local FIND_UNITS_CODE = [[
local out, n = {}, 0
for _, side in pairs({ coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE }) do
    for _, grp in ipairs(coalition.getGroups(side) or {}) do
        for _, u in ipairs(grp:getUnits() or {}) do
            if u and u:isExist() then
                n = n + 1
                local okN, tn = pcall(function() return u:getTypeName() end)
                tn = okN and tostring(tn) or "?"
                if tn:upper():find("BTR") then
                    local okP, p = pcall(function() return u:getPoint() end)
                    local okH, gh = pcall(land.getHeight, { x = p.x, y = p.z })
                    local okS, st = pcall(land.getSurfaceType, { x = p.x, y = p.z })
                    out[#out + 1] = string.format(
                        "%s|%s|side%d|%.1f|%.1f|unitY%.1f|groundY%s|surf%s",
                        u:getName(), tn, side, p.x, p.z, p.y,
                        okH and string.format("%.1f", gh) or "ERR",
                        okS and tostring(st) or "ERR")
                end
            end
        end
    end
end
if #out == 0 then return "ERR|no unit with BTR in its type name among " .. n .. " units" end
return "OK|" .. tostring(n) .. "|" .. table.concat(out, ";")
]]

--: The four facts over one sightline. `label` only rides through to the
--: output so a reader does not have to match lines up by position.
local function sightlineCode(ax, az, bx, bz, eyeA, eyeB, label)
    return string.format(
        [[
local LABEL = %q
local ax, az, bx, bz, ea, eb = %f, %f, %f, %f, %f, %f
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
local okB, by = pcall(land.getHeight, { x = bx, y = bz })
if not (okA and okB and ay and by) then return "ERR|endpoint getHeight failed" end
local from = { x = ax, y = ay + ea, z = az }
local to = { x = bx, y = by + eb, z = bz }
local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)

-- (1) our own terrain verdict, and the worst intrusion above the line
local maxAbove, tBlocked = -1e9, false
for k = 1, 39 do
    local t = k / 40
    local okS, sh = pcall(land.getHeight, { x = ax + (bx - ax) * t, y = az + (bz - az) * t })
    if okS and sh then
        local above = sh - (from.y + (to.y - from.y) * t)
        if above > maxAbove then maxAbove = above end
        if above > 0 then tBlocked = true end
    end
end

-- (2) getIP, and how far its intercept stands above local ground
local ipTxt = "none"
local dx, dy, dz = bx - ax, to.y - from.y, bz - az
local dl = math.sqrt(dx * dx + dy * dy + dz * dz)
local okI, ip = pcall(land.getIP, from, { x = dx / dl, y = dy / dl, z = dz / dl }, len + 20)
if okI and ip ~= nil then
    local okH, g2 = pcall(land.getHeight, { x = ip.x, y = ip.z })
    local d = (okH and g2) and (ip.y - g2) or -999
    ipTxt = string.format("hit@%%.0fm/aboveGround%%+.1fm",
        math.sqrt((ip.x - ax) ^ 2 + (ip.z - az) ^ 2), d)
end

-- (3) isVisible
local okV, vis = pcall(land.isVisible, from, to)

-- (4) SEGMENT scenery -- separates tree from building
local scen, names = 0, {}
pcall(function()
    world.searchObjects(Object.Category.SCENERY,
        { id = world.VolumeType.SEGMENT, params = { from = from, to = to } },
        function(obj)
            scen = scen + 1
            if #names < 3 then
                local okN, nm = pcall(function() return obj:getTypeName() end)
                names[#names + 1] = okN and tostring(nm) or "?"
            end
            return true
        end)
end)

return string.format(
    "%%s len=%%.0fm | terrainBlocked=%%s maxTerrainAboveLine=%%+.1fm | getIP=%%s"
        .. " | isVisible=%%s | SEGMENT=%%d[%%s]",
    LABEL, len, tostring(tBlocked), maxAbove, ipTxt,
    (okV and tostring(vis) or "ERR"), scen, table.concat(names, ","))
]],
        label,
        ax,
        az,
        bx,
        bz,
        eyeA,
        eyeB
    )
end

--: The AI detection path, asked in both directions. This is the only shipped
--: route known to test trees; see the header for what it folds in and why it
--: is characterised rather than consumed.
local function detectionCode(nameA, nameB)
    return string.format(
        [[
local a = Unit.getByName(%q)
local b = Unit.getByName(%q)
if a == nil or b == nil then return "ERR|unit lookup failed" end
local function ask(fromUnit, target, label)
    local okG, grp = pcall(function() return fromUnit:getGroup() end)
    if not okG or grp == nil then return label .. "=noGroup" end
    local okC, ctrl = pcall(function() return grp:getController() end)
    if not okC or ctrl == nil then return label .. "=noController" end
    local okD, det, vis, lastT, typ, dist = pcall(function()
        return ctrl:isTargetDetected(target, Controller.Detection.VISUAL)
    end)
    local n = -1
    local okL, lst = pcall(function()
        return ctrl:getDetectedTargets(Controller.Detection.VISUAL)
    end)
    if okL and type(lst) == "table" then n = #lst end
    if not okD then return label .. "=ERR(" .. tostring(det) .. ") visualTargets=" .. n end
    return string.format("%%s=detected:%%s visible:%%s dist:%%s visualTargets:%%d",
        label, tostring(det), tostring(vis), tostring(dist), n)
end
return "OK|" .. ask(a, b, "A_sees_B") .. " | " .. ask(b, a, "B_sees_A")
]],
        nameA,
        nameB
    )
end

local petrobrainTreeUnits = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local phase = "locate"
local plan = nil
local planIndex = 0
local ownX, ownZ = nil, nil

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

local function run(label, code)
    local t0 = os.clock()
    local ok, result = dostring(code)
    local ms = (os.clock() - t0) * 1000.0
    if not ok then
        logi(label .. ": FAILED " .. tostring(result))
    else
        logi(string.format("%s: ms=%.2f %s", label, ms, tostring(result)))
    end
    return ms, ok, result
end

--: Builds the sightline plan once the vehicles' real positions are known.
local function buildPlan(units)
    local a, b = units[1], units[2]
    local steps = {}

    -- THE test: through ~200 m of canopy, vehicle to vehicle at 2 m
    steps[#steps + 1] = {
        "FOREST_BTR_to_BTR",
        sightlineCode(a.x, a.z, b.x, b.z, 2.0, 2.0, "forest:" .. a.tn .. "->" .. b.tn),
    }

    -- The control: identical vector, translated to open ground
    local dx, dz = b.x - a.x, b.z - a.z
    steps[#steps + 1] = {
        "OPEN_CONTROL_same_vector",
        sightlineCode(OPEN_X, OPEN_Z, OPEN_X + dx, OPEN_Z + dz, 2.0, 2.0, "open:translated"),
    }

    -- The realistic case: the aircraft looking down at each vehicle
    if ownX ~= nil then
        steps[#steps + 1] = {
            "OWNSHIP_to_BTR_A",
            sightlineCode(ownX, ownZ, a.x, a.z, 30.0, 2.0, "ownship->" .. a.tn),
        }
        steps[#steps + 1] = {
            "OWNSHIP_to_BTR_B",
            sightlineCode(ownX, ownZ, b.x, b.z, 30.0, 2.0, "ownship->" .. b.tn),
        }
    end

    -- The AI path, both directions
    steps[#steps + 1] = { "AI_DETECTION", detectionCode(a.name, b.name) }

    -- Finish the SEGMENT-vs-terrain question on a ridge worth the name
    steps[#steps + 1] = {
        "SEGMENT_vs_TERRAIN_ridge_crest+926m",
        sightlineCode(RIDGE_AX, RIDGE_AZ, RIDGE_BX, RIDGE_BZ, 2.0, 2.0, "ridge:926m"),
    }
    return steps
end

--: Parses one `FIND_UNITS_CODE` record. Returns nil rather than raising on a
--: malformed field, so a surprise in the payload degrades to "units not
--: usable" with the raw line already logged, instead of killing the probe.
local function parseUnit(rec)
    local name, tn, side, x, z = rec:match("^([^|]*)|([^|]*)|side(%d+)|([%-%d%.]+)|([%-%d%.]+)|")
    if name == nil then
        return nil
    end
    return { name = name, tn = tn, side = tonumber(side), x = tonumber(x), z = tonumber(z) }
end

function petrobrainTreeUnits.onSimulationStart()
    simulationRunning = true
    startAt = nil
    phase = "locate"
    plan = nil
    planIndex = 0
    ownX, ownZ = nil, nil
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainTreeUnits.onSimulationFrame()
    if not simulationRunning or phase == "done" then
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

    if phase == "locate" then
        local _, ok, result = run(
            "locate_ownship",
            [[
local ok, u = pcall(world.getPlayer)
if not ok or u == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return u:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
return string.format("OK|%.1f|%.1f", p.x, p.z)
]]
        )
        local x, z = tostring(result):match("^OK|([%-%d%.]+)|([%-%d%.]+)$")
        if ok and x ~= nil then
            ownX, ownZ = tonumber(x), tonumber(z)
        end
        phase = "find"
        return
    end

    if phase == "find" then
        logi("=== tree LOS (unit-referenced) probe start ===")
        local _, ok, result = run("find_BTR_units", FIND_UNITS_CODE)
        local units = {}
        if ok then
            local body = tostring(result):match("^OK|%d+|(.*)$")
            if body then
                for rec in (body .. ";"):gmatch("([^;]+);") do
                    local u = parseUnit(rec)
                    if u then
                        units[#units + 1] = u
                    end
                end
            end
        end
        if #units < 2 then
            logi(
                "find_BTR_units: need 2 BTR units, parsed "
                    .. #units
                    .. " -- the raw line above is the truth; sightline steps skipped"
            )
            phase = "done"
            logi("=== probe end (units not usable) ===")
            return
        end
        local sideNote = (units[1].side == units[2].side)
            and (" SAME COALITION (side"
                .. units[1].side
                .. ") -- isTargetDetected is about enemies, so the AI half will be empty;"
                .. " put them on opposing sides to get that answer")
            or " opposing coalitions -- the AI detection half is valid"
        logi(
            string.format(
                "using %s(%s) at %.0f,%.0f and %s(%s) at %.0f,%.0f --%s",
                units[1].name,
                units[1].tn,
                units[1].x,
                units[1].z,
                units[2].name,
                units[2].tn,
                units[2].x,
                units[2].z,
                sideNote
            )
        )
        plan = buildPlan(units)
        planIndex = 0
        phase = "run"
        return
    end

    planIndex = planIndex + 1
    local step = plan[planIndex]
    if step == nil then
        logi("=== tree LOS (unit-referenced) probe end ===")
        phase = "done"
        return
    end
    local ms = run(step[1], step[2])
    if ms > ABORT_MS then
        logi(string.format("ABORT: %s took %.1f ms (ceiling %.1f)", step[1], ms, ABORT_MS))
        phase = "done"
    end
end

function petrobrainTreeUnits.onSimulationStop()
    simulationRunning = false
    phase = "locate"
    plan = nil
end

DCS.setUserCallbacks(petrobrainTreeUnits)

logi("hook loaded")
