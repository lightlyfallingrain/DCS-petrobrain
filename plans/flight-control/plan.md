# BL-16 — Petrovich flies the helicopter: plan

2026-10-26, Architect pass, planning only. **Revised 2026-10-31** from the goal check
(`plans/flight-control/alignment.md`, CONCERNS) and the user's answers to it — see "Revised
2026-10-31" directly below for what changed and why. **`BL-16` stays `[>]` deferred** (user: finish
9K113 first); this plan exists so the work is ready when it is picked up, and so stage 0 can be
flown whenever convenient. Specification: `plans/flight-control/explore-notes.md` (whole file,
including both 2026-10-26 addenda and the 2026-10-31 "Goal-check answers", which are binding) and
`docs/concept/flight-control-{1,2,3}.jpeg`. Where this plan and those words disagree, the words win
and this plan is wrong.

## Revised 2026-11-15 — parked mode (mode 2) is the first build

**Re-cut by the Architect**, user direction 2026-11-15: *"take BL-16, remove deferred status.
Let's build it. Let's actually start with the AI helper, that's the Player uses 9K113 case and
it's important to get done. After that we can build our own controls-not-parked flight
controlling."* Everything below the next divider (`## Series — unparked mode (mode 1): later
build, preserved unchanged`) is the **original 2026-10-26/10-31 plan, untouched** — its stage
numbers (0–6), decisions, co-moving fields and risks all still describe **mode 1 only** and are
not re-derived here. This section is the **new, separate stage series for mode 2**, numbered
**P0–P6** so the two series never collide. `BL-16`'s own entry
(`body-layer/ROADMAP/BL-16.md`) already carries the two-mode split and the stage-0 finding that
forces it.

### Why two modes, and why parked first

Stage 0 (mode 1's own S0-P block, flown 2026-11-01, `main`'s
`aircraft-layer/research/2026-11-01-bl16-command-hold-probe-findings.md` — that commit is on
`main` but not yet merged into this feature branch; its content is quoted below because it is the
fact that forces this re-cut) found that **a per-frame `LoSetCommand(2001–2003)` write is
completely ignored while the controls are parked** — user, verbatim: *"both pilot and copilot
control works, but only when control is not parked. When I press to park controls, DCS AI takes
over flying and does it's own thing overriding ours."* The probe's own log: during a held
operator-seat override, park cross-fades the cockpit args to the AI's own values over ~1.3 s and
the aircraft follows the AI, "no fight visible — the aircraft follows the AI, not a blend." S0-P2
(the raw-axis override, mode 1's lead hypothesis for the parked state) is **closed negative**.
S0-P3 (neutralise the AI while parked) was never run — the user skipped it directly to the
fallback: *"2 - skip it. BL-16 has to go with two modes: normal ops - write control axises;
controls parked - manipulate DCS AI via the AI wheel commands."* So **S0-P3b, the plan's own
documented fallback, is promoted from fallback to the production design for the parked state**,
and S0-P1/S0-P1b/S0-P2/S0-P2a–c/S0-P3/S0-P5/S0-P6 (the raw-axis-override rows for the parked
state) are now dead rows, closed by this finding — they are **not** re-run or re-planned; they
stay in the mode-1 series below only as the historical record of why mode 2 exists.

**Why parked first, not unparked:** the parked case is the user's named key use — *"that's the
Player uses 9K113 case and it's important to get done"* — and it is also the harder, riskier half
(driving ED's own AI through a menu rather than writing axes Petrobrain fully owns). Building it
first means the project's hardest unknown is resolved before the easier unparked series is
designed in depth; the 2026-10-26/10-31 unparked plan below stays as reference and is picked up
unchanged once mode 2 passes DoD.

**Goal check:** `plans/flight-control/alignment.md`, "Goal check — parked mode (2026-11-15)".
Verdict **ALIGNED** after the user's answers. Player expectations E-P1, E-P3–E-P11 (E-P2
withdrawn — no spoken line on park or unpark) are the specification this series has to satisfy;
every stage below says which E-P row it closes.

### Goal (mode 2)

On the park signal — no spoken handover — Petrovich takes over driving ED's own AI pilot through
the HELPER_AI wheel (device 30), resets its held altitude to current (the fix for the AI's known
park-sink), and from then on turns the pilot's spoken heading/altitude/speed goals into wheel
presses that move the AI's own held values toward them, one parameter at a time, within loose
tolerances (A9's same ±10%/20 m posture carried over). "Align" and "align for launch" are pressed
only on the pilot's word, from the sight seat. After a launch, an abort, or crossing a safety
floor/ceiling, Petrovich takes the AI back to level flight on his own and restores the
pre-alignment parameters. Unparking returns the aircraft to the player at once, silently.
Naked-eye lookout continues throughout; this mode never touches the 9K113 sight itself (the
player is on it).

### Amended 2026-11-15 (vocabulary, ICS capture, cycle orders)

Three things the user settled in the same message that answered plan check **Q-P1**
(`plans/flight-control/alignment.md`, "Plan check Q-P1 answered by the user"), folded in below
rather than re-cut — **the stage structure (P0–P6) is unchanged**; only P1–P4's content, the
Co-moving Fields table, the Behaviour constants table and the Risks list are edited in place.
Source, verbatim: `plans/flight-control/explore-notes.md`, "U3 decided, mode-cycle orders, and
the player command vocabulary"; the cycle orders are also now carried in
`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md` §5's state diagram.

**1. ICS capture from the operator seat is a new prerequisite stage, P-ICS, before P0** — see its
own write-up, inserted just above Stage P0 below. *"Audio capture must listen to both pilot and
copilot ICS (VOIP) triggers and treat them equally ... This is prerequirement for BL-16 player
commands to work"* (user, verbatim). Gates every parked-mode flight in this series, since the
pilot speaks from the CPG seat while parked.

**2. The short-left cycle has known orders**, so the mode-cycle loop (P1/P2) can bound its own
attempt count instead of an open-ended "escalate after N attempts": **`FLT > CBTM > FLT`** and
**`HVR > HVRT > CBTM > HVR`**. CBTM has two homes — which one a short-left returns to depends on
whether the aircraft was in forward flight or hover before the cycle into CBTM. The automatic
(DCS-driven) transitions are unchanged from the research note: FLT→HVR on speed 0 + slowing,
HVR→FLT on speed > 0 + accelerating, FLT/HVR→CBTM on CPG-view entry, CBTM→FLT/HVR on CPG-view
exit (user not certain which — the "read the mode every tick, never assume" posture this plan
already states covers that uncertainty without a design change). **U3 is answered**: a
player-driven mode press is reasserted over at once, not deferred — *"reassert at once — the
goal is to use the wheel command via Petrobrain, not player directly"* (user, verbatim). New
constant `MODE_CYCLE_MAX_ATTEMPTS = 3` (table below) replaces the open-ended attempt language in
P1/P2 — every mode in the cycle is at most 2 presses from any other, so 3 is a comfortable bound,
not a guess.

**3. The player vocabulary is now fully specified**, replacing the placeholder examples P2/P3
used ("turn heading 3 1 5", "hold 200 m radar", "speed 2 2 0"):

| Spoken | Token | Mode needed | Action / press | Notes |
|---|---|---|---|---|
| "level flight" | `level_flight` | FLT/HVR | `set_parked_heading`/`altitude`/`speed`, each to the **current** read value | stabilise, not a numeric target the pilot names |
| "Heading &lt;deg&gt;" | `turn_heading` | FLT/HVR | `set_parked_heading(deg)` | numeric; audio-adapter slot parser, built here first (P2), reused by mode 1's own Stage 4 later |
| "Heading &lt;N/NE/E/…&gt;" | `turn_heading` | FLT/HVR | same, after an 8/16-point compass→degrees translation | new audio-adapter slot parser |
| "Turn left/right &lt;deg&gt;" | `turn_heading_relative` | FLT/HVR | `set_parked_heading(current ± deg)`, computed once at command time | relative, not re-derived as the aircraft turns |
| "Break turn left/right" | `cbtm_break` | CBTM | Lua: long press left/right, no hold — 90° break | cycles to CBTM first if needed, same cycle-then-press shape as `cbtm_align` |
| "Break away" | `cbtm_break_away` | CBTM | Lua: long press left, wait `BREAK_AWAY_GAP_S`, long press left again | the two-`BREAK LEFT` 180 — "Mi-24 turns faster left" (user); `BREAK 180`'s own press is avoided, direction undetermined |
| "Align" / "Align [for] launch" | `cbtm_align` / `cbtm_align_for_launch` | CBTM | unchanged from Stage P3 | |
| "Straight" / "level off" | `level_off` | any | stop turn, hold current heading; **while `align_phase` is `"aligning"`/`"launch_aligned"`, this token is F-P1's spoken abort** (ties into Stage P4's recovery trigger list) | one token, two meanings gated by `align_phase` |
| "Speed &lt;value&gt;" | `set_speed` | FLT/HVR | nearest step; "max" is a legal value | |
| "Slow down" / "Speed up" | `speed_step` | FLT/HVR | one step down/up | |
| "Hover" | `set_speed` with value 0 | FLT/HVR | step 0 | causes the automatic FLT→HVR transition once DCS itself slows to hover |
| "alt[itude] &lt;value&gt; [radar/barometric]" | `set_altitude` | FLT/HVR | centre-toggle reference if it differs, then hold to value | **at risk, added 2026-11-16**: P0-5 measured a centre press *with the menu open* not toggling the reference at all (menu closed, it did). Stage P1's own takeover toggle presses centre while closed, before the menu is ever opened, which sidesteps this — but by the time P2 is built the menu is permanently open (the "menu stays open" decision below), so *this row's* centre-toggle may not be reachable as written. Needs a probe with a real pulse (not same-frame) before P2 commits to it; until then, treat "radar" as possibly unreachable by voice |
| "climb/descend &lt;m&gt;" | `altitude_step` | FLT/HVR | relative, current ± m | |
| "hold alt[itude]" | `hold_altitude` | FLT/HVR | freezes the goal at the current read altitude | |
| "left/right/forward/back" | `hvrt_translate` | **HVRT only** | Lua holds the press open until body-layer clears it — see Stage P2's HVRT sub-section | state-gated, not grammar-gated — see note below |
| "Hold" | `hvrt_hold` | HVRT only, while a translate is active | clears `held_translate_direction` | no existing token collision (grepped `crew_console.py`/`vocabulary.py`, none) |
| "up/down" | `hvrt_step` | HVRT only | Lua: short up/down, 2 m per tap, no hold semantics | |

**Vocabulary collision check, done rather than assumed**: `_RELATIVE_SCAN_TOKENS` already uses
bare "left"/"right" as *sectors* (`scan left`/`scan right`, `body-layer/src/belief/
crew_console.py` ~L321) and the step-through-contacts family uses them too (`step left`/`step
right`, ~L3774) — but **every existing use pairs the direction word with a verb** ("scan",
"step"); `audio-adapter/src/vocabulary.py`'s `PHRASES` table has no bare single-word phrase
today (confirmed by grep, not assumed). The new HVRT tokens are the first **bare** "left"/
"right"/"forward"/"back"/"up"/"down"/"hold" — `command_matcher.py`'s `VERB_ANCHOR_WORDS` is
derived from each phrase's own first word, so a bare phrase anchors on itself and would match
fine grammatically, but it would also fire outside HVRT with no mode check of its own. So this
needs **state-gated dispatch, not grammar alone**: `CrewConsole.handle_command` must route
`hvrt_translate`/`hvrt_step`/`hvrt_hold` to the AI-wheel handler only when `ai_mode == "HVRT"`,
and treat them as unmatched (fall through, same as any other out-of-context token) otherwise.

**`/command-map` must be redrawn once this vocabulary lands** — it spans Stage P2 (most of the
table above), Stage P3 (break/break-away), and Stage P4 (`level_off` as abort token). No separate
stage number is needed for the redraw itself: the merge skill's own stale-check
(`.claude/skills/command-map/SKILL.md`) fires automatically on whichever merge lands
`vocabulary.py` changes, per root `CLAUDE.md`'s existing merge sequence — flagged here so it is
not forgotten, not because this plan needs to own a new stage for it.

### Architecture decision: per-frame press timing lives in Export.lua, not body-layer

**The same split mode 1 already designed, reused rather than invented.** The wheel distinguishes
a short press (<0.5 s) from a long press/hold (>0.5 s, `HelperAI.lua:13`'s `long_press_time =
0.5`, confirmed live at a 0.80 s hold in
`aircraft-layer/research/2026-09-11-petrovich-detection-readout.md`, "CONFIRMED: far slots are
long presses") by timing a `performClickableAction(30, cmd, 1)` → `(cmd, 0)` pair on the frame
clock. Body-layer polls at roughly 1 Hz (`CrewConsole`'s poll loop); an HTTP-round-tripped press
sequence could not reliably land on the right side of a 0.5 s threshold, and a long **hold**
(altitude/heading, held "until the readback reaches target") needs to watch that readback every
frame to know when to release, not once a second. So:

- **Export.lua owns**: reading `list_indication(HELPERAI_DEVICE_ID)` (the same feed index, 6,
  that already carries Petrovich's own sensor target list — while the AI pilot flies, this page's
  content is the AI overlay instead, per
  `aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md` §3; **unverified whether it
  is populated with the wheel/overlay closed — Stage P0's first row**), parsing out
  `mode_text`/`course_text`/`alt_text`/`alt_add_text`/`speed_text`, deciding the next single press
  (a mode-cycle short-left, or the press the current goal needs), running the press/hold timing
  itself, and reporting a status line at the usual 5 Hz push rate (mirrors
  `run_sight_servo`/`push_sight_servo_state`).
- **Body-layer owns**: the handover/activation state (park signal → active, per E-P1), the
  **goal** (target heading/altitude/speed, one at a time per the interleaving rule below), the
  alignment/recovery state machine (E-P7–E-P9), and the vocabulary. It never decides *which wheel
  button* to press — only *what value Petrovich wants held*.

This keeps one Lua-side mechanism (`list_indication` parse → mode-aware nudge loop) that both the
heading/altitude/speed goal and the align/recovery exits use, instead of forking per command; it
is the same "controller vs effector" separation mode 1's plan already argues for its own loop.

### Actions, state params, "when" (root `CLAUDE.md`, "Behaviour as actions and params")

**Actions** (one thing, explicit params, report running/succeeded/failed, never decide *when*) —
new module `body-layer/src/belief/ai_pilot_wheel.py`:

- `set_parked_heading(deg: float)`, `set_parked_altitude(m: float, reference: "radar"|"baro")`,
  `set_parked_speed(step_kmh: float)` — each clamps to limits, returns the value actually set
  (A9's posture, carried over), bumps `goal_seq`.
- `cbtm_align()`, `cbtm_align_for_launch()` — player-only triggers (E-P7); refuse (not "unable" —
  silently ignored, since these are not spoken commands the player expects a readback failure
  from — this needs the user, see **U2**) outside CBTM-reachable state.
- `recover_to_level(reason: "launch"|"abort"|"agl_floor"|"ias_ceiling")` — internal-only entry
  point `decide_ai_pilot_wheel` calls; never reachable from voice.

**State params** (read-only queries over belief, typed, never DCS truth directly):
- `parked_active: bool`, `ai_mode: "FLT"|"CBTM"|"HVR"|"HVRT"|None` (mirrors Lua's parsed
  `mode_text`, `None` until first read), `held_heading/altitude/altitude_ref/speed: float | None`
  (the AI's own current values, read back from the status feed — never written directly), `goal:
  AiPilotWheelGoal | None`, `align_phase: "none"|"aligning"|"launch_aligned"|"recovering"`,
  `pre_align_snapshot: FlightSnapshot | None`.

**The "when"** — one function, `decide_ai_pilot_wheel(...)`, apart from the actions:
- activation on the park signal, altitude-first reset (issues 2026-11-15 write-up, "on park, set
  altitude to current, nudge if equal");
- interleaving: when more than one goal is outstanding, step one parameter's worth of progress per
  poll and rotate (the explore notes' own worked example: "speed +1 tap, heading −30°, alt +50 m,
  speed +1 tap, …" — body-layer decides the **order**, Lua executes **one press** per decide call
  and reports back before the next is issued, so the two loops stay in lockstep without body-layer
  needing frame-level timing);
- DCS-driven mode changes (CPG view → CBTM, hover transitions) are cycled back from toward
  whatever mode the current goal needs (Q4); a player-driven mode change is not expected and is
  not specially handled in this build (Q4) beyond the same cycle-back, which would otherwise
  silently undo a player's own wheel press — flagged as **U3**;
- alignment is entered only on `cbtm_align`/`cbtm_align_for_launch` (E-P7) and recovery fires on
  launch detection (payload count drop, reusing the feed `[[BL-B67]]` Stage 4 already built — see
  "Launch detection" below, never importing `belief.atgm_run` itself, per F-P3), a spoken abort, or
  crossing AGL < `AI_PILOT_RECOVER_AGL_FLOOR_M` / IAS > `AI_PILOT_RECOVER_IAS_CEILING_KMH` (Q5);
- recovery sequencing (Q7/Q8): snapshot heading+altitude at the recovery moment, mode-cycle to FLT
  (which, per Q7, adopts whatever heading is current rather than an old held one — no explicit
  heading press needed for the "hold current" half), say *"leveling off"*, then issue altitude and
  speed goals back toward `pre_align_snapshot` (altitude climbs smoothly via the same long-hold
  nudge loop; speed steps back **one step per decide cycle**, matching Q8's "one step at a time"
  and the interleaving rule above — no new mechanism).

### Launch detection, reusing BL-B67's feed only

F-P3 (`alignment.md`): the parked case is a **role swap** (player on the sight, Petrovich flying),
not a variant of `belief/atgm_run.py`'s own run. So `ai_pilot_wheel.py` reads
`AircraftLayerClient.get_payload_latest()` directly (the same feed `atgm_run.py`'s
`station_counts` already comes from) and watches for **any loaded station's count dropping
poll-to-poll** — the same signal shape as `atgm_run.py`'s `selected_step_count_last_seen`
bookkeeping, re-implemented locally rather than imported, because `atgm_run.py` is Petrovich's own
run and importing it here would wire the two together exactly as F-P3 says not to. No station
selection or knob logic is needed here — any count drop while `align_phase == "launch_aligned"`
is the player's shot.

### Co-moving Fields

Trigger fires: an align/recovery sub-state-machine with fields written externally (the player's
voice — `cbtm_align`/`cbtm_align_for_launch`/an abort word; DCS's own mode changes) and internally
(`decide_ai_pilot_wheel`'s recovery logic; Lua's own mode-cycle presses). `ParkedFlightState` and
the Lua `apw` table are new, so there are no construction sites yet to grep — **the Implementer
greps `ParkedFlightState(` and every assignment to Lua `apw.` after Stage P1 and extends this
table with any site not listed**, per step 6a's own worked lesson (`BL-B71`'s fourth
construction site, found only by grep, not by the transition narrative).

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `parked_active` | external (park signal, arg 852/952) | park → true | altitude goal set to current (nudge if equal); `align_phase = "none"`; no spoken line (E-P2 withdrawn) |
| `parked_active` | external (unpark) | unpark → false | Lua `apw.mode = off` same frame (held press released if any); any pending goal/align state dropped, not resumed on the next park (E-P10) |
| `align_phase` | external (voice) | `cbtm_align` | `"aligning"`; Lua cycles to CBTM, presses short-up |
| `align_phase` | external (voice) | `cbtm_align_for_launch` | `"launch_aligned"`; `pre_align_snapshot` captured from the **current** heading/altitude/speed goal (not the AI's raw readback, so a goal already in flight is what's restored); Lua cycles to CBTM, presses long-press-up |
| `align_phase` | internal (`decide_ai_pilot_wheel`) | launch detected / spoken abort / AGL floor / IAS ceiling, while `"launch_aligned"` | `"recovering"`; *"leveling off"* spoken once; Lua cycles to FLT |
| `align_phase` | internal | FLT reached and current heading/altitude snapshotted at that moment | `"recovering"` unchanged; `goal` set to `pre_align_snapshot`'s altitude and speed (heading is **not** re-issued — Q7, FLT already holds current) |
| `align_phase` | internal | `goal` settles within band on both altitude and speed | `"none"`; `pre_align_snapshot = None` |
| `goal` | external (voice) | new heading/altitude/speed command | `goal_seq` + 1; latest wins (E-P4); if `align_phase != "none"`, the goal is recorded but **not** issued to Lua until recovery reaches `"none"` (the alignment overrides it, per the open-assumption note in `alignment.md`) |
| Lua `apw.mode` | internal | mode read differs from what the current goal/align_phase needs | one short-left press issued, re-read next frame; no second press before the readback confirms the mode changed |
| Lua `apw.press` | internal | a press is open (long-hold in progress) and the mode changes underneath it | press released immediately (no held press survives a mode change — mirrors mode 1's own "a long hold in progress ends immediately on a mode change") |
| mode-cycle attempt count | internal (Lua) | `MODE_CYCLE_MAX_ATTEMPTS` (3) exhausted without reaching the needed mode | `goal_progress = "mode_blocked"`; the goal itself is **not** dropped — retried next poll (added 2026-11-15: the open-ended "escalate after N" language is now a named bound, per the Amended note above) |
| `held_translate_direction` | external (voice: left/right/forward/back, HVRT only) | HVRT translate command | set to that direction; Lua opens the matching outer-ring press that same frame it reads the change |
| `held_translate_direction` | external (voice: "Hold") | hold command | cleared to `None`; Lua releases the press the same frame it reads the clear |
| `held_translate_direction` | internal (Lua, `HVRT_TRANSLATE_MAX_HOLD_S` elapsed) | safety timeout | Lua releases the press and reports `"released_timeout"`; body-layer clears its own copy of the field on the next poll that observes the released status — no second source of truth held past that poll |
| `held_translate_direction` | internal | mode changes away from HVRT underneath an open translate | cleared and the press released immediately — same mode-change rule as the general `apw.press` row above |

(added 2026-11-15, the "Amended" note above — `ParkedFlightState`/`apw` still have no
construction sites to grep against as of this plan revision; the Implementer's grep still applies
once Stage P1 lands the type.)

**Implementer's grep, Stage P1 landed (2026-11-15):** `grep -rn "ParkedFlightState(" body-layer/src
body-layer/tests` finds exactly one production construction site
(`belief/ai_pilot_wheel.py`'s `advance_parked_flight_state`, which only ever `replace()`s via a
fresh `ParkedFlightState(...)` built from the latest feed, same single-construction-site shape
`GuidanceUnitState` already has) plus `body.py`'s own `field(default_factory=ParkedFlightState)` —
nothing else, and nothing in the Co-moving Fields table above is missing a row. **One naming
departure from this table's own wording, stated here because the table uses `apw.mode`/`apw.press`
as if they were literal Lua table fields and they are not**: Stage P1's `Export.lua` implementation
uses individual named module-level locals (`ai_pilot_parked_active`, `ai_pilot_mode_text`,
`ai_wheel_pending_cmd`, etc.), not a single Lua table named `apw` — there is no `apw.` assignment
anywhere in `Export.lua` to grep for. The wire-level JSON keys *are* `apw_`-prefixed
(`apw_parked_active`, `apw_mode_text`, …, matching this table's intent), and the table's own rows
read correctly if `apw.mode` is read as "the AI-pilot-wheel mode state" rather than a literal field
access. P2-P4 should keep using individual locals for the same reason P1 did: Lua has no hoisting,
and a single `apw` table assembled before every field exists would invite exactly the
declared-below-its-use bug this project's own `push_ptt_state` incident already demonstrated.

### Behaviour constants

| Constant | Default | Where | Why |
|---|---|---|---|
| `AI_PILOT_RECOVER_AGL_FLOOR_M` | 40 (Q5) | body-layer `tuning.py` | crash-avoidance floor, named in the goal check as `U1`-adjacent but the number itself is already the user's own default |
| `AI_PILOT_RECOVER_IAS_CEILING_KMH` | 280 (Q5) | body-layer `tuning.py` | over-speed avoidance ceiling, same source |
| `AI_PILOT_ALTITUDE_TOLERANCE_M` | 20 (user) | body-layer `tuning.py`, sent in the goal | "good enough" for the hold-up/down nudge loop |
| `AI_PILOT_HEADING_TOLERANCE_DEG` | 5 (same judgement call as mode 1's D-c; **not re-litigated, same default**) | body-layer `tuning.py` | no natural tolerance for a heading |
| `AI_PILOT_SPEED_STEPS_KMH` | `(0, 60, 120, 160, 200, 250)` + a MAX sentinel | body-layer `tuning.py` (sequence) | the wheel's own discrete steps (user, unverified at 160 — Stage P0) |
| `LONG_PRESS_HOLD_S` | 0.7 (margin above the confirmed 0.5 s threshold) | Export.lua constants block | the far-slot/long-press timing; **would want the X-T26 mechanism, noted not improvised, same as the 9K113 servo block** |
| `SHORT_PRESS_PULSE_S` | one or two frames (the existing `handle_petrovich_search_command` pattern) | Export.lua | short-tap timing |
| `MODE_READ_SETTLE_S` | ~1.0 (user's recon §7 estimate, "~1 s AI lag") | Export.lua | how long to wait after a mode-cycle press before trusting the new `mode_text` |
| `MODE_CYCLE_MAX_ATTEMPTS` | 3 (added 2026-11-15) | Export.lua constants block — the loop itself lives there, per the Architecture decision above | the known cycle orders (`FLT⇄CBTM`, `HVR→HVRT→CBTM→HVR`) bound every reachable mode within 2 presses; 3 gives one spare attempt rather than guessing at an open-ended N |
| `BREAK_AWAY_GAP_S` | 2.0 (user, verbatim — added 2026-11-15) | Export.lua constants block | the gap between the two `BREAK LEFT` presses `cbtm_break_away` issues |
| `HVRT_TRANSLATE_MAX_HOLD_S` | 15.0 (architect default, **not** user-specified — flag as a judgement call, revisit if a sortie shows it firing in ordinary use; added 2026-11-15) | Export.lua constants block | safety ceiling on a held HVRT translate press if the spoken "Hold" is lost |

### Implementer notes from the plan checks (2026-11-15)

- **Every new spoken token also goes into `audio-adapter/src/vocabulary.py`'s `TOKENS`/`PHRASES`**,
  the table that biases whisper's prompt — hand-synced, no automated cross-check
  (`audio-adapter/CLAUDE.md`; the 2026-10-23 "violence"/"same ahead" incident is what happens when
  it is missed). Applies to Stages P2, P3 and P4.
- **No shared `press(direction, duration)` entry point in Lua.** Each action hard-codes its own
  fixed press shape (which button, short / long / held). This is what makes E-P6 ("`HDG LOS`,
  short right, is never pressed") structural rather than conventional; with nine action paths a
  generic combinator is one typo from pressing it.
- **Q-P2 open, non-blocking:** `HVRT_TRANSLATE_MAX_HOLD_S` = 15 s is the architect's default, a
  tunable; the user has not confirmed the order of magnitude.

### Stage P-ICS — ICS capture from the operator seat (prerequisite)

Precedes P0; gates every parked-mode flight in this series, per the "Amended 2026-11-15" note
above — the pilot speaks from the CPG seat while parked, and today's capture path gates only on
the pilot's own trigger.

**Decision: one combined sample, not a per-seat pair.** `Export.lua`'s `push_ptt_state` (~L662)
currently reads only `ARG_PILOT_PTT = 738` (pilot). Extend it to also read **arg 856**
(`OP-STICK-PTT-PTR`, operator seat, `crew_member_access = {1}`, identical encoding — first-party,
DCS-SRS's own `Mi24P.lua` reads it for the copilot seat too) and send both raw values on the same
line: `{"t":..., "ptt":<pilot raw>, "ptt_op":<operator raw>}`. `schema.ptt.PttSample` gains a
second raw field (`raw_operator: float`); its `intercom`/`radio` properties become an **OR across
both raw values** — the trigger means "the crew channel is open", regardless of which seat
pressed it, which is exactly what the one consumer (`audio-adapter/src/ptt_source.py`'s
`DcsPTT.is_down`) wants and already reads (`payload.get("intercom")`/`"radio"`) with **no change
needed there**. `aircraft-layer/src/api/server.py`'s `_handle_ptt_state` (~L424, the SPU-8 gate)
also needs **no change**: `Spu8Sample.gate_open` (`schema/spu8.py`) already ANDs the pilot's
NET-1 switch (arg 377) with the co-pilot's ICS-power switch (arg 664) regardless of which seat is
talking, so the existing gate is already seat-symmetric.

**Why this over a `seat` field + OR-in-audio-adapter**: tagging each sample `"seat":
"pilot"|"operator"` and having `DcsPTT` fetch/OR two states is a bigger diff — a second cache
slot or a second poll, and a second place (`audio-adapter`) that has to know the OR rule — for no
behavioural gain, since nothing downstream needs to know *which* seat spoke. **The seat is still
useful diagnostics**: add an optional `last_seat: "pilot"|"operator"|"both"|None` field to
`PttSample`/`to_api_dict` (whichever raw value's own predicate fired; `"both"` if both did),
read only by `--debug` logging, never by `DcsPTT` or any gating logic. This keeps "the Lua layer
carries the raw value and decides nothing" true throughout: Lua ships two numbers, the Python
schema layer does the OR — the same layer that already decides `intercom`/`radio` from one
number — and `audio-adapter` is unchanged.

**Affected files**: `aircraft-layer/dcs-export/Export.lua` (`push_ptt_state`, the `ARG_PILOT_PTT`
block — add `ARG_OPERATOR_PTT = 856` beside it, extend the debounce-on-change check to fire on
either value moving); `aircraft-layer/src/schema/ptt.py` (`PttSample`, `from_dict`,
`to_api_dict`). `aircraft-layer/src/collector/server.py`'s `"ptt" in data` line-routing check
(~L403) is unaffected — same wire key, more fields. No change to `audio-adapter/src/
ptt_source.py` or `aircraft-layer/src/api/server.py`'s `_handle_ptt_state`.

**Tests**: `PttSample.from_dict` with only `ptt_op` moved (pilot untouched), both moved on the
same frame, and the `intercom`/`radio` OR truth table (neither / pilot-only / operator-only /
both); Export.lua's debounce-on-either-change, desk-checkable the same way `push_ptt_state`'s
existing logic already is (`aircraft-layer/CLAUDE.md`'s Export.lua testing note — no live DCS
needed for parse/encode, only the live check below).

**Flight P-ICS** (test card, named branch): from the **operator seat**, hold the ICS trigger to
its intercom stop (not the pilot's), confirm `GET /ptt/state`'s `"intercom"` goes true and
capture starts — the same observable behaviour the pilot's own trigger already produces. Release,
confirm it drops. Then repeat from the pilot seat, to confirm nothing regressed.

### Stage P0 — measure (desk pass already done; one short Windows probe)

No new Windows session needed beyond what the user already flew and screenshotted
(2026-11-01/11-14); this stage closes the handful of items the existing recon flags
`[inference]`/unverified, with a single short flight. Probe script:
`aircraft-layer/dcs-export/Export.probe-ai-pilot-wheel.lua`, same scaffold as
`Export.probe-9k113-flicker.lua`/the search-wheel handler, parked, operator seat, ED's AI flying.

| # | Measures | Pass | Decides |
|---|---|---|---|
| P0-1 | `list_indication(HELPERAI_DEVICE_ID)` content while parked, command (right) wheel **closed** vs **open** | populated either way, or only with the command wheel open | whether Export.lua must open the command wheel to read the texts. **Narrowed 2026-11-15 by the user:** the readback (left) overlay *"is always visible. There is no way to turn it off"* while the AI flies, so there is no cosmetic HUD cost either way; only the command wheel is normally off |
| P0-2 | One held press at 0.7 s on each ring position in FLT, confirmed against the overlay readback moving as a long action (not a repeated short tap) | 0.7 s reliably reads as long in this wheel too | `LONG_PRESS_HOLD_S` final value |
| P0-3 | Speed tap sequence from 0 to MAX, reading `speed_text` after each tap | the exact step list and MAX's displayed value | `AI_PILOT_SPEED_STEPS_KMH` |
| P0-4 | Press-to-readback latency: time from a press release to the overlay text changing | a number, used as `MODE_READ_SETTLE_S`'s floor | the read-compare-repeat loop's minimum wait before re-checking |
| P0-5 | Centre press (baro/radar toggle) from each reference, confirm readback flips and re-reading/re-setting altitude after is actually required (or the AI keeps the same numeric target across the toggle) | documented | whether the centre-press step in a reference change is needed at all |
| P0-6 | On park, confirm the sink and the fix: set altitude to current immediately on park, observe whether the AI still sinks first | no sink, or sink stops within a few seconds of the write | confirms E-P1/the user's own write-up as the production behaviour, not an assumption |
| P0-7 | FLT→HVR speed criterion: tap speed down to 0 in FLT, observe when `mode_text` itself flips without a mode-cycle press | a number or a settle time | whether `decide_ai_pilot_wheel` ever needs to *wait* for a DCS-driven mode change rather than press for one |

Go/no-go: nothing here can fail into a blocker — every row either confirms a number already
believed or narrows a mechanism detail (P0-1). If P0-1 fails (texts only filled while the
command wheel is open), Export.lua would have to open the right wheel to read — a visible menu
on the HUD, a **known limitation to state on the test card**, not a redesign. The left readback
overlay is on screen regardless (user, 2026-11-15), so a pass costs nothing cosmetically.

### Stage P1 — the seam and activation, no goals yet

**SUPERSEDED 2026-11-16** — see "Revised 2026-11-16 — takeover after the Batch A flights" below
for the production design. Batch A (built to the letter of this section, DoD-PASSED, merged
`c38740d0`) found two wrong assumptions once flown: the park/pedals-OR detection reads "parked"
whenever the AI is *not* flying (952 is arg 852's mirror, not a second park sensor), and ED's own
barometric target can come out hundreds of metres wrong, which the single "nudge if already equal"
shot never addresses. Kept below verbatim, per `docs/PROCESS.md`'s "Superseding a decision" — the
account of what was built and why it needed revision is itself worth keeping, not just the fix.

Minimal working version: the park signal takes over, holds altitude, does nothing else.

- **Lua**: `run_ai_pilot_wheel(t)` per frame beside `run_sight_servo(t)`. Parses
  `list_indication(HELPERAI_DEVICE_ID)` into `mode_text`/`course_text`/`alt_text`/
  `alt_add_text`/`speed_text`. On the park signal rising (arg 852/952 ≈ 1, the same observable
  mode 1's S0-12 already confirmed — reused, not re-probed), issues one altitude long-hold press
  up by `LONG_PRESS_HOLD_S` if the read current altitude equals the AI's held altitude (the nudge,
  per P0-6/the user's write-up), else holds nothing and leaves the AI's own value as the goal
  until body-layer sends one. `apw` status pushed at 5 Hz: `mode_text` fields, `parked_active`,
  last press issued. **No goal message yet** — this stage proves activation and the park-sink fix
  only, Decision-free otherwise.
- **Body-layer**: `ParkedFlightState`, advanced from the park-signal state param each poll (no
  voice token yet — activation is automatic, E-P1); no spoken line (E-P2 withdrawn).
- **Tests**: Lua parse function against the overlay's known text shapes (`R`/`B` suffix, mode
  names); park-rising detection; altitude-nudge-if-equal logic as a pure function.
- **Flight P1** (test card, named branch): park with the AI holding some altitude, confirm no
  sink and no speech. Unpark, confirm nothing untoward (no goal exists yet to drop).

### Stage P2 — heading, altitude, speed goals

- **Lua**: the nudge loop — given a goal (one of heading/altitude/speed), read current mode, cycle
  to FLT/HVR if needed (short-left, re-read, repeat — bounded by `MODE_READ_SETTLE_S` per attempt
  and `MODE_CYCLE_MAX_ATTEMPTS` (3) attempts overall, now a known quantity rather than an open
  engineering default, per the "Amended 2026-11-15" note above: the cycle orders are known, and
  every mode is at most 2 presses from any other), then issue the single press the goal needs
  (short tap for speed, long hold for altitude/heading, released once the readback is within
  tolerance or the body-layer goal changes), report `goal_progress: "pressing"|"settled"|
  "mode_blocked"` — `"mode_blocked"` on exhausting the attempt bound leaves the goal outstanding
  for retry next poll, never silently dropped.
- **Body-layer**: `set_parked_heading`/`set_parked_altitude`/`set_parked_speed`; interleaving
  across more than one outstanding goal (one parameter's step per poll, rotating); readback on
  acceptance, mirroring mode 1's Decision 10 shape (*"heading 3 1 5"*, *"speed 2 0 0"* — rounded to
  the nearest step per the explore notes, and the readback **names the step actually set**, per
  E-P3); no "unable" for a goal not quite reached (same posture as mode 1's A4, not re-litigated).
- Audio-adapter: reuse the slot parsers mode 1's plan already designed for `turn_heading`,
  `hold_altitude`, `speed` (Affected Modules, mode-1 series below) — **built here, first**, so
  mode 1's own Stage 4 does not redo this work; cross-reference added to that stage when mode 1 is
  picked up. New slot parsers needed for the full vocabulary table above: compass-point→degrees
  (`turn_heading`'s second form), `turn_heading_relative`, `speed_step`, `altitude_step`.
- **HVRT (hover translate) vocabulary — held press and the safety timeout.** "left"/"right"/
  "forward"/"back" (bare direction, state-gated to `ai_mode == "HVRT"`, per the vocabulary note
  above) set `held_translate_direction` to that direction; "Hold" clears it. **Lua holds the
  actual press** — the Architecture decision above already gives Export.lua ownership of
  press/hold timing, unchanged here — reading `held_translate_direction` each frame and keeping
  the matching outer-ring press open for as long as it is non-`None`, releasing the instant
  body-layer clears it (on "Hold") **or** `HVRT_TRANSLATE_MAX_HOLD_S` elapses, whichever comes
  first. The timeout is a safety ceiling, not the normal stop path — the normal stop is always the
  player's own "Hold" — but it exists because that stop is spoken and can be lost (a network drop
  between audio-adapter and body-layer, a missed recognition), while an open wheel press cannot
  discover that on its own. Lua reports `goal_progress: "released_timeout"` when it fires, so the
  test card has something concrete to look for. "up/down" (`hvrt_step`) is a discrete short press,
  2 m per tap, no hold semantics at all — unaffected by the timeout.
- **Flight P2**: park, speak a heading, then a speed, then an altitude in quick succession
  (interleaving); confirm the overlay converges on all three without one blocking another, within
  the tolerances, and the mode cycles correctly between FLT (speed/altitude/heading) with no
  player-visible stall. Then, from hover, cycle into HVRT and say "left", hold a few seconds, say
  "Hold"; confirm the AI translates only while held and stops on the spoken word, and separately
  confirm the AI eventually stops on its own if "Hold" is never said (the timeout, not flown to
  full duration — confirm the mechanism exists via `goal_progress`, not by waiting out 15 s live).

### Stage P3 — alignment and break turns on the player's word (E-P7)

- **Body-layer**: `cbtm_align`/`cbtm_align_for_launch`, each refusing (no "unable" — see **U2**)
  outside the states where CBTM is reachable; snapshotting `pre_align_snapshot` on
  `cbtm_align_for_launch`. Same refusal posture for `cbtm_break`/`cbtm_break_away` — outside
  CBTM-reachable state, the mode-cycle-then-press sequence is expected to succeed, per U1/U2.
- **Lua**: mode-cycle to CBTM, short-up (`cbtm_align`) or long-press-up (`cbtm_align_for_launch`,
  held for `LONG_PRESS_HOLD_S` then released — a discrete action, not an open hold); long press
  left/right, no hold (`cbtm_break`); long press left, wait `BREAK_AWAY_GAP_S`, long press left
  again (`cbtm_break_away` — never the single `BREAK 180` press, direction undetermined per the
  wheel research).
- **Flight P3**: from the operator seat, say "align" then "align for launch"; confirm the AI
  boresights toward the target as the explore notes describe, and that no automatic recovery fires
  yet (that is P4). Then say "break turn left", "break turn right", and "break away"; confirm the
  90° and the two-press 180 against the compass, and that nothing happens if the aircraft was not
  already in or reachable from CBTM.

### Stage P4 — recovery (E-P8, E-P9, F-P1, F-P2)

- **Body-layer**: `decide_ai_pilot_wheel`'s recovery branch — launch detection (payload count
  drop, see "Launch detection" above), spoken abort (the `level_off` token — "straight"/"level
  off" — while `align_phase` is `"aligning"`/`"launch_aligned"`, per the vocabulary table above;
  the same token stops an ordinary turn and holds current heading when no alignment is in
  progress, so the dispatcher's own `align_phase` check is what decides which meaning fires), AGL
  floor, IAS ceiling; `recover_to_level`; *"leveling off"*; the post-recovery goal sequencing
  (Q7/Q8) from the Co-moving Fields table.
- **Lua**: mode-cycle CBTM → FLT on a recovery signal from body-layer (no new Lua mechanism — this
  is the same goal/mode-cycle machinery P2 built, just triggered by a different caller).
- **Flight P4**: align for launch at a safe height, let it run past 40 m AGL without firing —
  confirm the automatic pull-out and the spoken line (F-P1); then a launch at a safe height — confirm
  the post-launch level-off and the smooth altitude/speed restoration (F-P2, Q7, Q8), with the sight
  (worked by the player, untouched by Petrovich) tracking the target throughout.

### Stage P5 — terrain reference (Q6) and seat/scope boundaries

**Note added 2026-11-16**: the revised Stage P1 (below) already puts the AI onto baro at
takeover, as part of the park-sink/wrong-target fix — not a separate decision taken here. This
stage's own job narrows to *confirming* that choice on the test card against what the player
actually observes over rising terrain, not implementing the toggle; the bullet below is kept as
the record of why baro was chosen.

- Default `ALT REF` to **baro** for the smoother hold (Q6 — radar is jerky), terrain avoidance
  along the flight path explicitly deferred to the player's own judgement and to `[[BL-B101]]`
  later, stated on the test card as a known limitation, not a silent gap.
- Confirm `write_sight_target` is never called while `parked_active` (F-P3 — Petrovich never
  touches the sight the player is working); confirm naked-eye calls continue unmodified (E-P11).
- **Flight P5**: fly a sortie over rising terrain with baro hold active; confirm the card's stated
  limitation matches what the player actually observes (no silent terrain-avoidance claim).

### Stage P6 — tune and accept

Flight-to-flight retunes of `LONG_PRESS_HOLD_S`/`MODE_READ_SETTLE_S`/the tolerances. Acceptance
against E-P1, E-P3–E-P11 (E-P2 withdrawn) and Q1–Q8, written into `docs/acceptance/`.

### E-P traceability

| Expectation | Closed by |
|---|---|
| (prerequisite, not an E-P row) | Stage P-ICS — gates every parked-mode flight below; without it, the player's spoken goals from the CPG seat never reach Petrovich at all |
| E-P1 (park is the handover, holds current state) | Stage P1 |
| E-P3 (spoken goals, honest readback, interleaved) | Stage P2 |
| E-P4 (latest wins) | Stage P2 |
| E-P5 (never undoes the player) | **Narrowed by the user, 2026-11-15, ALIGNED** (`alignment.md`, Plan check Q-P1): the player is not expected to operate the wheel while parked mode runs; if he does, Petrovich's goal wins and reasserts at once (**U3**, answered) |
| E-P6 (`HDG LOS` never pressed) | Stage P1 — short-right is never in the press vocabulary at all, not merely unused |
| E-P7 (alignment only on the player's word) | Stage P3 |
| E-P8 (level off and guidable after launch) | Stage P4 |
| E-P9 (never flies into the ground because of a Petrovich-chosen mode) | Stage P4 |
| E-P10 (unpark gives it back at once, nothing resumes) | Stage P1 |
| E-P11 (naked-eye crew work continues) | Stage P5 (explicit check; nothing in this series touches `optic_policy`) |

### Risks & Unknowns (mode 2)

- **list_indication(6) is shared with Petrovich's own sensor overlay** (the feed this project
  already streams for the `middle_list_text` target list). Nothing in this plan changes what that
  feed means when Petrovich is *not* flying the AI pilot — the two contents never coexist, since
  the park signal and HELPER_AI's own role are the same underlying state — but the parser added in
  Stage P1 must not be read as a second meaning for an existing field; it is a **new** flattening
  on the same raw dump, gated on `parked_active`.
- **Press-and-release timing drift.** `LONG_PRESS_HOLD_S` at 0.7 s is a margin over a measured
  0.5 s threshold in a *different* wheel context (Petrovich's sensor wheel, not the AI pilot
  wheel). P0-2 exists because the threshold is a DLL constant shared across wheels per the recon,
  but has not been directly confirmed on this wheel.
- ~~Mode-cycle order is unknown beyond the pairs the user named~~ **Resolved 2026-11-15**: the
  full short-left cycle orders are now known (`FLT⇄CBTM`, `HVR→HVRT→CBTM→HVR`, Amended note
  above), so `MODE_CYCLE_MAX_ATTEMPTS = 3` is a bound derived from the known graph, not a guess.
  The CPG-view-exit transition (CBTM→FLT/HVR) stays unconfirmed by the user's own account
  ("probably though I'm not sure") — unchanged risk, covered without a design change by "read the
  mode every tick, never assume."
- **The player is assumed not to change wheel modes himself** (Q4). **U3 is answered, 2026-11-15**:
  if he does, Petrovich's cycle-back reasserts at once rather than deferring — the cycle-back
  could visibly fight a mode the player just picked, and the user has accepted that for the first
  build (*"the goal is to use the wheel command via Petrobrain, not player directly"*).
- **`HVRT_TRANSLATE_MAX_HOLD_S`'s default (15 s) is the architect's own judgement call, not a
  user-specified figure** — added 2026-11-15, flagged here rather than silently treated as settled.
- **The ICS-capture OR-of-two-raw-values design (Stage P-ICS) changes `/ptt/state`'s meaning for
  every existing consumer**, not just this plan's own: `"intercom"`/`"radio"` now mean "either
  seat", where before they meant "the pilot." No other current consumer is seat-specific (checked:
  `audio-adapter`'s `DcsPTT` is the only reader), so this is believed safe, but it is a semantic
  widening of an existing field, not an additive one.
- **Recovery while a goal is also in flight.** If the player sets a new heading moments before a
  launch, the Co-moving Fields table's rule (alignment overrides, goal resumes only after
  `"none"`) could feel like a dropped command. Acceptable per the goal check's own reading, but
  worth naming on the test card.

### Second-order effect (mode 2)

Confirms the goal/vocabulary shape (heading/altitude/speed, one at a time, clamped and
interleaved) a mission-day pilot already has to learn once; mode 1 inherits the same vocabulary
rather than teaching a second one, and `[[BL-B95]]`'s eventual action catalogue gains its first
two "flying" actions a release early. Also answers, in passing, whether `list_indication(6)`'s
overlay channel needs forcing open (P0-1) — a fact mode 1 never needed and now has for free.

### Decisions Requiring User Input (mode 2)

- **U1 — `cbtm_align`/`cbtm_align_for_launch` outside CBTM-reachable state: silent no-op, or a
  spoken refusal?** The alignment.md goal check left this open implicitly (E-P7 only says who may
  trigger it). **Recommend:** a spoken "unable, not ready" only if the mode-cycle to CBTM itself
  fails to resolve within the attempt bound (Stage P2's `mode_blocked`) — otherwise silent, since
  the cycle-to-CBTM-then-press sequence is expected to succeed in ordinary flight and a refusal
  for an ordinary in-progress cycle would be noise.
- **U2 — same question, restated for scope**: should a refusal ever interrupt an in-progress
  alignment attempt mid-cycle, or only report failure after the attempt bound is exhausted?
  **Recommend:** only after exhaustion — matches mode 1's A4 posture ("fly within parameters,"
  no mid-attempt narration).
- **U3 — the player changing the AI wheel's mode himself.** Q4's answer assumes this does not
  happen; if it does, should Petrovich's cycle-back defer to the player's choice for some window
  before reasserting the mode his goal needs (closer to E-P5's spirit), or always reassert at
  once (simpler, matches the literal Q4 answer but risks fighting the player)?

  **Answered 2026-11-15 (user, verbatim):** *"reassert at once — the goal is to use the wheel
  command via Petrobrain, not player directly."* Always-reassert stands as the production
  behaviour; E-P5 is narrowed accordingly (see the E-P traceability table's E-P5 row and
  `alignment.md`'s Plan check Q-P1). No longer open.

## Revised 2026-11-16 — takeover after the Batch A flights

Batch A (Stage P-ICS/P0/P1 above) was DoD-PASSED and merged (`c38740d0`) on the strength of
fixtures and code reads — the acceptance boundary in `dod-batch-a.md` said plainly that the live
behaviour was still unverified. Two flights the same day found it wrong in two independent ways.
Source for everything below: `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md` (read in full);
quotes are the pilot's own. This revision replaces **Stage P1 only**; P-ICS is unaffected (passed
as built) and P0's own measurement rows are all now answered (see "Stage P0 — status" below).

### Why Stage P1 needed to change

1. **The detection never saw the handover.** The AI takes over on the operator-seat binding
   "Request Aircraft Control" (category "Petrovich AI Helper, Multicrew"); "Copilot Stick -
   PARK/UNPARK" — the control the original Stage P1 was named after and built to watch — does
   nothing at all (pilot, verbatim). Production's `852 OR 952 ≥ 0.9` compounds this: **952 is not
   a second park sensor, it is arg 852's exact mirror** (measured: 852 + 952 = 1.00 at every
   sample through the handover animation, settling at 852 = 1 / 952 = 0). So the OR term reads
   "parked" whenever the AI is simply *not* flying, which is the wrong state to call "parked" and
   is never the rising edge the nudge needs. **852 alone is the handover signal.**
2. **The fix the old design shipped (a one-shot nudge, armed only if the held and actual altitude
   already agreed) never had anywhere to apply itself**, because the trigger it waited on never
   fired. Separately, even where the trigger *does* fire, ED's AI carries two bugs the old design
   did not anticipate: the starting altitude is shown on the overlay but never reaches the AI's own
   logic (the sink), and the barometric target the pilot's own fix lands on can come out hundreds
   of metres wrong — measured **1658 m target against 921 m actual MSL**, so the AI climbed for
   17 s at up to 11 m/s after the sink had already been stopped. A fixed-duration "nudge" cannot
   correct an error of that size; it needs a closed loop that watches the readback and keeps
   correcting until it converges.
3. **The readback is only in `list_indication(6)` with the command (right) wheel open** — measured
   directly (P0-1): every overlay field reads `nil` closed, and is populated after one `ShowMenu`
   toggle. The always-visible compass overlay the pilot described (research note §3) is a
   different, HUD-only surface; the *text feed* Export.lua reads is gated on the command wheel.
   Stage P1 cannot read or correct anything without opening it, and the pilot has since accepted
   keeping it open permanently (next section) — this was not yet decided when Batch A's Stage P1
   was built.

### Settled, carried forward from the input documents (not re-litigated here)

- **The command menu stays open for as long as the AI flies.** Petrovich opens it on takeover and
  reopens it at once if the player closes it — accepted by the pilot as a cosmetic tradeoff. This
  makes `list_indication(6)` readable continuously from shortly after takeover onward.
- **Barometric is the reference**, chosen once and not re-derived here (Q6 already called it
  smoother; the pilot's own fix lands on it too). The blind assumption "the AI always starts on
  radar" is carried over from the pilot's own reasoning (*"Single press assumes the AI always
  starts on radar, as the pilot saw"* — already in the feedback doc's "What this settles," not a
  new claim introduced by this revision) — every measured sample so far agrees; flagged as a
  residual risk below, not re-opened as a question.
- **Correcting a wrong target is a closed loop**: hold up/down, read the overlay, release at
  target — the same shape Stage P2's own "release when readback reaches target" already planned,
  pulled forward into Stage P1 because the correction is needed on *every* takeover, not an
  optional extra.

### Revised Stage P1 — takeover and stabilisation

Minimal working version, replacing the old one: on the park signal, Petrovich gets the AI onto a
*correct* barometric altitude target before anything else happens, by watching the readback rather
than assuming a single press is enough.

**Sequence, in order — all of it time- or condition-driven from Export.lua alone, no body-layer
goal channel needed** (consistent with, not revising, the Architecture decision above: the
correction target is derived from `LoGetAltitudeAboveSeaLevel()` locally, nothing body-layer would
need to send):

1. **Detect takeover on arg 852 alone**, rising past `AI_PILOT_PARK_THRESHOLD` (0.9, unchanged).
   Arg 952 is no longer read for detection — kept only as a diagnostic value on the status push
   (see "Behaviour constants" below), so a future discrepancy is debuggable from the wire rather
   than inferred after the fact.
2. **Wait `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` (0.5 s, the pilot's own figure — *"I'd put a half
   second delay there"*), then press centre once, menu closed.** This is the one reliable way to
   toggle radar → barometric (P0-6's re-fly measured it working closed; P0-5 measured the *same*
   press failing while the menu was open). Issued blind — Export.lua cannot read anything before
   the menu has been opened at least once (point 3), so there is nothing to check first, and the
   toggle+adopt-current-value behaviour is what stops the sink regardless of whether it reads back
   confirmed.
3. **Open the command menu** (one `WHEEL_MENU_BUTTON` press — Export.lua's own existing name for
   command id 3001, the probe's `WHEEL_SHOW_MENU`) and leave it open. From here on, every 5 Hz
   tick: if the overlay reads every field `nil` for longer than `MODE_READ_SETTLE_S` (1.0 s,
   reused — not a new constant), conclude the player closed it and press `WHEEL_MENU_BUTTON` again.
   The settle window exists because the toggle is a single press that *closes* an open menu just
   as readily as it opens a closed one — reacting to one stale-looking tick would flap it shut
   again.
4. **Snapshot the correction target once**: after the first post-open read, take the AI's held
   altitude (`alt_text`) and the aircraft's own current altitude in whichever reference the
   overlay now shows (`alt_add_text`, same `ai_pilot_actual_altitude_m`-shaped lookup as before).
   If they already agree within `AI_PILOT_ALT_TOLERANCE_M`, do nothing further. If not, open a
   held press — **down** if the held target is above the snapshot, **up** if below (the AI climbs
   toward a high target, so lowering the target is what stops the climb) — and keep it open,
   re-reading every 5 Hz tick, releasing the instant the readback crosses the snapshot within
   tolerance, or at `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` (a safety ceiling, not an expected
   outcome — see Risks). This **replaces** the old one-shot nudge (`ai_pilot_pending_nudge`/
   `ai_pilot_should_nudge_altitude`/`ai_pilot_press_altitude_up_long_hold`) outright, not beside
   it: the old equality check is exactly this loop's own "already within tolerance, do nothing"
   case, generalised to handle an arbitrarily large error in either direction.
5. **On unpark** (852 falls below threshold): release any open press immediately (unchanged from
   before), drop every takeover-sequence field, and **close the command menu** if Petrovich opened
   it — symmetric with opening it, so the player gets back the view they had before parking. This
   is a local, reversible choice (Escalation Rules), decided here rather than escalated: nothing in
   the input documents says the player minds either way, and leaving it open would be the more
   surprising default.

**The snapshot, not a continuously-re-read target, is what the loop corrects toward** — matching
E-P1's "holds what it was doing," and avoiding a moving-target loop if the aircraft is itself still
settling from whatever it was doing at the moment of takeover.

**No shared `press(direction, duration)` entry point** — unchanged posture from the Implementer
notes above. The correction loop is its own dedicated up/down pair, never a parameterised
combinator, for the same E-P6 reason.

#### Amended 2026-11-16 — after the takeover rehearsal probe (main loop, pilot's answers)

Source: `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`, sections "Takeover rehearsal probe"
and "Explore, round 3". **This amends points 2 and 4 above; where they disagree, this wins.**

- **The correction goal is the handover altitude** (pilot, Q1: *"handolver alt"*): actual MSL
  **at the moment arg 852 crosses the threshold** (point 1), not at the first post-open read.
  Snapshot it in the same frame as detection.
- **Point 4 becomes two phases, per the pilot's own workaround** (*"hold down until current
  altitude at that moment is reached. That sends the value to DCS AI and stops the climb. Then
  continue adjusting the altitude value to what it was at handover moment"*):
  1. **Stop the drift:** hold toward the aircraft's *current* MSL, re-read live every tick, and
     release within `AI_PILOT_ALT_TOLERANCE_M` of it. *Inferred from the probe and the pilot's
     words: the AI applies a held value only on release* — during the probe's single 14 s hold
     the aircraft kept climbing 920 → 1050 m toward the old target. One continuous hold straight to
     the handover altitude would let it keep climbing the whole time.
  2. **Return to handover:** then hold toward the handover snapshot, release within tolerance.
  Skip phase 1 when the target already reads within tolerance of current MSL, and skip both
  when it is within tolerance of the handover altitude.
- **Quick path, tried first when it can work** (pilot, Q2: *"If AGL is < 700m, yes do that to
  fix it"*): centre pulse (barometric → radar), read; if the reference now reads `R`, centre pulse
  again (radar → barometric) and read. In the probe a second barometric switch gave a correct
  target (1080 against 1084). **The radar reference is capped at 700 m AGL** (pilot): a target
  above that forces barometric, so the first pulse is refused. *The wild target measured +740 m
  above handover twice, which is above 700 m AGL at any height,* so the read decides, not a
  precondition: **if the reference still reads `B` after the first pulse, fall back to the
  two-phase hold.** Attempt the quick path only when the aircraft's own AGL is below 700 m.
- **Centre presses with the menu open use a real pulse, `SHORT_PULSE_S` 0.15 s,** not a same-frame
  press/release. Measured: the 0.15 s pulse toggled B → R with the menu open. **This corrects
  point 2's premise and P0-5's reading**: the open-menu failure was our zero-length press, not ED.
  Point 2's first press stays blind and menu-closed (it works, and nothing is readable yet).
- **Held-press profile, measured both ways:** nothing for the first 0.5 s, about 16 m/s until about
  2.5 s, then about 50 m/s; the value moves about one more step after release. A 742 m error closed
  in 14 s. `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` 60 s is comfortably above that, so it stays a
  safety ceiling and the "minutes if linear" risk below is retired.
- **Keep-open, measured:** a hand-closed menu reads closed for 3 frames and reads open again about
  17 ms after the toggle. Point 3's 1 s settle window is generous; keep it, it costs nothing visible.
- **Expected transient, accepted by the pilot 2026-11-16** (*"BL-16 the workaround as planned is
  acceptable. Go ahead with the plan."*), after plan-aligner's CONCERNS (`alignment.md`, "Plan
  check — 2026-11-16"): when the wild barometric target appears, the fallback hold lets the AI climb
  about 130 m before phase 1 stops it (probe: 920 → 1050 m), then phase 2 brings it back to the
  handover altitude. This is the normal cost of the workaround, not a regression, and the usual
  path, since the wild target is above the 700 m radar cap. Keep the start of phase 1 as early as
  the sequence allows; that is the only lever.
- **The status push says which correction path ran** (`quick` / `hold` / `none`), and the Flight P1
  card asks the pilot to note it, so a flight where the quick path happened to work is not read as
  the normal case.

**Flight P1 (revised), test card, named branch**: from the operator seat, hand over with "Request
Aircraft Control" (name the binding on the card — the original card's generic "park" wording is
what produced Batch A's own confusion). Confirm: no sink; the command menu opens on its own within
a second or two; closing it manually causes it to reopen within about a second; the held
altitude converges to the actual altitude at takeover (watch `apw_alt_text`/`apw_last_press` —
note how long convergence actually takes, since the rate is unmeasured, below); `apw_arg852`/
`apw_arg952` behave as measured (852 alone crosses 0.9, 952 is its mirror). Unpark: confirm the
menu closes, any open press releases immediately, and nothing resumes on the next park (E-P10,
unchanged).

### Co-moving Fields (Stage P1 revision)

Trigger fires: a takeover sub-sequence with more than one field tracking "where in the sequence
are we," written both externally (the park signal, the player closing the menu) and internally
(the sequence's own advance, the correction loop's convergence). These are Export.lua module-level
locals, not a table — same naming convention as the existing table above (`apw.foo` read as "the
AI-pilot-wheel's `foo` state," not a literal Lua field).

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `apw.parked_active` | external (arg 852 only, now) | rising edge | `apw.takeover_stage = "toggling_reference"`; `apw.takeover_t = t` (for the 0.5 s delay) |
| `apw.parked_active` | external | falling edge (unpark) | any open press released same frame; `apw.takeover_stage = nil`; correction target cleared; menu closed if `apw.menu_open` |
| `apw.takeover_stage` | internal | `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` elapsed | centre pressed (menu closed); stage → `"opening_menu"` |
| `apw.takeover_stage` | internal | menu-open press issued | stage → `"correcting_altitude"`; `apw.menu_open = true` |
| `apw.takeover_stage` | internal | first post-open read lands | correction target snapshotted (or skipped if already within tolerance); stage → `"correcting_altitude"` (holding) or `nil` (nothing to correct) |
| `apw.takeover_stage` | internal | correction converges, or `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` elapses | open press released; stage → `nil` |
| `apw.menu_open` | internal | belief disagrees with a `nil`-everywhere read for > `MODE_READ_SETTLE_S` | `WHEEL_MENU_BUTTON` pressed again; belief flips to match what is about to be true, not re-read before trusting it |
| `apw.altitude_correction_{cmd,target_m,deadline_t}` | internal | opened (point 4 above) | held press open in the resolved direction; cleared on convergence, on `apw.parked_active` going false, or on deadline |
| `apw.correction_path` | internal | first post-open read lands, already within tolerance | `"none"`; `apw.takeover_stage = nil` |
| `apw.correction_path` | internal | first post-open read lands, correction needed, AGL below `AI_PILOT_QUICK_PATH_MAX_AGL_M` | `"quick"`; `apw.correction_substage = "quick_read1"`; `SHORT_PULSE_S` centre pulse issued |
| `apw.correction_path` | internal | first post-open read lands, correction needed, AGL at/above the cap (or AGL unreadable) | `"hold"`; two-phase hold begins |
| `apw.correction_substage` | internal | `quick_read1`: reference now reads `"R"` | `apw.correction_substage = "quick_read2"`; second `SHORT_PULSE_S` pulse issued |
| `apw.correction_substage` | internal | `quick_read1`: reference still reads `"B"` (switch refused) | `apw.correction_substage = nil`; `apw.correction_path = "hold"`; falls into the two-phase hold |
| `apw.correction_substage` | internal | `quick_read2` resolves, held altitude now within tolerance of the handover snapshot | `apw.correction_substage = nil`; `apw.takeover_stage = nil` (`apw.correction_path` stays `"quick"`) |
| `apw.correction_substage` | internal | `quick_read2` resolves, held altitude still outside tolerance (review fix, 2026-11-16 — the first toggle's own measured error is not known to be absent on the second) | `apw.correction_substage = nil`; `apw.correction_path = "hold"`; falls into the two-phase hold, same shape as `quick_read1`'s own refusal |
| `apw.correction_path`/`apw.correction_substage` | external | falling edge (unpark) | both cleared to `nil`, alongside `apw.takeover_stage` above |
| `apw.correction_path` | external | rising edge (takeover, arg 852) | cleared to `nil` alongside the handover snapshot and `apw.takeover_stage = "toggling_reference"` (`Export.lua`'s `if rising then` block; added after the re-review found this write site missing from the table, 2026-11-16) |

**Implementer's grep, once this stage lands:** `grep -n "takeover_stage\s*=" aircraft-layer/dcs-export/Export.lua` and the same for every other field above — confirm every write site matches a row here, and extend the table with any that does not (the existing table's own note on this: `BL-B71`'s fourth construction site, found only by grep).

**Re-run, 2026-11-16 (review fix round):** `grep -n "correction_substage\s*=\|correction_path\s*="
aircraft-layer/dcs-export/Export.lua` — ten write sites (two table-literal initialisers at
`Export.lua:2140-2141`, eight assignments), all now accounted for by the rows above, including the
new `quick_read2`-still-wrong site this round added. No field above this point is missing a row.

### Stage P0 — status (all seven rows answered)

Every row in the original table above now has a measured answer, from the fixed probe
(`fix/bl16-p0-probe-menu-open`, `aebcfd79`) flown 2026-11-16 — full log in the feedback doc. The
table's own "Measures"/"Decides" columns stay accurate as written; results:

- **P0-1**: readback only with the menu open, confirmed; toggling is repeatable. Decides
  `LONG_PRESS_HOLD_S`'s margin is adequate (unchanged) and that Export.lua must keep the menu open
  — now production behaviour, point 3 above.
- **P0-2**: 0.7 s reliably reads as long (altitude ±4 m, course ±2° per hold). **Open gap, not
  closed by this row**: that is the rate for one 0.7 s hold, not for the multi-second holds the
  correction loop (point 4) will actually issue against a 740 m error — see Risks.
- **P0-3**: speed steps 120→150→200→250→MAX measured (this flight started at 120, not 0 or 60 —
  the full low end of `AI_PILOT_SPEED_STEPS_KMH` is still unmeasured, a Stage P2 note, not this
  one).
- **P0-4**: release → readback change in ~0.007 s (next frame) — well inside `MODE_READ_SETTLE_S`.
- **P0-5**: centre press does **not** toggle the reference with the menu open (two presses, no
  flip); it does with the menu closed. This is why the sequence above toggles before opening, not
  after — see the P2 vocabulary table's own flagged row for the downstream consequence.
- **P0-6**: the pilot's fix (centre press, menu closed, 0.5 s after takeover) stops the sink, but
  the barometric target it lands on can be hundreds of metres wrong — the finding this whole
  revision is built around.
- **P0-7**: not a real limit — the AI was climbing to the wrong target and only slowed once it
  (eventually) got there; FLT → HVR at speed 0 works normally.

### The P1 telemetry mystery — resolved by construction, pending re-observation

Production's own `apw_parked_active` read `false` continuously while the AI was demonstrably
flying (`t: 12.397`, overlay visible, AI in control) — unexplained in the feedback doc, and the
probe's own abort check (reading 852 every frame) ruled out a momentary drop in 852 itself. The
one concrete, confirmed defect in the old detection — reading 952 as a second park sensor when it
is actually 852's inverted mirror — removes the only failure mode anyone has been able to name:
the OR term made "parked" read true whenever the AI was simply *not* flying (952 high, 852 low,
i.e. *before* any takeover) and produced a brief false-negative gap mid-handover-animation while
both args crossed 0.9 in opposite directions. Dropping 952 from detection removes both of those.
**This does not fully account for the one observed sample** — by the time of that `curl`, the
takeover animation had long finished and 852 should have read parked under the old logic too.
Decided here rather than escalated to Debugger now: **treat this as resolved by construction**,
re-observe on the next Flight P1 (which now also pushes raw 852/952 on the wire, point 1, so a
recurrence is directly diagnosable rather than inferred) — if `apw_parked_active` still disagrees
with an obviously-flying AI after this revision ships, that is the trigger for a Debugger pass,
not an assumption to carry forward unverified a second time.

### Behaviour constants (Stage P1 revision)

| Constant | Default | Where | Why |
|---|---|---|---|
| `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` | 0.5 (pilot, verbatim) | Export.lua constants block | delay from takeover to the blind centre press |
| `AI_PILOT_ALT_TOLERANCE_M` | 20.0 (renamed from `AI_PILOT_NUDGE_EPSILON_M`, same value and still Lua-local-only) | Export.lua constants block | governs both "is the target already correct" and "has the correction converged." Still duplicated against body-layer's `AI_PILOT_ALTITUDE_TOLERANCE_M` — unchanged from `dod-batch-a.md`'s own note, still deferred to Stage P2, which is where a real goal channel first exists to carry one value instead of two |
| `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` | 60.0 (architect default, **not** measured — flagged as a judgement call, same posture as `HVRT_TRANSLATE_MAX_HOLD_S`) | Export.lua constants block | safety ceiling only; the expected stop is always convergence, and the loop has no network dependency to lose (unlike HVRT's spoken "Hold") so this exists purely as a defensive bound, not a normal path |
| `AI_PILOT_PARK_THRESHOLD` | 0.9 (unchanged) | Export.lua constants block | now applied to arg 852 only; 952 dropped from the OR |
| diagnostic: raw `apw_arg852`/`apw_arg952` | — | added to `push_ai_pilot_wheel_state`'s wire fields | so a recurrence of the telemetry mystery is directly visible on the wire, not re-inferred from a probe |

`MODE_READ_SETTLE_S` is reused as-is (already declared for Stage P2/the probe; this revision is
its first production use).

### Downstream effects — what P2–P6 inherit

- **P2**: the mode-cycle loop no longer needs to *open* the menu itself — Stage P1 guarantees it is
  already open by the time any goal is spoken. But the "alt ... radar/barometric" vocabulary row
  (table above, flagged in place) inherits a real open question: every reference toggle after
  takeover would have to press centre with the menu open, which P0-5 measured as not working.
  Needs a probe with a real `SHORT_PRESS_PULSE_S` pulse (not same-frame) before Stage P2 commits to
  that row; until then, "radar" may be unreachable by voice. Not resolved here — P2 is not being
  re-planned by this revision, only flagged for whoever plans it.
  Also: Stage P1's own correction loop (point 4), flown on a known 740 m error, is itself a live
  data point for dod-batch-a.md's existing MONITOR item (whether a 5 Hz tick is fast enough for
  "release on readback-within-tolerance") — Flight P1 answers this before P2 needs to ask it again.
- **P5**: baro-as-default is now implemented by Stage P1, not a separate decision taken at P5 —
  edited in place above. P5's job narrows to confirming the known terrain-avoidance limitation on
  the test card.
- **P6**: gains `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` and `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S`
  to the retune list, alongside the existing `LONG_PRESS_HOLD_S`/`MODE_READ_SETTLE_S`/tolerances.
- **P3, P4**: unaffected — neither depends on the takeover sequence's internals, only on
  `parked_active` and the mode-cycle loop both working, which this revision does not change in
  shape.

### Risks & Unknowns (Stage P1 revision)

- **The correction-loop rate for a multi-second hold is unmeasured.** P0-2 measured ±4 m over one
  0.7 s hold (≈5.7 m/s if linear); correcting a 740 m error at that rate would take over two
  minutes. The pilot's own account (*"press and hold will have it keep incrementing the
  change ... value keeps changing while hold lasts"*) suggests it may accelerate, but this is not
  measured. `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` (60 s) is a judgement call made without that
  measurement — if Flight P1 shows the loop timing out before convergence on an ordinary-sized
  error, that is the signal to raise it or to add the dedicated measurement row this revision
  chose not to build a separate probe for (proportionality — this is a revision of one stage).
- **The P1 telemetry mystery is resolved by construction only for its one named cause** (above) —
  flagged as a real possibility it recurs, not asserted fixed.
- **"The AI always starts on radar" stays an assumption**, not a universal fact — every sample so
  far agrees, but an unconditional blind centre press would wrongly flip a baro-starting AI back to
  radar if that case ever occurs. No case has been observed; not re-opened as a question.
- **The menu-open centre-press failure (P0-5) blocks a real piece of future vocabulary** (P2's
  "radar/barometric" row) — carried forward above, not solved here.
- **Closing the menu on unpark is this revision's own call, not the pilot's explicit word** — low
  stakes, reversible, decided per the Escalation Rules rather than escalated.

### Second-order effect (Stage P1 revision)

Confirms the "watch the readback, don't trust one press" shape generally, before Stage P2 commits
to it for heading/speed too — the 740 m correction is a harder test of the hold-and-poll mechanism
than anything P2's own goals (bounded, user-issued values) would have exercised first, so P2
inherits a mechanism that has already been proven against a worse case than its own.

### Decisions Requiring User Input — unchanged by this revision

No new U-numbers. U1/U2/U3 (above) are untouched: U1/U2 remain unanswered and deferred to Stage
P2/P3; U3 remains answered and governs Stage P2's mode-cycle-back, not built in Stage P1. The
choices this revision makes on its own (blind centre-press ordering, snapshot-vs-live correction
target, the 60 s safety ceiling, closing the menu on unpark) are each local and reversible per the
Escalation Rules and are decided above rather than escalated.

## Series — unparked mode (mode 1): later build, preserved unchanged

Everything from here to the end of this file is the **original 2026-10-26/10-31 Architect pass**,
covering mode 1 (controls not parked, Petrovich writes the raw cyclic/collective/pedal axes).
**Not re-cut by the 2026-11-15 pass above** — its Stage 0–6 numbering, decisions, co-moving
fields, risks and open questions are untouched, and its own S0-P rows (the parked-state probe) are
now a closed, historical record: S0-P2/S0-P2a–c/S0-P3/S0-P5/S0-P6 (the raw-axis parked
hypotheses) are **closed negative** by the 2026-11-01 finding quoted above, and S0-P3b is
**superseded** by the whole of the P0–P6 series above, which is its promoted, fully designed
form. Pick this series up once mode 2 passes DoD, per the user's own ordering.

Desk recon for stage 0: `aircraft-layer/research/2026-10-26-bl16-flight-control-desk-recon.md`
(investigator, this pass). Its findings narrow stage 0; they do not replace it. What it changed
here, all forum- or third-party-sourced and so working assumptions only:

- **Channel letters** (three agreeing forum snippets): **H = yaw, K = roll, T = pitch, B =
  altitude**. "Course mode" is H with `RouteOn`.
- **Altitude hold and speed hold are named modes** in Chuck's Guide (contents only), so "not
  implemented" is less likely than the user's recollection suggested — *how well* they hold is the
  open question. Forum: speed hold reportedly **will not engage below ~150 km/h IAS**; altitude hold
  reportedly needs K/H/T on first.
- **Trimmer vs. attitude hold: two contradictory forum claims** (hold-while-pressed then
  re-reference on release, vs. trim moves only the spring centre). Probe-only.
- **No prior art** for `LoSetCommand` flight-axis override; the one community helicopter-assist
  project **unbinds the physical axes and routes through vJoy** "to avoid double control" — a
  data point for Decision 6, not a recipe.
- **No documented getter returns helicopter control positions**; no cyclic or pedal draw-arg is
  known by number; the five never-called getters have no documented shape. All probe items.

> **Recommend an opus re-run of this role before Stage 2 is built.** The control law is the
> high-risk part of this plan, it is written here against an unmeasured plant, and stage 0's
> numbers will change it. That revision is the moment for the deeper pass, not now.

### Revised 2026-10-31 — what changed and why

Every change below traces to one numbered user answer in `explore-notes.md`, "Goal-check answers
(user, verbatim, 2026-10-31)" (A1–A8, plus the general tolerance rule, cited here as **A9**), or to
the BR-2 note in the dispatch. **No 2026-10-26 decision was deleted**; superseded ones carry a
`REVISED` pointer (`docs/PROCESS.md`, "Superseding a decision").

| # | User answer (short) | What changed in this plan | Where |
|---|---|---|---|
| A1 | *"level [off\|flight]", "stop turn", "[fly] straight"* | New action `level_out` and its tokens join the **first** vocabulary (Stage 4, moved forward to Stage 2's flight as well, since a takeover mid-turn needs it). Rolls out, holds the heading reached. | Decision 12; Stage 2, Stage 4; audio-adapter |
| A2 | *"heading. Let's say <5 deg bank gets level flight"* | At takeover, \|bank\| < 5° → hold heading; ≥ 5° → continue the turn. 5° is a body-layer tunable, sent in `take`, applied by Lua at the capture frame. | Decision 1 REVISED; Stage 2; constants |
| A3 | *"no confirm. No key at this stage"* | Both handover tokens bypass the confirm band entirely. "I have controls" acts on any match while he flies, whatever STT confidence. The old risk mitigation ("act band only, never confirm band") is **reversed**. | Decision 13; Risks; `voice_commands.py`, `crew_console.py` |
| A4 | *"no, just fly within parameters"* | No "unable" callout for a goal not reached. Spoken goals outside his limits are clamped, not refused; open point on what the readback says (Decision needing user, D-a). | Decision 14; Stage 4 |
| A5 | *"yes"* (naked-eye calls continue) | `flying` stops **optics only** (binoculars, 9K113). Naked-eye scan, contact and threat calls, and "what do you see?" continue. Resolves the old plan's "suppressed / naked-eye decision" ambiguity. | Decision 15; `optic_policy.py` row; Co-moving Fields |
| A6 | *"AGL, unless player commands barometric. DCS radar alt does to see trees, I believe."* | The implicit hold at takeover and every spoken height default to **AGL** (radar, else DCS AGL). Stage 0 S0-6 now measures radar vs. DCS AGL over forest and town. AGL reference is smoothed so a treeline is not a step. | Decisions 1, 9 REVISED; S0-6; Stage 3; Risks |
| A7 | *"switch to copilot seat and use the 9K113, this is a key reason"* | The key use case is now explicit: player in the operator seat on the 9K113 while Petrovich flies. Stage 0's front-seat row (S0-10) was **promoted to a gate**, then absorbed into the parked block S0-P once P1 named the mechanism; a key-case flight is added (Flight 4b). | Decision 16; S0-P, S0-12, S0-13; Stage 4 |
| A8 | *"not … which seat is controlling … but whether AI or human player is controlling"* | Handover state is AI-vs-human, not seat-bound. A seat swap never releases and never takes. Lua has no seat-swap release path. Seat detection is built only if stage 0 shows the write path differs by seat. | Decision 17; state diagram; Co-moving Fields; S0-12 |
| A9 | *"+-10% variation is allowed, but … goal is to still align with the desired value"* | Per-quantity tolerance bands (tunable). Gains are tuned for smooth convergence into the band; **no test asserts tight tracking**. Stage 2's toy-plant tests and every flight's pass criteria are rewritten around "converges smoothly into the band, stays there, does not ring". | Decision 18; Stage 2, Stage 6; constants |
| BR-2 | dispatch note | Flight vocabulary and handover stay on the deterministic phrase path. The five goal actions are the seam a later brain mapping would call; handover is never brain-callable. No dependency on BR-2. | Decision 19; Second-order effect |
| P1 | *"DCS requires the "park controls" active for player to be able to use the 9K113. That makes DCS AI Petrovich control the aircraft … Petrobrain to overpower the DCS AI flying."* | **The key case's problem is not the player's stick but ED's own AI pilot**, which flies the aircraft whenever controls are parked. Overriding or displacing it is **stage 0's first and gating question** (S0-P). This replaces the earlier reading of A7 ("front-seat stick must be ignored"), which was wrong about the mechanism. | Decision 16 (rewritten); Stage 0 (S0-P block first); Risks |
| P2 | *"So there's two states really. When controls are parked … and when they are not. In both cases Petrobrain must be able to control the aircraft. These may need different solutions."* | Two first-class control states, **parked** and **unparked**, both must-haves. One action interface and one goal message; a **per-state flight effector** behind it in Lua, selected by the park state. A parked-state failure is a **blocker to report**, not a scope cut. Park-state detection becomes required. | Decision 20; Stage 0; the control-loop picture; Stage 1; Co-moving Fields; D-e |

| P3 | *""Petrobrain could steer ED's AI instead of fighting it," -> no. DCS AI flies hoorribly."* | Steering ED's AI (giving it a heading or altitude to fly) is **not an option** in any state. ED-AI commands are probed only as off-switches. With no off-switch and no winning override, the parked state is a blocker. | per-state effector section; S0-P3; go/no-go |

| P4 | *"Probable solution is to somehow overpower the cyclic, rudder and collective control values that DCS AI sets. Very similar to overpowerring the 9K113 sight slewing."* | The lead parked-state hypothesis is the 9K113 override precedent: per-frame axis writes that win. S0-P2 probes it first, with three new rows: does ED's AI fight back or wind up (S0-P2a), is handback in the parked state clean (S0-P2b), is handback to the player clean (S0-P2c). | S0-P2, S0-P2a–c; Risks |

P1–P4 arrived while this revision was being written (`explore-notes.md`, "The key challenge:
parked controls" and "Two control states", both 2026-10-31) and are folded into the same pass; where
an A-row above and a P-row disagree (A7/A8's reading that the front-seat problem was the player's
stick), the P-row wins.

What did **not** change: Stage 0 still comes first; the per-frame Export.lua loop and the
lift-vector-corrections control law; forward flight only (Decision 3); release jump not handled
(Decision 4); ATGM-run refusal (Decision 5 — it concerns *Petrovich's* attack run, not the player
working the 9K113 from the front, see Decision 16); the actions / params / "when" shape; constants
through the tuning pattern.

### Amended 2026-10-31 (plan check)

`plans/flight-control/alignment.md`'s "Plan check — 2026-10-31" (CONCERNS, W1/item 2/item 3) and a
follow-up binding correction from the user changed three things:

- **W1 — wobble is unconditional, not a fallback.** The user, verbatim: *"Regardless of how writing
  control axis values are done, that (invisible) wobble is needed on the control axises, similar to
  9K113 axises."* **Decision 6 is superseded** (Decision 6 REVISED, below): every flight-axis write,
  cyclic pitch/roll, pedal and collective, in both control states, carries the 9K113's
  `SERVO_WOBBLE` mechanism from the first write, never as something tried only if a plain write
  fails. S0-2 and S0-P2 now measure the wobble's **invisibility bound** (the smallest amplitude/
  pattern that still holds the axis, checked against visible aircraft motion and the cockpit stick/
  collective/pedal animation, args 1100–1113) rather than whether wobble is needed at all, and the
  first probe writes from `LuaExportBeforeNextFrame` — ED's own documented injection point
  (`Export.lua:59-64`) — noting the 9K113 override won by changing value every frame, not by
  writing last (`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` §6). Wobble
  amplitude is a tunable (Export.lua constants block, the `SERVO_WOBBLE`/`DITHER_AZ_DEG` pattern —
  see "Behaviour constants" below, already the right home for it).
- **Item 2, revised by a later binding correction.** The dispatch's first draft asked S0-P2 to guard
  against the AI flying through the SAU; the user then corrected that directly, verbatim: *"ED's AI
  may fly through the SAU autopilot -> does not, SAU is not very capably, DCS AI does manouvres SAU
  cannot. Though, DCS AI probably does not use the cockpit controls either, but instead inputs the
  movemnt somewhere internally. But that needs checking."* (`explore-notes.md`, "Where ED's AI
  acts.") So the plan now carries: the SAU-as-AI-path hypothesis dropped; the working belief that
  the AI's input is injected internally, neither through the SAU nor the cockpit stick/collective/
  pedal positions, to be checked rather than assumed (new row S0-P1b); S0-P2/S0-P2a judged on the
  aircraft's actual attitude/rate/heading/height response, with the stick/collective/pedal args
  logged only as diagnostics; and the consequence that if the AI's input is summed in after the
  axis value, overpowering it is a **fight** (a steady counter-deflection), not a clean override —
  S0-P2a is the row that decides which. SAU off-switch rows (`AutopilotOffOP` 3047,
  `iCommandAutopilotEmergOFF`) stay only for what Stage 0 needs about the SAU in its own right
  (S0-P5, Stage 5), not as a way to neutralise the AI pilot (S0-P3). The recon's exact numbers
  (args 852/952 for the park-stow animation, 1100–1113 for the cockpit stick/collective/pedal
  positions — not the external-model args 500–503/510–513 — device-30 lever 3011–3013,
  `HeliControlEXT` 3014, and the `BASE_SENSOR_*_NORMED` param handles) are folded into Stage 0a/0b
  below, replacing the earlier generic guesses.
- **Item 3 (D-e) — left for the user, not resolved here.** D-e's auto-take-on-park recommendation
  conflicts with the 2026-10-25 settled point 2, *"Handover is spoken only"*; a line is added to D-e
  below flagging the conflict. The decision stays open.

### Goal

On the spoken handover Petrovich takes the controls from where the pilot left them, keeps doing
what the aircraft was doing (a turn in progress continues; under 5° of bank he holds heading), and
flies spoken turn / heading / level / altitude / speed goals with smooth, converging corrections —
within about ±10%, never ringing — by a per-frame feedback loop in Export.lua on the raw cyclic,
collective and pedal axes — **in both control states: unparked, where the player's stick is
ignored, and parked, where ED's own AI pilot is flying and Petrobrain must overpower or displace
it** — holding a current-AGL terrain floor, keeping his naked-eye lookout but not his optics, and
keeping the controls when the player moves to the operator seat — until the pilot says "I have
controls", which acts at once.

### Pilot-value check

The pilot gets his eyes and hands back. **Revised (A7):** the uses the user named are lookout, map,
radios, navigation — and the **key case: moving to the operator seat and working the 9K113 while
Petrovich flies**. That is what makes this milestone worth its cost. **And the user has since named
the mechanism (P1): working the 9K113 requires "park controls", and parked controls hand the
aircraft to ED's AI pilot** — the AI he wants replaced (*"DCS AI flies very badly and
unreliably"*). So the key feature is literally *"Petrobrain to overpower the DCS AI flying"*, and it
puts two requirements at the top: Petrobrain's loop must win against ED's AI in the parked state
(S0-P, the first gate), and the aircraft must be a steady, smooth platform for guidance (A9 —
smoothness over exactness). The unparked state (player in the pilot seat, looking out, on the map
or radios) is an equal must-have (P2), with its own problem: the player's stick. The old
framing, "the player becomes the spotter", was the weakest part of the case (goal check F7: for
spotting alone, handing over switches off the better optics); it is no longer the headline.

The first vocabulary is what a pilot says to a crew member he trusts with the aircraft for a
minute: turn, heading, level, height, speed. It is also the foundation of pilot-Petrovich and of
aligning for an ATGM launch (page 2, priority 5; `[[BL-B67]]`), both of which need exactly this
controller and neither of which is in scope. **What the pilot does not get from this milestone**:
manoeuvres (*"break left"*, `[[BL-B95]]`), look-ahead terrain avoidance (`[[BL-B101]]`), hover /
slow flight (see Decision 3), navigation to a point, proper seat-change handling beyond "he keeps
the controls" (A7: *"later"*). The value bar this plan has to clear is therefore modest and
concrete, now two sentences:

1. **"I hand over in a turn at 150 m, nothing jumps, he finishes the turn on 315 at 200 m and 220,
   and I never fight him."**
2. **"I hand over, move to the front seat, park the controls, and guide a missile while he — not
   ED's AI — holds the aircraft steady; and if I say 'left 10' from the front, he turns."**

Anything that does not serve those sentences is out.

### The picture — handover (body-layer owns it)

```mermaid
stateDiagram-v2
  [*] --> PILOT
  PILOT --> TAKING: "you have controls" (never "confirm?")\n[airborne, in envelope,\nno ATGM attack run]
  PILOT --> PILOT: "you have controls" refused\n→ "unable, <reason>"
  TAKING --> PETROVICH: Lua status: active,\ncapture done\n→ "I have controls"
  TAKING --> PILOT: ack timeout / Lua refused\n→ "unable, <reason>"
  PETROVICH --> PETROVICH: turn / heading / level / hold / speed\n→ readback, new goal (clamped to limits)
  PETROVICH --> PETROVICH: player swaps seat / parks / unparks\n→ phase unchanged (Petrobrain keeps the controls);\nLua switches flight effector, outputs continuous
  PETROVICH --> PILOT: "I have controls" (any confidence, never "confirm?")\n→ "you have controls", Lua release
  PETROVICH --> PILOT: Lua released by itself\n(envelope, crash, mission restart)\n→ urgent "you have controls!"
  note right of PETROVICH
    optics: none (binoculars, 9K113) — derived, not stored
    naked eye: scanning, contact + threat calls, "what do you see?" answered
    unparked: physical stick ignored
    parked: ED's AI pilot overpowered / displaced (S0-P decides how)
    attack run: cannot be running (takeover refused during one)
    goal not reached: no callout — he flies within limits
  end note
```

**A Petrobrain service quitting mid-flight is unspecified behaviour** (Decision 2, user): no
watchdog, no adopt-on-restart, no emergency release. Lua resets only on DCS's own events (mission
restart, `LuaExportStop`, ownship dead). **A seat swap is not one of them** (Decision 17).

### The picture — the control loop (Export.lua owns it, every frame)

```mermaid
flowchart LR
  subgraph BL["body-layer (1 Hz) — handover, vocabulary, limits, bands, floor value"]
    V["voice token\n+ slots"] --> A["action\nset_turn / set_heading / level_out /\nset_altitude / set_speed"]
    A --> GM["goal message\n(seq, goals, limits, bands, floor_agl)"]
  end
  GM -->|"POST /command/flight_control\n→ UDP → poll_command_socket"| G
  subgraph EX["Export.lua — run_flight_control(t), every frame"]
    G["goal\n(latest seq)"] --> SH["reference shapers\nheading/turn rate · VS · IAS\njerk-limited S-curve,\napproach curve, no ringing"]
    F["floor: AGL (radar, else DCS), smoothed,\n+ trend → raises the vertical goal"] --> SH
    SH --> AD["desired acceleration\n(lateral, vertical, along-track)\n+ feedback on ref − state, rate"]
    M["measured state & trend\nattitude, rates, accel,\nIAS, VS, AGL, slip"] --> AD
    AD --> LV["lift-vector CORRECTIONS\nΔ disc tilt (pitch/bank target)\nΔ collective\nfrom accel error, incremental"]
    LV --> IN["inner: cyclic closes on tilt\ntarget with rate damping;\npedal on slip / heading"]
    IN --> U["control demand\n(cyclic, collective, pedal)\nfrom captured position,\nrate-limited, saturated"]
    M --> IN
    PS["park state\n(S0-12 signal)"] --> SEL{"flight effector"}
    U --> SEL
    SEL -->|unparked| EU["effector U\nLoSetCommand 2001–2004\n+ per-frame value change\n(beats the player's stick)"]
    SEL -->|parked| EP["effector P\nwhatever S0-P proves\nbeats ED's AI pilot"]
  end
  OUT -->|"5 Hz status: mode, takeover_mode, goal,\nerrors, in_band, limits hit, release reason"| BL
```

**What the box labelled "lift-vector corrections" is, and is not** (user, 2026-10-26: *"we do not
need to know the exact values for lift vector, rather just, what needs to change compared to what is
current state and what is happening now"*). No thrust, mass or lift magnitude is ever computed. The
loop compares the **acceleration it wants** with the **acceleration it measures** and nudges the
two things a pilot moves: where the disc points (tilt target, via cyclic) and how hard it pulls
(collective). The coupling the user described falls out rather than being programmed: tilting
forward drops the vertical acceleration, so the vertical error raises collective; tilting back at
speed balloons the aircraft, so the same error lowers it. There is no "collective for altitude"
path — collective answers the acceleration error **along the lift axis**, whatever caused it. When
collective saturates, the residual vertical error moves into the tilt target (trade speed for
height), which is the user's *"the lift vector is the only control if collective is at limit"*.

**The per-state flight effector (P2, 2026-10-31).** *"These may need different solutions."* The
controller above is the same in both states: it turns goals and measured state into a **control
demand**. What differs is how that demand reaches the aircraft, so the seam sits there, in Lua:
`flight_effector_unparked` and `flight_effector_parked`, each with the same three functions —
`start(captured)`, `apply(demand, state, dt)`, `stop()` — selected per frame by the park state. It
removes a real duplication rather than adding a speculative layer: without it, the controller, the
handover, the status feed and every body-layer action would fork per state. Body-layer's actions,
params, goal message and vocabulary are identical in both states and never learn which effector is
live, beyond a status field for logs and the test card.

**Petrobrain's own loop flies in both states; ED's AI is never the control path** (user, 2026-10-31,
`explore-notes.md` "Steering ED's AI is rejected": *"no. DCS AI flies hoorribly. That is *the*
reason I want Petrobrain to replace it."*). So both effectors take the same control demand. The
parked effector may differ from the unparked one in *how it gets the demand to win* — a stronger
override, a different write site, or a one-time act that **disables or neutralises** ED's AI on
`start()` and restores it on `stop()` — but never by handing ED's AI a heading or altitude to fly.
ED-AI command interfaces enter this plan only as candidate off-switches.

**What A9 changes in this loop (2026-10-31).** The target is a band, not a point, but the loop
still aims at the value (*"goal is to still align with the desired value"*). So: **no hard
deadband** (that would park the aircraft at the band edge), but gains, rate limits and the
integrator are tuned for a slow, smooth final approach rather than a fast one — any error inside
the band is corrected gently, and nothing the loop does near the target may produce a visible
oscillation. The band is used by the loop in exactly one place: `in_band` in the status feed, and
the Stage 5 "settled" test (inside band, rates small) before a Trimmer press.

### Stage 0 — measure (desk pass, then Windows probe: parked state first)

One probe script, `aircraft-layer/dcs-export/Export.probe-flight-axes.lua`, built on
`Export.probe-9k113-flicker.lua`'s logging/loop scaffold (not a fresh one), each test a timed
segment started by a key the pilot binds, logging every frame to its own file. **Air start,
straight and level, ~150 km/h, ~200 m AGL, over flat ground, SAU in whatever state the test card
names.** The user flies; nothing here needs body-layer.

**Revised 2026-10-31 (A6–A8, P1, P2).** Stage 0 now has **two blocks, one per control state, and
the parked block runs first** because it is the user's key feature and the likeliest to fail.
S0-6 gains the forest/town comparison; S0-12 (park-state and seat signal) and S0-13 (state change
while writing) are new; the old S0-10 ("repeat from the operator seat") is absorbed into S0-P.

**Stage 0a — investigator desk pass, before the Windows run.** These are stage 0's own questions,
not assumptions the plan rests on, so they are specified here rather than resolved in this pass; the
plan's structure is the same whatever the answers, because every one of them is gated by a probe
row. **A read-only recon of the installed DCS files is already running (pending, 2026-10-31)** in a
Windows session: target `aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` on
branch `investigation/mi24p-park-controls`, covering the `Command_StickPark_Ext` 3055 handler and
its state, ED's AI pilot command/target interface, whether parked mode gates `LoSetCommand` axis
commands, and whether the SAU can be engaged from code. **Stage 0a takes that note as its first
input**: each question below is answered from it where it can be, and the investigator's own pass
(scoped to the repo's existing research and the `DCS-files` listings, not the live install, so the
two do not duplicate) covers only what it leaves open. The coordinator folds the findings into this
plan at the plan-check stage; until then, each answer is a probe row, not an assumption. Any other
desk findings go to `aircraft-layer/research/<date>-bl16-parked-controls-desk-recon.md`. Everything
below is **names from `command_defs.lua` / the command surface, not verified behaviour**:

1. **What "park controls" is, mechanically.** Which command toggles it (`Command_StickPark_Ext`
   3055 in `i9K113_commands`? the helperai `EngageOperatorStickLever` 3011 /
   `DisengageOperatorStickButton(Cover)` 3012/3013? `HeliControlEXT` 3014?), and is the state
   readable (an arg, a param, a lamp)? Prior evidence is thin and only half relevant: run 8 of the
   9K113 obedience probe toggled 3055 forty-two times with zero effect **on the sight gate**
   (`aircraft-layer/research/2026-10-22-9k113-ai-axis-obedience-prior-art.md`, line 17) — it says
   nothing about whether 3055 parks the flight controls or whether a `LoSetCommand` of it is even
   honoured.
2. **What ED's AI pilot does while parked, and how it can be switched off.** Does it hold
   attitude, heading, altitude, or follow its own orders (`LineUp_EXT` 3017, `UTurn_EXT` 3018, the
   wheel)? Those orders matter **only** if one of them stops or freezes the AI — steering it is
   rejected by the user. Does it write the same
   `iCommand` axes the player's stick does (so a per-frame write might displace it), or act below
   the input layer (so nothing written from Export can)? Any `HelperAI.lua` parameter for the
   pilot's gains or authority? **Updated 2026-10-31 (binding correction):** the user's own flying
   experience rules out the SAU as the AI's path — *"ED's AI may fly through the SAU autopilot ->
   does not, SAU is not very capably, DCS AI does manouvres SAU cannot"* — so the SAU is not probed
   as an AI-neutralising path (S0-P3 drops it). The working belief, still to be checked (*"DCS AI
   probably does not use the cockpit controls either, but instead inputs the movemnt somewhere
   internally. But that needs checking."*): the AI's input is injected internally, neither through
   the SAU nor the cockpit stick/collective/pedal positions. New row S0-P1b checks this directly.
3. **Is there a parked state with no active AI pilot** that keeps the 9K113 usable — the Petrovich
   overlay closed vs. open, an AI-off or input-freeze command, an SAU mode the AI defers to? The 9K113 probes flew with "DCS AI Petrovich OFF (overlay closed)"; what that did to the
   *pilot* AI was never recorded.
4. **Hook / scripting level**: is any AI option or task reachable for the player's own aircraft
   (`Controller`, `net.dostring_in`)? Expected no; worth one look because it would be the cleanest
   displacement.
5. **Seat and park signal** for S0-12: any Export-readable value that changes with the player's
   seat or the park state (camera position, a cockpit param, which seat's args update — the 874
   precedent below). **Confirmed by the 2026-10-31 desk-recon**: the stick-park stow animation is
   **arg 852** (pilot's cyclic) and **arg 952** (pedals), a 0..1 lag element with a 0.2 s time
   constant (`HelperAI.lua:46`); 852 ≈ 1 after the toggle is the cheapest observable, to be
   confirmed live (direction, settle time) by one probe toggle rather than assumed.
6. **Radar altimeter and DCS AGL over trees and buildings** (A6).
7. **Community prior art**: any mod or script that flies a DCS module from Export while an AI crew
   member also flies (the vJoy helicopter-assist project in the 2026-10-26 recon unbinds axes; does
   anything address an AI pilot?).
8. **Param handles and SAU candidates, confirmed by the 2026-10-31 desk-recon.** ED's own
   `get_param_handle` example names `BASE_SENSOR_STICK_ROLL_NORMED`, `BASE_SENSOR_STICK_PITCH_NORMED`
   and `BASE_SENSOR_RUDDER_NORMED` (`Export.lua:1355-1357`) — generic base-sensor params, no
   documented collective equivalent, and whether the Mi-24P populates them at all is unchecked; a
   cheap probe alongside S0-P1b. `LoGetHelicopterFMData().master` ("flag that player is actually in
   control of flight model for multiplayer multicrew sessions") may flip with park state even
   single-player — log it in the same probe. `AutopilotOffOP` (10, 3047) and
   `iCommandAutopilotEmergOFF` are **not** AI-neutralising candidates (item 2 above); they are
   S0-P5's own SAU-off rows, relevant only to whether effector P can lean on the SAU (Stage 5).

The seat precedent behind (2) and (5): with the player in the copilot seat, the 9K113 AI-axis
writes stopped showing in arg 874 (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`,
§"~t 170 on") — a seat or park change demonstrably changes which writes take effect for one channel,
so no flight-axis behaviour is assumed to carry across from the unparked state.

