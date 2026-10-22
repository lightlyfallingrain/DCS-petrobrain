# 9K113 AI-latency probe — player axis held every frame, then ShowMenu latency

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #sight-slew
**Flight for:** [[BL-B80]]
<!-- doc-provenance:end -->

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-ai-latency.lua`.
Nothing else of ours needs to run.

**Why, two questions:**

- **Part A.** The 2026-10-21 player-axis runs wrote 3026/3025 once per step and saw the readback
  jump for 4–6 frames, then 0. They never re-sent it every frame, which is what made the AI axis
  work. If the player axis steers when held every frame **with DCS AI Petrovich off**, BL-B80 may
  not need the overlay at all — **but only if something still reports where the sight points**
  (user, 2026-10-22: without angles or a world position, DCS and Petrobrain cannot be kept in
  sync). 874/876 are the sight head's own gauge args. They have read 0 with his AI off, but no run
  has caught them at 0 while the head was visibly off-centre. So Part A compares **your eyes on the
  ASP-17 mark** with 874/876 in the log, and each step diffs every cockpit arg in case another one
  tracks the head.
- **Parts B–C.** How long from a ShowMenu press until the readback obeys. That sets BL-B80's
  AI-off detector timing. The first press is also bracketed by an all-arg diff, with 874 as known
  truth: it lists every arg that moves with the head, to cross-read against Part A.

## How the sight stabilises — user, 2026-10-22, verbatim

> *"the sight does not hold a fixed ground point. I may have expressed it imprecisely. It holds the
> last set pointing direction in world coordinate angles, within gimbal limits of course. So in
> practice, the gyro stabilized sight operates in world coordinate axis and keeps it direction. The
> gimbal limits from the airframe coordinate axis of course limit the sight position. From this
> follows: sight does not track a point on ground, but it keeps its world axis relative angles
> steady when the airframe axis rotates. When aircraft moves, so does the point-on-ground where the
> sight is looking. The slew axis commands, I'm not perfectly sure, but I think they are relative to
> current sight gyro stabilised angles."*

So two frames, and the probe tells them apart with turns:

| | airframe frame (gimbal) | world frame (gyro) |
|---|---|---|
| what holds steady | — | the sight's world direction (his AI off, no input) |
| what limits it | ±60° az, +20/−15° el gimbal stops | — |
| 874/876, if a true gimbal readback | changes by −Δheading during a turn | — |
| AI axis (3061/3060), unknown | 874 stays on the commanded value, mark swings with the nose | 874 drifts by the turn, mark keeps its world direction |

## Setup (Windows)

1. Back up `Saved Games\DCS\Scripts\Export.lua`, then copy the probe over it.
2. Mi-24P **air start** with the guidance unit warmed up (a ground start needs a 5-minute
   warm-up). Autopilot on, **straight and level, no turns** except in the TURN window: the gyro
   holds the line of sight while the airframe moves, which can look like sight motion.
3. **DCS AI Petrovich OFF** (overlay closed). Wheel hidden, as you fly normally.
4. From the **copilot seat**, switch OBSERV **on last** = **T+0**. Move to the **pilot seat**.

## Timeline (T+ from OBSERV on, ~2:45 total)

| T+ | what the probe does | what you do |
|---|---|---|
| 0:00–0:20 | nothing (gyro alignment, seat move) | get to the pilot seat |
| 0:20–0:30 | player az **+0.5**, every frame | **watch the ASP-17 mark: does it move right, and keep going?** |
| 0:30–0:35 | player az 0 | does it stay where it got to, or return to centre? |
| 0:35–0:45 | player az **−0.5** | moves left? |
| 0:45–0:50 | player az 0 | stays or returns? |
| 0:50–1:00 | player elev **+0.5** (sign-inverted, so probably **down**) | moves up or down? |
| 1:00–1:05 | player elev 0 | stays or returns? |
| 1:05–1:20 | player axis 0 | **TURN 1: gentle ~30° turn, then level.** Expect the mark to keep its world direction (gyro). The log shows whether 874 moves with it — if it stays 0, 874 is no readback with his AI off. |
| 1:22 | **probe presses ShowMenu** (his AI on), AI target 20° left | does anything show on screen? mark should go 20° left |
| 1:42–2:42 | holds 20° left; straight and level again | **close the overlay by hand (your AI-menu key) about 3 times, ~15 s apart** — e.g. at 1:50, 2:05, 2:20. The probe should reopen it each time. **After the third, at ~2:25: TURN 2, gentle ~30° turn to the RIGHT, then level.** Does the mark stay 20° left of the nose (AI axis is airframe-relative) or keep its world direction (world-relative)? The probe stops pressing after 3 recoveries, so the turn cannot trigger one. |
| ~2:45 | centres everything, done | his AI is probably still on; turn it off if you like |

If his AI is already on at 1:07 the probe does **not** press, so it doesn't turn it off.

## Bring back

- **Part A, per step: did the mark move, which way, how far, and did it hold or return at the 0
  steps?** "Nothing" is a full answer.
- TURN 1 (his AI off): did the mark keep its world direction or follow the nose?
- TURN 2 (AI axis holding 20° L): did the mark stay 20° left of the nose, or keep its world direction?
- Part B–C: did a ShowMenu press show anything visible (wheel, text, sound)? Did the mark jump back
  to 20° left after each time you closed the overlay?
- `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_ai_latency.log`.

Restore the production `Export.lua` afterwards.

## Results, run 1 (2026-10-22)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_ai_latency.log`.
DCS 2.9.30.28738, air start.

