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

-- Which seat the player occupies, from the camera (fix/ai-wheel-pilot-
-- seat-gate, `docs/acceptance/2026-11-16-ai-wheel-pilot-seat-feedback.md`).
-- Arg 852 is the **operator's** stick stow (`mainpanel_init.lua`
-- `StickStowingOp`): it reads stowed whenever no human flies from the
-- operator seat -- ED's AI flying it, *or* the player sitting in the
-- pilot seat. User: "AI never flies when player is in pilot seat", so
-- "AI flying" = 852 stowed AND the player is in the operator seat.
-- `Export.lua` cannot observe the seat-change key bindings, only their
-- effect: the camera moves to that seat's eye point. `Mods/aircraft/
-- Mi-24P/Views.lua`: pilot eye x = 3.15 m, operator x = 4.65 m (model
-- axes, forward), head travel x -0.1..+0.5 m -- pilot 3.05..3.65,
-- operator 4.55..5.15, so 4.1 m splits them with >= 0.45 m margin. A
-- camera outside the cockpit envelope (external, map, possibly the
-- 9K113 sight view) yields no reading and the last known seat holds.
-- **Unverified live** (projection origin, sight-view camera):
-- `apw_seat`/`apw_cam_fwd_m` on the status push exist to settle it.
local SEAT_BOUNDARY_FWD_M = 4.1
local SEAT_CAMERA_MIN_FWD_M = 2.0
local SEAT_CAMERA_MAX_FWD_M = 7.0
local SEAT_CAMERA_MAX_OFFAXIS_M = 1.5

-- "Good enough" tolerance for the **takeover correction** loop only: how
-- close the AI's held altitude (`alt_text`) must read to the *flown*
-- target (the live altitude in phase 1, the handover snapshot in phase
-- 2) before that correction treats itself as resolved. Renamed from
-- `AI_PILOT_NUDGE_EPSILON_M` (same value) now that the same number
-- governs three decisions instead of one (the pre-correction "is
-- anything wrong" check, and both hold phases' own release point).
-- Mirrors body-layer's `AI_PILOT_ALTITUDE_TOLERANCE_M` tunable
-- (`belief/ai_pilot_wheel.py`, default 20) -- duplicated here, not read
-- over the wire, because Stage P1 sends no goal message yet (the
-- Architecture decision's per-frame press timing stays entirely in this
-- file until Stage P2 wires a goal channel through); revisit once that
-- channel exists so there is one source of truth for this number.
--
-- **No longer the altitude *goal*'s own stop condition** (fix,
-- 2026-11-20, `docs/acceptance/2026-11-20-sortie-feedback.md`, "Desired
-- value must be exact; flying may be imprecise"): a voice-commanded
-- "altitude 100 radar" left the overlay's *set* value at 116 (a 16 m
-- error, inside this 20 m band, so `ai_pilot_goal_tick_altitude` below
-- stopped pressing with the overlay still wrong). The user's rule --
-- "the value *set* as desired must still be what player commanded...
-- flying is allowed to deviate from it a bit" -- means this band may
-- still gate whether *flown* altitude counts as having reached a
-- target, never whether the *overlay's own displayed number* matches
-- what was asked for. `ai_pilot_correction_direction` below now takes an
-- explicit tolerance argument; every takeover-correction call site below
-- still passes none (so it defaults to this constant), and only the
-- goal tick passes `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M` instead.
local AI_PILOT_ALT_TOLERANCE_M = 20.0

-- The altitude **goal**'s own stop condition (fix, 2026-11-20, same
-- sortie feedback as above): how close `alt_text` must read to the
-- voice-commanded target before `ai_pilot_goal_tick_altitude` stops
-- pressing. Every overlay altitude reading observed so far (research
-- note `2026-11-14-mi24p-ai-pilot-wheel-layout.md` section 3: `196 R`,
-- `948 B`; `2026-10-31-mi24p-park-controls-ai-pilot.md`'s `alt_text`
-- holder) has been a bare integer with no decimal point, so 0.5 is
-- "exactly equal to the nearest whole metre" rather than a real
-- tolerance window -- **not independently verified live** (no screenshot
-- has shown a fractional reading, but none was taken specifically
-- looking for one). The per-tick redirect in `ai_pilot_goal_tick_
-- altitude` already reverses direction the instant the needed direction
-- flips (see that function's own comment), so an overshoot past the
-- exact target on one hold-and-poll tick self-corrects on the next
-- rather than needing a second, finer press type -- FLT/HVR altitude has
-- no short-tap option to fall back to (layout research note section 5:
-- the outer up/down button's short-press behaviour in FLT/HVR is
-- undocumented, only its long-hold ramp is), so a tight hold-and-poll
-- band is the only lever available.
local AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M = 0.5

-- ``BL-B139`` (`docs/acceptance/2026-11-27-mode2-recovery-feedback.md`):
-- ED's AI pilot only reacts to a *change* of its displayed set altitude/
-- speed -- a recovery whose target already equals what the overlay shows
-- would otherwise settle with zero presses and never wake it up. While a
-- goal message carries `.wake` (set only for a recovery, body-layer's
-- own `ParkedFlightState.align_phase == "recovering"`), the altitude/
-- speed goal ticks below force one step away from the target before
-- letting the ordinary hold-and-poll/tap loop converge it right back --
-- "step down a bit, then back," never more than that. This is the
-- longest either direction is forced before the ticks below try the
-- opposite one (altitude's own continuous hold only -- the speed tap is
-- always exactly one tap, bounded by construction, see `ai_pilot_goal_
-- tick_speed`'s own comment): long enough that a few ticks' worth of
-- climb/descend rate clears `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M`, short
-- enough that a genuinely stuck wheel (the lower/upper stop) is retried
-- the other way within a couple of seconds rather than holding one
-- button open indefinitely.
local AI_PILOT_WAKE_KICK_TIMEOUT_S = 1.5

-- Delay from the park-rising edge to the blind reference-toggle press
-- (pilot, verbatim: "I'd put a half second delay there").
local AI_PILOT_REFERENCE_TOGGLE_DELAY_S = 0.5

-- Settle delay after the camera crosses *into* the operator seat, before
-- arg 852 is trusted (flight 8, 2026-11-18, `aircraft-layer/research/
-- 2026-11-18-bl16-m0-flight-axes-findings.md` "Flight 8"): the camera
-- reached the operator seat at 17.301 s while 852 still read 0.963
-- (stowed, from the pilot seat), then animated down over ~0.3 s
-- (0.930, 0.893, 0.853, ... 0.624 at +94 ms) -- a false park-rising edge
-- for a few frames if read immediately. User, verbatim: "allow that
-- initial small delay so that the control either unparks or remains
-- parked, then read state and that determines whether AI has controls".
-- 0.5 s covers the ~0.3 s animation with margin, same reasoning as
-- `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` above. Only the pilot-to-operator
-- direction needs this: the reverse (operator-to-pilot) forces the park
-- arg to `nil` unconditionally (`run_ai_pilot_wheel`'s seat gate), which
-- has no transient to absorb, and delaying *that* unpark would hold a
-- stale "parked" belief while the player already has the stick back --
-- see `run_ai_pilot_wheel`'s own comment at the seat gate. This is a
-- behaviour-affecting constant with no `tuning.py` equivalent in this
-- subproject (root `CLAUDE.md`, "Behaviour-affecting constants are
-- tunable") -- it would want that mechanism if aircraft-layer had one.
local AI_PILOT_SEAT_CHANGE_SETTLE_S = 0.5

-- How long the overlay must read every field `nil` before the menu is
-- believed closed and re-opened -- the toggle is a single press that
-- closes an open menu just as readily as it opens a closed one, so
-- reacting to one stale-looking tick would flap it shut again. ~1 s AI
-- lag is the user's own recon estimate (research note section 7);
-- measured live, a hand-closed menu reads closed for 3 frames and reads
-- open again ~17 ms after the re-toggle, so this is generous margin, not
-- a tight bound.
local MODE_READ_SETTLE_S = 1.0

-- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 4's
-- "align" row, U6 answered 2026-11-20: *"overlay updates in a few
-- frames. Anyhow, take whatever value the overlay has."*) -- the delay
-- between the align press and reading the overlay's own course back
-- into `desired.heading_deg`, so an unpark shortly after an align
-- already carries the aligned heading (Stage 3's own unpark-carry
-- reads `desired` verbatim; nothing else updates it for this press).
-- The user's own answer names "a few frames", not `MODE_READ_SETTLE_S`
-- (that 1.0 s figure is the *menu-closed* settle, a different read);
-- this project has no per-frame clock available outside DCS itself, so
-- a short sim-time margin stands in -- 0.1 s is 2-6 frames at this
-- aircraft's usual 20-60 fps range, comfortably inside "a few".
local ALIGN_READ_DELAY_S = 0.1

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

-- How close a spoken heading goal must read before the hold releases it
-- -- the heading goal's own stop condition, the only user of this
-- constant (unlike altitude, heading has no separate takeover-correction
-- use to keep a wider band for). **Tightened from 5.0 to 0.5, fix
-- 2026-11-20** (`docs/acceptance/2026-11-20-sortie-feedback.md`, "Desired
-- value must be exact; flying may be imprecise"): the same "good enough"
-- reasoning that left altitude's overlay 16 m off target applied here
-- too (a spoken heading landing anywhere within 5 deg of the target
-- would stop being corrected, overlay still wrong) -- 0.5 is "exactly
-- equal to the nearest whole degree," the same integer-display
-- assumption `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M` makes and with the
-- same caveat: every `course_text` reading seen so far (`71` in the
-- layout research note) has been a bare integer, but no screenshot was
-- taken specifically looking for a fractional one. **No longer mirrors**
-- body-layer's `AI_PILOT_HEADING_TOLERANCE_DEG` tunable (`belief/
-- ai_pilot_wheel.py`) -- that tunable is declared but has no code
-- consumer of its own (confirmed by grep: it is read nowhere in
-- body-layer), so nothing on that side needed to change, but its
-- docstring is updated alongside this fix to stop claiming a mirror this
-- precise. `ai_pilot_goal_heading_direction` below's own redirect-on-
-- overshoot behaviour (see that function's comment) is what keeps a
-- tight band from oscillating forever, the same reasoning the altitude
-- goal's own comment above gives.
local AI_PILOT_HEADING_TOLERANCE_DEG = 0.5

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

-- How long a goal/HVRT mode-cycle stays reported `"mode_blocked"` before
-- the attempt counter resets and pressing resumes on its own -- review
-- fix (BL-16 Stage P2): the bound above existed to stop pressing
-- forever, but nothing previously reset it short of a *different*
-- `param` arriving (the multi-goal rotation incidentally did this by
-- switching `active_param` back and forth) or the mode becoming ready on
-- its own -- so a single outstanding goal stuck on an unreachable mode
-- was retried never, after one spoken "unable, not ready," contradicting
-- the plan's own "retried next poll"/"goal never dropped" language. A
-- few seconds is long enough that a stuck wheel does not spam presses or
-- speech, short enough that a transient miss (the one-hop case the bound
-- itself exists for) recovers within one or two cooldowns rather than
-- needing a second spoken command to unstick it.
local MODE_BLOCKED_RETRY_S = 3.0

-- Safety ceiling on an open HVRT translate press if the spoken "Hold" is
-- lost (a network drop between audio-adapter and body-layer, a missed
-- recognition) -- the normal stop is always the player's own "Hold",
-- never this. Architect default, **not** user-specified (plan's own
-- flag, Q-P2) -- revisit if a sortie shows it firing in ordinary use.
local HVRT_TRANSLATE_MAX_HOLD_S = 15.0

-- Stage P3+P4's own CBTM one-shot channel (`plans/flight-control/
-- plan.md`, "Revised 2026-11-18 -- Stages P3+P4 ready to build", "The
-- CBTM one-shot wire channel"). `LONG_PRESS_HOLD_S` is the duration a
-- press is held open to register as the wheel's own "long press" (the
-- outer-ring option -- `AI_WHEEL_UP`/`_DOWN`/`_LEFT`/`_RIGHT`'s own
-- comment at the top of this file), reused for `align_for_launch`'s
-- long-up and every break's long-left/right -- a discrete action, never
-- an open hold (plan, "a discrete action, not an open hold"). `BREAK_
-- AWAY_GAP_S` is the gap between `break_away`'s two long-left presses
-- (user, verbatim, unchanged from the original plan).
local LONG_PRESS_HOLD_S = 0.7
local BREAK_AWAY_GAP_S = 2.0

-- True only while ED's AI is believed to be flying: 852 stowed AND the
-- player in the operator seat (see `SEAT_BOUNDARY_FWD_M`). Wire name
-- `apw_parked_active` kept for compatibility. Every per-tick press loop
-- in this file -- the takeover correction, the P2a goal dispatcher, and
-- P2b's HVRT translate -- reads only this flag (never arg 852 alone) to
-- decide whether to press anything at all, so the seat gate covers all
-- three mechanisms by construction, not by each one re-checking the
-- camera itself.
local ai_pilot_parked_active = false
-- `"pilot"`/`"operator"`/`nil` (not known yet) -- the last seat the
-- camera placed the player in; `ai_pilot_cam_fwd_m` is the raw forward
-- offset behind it, diagnostic only (status push).
local ai_pilot_player_seat = nil
local ai_pilot_cam_fwd_m = nil
-- Model time the pilot-to-operator settle window (`AI_PILOT_SEAT_CHANGE_
-- SETTLE_S` above) ends, or `nil` when no settle is in progress -- set
-- by `ai_pilot_update_seat` the frame the camera crosses into the
-- operator seat, consumed by `run_ai_pilot_wheel`'s own seat gate.
local ai_pilot_seat_settle_until_t = nil

-- BL-16 sortie 2026-11-20, `docs/acceptance/2026-11-20-sortie-feedback.
-- md` -- the body-layer process-start reset's own generation counter,
-- same shape as `flight_control.lua`'s own `fc_reset_epoch`. Only ever
-- written by `reset()` below, echoed on every status line.
local ai_pilot_reset_epoch = nil

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

-- Stage P3+P4's own pending-release pair -- deliberately a **third**
-- slot, separate from both pairs above, same reasoning as the goal
-- channel's own comment: the CBTM channel's own timed press (`align_
-- for_launch`/`break_*`) never needs to hold open at the same time as
-- a takeover correction or a goal/HVRT hold in correct operation (Lua's
-- own mutual-exclusion guard below pauses the goal/HVRT ticks whenever
-- a CBTM action is outstanding), but a third slot means that invariant
-- is never load-bearing for correctness, only for which press each
-- release call releases.
local ai_wheel_cbtm_pending_release_t = nil
local ai_wheel_cbtm_pending_cmd = nil

-- BL-16 Stage 3 -- the align press's own deferred overlay-course read
-- (`ALIGN_READ_DELAY_S`'s own deadline, `nil` when nothing is pending).
local ai_wheel_align_read_at_t = nil

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
-- reached. `.mode_blocked_since_t`: the model time the bound was first
-- exhausted, `nil` outside a blocked episode -- `MODE_BLOCKED_RETRY_S`
-- after this, the attempt counter resets and pressing resumes (review
-- fix: `"mode_blocked"` must retry, not stall forever). `.hold_cmd`: the
-- heading/altitude direction (`AI_WHEEL_UP`/`_DOWN`/`_LEFT`/`_RIGHT`)
-- currently held open by the goal loop, or `nil` -- distinct from
-- `ai_pilot_takeover.correction_hold_cmd`, same reason the two
-- pending-release pairs are kept apart. `.toggling_reference`: true
-- while an altitude goal's own reference-change pulse is in flight, so
-- the tick does not re-issue a second pulse on top of one already
-- running. `.hvrt_direction`: mirrors body-layer's own field,
-- `nil`/`"left"`/`"right"`/`"forward"`/`"back"`. `.hvrt_hold_cmd`/
-- `.hvrt_started_t`: the HVRT translate press currently held open (if
-- any) and when it opened, for the safety timeout. `.hvrt_mode_cycle_
-- attempts`/`.hvrt_mode_blocked_since_t`: the HVRT channel's own copy of
-- the two fields above -- review fix: `ai_pilot_goal_tick_hvrt`'s own
-- mode-cycle (into `HVRT`) previously had no bound at all, so it is kept
-- separate rather than sharing the FLT/HVR pair, since both ticks run
-- every overlay tick and must count their own attempts independently.
--
-- ``BL-B139``'s own wake-kick fields, same table rather than a third
-- one (they only ever matter alongside `.param`/`.goal_seq`): `.wake`
-- mirrors body-layer's own flag, sticky like `.param` (not a one-shot).
-- `.wake_done_seq`: the `.goal_seq` the kick has already run (or been
-- judged unnecessary) for -- `nil` until the first tick of a fresh
-- `.goal_seq` decides either way. `.wake_kick_dir`: the direction
-- currently being forced away from the target (`AI_WHEEL_DOWN`/`_UP`),
-- `nil` while not kicking. `.wake_kick_started_t`: the model time the
-- *current* forced direction began, for `AI_PILOT_WAKE_KICK_TIMEOUT_S`.
-- `.wake_kick_tried_up`: whether the down-then-up fallback has already
-- spent its one retry this `.goal_seq`, so a wheel stuck at both ends
-- gives up rather than flip-flopping forever.
local ai_pilot_goal = {
    param = nil,
    heading_target_deg = nil,
    altitude_target_m = nil,
    altitude_target_ref = nil,
    speed_target_kmh = nil,
    goal_seq = 0,
    progress = "idle",
    mode_cycle_attempts = 0,
    mode_blocked_since_t = nil,
    hold_cmd = nil,
    toggling_reference = false,
    hvrt_mode_cycle_attempts = 0,
    hvrt_mode_blocked_since_t = nil,
    hvrt_direction = nil,
    hvrt_hold_cmd = nil,
    hvrt_started_t = nil,
    wake = false,
    wake_done_seq = nil,
    wake_kick_dir = nil,
    wake_kick_started_t = nil,
    wake_kick_tried_up = false,
}

-- Stage P3+P4's own co-moving state -- the CBTM one-shot channel
-- (align/align-for-launch/break/break-away), kept in its own table for
-- the same Lua-5.1-local-ceiling reason `ai_pilot_takeover`/`ai_pilot_
-- goal` are. `.action`: `nil` (idle) or one of the five `cbtm_action`
-- wire values. `.seq`: the last `cbtm_seq` this channel has started
-- acting on -- compared against an incoming message's own `cbtm_seq`
-- the same "act once per distinct seq" way `hvrt_step` already is.
-- `.status`: `"idle"`/`"running"`/`"done"`, echoed on the status push
-- (`apw_cbtm_status`). `.mode_cycle_attempts`/`.mode_blocked_since_t`:
-- this channel's own copy of the goal channel's bounded-retry pair,
-- kept separate for the same reason the HVRT pair is. `.presses_done`:
-- how many timed presses this action has opened so far -- `1` for
-- `align_for_launch`/`break_left`/`break_right`, `2` for `break_away`
-- (the second press, after the gap). `.gap_until_t`: the model time
-- `break_away`'s second press may open, `nil` outside that gap.
local ai_pilot_cbtm = {
    action = nil,
    seq = 0,
    status = "idle",
    mode_cycle_attempts = 0,
    mode_blocked_since_t = nil,
    presses_done = 0,
    gap_until_t = nil,
}

-- The physical button each timed-press CBTM action holds open -- `"align"`
-- is a short tap (the wheel's own inner-ring option), handled separately
-- in `ai_pilot_cbtm_tick` below, not in this table.
local AI_PILOT_CBTM_PRESS_CMD = {
    align_for_launch = AI_WHEEL_UP,
    break_left = AI_WHEEL_LEFT,
    break_right = AI_WHEEL_RIGHT,
    break_away = AI_WHEEL_LEFT,
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
-- lower it; below means press UP. `tolerance_m` defaults to
-- `AI_PILOT_ALT_TOLERANCE_M` (every takeover-correction call site below
-- passes none) -- the altitude **goal** tick is the one caller that
-- passes its own, much tighter `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M`
-- instead (fix, 2026-11-20: see that constant's own comment for why the
-- two must not share one band).
local function ai_pilot_correction_direction(held_m, target_m, tolerance_m)
    if held_m == nil or target_m == nil then
        return nil
    end
    local tol = tolerance_m
    if tol == nil then
        tol = AI_PILOT_ALT_TOLERANCE_M
    end
    if math.abs(held_m - target_m) <= tol then
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

-- Pure decision: which seat the camera is in. `cam_p`/`own_p` are world
-- points ({x, y, z}; DCS x north, y up, z east), `heading_rad` true
-- heading, `pitch_rad` nose-up pitch. Projects the camera offset onto
-- the airframe's forward axis (bank does not move that axis, so it is
-- not needed). Returns `(seat, fwd_m)` -- `seat` is `nil` when any input
-- is missing or the camera is outside the cockpit envelope.
local function ai_pilot_seat_from_camera(cam_p, own_p, heading_rad, pitch_rad)
    if type(cam_p) ~= "table" or type(own_p) ~= "table" or type(heading_rad) ~= "number" then
        return nil, nil
    end
    if type(cam_p.x) ~= "number" or type(cam_p.y) ~= "number" or type(cam_p.z) ~= "number"
        or type(own_p.x) ~= "number" or type(own_p.y) ~= "number" or type(own_p.z) ~= "number" then
        return nil, nil
    end
    if type(pitch_rad) ~= "number" then
        pitch_rad = 0.0
    end
    local dx, dy, dz = cam_p.x - own_p.x, cam_p.y - own_p.y, cam_p.z - own_p.z
    local cp = math.cos(pitch_rad)
    local fwd = dx * cp * math.cos(heading_rad) + dy * math.sin(pitch_rad) + dz * cp * math.sin(heading_rad)
    local offaxis_sq = dx * dx + dy * dy + dz * dz - fwd * fwd
    if fwd < SEAT_CAMERA_MIN_FWD_M or fwd > SEAT_CAMERA_MAX_FWD_M
        or offaxis_sq > SEAT_CAMERA_MAX_OFFAXIS_M * SEAT_CAMERA_MAX_OFFAXIS_M then
        return nil, fwd
    end
    if fwd >= SEAT_BOUNDARY_FWD_M then
        return "operator", fwd
    end
    return "pilot", fwd
end

-- Reads camera + ownship and refreshes `ai_pilot_player_seat` (kept
-- when this frame gives no reading). Every frame, so a seat switch is
-- seen before arg 852's stow animation can produce a false edge. Also
-- arms the settle window (`AI_PILOT_SEAT_CHANGE_SETTLE_S`) the frame the
-- seat crosses from a known, different seat *into* "operator" -- the
-- one direction arg 852 can transiently still read stowed (flight 8
-- finding, see the constant's own comment); a first-ever reading
-- (`ai_pilot_player_seat` still `nil`) is not a switch and arms nothing.
local function ai_pilot_update_seat(t)
    local cam = safe_call(LoGetCameraPosition)
    local self_data = safe_call(LoGetSelfData)
    local cam_p = type(cam) == "table" and cam.p or nil
    local own_p = nil
    local heading = nil
    if type(self_data) == "table" then
        local pos = self_data.Position
        own_p = type(pos) == "table" and (pos.p or pos) or nil
        heading = self_data.Heading
    end
    local pitch = safe_call(LoGetADIPitchBankYaw)
    local seat, fwd = ai_pilot_seat_from_camera(cam_p, own_p, heading, pitch)
    ai_pilot_cam_fwd_m = fwd
    if seat ~= nil then
        if seat == "operator" and ai_pilot_player_seat ~= nil
            and ai_pilot_player_seat ~= "operator" then
            ai_pilot_seat_settle_until_t = t + AI_PILOT_SEAT_CHANGE_SETTLE_S
        end
        ai_pilot_player_seat = seat
    end
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

-- ``BL-B139``'s own altitude kick decision -- a continuous hold, so
-- the same forced direction is simply re-returned every tick the kick
-- is open (the caller's own `hold_cmd ~= dir` check keeps it open
-- without flicker); `AI_PILOT_WAKE_KICK_TIMEOUT_S` of holding one way
-- is what "steps the value" far enough to clear `AI_PILOT_GOAL_ALT_
-- EXACT_TOLERANCE_M`. Returns the direction to hold *instead of*
-- `ordinary_dir` this tick, or `nil` to use `ordinary_dir` unchanged --
-- `nil` covers both "no wake requested/already done" and "the kick (or
-- a real mismatch) has just been confirmed, hand off to the ordinary
-- correction converging back to the exact target."
local function ai_pilot_wake_kick_direction_hold(t, ordinary_dir)
    if not ai_pilot_goal.wake or ai_pilot_goal.wake_done_seq == ai_pilot_goal.goal_seq then
        return nil
    end
    if ordinary_dir ~= nil then
        -- Off target already -- either the kick just took effect, or
        -- this was never a "already at target" case to begin with.
        -- Either way, wake is achieved and the ordinary hold-and-poll
        -- loop below takes it the rest of the way.
        ai_pilot_goal.wake_done_seq = ai_pilot_goal.goal_seq
        ai_pilot_goal.wake_kick_dir = nil
        ai_pilot_goal.wake_kick_tried_up = false
        return nil
    end
    if ai_pilot_goal.wake_kick_dir == nil then
        ai_pilot_goal.wake_kick_dir = AI_WHEEL_DOWN
        ai_pilot_goal.wake_kick_started_t = t
    elseif t - ai_pilot_goal.wake_kick_started_t >= AI_PILOT_WAKE_KICK_TIMEOUT_S then
        if not ai_pilot_goal.wake_kick_tried_up then
            -- Holding down for the full timeout produced no detectable
            -- change -- the wheel's own lower stop. Try up instead.
            ai_pilot_goal.wake_kick_dir = AI_WHEEL_UP
            ai_pilot_goal.wake_kick_tried_up = true
            ai_pilot_goal.wake_kick_started_t = t
        else
            -- Both directions tried, neither moved the display -- give
            -- up rather than hold a button open forever (same "never
            -- stall forever" posture as `MODE_BLOCKED_RETRY_S`).
            ai_pilot_goal.wake_done_seq = ai_pilot_goal.goal_seq
            ai_pilot_goal.wake_kick_dir = nil
            ai_pilot_goal.wake_kick_tried_up = false
            return nil
        end
    end
    return ai_pilot_goal.wake_kick_dir
end

-- ``BL-B139``'s own speed kick decision -- the speed goal tick is a
-- single tap per tick, never a hold (see `ai_pilot_goal_tick_speed`'s
-- own comment), so a kick must tap **exactly once** per forced
-- direction and then wait for the next readback rather than re-tapping
-- every tick, which would walk the ladder more steps than "one press
-- down, then back" asks for. Returns a direction to tap *this* tick,
-- the string `"wait"` to take no action while a just-issued tap's
-- readback is still pending, or `nil` to use `ordinary_dir` unchanged.
local function ai_pilot_wake_kick_direction_tap(t, ordinary_dir)
    if not ai_pilot_goal.wake or ai_pilot_goal.wake_done_seq == ai_pilot_goal.goal_seq then
        return nil
    end
    if ordinary_dir ~= nil then
        ai_pilot_goal.wake_done_seq = ai_pilot_goal.goal_seq
        ai_pilot_goal.wake_kick_dir = nil
        ai_pilot_goal.wake_kick_tried_up = false
        return nil
    end
    if ai_pilot_goal.wake_kick_dir == nil then
        ai_pilot_goal.wake_kick_dir = AI_WHEEL_DOWN
        ai_pilot_goal.wake_kick_started_t = t
        return AI_WHEEL_DOWN
    end
    if t - ai_pilot_goal.wake_kick_started_t >= AI_PILOT_WAKE_KICK_TIMEOUT_S then
        if not ai_pilot_goal.wake_kick_tried_up then
            -- The down tap produced no detectable step -- the ladder's
            -- own lower rung. Try one tap up instead.
            ai_pilot_goal.wake_kick_dir = AI_WHEEL_UP
            ai_pilot_goal.wake_kick_tried_up = true
            ai_pilot_goal.wake_kick_started_t = t
            return AI_WHEEL_UP
        end
        -- Neither direction produced a detectable step -- give up.
        ai_pilot_goal.wake_done_seq = ai_pilot_goal.goal_seq
        ai_pilot_goal.wake_kick_dir = nil
        ai_pilot_goal.wake_kick_tried_up = false
        return nil
    end
    return "wait"
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
    local dir = ai_pilot_correction_direction(
        held_m, ai_pilot_goal.altitude_target_m, AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M)
    -- ``BL-B139``: while recovering, a value that already matches the
    -- target needs a forced kick instead of settling silently -- see
    -- `ai_pilot_wake_kick_direction_hold`'s own comment. `nil` back
    -- means "use `dir` as computed above" (no wake requested, already
    -- done, or the kick/mismatch just got picked up this tick).
    local kick_dir = ai_pilot_wake_kick_direction_hold(t, dir)
    if kick_dir ~= nil then
        dir = kick_dir
    end
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
    -- ``BL-B139``: same reasoning as the altitude tick above, but a
    -- single discrete tap per forced direction (`ai_pilot_wake_kick_
    -- direction_tap`'s own comment) -- `"wait"` means a just-issued
    -- tap's readback has not arrived yet, so no tap this tick, but
    -- still "pressing," not settled.
    local kick_dir = ai_pilot_wake_kick_direction_tap(t, dir)
    if kick_dir == "wait" then
        ai_pilot_goal.progress = "pressing"
        return
    end
    if kick_dir ~= nil then
        dir = kick_dir
    end
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
-- ATTEMPTS`, reported `"mode_blocked"` and retried after `MODE_BLOCKED_
-- RETRY_S`, never dropped and never stalled forever -- review fix, see
-- `MODE_BLOCKED_RETRY_S`'s own comment), then dispatches to the one tick
-- function `.param` needs. No-op (idle) while nothing is outstanding,
-- and no-op (paused, not dropped) while an HVRT translate direction is
-- outstanding -- review fix: a heading/altitude/speed goal and an HVRT
-- translate both being reachable from `HVR` meant this tick and
-- `ai_pilot_goal_tick_hvrt` below could press in the same tick, on the
-- *same* button code (`AI_WHEEL_LEFT`/3003 is both the mode-cycle press
-- here and the HVRT-left translate hold there). Body-layer's own
-- `goal_param_for_wire` already nulls `.param` on every message it sends
-- while a translate is held, so `ai_pilot_goal.param` is normally `nil`
-- by the time this runs; the explicit check below is the second,
-- Lua-side half of "never both press in one tick" (plan's review fix),
-- not the only one.
local function ai_pilot_goal_tick(t)
    if ai_pilot_goal.param == nil then
        return
    end
    -- Stage P3+P4: a CBTM action pauses the goal channel the same way
    -- an outstanding HVRT translate already does (plan, "cbtm_action
    -- non-None pauses the goal/HVRT ticks the same way an outstanding
    -- HVRT direction already pauses the goal tick") -- both ultimately
    -- drive the same physical wheel buttons.
    if ai_pilot_cbtm.action ~= nil then
        ai_pilot_goal_release_hold()
        return
    end
    if ai_pilot_goal.hvrt_direction ~= nil then
        ai_pilot_goal_release_hold()
        return
    end
    if not ai_pilot_goal_mode_ready(ai_pilot_mode_text) then
        ai_pilot_goal_release_hold()
        if ai_pilot_goal.mode_cycle_attempts >= MODE_CYCLE_MAX_ATTEMPTS then
            if ai_pilot_goal.mode_blocked_since_t == nil then
                ai_pilot_goal.mode_blocked_since_t = t
            end
            if t - ai_pilot_goal.mode_blocked_since_t < MODE_BLOCKED_RETRY_S then
                ai_pilot_goal.progress = "mode_blocked"
                return
            end
            -- Cooldown elapsed: reset and fall through to try again this
            -- same tick, rather than waiting for yet another tick to
            -- spend the first renewed attempt.
            ai_pilot_goal.mode_cycle_attempts = 0
            ai_pilot_goal.mode_blocked_since_t = nil
        end
        ai_pilot_goal.progress = "cycling_mode"
        ai_pilot_tap30(AI_WHEEL_LEFT)
        ai_pilot_goal.mode_cycle_attempts = ai_pilot_goal.mode_cycle_attempts + 1
        ai_pilot_last_press = "goal_mode_cycle"
        return
    end
    ai_pilot_goal.mode_cycle_attempts = 0
    ai_pilot_goal.mode_blocked_since_t = nil
    if ai_pilot_goal.param == "heading" then
        ai_pilot_goal_tick_heading(t)
    elseif ai_pilot_goal.param == "altitude" then
        ai_pilot_goal_tick_altitude(t)
    else
        ai_pilot_goal_tick_speed(t)
    end
end

-- Stage P2b: HVRT translate's own tick -- the plan's original "mode-
-- exclusive by construction" claim for this and `ai_pilot_goal_tick`
-- above does not hold (see that function's own comment); the two are
-- independent in the sense that neither queues or shares state with the
-- other, not in the sense that they cannot both be asked to act at once.
-- `.hvrt_direction` has no queueing/active-param state of its own, only
-- a held press that opens, redirects or releases as the field changes,
-- plus the safety timeout. **Only ever reached from `HVR` or already
-- `HVRT`** -- body-layer's own hover precondition (crew_console's
-- "unable, not ready" check) is what keeps this from ever being asked
-- to cycle from `FLT`, where the known cycle graph could not reach
-- `HVRT` within `MODE_CYCLE_MAX_ATTEMPTS` at all. Its own mode-cycle
-- (into `HVRT`) is bounded and retried the same way `ai_pilot_goal_
-- tick`'s is (`.hvrt_mode_cycle_attempts`/`.hvrt_mode_blocked_since_t`, a
-- separate pair so the two ticks never share one counter) -- review fix:
-- previously unbounded, so a press that never registered tapped
-- `AI_WHEEL_LEFT` forever with nothing reported and no voice escape,
-- since `crew_console`'s own "Hold" cancel was gated on the same
-- readiness check that gates the *start* (fixed on the body-layer side,
-- `_handle_hvrt_hold`). **`HVR` is also the one aircraft mode the
-- FLT/HVR goal channel's own `ai_pilot_goal_mode_ready` accepts** -- the
-- two channels being simultaneously reachable from the same mode is
-- `ai_pilot_goal_tick`'s own fix to make (the `.hvrt_direction` guard at
-- its top), not this function's: HVRT always wins once a translate
-- direction is set, so there is no reciprocal guard needed here.
local function ai_pilot_goal_tick_hvrt(t)
    -- Stage P3+P4: same CBTM pause as `ai_pilot_goal_tick` above.
    if ai_pilot_cbtm.action ~= nil then
        if ai_pilot_goal.hvrt_hold_cmd ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
            end)
            ai_pilot_goal.hvrt_hold_cmd = nil
            ai_pilot_goal.hvrt_started_t = nil
        end
        return
    end
    if ai_pilot_goal.hvrt_direction == nil then
        if ai_pilot_goal.hvrt_hold_cmd ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_pilot_goal.hvrt_hold_cmd, 0)
            end)
            ai_pilot_goal.hvrt_hold_cmd = nil
            ai_pilot_goal.hvrt_started_t = nil
        end
        ai_pilot_goal.hvrt_mode_cycle_attempts = 0
        ai_pilot_goal.hvrt_mode_blocked_since_t = nil
        return
    end
    if ai_pilot_mode_text ~= "HVRT" then
        if ai_pilot_mode_text == nil then
            return
        end
        if ai_pilot_goal.hvrt_mode_cycle_attempts >= MODE_CYCLE_MAX_ATTEMPTS then
            if ai_pilot_goal.hvrt_mode_blocked_since_t == nil then
                ai_pilot_goal.hvrt_mode_blocked_since_t = t
            end
            if t - ai_pilot_goal.hvrt_mode_blocked_since_t < MODE_BLOCKED_RETRY_S then
                ai_pilot_goal.progress = "mode_blocked"
                return
            end
            ai_pilot_goal.hvrt_mode_cycle_attempts = 0
            ai_pilot_goal.hvrt_mode_blocked_since_t = nil
        end
        ai_pilot_goal.progress = "cycling_mode"
        ai_pilot_tap30(AI_WHEEL_LEFT)
        ai_pilot_goal.hvrt_mode_cycle_attempts = ai_pilot_goal.hvrt_mode_cycle_attempts + 1
        ai_pilot_last_press = "goal_hvrt_mode_cycle"
        return
    end
    ai_pilot_goal.hvrt_mode_cycle_attempts = 0
    ai_pilot_goal.hvrt_mode_blocked_since_t = nil
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

