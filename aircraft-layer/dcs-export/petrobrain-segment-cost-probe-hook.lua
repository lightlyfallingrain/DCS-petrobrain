--[[
Throwaway probe Hook script: what does ONE `SEGMENT` scenery search cost?

**This is a probe, not pipeline code.** Deploy, sit ~15 s, read `dcs.log`
(prefix `PetrobrainSegCost`), delete.

THE ONLY QUESTION LEFT. A SEGMENT volume search gives true 3D building
occlusion -- proven 2026-09-29: 6 hits through a town at 2 m AGL, 0 at 15 m
and above, and 2 on a realistic 200 m-to-2 m slant
(`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
Findings 16 and 19). What is *not* known is whether it is cheap enough to run
per candidate per poll, which is the only way it would actually be used.

WHY THE PREVIOUS ATTEMPT GAVE A WRONG NUMBER, because this is the third time
the same mistake has been made in this investigation and it deserves naming:

  `segment_cost_1: ms=1.00  ->  ~1000 us per segment search`

That is wrong by one to two orders of magnitude, and the earlier flight had
already contradicted it -- a standalone SEGMENT search measured **0.00 ms**.
Two compounding errors, both mine:

  1. **Setup was inside the measurement.** The cost payload reused a shared
     preamble that runs a 200 m SPHERE search to locate a building. At N=1
     that sphere search *is* essentially the whole cost, and dividing it by
     one segment attributed all of it to the segment.
  2. **One sample at the clock's resolution.** `os.clock()` on Windows is
     1 ms-granular, so a single reading of "1.00 ms" means "somewhere in
     0 to 2 ms", and that was then multiplied by 20 to refuse the next rung.

The same shape -- fixed overhead charged to per-item cost, off a
quantisation-limited sample -- produced the bogus `400 us` and `1600 us`
figures earlier in this investigation, and shut down two ladders and the
whole X-B4 occlusion sweep. **The defence is structural, not care:**

  - **No setup in the payload.** The fan-out below needs no building
    positions, so there is no sphere search to contaminate it.
  - **An explicit N=0 baseline**, measured the same way, subtracted before
    anything is called a per-item cost.
  - **Repeats, trimmed**, so one scheduler outlier cannot set the figure --
    with the untrimmed peak logged beside it, since the peak is what would
    stutter the cockpit and must stay visible.

PREREQUISITE: `net.allow_dostring_in = { "scripting" }`. Already present.
THROTTLE: one bridge call per 0.25 s; escalation gated on the measured
per-item cost against an 8 ms call budget, 60 ms abort ceiling.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainSegCost"
local START_DELAY_S = 10.0
local TICK_INTERVAL_S = 0.25
local ABORT_MS = 60.0
local CALL_BUDGET_MS = 8.0
local REPEATS = 10
local TRIM_TOP = 2

--: N=0 first: it is the baseline every later figure is measured against.
local BATCH_SIZES = { 0, 20, 100, 200 }

local probeX, probeZ = -171265.8281, 25122.6621

local LOCATE_CODE = [[
local ok, unit = pcall(world.getPlayer)
if not ok or unit == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return unit:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
return string.format("OK|%.1f|%.1f", p.x, p.z)
]]

--: N segment searches fanning out from the aircraft to a 2 km ring, from
--: 30 m up down to 2 m above the far ground -- the slanted shape a real
--: per-candidate occlusion gate would issue, and the shape already shown to
--: return buildings correctly.
--:
--: Deliberately self-contained: no sphere search, no building lookup,
--: nothing but the segment searches being measured. N=0 runs the identical
--: code with the loop skipped, so the baseline carries exactly the same
--: bridge and `getHeight` overhead and subtracts cleanly.
local function costCode(n)
    return string.format(
        [[
local cx, cz, n = %f, %f, %d
local okH, gy = pcall(land.getHeight, { x = cx, y = cz })
if not okH or gy == nil then return "ERR|getHeight failed" end
local from = { x = cx, y = gy + 30, z = cz }
local hit, errs = 0, 0
for i = 1, n do
    local ang = (i / n) * 2 * math.pi
    local tx = cx + math.cos(ang) * 2000
    local tz = cz + math.sin(ang) * 2000
    local okT, ty = pcall(land.getHeight, { x = tx, y = tz })
    if okT and ty then
        local found = 0
        local ok = pcall(function()
            world.searchObjects(Object.Category.SCENERY,
                { id = world.VolumeType.SEGMENT,
                  params = { from = from, to = { x = tx, y = ty + 2, z = tz } } },
                function() found = found + 1 return true end)
        end)
        if ok then
            if found > 0 then hit = hit + 1 end
        else errs = errs + 1 end
    else errs = errs + 1 end
end
return string.format("%%d/%%d rays hit scenery, errs=%%d", hit, n, errs)
]],
        probeX,
        probeZ,
        n
    )
end

local petrobrainSegCost = {}
local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local located = false
local ladderIndex = 0
local baselineMs = nil
local perSegmentMs = nil
local group = nil

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

local function trimmedMean(values, drop)
    local sorted = {}
    for i, v in ipairs(values) do
        sorted[i] = v
    end
    table.sort(sorted)
    local keep = #sorted - drop
    if keep < 1 then
        keep = #sorted
    end
    local total = 0
    for i = 1, keep do
        total = total + sorted[i]
    end
    return total / keep, sorted[#sorted]
end

local function startRung()
    local n = BATCH_SIZES[ladderIndex]
    if n == nil then
        logi("=== segment cost probe end ===")
        group = nil
        ladderIndex = -1
        return
    end
    if n > 0 and perSegmentMs ~= nil then
        local predicted = (baselineMs + n * perSegmentMs) * 2.0
        if predicted > CALL_BUDGET_MS then
            logi(
                string.format(
                    "segment_cost_%d: SKIPPED -- predicted %.1f ms over the %.1f ms budget",
                    n,
                    predicted,
                    CALL_BUDGET_MS
                )
            )
            logi("=== segment cost probe end ===")
            group = nil
            ladderIndex = -1
            return
        end
    end
    group = { n = n, code = costCode(n), samples = {}, result = nil }
end

local function finishRung()
    local n = group.n
    local steady, peak = trimmedMean(group.samples, TRIM_TOP)
    if n == 0 then
        baselineMs = steady
        logi(
            string.format(
                "segment_cost_BASELINE: n=%d steady_ms=%.3f PEAK_ms=%.2f"
                    .. " -- bridge + one getHeight, no segment searches",
                #group.samples,
                steady,
                peak
            )
        )
    else
        --: Floor the per-item figure so a baseline-dominated reading cannot
        --: come out negative or zero and wave the next rung through.
        perSegmentMs = math.max((steady - (baselineMs or 0)) / n, 0.0005)
        logi(
            string.format(
                "segment_cost_%d: n=%d steady_ms=%.3f PEAK_ms=%.2f"
                    .. " -> %.1f us per SEGMENT search (baseline %.3f ms subtracted) | %s",
                n,
                #group.samples,
                steady,
                peak,
                perSegmentMs * 1000.0,
                baselineMs or 0,
                tostring(group.result)
            )
        )
    end
    ladderIndex = ladderIndex + 1
    startRung()
end

function petrobrainSegCost.onSimulationStart()
    simulationRunning = true
    startAt = nil
    located = false
    ladderIndex = 0
    baselineMs = nil
    perSegmentMs = nil
    group = nil
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainSegCost.onSimulationFrame()
    if not simulationRunning or ladderIndex < 0 then
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
            logi(
                string.format(
                    "locate_ownship: ms=%.2f FAILED (%s) -- falling back to %.1f,%.1f",
                    ms,
                    tostring(result),
                    probeX,
                    probeZ
                )
            )
        end
        located = true
        logi("=== segment cost probe start ===")
        ladderIndex = 1
        startRung()
        return
    end

    if group == nil then
        return
    end

    local t0 = os.clock()
    local ok, result = dostring(group.code)
    local ms = (os.clock() - t0) * 1000.0
    if not ok then
        logi(string.format("segment_cost_%d: FAILED %s", group.n, tostring(result)))
        ladderIndex = -1
        return
    end
    group.samples[#group.samples + 1] = ms
    group.result = result

    if ms > ABORT_MS then
        logi(string.format("ABORT: segment_cost_%d took %.1f ms (ceiling %.1f)", group.n, ms, ABORT_MS))
        ladderIndex = -1
        return
    end

    if #group.samples >= REPEATS then
        finishRung()
    end
end

function petrobrainSegCost.onSimulationStop()
    simulationRunning = false
    group = nil
    ladderIndex = 0
end

DCS.setUserCallbacks(petrobrainSegCost)

logi("hook loaded")
