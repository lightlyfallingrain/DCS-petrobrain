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
(logged by command sign, `SEEK_POS`/`CHECK_POS`) and the opposite second (`SEEK_NEG`/`CHECK_NEG`),
and its two summary lines are literally `EDGE UP` (first direction) and `EDGE DOWN` (second) —
"UP"/"DOWN" here just means "first"/"second", not a confirmed visual direction. That's yours to
tell it.

**Simplified 2026-10-27** (pilot direction — see `plans/9k113-hud-elevation-limits-probe/
implementation.md`, "Simplified per user, 2026-10-27"): one pass per direction, no repeated
cycles, no multi-minute stall margin. Stall rejection is now the same per-frame dither
Export.lua's production sight servo already applies to this axis, plus a brief reversal: when the
mark stops moving, the probe reverses command direction for about a second — if the mark moves
again, that was the true edge; if it doesn't, it was a momentary command stall and the probe just
resumes pushing.

## Setup (Windows)

1. Back up `Saved Games\DCS\Scripts\Export.lua`, then copy the probe over it.
2. Mi-24P **air start**, guidance unit warm (an in-flight start — this project's 9K113 probes are
   always flown this way, not a cold ground start).
3. Autopilot on, **straight and level** throughout — no turns, no pitch changes. A gyro-held
   sight drifts with attitude, which would be read as elevation movement that isn't the command.
4. **DCS AI Petrovich overlay OFF** the whole flight. **No joystick axes bound to the operator's
   controls.**
5. From the **copilot seat**, switch OBSERV **on last** = **T+0**. Move to the **pilot seat**
   right after and stay there — no 9K113 view.

## Timeline (T+ from OBSERV on)

| T+ | what the probe does | what you watch |
|---|---|---|
| 0:00–0:15 | nothing (gyro sync, fixed 15 s wait) | get to the pilot seat |
| 0:15 on | elevation slews slowly one way (dither always on) until it stops moving, then briefly reverses to check it's a real edge | the crosshair moves steadily toward one HUD edge, then stops — does it rise or fall? |
| edge confirmed | logs `EDGE UP`, then slews the other way, through centre, to the opposite edge, same check | crosshair crosses back through boresight to the far edge — rise or fall this time? |
| edge confirmed | logs `EDGE DOWN`, then `PROBE DONE`, and stops writing | crosshair stays wherever it ended up — **expected**, the AI axis is a rate command and stopping it does not snap it back to boresight |

Total runtime: ~1 minute (15 s wait, plus whatever it takes to reach each edge at ~0.5°/s — a few
seconds of commanding each direction if the measured azimuth clip, ≈4.3°, is any guide). If a
sweep seems to stall near the glass centre (not visibly approaching either edge) for more than a
few seconds at a time, that is the gate-stall case above — the probe's own reversal check should
clear it on its own; just note the rough time if you see it happen more than once or twice.

## Bring back

- **Which direction (the one logged `EDGE UP`, commanded first, or `EDGE DOWN`, commanded second)
  made the crosshair rise, and which made it fall?** This is the one thing only you can tell from
  the cockpit.
- Any stall near centre rather than at an edge (see above) — note it if you see one, even though
  the probe should recover from it unattended.
- If the returned elevation half-angle reads far from the already-measured azimuth figure
  (≈4.3°), give it a second look before treating it as settled — the raw log is still the ground
  truth either way.
- `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_hud_elevation_limits.log`.

Restore the production `Export.lua` afterwards.

## Results

*(to be filled in after the flight)*
