# 2026-10-30 — ASP-17 elevation mark (arg 555): scale and boresight fitted against a tracked target

Supersedes the scale/boresight in `2026-10-28-9k113-asp17-elevation-mark-calibration.md` (which was
gimbal-derived, never checked against a target). Flight account: `docs/acceptance/2026-10-30-sortie-feedback.md`
§1-§3.

## Method

DCS AI Petrovich (overlay) tracked a BMD-1 with the 9K113 while the pilot flew in from 7.1 to 2.6 km;
`aircraft_layer_sight_hands_off.flag` kept Export.lua's servo off the axes. Truth: body-layer
`--detection-trace` (per-object true bearing/elevation every poll), rotated into the airframe with the
slew trace's heading/pitch/bank. Mark: raw 555/566 from `aircraft_layer_slew_trace.log`, nearest frame.
The tracked unit is identified by azimuth: the mark's azimuth (shipped az calibration) matches unit
16790016 to ~0.1 deg throughout.

## Measured

| quantity | value |
|---|---|
| boresight (raw 555) | 0.8333 |
| scale | 36.14 deg/unit (1/0.0277) |
| samples / span | 107 unclipped, truth -1.7 to -14.5 deg |
| residual | rms 0.006 deg, max 0.03 deg, flat across bands (linear) |
| azimuth, shipped 0.500 / 1/0.039 | agrees to 0.09 deg rms over -3..0 deg (span too narrow to refit) |

Derived: raw clip 1.0 -> +6.0 deg, raw 0.278 -> -20.1 deg (past the -15 deg gimbal).

## Also established

- The gimbal args the Lua slew trace logs as `az`/`elev` stay ~0 -- the 555/566 mark is the only
  readable 9K113 direction.
- The mark updates with the player in the CPG seat.
- Hand-slewing gave a biased fit (0.850 / 1/0.0325): hand-tracking error plus a 3 deg span.
- `aircraft_layer_slew_trace.log` is overwritten on DCS restart -- copy it after each flight.

Data: `body-layer/logs/*-20261030-140320.jsonl` and `aircraft_layer_slew_trace-20261030-140320.log`
(gitignored, local).
