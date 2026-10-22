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

## Setup (Windows)

1. Back up `Saved Games\DCS\Scripts\Export.lua`, then copy the probe over it.
2. Mi-24P on the ground, warm-up done. Park facing something recognisable.
3. **DCS AI Petrovich OFF** (overlay closed). Wheel hidden, as you fly normally.
4. From the **copilot seat**, switch OBSERV **on last** = **T+0**. Move to the **pilot seat**.

## Timeline (T+ from OBSERV on, ~2:30 total)

| T+ | what the probe does | what you do |
|---|---|---|
| 0:00–0:20 | nothing (gyro alignment, seat move) | get to the pilot seat |
| 0:20–0:30 | player az **+0.5**, every frame | **watch the ASP-17 mark: does it move right, and keep going?** |
| 0:30–0:35 | player az 0 | does it stay where it got to, or return to centre? |
| 0:35–0:45 | player az **−0.5** | moves left? |
| 0:45–0:50 | player az 0 | stays or returns? |
| 0:50–1:00 | player elev **+0.5** (sign-inverted, so probably **down**) | moves up or down? |
| 1:00–1:05 | player elev 0 | stays or returns? |
| 1:07 | **probe presses ShowMenu** (his AI on), AI target 20° left | does anything show on screen? mark should go 20° left |
| 1:27–2:27 | holds 20° left | **close the overlay by hand (your AI-menu key) about 3 times, ~15 s apart** — e.g. at 1:35, 1:50, 2:05. The probe should reopen it each time. |
| ~2:30 | centres everything, done | his AI is probably still on; turn it off if you like |

If his AI is already on at 1:07 the probe does **not** press, so it doesn't turn it off.

## Bring back

- **Part A, per step: did the mark move, which way, how far, and did it hold or return at the 0
  steps?** "Nothing" is a full answer.
- Part B–C: did a ShowMenu press show anything visible (wheel, text, sound)? Did the mark jump back
  to 20° left after each time you closed the overlay?
- `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_ai_latency.log`.

Restore the production `Export.lua` afterwards.
