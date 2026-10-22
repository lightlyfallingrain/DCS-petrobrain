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