Pilot, verbatim: *"sight did move and then stay where it moved to. no AI overlay change unless I
pressed a button to do it"*.

### Measured

- **Part A, player axis held every frame — it steers.** 874 ramped 0 → +0.44 (the +60° gauge
  limit) in ~0.17 s and stayed there while held. At the axis-0 step, 874 fell to 0 in ~0.1 s
  and stayed 0 — **while the pilot saw the sight stay where it had moved to.** Same for −0.5
  (874 → −0.41) and elevation +0.5 (876 → −0.74, near the −0.75 gauge limit).
  **So under the player axis, 874/876 track the input, not the head position.**
- **Candidate position args** (from the per-step diffs: moved during the step, held at the
  following axis-0 step). Not confirmed:
  - **565/566** (identical pair): 0.476 → **0.667** at az +0.5, unchanged at az 0, → **0.333** at
    az −0.5, unchanged at az 0. Exact thirds look like a stop or limit, not the head itself.
  - **555/556** (identical pair): 0.883 → **0.277** at elev +0.5, unchanged at elev 0, and changed
    0.277 → 0.573 during TURN 1. Possibly the elevation counterpart.
  - Your earlier note that the ASP-17 adjustment knobs turn would fit paired args like these.
- **TURN 1:** the turn came in the last ~5 s of the window (heading 018° → 359°). 874 stayed 0.
- **Part B — the AI axis obeyed with the overlay off.** Within 1 s of the −20° target, 874 read
  exactly −0.14667 (−20.0°). The probe treated that as "his AI already on" and did not press. It
  held for the rest of the run, ~80 s, and fell to 0 the moment the probe stopped re-asserting.
- **Part C:** three brief near-0 readings (t = 128.1, 134.1, 163.7), each recovering within one
  sample without any press. Possibly the pilot's presses.
- The Part B truth-bracketed diff did not run: it was tied to the press, which never happened.

### Contradicts 2026-10-21

"The AI axis requires DCS AI Petrovich ON" rested on runs that were confounded: with his AI off,
the AI axis was only ever written **once per step**, never per frame. Per-frame writes were only
ever tried with his AI on. This run is the first per-frame AI-axis hold with the overlay off, and
it worked. One confound remains: Part A's player-axis writes came first.

### Pilot answers, verbatim

1. Overlay: *"off until I pressed to open it at about T+2min"*. So Part B's −20° hold (from
   T+1:20) ran with the overlay **off**.
2. Did the mark go to 20° left: *"could not tell. part A put elevation down beyond what the ASP-17
   can show in HUD."*
3. *"Elevation slew did move, so it works. If you rewrite the probe so that elevation change is
   removed, I can fly again."* → run 2: azimuth only, AI axis first (no player-axis writes before
   it), no ShowMenu presses at all.

## Run 2 — AI axis with the overlay off, azimuth only

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-ai-axis-off.lua`.
Log: `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_ai_axis_off.log`. No flag needed.

**Questions:** (1) does the AI axis point the sight, by eye, with the overlay off and no
player-axis writes before it? (2) does 874 then report the head, or echo the command?
(3) airframe- or world-relative (TURN 2)? (4) does the gyro keep the world direction after
player slew, and do 565/566 follow (TURN 1)? No elevation, no ShowMenu presses.

Setup: air start, guidance unit warm, autopilot, straight and level except in the TURN windows.
**Overlay OFF the whole flight — do not touch it.** OBSERV on from the copilot seat = T+0, then to
the pilot seat.

| T+ | probe | you |
|---|---|---|
| 0:20–0:30 | AI axis 10° **left**, every frame | mark goes ~10° left? |
| 0:30–0:40 | AI axis 10° **right** | mark goes ~10° right? |
| 0:40–0:45 | AI axis 10° left | settle |
| 0:45–1:05 | AI axis holds 10° left | **TURN 2: gentle ~30° right turn, then level.** Mark stays 10° left of the nose, or keeps its world direction? |
| 1:05–1:15 | stops writing | sight stays, or moves somewhere? |
| 1:15–1:16 | player axis +0.3 pulse | moves right? |
| 1:16–1:25 | player axis 0 | holds? |
| 1:25–1:27 | player axis −0.3, twice as long | moves left past where it started? |
| 1:27–1:35 | player axis 0 | holds? |
| 1:35–1:55 | player axis 0 | **TURN 1: gentle ~30° left turn, then level.** Mark keeps its world direction, or follows the nose? |
| 1:55 | centre written once, done | |

Bring back: per row, did the mark move, which way, roughly how far; TURN 2 and TURN 1 answers;
the log.

## Results, run 2 (2026-10-22)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_ai_axis_off.log`.
Pilot's visual observations: not yet given (log only so far).

### Measured

