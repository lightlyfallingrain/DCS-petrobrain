--[[
Petrobrain / ai_pilot_wheel -- BL-16 mode 2's AI-pilot takeover:
driving ED's own AI pilot through the HELPER_AI wheel (device 30) while
the stick is parked. `AC-B12` (`plans/ac-b12-export-modules/plan.md`):
one of the `dofile`-loaded module chunks `Export.lua` (the loader)
composes. Depends only on `core` (loaded first) -- `WHEEL_MENU_BUTTON`/
`WHEEL_CENTER_BUTTON` are read from there (shared with `petrovich.lua`,
same physical device, per `core.lua`'s own comment), never owned here.

**`AC-B13`'s fix lands in `M.on_stop` below** -- `LuaExportStop` never
released an open AI-pilot-wheel press or cleared the takeover state
(filed `aircraft-layer/ROADMAP/AC-B13.md`, from BL-16's takeover-revision
security analysis); this module's own stop hook is the first place that
reset can exist, since the single-file version's `LuaExportStop` never
had one at all -- there is no "move" for it, only a new addition.

**Stage P2a/P2b** (`plans/flight-control/plan.md`, "Stage P2 ready to
build") add the goal channel: `handle_ai_pilot_goal_command` (the inbound
op body-layer's `AircraftLayerClient.write_ai_pilot_goal` drives),
`ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt` (the per-5-Hz-tick nudge
loop, run from `update_ai_pilot_wheel_overlay` below, same cadence
reasoning as the takeover correction's own overlay-dependent steps), and
the mode-cycle-then-press machinery the goal/HVRT loops share with
nothing else in this file. Per the Architecture decision (plan): Lua
decides *which* press, body-layer only ever says *what value* is wanted.
--]]

local M = {}

-- Up/Down/Left/Right are the SAME physical ring buttons/command ids
-- Petrovich's own search wheel already uses (`core.WHEEL_MENU_BUTTON`/
-- `core.WHEEL_CENTER_BUTTON`) -- while parked, this device's wheel shows
-- ED's AI-pilot overlay instead of the search page (confirmed per
-- aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md), not
-- a second device. A short press (<0.5 s) reaches the inner-ring option,
-- a long press/hold reaches the outer-ring option -- that research
-- note's "Operating model" section 5. `AI_WHEEL_LEFT`/`AI_WHEEL_RIGHT`
-- (3003/3002) are Stage P2's own addition -- short press = mode cycle
-- (inner-left) / `HDG LOS` (inner-right, **never pressed by code**, E-P6);
-- long hold = `HDG LEFT`/`HDG RIGHT` (outer). **`AI_WHEEL_RIGHT` is only
-- ever used as a long hold in this file** -- a short press on it is
-- `HDG LOS`, which no code path may issue (E-P6, "never press short
-- right"); the mode cycle always presses `AI_WHEEL_LEFT`, never the
-- right button, matching the measured cycle graph (`FLT<->CBTM`,
-- `HVR->HVRT->CBTM->HVR`, all reached by *left* short presses only).
local AI_WHEEL_UP = 3004
local AI_WHEEL_DOWN = 3005
local AI_WHEEL_LEFT = 3003
local AI_WHEEL_RIGHT = 3002

-- Stick-park animation readback (`plans/flight-control/plan.md`,
-- "Revised 2026-11-16") -- arg 852 (cyclic stow) alone. 952 (pedals
-- stow) is **not** a second park sensor: measured live, 852 + 952 = 1.00
-- at every sample through the handover animation (settling at
-- 852 = 1 / 952 = 0) -- it is 852's exact mirror, so an OR across both
-- reads "parked" whenever the AI is simply not flying, never the real
-- rising edge the takeover sequence needs. Kept as a diagnostic value on
-- the status push only (`ai_pilot_takeover.raw_arg952` below).
local ARG_STICK_PARK = 852
local ARG_PEDALS_PARK = 952
local AI_PILOT_PARK_THRESHOLD = 0.9

-- "Good enough" tolerance for the altitude-correction loop below: how
-- close the AI's held altitude (`alt_text`) must read to a target before
-- the loop treats it as reached. Renamed from `AI_PILOT_NUDGE_EPSILON_M`
-- (same value) now that the same number governs three decisions instead
-- of one (the pre-correction "is anything wrong" check, and both hold
-- phases' own release point). Mirrors body-layer's `AI_PILOT_ALTITUDE_
-- TOLERANCE_M` tunable (`belief/ai_pilot_wheel.py`, default 20) --
-- duplicated here, not read over the wire, because Stage P1 sends no
-- goal message yet (the Architecture decision's per-frame press timing
-- stays entirely in this file until Stage P2 wires a goal channel
-- through); revisit once that channel exists so there is one source of
-- truth for this number.
local AI_PILOT_ALT_TOLERANCE_M = 20.0

-- Delay from the park-rising edge to the blind reference-toggle press
-- (pilot, verbatim: "I'd put a half second delay there").
local AI_PILOT_REFERENCE_TOGGLE_DELAY_S = 0.5

-- How long the overlay must read every field `nil` before the menu is
-- believed closed and re-opened -- the toggle is a single press that
-- closes an open menu just as readily as it opens a closed one, so
-- reacting to one stale-looking tick would flap it shut again. ~1 s AI
-- lag is the user's own recon estimate (research note section 7);
-- measured live, a hand-closed menu reads closed for 3 frames and reads
-- open again ~17 ms after the re-toggle, so this is generous margin, not
-- a tight bound.
local MODE_READ_SETTLE_S = 1.0

-- A real press/release pulse (not a same-frame tap) for a centre press
-- issued while the command menu is open -- measured live (P0-5 re-fly):
-- a same-frame press/release does not toggle ALT REF with the menu open,
-- a 0.15 s pulse does. The blind, menu-closed toggle at takeover (below)
-- stays a same-frame tap; only an open-menu centre press needs this.
local SHORT_PULSE_S = 0.15

-- Safety ceiling on the altitude-correction hold, not an expected
-- outcome: the loop's own readback-driven release is always the normal
-- path, and (unlike a spoken "Hold") this loop has no network dependency
-- to lose. Architect default, **not measured** -- a 742 m error closed
-- in 14 s during the takeover rehearsal probe, comfortably below this;
-- flag raised if a live flight shows it firing on an ordinary-sized
-- error.
local AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S = 60.0

-- ED's radar altitude reference is capped at 700 m AGL (pilot) -- a held
-- target above that forces barometric, so a centre pulse attempting to
-- switch away from baro is refused above this height. Not a judgement
-- call: a measured DCS-internal limit, gating only whether the quick
-- correction path (below) is attempted at all.
local AI_PILOT_QUICK_PATH_MAX_AGL_M = 700.0

-- How close a spoken heading goal must read before the hold releases it.
-- Mirrors body-layer's `AI_PILOT_HEADING_TOLERANCE_DEG` tunable
-- (`belief/ai_pilot_wheel.py`, default 5) -- duplicated here for the
-- identical reason `AI_PILOT_ALT_TOLERANCE_M` above is: the Architecture
-- decision keeps all per-frame press timing in Lua.
local AI_PILOT_HEADING_TOLERANCE_DEG = 5.0

-- The wheel's own highest *real* speed step -- a speed goal at or above
-- this is "aim for MAX" (body-layer's own `AI_PILOT_SPEED_MAX_SENTINEL_
-- KMH`, a value far above any real step, arrives on the wire for this
-- case; this is the threshold Lua itself uses to recognise it, never the
-- sentinel's exact value, so the two sides do not need to agree on one
-- magic number -- see `belief/ai_pilot_wheel.py`'s own comment on
-- `AI_PILOT_SPEED_MAX_SENTINEL_KMH`). Mirrors the top of body-layer's
-- `AI_PILOT_SPEED_STEPS_KMH` (250).
local AI_PILOT_SPEED_TOP_STEP_KMH = 250.0

-- How many short-left mode-cycle presses the goal/HVRT loops will spend
-- trying to reach a mode they need before giving up for this poll
-- (`goal_progress = "mode_blocked"`, retried next poll, never dropped).
-- The known cycle orders (`FLT<->CBTM`, `HVR->HVRT->CBTM->HVR`) bound
-- every reachable mode within 2 presses from any other; 3 gives one
-- spare attempt rather than guessing at an open-ended N (plan, "Amended
-- 2026-11-15").
local MODE_CYCLE_MAX_ATTEMPTS = 3

-- Safety ceiling on an open HVRT translate press if the spoken "Hold" is
-- lost (a network drop between audio-adapter and body-layer, a missed
-- recognition) -- the normal stop is always the player's own "Hold",
-- never this. Architect default, **not** user-specified (plan's own
-- flag, Q-P2) -- revisit if a sortie shows it firing in ordinary use.
local HVRT_TRANSLATE_MAX_HOLD_S = 15.0

local ai_pilot_parked_active = false
local ai_pilot_mode_text = nil
local ai_pilot_course_text = nil
local ai_pilot_alt_text = nil
local ai_pilot_alt_add_text = nil
local ai_pilot_speed_text = nil
local ai_pilot_last_press = nil
-- A separate pending-release slot from `petrovich.lua`'s own
-- `pending_release_t`/`WHEEL_CENTER_BUTTON` -- that one belongs to
-- Petrovich's own search wheel and may be open at the same time as this
-- one. Shared by every timed press this sequence issues (the open-menu
-- centre pulse and both altitude-hold directions): at most one is ever
-- open at a time, so one slot is enough, and unpark's own release
-- (below) does not need to know which kind it is.
local ai_wheel_pending_release_t = nil
local ai_wheel_pending_cmd = nil

-- Stage P2's own pending-release pair, deliberately **separate** from
-- the takeover-correction one above: the two mechanisms never need to
-- hold a press at the same time in correct operation (body-layer's own
-- `decide_ai_pilot_wheel` never promotes a goal while a takeover
-- correction is still running), but keeping them apart means a goal
-- hold's own release logic can never misread or clear takeover-specific
-- state (`ai_pilot_takeover.correction_hold_cmd`/`.stage`), and the
-- reverse -- correctness by construction rather than by that ordering
-- invariant holding everywhere it is assumed.
local ai_wheel_goal_pending_release_t = nil
local ai_wheel_goal_pending_cmd = nil

-- Takeover sub-sequence state (plan's own "Co-moving Fields" table,
-- Stage P1 revision), grouped into **one** table rather than one local
-- per field -- a deliberate, flagged departure from this project's own
-- "individual locals, no `apw` table" convention (plan, "One naming
-- departure..."): the single-file `Export.lua` hit Lua 5.1's hard
-- 200-live-local ceiling once this revision's dozen-odd new fields were
-- added as separate locals. Every field is initialised here, in one
-- place, so there is no forward-reference/hoisting risk (the concern the
-- original convention was guarding against) -- nothing reads a field
-- before this table exists. `.stage`: `nil` while unparked or once the
-- sequence has resolved, else `"toggling_reference"` ->
-- `"opening_menu"` -> `"correcting_altitude"`. `.t`: the rising-edge
-- model time, for the 0.5 s reference-toggle delay. `.handover_
-- altitude_m`: the handover goal, actual MSL snapshotted in the same
-- frame arg 852 crosses the threshold (pilot, Q1 -- "handolver alt"),
-- fixed for the life of one takeover. `.menu_open`: our own belief about
-- whether the command menu is open -- written only by the toggle presses
-- below, never re-read before being trusted (the table's own "belief
-- flips to match what is about to be true" rule). `.menu_closed_since_t`:
-- set the first tick the overlay reads every field `nil` while
-- `.menu_open` is true, cleared the moment a real field reads back --
-- drives the `MODE_READ_SETTLE_S` reopen check. `.awaiting_correction_
-- decision`: true from the menu-open press until the first tick the
-- overlay reads back populated -- the one-shot "decide what correction
-- (if any) is needed" step waits for this. `.correction_path`: diagnostic
-- + decision record of which correction path this takeover used --
-- `"quick"`/`"hold"`/`"none"`, `nil` before a decision is reached --
-- carried on the status push so a flight where the quick path happened
-- to work is not read as the normal case. `.correction_substage`: the
-- quick path's own sub-step (`"quick_read1"`/`"quick_read2"`), `nil`
-- outside it. `.correction_phase`: the two-phase hold's own sub-step
-- (`"phase1"`/`"phase2"`), `nil` outside a hold. `.correction_hold_cmd`:
-- the command (`AI_WHEEL_UP`/`AI_WHEEL_DOWN`) currently held open by the
-- correction loop, or `nil` if none -- distinct from `ai_wheel_pending_
-- cmd` above (which this also sets): this one is only ever a hold, so
-- the safety-ceiling release at its deadline knows to clear the
-- correction's own state too. `.raw_arg852`/`.raw_arg952`: raw diagnostic
-- readings of both park args, refreshed every frame -- the telemetry
-- mystery's own fix (plan, "The P1 telemetry mystery"), carried on the
-- wire so a recurrence is directly visible, not re-inferred from a
-- probe. `.menu_open_at_t`: the model time the menu-open tap is due, set
-- when the blind centre tap fires -- `AI_PILOT_MENU_OPEN_DELAY_S` after
-- it, matching the gap the rehearsal probe actually flew (centre at
-- +0.5 s, menu at +1.0 s after takeover), rather than the same frame.
-- `.AI_PILOT_MENU_OPEN_DELAY_S` is the one constant here, not per-
-- sequence state -- kept as a field on this table rather than a new
-- top-level local, since the single-file version was already at Lua
-- 5.1's 200-live-local ceiling and a table field costs no chunk local.
local ai_pilot_takeover = {
    stage = nil,
    t = nil,
    handover_altitude_m = nil,
    menu_open = false,
    menu_open_at_t = nil,
    menu_closed_since_t = nil,
    awaiting_correction_decision = false,
    correction_path = nil,
    correction_substage = nil,
    correction_phase = nil,
    correction_hold_cmd = nil,
    raw_arg852 = nil,
    raw_arg952 = nil,
    AI_PILOT_MENU_OPEN_DELAY_S = 0.5,
}

-- Stage P2a/P2b's own co-moving state -- one table, same reasoning as
-- `ai_pilot_takeover` above (the Lua 5.1 200-local ceiling). `.param`:
-- mirrors body-layer's `AiPilotWheelGoal.active_param` -- `nil` (idle),
-- `"heading"`/`"altitude"`/`"speed"`. `.heading_target_deg`/`.altitude_
-- target_m`/`.altitude_target_ref`/`.speed_target_kmh`: the targets for
-- whichever of those `.param` names -- only the one matching `.param` is
-- ever acted on (the selector design, plan's own wire-shape note).
-- `.goal_seq`: echoed on the status push so body-layer can tell which
-- goal a report belongs to. `.progress`: `"idle"`/`"pressing"`/
-- `"cycling_mode"`/`"settled"`/`"mode_blocked"`/`"released_timeout"`.
-- `.mode_cycle_attempts`: this poll's own count toward `MODE_CYCLE_MAX_
-- ATTEMPTS`, reset whenever `.param` changes or the needed mode is
-- reached. `.hold_cmd`: the heading/altitude direction (`AI_WHEEL_UP`/
-- `_DOWN`/`_LEFT`/`_RIGHT`) currently held open by the goal loop, or
-- `nil` -- distinct from `ai_pilot_takeover.correction_hold_cmd`, same
-- reason the two pending-release pairs are kept apart. `.toggling_
-- reference`: true while an altitude goal's own reference-change pulse
-- is in flight, so the tick does not re-issue a second pulse on top of
-- one already running. `.hvrt_direction`: mirrors body-layer's own
-- field, `nil`/`"left"`/`"right"`/`"forward"`/`"back"`. `.hvrt_hold_cmd`/
-- `.hvrt_started_t`: the HVRT translate press currently held open (if
-- any) and when it opened, for the safety timeout.
local ai_pilot_goal = {
    param = nil,
    heading_target_deg = nil,
    altitude_target_m = nil,
    altitude_target_ref = nil,
    speed_target_kmh = nil,
    goal_seq = 0,
    progress = "idle",
    mode_cycle_attempts = 0,
    hold_cmd = nil,
    toggling_reference = false,
    hvrt_direction = nil,
    hvrt_hold_cmd = nil,
    hvrt_started_t = nil,
}

-- Flattens one `list_indication(HELPERAI_DEVICE_ID)` raw dump into a flat
-- `{name: value}` table of every populated (non-child-only) node --
-- mirrors `aircraft-layer/src/schema/petrovich_indication.py`'s
-- `parse_indication_text` exactly (same recursive-descent algorithm,
-- same "parent value wins over a same-named descendant" ordering), but
-- is a **second, Lua-side** implementation, not a reuse of that Python
-- module: the AI-pilot nudge loop (`update_ai_pilot_wheel_overlay` below)
-- must decide its next press locally, without round-tripping through
-- body-layer (the Architecture decision above). Called from the 5 Hz
-- export tick, not per frame (`plans/flight-control/perf-batch-a.md`).
-- Pure function, degrades gracefully on unexpected structure (skips
-- rather than errors), same posture as the Python parser it mirrors.
local function parse_helperai_overlay_fields(raw)
    local lines = {}
    for line in (raw .. "\n"):gmatch("([^\n]*)\n") do
        lines[#lines + 1] = line
    end
    local n = #lines
    local fields = {}

    local function parse_nodes(start)
        local i = start
        while i <= n do
            local line = lines[i]
            if line == "" then
                i = i + 1
            elseif line == "}" then
                return i
            elseif line ~= "-----------------------------------------" then
                i = i + 1
            else
                i = i + 1
                if i > n then break end
                local name = lines[i]
                i = i + 1
                local value = nil
                if i <= n and lines[i] == "children are {" then
                    i = i + 1
                elseif i <= n then
                    value = lines[i]
                    i = i + 1
                    if i <= n and lines[i] == "children are {" then
                        i = i + 1
                    end
                end
                if value ~= nil then
                    fields[name] = value
                end
                i = parse_nodes(i)
                if i <= n and lines[i] == "}" then
                    i = i + 1
                end
            end
        end
        return i
    end

    parse_nodes(1)
    return fields
end

-- Pure decision (P1 test): which direction (if any) the correction loop
-- should hold to move `held_m` toward `target_m` -- `nil` means "already
-- within tolerance, or nothing to compare" (a missing reading on either
-- side is never treated as "needs correction"). The AI climbs toward a
-- high target, so a held value *above* the target means press DOWN to
-- lower it; below means press UP.
local function ai_pilot_correction_direction(held_m, target_m)
    if held_m == nil or target_m == nil then
        return nil
    end
    if math.abs(held_m - target_m) <= AI_PILOT_ALT_TOLERANCE_M then
        return nil
    end
    if held_m > target_m then
        return AI_WHEEL_DOWN
    end
    return AI_WHEEL_UP
end

-- Pure decision (P1 test): the quick correction path (a menu-open centre
-- pulse) is only attempted below `AI_PILOT_QUICK_PATH_MAX_AGL_M` -- an
-- unreadable AGL is never treated as eligible.
local function ai_pilot_quick_path_eligible(agl_m)
    return agl_m ~= nil and agl_m < AI_PILOT_QUICK_PATH_MAX_AGL_M
end

-- The AI's currently-held altitude, read off `alt_text` (purely numeric,
-- e.g. "196" -- the "R"/"B" reference is the separate `alt_add_text`
-- field, per the overlay-readback research note section 3). `nil` if
-- `alt_text` is absent or not numeric this frame.
local function ai_pilot_parse_altitude_text(alt_text)
    if alt_text == nil then
        return nil
    end
    return tonumber(alt_text)
end

-- The aircraft's own actual altitude, picked by the AI's currently-
-- displayed reference ("R" radar/AGL, "B" barometric/MSL) so the nudge
-- compares like with like. `nil` (no comparison) while the reference is
-- unknown this frame, rather than guessing one.
local function ai_pilot_actual_altitude_m(alt_add_text, alt_agl_m, alt_msl_m)
    if alt_add_text == "R" then
        return alt_agl_m
    elseif alt_add_text == "B" then
        return alt_msl_m
    end
    return nil
end

-- Stage P2's own pure decisions (P2a/P2b tests), grouped here rather
-- than scattered among the takeover-correction functions above, which
-- they share no state with.

-- FLT and HVR both support the hold vocabulary a heading/altitude/speed
-- goal needs -- `nil` (not yet read) is never treated as acceptable.
local function ai_pilot_goal_mode_ready(mode_text)
    return mode_text == "FLT" or mode_text == "HVR"
end

-- Pure decision (P2a test): which direction (if any) to hold to turn a
-- heading toward `target_deg`, by the shortest angular path. `nil` means
-- already within `AI_PILOT_HEADING_TOLERANCE_DEG`, or a missing reading
-- on either side.
local function ai_pilot_goal_heading_direction(held_deg, target_deg)
    if held_deg == nil or target_deg == nil then
        return nil
    end
    local diff = (target_deg - held_deg + 540) % 360 - 180
    if math.abs(diff) <= AI_PILOT_HEADING_TOLERANCE_DEG then
        return nil
    end
    if diff > 0 then
        return AI_WHEEL_RIGHT
    end
    return AI_WHEEL_LEFT
end

-- `"radar"`/`"barometric"` -> the overlay's own single-letter reference
-- code, or `nil` for an unrecognised/absent value.
local function ai_pilot_goal_ref_letter(ref)
    if ref == "radar" then
        return "R"
    elseif ref == "barometric" then
        return "B"
    end
    return nil
end

-- Pure decision (P2a test): does the goal's own altitude reference
-- differ from what the overlay currently shows? A missing goal
-- reference or a currently-unreadable overlay reference is never
-- treated as a mismatch -- there is nothing to compare.
local function ai_pilot_goal_altitude_ref_mismatch(ref, current_letter)
    local wanted_letter = ai_pilot_goal_ref_letter(ref)
    if wanted_letter == nil or current_letter == nil then
        return false
    end
    return wanted_letter ~= current_letter
end

-- Pure decision (P2a test): the speed goal's tap loop has no hold
-- semantics at all (plan: "not a hold at all -- one short tap... per
-- tick") -- `speed_text` reads an exact discrete step (or the literal
-- string `"MAX"`, P0-3), so this is an exact-match comparison, never a
-- tolerance window. `nil` means already at the target step, or a
-- missing/unreadable reading on either side.
local function ai_pilot_goal_speed_tap_direction(speed_text, target_kmh)
    if target_kmh == nil then
        return nil
    end
    local wants_max = target_kmh > AI_PILOT_SPEED_TOP_STEP_KMH
    if speed_text == "MAX" then
        if wants_max then
            return nil
        end
        return AI_WHEEL_DOWN
    end
    local held_kmh = tonumber(speed_text)
    if held_kmh == nil then
        return nil
    end
    if wants_max then
        return AI_WHEEL_UP
    end
    if held_kmh == target_kmh then
        return nil
    elseif held_kmh < target_kmh then
        return AI_WHEEL_UP
    end
    return AI_WHEEL_DOWN
end

-- `"left"`/`"right"`/`"forward"`/`"back"` -> the outer-ring button that
-- holds that HVRT translate direction (layout research note section 2:
-- `HOVER LEFT/RIGHT/FWD/BACK`), or `nil` for an unrecognised value.
local function ai_pilot_goal_hvrt_direction_cmd(direction)
    if direction == "left" then
        return AI_WHEEL_LEFT
    elseif direction == "right" then
        return AI_WHEEL_RIGHT
    elseif direction == "forward" then
        return AI_WHEEL_UP
    elseif direction == "back" then
        return AI_WHEEL_DOWN
    end
    return nil
end

-- Park rising-edge detection on arg 852 **alone** (plan, "Revised
-- 2026-11-16", point 1 -- 952 dropped, see `ARG_PEDALS_PARK`'s own
-- comment above) -- pure decision, P1 test: "park-rising detection".
-- Returns `(now_parked, rising)`.
local function ai_pilot_park_rising(prev_parked, stick_park_arg)
    local now_parked = stick_park_arg ~= nil and stick_park_arg >= AI_PILOT_PARK_THRESHOLD
    return now_parked, (now_parked and not prev_parked)
end

-- Same-frame press/release of either toggle button this sequence uses
-- (`core.WHEEL_CENTER_BUTTON` blind, menu closed -- proven live, P0
-- re-fly -- or `core.WHEEL_MENU_BUTTON` to open/re-open/close the
-- command menu, a true toggle on the DCS side). One shared helper rather
-- than two near-identical ones -- **not** the forbidden generic
-- `press(direction, duration)` shape (plan's own Implementer note,
-- E-P6): both buttons it is ever called with are fixed, pre-existing
-- wheel-menu constants, never one of the four directional ring buttons,
-- and there is no duration parameter.
local function ai_pilot_tap30(cmd)
    safe_call(function()
        GetDevice(30):performClickableAction(cmd, 1)
    end)
    safe_call(function()
        GetDevice(30):performClickableAction(cmd, 0)
    end)
end

-- Stage P2's own hold open/release pair -- deliberately **not** a
-- generic `press(direction, duration)` combinator (E-P6, same posture
-- as `ai_pilot_open_hold` below): `cmd` only ever arrives from
-- `ai_pilot_goal_heading_direction`/`ai_pilot_correction_direction`'s own
-- return values (`AI_WHEEL_UP`/`_DOWN`/`_LEFT`/`_RIGHT`), each already
-- restricted to a safe direction by its own caller, and there is no
-- duration parameter -- the safety ceiling armed here is always the
-- same fixed value. Writes the goal's own pending-release pair
-- (`ai_wheel_goal_pending_cmd`/`_release_t`), never the takeover
-- correction's -- see that pair's own comment for why they are kept
-- separate.
local function ai_pilot_goal_open_hold(cmd, t)
    safe_call(function()
        GetDevice(30):performClickableAction(cmd, 1)
    end)
    ai_pilot_goal.hold_cmd = cmd
    ai_wheel_goal_pending_cmd = cmd
    ai_wheel_goal_pending_release_t = t + AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S
end

-- Releases an open goal hold, if any -- a no-op when `ai_pilot_goal.
-- hold_cmd` is already `nil`, so every caller (a settled readback, a
-- different direction needed, a different `param` arriving, unpark) can
-- call this unconditionally.
local function ai_pilot_goal_release_hold()
    if ai_pilot_goal.hold_cmd == nil then
        return
    end
    safe_call(function()
        GetDevice(30):performClickableAction(ai_pilot_goal.hold_cmd, 0)
    end)
    ai_pilot_goal.hold_cmd = nil
    ai_wheel_goal_pending_cmd = nil
    ai_wheel_goal_pending_release_t = nil
end

-- Opens the altitude-correction hold -- **not** a generic `press(
-- direction, duration)` entry point (plan's own Implementer note,
-- E-P6): `cmd` is restricted to `AI_WHEEL_UP`/`AI_WHEEL_DOWN` by its one
-- caller (`ai_pilot_correction_direction`'s own return type), the
-- correction loop is the only thing that ever calls this, and nothing
-- here accepts a duration -- the deadline armed below is always the
-- same fixed safety ceiling. Dedicated to altitude correction, not a
-- cross-action combinator; kept as one function rather than an up/down
-- pair to stay under Lua 5.1's 200-live-local ceiling (see `ai_pilot_
-- takeover`'s own comment above). The loop's own readback check
-- (`ai_pilot_check_hold_convergence` below) releases early on
-- convergence and clears the deadline itself; this only arms it.
local function ai_pilot_open_hold(cmd, t)
    safe_call(function()
        GetDevice(30):performClickableAction(cmd, 1)
    end)
    ai_pilot_takeover.correction_hold_cmd = cmd
    ai_wheel_pending_cmd = cmd
    ai_wheel_pending_release_t = t + AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S
end

-- Begins the two-phase hold (plan, "Revised 2026-11-16" amendment,
-- point 4): phase 1 chases the aircraft's own *live* altitude (whichever
-- reference `alt_add_text` currently shows -- compares like with like,
-- same reasoning as the original Stage P1 nudge) to stop the climb;
-- phase 2, entered only once phase 1 is released or skipped, chases the
-- fixed handover snapshot. Either phase is skipped outright if `held` is
-- already within tolerance of its own target -- "skip phases that are
-- already within tolerance" (plan). Falls through to `"none"` (nothing
-- to correct, takeover resolved) if neither phase is needed, or if
-- `held` could not be read at all.
local function ai_pilot_begin_hold_phase(t, held)
    if held == nil then
        ai_pilot_takeover.correction_phase = nil
        ai_pilot_takeover.stage = nil
        return
    end
    local live_m = ai_pilot_actual_altitude_m(
        ai_pilot_alt_add_text,
        safe_call(LoGetAltitudeAboveGroundLevel),
        safe_call(LoGetAltitudeAboveSeaLevel))
    local dir1 = ai_pilot_correction_direction(held, live_m)
    if dir1 ~= nil then
        ai_pilot_takeover.correction_phase = "phase1"
        ai_pilot_open_hold(dir1, t)
        ai_pilot_last_press = "correction_hold_phase1"
        return
    end
    local dir2 = ai_pilot_correction_direction(held, ai_pilot_takeover.handover_altitude_m)
    if dir2 == nil then
        ai_pilot_takeover.correction_phase = nil
        ai_pilot_takeover.stage = nil
        return
    end
    ai_pilot_takeover.correction_phase = "phase2"
    ai_pilot_open_hold(dir2, t)
    ai_pilot_last_press = "correction_hold_phase2"
end

-- The one-shot decision, taken once the menu's first post-open read
-- lands: is anything wrong, and if so, which correction path. Plan,
-- "Revised 2026-11-16" amendment, point 5 -- quick path only below
-- `AI_PILOT_QUICK_PATH_MAX_AGL_M`, the two-phase hold otherwise.
local function ai_pilot_decide_correction(t)
    local held = ai_pilot_parse_altitude_text(ai_pilot_alt_text)
    if ai_pilot_correction_direction(held, ai_pilot_takeover.handover_altitude_m) == nil then
        ai_pilot_takeover.correction_path = "none"
        ai_pilot_takeover.stage = nil
        return
    end
    if ai_pilot_quick_path_eligible(safe_call(LoGetAltitudeAboveGroundLevel)) then
        ai_pilot_takeover.correction_path = "quick"
        ai_pilot_takeover.correction_substage = "quick_read1"
        -- `SHORT_PULSE_S` centre pulse, menu open -- the quick path's own
        -- press shape, released by the generic per-frame deadline check
        -- in `run_ai_pilot_wheel` below.
        safe_call(function()
            GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 1)
        end)
        ai_wheel_pending_cmd = WHEEL_CENTER_BUTTON
        ai_wheel_pending_release_t = t + SHORT_PULSE_S
        ai_pilot_last_press = "correction_quick_pulse1"
    else
        ai_pilot_takeover.correction_path = "hold"
        ai_pilot_begin_hold_phase(t, held)
    end
end

-- Per-5-Hz-tick readback check while a hold is open (plan point 4/
-- amendment): releases the instant the held value reads within
-- tolerance of this phase's own target, then either advances to phase 2
-- or resolves the takeover. An unreadable tick changes nothing -- the
-- safety ceiling (`run_ai_pilot_wheel`'s own deadline check) still
-- governs if readings never recover.
local function ai_pilot_check_hold_convergence(t)
    local held = ai_pilot_parse_altitude_text(ai_pilot_alt_text)
    local target_m
    if ai_pilot_takeover.correction_phase == "phase1" then
        target_m = ai_pilot_actual_altitude_m(
            ai_pilot_alt_add_text,
            safe_call(LoGetAltitudeAboveGroundLevel),
            safe_call(LoGetAltitudeAboveSeaLevel))
    else
        target_m = ai_pilot_takeover.handover_altitude_m
    end
    if held == nil or target_m == nil or math.abs(held - target_m) > AI_PILOT_ALT_TOLERANCE_M then
        return
    end

    safe_call(function()
        GetDevice(30):performClickableAction(ai_pilot_takeover.correction_hold_cmd, 0)
    end)
    ai_pilot_takeover.correction_hold_cmd = nil
    ai_wheel_pending_release_t = nil
    ai_wheel_pending_cmd = nil

    if ai_pilot_takeover.correction_phase == "phase2" then
        ai_pilot_takeover.correction_phase = nil
        ai_pilot_takeover.stage = nil
        return
    end
    -- phase1 released: `held` is now within tolerance of live altitude,
    -- so re-running the initial decision naturally skips phase1 (its own
    -- `dir1` resolves to `nil`) and opens phase2 (or resolves) against
    -- the handover snapshot -- same call the hold path's own first entry
    -- uses, rather than a second copy of phase2's open/resolve logic.
    ai_pilot_begin_hold_phase(t, held)
end

-- Stage P2a: the heading goal's own tick, called once the mode is
-- already acceptable (`ai_pilot_goal_tick` below has already checked).
-- Releases and reports `"settled"` the instant the readback crosses into
-- tolerance; switches direction immediately if the needed direction
-- changes (a preempting voice command, or simply crossing through the
-- target) without waiting for a release first.
local function ai_pilot_goal_tick_heading(t)
    local held_deg = tonumber(ai_pilot_course_text)
    local dir = ai_pilot_goal_heading_direction(held_deg, ai_pilot_goal.heading_target_deg)
    if dir == nil then
        ai_pilot_goal_release_hold()
        ai_pilot_goal.progress = "settled"
        return
    end
    ai_pilot_goal.progress = "pressing"
    if ai_pilot_goal.hold_cmd ~= dir then
        ai_pilot_goal_release_hold()
        ai_pilot_goal_open_hold(dir, t)
    end
end

-- Stage P2a: the altitude goal's own tick. Reuses `ai_pilot_correction_
-- direction` for the hold-and-poll direction (identical "good enough"
-- semantics to the takeover correction, plan: "reusing Stage P1's own
-- hold-and-poll shape") but adds the one thing the correction loop never
-- needed: a reference change, via the same real pulse
-- (`SHORT_PULSE_S`, menu already open per Stage P1) the takeover
-- correction's own quick path uses -- attempted first, every tick, until
-- the overlay confirms the switch, before any altitude hold is opened.
local function ai_pilot_goal_tick_altitude(t)
    if ai_pilot_goal_altitude_ref_mismatch(
        ai_pilot_goal.altitude_target_ref, ai_pilot_alt_add_text) then
        if not ai_pilot_goal.toggling_reference then
            ai_pilot_goal.toggling_reference = true
            ai_pilot_goal.progress = "pressing"
            safe_call(function()
                GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 1)
            end)
            ai_wheel_goal_pending_cmd = WHEEL_CENTER_BUTTON
            ai_wheel_goal_pending_release_t = t + SHORT_PULSE_S
            ai_pilot_last_press = "goal_reference_toggle"
        end
        return
    end
    ai_pilot_goal.toggling_reference = false
    local held_m = ai_pilot_parse_altitude_text(ai_pilot_alt_text)
    local dir = ai_pilot_correction_direction(held_m, ai_pilot_goal.altitude_target_m)
    if dir == nil then
        ai_pilot_goal_release_hold()
        ai_pilot_goal.progress = "settled"
        return
    end
    ai_pilot_goal.progress = "pressing"
    if ai_pilot_goal.hold_cmd ~= dir then
        ai_pilot_goal_release_hold()
        ai_pilot_goal_open_hold(dir, t)
    end
end

-- Stage P2a: the speed goal's own tick -- a short tap per tick, never a
-- hold (plan: "not a hold at all"), so there is nothing to open/release
-- here at all, unlike heading/altitude.
local function ai_pilot_goal_tick_speed(t)
    local dir = ai_pilot_goal_speed_tap_direction(
        ai_pilot_speed_text, ai_pilot_goal.speed_target_kmh)
    if dir == nil then
        ai_pilot_goal.progress = "settled"
        return
    end
    ai_pilot_goal.progress = "pressing"
    ai_pilot_tap30(dir)
    ai_pilot_last_press = "goal_speed_tap"
end

-- Stage P2a's own dispatcher, run once per overlay tick while a
-- heading/altitude/speed goal is active (`ai_pilot_goal.param ~= nil`):
-- cycles to an acceptable mode first (bounded by `MODE_CYCLE_MAX_
-- ATTEMPTS`, reported `"mode_blocked"` and retried next tick if
-- exhausted, never dropped), then dispatches to the one tick function
-- `.param` needs. No-op (idle) while nothing is outstanding.
local function ai_pilot_goal_tick(t)
    if ai_pilot_goal.param == nil then
        return
    end
    if not ai_pilot_goal_mode_ready(ai_pilot_mode_text) then
        ai_pilot_goal_release_hold()
        if ai_pilot_goal.mode_cycle_attempts >= MODE_CYCLE_MAX_ATTEMPTS then
            ai_pilot_goal.progress = "mode_blocked"
            return
        end
        ai_pilot_goal.progress = "cycling_mode"
        ai_pilot_tap30(AI_WHEEL_LEFT)
        ai_pilot_goal.mode_cycle_attempts = ai_pilot_goal.mode_cycle_attempts + 1
        ai_pilot_last_press = "goal_mode_cycle"
        return
    end
    ai_pilot_goal.mode_cycle_attempts = 0
    if ai_pilot_goal.param == "heading" then
        ai_pilot_goal_tick_heading(t)
    elseif ai_pilot_goal.param == "altitude" then
        ai_pilot_goal_tick_altitude(t)
    else
        ai_pilot_goal_tick_speed(t)
    end
end

-- Stage P2b: HVRT translate's own tick, independent of `ai_pilot_goal_
-- tick` above (mode-exclusive by construction, plan's own note) --
-- `.hvrt_direction` has no queueing/active-param state of its own, only
-- a held press that opens, redirects or releases as the field changes,
-- plus the safety timeout. **Only ever reached from `HVR` or already
-- `HVRT`** -- body-layer's own hover precondition (crew_console's
-- "unable, not ready" check) is what keeps this from ever being asked
-- to cycle from `FLT`, where the known cycle graph could not reach
-- `HVRT` within `MODE_CYCLE_MAX_ATTEMPTS` at all.
local function ai_pilot_goal_tick_hvrt(t)
    if ai_pilot_goal.hvrt_direction == nil then
        if ai_pilot_goal.hvrt_hold_cmd ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
            end)
            ai_pilot_goal.hvrt_hold_cmd = nil
            ai_pilot_goal.hvrt_started_t = nil
        end
        return
    end
    if ai_pilot_mode_text ~= "HVRT" then
        if ai_pilot_mode_text ~= nil then
            ai_pilot_tap30(AI_WHEEL_LEFT)
            ai_pilot_last_press = "goal_hvrt_mode_cycle"
        end
        return
    end
    local wanted_cmd = ai_pilot_goal_hvrt_direction_cmd(ai_pilot_goal.hvrt_direction)
    if wanted_cmd ~= ai_pilot_goal.hvrt_hold_cmd then
        if ai_pilot_goal.hvrt_hold_cmd ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
            end)
        end
        safe_call(function()
            GetDevice(30):performClickableAction(wanted_cmd, 1)
        end)
        ai_pilot_goal.hvrt_hold_cmd = wanted_cmd
        ai_pilot_goal.hvrt_started_t = t
        ai_pilot_last_press = "goal_hvrt_translate"
    elseif ai_pilot_goal.hvrt_started_t ~= nil
        and t - ai_pilot_goal.hvrt_started_t >= HVRT_TRANSLATE_MAX_HOLD_S then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
        end)
        ai_pilot_goal.hvrt_hold_cmd = nil
        ai_pilot_goal.hvrt_started_t = nil
        ai_pilot_goal.hvrt_direction = nil
        ai_pilot_goal.progress = "released_timeout"
    end
end

-- Per-frame AI-pilot-wheel loop, called every frame (not gated by the
-- 5 Hz export throttle) beside `sight.sight_servo_tick` -- the takeover
-- sequence's own time-driven steps (the rising-edge snapshot, the
-- 0.5 s-delayed blind reference toggle, the menu-open press right after
-- it) live here because they do not need a fresh overlay read; the
-- overlay-dependent steps (the correction decision, the keep-open check,
-- hold convergence) live in `update_ai_pilot_wheel_overlay` below, run
-- from the 5 Hz export tick. The shared press-release deadline (pulses
-- and the hold's own safety ceiling) is also checked here, every frame,
-- same reasoning as `sight.sight_servo_tick`'s per-frame correction.
-- E-P10: unpark releases any open press, closes the menu if this
-- sequence opened it, and drops every takeover-sequence field
-- immediately, the same frame -- nothing resumes on the next park.
local function run_ai_pilot_wheel(t)
    if ai_wheel_pending_release_t ~= nil and t >= ai_wheel_pending_release_t then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_pending_cmd, 0)
        end)
        local was_hold = ai_wheel_pending_cmd == AI_WHEEL_UP or ai_wheel_pending_cmd == AI_WHEEL_DOWN
        ai_wheel_pending_release_t = nil
        ai_wheel_pending_cmd = nil
        if was_hold then
            -- Safety-ceiling timeout, not convergence: give up on this
            -- hold rather than leave `ai_pilot_takeover.correction_hold_cmd`
            -- pointing at a command that is no longer pressed.
            ai_pilot_takeover.correction_hold_cmd = nil
            ai_pilot_takeover.correction_phase = nil
            ai_pilot_takeover.stage = nil
        end
    end

    -- Stage P2's own release-deadline check, against its own pending
    -- pair (never the takeover one above) -- covers both the altitude
    -- goal's reference-toggle pulse (`SHORT_PULSE_S`) and the heading/
    -- altitude hold's own safety ceiling.
    if ai_wheel_goal_pending_release_t ~= nil and t >= ai_wheel_goal_pending_release_t then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_goal_pending_cmd, 0)
        end)
        local was_hold = ai_wheel_goal_pending_cmd == AI_WHEEL_UP
            or ai_wheel_goal_pending_cmd == AI_WHEEL_DOWN
            or ai_wheel_goal_pending_cmd == AI_WHEEL_LEFT
            or ai_wheel_goal_pending_cmd == AI_WHEEL_RIGHT
        ai_wheel_goal_pending_release_t = nil
        ai_wheel_goal_pending_cmd = nil
        if was_hold then
            -- Safety-ceiling timeout, not convergence -- same posture as
            -- the takeover correction's own timeout above.
            ai_pilot_goal.hold_cmd = nil
        end
    end

    local stick_park = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_STICK_PARK)
    end)
    local pedals_park = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_PEDALS_PARK)
    end)
    ai_pilot_takeover.raw_arg852 = stick_park
    ai_pilot_takeover.raw_arg952 = pedals_park

    local now_parked, rising = ai_pilot_park_rising(ai_pilot_parked_active, stick_park)
    ai_pilot_parked_active = now_parked

    if not now_parked then
        if ai_wheel_pending_release_t ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_wheel_pending_cmd, 0)
            end)
            ai_wheel_pending_release_t = nil
            ai_wheel_pending_cmd = nil
        end
        -- Stage P2's own release, same frame -- any open goal hold or
        -- HVRT translate press, before the menu closes (E-P10: "nothing
        -- resumes on the next park").
        if ai_wheel_goal_pending_release_t ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_wheel_goal_pending_cmd, 0)
            end)
            ai_wheel_goal_pending_release_t = nil
            ai_wheel_goal_pending_cmd = nil
        end
        if ai_pilot_goal.hvrt_hold_cmd ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
            end)
        end
        if ai_pilot_takeover.menu_open then
            ai_pilot_tap30(WHEEL_MENU_BUTTON)
            ai_pilot_takeover.menu_open = false
        end
        ai_pilot_mode_text = nil
        ai_pilot_course_text = nil
        ai_pilot_alt_text = nil
        ai_pilot_alt_add_text = nil
        ai_pilot_speed_text = nil
        ai_pilot_takeover.stage = nil
        ai_pilot_takeover.t = nil
        ai_pilot_takeover.handover_altitude_m = nil
        ai_pilot_takeover.menu_open_at_t = nil
        ai_pilot_takeover.menu_closed_since_t = nil
        ai_pilot_takeover.awaiting_correction_decision = false
        ai_pilot_takeover.correction_path = nil
        ai_pilot_takeover.correction_substage = nil
        ai_pilot_takeover.correction_phase = nil
        ai_pilot_takeover.correction_hold_cmd = nil
        ai_pilot_goal.param = nil
        ai_pilot_goal.heading_target_deg = nil
        ai_pilot_goal.altitude_target_m = nil
        ai_pilot_goal.altitude_target_ref = nil
        ai_pilot_goal.speed_target_kmh = nil
        ai_pilot_goal.progress = "idle"
        ai_pilot_goal.mode_cycle_attempts = 0
        ai_pilot_goal.hold_cmd = nil
        ai_pilot_goal.toggling_reference = false
        ai_pilot_goal.hvrt_direction = nil
        ai_pilot_goal.hvrt_hold_cmd = nil
        ai_pilot_goal.hvrt_started_t = nil
        return
    end

    if rising then
        ai_pilot_takeover.handover_altitude_m = safe_call(LoGetAltitudeAboveSeaLevel)
        ai_pilot_takeover.stage = "toggling_reference"
        ai_pilot_takeover.t = t
        ai_pilot_takeover.correction_path = nil
    end

    if ai_pilot_takeover.stage == "toggling_reference"
        and t >= ai_pilot_takeover.t + AI_PILOT_REFERENCE_TOGGLE_DELAY_S then
        ai_pilot_tap30(WHEEL_CENTER_BUTTON)
        ai_pilot_last_press = "reference_toggle"
        ai_pilot_takeover.stage = "opening_menu"
        -- Matches the sequence actually flown in the rehearsal probe
        -- (centre at +0.5 s, menu-open at +1.0 s after takeover) rather
        -- than the same frame -- main-loop decision, not a plan or
        -- review requirement.
        ai_pilot_takeover.menu_open_at_t = t + ai_pilot_takeover.AI_PILOT_MENU_OPEN_DELAY_S
    end

    if ai_pilot_takeover.stage == "opening_menu"
        and t >= ai_pilot_takeover.menu_open_at_t then
        ai_pilot_tap30(WHEEL_MENU_BUTTON)
        ai_pilot_takeover.menu_open = true
        ai_pilot_takeover.menu_closed_since_t = nil
        ai_pilot_takeover.stage = "correcting_altitude"
        ai_pilot_takeover.awaiting_correction_decision = true
    end
end

-- Resolves everything that needs this tick's freshly-parsed overlay:
-- the keep-open check (independent of the takeover sequence, active
-- whenever we believe the menu is open), the one-shot correction
-- decision once the menu's first post-open read lands, the quick path's
-- two-pulse sub-sequence, and a hold's own convergence check -- run from
-- the 5 Hz export tick rather than every frame (perf fix, `plans/
-- flight-control/perf-batch-a.md`), since `list_indication` itself only
-- updates at that cadence. `raw` is the one `list_indication(HELPERAI_
-- DEVICE_ID)` dump this tick's export already read, shared with
-- `petrovich.push_indication`'s own consumer -- not a second device
-- read. **Device 6 is one call per 5 Hz tick now, shared by both
-- consumers; a future per-frame addition that needs its content must
-- feed off that same tick-local read, not reintroduce its own per-frame
-- `list_indication(6)` call.** No-op while unparked (fields already
-- cleared by `run_ai_pilot_wheel`'s own unpark branch) or before this
-- tick's dump exists. The four branches below (`ai_pilot_takeover.
-- awaiting_correction_decision`, `quick_read1`, `quick_read2`, an open
-- hold) are mutually exclusive by construction -- `elseif`, not
-- independent `if`s -- so a tick never both decides *and* reacts to the
-- decision it just made against a stale read.
local function update_ai_pilot_wheel_overlay(raw, t)
    if not ai_pilot_parked_active or raw == nil then
        return
    end

    local fields = parse_helperai_overlay_fields(raw)
    ai_pilot_mode_text = fields.mode_text
    ai_pilot_course_text = fields.course_text
    ai_pilot_alt_text = fields.alt_text
    ai_pilot_alt_add_text = fields.alt_add_text
    ai_pilot_speed_text = fields.speed_text

    local fields_all_nil = ai_pilot_mode_text == nil and ai_pilot_course_text == nil
        and ai_pilot_alt_text == nil and ai_pilot_alt_add_text == nil
        and ai_pilot_speed_text == nil

    if ai_pilot_takeover.menu_open then
        if fields_all_nil then
            if ai_pilot_takeover.menu_closed_since_t == nil then
                ai_pilot_takeover.menu_closed_since_t = t
            elseif t - ai_pilot_takeover.menu_closed_since_t > MODE_READ_SETTLE_S then
                ai_pilot_tap30(WHEEL_MENU_BUTTON)
                ai_pilot_takeover.menu_closed_since_t = nil
            end
        else
            ai_pilot_takeover.menu_closed_since_t = nil
        end
    end

    if ai_pilot_takeover.awaiting_correction_decision then
        if not fields_all_nil then
            ai_pilot_takeover.awaiting_correction_decision = false
            ai_pilot_decide_correction(t)
        end
    elseif ai_pilot_takeover.correction_substage == "quick_read1" then
        ai_pilot_takeover.correction_substage = nil
        if ai_pilot_alt_add_text == "R" then
            ai_pilot_takeover.correction_substage = "quick_read2"
            -- Second pulse, same `SHORT_PULSE_S` shape as the first.
            safe_call(function()
                GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 1)
            end)
            ai_wheel_pending_cmd = WHEEL_CENTER_BUTTON
            ai_wheel_pending_release_t = t + SHORT_PULSE_S
            ai_pilot_last_press = "correction_quick_pulse2"
        else
            -- Still B: the radar switch was refused (>= 700 m AGL, or
            -- any other reason) -- fall back to the two-phase hold.
            ai_pilot_takeover.correction_path = "hold"
            ai_pilot_begin_hold_phase(t, ai_pilot_parse_altitude_text(ai_pilot_alt_text))
        end
    elseif ai_pilot_takeover.correction_substage == "quick_read2" then
        -- Re-check tolerance rather than trust the second switch blindly
        -- (review: the plan is silent here, and the one measured sample
        -- of a correct second-toggle target does not establish the bug
        -- is absent on it -- the first toggle demonstrably has it, twice).
        -- Falls through to the same two-phase hold the first pulse's own
        -- refusal uses, so a bad target is never resolved as "none".
        ai_pilot_takeover.correction_substage = nil
        local held = ai_pilot_parse_altitude_text(ai_pilot_alt_text)
        if ai_pilot_correction_direction(held, ai_pilot_takeover.handover_altitude_m) == nil then
            ai_pilot_takeover.stage = nil
        else
            ai_pilot_takeover.correction_path = "hold"
            ai_pilot_begin_hold_phase(t, held)
        end
    elseif ai_pilot_takeover.correction_hold_cmd ~= nil then
        ai_pilot_check_hold_convergence(t)
    end

    -- Stage P2a/P2b's own tick, run against this same freshly-parsed
    -- read -- guarded on `not fields_all_nil` for the identical reason
    -- the correction-decision branch above is: a transiently-closed menu
    -- must not be read as "mode unknown, start cycling," which would
    -- spend a mode-cycle attempt on a stale tick rather than a real mode
    -- change. Independent of the takeover branches above -- body-layer's
    -- own `decide_ai_pilot_wheel` never promotes a goal while `ai_pilot_
    -- takeover.stage` would be non-`nil` on the body-layer side, so a
    -- goal and an active takeover correction do not fight for the same
    -- ticks in correct operation, but this function does not assume
    -- that itself (see the goal pending-release pair's own comment).
    if not fields_all_nil then
        ai_pilot_goal_tick(t)
    end
    ai_pilot_goal_tick_hvrt(t)
end

-- Stage P2's own inbound op (`plans/flight-control/plan.md`, "Stage P2
-- ready to build", "The goal channel -- wire shape") -- same uniform
-- `(data, t)` shape `commands.lua`'s dispatch table expects, mirroring
-- `handle_sight_target_command`'s own validate-then-assign pattern.
-- **A different `param` than the one currently active releases any open
-- hold immediately** (Co-moving Fields: "any open press released
-- immediately -- same rule as the existing mode-change row, generalised
-- from 'mode changes' to 'active param changes'") -- checked before the
-- new fields are assigned, so the comparison is always against the
-- *previous* `.param`. `hvrt_direction` travels in the same message
-- (plan's own note) and needs no such reconciliation: Stage P2b's own
-- tick already opens/redirects/releases purely from reading the field's
-- current value each tick, never from an edge detected here.
local function handle_ai_pilot_goal_command(data, t)
    local goal_seq = extract_json_number_field(data, "goal_seq")
    if goal_seq == nil then
        debug_log("ignoring malformed ai_pilot_goal command (missing goal_seq)")
        return
    end
    local param = extract_json_string_field(data, "param")
    local heading_target_deg = extract_json_number_field(data, "heading_target_deg")
    local altitude_target_m = extract_json_number_field(data, "altitude_target_m")
    local altitude_target_ref = extract_json_string_field(data, "altitude_target_ref")
    local speed_target_kmh = extract_json_number_field(data, "speed_target_kmh")
    local hvrt_direction = extract_json_string_field(data, "hvrt_direction")

    if param ~= ai_pilot_goal.param then
        ai_pilot_goal_release_hold()
        ai_pilot_goal.mode_cycle_attempts = 0
        ai_pilot_goal.toggling_reference = false
    end

    ai_pilot_goal.goal_seq = goal_seq
    ai_pilot_goal.param = param
    ai_pilot_goal.heading_target_deg = heading_target_deg
    ai_pilot_goal.altitude_target_m = altitude_target_m
    ai_pilot_goal.altitude_target_ref = altitude_target_ref
    ai_pilot_goal.speed_target_kmh = speed_target_kmh
    ai_pilot_goal.hvrt_direction = hvrt_direction
    if param ~= nil then
        ai_pilot_goal.progress = "pressing"
    elseif hvrt_direction == nil then
        ai_pilot_goal.progress = "idle"
    end
end

-- Sends `run_ai_pilot_wheel`'s own status at 5 Hz, same cadence as the
-- telemetry line. Wire key `"apw_parked_active"` doubles as the
-- collector's route key, same pattern as `"servo_mode"`/`"net1"`/
-- `"ptt"`. `apw_arg852`/`apw_arg952`/`apw_takeover_stage`/`apw_
-- correction_path` are additive (plan, "Revised 2026-11-16", point
-- 7/"The P1 telemetry mystery") -- the raw park args and the correction
-- path are diagnostic, so a recurrence of either open question is
-- directly visible on the wire rather than re-inferred from a probe.
-- `apw_goal_progress`/`apw_goal_seq` are Stage P2's own additions --
-- `Export.lua`'s own report of where the goal-channel loop is, and
-- which goal message it is reporting against.
local function push_ai_pilot_wheel_state(t)
    if client == nil then
        return
    end
    local function text_or_null(value)
        if value == nil then
            return "null"
        end
        return '"' .. json_escape_string(value) .. '"'
    end
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"apw_parked_active":' .. tostring(ai_pilot_parked_active)
        .. ',"apw_mode_text":' .. text_or_null(ai_pilot_mode_text)
        .. ',"apw_course_text":' .. text_or_null(ai_pilot_course_text)
        .. ',"apw_alt_text":' .. text_or_null(ai_pilot_alt_text)
        .. ',"apw_alt_add_text":' .. text_or_null(ai_pilot_alt_add_text)
        .. ',"apw_speed_text":' .. text_or_null(ai_pilot_speed_text)
        .. ',"apw_last_press":' .. text_or_null(ai_pilot_last_press)
        .. ',"apw_arg852":' .. fmt_num_or_null(ai_pilot_takeover.raw_arg852)
        .. ',"apw_arg952":' .. fmt_num_or_null(ai_pilot_takeover.raw_arg952)
        .. ',"apw_takeover_stage":' .. text_or_null(ai_pilot_takeover.stage)
        .. ',"apw_correction_path":' .. text_or_null(ai_pilot_takeover.correction_path)
        .. ',"apw_goal_progress":' .. text_or_null(ai_pilot_goal.progress)
        .. ',"apw_goal_seq":' .. fmt_num_or_null(ai_pilot_goal.goal_seq) .. '}\n')
    if not ok then
        debug_log("ai-pilot-wheel send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- `AC-B13`: release any open AI-wheel press, then clear the pending-press
-- fields and the takeover state -- mirrors `petrovich.lua`'s own
-- `pending_release_t = nil` reset shape, which this module never had
-- (BL-16 Batch A's one-shot nudge never needed a stop-hook reset; the
-- takeover revision widened the window to the 60 s correction-hold
-- ceiling and `LuaExportStop` was never updated for it -- the AC-B13
-- finding). Deliberately does **not** touch `ai_pilot_parked_active` or
-- the overlay text fields (`ai_pilot_mode_text`/`_course_text`/
-- `_alt_text`/`_alt_add_text`/`_speed_text`/`_last_press`) -- that is a
-- second, adjacent gap the plan found but explicitly scoped out, filed
-- separately as `BL-B117`.
local function on_stop()
    if ai_wheel_pending_cmd ~= nil then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_pending_cmd, 0)
        end)
    end
    ai_wheel_pending_release_t = nil
    ai_wheel_pending_cmd = nil
    ai_pilot_takeover.stage = nil
    ai_pilot_takeover.t = nil
    ai_pilot_takeover.handover_altitude_m = nil
    ai_pilot_takeover.menu_open = false
    ai_pilot_takeover.menu_open_at_t = nil
    ai_pilot_takeover.menu_closed_since_t = nil
    ai_pilot_takeover.awaiting_correction_decision = false
    ai_pilot_takeover.correction_path = nil
    ai_pilot_takeover.correction_substage = nil
    ai_pilot_takeover.correction_phase = nil
    ai_pilot_takeover.correction_hold_cmd = nil
    ai_pilot_takeover.raw_arg852 = nil
    ai_pilot_takeover.raw_arg952 = nil
    -- Stage P2's own release/reset -- the same AC-B13-class gap (a
    -- long-lived open press with no `LuaExportStop` reset) would exist
    -- here otherwise, so it is closed proactively rather than waiting
    -- for a second incident to find it.
    if ai_wheel_goal_pending_cmd ~= nil then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_goal_pending_cmd, 0)
        end)
    end
    if ai_pilot_goal.hvrt_hold_cmd ~= nil then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
        end)
    end
    ai_wheel_goal_pending_release_t = nil
    ai_wheel_goal_pending_cmd = nil
    ai_pilot_goal.param = nil
    ai_pilot_goal.heading_target_deg = nil
    ai_pilot_goal.altitude_target_m = nil
    ai_pilot_goal.altitude_target_ref = nil
    ai_pilot_goal.speed_target_kmh = nil
    ai_pilot_goal.progress = "idle"
    ai_pilot_goal.mode_cycle_attempts = 0
    ai_pilot_goal.hold_cmd = nil
    ai_pilot_goal.toggling_reference = false
    ai_pilot_goal.hvrt_direction = nil
    ai_pilot_goal.hvrt_hold_cmd = nil
    ai_pilot_goal.hvrt_started_t = nil
end

M.run_ai_pilot_wheel = run_ai_pilot_wheel
M.update_ai_pilot_wheel_overlay = update_ai_pilot_wheel_overlay
M.push_ai_pilot_wheel_state = push_ai_pilot_wheel_state
M.handle_ai_pilot_goal_command = handle_ai_pilot_goal_command
M.on_stop = on_stop

return M
