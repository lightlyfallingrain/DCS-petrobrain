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
| 0:20 on | **cycle 1 POS**: elevation slews slowly one way until it stops moving (plateau), holds ~20 s more to confirm, then reverses | the crosshair moves steadily toward one HUD edge, then stops — does it rise or fall? |
| — | **cycle 1 NEG**: slews the other way, through centre, to the opposite plateau | crosshair crosses back through boresight to the far edge — rise or fall this time? |
| — | repeats POS/NEG two more times (3 cycles total) | the crosshair should stop at the *same* two edges each time |
| after cycle 3 | nudges back toward the last edge reached (a few seconds, not a precise re-centre), then stops writing | crosshair settles a few degrees off true centre — **expected**, not a sign the probe failed (the AI axis is a rate command, so stopping the command does not snap it back to boresight) |

Total runtime depends on how far the edges are from boresight and whether the known AI-axis
command gate fires — likely 4–8 minutes (longer than earlier 9K113 probes: the hold that confirms
each plateau was lengthened past the gate's documented 4–18 s window, see below). If a sweep seems
to run unusually long (over ~60 s without the crosshair stopping), that is the probe's own timeout
logging "no plateau found" for that leg and moving on; nothing to do.

**What a gate-stall looks like by eye, and what to do about it.** This project has previously
measured the 9K113 AI axis intermittently ignoring a held command for 4–18 s at a stretch, and once
for an entire flight. If that happens right as a seek begins, the crosshair can sit almost exactly
where it started — near the glass centre, not visibly approaching either edge — while the probe is
still in a seek segment pushing it. The probe now defends against this itself (it logs `SUSPECT`
rather than accepting a near-zero-travel stop as a plateau, and keeps retrying), but **watch for it
anyway**: if you see the crosshair stall near centre rather than approaching an edge for more than a
few seconds, note it and the rough time, and flag that leg for a re-check even if the log's own
`SUMMARY` line comes back clean — your eyes are the backstop against the log's own logic being
wrong.

## Bring back

- **Which direction (POS, commanded first, or NEG, commanded second) made the crosshair rise, and
  which made it fall?** This is the one thing only you can tell from the cockpit.
- **Did the crosshair visibly stop at the same two edges on all three cycles**, or did a sweep run
  further/stop short on some cycles? (The log's own `SUMMARY` lines answer this mechanically, but
  your eyes are the check against the log being wrong.)
- Any stall near centre rather than at an edge, per "What a gate-stall looks like by eye" above —
  the probe's own `SUSPECT`/`STALL not a clip` logging should already catch these, but note it if
  you see one.
- If the returned elevation half-angle reads far from the already-measured azimuth figure
  (≈4.3°), give it a second look before treating it as settled — the raw log is still the ground
  truth either way.
- `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_hud_elevation_limits.log`.

Restore the production `Export.lua` afterwards.

## Results

*(to be filled in after the flight)*
