--[[
Throwaway probe Hook script: does `land.getHeight` work through the
mission-scripting bridge, do trees and buildings block `land.isVisible`,
and what does any of it cost?

**This is a probe, not pipeline code.** It is deployed by hand for one
sortie, writes only to `dcs.log`, and is deleted afterwards. It answers the
two questions `aircraft-layer/research/2026-09-28-live-terrain-probing-
feasibility.md` left open ("Unresolved", items 1 and 3), plus backlog item
X-B4.

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
**Syria** mission for ~60 s, then delete the file again. Output goes to
`Saved Games/DCS/Logs/dcs.log`, prefixed `PetrobrainElevProbe`.

-------------------------------------------------------------------------
THE THROTTLE, AND WHY IT IS ADAPTIVE RATHER THAN A FIXED CAP
-------------------------------------------------------------------------

**User direction, 2026-09-29: *"We can't freeze the cockpit for a minute,
not even for testing. DCS might crash or windows might close it as
unresponsive."*** He is right, and the first version of this probe was
unsafe: it ran up to 20 repeats of a 2,601-point batch back-to-back inside
a single `onSimulationFrame`, which is ~52,000 engine calls in one frame.
At an unknown per-call cost that is an unbounded stall on DCS's own thread,
and Windows marks a process unresponsive after ~5 s without a message pump.

**A fixed cap would not have fixed it**, which is the point worth keeping:
the per-call cost is precisely the thing being measured, so any batch size
chosen in advance is a guess against an unknown. Two mechanisms instead:

1. **One bridge call per `TICK_INTERVAL_S`, never a burst.** Repeats are
   spread across frames rather than run in a loop, so the game gets every
   intervening frame back. At a `CALL_BUDGET_MS` call every 250 ms the duty
   cycle is a few percent, and the whole probe takes ~40 s of sitting still
   instead of one long hitch.
2. **Escalate only where measurement says it is safe.** Every batch starts
   at N=1 and steps up only while `fixed + N x per_item`, doubled for
   safety, stays under `CALL_BUDGET_MS`. `per_item` comes from the batch
   just measured, so each step is gated by real numbers rather than
   optimism. **Every** step adapts, including the two that are not simple
   batches: the scenery search walks 50 -> 600 m predicting each radius by
   area scaling from the last one's measured cost, and the occlusion sweep
   picks both its samples-per-pair and its pairs-per-call from the measured
   `getHeight`/`isVisible` costs. A step that cannot fit says so and is
   skipped; none of them guesses.

Driving a harness over this state machine at simulated costs from 1 us to
1000 us per engine call keeps the worst single call between 1.1 and
16.5 ms, and the whole probe between 18 and 45 s of sitting still. The
16.5 ms worst case is `known_points`, the one call that runs before any
measurement exists to gate it -- see its own comment.

`ABORT_MS` is the backstop: any single call over it stops the entire probe
immediately. **Hitting it is not a failure of the probe, it is the
headline finding** -- it would mean live terrain probing is not affordable
at any useful density, and the `.surface5` file route stops being a parked
fallback (`world-model/research/2026-09-29-surface5-elevation-confirmed.md`).

`os.clock()` on Windows is wall-clock with `CLOCKS_PER_SEC = 1000`, i.e.
**1 ms granularity**, which is also why the production velocity hook's
numbers are all whole milliseconds. A single small call cannot be timed at
all -- it reads 0 or 1 ms -- so small sizes are averaged over `REPEATS`
and the per-item estimate is floored and safety-doubled before it is
trusted to gate anything.

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
that clips a hill our sample sweep happened to step over would *look* like
an object blocking it. So the probe runs a **controlled comparison**:

  - the same procedure in two places -- a **3 km box around the player's
    own aircraft**, which the user positions near a town, forest and
    mountains for exactly this purpose, and **Deir ez-Zor (open desert)**
    as the control. Ownship beats any blind coordinate here: he can set up
    the discriminating case deliberately and then check the logged centre
    against what he built. If `world.getPlayer()` turns out unreachable
    through the bridge, it falls back to Mezzeh and says so;
  - per point pair, a terrain-only occlusion verdict computed here from
    `land.getHeight` samples (our own algorithm, so the comparison is
    against the thing we would otherwise ship), against `land.isVisible`;
  - endpoints 2 m above local terrain, pairs under ~1.5 km, so terrain
    almost never blocks and anything that does is something else.

The signal is the **"terrain says clear, `isVisible` says blocked" rate,
ownship-area minus desert.** Terrain-sampling error is present in both areas
equally, so it subtracts out; buildings and trees are not. A large gap
means `isVisible` sees more than the heightfield. A gap near zero means it
is terrain-only and X-B4's 9K113 half collapses, which is a real outcome
and the reason the desert control is here rather than assumed away.

**Town and forest test different things and both are wanted.** Buildings
are candidate `world.searchObjects` scenery, i.e. potentially extractable
as data; trees almost certainly are not, so for them `isVisible` is the
only route and this comparison is the only evidence. Mountains in the same
box are the sanity check: terrain-only and `isVisible` should agree there,
and if they do not, the comparison machinery itself is wrong.

Pairs are derived from a stateless integer hash of the pair index, not a
running RNG, so the sweep can be cut into per-frame chunks that each
compute their own pairs independently -- and so two sorties produce the
same pairs and a surprising number can be re-examined at the exact
coordinates that produced it.

**`world.searchObjects` is the other half** -- if it enumerates
`Object.Category.SCENERY` with positions, buildings are *extractable* into
the world model, not merely testable one ray at a time. The probe reports
how many it finds over Mezzeh and dumps a few type names and positions,
which is what would tell us whether the data has the shape
`store.models.StoredFeature` could hold. Trees are almost certainly not
scenery objects (they are terrain-baked), so for them `isVisible` is
expected to be the only route -- the comparison above is what tests that.
Its radius starts small for the same throttle reason: an unbounded search
over a dense city is exactly the call that could stall a frame.

Everything is `pcall`-wrapped and reports which call failed: all three of
these functions are unverified through this bridge, and a probe that dies
on the first nil teaches nothing about the other two.
]]

