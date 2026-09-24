--[[
WEAPON-OBJECT PROBE -- not the production export script.

Self-contained: does NOT connect to the collector. Appends to
Logs\aircraft_layer_probe_weapons.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`, fly, then read the log back.
**This replaces the production Export.lua for the duration** -- the normal
body-layer pipeline does not run while this is in place. Put the real
Export.lua back afterwards.

THE QUESTION, AND WHY IT IS WORTH ONE SORTIE

`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-
bridge.md` (second addendum) asks whether `LoGetWorldObjects()` returns
in-flight weapon objects -- shells, rockets, missiles -- as ordinary
entries, alongside the units it is already known to return.

If it does, **perceiving that we are being shot at needs no event handler
at all.** A tracer becomes just another object in the feed
`body-layer/src/perception/` already gates on field of view, angular size
and terrain line of sight, and the whole "being engaged" channel reduces to
something the naked-eye path can already see. That would be by far the
cheapest answer available, and it is the reason to look before building
anything event-driven.

The supporting signal is that Tacview renders individual AAA rounds -- but
Tacview's DCS exporter is a compiled plugin, so that evidences the engine
tracking rounds as objects, not this Lua surface exposing them. Hence the
look.

WHAT IT LOGS

Once a second: the total object count, and every object Name seen for the
first time this sortie. A steady mission converges quickly to silence; a
burst of gunfire, if shells are objects, shows as a count spike and a run
of new names. Both halves matter -- names alone would miss short-lived
objects that appear and vanish between polls, and a count alone would not
say what appeared.

HOW TO FLY IT

Put yourself where a ground AAA unit (ZU-23-2 or Shilka, set to engage)
actually fires -- at you or at a decoy -- and hold there while it shoots.
Then read the log:

  * Object count spikes while it fires, plus new names -> weapon objects
    are in the feed. Note the names; they are what a filter would key on.
  * Count flat and no new names while tracers are visibly in the air ->
    weapon objects are NOT exposed here. That is a real, useful negative:
    it closes the cheap route and leaves the firing-event handler
    (`petrobrain-damage-events-probe-hook.lua`) as the only candidate.

Delete this file once the question is settled.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_weapons.log"
local POLL_INTERVAL_S = 1.0

local log_file = nil
local function model_time()
    local ok, t = pcall(LoGetModelTime)
    if ok and type(t) == "number" then
        return t
    end
    return -1.0
end

local function logline(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then
            return
        end
        log_file = f
    end
    log_file:write(string.format("[%.2f] %s\n", model_time(), msg))
    log_file:flush()
end

--: Every object Name seen so far this sortie. Names, not ids: a shell gets
--: a fresh id every round fired, which would make an id-keyed set grow
--: without telling us anything, while the *name* is the type and repeats.
local seen_names = {}
local next_poll_at = 0

function LuaExportStart()
    logline("=== weapon-object probe start ===")
end

--: Required export callback. Not a throttle on `LuaExportAfterNextFrame`
--: despite reading like one -- see the production `Export.lua`'s own header
--: note; the poll rate below is what actually paces this probe.
function LuaExportActivityNextEvent(t)
    return t + 1.0
end

function LuaExportAfterNextFrame()
    local now = model_time()
    if now < 0 then
        return
    end
    if now < next_poll_at then
        return
    end
    next_poll_at = now + POLL_INTERVAL_S

    local ok, objects = pcall(LoGetWorldObjects)
    if not ok or type(objects) ~= "table" then
        logline("LoGetWorldObjects failed: " .. tostring(objects))
        return
    end

    local count = 0
    local fresh = {}
    for _, obj in pairs(objects) do
        count = count + 1
        local name = nil
        if type(obj) == "table" then
            name = obj.Name
        end
        if type(name) == "string" and seen_names[name] == nil then
            seen_names[name] = true
            fresh[#fresh + 1] = name
        end
    end

    if #fresh > 0 then
        logline("count=" .. tostring(count) .. " NEW: " .. table.concat(fresh, ", "))
    else
        logline("count=" .. tostring(count))
    end
end

function LuaExportStop()
    logline("=== weapon-object probe stop ===")
end