**Stage 0b — S0-P, the parked state (first Windows segment, gating).** Player in the operator seat,
park controls selected, ED's AI flying. Same probe script, its own segments and log file.

| # | Measures | Pass | Fail → | Decides |
|---|---|---|---|---|
| S0-P1 | Baseline: what ED's AI does when parked, hands off, 60 s — attitude, heading, altitude, IAS traces; cockpit stick/collective/pedal args (1100–1113) | its behaviour and its control activity recorded (does it hold, drift, follow an order?) | — | what Petrobrain is competing with |
| S0-P1b | **New (2026-10-31, "Where ED's AI acts").** Locate where the AI's input actually enters: during S0-P1's baseline, do args 1100–1113 visibly move as the AI flies, and does `LoGetHelicopterFMData()` (attitude, rates, accelerations, `master`) show control activity the args do not? | one of: args move (the AI acts on the control positions — S0-P2's override may simply win); args stay still while FM data shows activity not explained by them (the AI acts internally, per the user's working belief — S0-P2 is a fight, not a cancel); neither shows activity (re-check S0-P1's premise) | ambiguous → log longer, cross-check `master` toggling and the `BASE_SENSOR_*_NORMED` param handles (desk item 8) | which reading S0-P2/S0-P2a apply; confirms args are diagnostics only, never pass/fail |
| S0-P2 | **The user's lead hypothesis, probed first** (P4): overpower ED's AI on the axes, the 9K113 slew precedent. Per-frame `LoSetCommand(2001–2004)` — cyclic pitch/roll, pedal, collective — carrying the mandatory wobble (Decision 6 REVISED: dither/flicker, never a held constant), both write sites (S0-3), first write from `LuaExportBeforeNextFrame` | **the aircraft's actual response** (attitude, rates, heading, height) follows Petrobrain's commanded goal, not ED's AI's. Args 1100–1113 are logged as diagnostics only and are **never** the pass criterion (2026-10-31: the user's working belief is that the AI's input is injected internally, through neither the SAU nor those args — S0-P1b checks this) | the aircraft keeps following the AI's goal instead, or the response never settles → S0-P3, and S0-P2a decides whether what remains is a fight worth living with | **effector P = raw axes?** and which write site / mechanism |
| S0-P2a | **Does ED's AI fight back, and is this an override or a fight?** During a 60 s held override, judged on the aircraft's actual attitude/rate/heading/height response, never on the args (2026-10-31: if S0-P1b finds the AI's input is injected internally and summed in after the axis value, the per-frame write plus wobble **counters** the AI's effect rather than replacing it — a **fight**, not an override). Log whatever of the AI's own control activity is readable (args between Export writes) for diagnostics only | the aircraft's response stays bounded and smooth at the A9 bands, whether because the override replaces the AI's input or because the fight settles into a steady counter-deflection | the response **winds up** (growing oscillation or drift) or never converges → record size/rate; try flicker vs. dither vs. write site; still failing → S0-P3 | whether it is an override or a fight, and whether either is smooth enough to guide from (A9) |
| S0-P2b | **Handback while parked**: stop the override after 60 s held off the AI's own attitude | the AI resumes from where the aircraft is, smoothly | a **jump** (wound-up AI demand released at once) → measure it; candidate mitigations to try in the same segment: hold the override while ramping toward the AI's current demand before stopping, or a one-shot AI reset/off-on if desk item 2 finds one | parked `stop()` shape; D-e's question 2 |
| S0-P2c | **Handback to the player** (unpark, then stop the override) — the clean path the user actually wants after guidance | the player's stick takes over with no jump beyond Decision 4's accepted stick mismatch, and ED's AI does not get a frame in between | an AI frame or AI wind-up released during the unpark → order the hand-off (stop override only once the unpark has registered, per S0-12) | the release sequence in both states |
| S0-P3 | Neutralise the AI while staying parked: each candidate from desk item 3 (overlay closed/open, 3055, 3011–3014, an ED-AI command that switches it off or freezes its inputs), then repeat S0-P2. **SAU on/off is not a candidate here** (2026-10-31: the user's flying experience rules out the SAU as the AI's path — "Where ED's AI acts" — so SAU rows are probed only for the SAU's own sake, S0-P5/Stage 5, never as a way to neutralise the AI pilot). **Only as off-switches** — a command that makes ED's AI fly a heading or altitude is not a candidate (user, 2026-10-31) | some state exists where the 9K113 still works and the raw writes win | none → **blocker, report to the user** | **effector P = raw axes after neutralising X** |
| S0-P3b | **Fallback, only if S0-P2 and S0-P3 both fail** (user, 2026-10-31, "Fallback to investigate: numeric targets for ED's AI"). Can ED's AI's held heading, altitude and speed be **set as numbers** from code (a command value, param handle, or repeated nudges driven to a numeric goal by Petrobrain's loop), so the pilot's spoken goals replace ED's UI? Desk result (recon §7, 2026-10-31): **no numeric set path** -- every device-30 command is press/release, no axis clickable, no param handles; `HelperAI.lua` nudge constants imply a press-and-hold ramp (tap < 0.5 s, low then high rate after 2 s, alt tap step 2, ~1 s AI lag), so only a slow, coarse nudge loop remains. The AI's held IAS/ALT/course/mode are likely **readable** as text via `list_indication(6)` (HelperAI overlay page, unverified whether filled when overlay hidden) -- which a nudge loop needs as feedback. Probe nudge commands' step sizes and whether a loop of nudges converges on a number | the AI holds a spoken heading/alt/speed within the A9 bands, set without the pilot touching ED's menu | no numeric path and nudges too coarse to converge → parked state stays a blocker (go/no-go unchanged) | **a degraded parked mode**: fixes ED's UI, not ED's flying; reported to the user as such, never a silent scope cut |
| S0-P5 | SAU under parked control, for the SAU's own sake (Stage 5), not as an AI-neutralising path: do K/H/T/B and Trimmer act, does the AI fight them, and do `AutopilotOffOP` (3047) / `iCommandAutopilotEmergOFF` do anything to the SAU itself? | documented | — | whether effector P can lean on the SAU |
| S0-P6 | Capture at takeover in the parked state: can the control positions ED's AI is holding be read (the S0-6 args), so Petrobrain starts from them with no jump? | positions readable per frame | not readable → escalate (no-jump takeover impossible in this state) | Stage 1 capture, parked |

**Go/no-go after S0-P:** pass at P2 or P3 → continue. **All fail → the key
feature is blocked: stop and report to the user before anything is built.** It is not a scope cut —
the parked state is a must-have (P2). What would still have value without it is the unparked state
(lookout, map, radios, navigation, A7); whether to build that alone, wait, or look for a deeper
workaround is the user's decision, with the evidence in front of him.

**Stage 0c — the unparked state.** Player in the pilot seat (and, separately, in the operator seat
without park, if DCS allows that). The original rows, unchanged in substance:

| # | Measures | Pass | Fail → | Decides |
|---|---|---|---|---|
| S0-1 | Per-frame `LoSetCommand(2001/2002/2003/2004, v)` with a small sine on each axis in turn, hands off | aircraft responds, cockpit stick/collective/pedal args follow `v` | stop: no write path; re-explore | everything |
| S0-2 | Same, **with the physical stick held deflected, then stirred**. Wobble is mandatory on every write (Decision 6 REVISED — not "measure first, explore only if it fails"): this row measures the **invisibility bound**, the smallest flicker (±1e-4 and smaller) or dither amplitude that still holds the axis against the moving stick, checked against both visible aircraft motion and the cockpit stick/collective/pedal animation (args 1100–1103 pilot, 1110–1113 operator) | effective control (args) stays on the written value within ±0.01 while the stick moves; a wobble amplitude found that holds the axis with no visible twitch, in the aircraft or the cockpit animation | neither dither nor flicker holds at any amplitude below the visibility bound → escalate (Decision 6 REVISED has no fallback: wobble is the mechanism, not an option) | override mechanism; wobble amplitude (tunable, Export.lua constants block); Stage 1 |
| S0-3 | `LuaExportBeforeNextFrame` vs `AfterNextFrame` as the write site. ED's own documented injection point is `BeforeNextFrame` (`Export.lua:59-64`); the 9K113 sight override won from `AfterNextFrame` by changing value every frame, not by writing last (`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` §6) — so S0-1/S0-2/S0-P2's first probe writes from `BeforeNextFrame`, to see whether write order matters at all once the per-frame value change (wobble) is present | either works; pick the one with no one-frame physical-stick leak in S0-2 | — | where `run_flight_control` is called |
| S0-4 | Is `v` an **absolute** control position or **relative to trim**? Trim with the Trimmer, then write `v = 0` | documented either way | — | capture (Stage 1): absolute → capture = current args; trim-relative → capture = args − trim |
| S0-5 | **Release**: stop writing with Petrovich's output ≠ physical stick. Does the axis snap to the physical stick at once, or only when the stick next moves? | documented only | — | nothing — the release jump is not handled (Decision 4) |
| S0-6 | Read side at frame rate: `LoGetADIPitchBankYaw`, `LoGetAngularVelocity`, `LoGetAccelerationUnits`, `LoGetVectorVelocity`, `LoGetVerticalVelocity`, `LoGetIndicatedAirSpeed`, `LoGetRadarAltimeter` (value + valid, up to what height and bank — **does it read at all?**), `LoGetAltitudeAboveGroundLevel` (fallback — Decision 7), `LoGetAltitudeAboveSeaLevel`, `LoGetMagneticYaw` / `LoGetSelfData().Heading` **compared against the HSI heading card** (Decision 8), `LoGetSlipBallPosition`, stick/collective/pedal draw args — **1100–1103 pilot, 1110–1113 operator**
(cyclic pitch, cyclic roll, collective, pedals, confirmed by the 2026-10-31 desk-recon,
`CreateSimpleConnectedGauge`); the external 3D-model args 500–503/510–513 are a different, lower-
priority observable, not the cockpit positions the loop needs. **Added (A6):** a pass at ~50 m and ~150 m over open ground, then forest, then a town, logging radar and DCS AGL side by side, and the cockpit radar-altimeter needle | every quantity the loop closes on is present and changes every frame (not 5 Hz-stepped); each getter's table `debug_dump`ed once; a `get_argument_value` sweep while the pilot moves stick, collective and pedals finds the args that track each. **Over forest/town: the radar-vs-DCS-AGL difference is recorded** (the user believes radar reads the canopy; whether DCS AGL does is unknown) | a quantity stepped or absent → derive it and say so; no control-position arg → escalate; radar never valid → fallback is the only source (Decision 7, already accepted) | Stage 2 inputs; Stage 1 capture; Stage 3 floor and the AGL smoothing time constant; what a spoken "50 m" buys over trees |
| S0-7 | Response sign and rough size: a 0.05 step on each axis from trim, 2 s, back | sign, rough gain and lag per axis recorded (no plant model needed — user's addendum) | — | initial gains, rate limits |
| S0-8 | SAU from code: engage H/K/T/B via device 10 (`performClickableAction`, the `cockpit_switch` op), confirm the letter mapping against cockpit labels, observe hold; hold and release `Trimmer` while off the held attitude — re-reference on release, or fixed? Altitude (`HeightOn`/B, with K/H/T on first) and `SpeedOn` (above 150 km/h): hold or drift over 30 s? `HoverOn`, `RouteOn`: do anything? | each channel: engages yes/no, holds how well, Trimmer behaviour recorded | — | Stage 5 branch (below) |
| S0-9 | SAU vs raw writes: with K/H/T on, does a written cyclic change get fought (held back by the SAU's limited authority) or followed? | documented | — | whether SAU stays on during manoeuvres (Stage 5) |
| S0-10 | **Absorbed into S0-P (P1, P2), 2026-10-31.** Was: "repeat S0-1 from the operator seat". The operator seat with park controls is the parked state, probed in its own block above; the operator seat without park (if DCS allows it) is an unparked case, run as S0-1/S0-2/S0-7 again from the front | — | — | — |
| S0-11 | **Pilot-flown reference manoeuvres** (Decision 11): the user flies a set of known manoeuvres by hand; log the cockpit cyclic, collective and pedal positions (not raw joystick axes) per frame beside the S0-6 telemetry | each manoeuvre's input shape and the aircraft's response are on one time base. **Added (A9):** also record how far the user's own hand-flown speed/height/heading wander in "steady" flight — that is the empirical band | no readable input position → escalate (same as S0-6) | Stage 2 gains, rate limits and step shapes; Stage 2 and 6 reference traces; the default band values (Decision 18) |
| S0-12 | **New (A8, P2).** **Park-state signal** (required: it selects the flight effector) and seat signal (only if behaviour differs by seat within one state). Desk item 5's confirmed candidate: **arg 852** (stick stow, pilot's cyclic) and **arg 952** (pedals stow), a 0..1 lag element settling in ~0.2 s (`HelperAI.lua:46`) — 852 ≈ 1 is the cheapest observable, confirmed live by one probe toggle (direction, settle time); then sweep camera position, a cockpit param, which seat's args update (the 874 precedent), the 3055 state, as a cross-check | a reliable per-frame signal for parked / unparked; seat documented either way | **no park signal → escalate**: effector selection would have to be spoken or inferred, a user decision | how Lua selects the effector; whether body-layer needs seat state at all |
| S0-13 | **New (A8, P2).** State change **while writing**: with the S0-2 / S0-P winner holding a constant, swap pilot → operator, park, unpark, swap back | no jump at any change; the aircraft stays under the probe's control throughout | a jump or lapse → record size and duration; Lua re-captures on a park change (needs S0-12) | Co-moving Fields' park/seat rows; the effector hand-off; Flight 4b |

**Branches the plan carries until stage 0 lands**

```mermaid
flowchart TD
  P{"S0-P2 parked (lead hypothesis):\nper-frame axis writes beat ED's AI,\nno fight-back, clean handback (P2a–c)?"} -->|yes| PU["effector P = raw axes"]
  P -->|no| P3{"S0-P3: neutralise AI,\n9K113 still usable?"}
  P3 -->|yes| PN["effector P = neutralise X,\nthen raw axes"]
  P3 -->|no| BLK["BLOCKER: report to user\n(not a scope cut;\nsteering ED's AI is rejected)"]
  PU --> U
  PN --> U
  U{"S0-1/S0-2 unparked:\nwrites act, stick ignored?"} -->|"flicker"| W1["effector U: flicker"]
  U -->|"dither only"| W2["effector U: dither"]
  U -->|"neither"| D6["Decision 6, also a blocker\n(unparked is a must-have too)"]
  W1 --> SIG{"S0-12 park signal?"}
  W2 --> SIG
  SIG -->|no| ESC["escalate: how is\nthe effector chosen?"]
  SIG -->|yes| S4{"S0-4 absolute?"}
  S4 -->|absolute| C1["capture = args"]
  S4 -->|trim-relative| C2["capture = args − trim"]
  C1 --> S8{"S0-8/9 SAU drivable\n+ Trimmer re-references?"}
  C2 --> S8
  S8 -->|yes| SA["Stage 5: SAU holds steady state,\nTrimmer on each settle"]
  S8 -->|no| SB["Stage 5 dropped: Petrovich's loop\nholds everything; SAU left as found"]
```

### Affected Modules / Files

**aircraft-layer**
- `dcs-export/Export.probe-flight-axes.lua` (new, Stage 0) — the probe above, now including the
  operator-seat, seat-swap and forest/town segments.
- `dcs-export/Export.lua` — `handle_flight_control_command` (parse + bound-check, the
  `handle_sight_target_command` pattern: `extract_json_number_field`, whole-command reject on any
  non-finite or out-of-bound field); `run_flight_control(t)` per frame beside `run_sight_servo(t)`;
  `push_flight_control_state(t)` at the 5 Hz gate beside `push_sight_servo_state` (fields now
  include `takeover_mode` and per-goal `in_band`); a flag-gated per-frame `push_flight_trace` to its
  own file (the `push_slew_trace` pattern — built in from the start); `EXPORT_SCRIPT_VERSION` bump.
  **No seat-swap or park-change release path** (Decision 17). **The per-state flight effector
  (P2, Decision 20)**: `flight_effector_unparked` / `flight_effector_parked`, same
  `start` / `apply` / `stop`, selected per frame by the S0-12 park signal, with a continuous
  hand-off on a park change (S0-13). A per-seat path within one state only if stage 0 requires it.
- `src/collector/command_sender.py` — `send_flight_control`; `src/api/server.py` —
  `POST /command/flight_control`, `GET /flight_control/latest`; `src/schema/flight_control.py`
  (new), `src/collector/cache.py`, `src/collector/server.py` — the status feed, same shape and
  same "second feed, different rate class" reasoning as `/sight_servo/latest`.
- `tests/test_flight_control_api.py`, `tests/test_flight_control_lua.py` (pure Lua functions under
  `lua5.1`/`luajit`, skipped without one — `test_sight_servo_lua.py`'s precedent);
  `tests/test_export_lua_constants_parity.py` gains the wire bounds.
- `aircraft-layer/CLAUDE.md` — the write surface section: a third write path that is neither fixed
  vocabulary nor "any switch": bounded flight goals only, never raw axis values from the LAN.

**body-layer**
- `src/belief/flight_control.py` (new) — `FlightControlState` (frozen) and the handover state
  machine; the **actions** (`take_controls`, `release_controls`, `set_turn`, `set_heading`,
  `level_out`, `set_altitude`, `set_speed` — each does one thing, explicit params, never decides
  when; the five goal actions clamp to limits and return the value actually set); the **state
  params** (`has_controls`, `goal`, `takeover_mode`, `in_band`, `controls_parked` (P2; the "when"
  needs it only if D-e is answered with either recommendation), `flight_status` — read from Lua's
  status feed and ownship instruments only); the **"when"** (refusal preconditions,
  takeover/release ordering, the floor-over-goal priority, the handover-token reading by state) in
  one function, `decide_flight_control(...)`, apart from the actions, so it can move into a
  `[[BL-B95]]` script later without touching them. New module because this is new state with no
  home: `sight_effector` is the 9K113's cockpit writes, `effector_engine` runs switch checklists,
  `attack_run` is the ATGM run.
- `src/belief/voice_commands.py` — **new (A3):** `HANDOVER_TOKENS` frozenset beside
  `CANCEL_TOKENS`, and a branch in `classify_response` ahead of the floor comparison: a handover
  token never returns `"confirm"`. Detail in Decision 13. Not a tunable: it is a rule about which
  tokens may ask, the `CANCEL_TOKENS` precedent.
- `src/belief/crew_console.py` — dispatch for the new tokens; readbacks via `belief.speech`;
  the state-dependent handover reading (Decision 13); refusals as `"unable, <reason>"` for the
  handover only (A4 removes goal refusals).
- `src/belief/optic_policy.py` — `decide(...)` gains one **input** `flying: bool` (the `steady`
  precedent). **Revised (A5):** when `flying`, `decide` returns the naked-eye scan decision — the
  binocular and sight tiers are unavailable — before any phase logic; it does not suppress the
  naked eye. **Not an `OpticState` field**: derived from `FlightControlState` per poll, so there is
  nothing to carry across `OpticState(...)`'s construction sites (Co-moving Fields).
- `src/belief/attack_run.py` — read only: an engaged ATGM run refuses takeover (Decision 5).
- `src/body.py` — advance `FlightControlState` each poll; pass `flying` into `decide`; skip
  `write_sight_target` while flying (so Petrovich never fights the player's hands on the 9K113 in
  the key case — Decision 16).
- `src/aircraft_client.py` — `write_flight_control`, `get_flight_control_latest`.
- `src/belief/effector_sequences.py` — two triggers, `controls-taken` / `controls-released`, so
  any SAU switch work in Stage 5 is a `config/sequences/mi-24p/` table (BL-B90), not new code;
  `config/sequences/triggers.md` regenerated.
- `src/tuning.py` consumers / `config/defaults.toml` — the behaviour limits and bands (below).
  Regenerate and read the **rendered** first sentence of each.
- `body-layer/CLAUDE.md` — module list; Invariants: the physical stick is ignored while Petrovich
  has the controls; no LAN message carries raw axis values; handover tokens never ask "confirm?".

**audio-adapter**
- `src/vocabulary.py`, `src/command_matcher.py` — tokens `you_have_controls`, `i_have_controls`
  (plain phrases), **`level_out` (new, A1: "level", "level off", "level flight", "stop turn",
  "straight", "fly straight")**, and slotted `turn` (`left|right`, optional degrees), `turn_heading`
  (three digit words), `hold_altitude` (number, optional `metres`, optional `radar|barometric`),
  `speed` (three digit words; km/h) — slot parsers beside `parse_step_count`/`parse_clock`, same
  posture. **Check for collisions before adding**: "straight" and "level" are short words; the
  matcher's existing ambiguity guard must be run against the whole vocabulary with the new phrases
  in it (a test, not a reading).
- `/command-map` skill afterwards (vocabulary changed).

**Not touched**: world-model (no terrain lookup in BL-16 — that is `[[BL-B101]]`), brain-layer
(Decision 19).

### Behaviour constants — where each lives

| Constant | Where | Why there |
|---|---|---|
| terrain floor AGL, floor look-ahead time on the AGL trend | body-layer `tuning.py` (`belief.flight_control.*`), sent in every goal message | what Petrovich does |
| max bank for a spoken turn, max turn rate, max climb / descent VS, max along-track accel, minimum takeover IAS | body-layer `tuning.py`, sent in the goal message | what Petrovich does; the pilot will want to tune "how hard he turns" |
| **`TAKEOVER_LEVEL_BANK_DEG` = 5.0** (A2), `status="judgement"`, bounds ~1–15 | body-layer `tuning.py`, sent in `take` | the user's own number, explicitly a rough one (*"let's say"*) |
| **tolerance bands (A9)**: `SPEED_BAND_FRAC` 0.10, `ALT_BAND_FRAC` 0.10 with `ALT_BAND_MIN_M` (floor so 50 m AGL is not held to ±5 m), `TURN_RATE_BAND_FRAC` 0.10, `HEADING_BAND_DEG` (no natural "10%" — default 5°, judgement, see D-c) | body-layer `tuning.py`, sent in the goal message | what "good enough" means is a behaviour decision; Lua uses it only for `in_band` and Stage 5's settle test; acceptance and `sortie-log-triage` read the same values |
| handover ack timeout | body-layer `tuning.py` | how long he waits |
| shaper jerk limits, loop gains, output rate limits, saturation, flicker/dither amplitude, accel filter time constant, **AGL reference smoothing time constant (A6)** | Export.lua, **one commented block** | how the loop closes, not what he does. **Would want the X-T26 mechanism**; outside body-layer it does not exist, so noted, not improvised (the 9K113 servo's precedent) |

Sending the limits and bands in the goal message keeps one source of truth for behaviour
(body-layer) while the loop runs where it must (Lua). Lua bounds-checks them against hard ceilings
of its own.

### Implementation Plan

**Stage 0 — measure.** As above: 0a desk pass (taking the pending Windows recon as input), then 0b
S0-P parked (go/no-go), then 0c unparked. Output:
`aircraft-layer/research/<date>-flight-axes-probe-results.md` and a correction to
`mi24p-command-surface.md` §8 (which still says "unverified for a helicopter"). **Then amend this
plan** — every row marked "decides" above is a sub-decision to record here (`Decision N REVISED`
form) before Stage 1 starts. **S0-P failing (or the unparked S0-2 failing) stops the milestone for a
user conversation** — a blocker report, since both states are must-haves — not an
Architect workaround.

**Stage 1 — the seam and the handover, flying nothing.** Minimal working version.
- Lua: `flight_control` op with `take` / `release` / `goal`. `take` captures the current control
  positions (per S0-4 / S0-P6) and starts writing **exactly those values** every frame through
  **both flight effectors from the start** (Decision 20) — unparked with the S0-2 mechanism,
  parked with the S0-P winner — so Petrovich "holds the controls still" in either state, and the
  effector hand-off on a park change is in from the first build rather than retrofitted. `release`
  stops writing at once and calls the active effector's `stop()` (which restores anything S0-P3's
  off-switch changed) (Decision 4). Mission restart / `LuaExportStop` / ownship dead → release and
  reset. No watchdog (Decision 2). No release on a seat swap or park change (Decision 17).
- Body-layer: `FlightControlState`, the two tokens through the confirm bypass (Decision 13),
  refusals (not airborne, below min IAS, Export too old, ATGM attack run engaged), ack wait, "I have
  controls" only after Lua's status says `active` (the speech states a fact Lua confirmed, not an
  intention), optics off and naked eye on via `flying` (Decision 15).
- Tests: state machine transitions (every row of Co-moving Fields); `classify_response` never
  returns `"confirm"` for a handover token at any confidence, and the ambiguous-pair reading by
  state; Lua capture continuity (`u(t0) == captured`, bit-exact) and bounds rejection; API
  validation; `optic_policy.decide(flying=True)` yields naked-eye decisions only, never a
  binocular or sight tier.
- **Flight 1** (test card, named branch): level flight, SAU on, hand over, stir the stick, hand
  back — then hand over again, **swap to the operator seat, park the controls, wait 30 s, unpark,
  swap back, hand back** (S0-13's outcome tells the card what to expect at each change). Pass: no
  jump at takeover or at any park change, the stick is ignored unparked, **ED's AI never visibly
  takes the aircraft while parked**, release behaves as S0-5 predicted, optics stop and resume,
  naked-eye calls keep coming while he holds, "I have controls" never answered with "confirm?",
  speech in the right order.

**Stage 2 — hold the current state (priorities 2 and 3), plus the stop word.** The controller.
- Lua: shapers, desired-acceleration feedback, lift-vector corrections, inner tilt loop, pedal
  coordination, saturation priority (floor > altitude > speed), envelope monitor (Decision 3).
  On `take` (Decision 1 REVISED): if \|bank\| < `TAKEOVER_LEVEL_BANK_DEG` at the capture frame,
  goal = **hold the current heading** (roll out from the small bank, shaped); otherwise goal =
  **current turn rate**. IAS goal = current IAS; altitude goal = **current AGL** (level-off from a
  climb or descent, A6). Shaper state initialised to current value **and current rate**, so the
  reference starts where the aircraft is — this is what makes a turn in progress continue rather
  than roll out. Status reports `takeover_mode: heading | turn` so body-layer knows which goal it
  holds.
- `level_out` (A1) is built here, not in Stage 4: it is how a turn inherited at takeover ends
  (goal check F1), and Flight 2 needs it. Body-layer: the action plus its tokens. Lua: turn-rate
  goal to 0 through the shaper; the heading at which the roll-out settles becomes the held
  heading (not the heading at the moment the word was spoken — the aircraft carries some degrees
  through the roll-out, and snapping back to the spoken-moment heading would be an S-curve
  reversal).
- Offline: Lua tests against a deliberately crude toy plant (point mass, first-order attitude lag,
  sign/size from S0-7). **Rewritten for A9 — the assertions are about smoothness and convergence,
  never tight tracking:**
  - **enters the band** within a time bound derived from the limits (not a tight one);
  - **stays in the band** once entered (no exit for the rest of the run, disturbance-free plant);
  - **does not ring**: the error crosses zero at most once per step goal, and any overshoot stays
    inside the band;
  - **keeps converging**: the mean error over the last window is smaller than over the first
    window inside the band (the loop aims at the value, A9's second half) — no assertion on how
    close it gets;
  - **smooth outputs**: per-frame output change and its rate of change stay under the configured
    limits; output continuity at takeover (bit-exact on the first frame);
  - saturation behaviour; takeover at bank 4.9° → heading mode, 5.1° → turn mode.
  The toy plant proves the shaper and the wiring, not the tuning; the flights tune.
- **Flight 2**: take over straight (with a deliberate ~3° bank), then mid-turn, then climbing; say
  "level" during the inherited turn. Pass, judged on the per-frame trace against the bands
  (`sortie-log-triage` gains a flight-trace section that reports time-to-band, time-in-band and
  zero crossings — not RMS error): the ~3° case holds heading; the turn continues at its rate;
  "level" rolls out smoothly and holds; altitude and IAS stay in band; nothing visibly oscillates.

**Stage 3 — terrain floor from current AGL.** In Lua, every frame: if height above ground (radar
altitude when valid, else `LoGetAltitudeAboveGroundLevel` — Decision 7), **smoothed with the
Export.lua time constant set from S0-6** (so a forest edge is not a 20 m step in the reference),
plus its trend × look-ahead falls below the floor, the vertical goal is raised to the floor, over
any spoken altitude; for a barometric goal the floor is converted through the current
AGL-minus-baro difference. The floor itself acts on the **unsmoothed** minimum of the available
sources, because smoothing a floor delays it exactly when it matters. Body-layer sends the floor
value and says, once per event, that he is climbing for terrain (that call is settled, point 7 —
A4 removes only the "goal not reached" call). **Flight 3**: hold 60 m over rising ground, and over a
forest edge.

**Stage 4 — the rest of the first vocabulary.** Slots in audio-adapter; `set_turn` (relative
degrees, or continuous when no degrees), `set_heading` (shortest way unless a direction was
spoken; the heading the HSI shows — Decision 8), `set_altitude` (**AGL by default** — Decision 9
REVISED; barometric only when spoken), `set_speed` (km/h IAS); short readback on every accepted
command (Decision 10), no callout when the goal is reached and **none when it is not** (Decision
14). Goals outside his limits are **clamped, not refused** (Decision 14; readback wording is D-a).
A new goal never resets the shaper: the S-curve continues from the current reference value and
rate, so a heading changed mid-turn bends smoothly.
- **Flight 4**: sentence 1 of the pilot-value check.
- **Flight 4b — the key case (A7, P1)**: hand over in the pilot seat, move to the operator seat,
  **park the controls**, run the 9K113 through a guidance (or at least a long hand-slew) while
  Petrovich holds; from the front seat say "left 10", "level", "speed 1 8 0". Pass: no jump at the
  swap or the park, **ED's AI never flies the aircraft** (trace: control args follow Petrobrain's
  demand, not the AI's), heading/height/speed stay in band during the guidance, the sight is never
  written by Petrovich (`write_sight_target` skipped), commands from the front seat act. What
  "I have controls" does while parked is D-e; the card follows its answer. **Known limitation to
  state on the card**: his naked-eye mask is still modelled from the
  copilot station (`cockpit_mask.STATION_CO_PILOT`) even though he now sits in the pilot seat —
  proper seat handling is later (A7).

**Stage 5 — SAU for the steady state (branch, gated on S0-8/9).** If the SAU can be driven and
Trimmer re-references it: once every shaper has settled (**inside its band** and rates small — A9),
press Trimmer (the `cockpit_switch` op) so the SAU holds the attitude Petrovich arrived at, and let
his loop work only on what the SAU cannot hold (altitude, speed — per the user, poorly or not at
all). Channel engagement on takeover via a `controls-taken` sequence table. If not: this stage is
dropped, the controller already holds everything, and the plan says so.

**Stage 6 — tune and accept.** Flight-to-flight retunes of the Lua block. **Acceptance is the
bands, not tight tracking (A9):** for each goal type, time-to-band, stays-in-band and no visible
oscillation, across the corners of the envelope the user actually flies (50–800 m AGL, cruise
speeds, light and heavy) and in both seats. Bands written into `docs/acceptance/`, `BL-16`
acceptance against the explore notes' settled points 1–8 and the goal check's E1–E10.

Performance and Security run once per batch of stages built together (root `CLAUDE.md`); Security's
deep analysis should look first at the new write path (bounded goals only, loopback socket) and the
confirm bypass (a handover token is the one command class that can never be asked about).

### Co-moving Fields

Trigger fires: a mode machine with fields on both sides of a LAN seam, written externally (pilot
voice, and now the player's seat) and internally (Lua envelope, body-layer refusals).
`FlightControlState` and the Lua `fc` table are new, so there are no construction sites yet to
grep; **the Implementer greps `FlightControlState(` and every assignment to Lua `fc.` after Stage 1
and extends this table with any site not listed** (step 6a's own lesson). The existing type in
scope is `OpticState` (`optic_policy.py` constructs it fresh at ~2689 and ~2768) — this design
keeps `flying` out of it on purpose, so those sites cannot drop it. Rows marked **(2026-10-31)**
are new or changed.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| body `phase` | internal | "you have controls" accepted (no ATGM attack run engaged — Decision 5), **at any STT confidence that matched (2026-10-31)** | `TAKING`; `take_sent_sim` set; Lua `take` sent with current limits, bands, floor and `TAKEOVER_LEVEL_BANK_DEG` |
| body `phase` | internal | Lua status `active` with matching `take_seq` | `PETROVICH`; "I have controls" queued exactly once; `takeover_mode` copied from status |
| body `phase` | internal | ack timeout or Lua `refused` | `PILOT`; Lua told `release` anyway (idempotent); "unable, <reason>" |
| body `phase` | external (voice) | "I have controls" **(2026-10-31: any matched confidence, no confirm band, ambiguity with "you have controls" resolves to release while `PETROVICH`)** | `PILOT`; Lua `release` sent; "you have controls" spoken; any pending confirm question cleared |
| body `phase` | external (Lua) | status `released` with a reason while `PETROVICH` | `PILOT`; urgent "you have controls!" with the reason |
| body `phase`, Lua `fc.mode` | external (player) | **player swaps seat (2026-10-31, Decision 17)** | both **unchanged**; no `release`, no `take`; goal unchanged; outputs keep being written (S0-13 says whether a re-capture is needed) |
| Lua `fc.effector`, controller state, `fc.out_*` **(2026-10-31, P2)** | external (player, via S0-12 signal) | **park ↔ unpark while `active`** | `phase`, `fc.mode`, goal and shaper/integrator state **unchanged**; old effector `stop()`, new effector `start(current demand)` in the **same frame** (no frame without a write); first demand through the new effector == last demand through the old (bit-exact) unless S0-13 requires a re-capture; status `effector` field updated |
| Lua `fc.effector` **(2026-10-31, P2)** | external (`take`) | take while parked / while unparked | effector matches the park signal at the capture frame; capture read per S0-4 (unparked) or S0-P6 (parked) |
| Lua `fc.effector` **(2026-10-31, P2)** | external (`release`) or internal reset | release / reset while parked | parked effector `stop()` runs, restoring whatever its off-switch changed (S0-P3), so ED's own parked behaviour is back as the player found it |
| `flying` (derived) | — | any of the above | `== (phase in {TAKING, PETROVICH})`; **no binocular or sight-tier percept that poll; naked-eye percepts and calls continue (2026-10-31, Decision 15)**; `write_sight_target` not called |
| attack run | external (voice) | engage requested while `flying` | refused — the run needs the optics he has stopped using (Decision 5's mirror) |
| body `goal`, `goal_seq` | external (voice) | new goal (incl. `level_out`) | `goal_seq` +1; goal value clamped to limits (Decision 14); Lua applies only `seq > last_seq` |
| Lua `fc.mode` | external (`take`) | take | `active`; `fc.out_* == captured_*` bit-exact on the first written frame |
| Lua `fc.takeover_mode` **(2026-10-31)** | external (`take`) | take | `heading` iff \|bank\| < threshold at the capture frame, else `turn`; heading goal = current heading or turn-rate goal = current rate accordingly |
| Lua shaper states | external (`take`) | take | value = measured, rate = measured rate; integrators 0 |
| Lua shaper states | external (`goal`) | new goal | **unchanged** (no reset); only the shaper targets move |
| Lua heading goal **(2026-10-31)** | internal | `level_out` roll-out settles (turn rate inside band of 0) | heading goal = heading at settle, not heading when spoken |
| Lua `fc.mode` | external (`release`) | release | `off`; no write this frame or after; S0-5 behaviour |
| Lua `fc.mode` | internal | `LuaExportStop`, model time jumps back (restart), ownship dead | `off`; all `fc` state reset; status reason |
| Lua `fc.*` | internal | pause (`dt <= 0`) or `dt` > cap | outputs unchanged and still re-written (override must not lapse); integrators frozen |

### Risks & Unknowns

- **The override may not hold against a stick that is moving.** Everything rests on S0-2. If DCS
  applies the physical joystick after Export's write, or the per-frame value change shows as a felt
  twitch, the "stick is ignored" requirement cannot be met by this mechanism (Decision 6).
- **(2026-10-31, P1) The parked state may have no workaround — the highest risk in this plan.**
  ED's AI pilot flies whenever controls are parked. If it acts below the input layer, or re-writes
  the axes after Export each frame, and nothing reachable from Export or a Hook switches it off
  while keeping the 9K113 usable, Petrobrain cannot fly the key case. Steering ED's AI is rejected
  (P3), so there is no partial fallback inside this state. S0-P is first and gating for exactly
  this reason, with the user's own hypothesis (per-frame axis override, the 9K113 precedent, P4)
  probed first. **Even if the override wins, ED's AI may fight it**: a controller whose commands
  are ignored can wind up and then jump when released, or alternate with ours frame by frame — both
  would wreck the steady platform guidance needs. S0-P2a/b/c measure exactly that. The 9K113
  precedent is encouraging but not proof: that was one rate-commanded sight channel, this is four
  flight axes on a flying aircraft. A failure is **reported to the user as a blocker** with the evidence, and the user
  decides — not scoped down by the Architect. The unparked state would still have value (lookout,
  map, radios, navigation), but whether to build it alone is his call. **(2026-10-31, updated.) The
  SAU is ruled out as the AI's path** — the user's own flying experience: ED's AI performs
  manoeuvres the SAU cannot — **and the working belief is that its input is injected internally**,
  neither through the SAU nor the cockpit stick/collective/pedal args (1100–1113), to be checked
  (S0-P1b) rather than assumed. If true, "overpowering" the AI is a **fight** — a steady counter-
  deflection — not a clean override, and S0-P2/S0-P2a are judged on the aircraft's actual response,
  never on the args, which can read as a pass while the AI is still the one flying.
- **(2026-10-31) Two effectors, two failure surfaces.** A park change mid-flight is a hand-off
  between two different write mechanisms, one of which may involve switching ED's AI off. A lapse
  of one frame lets ED's AI (parked) or the stick (unparked) in. S0-13 measures it; the Co-moving
  Fields row makes "same frame, no gap" a test. An off-switch that is not restored on `stop()`
  would leave the aircraft parked with no AI and nobody flying — `stop()` restores it, and the
  `release`/reset rows test that.
- **Release is the inverse jump, accepted as is** (Decision 4): a known joystick limitation, no
  DCS-to-joystick channel exists. The pilot matches his controls, as in any DCS seat change.
- **Misrecognised handover — mitigation REVISED 2026-10-31 (A3).** The 2026-10-26 mitigation
  ("both tokens act only from the act band, never the confirm band without a 'yes'") is **withdrawn**
  by the user's answer: no confirm, ever. What remains: (a) the state-dependent reading — the token
  that would be a no-op in the current state is answered as a restatement, not acted on; (b) the
  two failure directions are made asymmetric on purpose, in the user's favour: while Petrovich
  flies, a misheard or ambiguous handover phrase **releases**; while the pilot flies, an ambiguous
  pair says "say again" rather than taking (Decision 13). Residual risk: a false "I have controls"
  hands back an aircraft whose stick is wherever the player left it — he hears "you have controls"
  and has the stick in hand; accepted by A3.
- **Controller tuned on one aircraft state.** Gains found at 150 km/h / mid weight may ring at
  250 km/h or heavy. Stage 6 must fly the corners of the envelope the user actually uses
  (50–800 m AGL, cruise speeds), not one point. A9's bands make this easier, not harder: gentle
  gains are more robust across the envelope.
- **Asymmetric yaw** (user): right-pedal margin is small at low speed and a collective increase
  eats it. The pedal output carries a direction-dependent limit, and a collective increase is
  rate-limited when right pedal is near it. Untested until Flight 2.
- **SAU behaviour is the user's recollection plus an older document** — Stage 5 may vanish.
- **(2026-10-31) AGL over trees and towns.** The user believes DCS radar altitude reads the canopy;
  whether `LoGetAltitudeAboveGroundLevel` does is unknown (goal check F6, agent's understanding
  only). If radar reads canopy and the fallback reads bare ground, a spoken "50 m" buys different
  clearance depending on which source is live, and a source switch over forest is a step of
  canopy height. S0-6 measures it; the status feed already carries which source is in use, and
  the AGL reference is smoothed. **Holding AGL over broken ground** means following every rise; at
  50 m with ±10% the loop would pitch constantly if it tried to track tightly — the smoothing time
  constant and A9's gentle gains are the answer, and Flight 3 checks it.
- **The DCS AGL fallback is terrain truth, not an instrument** (Decision 7). Accepted by the user
  as the workaround when radar altitude is missing; a deliberate, named exception to the
  no-omniscience line, confined to the floor and the AGL hold.
- **(2026-10-31) Naked-eye spotting from the wrong seat after a swap.** Petrovich in the pilot seat
  still sees through the copilot station's cockpit mask. Accepted for BL-16 (A7: seat handling
  later); stated on the Flight 4b card so a sortie finding about it is not read as a defect.
- **(2026-10-31) Short new words in the vocabulary.** "Level" and "straight" are short and common
  in ordinary crew speech ("target's straight ahead"). A false `level_out` while he flies is
  harmless-ish (he stops a turn), but a collision with an existing token is not. Stage 4's matcher
  test runs the full vocabulary, and the speech log will show false fires.
- **Model time while paused** keeps advancing per `aircraft-layer/CLAUDE.md`; the loop must use
  model-time `dt` and not integrate through a pause as if flying (Co-moving Fields' last row).
  Include a paused-state check in Flight 1, as that file requires.
- **Scope creep toward manoeuvres and seat handling.** "Break left" is one shaper limit away once
  Stage 4 exists; it stays out (`[[BL-B95]]`) by user direction. Proper seat-change behaviour
  (Petrovich taking over copilot tasks when the player is in the pilot seat, or vice versa) stays
  out by A7.

### Second-order effect

Unblocks pilot-Petrovich and the ATGM launch alignment (page 2, priority 5; `[[BL-B67]]`): both
become a new **goal source** for the same Lua loop, not a new controller — which is why the goal
message carries goals and limits rather than "turn" commands. **A7 brings pilot-Petrovich forward in
practice**: the key case is already "player on the 9K113, Petrovich flying", so the eventual
launch-alignment goal source has a user flying the exact configuration it will serve from the
first flight. It also makes `[[BL-B95]]`'s action catalogue concrete: the seven flight actions are
its first non-cockpit actions. **And it fixes the seam BR-2 would use** (Decision 19): a brain
mapping of "come left a bit" calls `set_turn`, never a new path. It complicates nothing in 9K113,
except that an engaged ATGM attack run refuses handover (Decision 5).

### Decisions (user, 2026-10-26)

All ten settled in the plan review. The user's words are quoted where they carry the reasoning;
the Architect's options and recommendations are in git history (`ca818317`).

1. **Climb or descent in progress at takeover: level off smoothly** at the altitude reached; the
   turn continues; current IAS held. (Agreed with the recommendation.)
   → **REVISED 2026-10-31** as Decision 1 REVISED below (bank threshold; altitude reached is AGL).
2. **A Petrobrain service quitting is unspecified behaviour.** *"If any of Petrobrain service quit,
   behaviour is unspecified. Don't plan for contingencies at this stage."* No watchdog, no
   adopt-on-restart, no emergency release button. Lua still resets on DCS's own events (mission
   restart, `LuaExportStop`, ownship dead) — those are not service contingencies.
3. **Forward flight only** for the first build: minimum takeover IAS (tunable, ~80 km/h), speed
   goals clamped to it. (Agreed.)
4. **Release jump: not handled.** *"This is a known problem with joysticks, there is no DCS to
   joystick channel."* Release stops writing at once; no trim transfer, no collective callout.
   S0-5 is recorded only.
5. **Takeover is refused during an ATGM attack run** — *"unable, <reason>"*. No missile-in-flight
   tracking needed. Mirror case (an attack run requested while he flies) is refused as well,
   because his optics are off; that follows from settled point 2, not a separate decision.
6. **Stick override: measure first** (S0-2), explore options only if it fails.
   → **REVISED 2026-10-31** as Decision 6 REVISED below (wobble is unconditional, not a fallback).
7. **Radar altitude preferred; DCS AGL (`LoGetAltitudeAboveGroundLevel`) is the fallback**
   whenever radar altitude is unavailable or invalid. *"That is acceptable workaround for radar
   alt."* Clarified the same day: *"fallback. We earlier noticed that we get no radar alt reading,
   so that fallback may become our only source, but radar alt reading would be preferred."* One
   height-above-ground source feeds both the terrain floor and the radar-referenced hold, with a
   status flag saying which is in use. S0-6 settles whether `LoGetRadarAltimeter` returns anything
   at all. The fallback is a named exception to the no-omniscience line, scoped to flight control.
8. **"Turn heading" uses whatever the HSI shows.** *"Whatever the HSI uses."* S0-6 compares the
   candidate getters against the HSI heading card and the matching one is used.
9. **Altitude reference defaults to radar** (radar altitude, DCS AGL as fallback — Decision 7). The readback says
   *"barometric"* only when barometric is in use; radar is unspoken.
   → **REVISED 2026-10-31** as Decision 9 REVISED below (same reference, now named AGL and
   extended to the implicit hold at takeover).
10. **Short readback for every command; no callout when the goal is reached.** The user's examples:

    | command | readback |
    |---|---|
    | turn left 20 degrees | *"20 left"* |
    | speed 2 2 0 | *"speed 2 2 0"* |
    | altitude 300 m | *"300 meters"* |
    | altitude 300 m barometric | *"300 meters barometric"* (Decision 9) |
    | turn heading 3 1 5 | *"heading 3 1 5"* |
    | turn left (no degrees, continuous) | *"left"* |

    The last two confirmed by the user the same day. Same shape for anything else: number first,
    no filler; the strings go in the test card for the user to hear.
11. **Record the pilot flying first: his control inputs and the aircraft's response.** User,
    2026-10-26, verbatim: *"A smart way to get data for what control inputs look like, is to read
    and log my joystick input value (=cyclic and collective and pedal axis values) in DCS and log
    them. Add aircraft telemetry data to that and we get controls input values, how they change,
    and how that affects the aircraft. I fly a set of known manouvres and we log how, with how much
    controller deflection and how the aircraft behaves in response."* Added to stage 0 as **S0-11**.
    **Channel settled the same day, verbatim:** *"this is better than my joystick values, the cyclic
    and collective values are what we really need, not my actual joystick axis values."* So S0-11
    logs the **cockpit control positions** (cyclic, collective, pedals; the args the S0-6 sweep
    finds), never the raw joystick axes: those are what Petrovich will write and what the aircraft
    answers to. Still to plan: the manoeuvre list, and how the recordings seed gains, rate limits
    and the Stage 2 tests.

### Decisions (user, 2026-10-31 — from the goal check)

Source: `explore-notes.md`, "Goal-check answers (user, verbatim, 2026-10-31)". Verbatim there;
quoted here only where the words carry the design.

- **Decision 1 REVISED** (supersedes 1; A2, A6). At takeover: *"heading. Let's say <5 deg bank gets
  level flight."* \|bank\| < `TAKEOVER_LEVEL_BANK_DEG` (5°, tunable) at the capture frame → hold
  the current heading; otherwise the turn continues at its rate. A climb or descent levels off
  smoothly at the height reached, **held as AGL** (*"AGL, unless player commands barometric"*).
  IAS held. The threshold lives in body-layer and is applied by Lua because only Lua sees the
  capture frame; Lua reports which mode it chose.
- **Decision 9 REVISED** (supersedes 9; A6). Every height Petrovich holds — spoken or implicit — is
  **AGL** by default (radar when valid, DCS AGL otherwise, Decision 7), barometric only when the
  player says so. The readback names "barometric" only when it is in use (unchanged). Whether AGL
  means above the canopy or above the ground beneath it is measured in S0-6, not assumed: the user
  *believes* radar reads trees.
- **12. Stop/level words** (A1): *"level [off|flight]", "stop turn", "[fly] straight"*. One action,
  `level_out`: roll out, hold the heading reached. In the first vocabulary, built in Stage 2.
  Readback proposed as *"level"* (the "left" pattern: the word, no filler) — the user hears it on
  the Flight 2 card. Whether "level off" should also stop a climb is open (D-b).
- **13. Handover never asks "confirm?"** (A3): *"no confirm. No key at this stage."* In
  `classify_response`, a token in `HANDOVER_TOKENS` never takes the `"confirm"` disposition:
  - **`i_have_controls`**: acts on any match, at any STT confidence — the emergency take-back
    the goal check (F3) was about. A "say again" would also be a delay, so the confidence floors do
    not apply to it at all. The matcher's own `MATCH_FLOOR` still decides whether it *was* this
    phrase.
  - **`you_have_controls`**: also never confirmed. Acts at `CONFIRM_FLOOR` and above; below that,
    "say again" (it is the direction where a false fire takes the aircraft and ignores the stick,
    and the recovery is one always-acting phrase).
  - **Ambiguity between the two phrases** (the matcher's `ambiguous` case, which today forces a
    confirm): resolved by state — while `PETROVICH` it **releases**; while `PILOT` it says "say
    again". The asymmetry is deliberate and follows the user's ranking: getting the aircraft back
    fast beats avoiding a false release.
  - **No bound key** now; *"will come back to that if needed"*.
  This is a local, reversible rule and was chosen rather than escalated; the one part worth the
  user's eye is the `you_have_controls` floor (D-d).
- **14. No "unable" for a goal not reached; fly within limits** (A4): *"no, just fly within
  parameters"*. No callout when a goal stalls (collective limit, pedal margin, floor). A spoken goal
  outside his limits (speed above max, height below the floor, IAS below the forward-flight
  minimum) is **clamped to the limit, not refused** — the 2026-10-26 Stage 4 refusal ("unable,
  below the floor / outside limits") is withdrawn. Handover refusals stay (they are E1/E7, settled).
  Open: what the readback says when the goal was clamped (D-a).
- **15. Naked eye stays on while he flies** (A5): *"yes"*. `flying` removes the binocular and sight
  tiers only. Naked-eye scanning, contact and threat calls, and answers to "what do you see?" carry
  on. A flying crewman's scan would realistically be narrower and more forward; that is a later
  tune, not scope here.
- **16. The key case is the player on the 9K113 in the operator seat, controls parked, while
  Petrobrain — not ED's AI — flies** (A7, P1, P3). The problem in that state is ED's AI pilot,
  which DCS puts in charge whenever controls are parked; the player's stick is already ignored by
  DCS there. Consequences: S0-P is stage 0's first block and a go/no-go; steering ED's AI is not a
  solution (P3); Flight 4b; `write_sight_target` is skipped while flying, so
  Petrovich never touches the sight the player is working; Decision 5's refusal is about
  *Petrovich's* attack run (`attack_run.py`), so the player guiding a missile from the front is not
  blocked by it. *"We'll build more proper handling of seat change later, I need the flight
  controlling to work first."*
- **17. Control authority is AI-vs-human, not seat-bound** (A8): *"Player hands off must remain
  player hands off and therefore Petrovich flying must remain Petrovich flying."* A seat swap never
  changes `phase`, never sends `release` or `take`, and Lua has no swap-triggered release. Refines
  memory `project_petrovich_operates_opposite_seat` (which seat he sits in still follows the
  player; the handover state carries across). **A park or unpark never changes `phase` either** —
  it changes only which flight effector is live (Decision 20). Seat detection is built **only** if
  stage 0 shows the write path differs by seat within one control state; park-state detection is
  required regardless (S0-12).
- **18. Tolerance: about ±10%, always converging, smoothness first** (A9): *"200 km/h desired speed
  can vary +-10 km/h with no problem … Smoothness is more important than maintaining an exact
  value. As general rule +-10% variation is allowed, but of course goal is to still align with the
  desired value."* Per-quantity bands in body-layer tuning; no hard deadband; gains tuned for a
  gentle approach; **no test, offline or in flight, asserts tight tracking** — they assert smooth
  convergence into the band, staying there, and no ringing. Note the user's own example (±10 on
  200) is 5%, inside the 10% rule; the default is the rule's 10%, and S0-11's record of his own
  hand-flown wander is the evidence to tune it.
- **19. Flight commands stay on the deterministic phrase path; the brain gets a seam, not a
  dependency** (BR-2's working lean, `feature/brain-tool-calls`, `plans/brain-tool-calls/
  alignment.md`). All BL-16 tokens are phrasebook tokens dispatched by `crew_console`. The five goal
  actions (`set_turn`, `set_heading`, `level_out`, `set_altitude`, `set_speed`) are plain functions
  with explicit params so a later brain mapping of *"come left a bit"* can call `set_turn` through
  `TOOL_SET` without a second path. **`take_controls`/`release_controls` are never exposed to the
  brain**: the controls change hands only on the explicit phrase. BL-16 adds no brain tool and does
  not wait for BR-2.
- **20. Two control states, both must-haves, one interface, a per-state effector** (P2, P3):
  *"In both cases Petrobrain must be able to control the aircraft. These may need different
  solutions."* Unparked: the problem is the player's stick (S0-1/S0-2). Parked: the problem is ED's
  AI pilot (S0-P). Petrobrain's own loop flies in both — *"DCS AI flies hoorribly. That is *the*
  reason I want Petrobrain to replace it."* — so ED-AI commands are probed only as off-switches.
  The controller, handover, actions, params, goal message and vocabulary are shared; only the
  Lua flight effector differs (`start` / `apply(demand, state, dt)` / `stop`), selected per frame
  by the park signal. Neither state is the fallback for the other: a failure in either is a
  blocker reported to the user.

### Decisions (user, 2026-10-31 — from the plan check)

Source: `plans/flight-control/alignment.md`, "Plan check — 2026-10-31" (W1), and a follow-up binding
correction from the user on item 2's hypothesis (`explore-notes.md`, "Where ED's AI acts"). Verbatim
quoted where the words carry the design.

- **Decision 6 REVISED** (supersedes 6; W1). *"Regardless of how writing control axis values are
  done, that (invisible) wobble is needed on the control axises, similar to 9K113 axises."* Wobble
  — the 9K113's `SERVO_WOBBLE` dither/flicker mechanism, reused rather than rebuilt — is **mandatory
  on every flight-axis write, cyclic pitch/roll, pedal and collective, in both control states, from
  the first write**, not a fallback tried only if a held constant fails. S0-2 and S0-P2 measure its
  **invisibility bound** (the smallest amplitude/pattern that still holds the axis, checked against
  visible aircraft motion and the cockpit stick/collective/pedal animation, args 1100–1113) rather
  than whether it is needed at all. The amplitude is a tunable, in the Export.lua constants block
  (the existing `SERVO_WOBBLE`/`DITHER_AZ_DEG` home — "Behaviour constants" table, unchanged by this
  revision). The first probe writes from `LuaExportBeforeNextFrame`, ED's own documented injection
  point, noting the 9K113 override won by changing value every frame, not by writing last.
- **ED's AI does not act through the SAU; the working belief is internal injection, to be checked.**
  The user, correcting a hypothesis the dispatch had floated: *"ED's AI may fly through the SAU
  autopilot -> does not, SAU is not very capably, DCS AI does manouvres SAU cannot. Though, DCS AI
  probably does not use the cockpit controls either, but instead inputs the movemnt somewhere
  internally. But that needs checking."* Consequences, all folded into Stage 0b above: S0-P3 drops
  SAU on/off as an AI-neutralising candidate (SAU rows stay only for S0-P5/Stage 5, the SAU's own
  behaviour); a new row S0-P1b locates where the AI's input actually enters (do args 1100–1113
  move, does `LoGetHelicopterFMData()` show activity the args do not); S0-P2/S0-P2a are judged on
  the aircraft's actual attitude/rate/heading/height response, never on the args, which are logged
  as diagnostics only; and if the AI's input is summed in after the axis value, "overpowering" it is
  a **fight** (a steady counter-deflection), not a clean override — S0-P2a is the row that decides
  which.

### Decisions Requiring User Input

None of these block Stage 0. D-e should be settled before Stage 1 (it shapes the handover rules);
D-a to D-c before Stage 4's test card is written.

- **D-e — Handover in the parked state.** The player cannot fly while parked, so the two handover
  phrases mean something different there. Two questions:
  1. **Parking while Petrovich does not have the controls** hands the aircraft to ED's AI — the
     thing the user wants replaced. Should parking count as *"you have controls"* (Petrobrain takes
     over automatically from ED's AI and says *"I have controls"*), or does the spoken phrase stay
     the only trigger? **Recommendation:** auto-take on park, once S0-12 gives a reliable park
     signal — otherwise the default state of the key case is ED's AI flying until the player
     remembers to speak, and A8's *"player hands off must remain player hands off"* reads naturally
     as "and Petrobrain flying".
  2. **"I have controls" while parked**: the player cannot take the aircraft from the front seat
     with the controls parked, so releasing would hand it to ED's AI. **Recommendation:** answer
     *"unable, controls parked"* and keep flying; release only once unparked. That is an
     understood-but-unavailable command, so "unable", not "say again"
     (`project_say_again_vs_unable`), and it still never asks "confirm?" (Decision 13).

  **Flagged at the 2026-10-31 plan check, left open:** question 1's recommendation (auto-take on
  park) conflicts with the 2026-10-25 settled point 2, *"Handover is spoken only"* — an auto-take is
  not a spoken handover, it is Petrovich taking the controls on a cockpit-switch event the player
  did not narrate. The recommendation is not withdrawn, but it should not be read as settled; the
  user decides, weighing it against the spoken-only rule rather than this plan's framing of A8.

- **D-a — Readback when a goal is clamped (Decision 14).** "Speed 3 5 0" with a 300 limit, or
  "hold 20" with a 30 m floor. **Recommendation:** read back the value he will actually fly
  (*"speed 3 0 0"*, *"30 meters"*), with no "unable" and no explanation — honest (code owns the
  fact), one word long, and the pilot hears the difference without having to monitor anything.
  Alternative: read back what was asked and fly the limit silently.
- **D-b — Does "level off" also stop a climb or descent?** In pilot usage "level off" usually means
  stop climbing. The answer (A1) grouped it with the turn-stopping words. **Recommendation:** all six
  phrases stop the turn only, exactly as answered; if the user wants "level off" to also hold the
  current height, it is one extra goal in the same action.
- **D-c — Heading band.** "±10%" has no meaning for a heading. **Recommendation:** ±5° default,
  tunable (the HSI card's resolution and a pilot's own straight-and-level wander are both about
  that); S0-11 gives the real figure.
- **D-d — Floor for "you have controls" (Decision 13).** Recommended: never "confirm?", acts from
  `CONFIRM_FLOOR` up, "say again" below. The alternative — acting at any confidence like
  "I have controls" — is simpler but makes a false takeover likelier. Only matters if the user
  reads A3 as covering both directions equally.
