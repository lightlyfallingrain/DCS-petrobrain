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

STAGE 0 EXTENSION (`plans/bl-b67-atgm-run/plan.md`, BL-B67) -- 2026-10-29

Added for the ATGM-run plan's own Stage 0 probe sortie, answering Q1
(`LoGetPayloadInfo` shape/cadence, count-drop timing), Q2 (the launched-
missile's `LoGetWorldObjects` `Name`, via the first-seen key dump below)
and Q3 (knob step -> station, and whether a 3038 write is an absolute
set). Still disposable, still deleted once BL-B67's questions are
answered -- this header note does not change that posture, it only says
why this file now also drives the 9K113 knob and the Radiation Reset
button instead of only reading.

  * The first-seen key dump (`seen_names`/`fresh` below) now also records
    every table key on a never-before-seen object, not just its `Name` --
    settles whether a Shturm/Ataka object carries any field a rocket
    object (`C_8`) doesn't.
  * `LoGetPayloadInfo()` is read every poll alongside the object count,
    logging each station's `name:count` and `CurrentStation`.
  * Args 963 (`SHSCHO-KNOB-PTR`) and 882 (`OP-AIM-RESET-RAD-PTR`) are read
    every *frame* (not gated by `POLL_INTERVAL_S`) and logged only when
    their value changes, so the readback of a knob step or a reset press
    lands on the frame it actually took effect, not up to a second late.
  * A scripted sequence steps the knob through all 9 positions
    (`GetDevice(7):performClickableAction(3038, n * 0.1)`, device 7 =
    `DEV_I9K113`, the same device id the production `Export.lua` already
    uses for this unit) two seconds apart, parks on the first step whose
    `CurrentStation` correlates with a loaded station, then presses
    Radiation Reset once (3029: 1, then 0 one second later). After that,
    whenever the parked station's count drops, it auto-advances to the
    next loaded station -- see `maybe_advance_station`'s own comment for
    the one assumption this makes that Q3 itself has not settled yet.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_weapons.log"
local POLL_INTERVAL_S = 1.0

--: Same device id the production Export.lua uses for the 9K113 unit
--: (`DEV_I9K113 = 7`) -- GetDevice(device):performClickableAction(cmd,
--: value) is the one write mechanism this probe needs, no new API.
local DEV_I9K113 = 7
local CMD_KNOB = 3038
local ARG_KNOB = 963
local CMD_RAD_RESET = 3029
local ARG_RAD_RESET = 882
local KNOB_STEP_INTERVAL_S = 2.0
local KNOB_SETTLE_S = 2.0
local RESET_HOLD_S = 1.0

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

--: Last frame's value of each watched arg, logged only on change so a
--: steady knob/button does not spam the log every frame.
local last_arg963 = nil
local last_arg882 = nil

--: Live per-Stations-index count from the most recent `LoGetPayloadInfo`
--: read, keyed by that array's own index -- used by the auto-advance
--: logic below. Whether this index equals the knob step is Q3's own open
--: question, not assumed settled by using it as a dict key here.
local last_station_counts = {}

--: The knob/Radiation-Reset script's own state machine. SWEEP steps
--: through 1..8 (0 is "off" per the documented `CurrentStation` meaning,
--: so it is skipped); PARK writes the first loaded step the sweep found;
--: RESET presses then releases 3029; DONE is terminal and leaves the
--: auto-advance logic (`maybe_advance_station`) in charge from then on.
local knob_phase = "SWEEP"
local sweep_step = 1
local sweep_next_at = 0
local sweep_best_step = nil
local park_at = nil
local reset_press_at = nil
local reset_release_at = nil
local parked_step = nil
local last_parked_count = nil

local function clickable(cmd, value)
    local ok, err = pcall(function()
        GetDevice(DEV_I9K113):performClickableAction(cmd, value)
    end)
    if not ok then
        logline("performClickableAction failed cmd=" .. tostring(cmd)
            .. " value=" .. tostring(value) .. " err=" .. tostring(err))
    end
end

local function read_arg(n)
    local ok, v = pcall(function() return GetDevice(0):get_argument_value(n) end)
    if ok and type(v) == "number" then
        return v
    end
    return nil
end

--: Every frame, not gated by `POLL_INTERVAL_S` -- a knob step or a reset
--: press should show up on the frame it actually took effect.
local function poll_watched_args()
    local a963 = read_arg(ARG_KNOB)
    if a963 ~= nil and a963 ~= last_arg963 then
        logline("arg963(knob)=" .. string.format("%.3f", a963))
        last_arg963 = a963
    end
    local a882 = read_arg(ARG_RAD_RESET)
    if a882 ~= nil and a882 ~= last_arg882 then
        logline("arg882(rad_reset)=" .. string.format("%.3f", a882))
        last_arg882 = a882
    end
end

--: Logs each station's `name:count` and `CurrentStation`, and refreshes
--: `last_station_counts` for the auto-advance logic. `LoGetNameByType`
--: resolves the four-level weapon classification to a display name,
--: falling back to the raw levels when nothing is registered.
local function format_payload(payload)
    local parts = {}
    for i, st in pairs(payload.Stations or {}) do
        local okn, nm = pcall(LoGetNameByType, st.weapon[1], st.weapon[2], st.weapon[3], st.weapon[4])
        parts[#parts + 1] = tostring(i) .. ":" .. tostring(okn and nm or "?") .. ":" .. tostring(st.count)
        last_station_counts[i] = st.count
    end
    return "current=" .. tostring(payload.CurrentStation) .. " stations=" .. table.concat(parts, ";")
end

local function poll_payload()
    local ok, payload = pcall(LoGetPayloadInfo)
    if not ok or type(payload) ~= "table" then
        logline("LoGetPayloadInfo failed: " .. tostring(payload))
        return nil
    end
    logline("payload " .. format_payload(payload))
    return payload
end

--: Advances the SWEEP/PARK/RESET state machine. Runs every frame; each
--: phase gates on model time so it paces itself regardless of frame
--: rate. `sweep_best_step` is picked from whatever `last_station_counts`
--: holds two seconds after writing each step (i.e. from the *next*
--: payload poll after that write), not read synchronously here.
local function run_knob_script(now)
    if knob_phase == "SWEEP" then
        if now < sweep_next_at then
            return
        end
        if sweep_step > 8 then
            knob_phase = "PARK"
            park_at = now
            return
        end
        if sweep_best_step == nil then
            local c = last_station_counts[sweep_step]
            if c ~= nil and c > 0 then
                sweep_best_step = sweep_step
            end
        end
        clickable(CMD_KNOB, sweep_step * 0.1)
        logline("SWEEP write step=" .. tostring(sweep_step))
        sweep_next_at = now + KNOB_STEP_INTERVAL_S
        sweep_step = sweep_step + 1
        return
    end
    if knob_phase == "PARK" then
        if now < park_at + KNOB_SETTLE_S then
            return
        end
        parked_step = sweep_best_step or 1
        clickable(CMD_KNOB, parked_step * 0.1)
        if sweep_best_step == nil then
            logline("PARKED step=" .. tostring(parked_step)
                .. " (no loaded station found during sweep, defaulting to step 1)")
        else
            logline("PARKED step=" .. tostring(parked_step))
        end
        knob_phase = "RESET"
        reset_press_at = now + KNOB_SETTLE_S
        return
    end
    if knob_phase == "RESET" then
        if reset_release_at == nil then
            if now < reset_press_at then
                return
            end
            clickable(CMD_RAD_RESET, 1.0)
            logline("RADIATION RESET pressed (3029=1)")
            reset_release_at = now + RESET_HOLD_S
            return
        end
        if now < reset_release_at then
            return
        end
        clickable(CMD_RAD_RESET, 0.0)
        logline("RADIATION RESET released (3029=0)")
        knob_phase = "DONE"
        return
    end
    -- DONE: the sweep/park/reset script has nothing left to do; count-drop
    -- auto-advance (below) takes over from here.
end

--: Auto-advances the knob to the next loaded station once the parked
--: one's count drops, so the pilot does not have to touch the knob
--: between missiles. Cyclic over steps 1..8.
--:
--: **Assumes the `Stations` array index equals the knob step** -- exactly
--: the mapping Q3 asks about, not yet confirmed by anything in this
--: file. Treat its choice of "next station" as a hypothesis the
--: SWEEP/PARK log either confirms or refutes (if `CurrentStation` after
--: writing step N is N, the assumption holds; if not, this logic is
--: picking the wrong station and the log says so either way).
local function maybe_advance_station(now)
    if parked_step == nil then
        return
    end
    local count = last_station_counts[parked_step]
    if count == nil then
        return
    end
    if last_parked_count ~= nil and count < last_parked_count then
        logline("COUNT DROP step=" .. tostring(parked_step)
            .. " " .. tostring(last_parked_count) .. "->" .. tostring(count))
        local next_step = nil
        for offset = 1, 8 do
            local candidate = ((parked_step - 1 + offset) % 8) + 1
            local c = last_station_counts[candidate]
            if c ~= nil and c > 0 then
                next_step = candidate
                break
            end
        end
        if next_step ~= nil then
            parked_step = next_step
            clickable(CMD_KNOB, parked_step * 0.1)
            logline("ADVANCED to step=" .. tostring(parked_step))
            last_parked_count = last_station_counts[parked_step]
        else
            logline("NO MORE LOADED STATIONS")
            last_parked_count = count
        end
        return
    end
    last_parked_count = count
end

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

    -- Every frame, regardless of the 1 Hz gate below: a knob step or a
    -- reset press needs its readback on the frame it took effect, and the
    -- script itself needs to keep advancing even between 1 Hz polls.
    poll_watched_args()
    run_knob_script(now)

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
            -- One-shot key dump on first sight of this Name -- settles
            -- whether a missile object carries a field a rocket object
            -- (`C_8`) doesn't, without guessing the key in advance.
            local keys = {}
            for k in pairs(obj) do
                keys[#keys + 1] = tostring(k)
            end
            fresh[#fresh + 1] = name .. " keys=" .. table.concat(keys, ",")
        end
    end

    if #fresh > 0 then
        logline("count=" .. tostring(count) .. " NEW: " .. table.concat(fresh, "; "))
    else
        logline("count=" .. tostring(count))
    end

    local payload = poll_payload()
    if payload ~= nil then
        maybe_advance_station(now)
    end
end

function LuaExportStop()
    logline("=== weapon-object probe stop ===")
end
