--[[
Aircraft Layer -- unit-identifier join probe (Hook state -> mission
scripting state), plus a name missing/duplicate census.

Research note: `aircraft-layer/research/2026-10-06-unit-id-join-probe.md`
(the question, the reduction script, and the deployment steps).

WHAT THIS ANSWERS
-----------------
Q1. Does `Unit:getObjectID()` exist in this DCS version, and does its value
    equal the `LoGetWorldObjects` table key for the same unit?
Q2. If not, does `Unit:getID()`? Or neither?
Q3. Does the same hold for static objects (`coalition.getStaticObjects`)
    and for scenery (`world.searchObjects(Object.Category.SCENERY, ...)`)
    -- the population that today can never be joined at all?
Q4. How often are unit names missing or duplicated among in-bubble units?
    Per poll: total units, count with a nil/empty name, count of names
    shared by 2+ units, and the duplicate names themselves.

Q4 is the root-cause measurement for the LOS join defect
(`plans/post-review-fixes/explore-notes.md` SS1) and is useful on its own
even if Q1 answers cleanly.

WHY IT IS A HOOK SCRIPT AND LOGS TO dcs.log
-------------------------------------------
This box is configured `net.allow_dostring_in = { "scripting" }` only
(see `petrobrain-api-surface-probe-hook.lua` and
`petrobrain-damage-events-probe-hook.lua`). The *Export* side of the join
is already captured by the shipping pipeline (`Export.lua` publishes
`object_id` -- the `LoGetWorldObjects` table key -- plus `unit_name` and
`is_ownship`, served at `GET /world_objects/latest`), so this probe only
needs the **scripting** side. Nothing here needs `"export"` added to
`allow_dostring_in`, and this script creates no socket, no port and no
collector change: it writes to `dcs.log` only.

HOW THE TWO SIDES GET CORRELATED
--------------------------------
Three independent anchors, strongest first:

  1. **Ownship, name-free.** `Export.lua` marks exactly one object
     `is_ownship: true` (it compares the `LoGetWorldObjects` key against
     `LoGetPlayerPlaneId()`), so that object's `object_id` *is* a genuine
     table key for a known unit. This script logs the player's own
     `getID()`/`getObjectID()` on the `PB_UIDJ_OWN` line. One integer
     comparison settles Q1/Q2 with no name matching at all.
  2. **Lat/lon, name-free.** Every entry below carries lat/lon/alt taken
     from `coord.LOtoLL` *inside the scripting state*, in the same frame.
     `GET /world_objects/latest` reports lat/lon too, so entries match
     positionally. This is what covers duplicate-named and nil-named
     objects, which by construction cannot be matched by name.
  3. **Unique names.** For any unit whose name is unique this poll, the
     name itself is a valid join key, and the reduction uses it as a
     cross-check on (2).

LOG LINE FORMAT
---------------
Every line this script writes contains a `PB_UIDJ` marker. Each marker is
followed by `|`-delimited fields. DCS prefixes its own timestamp/level/
subsystem text, so a parser must search for the marker **anywhere in the
line**, never anchor at column 0. Lines are not truncated by DCS, but the
per-object sections are still chunked (`CHUNK_MAX_CHARS`) and carry an
explicit `chunk=<i>/<m>` so a missing piece is detectable rather than
silent.

  PB_UIDJ_META|poll=<n>|poll_t=<timer.getTime()>|units=<n>|nil_name=<n>
      |dup_name_groups=<n>|dup_name_units=<n>|statics=<n>|scenery=<n>
      |units_logged=<n>|statics_logged=<n>|scenery_logged=<n>
  PB_UIDJ_API|poll=<n>|<probe>=<type-or-value>|...
      -- existence/type/value of each candidate id accessor, probed on one
         real unit. This is the direct Q1/Q2 existence answer.
  PB_UIDJ_OWN|poll=<n>|<entry>
      -- the player's own unit; anchor (1) above.
  PB_UIDJ_DUP|poll=<n>|chunk=<i>/<m>|<name>*<count>;...
      -- only names shared by 2+ units this poll. Absent when there are
         none (that itself is the Q4 answer for that poll).
  PB_UIDJ_U|poll=<n>|chunk=<i>/<m>|<entry>;<entry>;...   -- units
  PB_UIDJ_S|poll=<n>|chunk=<i>/<m>|<entry>;<entry>;...   -- statics
  PB_UIDJ_C|poll=<n>|chunk=<i>/<m>|<entry>;<entry>;...   -- scenery
  PB_UIDJ_ERR|poll=<n>|<message>                         -- a failed poll
  PB_UIDJ_DONE|polls=<n>                                 -- cap reached

`<entry>` is always exactly six `~`-separated fields:

    <name>~<getID>~<getObjectID>~<lat>~<lon>~<alt>

`<name>` is `<NIL>` when the accessor failed or returned nil/empty (that
is the Q4 "missing name" case). `<getID>`/`<getObjectID>` are `<ERR>` when
the accessor raised and `<NONE>` when it does not exist on that object.
Separator characters (`~ ; | #` and newlines) inside a name are replaced
with `_` before emission, so the format cannot be broken by a
mission-author's unit name; a name containing one of those will therefore
not match the Export side by string equality, which is exactly why
anchors (1) and (2) are position-based.

SAFETY / COST
-------------
Every DCS API call is wrapped in `pcall`, on both sides of the bridge: a
probe that raises inside `onSimulationFrame` would take the mission down
with it, and the user cannot debug that mid-flight. Polling is gated to
between `onSimulationStart`/`onSimulationStop`, runs at 1 Hz, and stops
itself after `MAX_POLLS` polls -- a handful of polls answers every
question here, and the cap means the probe cannot bloat `dcs.log` if the
sortie runs long. Scenery search is a single 300 m sphere, per
`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
Finding 14 (superlinear cost above that).

REQUIRES the same `autoexec.cfg` opt-in as every other `dostring_in`-using
Hook script -- see `aircraft-layer/WORKFLOW.md`. Without it,
`net.dostring_in` returns `("Invalid state name", false)` every poll and
this script logs `PB_UIDJ_ERR` lines instead of data.
--]]

log.write("PetrobrainUnitIdJoin", log.INFO, "Loading - Petrobrain unit id join probe")

local DCS = require("DCS")

--: 1 Hz, matching every other `dostring_in`-based feed in this codebase.
local POLL_INTERVAL_S = 1.0

--: Self-limiting: a handful of polls answers all four questions, and the
--: cap keeps `dcs.log` small whatever the sortie length.
local MAX_POLLS = 10

--: Max characters per emitted section line before chunking. Well under
--: any plausible log-line limit; lines are not truncated by DCS
--: (verified 2026-10-05), this is purely to keep the log readable.
local CHUNK_MAX_CHARS = 900

local petrobrainUnitIdJoin = {}

local simulationRunning = false
local nextPollAt = 0
local pollCount = 0

local function logi(message)
    log.write("PetrobrainUnitIdJoin", log.INFO, message)
end

--: Mirrors every other Hook script's own `dostring_in` wrapper exactly.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

--: Splits a `;`-delimited section into chunks of at most
--: `CHUNK_MAX_CHARS`, never cutting an entry in half. Returns an array of
--: strings (empty when the section is empty).
local function chunkSection(section)
    local chunks = {}
    if section == nil or section == "" then
        return chunks
    end
    local current = nil
    for entry in string.gmatch(section, "([^;]+)") do
        if current == nil then
            current = entry
        elseif #current + 1 + #entry > CHUNK_MAX_CHARS then
            chunks[#chunks + 1] = current
            current = entry
        else
            current = current .. ";" .. entry
        end
    end
    if current ~= nil then
        chunks[#chunks + 1] = current
    end
    return chunks
end

--: Emits one section as `marker|poll=<n>|chunk=<i>/<m>|<payload>` lines.
--: A section with no entries emits nothing -- its counts are already on
--: the `PB_UIDJ_META` line, so absence is unambiguous rather than lossy.
local function logSection(marker, poll, section)
    local chunks = chunkSection(section)
    local total = #chunks
    for i = 1, total do
        logi(
            marker
                .. "|poll=" .. tostring(poll)
                .. "|chunk=" .. tostring(i) .. "/" .. tostring(total)
                .. "|" .. chunks[i]
        )
    end
end

--: The scripting-state chunk. Returns a single string (one scalar is all
--: `dostring_in` can carry back), sections separated by `#`:
--:   OK#<meta>#<api>#<own>#<dups>#<units>#<statics>#<scenery>
--: or `ERR|<message>` on a failure it can describe itself.
--:
--: Long-bracket level `[==[` is deliberate: it leaves `]]` usable inside
--: the chunk without terminating the literal early.
local PROBE_CODE = [==[
local function esc(s)
    if s == nil then return "<NIL>" end
    s = tostring(s)
    if s == "" then return "<NIL>" end
    s = string.gsub(s, "[~;|#\r\n]", "_")
    return s
end

-- Reads one candidate accessor off an object, reporting existence
-- separately from failure: "<NONE>" when the method is absent on this
-- object, "<ERR>" when calling it raised.
local function readId(obj, method)
    if obj == nil then return "<NONE>" end
    local okType, fn = pcall(function() return obj[method] end)
    if not okType or type(fn) ~= "function" then
        return "<NONE>"
    end
    local okCall, value = pcall(fn, obj)
    if not okCall then
        return "<ERR>"
    end
    if value == nil then
        return "<NIL>"
    end
    return tostring(value)
end

-- `<name>~<getID>~<getObjectID>~<lat>~<lon>~<alt>` for any Object-like
-- handle. Position comes from `coord.LOtoLL` in this same frame, which is
-- the name-free correlation anchor against `GET /world_objects/latest`.
local function entryFor(obj)
    local nameRaw = nil
    local okName, n = pcall(function() return obj:getName() end)
    if okName then nameRaw = n end
    local idStr = readId(obj, "getID")
    local objIdStr = readId(obj, "getObjectID")
    local lat, lon, alt = "<ERR>", "<ERR>", "<ERR>"
    local okPoint, p = pcall(function() return obj:getPoint() end)
    if okPoint and p ~= nil then
        local okLL, la, lo, al = pcall(coord.LOtoLL, p)
        if okLL and la ~= nil then
            lat = string.format("%.7f", la)
            lon = string.format("%.7f", lo)
            alt = string.format("%.2f", al or 0.0)
        end
    end
    return esc(nameRaw) .. "~" .. idStr .. "~" .. objIdStr
        .. "~" .. lat .. "~" .. lon .. "~" .. alt
end

local okPlayer, player = pcall(world.getPlayer)
if not okPlayer or player == nil then
    return "ERR|world.getPlayer unavailable"
end
local okPos, ppoint = pcall(function() return player:getPoint() end)
if not okPos or ppoint == nil then
    return "ERR|player getPoint failed"
end

local BUBBLE_M = 10000.0
local MAX_UNITS_LOGGED = 400
local MAX_STATICS_LOGGED = 200
local MAX_SCENERY_LOGGED = 20
local SCENERY_RADIUS_M = 300.0

local playerId = nil
local okPid, pid = pcall(function() return player:getID() end)
if okPid then playerId = pid end

-- Units, all three sides, inside the candidate bubble.
local unitEntries = {}
local unitCount = 0
local nilNameCount = 0
local nameCounts = {}
local sides = { coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE }

for _, side in pairs(sides) do
    local okGroups, groups = pcall(coalition.getGroups, side)
    if okGroups and groups ~= nil then
        for _, grp in ipairs(groups) do
            local okUnits, units = pcall(function() return grp:getUnits() end)
            if okUnits and units ~= nil then
                for _, unit in ipairs(units) do
                    local okExist, exists = pcall(function() return unit:isExist() end)
                    if okExist and exists then
                        local okUP, up = pcall(function() return unit:getPoint() end)
                        if okUP and up ~= nil then
                            local dx = up.x - ppoint.x
                            local dz = up.z - ppoint.z
                            if math.sqrt(dx * dx + dz * dz) <= BUBBLE_M then
                                unitCount = unitCount + 1
                                local okN, nm = pcall(function() return unit:getName() end)
                                if okN and nm ~= nil and nm ~= "" then
                                    nameCounts[nm] = (nameCounts[nm] or 0) + 1
                                else
                                    nilNameCount = nilNameCount + 1
                                end
                                if #unitEntries < MAX_UNITS_LOGGED then
                                    unitEntries[#unitEntries + 1] = entryFor(unit)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end

-- Q4: names shared by 2+ units this poll, and how many units that covers.
local dupParts = {}
local dupGroups = 0
local dupUnits = 0
for nm, c in pairs(nameCounts) do
    if c > 1 then
        dupGroups = dupGroups + 1
        dupUnits = dupUnits + c
        dupParts[#dupParts + 1] = esc(nm) .. "*" .. tostring(c)
    end
end

-- Statics: the population the LOS Hook never enumerates at all, so today
-- it can never be joined. Same entry shape, so the same reduction covers it.
local staticEntries = {}
local staticCount = 0
for _, side in pairs(sides) do
    local okS, statics = pcall(coalition.getStaticObjects, side)
    if okS and statics ~= nil then
        for _, st in ipairs(statics) do
            local okUP, up = pcall(function() return st:getPoint() end)
            if okUP and up ~= nil then
                local dx = up.x - ppoint.x
                local dz = up.z - ppoint.z
                if math.sqrt(dx * dx + dz * dz) <= BUBBLE_M then
                    staticCount = staticCount + 1
                    if #staticEntries < MAX_STATICS_LOGGED then
                        staticEntries[#staticEntries + 1] = entryFor(st)
                    end
                end
            end
        end
    end
end

-- Scenery: one small sphere only (superlinear cost above ~300 m).
local sceneryEntries = {}
local sceneryCount = 0
pcall(function()
    world.searchObjects(
        Object.Category.SCENERY,
        { id = world.VolumeType.SPHERE,
          params = { point = ppoint, radius = SCENERY_RADIUS_M } },
        function(obj)
            sceneryCount = sceneryCount + 1
            if #sceneryEntries < MAX_SCENERY_LOGGED then
                sceneryEntries[#sceneryEntries + 1] = entryFor(obj)
            end
            return true
        end
    )
end)

-- Q1/Q2 existence answer, probed on one real unit (the player) and on the
-- Unit/Object classes themselves. Reported as type names plus the live
-- value, so "exists but returns nil" is distinguishable from "absent".
local probeUnit = player
local apiParts = {}
local function noteType(label, value)
    apiParts[#apiParts + 1] = label .. "=" .. type(value)
end
pcall(function() noteType("class.Unit.getObjectID", Unit.getObjectID) end)
pcall(function() noteType("class.Unit.getID", Unit.getID) end)
pcall(function() noteType("class.Object.getID", Object.getID) end)
pcall(function() noteType("class.StaticObject.getID", StaticObject.getID) end)
pcall(function() noteType("inst.getObjectID", probeUnit.getObjectID) end)
pcall(function() noteType("inst.getID", probeUnit.getID) end)
pcall(function() noteType("inst.getNumber", probeUnit.getNumber) end)
apiParts[#apiParts + 1] = "value.getObjectID=" .. readId(probeUnit, "getObjectID")
apiParts[#apiParts + 1] = "value.getID=" .. readId(probeUnit, "getID")
apiParts[#apiParts + 1] = "value.getNumber=" .. readId(probeUnit, "getNumber")
apiParts[#apiParts + 1] = "player.getID=" .. tostring(playerId)

local ownEntry = entryFor(player)

local meta = "poll_t=" .. tostring(timer.getTime())
    .. "|units=" .. tostring(unitCount)
    .. "|nil_name=" .. tostring(nilNameCount)
    .. "|dup_name_groups=" .. tostring(dupGroups)
    .. "|dup_name_units=" .. tostring(dupUnits)
    .. "|statics=" .. tostring(staticCount)
    .. "|scenery=" .. tostring(sceneryCount)
    .. "|units_logged=" .. tostring(#unitEntries)
    .. "|statics_logged=" .. tostring(#staticEntries)
    .. "|scenery_logged=" .. tostring(#sceneryEntries)

return "OK#" .. meta
    .. "#" .. table.concat(apiParts, "|")
    .. "#" .. ownEntry
    .. "#" .. table.concat(dupParts, ";")
    .. "#" .. table.concat(unitEntries, ";")
    .. "#" .. table.concat(staticEntries, ";")
    .. "#" .. table.concat(sceneryEntries, ";")
]==]

--: Splits the returned payload on `#` into exactly its named sections.
--: Trailing empty sections survive (`gmatch("([^#]*)")` would drop them),
--: so a poll with no statics still parses.
local function splitSections(payload)
    local sections = {}
    local start = 1
    while true do
        local found = string.find(payload, "#", start, true)
        if found == nil then
            sections[#sections + 1] = string.sub(payload, start)
            break
        end
        sections[#sections + 1] = string.sub(payload, start, found - 1)
        start = found + 1
    end
    return sections
end

local function pollAndLog()
    pollCount = pollCount + 1
    local ok, result = dostring("scripting", PROBE_CODE)
    if not ok or type(result) ~= "string" then
        logi("PB_UIDJ_ERR|poll=" .. tostring(pollCount)
            .. "|bridge ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    if string.sub(result, 1, 4) == "ERR|" then
        logi("PB_UIDJ_ERR|poll=" .. tostring(pollCount) .. "|" .. result)
        return
    end

    local s = splitSections(result)
    -- s[1]="OK", 2=meta, 3=api, 4=own, 5=dups, 6=units, 7=statics, 8=scenery
    if s[1] ~= "OK" or #s < 8 then
        logi("PB_UIDJ_ERR|poll=" .. tostring(pollCount)
            .. "|malformed payload, sections=" .. tostring(#s))
        return
    end

    logi("PB_UIDJ_META|poll=" .. tostring(pollCount) .. "|" .. s[2])
    logi("PB_UIDJ_API|poll=" .. tostring(pollCount) .. "|" .. s[3])
    logi("PB_UIDJ_OWN|poll=" .. tostring(pollCount) .. "|" .. s[4])
    logSection("PB_UIDJ_DUP", pollCount, s[5])
    logSection("PB_UIDJ_U", pollCount, s[6])
    logSection("PB_UIDJ_S", pollCount, s[7])
    logSection("PB_UIDJ_C", pollCount, s[8])
end

function petrobrainUnitIdJoin.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    nextPollAt = 0
    pollCount = 0
end

function petrobrainUnitIdJoin.onSimulationFrame()
    if not simulationRunning then
        return
    end
    if pollCount >= MAX_POLLS then
        return
    end
    local now = DCS.getRealTime()
    if now < nextPollAt then
        return
    end
    nextPollAt = now + POLL_INTERVAL_S
    local ok, err = pcall(pollAndLog)
    if not ok then
        logi("PB_UIDJ_ERR|poll=" .. tostring(pollCount) .. "|hook raised: " .. tostring(err))
    end
    if pollCount >= MAX_POLLS then
        logi("PB_UIDJ_DONE|polls=" .. tostring(pollCount))
    end
end

function petrobrainUnitIdJoin.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
end

DCS.setUserCallbacks(petrobrainUnitIdJoin)

logi("loaded")