- **AI axis per frame, overlay off, no player-axis writes before it:** 874 = the command exactly
  (−0.07333 / +0.07333 = ∓10.0°), every step. Run 1's confound is gone.
- **874 moves far faster than the sight can.** 0 → −10° in ~0.04 s (S1); −10° → +10° in ~0.04 s
  (S2); back to 0 within ~0.05 s when writes stop (S5). That is ~250°/s against the 9K113's
  20°/s horizontal slew (`Devices_specs/9K113.lua`), and the pilot reported the real ASP-17 mark
  moving "at steady pace, not instantaneously" under the AI. Player axis likewise: 874 → +50° in
  ~0.7 s on a 1 s +0.3 pulse, back to 0 within ~0.1 s at axis 0. **Reading: 874/876 report the
  slew demand (target or input), not the head position, in both modes.** Run 2 is consistent
  with that; the pilot's eyes decide it.
- **565/566** slid 0.439 → 0.333 over ~2.7 s at the start of S1 (steady pace), then stayed at
  exactly 0.33333 for the rest of the run, through 10° R and both player pulses. Looks like
  something reaching a limit — possibly the ASP-17 mark at the edge of its field. Unresolved.
- **555/556** change only with manoeuvre (TURN 2 dip to 0.66, TURN 1 to 1.0), not with any command.
- **No arg in the all-arg diffs tracks the commands** (left / right / held / pulse-and-hold). The
  remaining movers are attitude-driven instruments or blinking lights (157/358/929 alternate 0/1).
- Heading drifted right ~0.4°/s through the straight segments (006° → 046°); TURN 2 018° → 035°,
  TURN 1 048° → 027°.

### Video (2026-10-22, `win-mac-sync/from-windows/Digital Combat Simulator  Black Shark 2026.10.22 - 11.04.07.01.mov`)

Pilot, verbatim: *"After video started, a couple of seconds I and swithced OBSERV on. After that I
moved to pilot seat and started the timer (Mi-24 clock in build timer), so about 1-2s after observ
on."* and *"sight movement apparent video time 0:20 - 0:30"*.

At 1280×720 the clock face is too small to read the chronometer. Synced instead on one event:
the ASP-17 crosshair was tracked frame by frame (every 0.5 s, position relative to the two lamps on
the sight frame) and its sudden slide left at video ~0:26 lined up with arg 565 sliding
0.439 → 0.333 at log t = 56.6 (S1 start). So video ≈ log t − 30.8 s. The file-name timestamp
against the log's wall clock gives the same to ~1 s.

- **Video 0:17–0:25 (DELAY, no writes):** the mark drifts slowly left of centre while the heading
  creeps right ~0.4°/s. Fits the gyro holding a world direction.
- **Video ~0:26 (S1 start, AI axis 10° L, overlay off):** the mark slides quickly to the left edge
  of the ASP-17. **The AI axis moved the sight with the overlay off.**
- **Video 0:27 → end:** the mark stays pinned at the left edge, exactly as 565 stays at 0.33333.
  10° R, the release, both player pulses and both turns produce no visible change. Whatever the
  head did after S1 is outside the ASP-17's field, so this run cannot say.
- **Video 1:46–1:53 (TURN 1):** the crosshair leaves the glass vertically; 555/556 read 1.0 in the
  same window.

**Reading: 565/566 are the ASP-17 mark's horizontal position and 555/556 its vertical.** They
follow the actual line of sight (steady-pace slide, gyro drift) but clip at the edge of the
ASP-17's field (565 = 0.333 at the left edge). That makes them a real actual-position readback,
but only near the boresight. Their scale in degrees is unknown.

## Run 3 — AI axis small steps, overlay off

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-ai-steps.lua`.
Log: `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_ai_steps.log`. No flag needed. Video welcome.

**Questions:** degree scale of 565 (the ASP-17 mark); position or rate command (each step settles
and holds, or keeps sliding to the edge); airframe- or world-relative (TURN 2 at 2° L); does the
mark stay when writes stop.

Setup: air start, guidance unit warm, autopilot, **hold heading as steady as you can** (run 2
drifted ~40° in two minutes, and the gyro turns drift into mark movement). Straight and level except
in TURN 2. **Overlay OFF the whole flight.** OBSERV on from the copilot seat = T+0, then to the pilot
seat.

| T+ | AI axis, every frame | you |
|---|---|---|
| 0:20 | 0° (centre) | where does the mark sit? |
| 0:28 | 1° L | small step left, then holds? |
| 0:36 | 2° L | |
| 0:44 | 3° L | still on the glass? |
| 0:52 | 0° | back to centre? |
| 1:00 | 1° R | |
| 1:08 | 2° R | |
| 1:16 | 3° R | |
| 1:24 | 0° | |
| 1:32–1:52 | 2° L | **TURN 2: gentle ~20° right turn, then level.** Mark stays 2° left of the nose, or runs left? |
| 1:52 | 0° | |
| 1:57–2:05 | writes stop | mark stays, or moves? |
| 2:05 | centre written once, done | |

Bring back: does each step move then hold, or keep sliding; is 3° still on the glass; TURN 2;
release; the log (and the video, if recorded).

## Results, run 3 (2026-10-22)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_ai_steps.log`. Video (4K):
`win-mac-sync/from-windows/Digital Combat Simulator  Black Shark 2026.10.22 - 11.34.02.04.mp4`,
synced by file timestamp against the log's wall clock (pilot: *"I started video early so it's easier
to sync by (file) timestamp"*). Spot frames at video 2:25 / 2:38 (mark left, 565 = 0.333) and 2:54
(mark right, 565 = 0.625) agree with the log. Heading held 011.9–012.1° until TURN 2.