local DCS = require("DCS")

local LOG_PREFIX = "PetrobrainElevProbe"
local START_DELAY_S = 10.0 -- let the terrain finish loading before probing

--: Target ceiling for any single bridge call. Well under a 60 fps frame
--: (16.7 ms), so even a call that lands badly costs part of one frame
--: rather than a visible hitch.
local CALL_BUDGET_MS = 8.0
--: Any single call over this stops the whole probe.
--:
--: **Raised from 25 ms to 60 ms on 2026-09-29 after it killed a run.**
--: `known_points` touches eight locations scattered across the whole
--: theatre and took 31 ms -- and that is now known to be a real, expected
--: *cold-terrain* cost rather than a malfunction, so aborting on it threw
--: away the entire sortie for nothing. Cold cost is the thing this probe
--: now exists to measure; a ceiling below it cannot measure it. 60 ms is
--: ~4 frames -- visible, not dangerous -- and the one-call-per-250 ms
--: throttle keeps the duty cycle at ~1% even at that size.
local ABORT_MS = 60.0
--: Minimum gap between bridge calls. The game gets every frame in between.
local TICK_INTERVAL_S = 0.25
--: Repeats per measured size. Enough to average out 1 ms granularity
--: without making the probe outlast the user's patience.
local REPEATS = 10
--: Samples discarded from the top of each series before estimating cost.
--: See `trimmedMean` for what this is defending against and why.
local TRIM_TOP = 2

--: Metres between successive "fresh ground" patches. Far enough apart that
--: probing patch N tells the engine nothing about patch N+1.
local PATCH_STRIDE_M = 4000

--: A call at or above this probably dropped a frame the pilot could feel.
--: Logged loudly rather than acted on -- the point is that it be visible in
--: the log next to the thing that caused it.
local STUTTER_WARN_MS = 12.0

--: Cold calls get their own, larger budget. They are *expected* to exceed
--: the warm one -- that overrun is the measurement, not a malfunction --
--: so gating them at `CALL_BUDGET_MS` would refuse to measure the very
--: thing the pilot felt. Still well under `ABORT_MS`.
local COLD_BUDGET_MS = 40.0

--: Escalation ladders. Each starts at 1 and steps up only while the
--: measured cost predicts the next rung stays under `CALL_BUDGET_MS`.
local BATCH_SIZES = { 1, 10, 50, 200, 500, 2601 }
local ISVISIBLE_BATCH_SIZES = { 1, 10, 50, 200 }

--: Confirmation-only rungs. The per-item cost is settled -- 0.9 us/point
--: and 10 us/ray, measured consistently on two flights -- so re-walking a
--: six-rung ladder from N=1 buys nothing and costs 15 s of the user's
--: sortie. Just re-check the top.
local CONFIRM_BATCH_SIZES = { 2601 }
local CONFIRM_ISVISIBLE_SIZES = { 200 }

--: X-B4 occlusion sweep. 40 pairs per area separates a "buildings block"
--: rate from a "they do not" rate (0/40 vs 15/40 is unmistakable);
--: 30 samples per pair keeps terrain-sampling error low enough that the
--: urban-minus-desert difference is the dominant term.
local OCCLUSION_PAIRS = 40
--: Hard ceiling on pairs per bridge call, whatever the cost estimate says.
local OCCLUSION_MAX_PAIRS_PER_CALL = 8

--: Scenery search radii, metres -- another escalation ladder, and the one
--: that most needs to be. `world.searchObjects`'s cost scales with however
--: many objects are in the volume, which is exactly what is unknown before
--: asking: a 600 m sphere over a dense city could be a handful of
--: buildings or thousands. Driving a harness over this probe's own state
--: machine at 200 us/engine-call had the fixed-radius version take 40 ms
--: in one call -- past the abort ceiling. So it starts tiny and grows only
--: while the measured cost, scaled by area, says the next radius fits.
local SCENERY_RADII_M = { 50, 150, 300, 600 }

--: Terrain-sample counts per occlusion pair, largest first. The sweep
--: takes the largest that fits one pair inside the call budget. Dropping
--: to a coarser count is sound here in a way it would not normally be:
--: the finding is the *difference* between the urban and desert rates, and
--: both areas get whatever count is chosen, so sampling error stays a
--: common term and cancels. A coarser sweep widens the confidence interval;
--: it does not bias the comparison.
local OCCLUSION_SAMPLE_LADDER = { 30, 10, 4 }

