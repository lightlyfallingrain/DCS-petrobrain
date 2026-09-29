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

THE COORDINATE CONVENTION IS THE EASY MISTAKE: `land.getHeight` takes a
2D vector `{x = <world x>, y = <world z>}` -- its `y` is the world **z**
axis, not altitude (`world-model/tools/dcs-mission-probe/
elevation_probe.lua` line 161). Passing `{x=, z=}` returns nil silently.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainElevProbe"
local START_DELAY_S = 10.0 -- let the terrain finish loading before probing
local BATCH_SIZES = { 1, 100, 500, 2601 }
local REPEATS = 20

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
    for i = 1, REPEATS do
        local t0 = os.clock()
        local ok, result = dostring(code)
        local ms = (os.clock() - t0) * 1000.0
        if not ok then
            logi(label .. ": FAILED on iteration " .. i .. " result=" .. tostring(result))
            return
        end
        lastResult = result
        samples[#samples + 1] = ms
        total = total + ms
    end
    table.sort(samples)
    logi(
        string.format(
            "%s: n=%d mean_ms=%.3f min_ms=%.2f med_ms=%.2f max_ms=%.2f result=%s",
            label,
            REPEATS,
            total / REPEATS,
            samples[1],
            samples[math.ceil(REPEATS / 2)],
            samples[REPEATS],
            tostring(lastResult)
        )
    )
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