### Measured (565 = ASP-17 mark horizontal; 0.333 = left edge)

| step | command | 565 over the step | reading |
|---|---|---|---|
| S1 | 0° | 0.468 → 0.466 | slow drift only |
| S2 | 1° L | 0.465 → 0.464 | **no movement** |
| S3 | 2° L | 0.464 → 0.358, **steady −0.0135/s for all 8 s, never settles** | slides |
| S4 | 3° L | → 0.333 (edge) in ~1 s | slides faster, pins |
| S5 | 0° | 0.333 | stays pinned: **does not return** |
| S6 | 1° R | 0.333 | no movement |
| S7 | 2° R | 0.333 until the last ~1 s | head comes back into the field |
| S8 | 3° R | 0.353 → 0.625, **steady +0.040/s** | slides, 3× the 2° rate |
| S9 | 0° | 0.625 → 0.646 | stops (residual matches −0.5° heading drift) |
| TURN 2 | 2° L, right turn 011.5° → 021.7° | 0.650 → 0.333 (edge) in ~5 s | runs left with the turn |
| release | writes stop | 0.333 | pinned, nothing to see |

- **The AI axis, with the overlay off, is a rate command, not a position.** A held 2° never
  settles; 0° does not bring the mark back; a step reverses the slide instead of going to a place.
- **Rate law (rough):** 1° → 0, 2° → 0.48°/s, 3° → 1.4°/s, and run 2's 10° → ~9.5°/s. That fits
  rate ≈ (|cmd| − ~1.5°) °/s: a joystick-style deadzone of ~0.025 axis units and ~60°/s per unit
  beyond it. Degree scale used: 565 ≈ 0.028 per degree, from TURN 2's gyro run-off (below).
