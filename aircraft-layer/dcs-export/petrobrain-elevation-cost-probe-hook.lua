--[[
Throwaway probe Hook script: does `land.getHeight` work through the
mission-scripting bridge, and what does a batch of them cost?

**This is a probe, not pipeline code.** It is deployed by hand for one
sortie, writes only to `dcs.log`, and is deleted afterwards. It answers the
two questions `aircraft-layer/research/2026-09-28-live-terrain-probing-
feasibility.md` left open ("Unresolved", items 1 and 3):

  1. `land.getHeight`/`land.getSurfaceType` are *inferred* to work through
     `net.dostring_in("scripting", ...)` because they live in the same
     Mission Scripting environment as `Object.getVelocity()`, which the
     production telemetry hook has used since 2026-09-22. **No session has
     ever called them through the bridge and read a number back.** This
     script does, at eight coordinates whose true heights are already
     recorded in `Saved Games/DCS/Logs/elevation_probe_output.jsonl` (the
     M4 mission-editor probe, 2026-09-06), so the answer is checkable and
     not merely non-nil.
  2. Per-call cost of a `getHeight` batch, which is a *different* engine
     call from `getVelocity` (plausibly a heightfield sample or raycast
     rather than a stored per-unit field) and so is not covered by the
     velocity hook's own `bridge_call_ms`.

PREREQUISITE, same as every other hook here: `Saved Games/DCS/Config/
autoexec.cfg` must contain `net.allow_dostring_in = { "scripting" }` or
every call returns `("Invalid state name", false)`. It is already present
on this machine (the F10 menu works), so nothing needs doing.

DEPLOY: copy to `Saved Games/DCS/Scripts/Hooks/`, fly or just sit in any
**Syria** mission for ~30 s, then delete the file again. Output goes to
`Saved Games/DCS/Logs/dcs.log`, prefixed `PetrobrainElevProbe`.

WHY THE ODD MEASUREMENT SHAPE: `os.clock()` on Windows is wall-clock with
`CLOCKS_PER_SEC = 1000`, i.e. **1 ms granularity**. That is why the
production velocity hook's numbers are all whole milliseconds, and it means
a single small batch cannot be timed at all -- it reads 0 or 1 ms. So each
batch size is run `REPEATS` times and the *total* is divided, and a
zero-work `return "x"` call is timed the same way to separate fixed bridge
overhead from the terrain queries themselves. Without that null column the
batch numbers would be unattributable.

THE COORDINATE CONVENTION IS THE EASY MISTAKE, AND THE TWO CALLS DIFFER:
`land.getHeight` takes a **2D** vector `{x = <world x>, y = <world z>}` --
its `y` is the world **z** axis, not altitude (`world-model/tools/
dcs-mission-probe/elevation_probe.lua` line 161). `land.isVisible` and
`land.getIP` take **3D** vectors `{x, y, z}` where `y` *is* altitude.
Passing the wrong shape returns nil silently, with no error.

-------------------------------------------------------------------------
X-B4: DO TREES AND BUILDINGS BLOCK LINE OF SIGHT, AND CAN WE READ THEM?
-------------------------------------------------------------------------

Added 2026-09-29 at the user's direction, riding the same sortie. This is
backlog item X-B4 (his own, 2026-09-25) plus a new half he raised today:
not just "does DCS's LOS test see trees", but "can we get tree/building
data out of DCS at all", which would be worth a great deal to our own LOS.

**What is already known from the shipped files, and what it does not
settle.** `Scripts/AI/Detection.lua`'s `visual_detection` table sets
`objects_LOS_test = true`, `trees_LOS_test = false` and
`trees_LOS_test_T4 = true`; every installed theatre is Terrain-4, so **ED's
own AI detection** samples buildings and trees for line of sight. That is a
statement about the AI, **not** about the scripting API. `land.isVisible`,
`land.getIP` and `world.searchObjects` are implemented natively -- nothing
in `Scripts/` defines them, only `ScriptingSystem.lua`'s
`class(SceneryObject, Object)` -- so their semantics cannot be read off
disk and can only be measured live. Hence this probe.

**The discriminating design, which is the part worth getting right.**
Asking "did `isVisible` return false" proves nothing on its own: our own
terrain-only LOS would also return false across a ridge, and a sightline
that clips a hill our 60-sample sweep happened to step over would *look*
like an object blocking it. So the probe runs a **controlled comparison**:

  - the same procedure in two places -- **Mezzeh (dense urban)** and
    **Deir ez-Zor (open desert)**, both with recorded ground-truth heights;
  - per point pair, a terrain-only occlusion verdict computed here from 60
    `land.getHeight` samples (our own algorithm, so the comparison is
    against the thing we would otherwise ship), against `land.isVisible`;
  - endpoints 2 m above local terrain, pairs under ~1.5 km, so terrain
    almost never blocks and anything that does is something else.

The signal is the **"terrain says clear, `isVisible` says blocked" rate,
urban minus desert.** Terrain-sampling error is present in both areas
equally, so it subtracts out; buildings and trees are not. A large gap
means `isVisible` sees more than the heightfield. A gap near zero means it
is terrain-only and X-B4's 9K113 half collapses, which is a real outcome
and the reason the desert control is here rather than assumed away.

**`world.searchObjects` is the other half** -- if it enumerates
`Object.Category.SCENERY` with positions, buildings are *extractable* into
the world model, not merely testable one ray at a time. The probe reports
how many it finds in a 1 km sphere over Mezzeh and dumps a few type names
and positions, which is what would tell us whether the data has the shape
`store.models.StoredFeature` could hold. Trees are almost certainly not
scenery objects (they are terrain-baked), so for them `isVisible` is
expected to be the only route -- the comparison above is what tests that.

Everything is `pcall`-wrapped and reports which call failed: all three of
these functions are unverified through this bridge, and a probe that dies
on the first nil teaches nothing about the other two.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainElevProbe"
local START_DELAY_S = 10.0 -- let the terrain finish loading before probing
local BATCH_SIZES = { 1, 100, 500, 2601 }
local REPEATS = 20

-- X-B4. 40 pairs per area is enough to separate a "buildings block" rate
-- from a "they do not" rate (a 0/40 vs 15/40 split is unmistakable) while
-- keeping each area under ~2,400 getHeight calls.
local OCCLUSION_PAIRS = 40
-- Batch sizes a real per-poll detectability gate would use: one sightline
-- per candidate contact, a dense scene being the upper end.
local ISVISIBLE_BATCH_SIZES = { 1, 50, 200 }
-- Wall-clock ceiling per timed series. Eight series, so the whole probe's
-- worst case is bounded at a few seconds of cockpit freeze rather than
-- whatever 52,000 unknown-cost engine calls happen to add up to.
local SERIES_BUDGET_MS = 500.0

-- The eight M4 spot-check points, with the heights `land.getHeight`
-- returned for them on 2026-09-06 via a mission-editor trigger. If the
-- bridge route works, it must reproduce these; a mismatch means the bridge
-- reaches a different terrain state, which would itself be the finding.
local KNOWN_POINTS = [[
local known = {
    {"damascus_osdi", -179748.3281, 50728.2656},
    {"latakia_oslk", 43237.9688, 5841.1646},
    {"beirut_olba", -132952.7344, -42476.5820},
    {"aleppo_osap", 126175.2969, 123040.0156},
    {"klieat_olka_coastal", -48636.1523, 7884.5889},
    {"mezzeh_os67_urban", -171265.8281, 25122.6621},
    {"deir_ez_zor_osdz_desert", 25885.5547, 390774.8750},
    {"kahramanmaras_ltcn_mountainous", 276904.9688, 101895.7422},
}
local out = {}
for _, p in ipairs(known) do
    local okH, h = pcall(land.getHeight, { x = p[2], y = p[3] })
    local okS, s = pcall(land.getSurfaceType, { x = p[2], y = p[3] })
    out[#out + 1] = p[1] .. "=" .. tostring(okH and h or "ERR")
        .. "/" .. tostring(okS and s or "ERR")
end
return table.concat(out, ";")
]]

-- A batch of N getHeight calls on a 100 m grid (M8's locked probe spacing)
-- anchored near Damascus, i.e. over real varied terrain rather than sea.
-- Returns a checksum plus the count so the call cannot be optimised away
-- and a truncated/failed batch is visible.
local function batchCode(n)
    return string.format(
        [[
local n, sum, got = %d, 0, 0
local x0, z0 = -180000, 50000
local side = math.ceil(math.sqrt(n))
for i = 0, n - 1 do
    local px = x0 + (i %% side) * 100
    local pz = z0 + math.floor(i / side) * 100
    local ok, h = pcall(land.getHeight, { x = px, y = pz })
    if ok and h then sum = sum + h; got = got + 1 end
end
return tostring(got) .. "|" .. string.format("%%.1f", sum)
]],
        n
    )
end

local NULL_CODE = [[return "x"]]

-- X-B4 part 1: does `world.searchObjects` enumerate buildings, and with
-- what attached to them? A 1 km sphere over Mezzeh (dense urban, and a
-- recorded ground-truth point). Capped at SAMPLE_CAP reported objects --
-- the count is the interesting number, the samples are there to show what
-- shape the data has.
local SCENERY_CODE = [[
local centre = { x = -171265.8281, z = 25122.6621 }
local okH, groundY = pcall(land.getHeight, { x = centre.x, y = centre.z })
if not okH or groundY == nil then return "ERR|getHeight failed at centre" end
local volume = {
    id = world.VolumeType.SPHERE,
    params = { point = { x = centre.x, y = groundY, z = centre.z }, radius = 1000 },
}
local count, samples = 0, {}
local SAMPLE_CAP = 6
local ok, err = pcall(function()
    world.searchObjects(Object.Category.SCENERY, volume, function(obj)
        count = count + 1
        if #samples < SAMPLE_CAP then
            local name = "?"
            local okN, n = pcall(function() return obj:getTypeName() end)
            if okN and n then name = tostring(n) end
            local px, py, pz = "?", "?", "?"
            local okP, p = pcall(function() return obj:getPoint() end)
            if okP and p then px, py, pz = p.x, p.y, p.z end
            local desc = "?"
            local okD, d = pcall(function() return obj:getDesc() end)
            if okD and type(d) == "table" then
                desc = tostring(d.typeName or d.displayName or "tbl")
            end
            samples[#samples + 1] = string.format(
                "%s@%s,%s,%s[%s]", name, tostring(px), tostring(py), tostring(pz), desc)
        end
        return true
    end)
end)
if not ok then return "ERR|" .. tostring(err) end
return "OK|count=" .. tostring(count) .. "|" .. table.concat(samples, ";")
]]

-- X-B4 part 2: the controlled comparison. `area` is "urban" or "desert";
-- both run identically, and the DIFFERENCE between them is the finding --
-- see the file header for why a single area proves nothing.
--
-- Deterministic LCG rather than math.random: the same pairs every run, so
-- two sorties are comparable and a surprising number can be re-examined at
-- the exact coordinates that produced it.
local function occlusionCode(area, pairs_n)
    local cx, cz = -171265.8281, 25122.6621 -- Mezzeh, dense urban
    if area == "desert" then
        cx, cz = 25885.5547, 390774.8750 -- Deir ez-Zor, open desert
    end
    return string.format(
        [[
local cx, cz, N = %f, %f, %d
local seed = 12345
local function rnd()
    seed = (1103515245 * seed + 12345) %% 2147483648
    return seed / 2147483648
end
local SAMPLES = 60
local EYE = 2.0
local terrainClearVisBlocked, bothClear, bothBlocked, terrainBlockedVisClear = 0, 0, 0, 0
local visErrors, heightErrors = 0, 0
for i = 1, N do
    local ax = cx + (rnd() - 0.5) * 3000
    local az = cz + (rnd() - 0.5) * 3000
    local bx = cx + (rnd() - 0.5) * 3000
    local bz = cz + (rnd() - 0.5) * 3000
    local okA, ay = pcall(land.getHeight, { x = ax, y = az })
    local okB, by = pcall(land.getHeight, { x = bx, y = bz })
    if not (okA and okB and ay and by) then
        heightErrors = heightErrors + 1
    else
        local fromY, toY = ay + EYE, by + EYE
        -- terrain-only verdict, our own algorithm at high sample density
        local terrainBlocked = false
        for s = 1, SAMPLES - 1 do
            local t = s / SAMPLES
            local sx = ax + (bx - ax) * t
            local sz = az + (bz - az) * t
            local okS, sh = pcall(land.getHeight, { x = sx, y = sz })
            if okS and sh then
                if sh > fromY + (toY - fromY) * t then terrainBlocked = true break end
            end
        end
        local okV, vis = pcall(land.isVisible,
            { x = ax, y = fromY, z = az }, { x = bx, y = toY, z = bz })
        if not okV or vis == nil then
            visErrors = visErrors + 1
        else
            local visBlocked = not vis
            if terrainBlocked and visBlocked then bothBlocked = bothBlocked + 1
            elseif terrainBlocked and not visBlocked then
                terrainBlockedVisClear = terrainBlockedVisClear + 1
            elseif (not terrainBlocked) and visBlocked then
                terrainClearVisBlocked = terrainClearVisBlocked + 1
            else bothClear = bothClear + 1 end
        end
    end
end
return string.format(
    "pairs=%%d bothClear=%%d bothBlocked=%%d TERRAIN_CLEAR_VIS_BLOCKED=%%d terrainBlockedVisClear=%%d visErr=%%d hErr=%%d",
    N, bothClear, bothBlocked, terrainClearVisBlocked, terrainBlockedVisClear, visErrors, heightErrors)
]],
        cx,
        cz,
        pairs_n
    )
end

-- Cost of N `isVisible` rays in one bridge call, fanning out from one
-- observer over Mezzeh to N points on a 5 km ring -- the shape a per-poll
-- detectability gate would issue. Returns the blocked count so the call
-- cannot be optimised away and a silently-failing batch is visible.
local function isVisibleBatchCode(n)
    return string.format(
        [[
local n = %d
local ax, az = -171265.8281, 25122.6621
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
if not okA or ay == nil then return "ERR|getHeight failed" end
local from = { x = ax, y = ay + 30.0, z = az }
local blocked, errs = 0, 0
for i = 1, n do
    local a = (i / n) * 2 * math.pi
    local tx = ax + math.cos(a) * 5000
    local tz = az + math.sin(a) * 5000
    local okH, th = pcall(land.getHeight, { x = tx, y = tz })
    if okH and th then
        local okV, vis = pcall(land.isVisible, from, { x = tx, y = th + 2.0, z = tz })
        if okV and vis ~= nil then
            if not vis then blocked = blocked + 1 end
        else errs = errs + 1 end
    else errs = errs + 1 end
end
return tostring(blocked) .. "/" .. tostring(n) .. " blocked, errs=" .. tostring(errs)
]],
        n
    )
end

-- X-B4 part 3: does `land.getIP` return *where* the ray was blocked? That
-- is the difference between Petrovich knowing he cannot see something and
-- being able to say "the treeline short of it" -- which is the half of
-- this that reaches the pilot. Fired along a shallow ray over Mezzeh.
local GETIP_CODE = [[
local ax, az = -171265.8281, 25122.6621
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
if not okA or ay == nil then return "ERR|getHeight failed" end
local origin = { x = ax, y = ay + 2.0, z = az }
local dir = { x = 1.0, y = -0.02, z = 0.0 }
local ok, ip = pcall(land.getIP, origin, dir, 5000)
if not ok then return "ERR|" .. tostring(ip) end
if ip == nil then return "OK|nil (nothing hit within 5000 m)" end
return string.format("OK|hit at %s,%s,%s (%.0f m out)",
    tostring(ip.x), tostring(ip.y), tostring(ip.z), ip.x - ax)
]]

local petrobrainElevProbe = {}
local fireAt = nil
local done = false

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

-- Times `code` REPEATS times and logs every individual sample, so the tail
-- is visible and not just a mean -- a p99 stutter is what would actually
-- hurt in the cockpit, and a mean hides it.
local function timeSeries(label, code)
    local samples = {}
    local total = 0
    local lastResult = nil
    local n = 0
    for i = 1, REPEATS do
        local t0 = os.clock()
        local ok, result = dostring(code)
        local ms = (os.clock() - t0) * 1000.0
        if not ok then
            logi(label .. ": FAILED on iteration " .. i .. " result=" .. tostring(result))
            return
        end
        lastResult = result
        n = n + 1
        samples[#samples + 1] = ms
        total = total + ms
        -- The cost being measured is the thing that is unknown, and this
        -- runs on DCS's own thread. 20 repeats of a 2,601-point batch is
        -- ~52,000 engine calls; at 1 ms each that is a minute-long freeze
        -- in the cockpit. So stop the series once it has spent its budget
        -- and report how many samples actually ran -- a smaller n with an
        -- honest mean is worth more than a hung game, and if the budget is
        -- hit at all that is itself the headline finding.
        if total > SERIES_BUDGET_MS then
            logi(
                string.format(
                    "%s: budget %.0f ms hit after %d/%d repeats -- series cut short",
                    label,
                    SERIES_BUDGET_MS,
                    n,
                    REPEATS
                )
            )
            break
        end
    end
    table.sort(samples)
    logi(
        string.format(
            "%s: n=%d mean_ms=%.3f min_ms=%.2f med_ms=%.2f max_ms=%.2f result=%s",
            label,
            n,
            total / n,
            samples[1],
            samples[math.ceil(n / 2)],
            samples[n],
            tostring(lastResult)
        )
    )
end

-- One call, result logged verbatim, timing included but incidental. For
-- the semantic questions, where the answer is the returned string and a
-- 1 ms-granular duration is only context.
local function runOnce(label, code)
    local t0 = os.clock()
    local ok, result = dostring(code)
    local ms = (os.clock() - t0) * 1000.0
    if not ok then
        logi(label .. ": FAILED result=" .. tostring(result))
        return
    end
    logi(string.format("%s: ms=%.2f result=%s", label, ms, tostring(result)))
end

local function runProbe()
    logi("=== elevation bridge probe start ===")

    -- Question 1: does it work at all, and does it agree with the M4 probe?
    local ok, result = dostring(KNOWN_POINTS)
    if not ok then
        logi("KNOWN POINTS FAILED: " .. tostring(result))
        logi("=== elevation bridge probe end (land.* unreachable via bridge) ===")
        return
    end
    logi("known points (name=height/surfacetype): " .. tostring(result))

    -- Question 2: what does it cost?
    timeSeries("null_call", NULL_CODE)
    for _, n in ipairs(BATCH_SIZES) do
        timeSeries("getHeight_batch_" .. n, batchCode(n))
    end

    -- X-B4. Run once each (not REPEATS times): these are semantic
    -- questions, and the occlusion comparison is already 40 pairs x 60
    -- height samples per area. Cost for isVisible specifically is measured
    -- separately below, on its own, where a repeat loop is affordable.
    runOnce("scenery_search", SCENERY_CODE)
    runOnce("getIP", GETIP_CODE)
    runOnce("occlusion_urban", occlusionCode("urban", OCCLUSION_PAIRS))
    runOnce("occlusion_desert", occlusionCode("desert", OCCLUSION_PAIRS))

    -- Cost of isVisible alone, at the batch sizes a per-poll detectability
    -- gate would actually use. If this is cheap, DCS's own occlusion test
    -- could replace our elevation-grid LOS outright rather than supplement
    -- it -- which is the outcome worth knowing.
    for _, n in ipairs(ISVISIBLE_BATCH_SIZES) do
        timeSeries("isVisible_batch_" .. n, isVisibleBatchCode(n))
    end

    logi("=== elevation bridge probe end ===")
end

function petrobrainElevProbe.onSimulationStart()
    fireAt = nil
    done = false
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainElevProbe.onSimulationFrame()
    if done then
        return
    end
    local now = DCS.getRealTime()
    if fireAt == nil then
        fireAt = now + START_DELAY_S
        return
    end
    if now < fireAt then
        return
    end
    done = true
    local ok, err = pcall(runProbe)
    if not ok then
        logi("probe raised: " .. tostring(err))
    end
end

function petrobrainElevProbe.onSimulationStop()
    done = false
    fireAt = nil
end

DCS.setUserCallbacks(petrobrainElevProbe)

logi("hook loaded")
