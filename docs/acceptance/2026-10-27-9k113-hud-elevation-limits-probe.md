# 9K113 HUD elevation limits probe

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #sight-slew
**Flight for:** [[BL-B80]]
<!-- doc-provenance:end -->

**Branch: `probe/9k113-hud-elevation-limits`.** Script:
`aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua`.
Nothing else of ours needs to run.

**Why.** The ASP-17 HUD field's azimuth clip is already measured (565/566, ≈ ±4.3°,
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` line 423). The elevation clip (555/556)
never has been — v3 of `plans/9k113-sight-pointing/plan.md` ships a placeholder elevation
half-angle for the edge-park design pending exactly this flight (pilot, 2026-10-26, verbatim:
*"Elevation - measure in flight"*). User request, verbatim: *"create a probe for measuring the HUD
elevation limits. slew up until limit, then down until limit and log the values. That'll then be
super easy to measure."*

**What the probe does not know.** Which signed elevation command moves the crosshair visually
*up* on the glass has never been nailed down in this project (one earlier run called it
"sign-inverted, so probably down" and left it unconfirmed). The probe commands one direction first
(logged as `POS`) and the opposite second (`NEG`), sweeping between the two edges three times, and
leaves the up/down labelling to you.

## Setup (Windows)

1. Back up `Saved Games\DCS\Scripts\Export.lua`, then copy the probe over it.
2. Mi-24P **air start**, guidance unit warm (an in-flight start — this project's 9K113 probes are
   always flown this way, not a cold ground start).
3. Autopilot on, **straight and level** throughout — no turns, no pitch changes. A gyro-held
   sight drifts with attitude, which would be read as elevation movement that isn't the command.
4. **DCS AI Petrovich overlay OFF** the whole flight. **No joystick axes bound to the operator's
   controls.**
5. From the **copilot seat**, switch OBSERV **on last** = **T+0**. Move to the **pilot seat** by
   T+0:20 and stay there — no 9K113 view.

## Timeline (T+ from OBSERV on)

| T+ | what the probe does | what you watch |
|---|---|---|
| 0:00–0:20 | nothing (gyro alignment, seat move) | get to the pilot seat |
| 0:20 on | **cycle 1 POS**: elevation slews slowly one way until it stops moving (plateau), holds a few seconds more to confirm, then reverses | the crosshair moves steadily toward one HUD edge, then stops — does it rise or fall? |
| — | **cycle 1 NEG**: slews the other way, through centre, to the opposite plateau | crosshair crosses back through boresight to the far edge — rise or fall this time? |
| — | repeats POS/NEG two more times (3 cycles total) | the crosshair should stop at the *same* two edges each time |
| after cycle 3 | nudges back toward the last edge reached, then centres and stops writing | crosshair settles, no further movement |

Total runtime depends on how far the edges are from boresight — likely 2–4 minutes. If a sweep
seems to run unusually long (over ~30 s without the crosshair stopping), that is the probe's own
timeout logging a "no plateau found" for that leg and moving on; nothing to do.

## Bring back

- **Which direction (POS, commanded first, or NEG, commanded second) made the crosshair rise, and
  which made it fall?** This is the one thing only you can tell from the cockpit.
- **Did the crosshair visibly stop at the same two edges on all three cycles**, or did a sweep run
  further/stop short on some cycles? (The log's own `SUMMARY` lines answer this mechanically, but
  your eyes are the check against the log being wrong.)
- Anything that looked like a stall rather than a real stop (crosshair pauses mid-glass, then
  resumes) — the probe's own margin-push should already tell these apart and log them as `STALL
  not a clip`, but note it if you see one.
- `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_hud_elevation_limits.log`.

Restore the production `Export.lua` afterwards.

## Results

*(to be filled in after the flight)*