-- Stage P3+P4: CBTM is reachable only from this one overlay mode --
-- unlike the FLT/HVR goal channel's two-mode acceptance.
local function ai_pilot_cbtm_mode_ready(mode_text)
    return mode_text == "CBTM"
end

-- Clears every running-episode field back to idle -- called once a
-- channel action's last press has released, or once a bare "align"
-- tap has fired. Never touches `.action`/`.seq` themselves when called
-- mid-episode by anything other than the action's own completion (there
-- is no such caller today, but this keeps the reset's own meaning
-- narrow: "this run is over," not "forget what the last run was").
local function ai_pilot_cbtm_finish()
    ai_pilot_cbtm.action = nil
    ai_pilot_cbtm.status = "done"
    ai_pilot_cbtm.presses_done = 0
    ai_pilot_cbtm.gap_until_t = nil
    ai_pilot_cbtm.mode_cycle_attempts = 0
    ai_pilot_cbtm.mode_blocked_since_t = nil
end

-- Stage P3+P4's own dispatcher (plan, "The CBTM one-shot wire channel"):
-- cycles to CBTM first (bounded/retried the same way the goal channel's
-- own mode-cycle is, `MODE_CYCLE_MAX_ATTEMPTS`/`MODE_BLOCKED_RETRY_S`,
-- no new bound invented), then issues the one press shape the action
-- needs. The actual *release* of a timed press happens in `run_ai_
-- pilot_wheel`'s own per-frame deadline check below (`ai_wheel_cbtm_
-- pending_release_t`), never here -- same split every other timed press
-- in this file already has (open here, release there).
local function ai_pilot_cbtm_tick(t)
    if ai_pilot_cbtm.action == nil then
        return
    end
    ai_pilot_cbtm.status = "running"
    if ai_wheel_cbtm_pending_cmd ~= nil then
        -- A timed press is already open -- nothing to decide until it
        -- releases.
        return
    end
    if ai_pilot_cbtm.gap_until_t ~= nil then
        if t < ai_pilot_cbtm.gap_until_t then
            return
        end
        ai_pilot_cbtm.gap_until_t = nil
    end
    if not ai_pilot_cbtm_mode_ready(ai_pilot_mode_text) then
        if ai_pilot_cbtm.mode_cycle_attempts >= MODE_CYCLE_MAX_ATTEMPTS then
            if ai_pilot_cbtm.mode_blocked_since_t == nil then
                ai_pilot_cbtm.mode_blocked_since_t = t
            end
            if t - ai_pilot_cbtm.mode_blocked_since_t < MODE_BLOCKED_RETRY_S then
                return
            end
            ai_pilot_cbtm.mode_cycle_attempts = 0
            ai_pilot_cbtm.mode_blocked_since_t = nil
        end
        ai_pilot_tap30(AI_WHEEL_LEFT)
        ai_pilot_cbtm.mode_cycle_attempts = ai_pilot_cbtm.mode_cycle_attempts + 1
        ai_pilot_last_press = "cbtm_mode_cycle"
        return
    end
    ai_pilot_cbtm.mode_cycle_attempts = 0
    ai_pilot_cbtm.mode_blocked_since_t = nil

    if ai_pilot_cbtm.action == "align" then
        -- Short up, release -- the inner-ring option, a same-frame tap
        -- (plan: "'align' -- short-up, release").
        ai_pilot_tap30(AI_WHEEL_UP)
        ai_pilot_last_press = "cbtm_align"
        ai_pilot_cbtm_finish()
        -- BL-16 Stage 3 -- schedule the delayed overlay-course read
        -- into `desired.heading_deg` (module docstring, `ALIGN_READ_
        -- DELAY_S`). A later align press (or anything else) simply
        -- overwrites this deadline -- only the most recent align's own
        -- read ever lands.
        ai_wheel_align_read_at_t = t + ALIGN_READ_DELAY_S
        return
    end

    local cmd = AI_PILOT_CBTM_PRESS_CMD[ai_pilot_cbtm.action]
    safe_call(function()
        GetDevice(30):performClickableAction(cmd, 1)
    end)
    ai_wheel_cbtm_pending_cmd = cmd
    ai_wheel_cbtm_pending_release_t = t + LONG_PRESS_HOLD_S
    ai_pilot_cbtm.presses_done = ai_pilot_cbtm.presses_done + 1
    ai_pilot_last_press = "cbtm_" .. ai_pilot_cbtm.action
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

    -- Stage P3+P4's own release-deadline check, against its own third
    -- pending pair. Unlike the two checks above, releasing here is
    -- always the *normal* path (every CBTM timed press releases after
    -- exactly `LONG_PRESS_HOLD_S`, there is no convergence to wait for),
    -- so what happens next depends only on how many presses the action
    -- needed: `break_away`'s first release opens the `BREAK_AWAY_GAP_S`
    -- gap before its second; every other case (including `break_away`'s
    -- own second release) finishes the episode.
    if ai_wheel_cbtm_pending_release_t ~= nil and t >= ai_wheel_cbtm_pending_release_t then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_cbtm_pending_cmd, 0)
        end)
        ai_wheel_cbtm_pending_release_t = nil
        ai_wheel_cbtm_pending_cmd = nil
        if ai_pilot_cbtm.action == "break_away" and ai_pilot_cbtm.presses_done < 2 then
            ai_pilot_cbtm.gap_until_t = t + BREAK_AWAY_GAP_S
        else
            ai_pilot_cbtm_finish()
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

    -- Seat gate: the stow arg counts only while the player is in the
    -- operator seat -- in the pilot seat 852 reads stowed with nobody
    -- but the player flying (`SEAT_BOUNDARY_FWD_M`'s comment). Leaving
    -- the operator seat is still immediate (`in_operator_seat and
    -- stick_park or nil` below forces the reading to `nil` the same
    -- frame) -- only entering it waits out the settle window, and only
    -- while still in the operator seat: a hop back to the pilot seat
    -- before the window ends clears `in_operator_seat` and the real,
    -- immediate gate applies, never the held value.
    ai_pilot_update_seat(t)
    local in_operator_seat = ai_pilot_player_seat == "operator"
    if ai_pilot_seat_settle_until_t ~= nil and t >= ai_pilot_seat_settle_until_t then
        ai_pilot_seat_settle_until_t = nil
    end
    local settling = in_operator_seat and ai_pilot_seat_settle_until_t ~= nil
    local now_parked, rising
    if settling then
        now_parked, rising = ai_pilot_parked_active, false
    else
        now_parked, rising = ai_pilot_park_rising(
            ai_pilot_parked_active, in_operator_seat and stick_park or nil)
    end
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
        -- resumes on the next park"). Unconditional, regardless of seat
        -- (fix/ai-wheel-pilot-seat-gate's own rule: leaving the seat
        -- releases held presses with no menu tap -- a held press is a
        -- physical cockpit-device action, not a wheel-menu navigation,
        -- so there is no "wrong wheel" risk in releasing it from either
        -- seat).
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
        -- Stage P3+P4's own release, same frame -- the same "nothing
        -- resumes on the next park" reasoning as the goal channel's own
        -- release immediately above.
        if ai_wheel_cbtm_pending_release_t ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_wheel_cbtm_pending_cmd, 0)
            end)
            ai_wheel_cbtm_pending_release_t = nil
            ai_wheel_cbtm_pending_cmd = nil
        end
        ai_pilot_cbtm.action = nil
        ai_pilot_cbtm.status = "idle"
        ai_pilot_cbtm.presses_done = 0
        ai_pilot_cbtm.gap_until_t = nil
        ai_pilot_cbtm.mode_cycle_attempts = 0
        ai_pilot_cbtm.mode_blocked_since_t = nil
        -- Close the menu only if the player is still in the operator
        -- seat (took the controls back). Leaving the seat ends AI flight
        -- on DCS's side; a menu tap then would land on the pilot seat's
        -- own wheel -- exactly the press this gate exists to prevent.
        if ai_pilot_takeover.menu_open and in_operator_seat then
            ai_pilot_tap30(WHEEL_MENU_BUTTON)
        end
        ai_pilot_takeover.menu_open = false
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
        ai_pilot_goal.mode_blocked_since_t = nil
        ai_pilot_goal.hold_cmd = nil
        ai_pilot_goal.toggling_reference = false
        ai_pilot_goal.hvrt_direction = nil
        ai_pilot_goal.hvrt_hold_cmd = nil
        ai_pilot_goal.hvrt_started_t = nil
        ai_pilot_goal.hvrt_mode_cycle_attempts = 0
        ai_pilot_goal.hvrt_mode_blocked_since_t = nil
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
        -- Stage P3+P4's own tick, same `not fields_all_nil` guard as
        -- the goal tick (it reads `ai_pilot_mode_text` too). `ai_pilot_
        -- cbtm.action` is set by `handle_ai_pilot_goal_command` on
        -- message receipt, not by this tick, so the two ticks' relative
        -- order here does not matter for the pause guard.
        ai_pilot_cbtm_tick(t)
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

-- ``BL-B139``'s own bool parse -- `extract_json_string_field`/`_number_
-- field` (`core.lua`) have no boolean sibling; mirrors `flight_control.
-- lua`'s own local copy of the same helper (kept local there too, not
-- promoted to `_G`) rather than inventing a third shape.
local function extract_json_bool_field(json_text, field_name)
    if json_text:match("\"" .. field_name .. "\"%s*:%s*true") then
        return true
    end
    if json_text:match("\"" .. field_name .. "\"%s*:%s*false") then
        return false
    end
    return nil
end

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
    -- ``BL-B139``'s own sticky flag -- absent (`nil`, an older body-
    -- layer or a message that never set it) reads as `false`, same
    -- "missing means the old behaviour" posture every additive field on
    -- this channel already takes.
    local wake = extract_json_bool_field(data, "wake")
    if wake == nil then
        wake = false
    end
    -- `hvrt_step` is a **one-shot trigger**, not sticky state like every
    -- other field here (Stage P2b's own task list, not in the plan's
    -- "wire shape" section -- see `CommandSender.send_ai_pilot_goal`'s
    -- own docstring for why this field exists at all). Acted on exactly
    -- once per distinct `goal_seq` -- checked against the *old*
    -- `ai_pilot_goal.goal_seq` below, before it is overwritten, so a
    -- re-delivered or otherwise-unchanged message never taps twice.
    local hvrt_step = extract_json_string_field(data, "hvrt_step")
    if hvrt_step ~= nil and goal_seq ~= ai_pilot_goal.goal_seq then
        local step_cmd = nil
        if hvrt_step == "up" then
            step_cmd = AI_WHEEL_UP
        elseif hvrt_step == "down" then
            step_cmd = AI_WHEEL_DOWN
        end
        if step_cmd ~= nil then
            ai_pilot_tap30(step_cmd)
            ai_pilot_last_press = "goal_hvrt_step"
        end
    end

    if param ~= ai_pilot_goal.param then
        ai_pilot_goal_release_hold()
        ai_pilot_goal.mode_cycle_attempts = 0
        ai_pilot_goal.mode_blocked_since_t = nil
        ai_pilot_goal.toggling_reference = false
        -- ``BL-B139``: a wake kick in progress for the *previous*
        -- param must not bleed into the new one -- same reasoning as
        -- the three resets above, extended to the wake-kick fields.
        ai_pilot_goal.wake_kick_dir = nil
        ai_pilot_goal.wake_kick_started_t = nil
        ai_pilot_goal.wake_kick_tried_up = false
    end

    ai_pilot_goal.goal_seq = goal_seq
    ai_pilot_goal.param = param
    ai_pilot_goal.wake = wake
    ai_pilot_goal.heading_target_deg = heading_target_deg
    ai_pilot_goal.altitude_target_m = altitude_target_m
    ai_pilot_goal.altitude_target_ref = altitude_target_ref
    ai_pilot_goal.speed_target_kmh = speed_target_kmh
    ai_pilot_goal.hvrt_direction = hvrt_direction

    -- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`) -- this
    -- channel no longer mirrors itself into `desired` here: body-layer
    -- now sends an explicit numbered `set` on the `flight` channel
    -- alongside every mode-2 voice goal (plan, Stage 3 bullet "Every
    -- mode-2 voice goal also writes a set"), which is what updates
    -- `desired` -- that write carries its own `seq`/epoch/bounds
    -- checking, which this receipt-time mirror never had.
    if param ~= nil then
        ai_pilot_goal.progress = "pressing"
    elseif hvrt_direction == nil then
        ai_pilot_goal.progress = "idle"
    end

    -- Stage P3+P4's own sibling one-shot fields, same message (plan,
    -- "The CBTM one-shot wire channel"). `cbtm_seq` is this channel's
    -- own distinct sequence space, never compared against `goal_seq`
    -- above -- acted on exactly once per distinct `cbtm_seq`, same
    -- "act once per distinct seq" contract `hvrt_step` already has. A
    -- fresh trigger always starts a new run, releasing whatever timed
    -- press the previous one left open (a break always wins -- F-P7 --
    -- and there is no other caller that could leave a stale press open
    -- across two distinct `cbtm_seq` values in correct operation).
    local cbtm_action = extract_json_string_field(data, "cbtm_action")
    local cbtm_seq = extract_json_number_field(data, "cbtm_seq")
    if cbtm_action ~= nil and cbtm_seq ~= nil and cbtm_seq ~= ai_pilot_cbtm.seq then
        if ai_wheel_cbtm_pending_release_t ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_wheel_cbtm_pending_cmd, 0)
            end)
            ai_wheel_cbtm_pending_release_t = nil
            ai_wheel_cbtm_pending_cmd = nil
        end
        ai_pilot_cbtm.action = cbtm_action
        ai_pilot_cbtm.seq = cbtm_seq
        ai_pilot_cbtm.status = "running"
        ai_pilot_cbtm.presses_done = 0
        ai_pilot_cbtm.gap_until_t = nil
        ai_pilot_cbtm.mode_cycle_attempts = 0
        ai_pilot_cbtm.mode_blocked_since_t = nil
    elseif param ~= nil and ai_pilot_cbtm.action ~= nil then
        -- 2026-11-20 rework (`docs/acceptance/2026-11-20-sortie-
        -- feedback.md`, "Mode 2 root cause and the 'latest wins'
        -- direction"): a heading/altitude/speed goal message arriving
        -- while a CBTM episode (align/align-for-launch/break/break-
        -- away) is still open ends that episode immediately -- "latest
        -- player command always wins" (user, verbatim), not "wins once
        -- Export.lua reports the episode done." Without this,
        -- `ai_pilot_goal_tick` (and `ai_pilot_goal_tick_hvrt`) would
        -- keep pausing against `ai_pilot_cbtm.action ~= nil` until the
        -- episode releases on its own -- the goal would sit
        -- acknowledged but never flown, the same symptom the original
        -- bug had, moved one layer down. Releases any open timed press
        -- and drops `break_away`'s own pending second press
        -- (`.gap_until_t`) the same way `ai_pilot_cbtm_finish` always
        -- has; `.status` becomes `"done"`, the same value a break that
        -- ran to completion reports -- body-layer's own `decide_ai_
        -- pilot_wheel` no longer reads this status for F-P7 at all
        -- (command order alone decides it now), so there is no reason
        -- to invent a second, distinct "superseded" status value only
        -- this layer would ever read.
        if ai_wheel_cbtm_pending_release_t ~= nil then
            safe_call(function()
                GetDevice(30):performClickableAction(ai_wheel_cbtm_pending_cmd, 0)
            end)
            ai_wheel_cbtm_pending_release_t = nil
            ai_wheel_cbtm_pending_cmd = nil
        end
        ai_pilot_cbtm_finish()
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
        -- `json_escape_string` already returns a quoted literal
        -- (`"..."`) -- wrapping it in another pair of quotes here
        -- produced `""FLT""`, invalid JSON, on every non-nil text field
        -- (found and fixed, `plans/apw-status-json-quotes/debug.md`).
        return json_escape_string(value)
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
        .. ',"apw_goal_seq":' .. fmt_int_or_null(ai_pilot_goal.goal_seq)
        .. ',"apw_seat":' .. text_or_null(ai_pilot_player_seat)
        .. ',"apw_cam_fwd_m":' .. fmt_num_or_null(ai_pilot_cam_fwd_m)
        .. ',"apw_cbtm_status":' .. text_or_null(ai_pilot_cbtm.status)
        .. ',"apw_cbtm_seq":' .. fmt_int_or_null(ai_pilot_cbtm.seq)
        .. ',"apw_reset_epoch":' .. fmt_int_or_null(ai_pilot_reset_epoch) .. '}\n')
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
    ai_pilot_goal.mode_blocked_since_t = nil
    ai_pilot_goal.hold_cmd = nil
    ai_pilot_goal.toggling_reference = false
    ai_pilot_goal.hvrt_direction = nil
    ai_pilot_goal.hvrt_hold_cmd = nil
    ai_pilot_goal.hvrt_started_t = nil
    ai_pilot_goal.hvrt_mode_cycle_attempts = 0
    ai_pilot_goal.hvrt_mode_blocked_since_t = nil
    -- Stage P3+P4's own release/reset -- same AC-B13-class gap (a
    -- long-lived open press with no `LuaExportStop` reset) this
    -- channel would otherwise have.
    if ai_wheel_cbtm_pending_cmd ~= nil then
        safe_call(function()
            GetDevice(30):performClickableAction(ai_wheel_cbtm_pending_cmd, 0)
        end)
    end
    ai_wheel_cbtm_pending_release_t = nil
    ai_wheel_cbtm_pending_cmd = nil
    ai_pilot_cbtm.action = nil
    ai_pilot_cbtm.status = "idle"
    ai_pilot_cbtm.presses_done = 0
    ai_pilot_cbtm.gap_until_t = nil
    ai_pilot_cbtm.mode_cycle_attempts = 0
    ai_pilot_cbtm.mode_blocked_since_t = nil
    -- A new mission starts with no seat known: nothing is pressed until
    -- the camera has placed the player in the operator seat.
    ai_pilot_player_seat = nil
    ai_pilot_cam_fwd_m = nil
    ai_pilot_seat_settle_until_t = nil
end

-- Body-layer process-start reset (BL-16 sortie 2026-11-20, `docs/
-- acceptance/2026-11-20-sortie-feedback.md`) -- same reasoning as
-- `flight_control.lua`'s own `reset()`: reuses `on_stop` above (lets go
-- of every open press, clears the goal/CBTM/takeover state, same
-- effect a mission restart already has -- ED's AI keeps flying), then
-- goes one step further for the two seq fields `on_stop` deliberately
-- leaves alone (they are not reset across a mission restart, same
-- "mirror the last value sent" posture `flight_control.lua`'s own `fc_
-- last_cmd_seq` has): `ai_pilot_goal.goal_seq`/`ai_pilot_cbtm.seq` go
-- back to their startup default (`0`), so body-layer's own fresh goal/
-- CBTM cursors (which also start this process at their own defaults)
-- are never seen as "nothing new" against a stale pre-restart value.
-- Idempotent and safely re-sendable, same posture as `flight_control.
-- lua`'s `reset()`.
local function reset(epoch)
    on_stop()
    ai_pilot_goal.goal_seq = 0
    ai_pilot_cbtm.seq = 0
    ai_pilot_reset_epoch = epoch
end

-- `plans/flight-control/plan.md`, "Revised 2026-11-18", Decision 25 --
-- read-only getters for `flight_control.lua`, the mode-1 module. **Must
-- return `ai_pilot_parked_active`, never 852 alone**: 852 alone would
-- self-release mode 1 the moment it started with the player in the
-- pilot seat (852 reads stowed there with nobody but the player flying
-- -- the seat gate above is exactly what tells the two cases apart).
local function is_parked()
    return ai_pilot_parked_active
end

-- Read-only mirror of `ai_pilot_player_seat` -- `"pilot"`/`"operator"`/
-- `nil` (unknown this mission). Never gates whether mode 1 may run
-- (Decision 25). **Read again by `flight_control.lua`'s voice-take
-- capture** (user rule 2026-11-24, `plans/flight-lift-vector/debug-
-- 2026-11-24b.md`: read the controls of the seat the player is in) --
-- first choice whenever that seat's arg set reads live; M0-J's (flight
-- 9) finding that the camera seat can read an all-zero set before the
-- player requests control is why an idle player's seat still falls back
-- to the live-set rule (`aircraft-layer/research/2026-11-18-bl16-m0-
-- flight-axes-findings.md`, "Flight 9").
local function player_seat()
    return ai_pilot_player_seat
end

-- Read-only mirror of the raw stow arg (852) -- `flight_control.lua`'s
-- own unpark-take capture rule (M0-J, flight 9) tracks this every frame
-- while parked to find the last frame it read fully stowed (>= 0.99),
-- since the two arg sets have already begun their ~1.5 s cross-fade by
-- the time `ai_pilot_parked_active`'s own 0.9 edge fires.
local function stick_park_raw()
    return ai_pilot_takeover.raw_arg852
end

-- Read-only getter for the overlay's own *set* heading/altitude/speed,
-- the same parsed fields `ParkedFlightState.held_heading`/`held_
-- altitude`/`held_altitude_ref`/`held_speed` mirror on the body-layer
-- side (`update_ai_pilot_wheel_overlay` above is this module's single
-- parse site for the raw text; this getter re-reads the same locals,
-- never a second parse). Every field may be `nil` (not yet read this
-- mission, or not a plain number -- `speed_text` can read `"MAX"`).
-- **BL-16 Stage 3**: no longer read by `flight_control.lua`'s own
-- unpark-take (that seed comes from `flight_desired.get()` now) --
-- still read by `flight_desired.lua`'s own off->m2 reseed and by this
-- module's own align-read below, both read-only against this module's
-- state, never the reverse.
local function held_targets()
    return {
        heading_deg = tonumber(ai_pilot_course_text),
        alt_m = ai_pilot_parse_altitude_text(ai_pilot_alt_text),
        alt_ref = ai_pilot_alt_add_text,
        speed_kmh = tonumber(ai_pilot_speed_text),
    }
end

-- BL-16 Stage 3 (module docstring near `ALIGN_READ_DELAY_S`) -- wraps
-- `run_ai_pilot_wheel` so the deferred align-read can call `held_
-- targets` above, which is declared after `run_ai_pilot_wheel` itself
-- (Lua has no hoisting: a function defined before a `local`'s own
-- declaration sees that name as a global, not this one -- `aircraft-
-- layer/CLAUDE.md`'s own "no-hoisting" note). Exported in `run_ai_
-- pilot_wheel`'s place below, so `Export.lua`'s call site needs no
-- change.
local function run_ai_pilot_wheel_with_align_read(t)
    if ai_wheel_align_read_at_t ~= nil and t >= ai_wheel_align_read_at_t then
        ai_wheel_align_read_at_t = nil
        if flight_desired ~= nil then
            local held = safe_call(held_targets)
            if type(held) == "table" and type(held.heading_deg) == "number" then
                safe_call(function()
                    flight_desired.write_internal({ heading_deg = held.heading_deg })
                end)
            end
        end
    end
    return run_ai_pilot_wheel(t)
end

M.run_ai_pilot_wheel = run_ai_pilot_wheel_with_align_read
M.update_ai_pilot_wheel_overlay = update_ai_pilot_wheel_overlay
M.push_ai_pilot_wheel_state = push_ai_pilot_wheel_state
M.handle_ai_pilot_goal_command = handle_ai_pilot_goal_command
M.on_stop = on_stop
M.reset = reset
M.is_parked = is_parked
M.player_seat = player_seat
M.stick_park_raw = stick_park_raw
M.held_targets = held_targets

return M
