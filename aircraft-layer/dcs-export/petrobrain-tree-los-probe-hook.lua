--[[
Throwaway probe Hook script: does ANY scripting call see trees for line of
sight?

**This is a probe, not pipeline code.** Deploy, sit ~20 s, read `dcs.log`
(prefix `PetrobrainTreeLos`), delete.

WHY THIS REOPENS SOMETHING ALREADY CLOSED. `aircraft-layer/research/
2026-09-29-bridge-terrain-probe-results.md` recorded that trees are not
scenery objects (ten flights of `searchObjects`, never one returned) and that
`land.isVisible` is terrain-only. Both still stand. **What changed is the
requirement**, per the user:

> *"'vehicle under trees is undetectable at any range from any optic' -- in a
> forest, yes very much. But if it's just a couple of trees or a line of trees
> along a road, then tree LOS really matters. We must investigate if there is
> any way to get LOS considering trees. We don't need to know individual tree
> placement... but need to know if they block LOS."*

A statistical model over an OSM forest polygon is honest for *forest*. It
cannot express "this sightline is blocked and the one ten metres left is not",
which is what a treeline along a road is -- and OSM may carry no polygon there
at all. That is discrete occlusion, and a Mi-24P attacking along a road meets
it constantly.

**The engine demonstrably has the data**: the F10 map draws individual trees,
flying into one destroys the aircraft, and DCS's own AI Petrovich is blocked by
trees when using the 9K113 -- that last being `Scripts/AI/Detection.lua`'s
`trees_LOS_test_T4`. So at least one shipped code path does a tree-occluded LOS
test. The open question is only whether a *scripting* call exposes it.

**`land.getIP` is the candidate, and it was never actually pointed at trees.**
It was fired twice before, but blind -- 8 rays on compass octants from wherever
the aircraft happened to be. Every ray fitted a pure-terrain model to within
0.8 m, which proves the call returns real geometry and proves nothing at all
about trees if no ray crossed canopy. This probe aims it deliberately.

-------------------------------------------------------------------------
THE DISCRIMINATOR, which is the part worth getting right
-------------------------------------------------------------------------

For each ray, four independent facts are collected, and it is their
combination that identifies a tree rather than any one of them:

  1. **terrain-only verdict** -- computed here from `land.getHeight` samples
     along the ray, i.e. our own algorithm, the thing we would otherwise ship.
  2. **`land.getIP`** -- if it returns an intercept, `land.getHeight` is read
     at that intercept's own (x, z) and the **delta above local ground** is
     what matters. A terrain hit has delta ~0 by construction. A delta of
     metres means the ray struck something standing above the ground.
  3. **`land.isVisible`** on the same endpoints -- known terrain-only, carried
     as a same-payload reference.
  4. **SEGMENT `searchObjects`** on the same line -- known to return buildings.
     **This is what separates a tree from a building**: a blocker that getIP
     sees while the segment search returns no scenery is, by elimination, not
     a building.

So: **terrain says clear + getIP hits well above ground + no scenery on the
line = a tree.** Any other combination is something else, and is reported as
such rather than being read as a positive.

**Geometry is the realistic case, not a convenient one.** Each ray runs from
30 m above the site down to 2 m above ground 300 m away -- a Mi-24P looking at
a vehicle. On flat open ground that line never approaches the surface, so the
control is clean; through canopy it passes straight through the 15-25 m band
where trees live.

**Sites, and why these.** Ray geometry is derived from ground whose cover is
known, and every site has a matched control, because a positive without a
control is what made the earlier building finding worth believing:

  - **FOREST_A** 203782, 43009 -- a **251 km2** OSM forest polygon, interior
    point **4.3 km** from the nearest edge. Cannot be an edge artefact.
  - **FOREST_B** 221119, 98791 -- 85 km2, 3.1 km deep. A second polygon, so
    one wrong polygon cannot carry the result.
  - **OPEN** 205853, 35282 -- **no landcover, settlement or water mapped
    within 400 m**, 8 km from FOREST_A. The control.
  - **OWNSHIP** -- wherever the aircraft is, as an opportunistic extra.

All four came from `world-model/data/world-model/syria-full.sqlite`'s own OSM
landcover layer, queried on this box. **OSM forest is not proof of DCS trees**
-- that is exactly why fact (2) above is the evidence and the polygon is only
how the ray was aimed.

**A clean negative is a real result here**, not a formality: if getIP shows
nothing above ground inside 251 km2 of mapped forest, then no scripting call
reaches tree geometry and the statistical-landcover route is the only one,
which settles the design question either way.

ALSO DUMPED: `land.SurfaceType`'s members. It was never enumerated, and if the
engine has a forest surface type that is a direct, cheap signal.

ON COST, since the Mac session asked: this probe reports **raw per-call
milliseconds with NO baseline subtracted**. They are not per-item figures and
must not be read as such -- each call bundles setup, ~12 `getHeight` samples
per ray, and three different API calls. Per-item costs for `getHeight`,
`isVisible` and SEGMENT are already measured properly elsewhere.

PREREQUISITE: `net.allow_dostring_in = { "scripting" }`. Already present.
THROTTLE: one bridge call per 0.25 s, 60 ms abort ceiling.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainTreeLos"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25
local ABORT_MS = 60.0

--: Metres a `getIP` intercept must stand above local ground before it counts
--: as a non-terrain blocker. Generous: terrain hits sit at ~0 by
--: construction, and DCS trees are 15-25 m, so anything in between is
--: unambiguous either way.
local BLOCKER_DELTA_M = 4.0

local RAYS = 8
local RAY_LEN_M = 300
local EYE_M = 30 -- observer height above ground
local TARGET_M = 2 -- target height above ground

local probeX, probeZ = nil, nil

local LOCATE_CODE = [[
local ok, unit = pcall(world.getPlayer)
if not ok or unit == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return unit:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
return string.format("OK|%.1f|%.1f", p.x, p.z)
]]

local SURFACETYPE_CODE = [[
local ok, t = pcall(function() return land.SurfaceType end)
if not ok or type(t) ~= "table" then return "ABSENT" end
local keys = {}
for k, v in pairs(t) do keys[#keys + 1] = tostring(k) .. "=" .. tostring(v) end
table.sort(keys)
return "OK|" .. table.concat(keys, " ")
]]

--: One site, `RAYS` rays. See the header for what each of the four facts is
--: for and why it takes all of them to name a tree.
local function siteCode(x, z)
    return string.format(
        [[
local cx, cz = %f, %f
local RAYS, LEN, EYE, TGT, DELTA = %d, %d, %d, %d, %f
local okG, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okG or gy == nil then return "ERR|getHeight failed at site" end
local surf = "?"
local okST, st = pcall(land.getSurfaceType, { x = cx, y = cz })
if okST and st then surf = tostring(st) end

local treeLike, terrainHit, visBlocked, sceneryRays, clearAll = 0, 0, 0, 0, 0
local maxDelta, examples = 0, {}

for i = 1, RAYS do
    local ang = (i - 1) * 2 * math.pi / RAYS
    local tx = cx + math.cos(ang) * LEN
    local tz = cz + math.sin(ang) * LEN
    local okT, ty = pcall(land.getHeight, { x = tx, y = tz })
    if okT and ty then
        local fromY, toY = gy + EYE, ty + TGT
        local from = { x = cx, y = fromY, z = cz }
        local to = { x = tx, y = toY, z = tz }

        -- (1) terrain-only verdict, our own algorithm
        local tBlocked = false
        for s = 1, 11 do
            local t = s / 12
            local okS, sh = pcall(land.getHeight,
                { x = cx + (tx - cx) * t, y = cz + (tz - cz) * t })
            if okS and sh and sh > fromY + (toY - fromY) * t then tBlocked = true break end
        end

        -- (2) getIP, and how far its intercept stands above local ground
        local dx, dy, dz = tx - cx, toY - fromY, tz - cz
        local dlen = math.sqrt(dx * dx + dy * dy + dz * dz)
        local delta, ipDist = nil, nil
        local okI, ip = pcall(land.getIP, from,
            { x = dx / dlen, y = dy / dlen, z = dz / dlen }, LEN + 20)
        if okI and ip ~= nil then
            local okH, groundAtIp = pcall(land.getHeight, { x = ip.x, y = ip.z })
            if okH and groundAtIp then
                delta = ip.y - groundAtIp
                ipDist = math.sqrt((ip.x - cx) ^ 2 + (ip.z - cz) ^ 2)
            end
        end

        -- (3) isVisible, same endpoints
        local okV, vis = pcall(land.isVisible, from, to)
        local vBlocked = (okV and vis == false)

        -- (4) SEGMENT scenery on the same line -- separates tree from building
        local scenery = 0
        pcall(function()
            world.searchObjects(Object.Category.SCENERY,
                { id = world.VolumeType.SEGMENT, params = { from = from, to = to } },
                function() scenery = scenery + 1 return true end)
        end)

        if delta ~= nil and delta > maxDelta then maxDelta = delta end
        if vBlocked then visBlocked = visBlocked + 1 end
        if scenery > 0 then sceneryRays = sceneryRays + 1 end

        if tBlocked then
            terrainHit = terrainHit + 1
        elseif delta ~= nil and delta > DELTA and scenery == 0 then
            -- terrain clear, something standing above ground, not scenery
            treeLike = treeLike + 1
            if #examples < 3 then
                examples[#examples + 1] =
                    string.format("az%%d@%%.0fm+%%.1fm", i, ipDist or -1, delta)
            end
        else
            clearAll = clearAll + 1
        end
    end
end
return string.format(
    "surf=%%s groundY=%%.1f | TREE_LIKE=%%d terrainBlocked=%%d clear=%%d"
        .. " | visBlocked=%%d sceneryRays=%%d maxDeltaAboveGround=%%.1fm | %%s",
    surf, gy, treeLike, terrainHit, clearAll, visBlocked, sceneryRays, maxDelta,
    table.concat(examples, ";"))
]],
        x,
        z,
        RAYS,
        RAY_LEN_M,
        EYE_M,
        TARGET_M,
        BLOCKER_DELTA_M
    )
end

--: Sites picked from world-model's own OSM landcover on the Windows box --
--: see the header for the areas and edge depths, and for why OSM forest is
--: how the ray is aimed rather than the evidence itself.
local SITES = {
    { "FOREST_A_251km2_deep4.3km", 203782.0, 43009.0 },
    { "FOREST_B_85km2_deep3.1km", 221119.0, 98791.0 },
    { "OPEN_CONTROL_nothing_within_400m", 205853.0, 35282.0 },
}

local petrobrainTreeLos = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local stepIndex = 0
local located = false

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
    return ms
end

function petrobrainTreeLos.onSimulationStart()
    simulationRunning = true
    startAt = nil
    stepIndex = 0
    located = false
    probeX, probeZ = nil, nil
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainTreeLos.onSimulationFrame()
    if not simulationRunning or stepIndex < 0 then
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

    if not located then
        local t0 = os.clock()
        local ok, result = dostring(LOCATE_CODE)
        local ms = (os.clock() - t0) * 1000.0
        local x, z = tostring(result):match("^OK|([%-%d%.]+)|([%-%d%.]+)$")
        if ok and x ~= nil then
            probeX, probeZ = tonumber(x), tonumber(z)
            logi(string.format("locate_ownship: ms=%.2f centre=%.1f,%.1f", ms, probeX, probeZ))
        else
            logi("locate_ownship: FAILED (" .. tostring(result) .. ") -- ownship site skipped")
        end
        located = true
        logi("=== tree LOS probe start ===")
        logi(
            string.format(
                "geometry: %d rays, %d m, observer +%d m -> target +%d m; blocker threshold %.1f m"
                    .. " above local ground. Costs below are RAW call ms, NO baseline subtracted.",
                RAYS,
                RAY_LEN_M,
                EYE_M,
                TARGET_M,
                BLOCKER_DELTA_M
            )
        )
        return
    end

    stepIndex = stepIndex + 1

    if stepIndex == 1 then
        run("land.SurfaceType", SURFACETYPE_CODE)
        return
    end

    local site = SITES[stepIndex - 1]
    if site ~= nil then
        local ms = run(site[1], siteCode(site[2], site[3]))
        if ms > ABORT_MS then
            logi(string.format("ABORT: %.1f ms over ceiling %.1f", ms, ABORT_MS))
            stepIndex = -1
        end
        return
    end

    if stepIndex == #SITES + 2 and probeX ~= nil then
        run("OWNSHIP_opportunistic", siteCode(probeX, probeZ))
        return
    end

    logi("=== tree LOS probe end ===")
    stepIndex = -1
end

function petrobrainTreeLos.onSimulationStop()
    simulationRunning = false
    stepIndex = 0
    located = false
end

DCS.setUserCallbacks(petrobrainTreeLos)

logi("hook loaded")
