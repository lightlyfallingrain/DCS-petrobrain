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

--: Does a SEGMENT search catch TERRAIN, or only scenery?
--:
--: The Mac session's question, and a fair one: the DCS-driven LOS design
--: uses `SEGMENT` for buildings AND `land.isVisible` for terrain, on the
--: assumption that SEGMENT ignores terrain because terrain is not a scenery
--: object. **That assumption is inferred and has never been tested** --
--: nobody has fired a SEGMENT ray through a hill. It is the same shape of
--: inference that turned out wrong when `isVisible` was assumed to see
--: buildings. If SEGMENT does catch terrain, the LOS verdict is one call
--: rather than two and a whole stage of that plan disappears.
--:
--: Geometry is not plausible-looking, it is provable, taken from
--: `world-model`'s own elevation grid on this box:
--:
--:   - **RIDGE**: A(341088, 167559) h=1689 -> B(341088, 173559) h=1595,
--:     6 km apart, profile 1689/1875/2133/**2615**/2229/1837/1595 -- a crest
--:     standing **926 m above the higher endpoint**. A sightline at 2 m AGL
--:     is buried under most of a kilometre of rock; no grid error survives
--:     that margin.
--:
--:     **The first attempt at this fired at the wrong place.** The grid is
--:     indexed `x = origin_x + row*spacing`, `z = origin_z + col*spacing`
--:     (`store/reader.py:sample_grid`), and the site search had row and col
--:     swapped -- so the 2026-09-29 20:09 flight aimed at gentle hills and
--:     DCS reported the line blocked by only **4 m**, not the ~1000 m
--:     intended. SEGMENT still returned 0 there, but a 4 m margin against a
--:     call that might carry a tolerance is not the decisive test this was
--:     supposed to be. These coordinates are the corrected ones.
--:   - **FLAT**: A(166088, -115441) -> B(172088, -115441), the same 6 km,
--:     profile 763/762/762/762/763/763/763 m -- a **1 m** spread. The
--:     control, which must come back empty.
--:
--: Both pairs have **nothing built, no landcover and no water within 1200 m**
--: of either endpoint or the midpoint, so a hit cannot be a building sitting
--: on the ridge. **What comes back matters as much as whether**: the type
--: name distinguishes a terrain hit from a stray object, so it is reported.
local function terrainSegmentCode(ax, az, bx, bz)
    return string.format(
        [[
local ax, az, bx, bz = %f, %f, %f, %f
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
local okB, by = pcall(land.getHeight, { x = bx, y = bz })
if not (okA and okB and ay and by) then return "ERR|endpoint getHeight failed" end
local from = { x = ax, y = ay + 2, z = az }
local to = { x = bx, y = by + 2, z = bz }

-- our own terrain verdict over the same line, and the worst intrusion
local maxAbove, blocked = -1e9, false
for k = 1, 59 do
    local t = k / 60
    local okS, sh = pcall(land.getHeight, { x = ax + (bx - ax) * t, y = az + (bz - az) * t })
    if okS and sh then
        local above = sh - (from.y + (to.y - from.y) * t)
        if above > maxAbove then maxAbove = above end
        if above > 0 then blocked = true end
    end
end

local hits, names = 0, {}
local okSeg, segErr = pcall(function()
    world.searchObjects(Object.Category.SCENERY,
        { id = world.VolumeType.SEGMENT, params = { from = from, to = to } },
        function(obj)
            hits = hits + 1
            if #names < 4 then
                local okN, n = pcall(function() return obj:getTypeName() end)
                names[#names + 1] = okN and tostring(n) or "?"
            end
            return true
        end)
end)
if not okSeg then return "ERR|segment search: " .. tostring(segErr) end

local okV, vis = pcall(land.isVisible, from, to)
return string.format(
    "terrainBlocked=%%s maxTerrainAboveLine=%%.0fm | SEGMENT_hits=%%d[%%s] | isVisible=%%s",
    tostring(blocked), maxAbove, hits, table.concat(names, ","),
    (okV and tostring(vis) or "ERR"))
]],
        ax,
        az,
        bx,
        bz
    )
end

--: A dense fan from the aircraft, to close the one real weakness in the
--: forest result.
--:
--: The forest sites were aimed using OSM polygons, and OSM forest is not
--: proof of DCS trees. If DCS simply has no trees at those coordinates then
--: "nothing above ground" is vacuous rather than a negative, and the probe
--: cannot tell those two apart on its own -- `getIP` is the thing under
--: test, so using it to confirm the trees are there would be circular.
--:
--: **The pilot breaks the circle.** He parks where he can *see* trees, this
--: fires 24 azimuths x 2 heights out to 150 m, and reports the largest
--: intercept standing above local ground. Visual confirmation plus a null
--: result is a real negative; without it the forest sites only say "nothing
--: was found where OSM claims forest".
--:
--: Two heights because the failure modes differ: 3 m is trunk height, where
--: a ray also risks clipping undulating ground, and 12 m is mid-canopy,
--: clear of terrain but squarely in the crowns.
local function ownshipFanCode(x, z)
    return string.format(
        [[
local cx, cz = %f, %f
local okG, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okG or gy == nil then return "ERR|getHeight failed" end
local out = {}
for _, eye in ipairs({ 3, 12 }) do
    local maxDelta, above4, hits, misses = 0, 0, 0, 0
    for i = 1, 24 do
        local ang = (i - 1) * 2 * math.pi / 24
        local tx = cx + math.cos(ang) * 150
        local tz = cz + math.sin(ang) * 150
        local okT, ty = pcall(land.getHeight, { x = tx, y = tz })
        if okT and ty then
            local from = { x = cx, y = gy + eye, z = cz }
            local dx, dy, dz = tx - cx, (ty + eye) - (gy + eye), tz - cz
            local dl = math.sqrt(dx * dx + dy * dy + dz * dz)
            local okI, ip = pcall(land.getIP, from,
                { x = dx / dl, y = dy / dl, z = dz / dl }, 160)
            if okI and ip ~= nil then
                hits = hits + 1
                local okH, g2 = pcall(land.getHeight, { x = ip.x, y = ip.z })
                if okH and g2 then
                    local d = ip.y - g2
                    if d > maxDelta then maxDelta = d end
                    if d > 4.0 then above4 = above4 + 1 end
                end
            else
                misses = misses + 1
            end
        end
    end
    out[#out + 1] = string.format(
        "eye%%dm: ipHits=%%d/24 noHit=%%d ABOVE_GROUND_gt4m=%%d maxDelta=%%.1fm",
        eye, hits, misses, above4, maxDelta)
end
return "groundY=" .. string.format("%%.1f", gy) .. " | " .. table.concat(out, " | ")
]],
        x,
        z
    )
end

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
        if probeX ~= nil then
            run("OWNSHIP_DENSE_FAN_park_where_you_see_trees", ownshipFanCode(probeX, probeZ))
        end
        return
    end

    if stepIndex == 2 then
        run(
            "SEGMENT_vs_TERRAIN_ridge_crest+926m",
            terrainSegmentCode(341088.0, 167559.0, 341088.0, 173559.0)
        )
        return
    end

    if stepIndex == 3 then
        run(
            "SEGMENT_vs_TERRAIN_flat_control_1m",
            terrainSegmentCode(166088.0, -115441.0, 172088.0, -115441.0)
        )
        return
    end

    local site = SITES[stepIndex - 3]
    if site ~= nil then
        local ms = run(site[1], siteCode(site[2], site[3]))
        if ms > ABORT_MS then
            logi(string.format("ABORT: %.1f ms over ceiling %.1f", ms, ABORT_MS))
            stepIndex = -1
        end
        return
    end

    if stepIndex == #SITES + 4 and probeX ~= nil then
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