local MEZZEH_X, MEZZEH_Z = -171265.8281, 25122.6621 -- dense urban fallback
local DEIR_X, DEIR_Z = 25885.5547, 390774.8750 -- open desert control

--: The rich-terrain centre every non-control step probes around. Resolved
--: at run time to the **player's own aircraft** via `world.getPlayer()`,
--: because the user prepares the flight to sit near a town, forest and
--: mountains (his offer, 2026-09-29) -- which is a far better test bed
--: than any coordinate picked blind, and one he can eyeball against what
--: the probe reports. Falls back to Mezzeh if `world.getPlayer()` is not
--: available through the bridge, and says which it used either way.
local probeX, probeZ = MEZZEH_X, MEZZEH_Z
local probeCentreSource = "fallback:mezzeh"

--: One engine call. Returns the player's ground position, or an error we
--: report and carry on from -- `world.getPlayer()` is itself unverified
--: through this bridge, so it must not be able to sink the probe.
local LOCATE_CODE = [[
local ok, unit = pcall(world.getPlayer)
if not ok or unit == nil then return "ERR|world.getPlayer unavailable" end
local okP, p = pcall(function() return unit:getPoint() end)
if not okP or p == nil then return "ERR|getPoint failed" end
local name = "?"
local okN, n = pcall(function() return unit:getTypeName() end)
if okN and n then name = tostring(n) end
return string.format("OK|%.1f|%.1f|%s", p.x, p.z, name)
]]

-- The eight M4 spot-check points, with the heights `land.getHeight`
-- returned for them on 2026-09-06 via a mission-editor trigger. If the
-- bridge route works, it must reproduce these; a mismatch means the bridge
-- reaches a different terrain state, which would itself be the finding.
--
-- This is the one call that cannot be cost-gated -- it runs first, before
-- anything has been measured, so there is no estimate to gate it with.
-- That is why it is exactly 16 engine calls (8 points x getHeight +
-- getSurfaceType) and not a point more: even at an absurd 1 ms per call
-- that is ~16 ms, one frame, and still inside `ABORT_MS`. Adding points
-- here is not free the way it looks.
--: One point per bridge call -- see the plan step for why this is no
--: longer a single 16-call payload. `%d` is substituted twice: once to
--: pick the point, once so the returned string names it.
local KNOWN_POINT_TEMPLATE = [[
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
local p = known[%d]
if p == nil then return "ERR|no such point %d" end
local okH, h = pcall(land.getHeight, { x = p[2], y = p[3] })
local okS, s = pcall(land.getSurfaceType, { x = p[2], y = p[3] })
return p[1] .. "=" .. tostring(okH and h or "ERR") .. "/" .. tostring(okS and s or "ERR")
]]
local NULL_CODE = [[return "x"]]

