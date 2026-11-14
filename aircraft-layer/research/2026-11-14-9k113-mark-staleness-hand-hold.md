# 2026-11-14 — 9K113 mark (args 555/566) is fresh only while the sight is being slewed

Flight account: `docs/acceptance/2026-11-14-9k113-hands-off-calibration-sortie.md`. Builds on
`2026-10-30-9k113-asp17-elevation-mark-flight-fit.md`, which it confirms. Its "−15° gimbal" premise
is not confirmed (see below).

## Method

The pilot hand-held a static BMD-1 in the 9K113 sight with the hands-off flag active, twice, in a hover.
Truth was the unit's position from the session's LoGetWorldObjects dump (aircraft_layer_debug log). Ownship
position, heading, pitch and bank came from body-layer `dcs-slew-trace` jsonl. Both were rotated into the
airframe. Mark values are raw 555/566 from `aircraft_layer_slew_trace.log`, converted with the shipped
calibration (el 0.8333, 1/0.0277; az 0.500, 1/0.039). The Lua trace and the jsonl share a time base
(both end at t = 1173.1).

## Measured — hold 2 (3.0 km, 506 m AGL, truth el ≈ −10°)

| elevation mark age (since raw 555 last changed) | n | mark − truth (airframe) |
|---|---|---|
| < 0.3 s (pilot slewing) | 18 | **+0.02° ± 0.06°**, max 0.20° |
| 0.3–2 s | 11 | −0.39° ± 0.71° |
| > 2 s | 155 | −0.93° ± 0.31°, max 1.49° |

Azimuth (almost always fresh, n = 184): −0.10° ± 0.43° over −1.5…+3°.

Raw 555 stayed at exactly **0.5304 for 60 s** (t 1104–1166) while the airframe pitch eased from 1.2° to 0.1°.
The target's horizon-referenced elevation held at −9.72° ± 0.03°, so its elevation relative to the airframe
rose by 1.1°. The mark did not move.

## Conclusions

1. **The 10-30 elevation calibration holds at 3 km / −10°.** Fresh samples agree within 0.06° (1 sd),
   with no refit needed. Azimuth calibration also agrees across its narrow span.
2. **The mark is a stale reading whenever nothing is slewing the sight.** It does not follow the
   airframe's motion under a stabilised line of sight. In a hand-hold the reading drifts by the
   airframe's attitude change since the last input, measured here up to 1.5°.
   The 10-30 fit did not see this because Petrovich slewed continuously. A horizon-referenced mark is
   ruled out: the 10-30 flight flew at about −2.6° pitch, which predicts the opposite sign to the error
   seen here.
   *Consequence:* anything that reads 555/566 as "where the sight looks now" is only right while it is
   also driving the sight, as the servo does. A belief or debug view that reads the mark during a
   hold, or after the servo goes quiet, inherits the error.
3. **Hold 1 cannot be used.** Truth was el −31°, az +8…+12°. The elevation mark was pegged at raw
   0.0149 → 0.0000 (≈ −30°) and azimuth at its clip of 0.6667 (+4.3°) for the whole hold. That gives the
   mark's display limits (az ±4.3°, el floor ≈ −30°), not a calibration point.
   The pilot reports holding the target in the sight there. If that is right, the DCS 9K113 depresses to at least −31°.
   That contradicts the −15° gimbal limit sourced from the real-system manual
   (`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`). The mark cannot confirm it.
   **Unverified; a hold at about −20…−25° inside the mark's range would settle it.**

## Second sortie (stamp `20261114-224028`): BTR-60 at 1.07 km, 189 m AGL, el ≈ −11°

| | n | mark − truth |
|---|---|---|
| elevation, fresh (< 0.3 s) | 12 | **+0.06° ± 0.01°** |
| elevation, stale (> 2 s) | 71 | −0.46° ± 0.40° |
| azimuth, fresh | 85 | −0.01° ± 0.27° |

The stale elevation error regresses on airframe pitch with **slope 1.27, residual 0.08°**. The error
is the attitude change since the last slew input, which confirms conclusion 2 with a second target and
range. It was the same −11° band as hold 2, so it adds nothing below −15°.

Limit sweep: azimuth reached the mark's clip on both sides (raw 0.3333 / 0.6667 = ±4.27°) and stayed
there for 12–13 s each. **The mark cannot show where the sight's own azimuth stops.** Elevation moved
only from −11.4° to −3.3° before the log ended at t = 435 s, so it reached neither stop. The gimbal
args (`az`/`elev`) stayed at 0 throughout, as before.

## Next instrument, if the limits matter

The 555/566 mark cannot measure the sight's limits: it clips at ±4.3° in azimuth and about −30° in elevation, and it is stale
between inputs. **`LoGetCameraPosition()` while the player is in the 9K113 view** may give the sight's
actual line of sight directly. That is unverified: it assumes the view camera is bound to the sight
LOS. Only reading is proposed here. The 2026-09-11 rejection (`2026-09-11-petrovich-detection-readout.md`)
is of *setting* the camera.

## Not established

The mechanism behind the staleness: update-on-input, or a body-relative value that is not recomputed
under stabilisation. The finding about when the mark can be trusted is the same either way.