- **Gyro world hold confirmed.** In TURN 2 the mark ran left at ~0.03 of 565 per degree of heading
  change, beyond the commanded slide. The commanded slide adds on top: the AI axis drives the
  gyro-stabilised direction (the pilot's guess, verbatim earlier: *"relative to current sight gyro
  stabilised angles"*).
- **ASP-17 mark field ≈ ±6°** at that scale (0.333 … 0.667 around 0.5).
- **565/566 is the only arg that tracks the slides** (all-arg diffs). 874 echoes the demand.

### What this changes

The 2026-10-21 "position target, exact" reading was made with the overlay on, and rested on 874,
now known to echo the demand. Its targets (20–60°) were all outside the ASP-17 field, so no run has
yet shown a true position command in either mode. BL-B80 as built (position target, rate-limited in
Export.lua, overlay kept on, 874 as the readback) rests on that reading. **Explore with the user
before any change.**

### Pilot answers after run 3, verbatim

1. Real 9K113 slew control rate-based with a deadzone? *"yes, small deadzone"*.
2. How does the operator know where the sight points? *"copilot knows by the indicators in the
   sight view itself. (ref docs/concept/mi-24_info/9k113-reticle-narrow-x10.png). The pilot does
   not outside of ASP-17 crosshair, except that what the copilot *says*."*

Direction, verbatim:

> *"If there's no way to know where it is pointing, we may have to separate within HUD and outside
> HUD pointing logic.*
> *- outside could just be the current simulation plus slew time*
> *- within HUD it's important to get the ASP-17 show *where* the target is so that pilot can line
> up. Important for attack runs in general and critical for ATGM guidance."*

*"Build the probe."* → run 4: the same small steps with the overlay **on**.

## Run 4 — the same small steps, overlay ON

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-ai-steps-on.lua`.
Log: `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_ai_steps_on.log`.

**Question:** with DCS AI Petrovich on, is the AI axis a **position** command? Position: each step
moves at a steady pace and then holds at a place proportional to the command, and 0° returns the
mark to centre. Rate: as in run 3.

Setup as run 3, except: **turn the DCS AI Petrovich overlay ON before OBSERV** and leave it on
(do not command any scan). Timeline identical to run 3 (T+0:20 centre … 1:32–1:52 TURN 2 at 2° L …
1:57–2:05 release, done 2:05). Video by file timestamp again.

## Results, run 4 (2026-10-22)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_ai_steps_on.log`. Video (4K):
`win-mac-sync/from-windows/Digital Combat Simulator  Black Shark 2026.10.22 - 12.04.50.06.mp4`
(start 12:04:50 by file name).

Pilot, verbatim: *"Crosshair moved slowly to left, stayed at edge of hud. I turned so that HUD
showed where it's actually pointing. Overlay is the triangle style three line grosshair since I've
turned the menu wheel off. At the end of video is me slewing the 9K113 +-60 degrees using the player
9K113 view and controls."* and *"the red line in 9K113 player view is the controller deflection
vector"*.

### Measured (565 = ASP-17 mark horizontal; 0.333 left edge, 0.667 right edge)

| step | command | 565 | reading |
|---|---|---|---|
| S1 | 0° | 0.512 → 0.507 | drift only |
| S2 | 1° L | → 0.399, **steady −0.0135/s** | slides (overlay off: 1° did nothing) |
| S3 | 2° L | −0.03/s, edge at ~3 s | slides faster, pins |
| S4, S5 | 3° L, then 0° | pinned 0.333 | pilot turns left 004° → 348°: mark comes back to 0.57 with the turn |
| S6 | 1° R | +0.002–0.005/s (heading drift alone ≈ +0.003/s) | ~nothing |
| S7 | 2° R | +0.013 → +0.025/s, edge 0.667 | slides, pins |
| S8–S10 | 3° R, 0°, 2° L | pinned 0.667 | head far right of the field |
| ~t 170 on | — | 565/555/874 frozen | **pilot moved to the copilot seat / 9K113 view** (video ~2:50) |

- **Overlay ON does not make the AI axis a position command.** It is still rate: steps slide and
  never settle, 0° stops but does not return. The deadzone looks smaller or offset (1° L slides,
  1° R barely), but the model is the same.
- **So the 2026-10-21 "position target, exact" reading is withdrawn in both modes.** 874 echoes the
  demand; it never showed position.
- **With the player in the copilot seat, the probe's AI-axis writes stop showing in 874** (it stayed
  at −0.0147 through S11's 0° writes), and the pilot-seat ASP-17 args (565/555) stop updating.
  Fits the opposite-seat rule (`project_petrovich_operates_opposite_seat`): whoever sits in the
  copilot seat owns the sight.
- The pilot's hand slew to ±60° at the end of the video came after the probe had stopped logging,
  so no args were recorded for it. The red line in the 9K113 view is the controller deflection,
  not a position indicator.

### The hand slew at video 2:55 onwards (correction to the line above)

Pilot, verbatim: *"player slew video time 2:55 onwards"*. That is log t ≈ 172 → 192, so S10's tail,
S11 and S12 **did** record it (the probe was still running until video 3:14).

- **Only 566 and 556 move** during the hand slew (566 0.667 → 0.333 across the field; 556 swings).
  Their pilot-seat twins 565/555 froze at the seat change. So each pair is two copies of the ASP-17
  mark, and the 566/556 copy keeps updating with the player in the copilot seat.
- **874 does not follow the hand slew at all** (stays −0.0147, the probe's last AI value).
- **No arg in 0..3000 tracks a full-range sight position.** The S11/S12 all-arg diffs list only
  566, 556 and 882. A full-range index would have to end each step where it started to be missed.
- Remaining places a full-range readback could live: args above 3000, or the 9K113 sight's
  `list_indication` text (the reticle's 0/1/3/6 scale may be drawn as an indication, not an arg).

## Run 5 — device methods, mark scales, rate law

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-methods.lua`.
Log: `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_methods.log`. Video welcome (file timestamp).

**Questions:** (E) does the 9K113 device object expose any native getter to Lua — `get_LandPoint`
above all? (S1/S2) the ASP-17 mark's degree scale in azimuth (565) and elevation (555), from the
gyro world hold during small heading and pitch changes; (S3–S14) the AI-axis rate law, azimuth and
elevation, in short pulses that keep the mark on the glass.

Setup: air start, guidance unit warm, autopilot, heading steady, **overlay OFF**. OBSERV on from the
copilot seat = T+0, then to the pilot seat. Nothing in this script touches a switch or ShowMenu.

| T+ | probe | you |
|---|---|---|
| 0:20 | lists device methods (instant, one log burst) | — |
| 0:20–0:30 | axis 0 | **HDG: gentle ~5° heading change right, then back.** |
| 0:30–0:40 | axis 0 | **PITCH: gentle ~3° nose up, then back.** |
| 0:40–1:02 | AI az pulses: 2.5° L, 0, 2.5° R, 0, 4° L, 0, 4° R, 0 | watch: small steps, mark stays on the glass? |
| 1:02–1:12 | AI elev pulses: +0.1, 0, −0.1, 0 | mark moves up / down? which way first? |
| 1:12–1:17 | writes stop | — |
| 1:17 | done | |

Bring back: the log (and video); whether the mark stayed on the glass; which way the elevation
pulse moved it first.

## Results, run 5 (2026-10-22)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_methods.log`. No video
(pilot: *"no video this time"*).

### E — device methods: definitive negative

Every device object is the same thin wrapper — one own key, `link` (userdata), and an `__index`
table:

- device 7 (9K113) and 16 (ASP-17): `SetCommand`, `listen_command`, `listen_event`,
  `performClickableAction`. Nothing else.
- device 0 (main panel): the same plus `get_argument_value`, `set_argument_value`,
  `update_arguments`, `get_light_reference`.

None of the native getter names (`get_LandPoint`, `getCurrentFOV`, `isGyroReady`, …) resolve.
**There is no Lua route to the sight's aim point.** Outside the ASP-17 field, Petrobrain can only
estimate.

### Mark scales (gyro world hold, axis 0)

- **Rest position** (OBSERV off): 565 = 0.500, 555 = 0.556.
- **565 ≈ −0.039 per degree of heading** (nose right → mark left): +2.6° → −0.103, and back
  −2.6° → +0.102. So the horizontal field edges (0.333 / 0.667) sit about **±4.3°** from centre.
  Corrects runs 3–4's 0.028/deg estimate, which mixed commanded slide into the heading change.
- **555 ≈ −0.028 per degree of nose-up pitch**: +0.88° → −0.024, −1.51° → +0.042.

### Rate law: inconsistent with run 3

- Azimuth 2.5° L/R (3 s each) and 4° L/R (2 s each): **no movement** beyond heading drift.
  In run 3, 2° and 3° slid steadily (≈0.35°/s and ≈1.0°/s at the corrected scale).
- Elevation −0.1 (2 s): slid ~1°/s (555 −0.027/s) within 0.1 s of the command, and stopped at 0.
  Elevation +0.1: no movement.
- The sight's elevation sat ~10° off the rest position throughout (555 ≈ 0.83 against 0.556).

Something gates the AI axis that we do not understand yet. Candidates: a gimbal stop on the
blocked direction, a deadzone that is not fixed, or a difference in setup between runs.

## Results, run 5b (2026-10-22, same script flown again)

Log: `aircraft-layer/research/logs/2026-10-22/aircraft_layer_probe_9k113_methods_b.log`. Pilot,
verbatim: *"I saw croshair move at about 0:40 and 0:50"*. The log ends at S12.

- **2.5° L (S3): slid −0.035/s of 565 = 0.9°/s. 2.5° R (S5): +0.033/s = 0.85°/s.** Then
  4° L, 4° R and elevation +0.1: **nothing**.
- Method listing identical to run 5a.

### The rate law is already in the module's own spec file

`aircraft-layer/research/mi24p-command-surface.md` §4 (from `Devices_specs/9K113.lua`):
`axis_use_velocity = true`, `h_axis_velocity = 20°/s`, `v_axis_velocity = 10°/s`,
`Slew_dead_zone = 0.003`. So rate = value × 20°/s in azimuth, × 10°/s in elevation:

| command | predicted | measured |
|---|---|---|
| az 2.5° (0.0417) | 0.83°/s | 0.85–0.9°/s (5b) |
| az 3° (0.05) | 1.0°/s | 1.03°/s (run 3) |
| elev −0.1 | 1.0°/s | 0.96°/s (5a) |

The "deadzone of ~1.5°" read from run 3 was wrong: the real deadzone is 0.003 (0.2°). What
stopped the small commands is a gate.

### The gate: arg 962

Arg 962 flips **1 → 0 in exactly the step where the AI axis first starts to move the sight**, in
every run where it moved: run 3 S3 (2° L), run 4 S2 (1° L), run 5a S13 (elev −0.1). In run 5b it
flipped **0 → 1 in S5**, and **every later command did nothing**. While 962 = 1, commands of up
to 4° for 2–3 s were ignored (5a), and 1° for 8 s (run 3). Its name is not in any note here;
`mainpanel_init.lua` / `clickabledata.lua` on the DCS machine will say.

### Arg 962 identified (Windows session `omen-proud-beaver`, read-only, 2026-10-22)

**Arg 962 is the 9K113 LAUNCH PERMITTED lamp** (`SCHO_9K113_LAUNCH_PERM`, operator's right
board): `lamps.lua:617`, a 1:1 binary lamp fed by the native `op_right_board_lights` controller.
Siblings: 957 COMPL_ON, 958 PU_OFF, 959 CHECK, 960 READY, 961 MSL_EXIST. So it is an **effect**,
not a gate: launch permission is withdrawn while the sight moves. The correlation stands — every
time the AI axis was ignored, the lamp was lit — but what blocks the axis is still unknown.

Also from that lookup: `Devices_specs/9K113.lua` has no park, cage, helper or lock keys; the
operator stick has a **Park/Unpark** toggle, `Command_StickPark_Ext = 3055` on device 7
(`Input/Mi_24P_op/*/default.lua`, `value_down = 1`); any park/cage/enable state lives in native
code. Candidate to test: a parked operator stick blocks the AI axis.

## Run 6 — reproduce the gate, try the stick park toggle

**Branch: `probe/9k113-ai-latency`.** Script: `aircraft-layer/dcs-export/Export.probe-9k113-slew-gate.lua`.
Log: `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_slew_gate.log`. Video welcome.

**Questions:** does the gate reproduce (axis works, sight comes back near centre, lamp lights, then
ignored)? Does toggling Park/Unpark Operators Stick (`SetCommand(3055, 1)`) release it? Every row
logs the ASP-17 mark and lamps 957–962.

Setup: air start, guidance unit warm, autopilot, heading steady, **overlay OFF**. OBSERV on from the
copilot seat = T+0, then to the pilot seat. **Don't press the stick park key yourself.**

| T+ | probe | you |
|---|---|---|
| 0:20–0:52 | 2.5° L / 0 / 2.5° R / 0, twice | mark moves each time, or stops responding? |
| 0:52 | **stick park toggle #1** | anything visible? |
| 0:55–1:09 | 2.5° L / 0 / 2.5° R / 0 | moves again? |
| 1:09 | **stick park toggle #2** (back) | |
| 1:12–1:19 | 2.5° L / 0 | moves? |
| 1:19–1:27 | axis 0 | **HDG: gentle ~3° heading change, then back.** Does the mark stay fixed on the nose, or slide? |
| 1:27–1:42 | **escape attempts:** 10° L for 0.5 s, 0, elev −0.1 for 1 s, 0, then 2.5° R, 0 | which of these moved the mark? |
| 1:45 | done | |

Bring back: the log; which pulses visibly moved the mark; anything on screen at the two toggles.

### Pilot on the LAUNCH PERMITTED lamp, verbatim

> *"9K113 LAUNCH PERMITTED lamp - is lit when 9K113 point at boresight within a certain (0.3 deg?)
> limit. Otherwise it is off. Reason is the missile guidance radio beam width limit. This is only
> relevant for ATGM guidance and launch."*

Consequences:

- **962 is an at-boresight readback** (sight within ~0.3° of boresight). The ASP-17 mark's
  boresight value can be calibrated from it (in 5b the lamp lit with 565 ≈ 0.517, not 0.500).
  **Correction (pilot, verbatim): *"no. Boresight is always within HUD. Both are fixed at
  aircraft ahead direction. Boresight sits within HUD, but HUD area a larger."*** So the lamp adds
  nothing outside the HUD — inside it the mark args already give position; the lamp is a finer
  at-boresight signal and the launch condition. An earlier draft here claimed it re-anchors the
  outside-HUD estimate; that was wrong.
- **Every ignored AI command so far happened with the sight at boresight.** Run 6 now ends with
  escape attempts (a short 10° azimuth pulse, a short elevation pulse) to see what breaks the hold.
- For BL-B67 (ATGM): the lamp is the launch condition itself.

Pilot, verbatim: *"boresight is aircraft boresight. Fixed at aircraft coordinate axis."* So the
lamp means **sight direction = the aircraft's own axis (±~0.3°)**, and a lit lamp is a fix of
azimuth 0 / elevation 0 in the airframe frame, always inside the HUD field. Open: while the lamp is lit and commands are
ignored, is the sight caged to the airframe axis (mark fixed to the nose through a heading
change) or still gyro-held? Run 6 adds a ~3° heading change at 1:19 to tell.

### Pilot on gyro alignment, verbatim

> *"Sight sits at boresight until the gyro alignment is done. OBSERV ON, then the gyro alignment
> delay *during which* sight is locked to boresight. After alignment is done, then the sight can be
> skewed by axis commands. (The way it works for a player)"*

Against the runs (probe steps start at T+20 s after OBSERV on):

| run | first ignored | first worked | fits "locked until aligned"? |
|---|---|---|---|
| 3 | 1° L at T+28 | 2° L at T+36 | yes, if alignment took ~30 s |
| 4 | — | 1° L at T+28 | yes |
| 5a | az pulses T+40 … T+62 | elev −0.1 at T+67 | only if alignment took ~65 s |
| 5b | — | 2.5° L at T+40 | yes; **but it stopped again at T+52**, after the sight came back to boresight — alignment does not explain that |

So alignment explains the start of most runs, if it takes longer than the ~10 s assumed (BL-B80's
`GYRO_ALIGNMENT_S` = 10). 5b's re-lock does not fit. Run 6 logs lamps 957–961 every row;
960 (`SCHO_9K113_READY`) may mark alignment done.

### Pilot's own run (modified v5: alternating left/right slews), verbatim

> *"No sprict v6 yet, but I did one test of my own. I modified v5 scripts to simple slew left then
> right then left, then right, .... The croshair does move."*

No log for this run. With a continuous left/right alternation the sight keeps moving, so the
re-lock seen in 5b did not appear. 5b's re-lock came after a return to boresight with the axis at
0; this run probably never let the sight settle there.

### Pilot on the alignment-done lamp, verbatim

> *"light ROLL SYNC TR UNCAGE also by Л5 in the guidance unit illuminates when the 9K113 gyro
> alignment is done and the sight can be moved."*

So alignment completion has its own lamp on the guidance unit (Л5, "ROLL SYNC TR UNCAGE"), and the
probe can log it rather than infer alignment from the first movement. Its arg number is not yet
known (not in 957–962); to be looked up on the DCS machine and added to run 6's `WATCH_ARGS`.

### Pilot's alternating run: log (`logs/2026-10-22/aircraft_layer_probe_9k113_methods_c_pilot_alternating.log`)

Second session in the file, OBSERV on at t=38.725 = T+0. The pilot's script is not in the repo:
its log shows STEP 2/2 "AI az 2.5 R" repeating, 874 echoing +2.5 nearly throughout, yet the mark
swings both ways. So the direction actually sent cannot be read from this log alone.

| T+ | what the args show | explained by |
|---|---|---|
| 0–10 | 565 fixed at 0.5002, 555 settles to 0.833 | **caged during alignment, ~10 s** — matches the pilot's ~10 s |
| 10–20 | 565 drifts −0.004/s while heading drifts +0.1°/s, 874 = 0 | gyro free: world-held direction, the nose turning under it |
| 20–41 | 874 = **0** although the script writes; mark only drifts with heading | the writes are not landing. Unlike every earlier "ignored" phase, where 874 echoed the demand |
| 41– | 874 = 2.5, mark moves at ~0.8°/s | normal |
| 74.3–80.2 | mark **stops dead at 0.527** with 874 = +2.5, lamp 962 lit, OBSERV on throughout; resumes after **6.0 s** | **unexplained** — the 5b re-lock, reproduced |
| 183.4 | OBSERV (886) **off for ~1 s**, then on; mark snaps to boresight, held ~10 s | re-cage + realignment |
| 266 | OBSERV **off ~4 s** during a hard manoeuvre (hdg 340→004→340, pitch +5/−5); held ~12 s | re-cage + realignment |

So two of the three stalls are OBSERV cycling followed by the ~10 s realignment, and the first
gap is the alignment itself. **The one stall that is still unexplained is a sight that passes
through boresight, is caught there, and holds for about 6 s under a live command.** Run 6 now
logs every lamp change per frame, which will show whether a lamp marks that hold.

Pilot, verbatim, on the unexplained stalls:

> *"the couple of unexpected no-slew are probably me using the 9K113 view position. The script
> seems to have no effect then. That is ok."*

So the probe's writes do nothing while the player is in the operator's 9K113 sight view — the
opposite-seat rule (Petrovich only works the seat the player is not in), and accepted as correct
behaviour. That fits T+20–41 directly (874 = 0). For T+74–80 it is the likeliest explanation, but
not proven by the log: 874 kept echoing +2.5 there. Run 6 is flown from the pilot seat throughout,
so a hold that still appears there is a real gate.

## Run 6 results (`logs/2026-10-22/aircraft_layer_probe_9k113_slew_gate.log`)

Flown with the run-6 script **before** the lamp logger was added: rows carry 957–962, not 898 or
L1–L14. OBSERV on at t=30.508 = T+0. AI L → 565 down, R → 565 up; a moving 2.5° pulse gives
≈0.11–0.16 per 4 s (0.83°/s), as before.

- **Alignment ≈ 13 s.** 565 stays at 0.5001 while heading moves 341.8→338.1 (caged to the
  airframe), then from T+13–15 follows heading (world-held).
- **Lamps:** 960 READY is lit from mission start, so it is not the alignment lamp. 962 is lit for
  565 ≈ 0.473–0.530, i.e. about ±0.7° around 0.50, and at rest before OBSERV.
- **Stick park toggle:** no visible effect of its own.

| T+ | 962 lamp | AI axis |
|---|---|---|
| 20.7–24.7 | lit (sitting near boresight, axis 0) | — |
| 24–38 | off | **2.5° L and R ignored**; mark only follows heading (world-held) |
| 38–64 | lit 48.3–53.0 (sitting, axis 0); toggle #1 at 52.5 | every pulse moves |
| 64.5–66.0 | lit (passing through under command) | — |
| 72–76 | off | **2.5° L ignored**; toggle #2 at 69 |
| 87.1 | | 10° L for 0.5 s **moves** (≈1.7°), lamp lit 87.1–87.6 passing boresight |
| 90–99 | off | **elev −0.1 and 2.5° R ignored** (mark change = heading +2.7° alone) |

Reading, not yet proven: **after the sight leaves the boresight zone (962 goes off), the AI axis
is ignored for roughly 10–14 s**, the same length as the alignment after OBSERV on. Three of the four
lamp-off edges are followed by such a hold. The fourth (T+53.0) is not, and it came 0.5 s after
stick park toggle #1. Whether the 10° pulse at T+87 broke through a hold or came after one had
timed out (21 s after T+66) cannot be told. The pilot did not fly the HDG step (heading constant),
so caged vs world-held during a hold is answered only for the first one (world-held).

**Cross-check against the pilot's alternating run weakens the lamp-off-edge reading:** there the
sight passed through the zone under a live command (T+59–62, T+152–155) and kept moving. That
run never held the axis at 0. A reading that fits both logs:

> **Axis released (0) while the sight is within ~1° of boresight → small commands are ignored for
> ~10+ s.** Run 6: hold 1 sat in the zone (0.52–0.53), hold 2 at 0.529–0.533, hold 3 at
> 0.459–0.470 (zone edge 0.473–0.530); axis-0 steps far from boresight (0.35–0.39, steps 7 and
> 12) were followed by working pulses. Exception: steps 9–10 sat in the zone and step 11 worked,
> with stick park toggle #1 in between.

During a hold the mark does not snap to boresight; it stays world-held (hold 1). So this is the
axis being ignored, not a re-cage. Next run: measure the hold's length directly (release near
boresight, then probe with a 2.5° pulse every few seconds), test the toggle as a release on its
own, and log Л5 (898 and L1–L14) per frame.

Pilot, verbatim, on run 6: *"sight correctly world held at turns"* — so during the holds too the
sight keeps its world direction through turns (consistent with hold 1 in the log): the hold drops
AI-axis commands, it does not cage the sight.