-- N getHeight calls on a 100 m grid (M8's locked probe spacing) over real
-- varied terrain near Damascus. Returns a checksum plus the count so the
-- call cannot be optimised away and a truncated batch is visible.
local function batchCode(n, patchIndex)
    return string.format(
        [[
local n, sum, got = %d, 0, 0
local x0, z0 = %f, %f
local side = math.ceil(math.sqrt(n))
for i = 0, n - 1 do
    local px = x0 + (i %% side) * 100
    local pz = z0 + math.floor(i / side) * 100
    local ok, h = pcall(land.getHeight, { x = px, y = pz })
    if ok and h then sum = sum + h; got = got + 1 end
end
return tostring(got) .. "|" .. string.format("%%.1f", sum)
]],
        n,
        probeX + patchIndex * PATCH_STRIDE_M,
        probeZ
    )
end

-- N `isVisible` rays in one bridge call, fanning out from one observer
-- over Mezzeh to N points on a 5 km ring -- the shape a per-poll
-- detectability gate would issue.
local function isVisibleBatchCode(n, _patchIndex)
    return string.format(
        [[
local n = %d
local ax, az = %f, %f
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
        n,
        probeX,
        probeZ
    )
end

-- X-B4 part 1: does `world.searchObjects` enumerate buildings, and with
-- what attached to them?
local function sceneryCode(radius)
    return string.format(
        [[
local cx, cz = %f, %f
local okH, groundY = pcall(land.getHeight, { x = cx, y = cz })
if not okH or groundY == nil then return "ERR|getHeight failed at centre" end
local volume = {
    id = world.VolumeType.SPHERE,
    params = { point = { x = cx, y = groundY, z = cz }, radius = %d },
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
            -- Dump the desc table's own keys, one level deep, for the
            -- FIRST object only. A LOS occluder needs extent, not a
            -- point, and the 2026-09-29 run read only `typeName` -- so
            -- whether a box/dimensions field exists here is still open.
            -- This is what closes it, at the cost of one serialisation.
            local desc = "?"
            local okD, d = pcall(function() return obj:getDesc() end)
            if okD and type(d) == "table" then
                if #samples == 0 then
                    local keys = {}
                    for k, v in pairs(d) do
                        if type(v) == "table" then
                            local inner = {}
                            for k2, v2 in pairs(v) do
                                inner[#inner + 1] = tostring(k2) .. "=" .. tostring(v2)
                            end
                            keys[#keys + 1] = tostring(k) .. "{" .. table.concat(inner, ",") .. "}"
                        else
                            keys[#keys + 1] = tostring(k) .. "=" .. tostring(v)
                        end
                    end
                    desc = "FULLDESC:" .. table.concat(keys, "|")
                else
                    desc = tostring(d.typeName or d.displayName or "tbl")
                end
            end
            samples[#samples + 1] = string.format(
                "%%s@%%s,%%s,%%s[%%s]", name, tostring(px), tostring(py), tostring(pz), desc)
        end
        return true
    end)
end)
if not ok then return "ERR|" .. tostring(err) end
return "OK|radius=%d count=" .. tostring(count) .. "|" .. table.concat(samples, ";")
]],
        probeX,
        probeZ,
        radius,
        radius
    )
end

-- X-B4 part 4, added after flight 4: the DECISIVE test, and the one the
-- random-pair sweep cannot be trusted to have run.
--
-- Flight 4's sweep found no urban-vs-desert gap (1/40 vs 0/40), which
-- points at `isVisible` being terrain-only. But 40 random pairs in a 3 km
-- box mostly miss a town that occupies a small part of it, so "no gap" is
-- confounded with "no sightline actually crossed a building". This removes
-- the confound: ask `world.searchObjects` where the buildings ARE, then
-- fire a ray straight through each one, 60 m either side of its centre at
-- 2 m above local ground.
--
-- If `isVisible` tests buildings, these are blocked. If it is terrain-only,
-- they are clear. There is nothing to interpret.
local function throughBuildingsCode(maxBuildings)
    return string.format(
        [[
local cx, cz, MAXB = %f, %f, %d
local okH, groundY = pcall(land.getHeight, { x = cx, y = cz })
if not okH or groundY == nil then return "ERR|getHeight failed at centre" end
local volume = {
    id = world.VolumeType.SPHERE,
    params = { point = { x = cx, y = groundY, z = cz }, radius = 200 },
}
local buildings = {}
local okS, err = pcall(function()
    world.searchObjects(Object.Category.SCENERY, volume, function(obj)
        if #buildings >= MAXB then return false end
        local okP, p = pcall(function() return obj:getPoint() end)
        local okN, n = pcall(function() return obj:getTypeName() end)
        if okP and p then
            buildings[#buildings + 1] = { p.x, p.z, okN and tostring(n) or "?" }
        end
        return true
    end)
end)
if not okS then return "ERR|" .. tostring(err) end
if #buildings == 0 then return "ERR|no scenery within 200 m" end
local blocked, clear, terrBlocked, out = 0, 0, 0, {}
for i, b in ipairs(buildings) do
    local bx, bz = b[1], b[2]
    -- ray axis: from the probe centre towards the building, extended past it
    local dx, dz = bx - cx, bz - cz
    local len = math.sqrt(dx * dx + dz * dz)
    if len > 1 then
        dx, dz = dx / len, dz / len
        local ax, az = bx - dx * 60, bz - dz * 60
        local ex, ez = bx + dx * 60, bz + dz * 60
        local okA, ay = pcall(land.getHeight, { x = ax, y = az })
        local okE, ey = pcall(land.getHeight, { x = ex, y = ez })
        if okA and okE and ay and ey then
            -- terrain-only verdict over the same 120 m, so a rise between
            -- the endpoints is not mistaken for the building
            local tBlocked = false
            for k = 1, 19 do
                local t = k / 20
                local okM, mh = pcall(land.getHeight,
                    { x = ax + (ex - ax) * t, y = az + (ez - az) * t })
                if okM and mh and mh > (ay + 2) + ((ey + 2) - (ay + 2)) * t then
                    tBlocked = true
                    break
                end
            end
            local okV, vis = pcall(land.isVisible,
                { x = ax, y = ay + 2, z = az }, { x = ex, y = ey + 2, z = ez })
            if okV and vis ~= nil then
                if tBlocked then terrBlocked = terrBlocked + 1
                elseif vis then clear = clear + 1
                else blocked = blocked + 1 end
                if #out < 4 then
                    out[#out + 1] = b[3] .. (vis and ":CLEAR" or ":BLOCKED")
                        .. (tBlocked and "(terrain)" or "")
                end
            end
        end
    end
end
return string.format(
    "n=%%d BLOCKED_BY_SOMETHING=%%d clear=%%d terrainBlocked=%%d | %%s",
    #buildings, blocked, clear, terrBlocked, table.concat(out, ";"))
]],
        probeX,
        probeZ,
        maxBuildings
    )
end

-- X-B4 part 3: does `land.getIP` return *where* the ray was blocked? That
-- is the difference between Petrovich knowing he cannot see something and
-- being able to say "the treeline short of it" -- the half that reaches
-- the pilot.
-- Eight rays, one per compass octant, so a ray that happens to point at
-- open ground does not read as "getIP returns nil". Shallow (-0.02) and
-- 2 m up, i.e. the geometry of looking *along* the ground at a treeline or
-- a building edge rather than down at terrain.
local function getIPCode()
    return string.format(
        [[
local ax, az = %f, %f
local okA, ay = pcall(land.getHeight, { x = ax, y = az })
if not okA or ay == nil then return "ERR|getHeight failed" end
local origin = { x = ax, y = ay + 2.0, z = az }
local out = {}
for i = 0, 7 do
    local a = i * math.pi / 4
    local dir = { x = math.cos(a), y = -0.02, z = math.sin(a) }
    local ok, ip = pcall(land.getIP, origin, dir, 5000)
    if not ok then
        out[#out + 1] = i .. "=ERR"
    elseif ip == nil then
        out[#out + 1] = i .. "=nil"
    else
        local dx, dz = ip.x - ax, ip.z - az
        out[#out + 1] = string.format("%%d=%%.0fm/y%%.0f", i, math.sqrt(dx * dx + dz * dz), ip.y)
    end
end
return "OK|" .. table.concat(out, ";")
]],
        probeX,
        probeZ
    )
end

-- X-B4 part 2: one chunk of the controlled comparison -- pairs
-- `firstPair`..`lastPair` of the sweep over `area`. Pair coordinates come
-- from a stateless hash of the pair index so chunks are independent and
-- reproducible; see the header.
local function occlusionChunkCode(area, firstPair, lastPair, samplesPerPair)
    local cx, cz = probeX, probeZ
    if area == "desert" then
        cx, cz = DEIR_X, DEIR_Z
    end
    return string.format(
        [[
local cx, cz = %f, %f
local first, last, SAMPLES, EYE = %d, %d, %d, 2.0
local function hash(i, salt)
    local v = (i * 2654435 + salt * 40503) %% 2147483648
    v = (v * 1103515245 + 12345) %% 2147483648
    return v / 2147483648
end
local tcvb, bc, bb, tbvc, visErr, hErr = 0, 0, 0, 0, 0, 0
for i = first, last do
    local ax = cx + (hash(i, 1) - 0.5) * 3000
    local az = cz + (hash(i, 2) - 0.5) * 3000
    local bx = cx + (hash(i, 3) - 0.5) * 3000
    local bz = cz + (hash(i, 4) - 0.5) * 3000
    local okA, ay = pcall(land.getHeight, { x = ax, y = az })
    local okB, by = pcall(land.getHeight, { x = bx, y = bz })
    if not (okA and okB and ay and by) then
        hErr = hErr + 1
    else
        local fromY, toY = ay + EYE, by + EYE
        local terrainBlocked = false
        for s = 1, SAMPLES - 1 do
            local t = s / SAMPLES
            local okS, sh = pcall(land.getHeight,
                { x = ax + (bx - ax) * t, y = az + (bz - az) * t })
            if okS and sh and sh > fromY + (toY - fromY) * t then
                terrainBlocked = true
                break
            end
        end
        local okV, vis = pcall(land.isVisible,
            { x = ax, y = fromY, z = az }, { x = bx, y = toY, z = bz })
        if not okV or vis == nil then
            visErr = visErr + 1
        else
            local visBlocked = not vis
            if terrainBlocked and visBlocked then bb = bb + 1
            elseif terrainBlocked then tbvc = tbvc + 1
            elseif visBlocked then tcvb = tcvb + 1
            else bc = bc + 1 end
        end
    end
end
return table.concat({tcvb, bc, bb, tbvc, visErr, hErr}, ",")
]],
        cx,
        cz,
        firstPair,
        lastPair,
        samplesPerPair
    )
end

local petrobrainElevProbe = {}

local simulationRunning = false
local startAt = nil
local nextCallAt = 0
local aborted = false
local finished = false

--: Cost model, filled in as the probe measures itself. `fixedMs` is the
--: bare bridge overhead; the per-item figures gate every escalation.
local fixedMs = 0.5
--: Kept apart deliberately. A cold figure must never gate warm work:
--: in simulation, a cold `getHeight` estimate at N=1 (where the whole
--: per-patch penalty lands on a single point) predicted 620 ms for N=10
--: and shut down the warm ladder and the entire X-B4 occlusion sweep --
--: all of which are warm operations. That is the same mistake as the
--: 2026-09-29 outlier bug wearing a different hat: one regime's number
--: deciding another regime's budget.
--: Seeded from flights 4 and 5 (0.87-0.96 us/point measured twice) rather
--: than left nil, because the decisive steps now run BEFORE the ladders
--: that would otherwise measure it. A seed that is wrong by 2x still sizes
--: a chunk safely; having no estimate at all would force the occlusion
--: sweep down to 1 pair per call and cost another sortie.
local getHeightWarmPerItemMs = 0.001
local getHeightColdPerItemMs = nil
local isVisiblePerItemMs = 0.010

--: The current measurement group. `codeFor(i)` yields the i-th call's
--: code; `onDone(samples, lastResult)` summarises and queues what is next.
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

local function median(sorted)
    return sorted[math.ceil(#sorted / 2)]
end

--: Would a batch of `n` items at `perItemMs` fit the budget? Doubled for
--: safety, because `perItemMs` is derived from 1 ms-granular timings and
--: is therefore an estimate with real error in it. An unmeasured
--: `perItemMs` (nil) means only the smallest rung is allowed.
local function fitsBudget(n, perItemMs, budgetMs)
    if perItemMs == nil then
        return n <= 1
    end
    return (fixedMs + n * perItemMs) * 2.0 <= (budgetMs or CALL_BUDGET_MS)
end

--: Mean of the samples with the top `drop` discarded.
--:
--: **This is the fix for the 2026-09-29 run, where a plain mean shut the
--: whole probe down on noise.** At 1 ms clock granularity a sub-millisecond
--: call reads 0 ms nine times out of ten and then catches one stray frame:
--: `getHeight_batch_1` logged nine 0 ms samples and a single 4 ms one, and
--: the mean (0.4 ms) was then attributed entirely to *one* `getHeight`
--: call -- 400 us each. `isVisible_batch_1` did the same with a 15 ms
--: outlier and came out at 1600 us. Both ladders then refused their next
--: rung as unaffordable, and the X-B4 occlusion sweep was skipped for want
--: of a cost estimate. The real cost is nowhere near that: the same run
--: searched 135 scenery objects in 1 ms and fired 8 `getIP` raycasts in
--: under one.
--:
--: An outlier that large is scheduler or frame contention, not the payload
--: -- the 2026-09-28 bridge measurements showed exactly that shape, maxima
--: an order of magnitude over p99 and indifferent to payload size. So trim
--: it. The maximum is still logged, because the tail is what would stutter
--: the cockpit and must stay visible even when it is excluded from the
--: estimate.
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
    return total / keep
end

local function estimatePerItem(costMs, n)
    --: Floor at a small positive value: a trimmed mean of all-zero samples
    --: is 0, and a zero estimate would wave every later rung through with
    --: no check at all. 0.5 us/call is below anything plausible for an
    --: engine call and is deliberately not a guess at the real figure --
    --: it exists so the *next* rung produces a measurable number, which
    --: then replaces it.
    return math.max((costMs - fixedMs) / n, 0.0005)
end

local function beginGroup(label, codeFor, count, onDone)
    group = {
        label = label,
        codeFor = codeFor,
        count = count,
        index = 0,
        samples = {},
        results = {},
        onDone = onDone,
    }
end

local plan = {}
local planIndex = 0

local function advancePlan()
    planIndex = planIndex + 1
    local step = plan[planIndex]
    if step == nil then
        finished = true
        logi("=== elevation bridge probe end ===")
        return
    end
    step()
end

--: Walks an escalation ladder: measure rung `ladderIndex`, then continue
--: only if the measured cost says the next rung is affordable.
local function runLadder(name, sizes, ladderIndex, codeFn, perItemSetter, perItemGetter, budgetMs, gateGetter)
    local n = sizes[ladderIndex]
    if n == nil then
        advancePlan()
        return
    end
    local gate = (gateGetter or perItemGetter)()
    if not fitsBudget(n, gate, budgetMs) then
        logi(
            string.format(
                "%s_batch_%d: SKIPPED -- predicted %.1f ms exceeds the %.1f ms call budget"
                    .. " (this is the affordability answer, not an error)",
                name,
                n,
                (fixedMs + n * (gate or 0)) * 2.0,
                budgetMs
            )
        )
        advancePlan()
        return
    end
    beginGroup(name .. "_batch_" .. n, function(i)
        return codeFn(n, i)
    end, REPEATS, function(samples, lastResult)
        --: Two numbers, not one, and the distinction is the whole point --
        --: see `trimmedMean` and the header. `steady` is the repeat cost
        --: with the top samples trimmed; `peak` is the untrimmed maximum,
        --: which for a cold-ground batch IS the cost, not noise.
        local steady = trimmedMean(samples, TRIM_TOP)
        perItemSetter(estimatePerItem(steady, n))
        table.sort(samples)
        local peak = samples[#samples]
        logi(
            string.format(
                "%s_batch_%d: n=%d steady_ms=%.3f med_ms=%.2f PEAK_ms=%.2f"
                    .. " steady_per_item_us=%.1f peak_per_item_us=%.1f%s result=%s",
                name,
                n,
                #samples,
                steady,
                median(samples),
                peak,
                perItemGetter() * 1000.0,
                math.max(peak - fixedMs, 0) / n * 1000.0,
                peak >= STUTTER_WARN_MS and " STUTTER_LIKELY" or "",
                tostring(lastResult)
            )
        )
        runLadder(
            name,
            sizes,
            ladderIndex + 1,
            codeFn,
            perItemSetter,
            perItemGetter,
            budgetMs,
            gateGetter
        )
    end)
end

--: Picks the sample count and pairs-per-call that fit the budget, from
--: what has actually been measured. Returns nil when even the coarsest
--: single pair does not fit -- in which case the sweep is skipped and said
--: so, rather than quietly running something that stalls a frame.
local function occlusionShape()
    local perHeight = getHeightWarmPerItemMs or 0.05
    local perVis = isVisiblePerItemMs or perHeight
    local budget = CALL_BUDGET_MS / 2.0 - fixedMs
    for _, samplesPerPair in ipairs(OCCLUSION_SAMPLE_LADDER) do
        local perPair = perHeight * (samplesPerPair + 1) + perVis
        if perPair <= budget then
            local n = math.floor(budget / perPair)
            if n > OCCLUSION_MAX_PAIRS_PER_CALL then
                n = OCCLUSION_MAX_PAIRS_PER_CALL
            end
            return samplesPerPair, n
        end
    end
    return nil, nil
end

local function runOcclusion(area)
    local samplesPerPair, perCall = occlusionShape()
    if samplesPerPair == nil then
        logi(
            string.format(
                "occlusion_%s: SKIPPED -- even one pair at %d samples exceeds the"
                    .. " %.1f ms call budget at the measured cost."
                    .. " X-B4's tree/building question is unanswered this sortie.",
                area,
                OCCLUSION_SAMPLE_LADDER[#OCCLUSION_SAMPLE_LADDER],
                CALL_BUDGET_MS
            )
        )
        advancePlan()
        return
    end
    local chunks = math.ceil(OCCLUSION_PAIRS / perCall)
    logi(
        string.format(
            "occlusion_%s: %d pairs in %d chunks of <=%d (%d height samples/pair)",
            area,
            OCCLUSION_PAIRS,
            chunks,
            perCall,
            samplesPerPair
        )
    )
    beginGroup("occlusion_" .. area, function(i)
        local first = (i - 1) * perCall + 1
        local last = math.min(i * perCall, OCCLUSION_PAIRS)
        return occlusionChunkCode(area, first, last, samplesPerPair)
    end, chunks, function(samples, _lastResult)
        local totals = { 0, 0, 0, 0, 0, 0 }
        for _, raw in ipairs(group.results) do
            local k = 1
            for value in tostring(raw):gmatch("[^,]+") do
                totals[k] = totals[k] + (tonumber(value) or 0)
                k = k + 1
            end
        end
        table.sort(samples)
        logi(
            string.format(
                "occlusion_%s: TERRAIN_CLEAR_VIS_BLOCKED=%d bothClear=%d bothBlocked=%d"
                    .. " terrainBlockedVisClear=%d visErr=%d hErr=%d"
                    .. " (chunks=%d max_call_ms=%.2f)",
                area,
                totals[1],
                totals[2],
                totals[3],
                totals[4],
                totals[5],
                totals[6],
                #samples,
                samples[#samples]
            )
        )
        advancePlan()
    end)
end

--: Walks the scenery radii, one call each, predicting the next radius by
--: area scaling from what the last one actually cost. Stops as soon as the
--: prediction leaves the budget -- so the ladder's last completed rung is
--: itself the answer to "how big a volume can we afford to search".
local function runScenery(ladderIndex, lastRadius, lastMs)
    local radius = SCENERY_RADII_M[ladderIndex]
    if radius == nil then
        advancePlan()
        return
    end
    if lastRadius ~= nil and lastMs > 1.0 then
        --: Only predict from a reading the clock could actually resolve.
        --: Flight 4 refused the 150 m rung on a "predicted 18 ms" derived
        --: from a 1 ms reading at 50 m -- but 1 ms IS the quantisation
        --: floor, and flight 1 had already searched 300 m / 135 objects in
        --: that same 1 ms. Scaling noise by 9 and then doubling it is not
        --: a prediction. Below the resolution limit, just try the next rung;
        --: the abort ceiling is the real protection.
        local scale = (radius / lastRadius) ^ 2
        local predicted = (fixedMs + (lastMs - fixedMs) * scale) * 2.0
        if predicted > CALL_BUDGET_MS then
            logi(
                string.format(
                    "scenery_search_%dm: SKIPPED -- predicted %.1f ms from the %d m"
                        .. " measurement exceeds the %.1f ms call budget."
                        .. " Largest affordable search volume: %d m radius.",
                    radius,
                    predicted,
                    lastRadius,
                    CALL_BUDGET_MS,
                    lastRadius
                )
            )
            advancePlan()
            return
        end
    end
    beginGroup("scenery_search_" .. radius .. "m", function()
        return sceneryCode(radius)
    end, 1, function(samples, lastResult)
        logi(
            string.format(
                "scenery_search_%dm: ms=%.2f result=%s",
                radius,
                samples[1],
                tostring(lastResult)
            )
        )
        runScenery(ladderIndex + 1, radius, samples[1])
    end)
end

local function runSingle(label, code)
    beginGroup(label, function()
        return code
    end, 1, function(samples, lastResult)
        logi(string.format("%s: ms=%.2f result=%s", label, samples[1], tostring(lastResult)))
        advancePlan()
    end)
end

--: Runs one queued bridge call. Never more than one per tick, so a slow
--: call costs part of one frame and the game gets the next one back.
local function step()
    group.index = group.index + 1
    local code = group.codeFor(group.index)
    local t0 = os.clock()
    local ok, result = dostring(code)
    local ms = (os.clock() - t0) * 1000.0

    if not ok then
        logi(group.label .. ": FAILED on call " .. group.index .. " result=" .. tostring(result))
        advancePlan()
        return
    end

    group.samples[#group.samples + 1] = ms
    group.results[#group.results + 1] = result

    if ms > ABORT_MS then
        aborted = true
        logi(
            string.format(
                "ABORT: %s call %d took %.1f ms (ceiling %.1f ms). Stopping the probe --"
                    .. " this is the finding: live probing is not affordable at this density.",
                group.label,
                group.index,
                ms,
                ABORT_MS
            )
        )
        logi("=== elevation bridge probe end (aborted on cost) ===")
        return
    end

    if group.index >= group.count then
        local done = group.onDone
        done(group.samples, result)
    end
end

local function buildPlan()
    --: ORDER IS DELIBERATE, and it changed on 2026-09-29 after flight 5.
    --:
    --: That flight was stopped ~40 s in -- a perfectly reasonable length of
    --: time to sit still -- and the probe was still grinding through cost
    --: ladders whose answer was already settled twice over (0.9 us/point,
    --: 10 us/ray). The one genuinely open question, `through_buildings`,
    --: was queued behind them and never ran. Five sorties in, that is a
    --: waste of the user's flying, not a scheduling detail.
    --:
    --: So: unanswered questions first, cheapest-decisive first of all, and
    --: the re-measurements last where losing them costs nothing. Anything
    --: that needs a long sit must be the thing that is already known.
    plan = {
        function()
            beginGroup("warmup", function()
                return NULL_CODE
            end, 1, function(samples, _)
                logi(string.format("warmup: ms=%.2f (discarded)", samples[1]))
                advancePlan()
            end)
        end,
        function()
            beginGroup("locate_ownship", function()
                return LOCATE_CODE
            end, 1, function(samples, result)
                local x, z, unitName = tostring(result):match("^OK|([%-%d%.]+)|([%-%d%.]+)|(.*)$")
                if x ~= nil then
                    probeX, probeZ = tonumber(x), tonumber(z)
                    probeCentreSource = "ownship:" .. tostring(unitName)
                    logi(
                        string.format(
                            "locate_ownship: ms=%.2f centre=%.1f,%.1f source=%s",
                            samples[1],
                            probeX,
                            probeZ,
                            probeCentreSource
                        )
                    )
                else
                    logi(
                        string.format(
                            "locate_ownship: ms=%.2f FAILED (%s) -- falling back to %s at %.1f,%.1f",
                            samples[1],
                            tostring(result),
                            probeCentreSource,
                            probeX,
                            probeZ
                        )
                    )
                end
                advancePlan()
            end)
        end,
        --: THE open question: one call, and it settles X-B4.
        function()
            runSingle("through_buildings", throughBuildingsCode(12))
        end,
        --: Wider net, in case 200 m held too few buildings to be decisive.
        function()
            runSingle("through_buildings_wide", throughBuildingsCode(40))
        end,
        function()
            runOcclusion("urban")
        end,
        function()
            runOcclusion("desert")
        end,
        function()
            runScenery(1, nil, nil)
        end,
        function()
            runSingle("getIP", getIPCode())
        end,
        function()
            beginGroup("known_points", function(i)
                return string.format(KNOWN_POINT_TEMPLATE, i, i)
            end, 8, function(samples, _)
                table.sort(samples)
                for idx, raw in ipairs(group.results) do
                    logi(string.format("known_point[%d]: %s", idx, tostring(raw)))
                end
                logi(
                    string.format(
                        "known_points: 8 calls, med_ms=%.2f PEAK_ms=%.2f%s",
                        median(samples),
                        samples[#samples],
                        samples[#samples] >= STUTTER_WARN_MS and " STUTTER_LIKELY" or ""
                    )
                )
                advancePlan()
            end)
        end,
        --: Re-measurements from here down. Settled twice; kept only to
        --: confirm nothing has drifted, and last because losing them to a
        --: short sortie costs nothing.
        function()
            beginGroup("null_call", function()
                return NULL_CODE
            end, REPEATS, function(samples, _)
                fixedMs = trimmedMean(samples, TRIM_TOP)
                table.sort(samples)
                logi(
                    string.format(
                        "null_call: n=%d trimmed_ms=%.3f med_ms=%.2f max_ms=%.2f"
                            .. " -- taken as fixed bridge overhead",
                        #samples,
                        fixedMs,
                        median(samples),
                        samples[#samples]
                    )
                )
                advancePlan()
            end)
        end,
        function()
            runLadder("getHeightWARM", CONFIRM_BATCH_SIZES, 1, function(n, _i)
                return batchCode(n, 0)
            end, function(v)
                getHeightWarmPerItemMs = v
            end, function()
                return getHeightWarmPerItemMs
            end, CALL_BUDGET_MS)
        end,
        function()
            runLadder("getHeightCOLD", CONFIRM_BATCH_SIZES, 1, function(n, i)
                return batchCode(n, i + 1)
            end, function(v)
                getHeightColdPerItemMs = v
            end, function()
                return getHeightColdPerItemMs
            end, COLD_BUDGET_MS, function()
                return getHeightWarmPerItemMs
            end)
        end,
        function()
            runLadder("isVisible", CONFIRM_ISVISIBLE_SIZES, 1, isVisibleBatchCode, function(v)
                isVisiblePerItemMs = v
            end, function()
                return isVisiblePerItemMs
            end, CALL_BUDGET_MS)
        end,
    }
    planIndex = 0
end

function petrobrainElevProbe.onSimulationStart()
    simulationRunning = true
    startAt = nil
    aborted = false
    finished = false
    group = nil
    getHeightWarmPerItemMs = 0.001
    getHeightColdPerItemMs = nil
    isVisiblePerItemMs = 0.010
    logi("loaded, will probe " .. START_DELAY_S .. "s after sim start")
end

function petrobrainElevProbe.onSimulationFrame()
    if not simulationRunning or aborted or finished then
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

    if group == nil then
        logi("=== elevation bridge probe start ===")
        logi(
            string.format(
                "throttle: <=1 bridge call / %.2fs, call budget %.1f ms, abort ceiling %.1f ms",
                TICK_INTERVAL_S,
                CALL_BUDGET_MS,
                ABORT_MS
            )
        )
        buildPlan()
        advancePlan()
        return
    end

    local ok, err = pcall(step)
    if not ok then
        logi("probe raised: " .. tostring(err))
        aborted = true
    end
end

function petrobrainElevProbe.onSimulationStop()
    simulationRunning = false
    group = nil
end

DCS.setUserCallbacks(petrobrainElevProbe)

logi("hook loaded")
