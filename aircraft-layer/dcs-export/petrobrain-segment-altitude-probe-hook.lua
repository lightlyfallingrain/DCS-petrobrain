--[[
Throwaway probe Hook script: is a SEGMENT volume search a true 3D
intersection test, or a 2D footprint test?

**This is a probe, not pipeline code.** Deploy, sit ~20 s, read `dcs.log`
(prefix `PetrobrainSegAlt`), delete.

WHY THIS IS THE QUESTION THAT DECIDES IT. On 2026-09-29 a SEGMENT search
along a 120 m line 2 m above ground returned **3 buildings** where the line
crossed a town and **0** over open ground 3 km away, at 0.00 ms
(`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
Finding 16). That is building-aware occlusion, which `land.isVisible` --
called on the identical endpoints in the same payload, returning `true` --
does not provide.

But every one of those segments was at **2 m AGL**, so the result is equally
consistent with two very different implementations:

  - **A true 3D test.** The segment intersects the buildings' actual geometry.
    Raise it above the rooftops and the hits go away.
  - **A 2D footprint test** that ignores `y` entirely. Then a Mi-24P at 200 m
    flying *over* a town would be "blocked" by every building beneath it, and
    the mechanism is worse than useless for this project -- it is actively
    wrong in exactly the situation Petrovich spends the sortie in.

**Nothing measured so far distinguishes these**, and the difference is the
whole value of the finding. Hence: fire the same horizontal segment through
the same buildings at a ladder of altitudes.

  - 2 m AGL -- the known-positive baseline, must reproduce the 3 hits.
  - 15 m -- around or just above typical `SYRIA_*` rooftop height.
  - 50 m, 200 m, 500 m -- unambiguously above anything.

**Reading the result:** hits falling to 0 as altitude rises is a 3D test and
the mechanism is usable. Hits staying flat is a 2D footprint and it must not
be used for air-to-ground LOS. A partial fall tells us roughly where the
model tops out, which is also useful.

Also fired: the **realistic geometry**, a slanted sightline from 200 m above
and 1 km back down to a point at ground level just beyond the buildings --
the actual Mi-24P-looking-at-a-target case, as opposed to the horizontal
line that is convenient to reason about. A 3D test should report the
buildings only when the slant actually clips them.

And a cost measurement, because if this is to run per candidate per poll the
per-call figure matters: N segment searches in one bridge call, N escalating
while measurement says it is safe.

PREREQUISITE: `net.allow_dostring_in = { "scripting" }`. Already present.
THROTTLE: one bridge call per 0.25 s; every search is 120 m-1 km, far below
the 600 m sphere that cost 18 ms.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainSegAlt"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25
local ABORT_MS = 60.0
local ALTITUDES = { 2, 15, 50, 200, 500 }
local COST_BATCH_SIZES = { 1, 20, 100 }
local CALL_BUDGET_MS = 8.0

local probeX, probeZ = -171265.8281, 25122.6621

local LOCATE_CODE = [[
local ok, unit = pcall(world.getPlayer)
if not ok or unit == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return unit:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
return string.format("OK|%.1f|%.1f", p.x, p.z)
]]

--: Shared preamble: find the same building the last probe found, and derive
--: the same 120 m axis through it, so the altitude ladder is varying one
--: thing and one thing only.
local PREAMBLE = [[
local cx, cz = %f, %f
local okH, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okH or gy == nil then return "ERR|getHeight failed at centre" end
local target = nil
local okS, serr = pcall(function()
    world.searchObjects(Object.Category.SCENERY,
        { id = world.VolumeType.SPHERE,
          params = { point = { x = cx, y = gy, z = cz }, radius = 200 } },
        function(obj)
            if target ~= nil then return false end
            local okP, p = pcall(function() return obj:getPoint() end)
            local okN, n = pcall(function() return obj:getTypeName() end)
            if okP and p then target = { p.x, p.y, p.z, okN and tostring(n) or "?" } end
            return true
        end)
end)
if not okS then return "ERR|sphere search: " .. tostring(serr) end
if target == nil then return "ERR|no scenery within 200 m" end
local bx, by, bz = target[1], target[2], target[3]
local dx, dz = bx - cx, bz - cz
local len = math.sqrt(dx * dx + dz * dz)
if len < 1 then dx, dz, len = 1, 0, 1 end
dx, dz = dx / len, dz / len
local ax, az = bx - dx * 60, bz - dz * 60
local ex, ez = bx + dx * 60, bz + dz * 60
local okB, groundAtB = pcall(land.getHeight, { x = bx, y = bz })
if not okB or groundAtB == nil then return "ERR|getHeight at building failed" end
local function segHits(fx, fy, fz, tx, ty, tz)
    local hits, names = 0, {}
    local ok, e = pcall(function()
        world.searchObjects(Object.Category.SCENERY,
            { id = world.VolumeType.SEGMENT,
              params = { from = { x = fx, y = fy, z = fz },
                         to   = { x = tx, y = ty, z = tz } } },
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
]]

--: The altitude ladder, all rungs in one call so they see identical state.
local function altitudeCode()
    return string.format(
        PREAMBLE .. [[
local out = {}
local alts = { %s }
for _, a in ipairs(alts) do
    local h, names = segHits(ax, groundAtB + a, az, ex, groundAtB + a, ez)
    out[#out + 1] = string.format("%%dm=%%d", a, h)
end
-- realistic geometry: 200 m up and 1 km back, looking down at a point just
-- past the buildings -- the actual Mi-24P case rather than a convenient
-- horizontal line
local sx, sz = bx - dx * 1000, bz - dz * 1000
local slantHits = segHits(sx, groundAtB + 200, sz, ex, groundAtB + 2, ez)
return string.format("target=%%s buildingY=%%.1f groundY=%%.1f | %%s | slant_200m_to_2m=%%d",
    target[4], by, groundAtB, table.concat(out, " "), slantHits)
]],
        probeX,
        probeZ,
        table.concat(ALTITUDES, ", ")
    )
end

--: N segment searches in one bridge call, fanning out from the aircraft --
--: the shape a per-poll occlusion gate would issue.
local function costCode(n)
    return string.format(
        PREAMBLE .. [[
local n = %d
local blocked, errs = 0, 0
for i = 1, n do
    local ang = (i / n) * 2 * math.pi
    local tx = cx + math.cos(ang) * 2000
    local tz = cz + math.sin(ang) * 2000
    local okT, ty = pcall(land.getHeight, { x = tx, y = tz })
    if okT and ty then
        local h = segHits(cx, gy + 30, cz, tx, ty + 2, tz)
        if h > 0 then blocked = blocked + 1 elseif h < 0 then errs = errs + 1 end
    else errs = errs + 1 end
end
return string.format("%%d/%%d segments hit scenery, errs=%%d", blocked, n, errs)
]],
        probeX,
        probeZ,
        n
    )
end

local petrobrainSegAlt = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local phase = "locate"
local costIndex = 0
local perCallMs = nil

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
    return ok, result, ms
end

function petrobrainSegAlt.onSimulationStart()
    simulationRunning = true
    startAt = nil
    phase = "locate"
    costIndex = 0
    perCallMs = nil
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainSegAlt.onSimulationFrame()
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
        local _, result = run("locate_ownship", LOCATE_CODE)
        local x, z = tostring(result):match("^OK|([%-%d%.]+)|([%-%d%.]+)$")
        if x ~= nil then
            probeX, probeZ = tonumber(x), tonumber(z)
            logi(string.format("centre=%.1f,%.1f (ownship)", probeX, probeZ))
        else
            logi(string.format("falling back to Mezzeh at %.1f,%.1f", probeX, probeZ))
        end
        logi("=== segment altitude probe start ===")
        phase = "altitude"
        return
    end

    if phase == "altitude" then
        run("ALTITUDE_LADDER", altitudeCode())
        phase = "cost"
        return
    end

    if phase == "cost" then
        costIndex = costIndex + 1
        local n = COST_BATCH_SIZES[costIndex]
        if n == nil then
            logi("=== segment altitude probe end ===")
            phase = "done"
            return
        end
        --: Same discipline as the terrain probe: escalate only while the
        --: measured cost says the next rung fits.
        if perCallMs ~= nil and perCallMs * n * 2.0 > CALL_BUDGET_MS then
            logi(
                string.format(
                    "segment_cost_%d: SKIPPED -- predicted %.1f ms over the %.1f ms budget",
                    n,
                    perCallMs * n * 2.0,
                    CALL_BUDGET_MS
                )
            )
            logi("=== segment altitude probe end ===")
            phase = "done"
            return
        end
        local ok, _, ms = run("segment_cost_" .. n, costCode(n))
        if ok then
            perCallMs = ms / n
            logi(string.format("segment_cost_%d: ~%.1f us per segment search", n, perCallMs * 1000))
        end
        if ms > ABORT_MS then
            logi(string.format("ABORT: %.1f ms over ceiling %.1f", ms, ABORT_MS))
            phase = "done"
        end
        return
    end
end

function petrobrainSegAlt.onSimulationStop()
    simulationRunning = false
    phase = "locate"
end

DCS.setUserCallbacks(petrobrainSegAlt)

logi("hook loaded")
