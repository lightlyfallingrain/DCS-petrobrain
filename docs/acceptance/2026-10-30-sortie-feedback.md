# Sortie feedback — 2026-10-30

Sortie logs: `body-layer/logs/*-20261030-113535.jsonl` (slew trace, speech), `dcs.log` symlinked
there. Screenshot: `img/2026-10-30-atgm-mark-low.webp`.

## 1. ATGM run: sight mark correct in azimuth, low in elevation

User's words:

> *"There are two target in HUD. One a bit to right and one exacly under the crosshair line. The
> latter is the target (engage commanded). Azimuth of crosshair is correct, but vertical position is
> clearly below the actual target."*

Commands that sortie (speech log): `set target ahead nearest` (t=522), `engage missiles` (556),
`step right` (588).

### What the logs say (first reading — not yet explored with the user)

Slew trace at t=590.3, target BTR-70 at 1830 m:

| quantity | value |
|---|---|
| target true world el / bearing | −5.17° / 283.53° |
| Petrovich's head goal world el / az | −5.12° / 283.28° |
| ownship pitch | +0.73° |
| servo setpoint (body el) | −5.858° |
| mark readback (body el, via calibration) | −5.854° |

So Petrovich's modelled aim is on the target, and the servo holds the mark at its setpoint to
0.004°. Every step is consistent **in the code's own degrees**. The mismatch the user sees is
therefore in the conversion from the 555 mark gauge to degrees — `MARK_BORESIGHT_EL = 0.83`,
`MARK_DEG_PER_UNIT_EL = 1/0.037` (`aircraft-layer/dcs-export/Export.lua`). That scale was chosen by
argument, not measurement, at the 2026-10-28 merge
(`plans/9k113-sight-pointing/review-el-field.md`, "Calibration-scale opinion"), which recommended a
dedicated calibration flight. The rejected flight-derived 1/0.030 would put this mark ~1.4° lower
in DCS's real degrees than the code believes — the same direction as observed. A boresight error
would too. One observation cannot separate scale from boresight.

Screenshot: mark cross ~80 px below the target at 2000 px width; the angular size depends on the
view FOV, which is not known, so no degree figure is claimed from it.

Consequence: in DCS the missile follows the sight line, so a low mark means ATGM shots hit short.
This sits on `[[BL-B80]]` (pointing accuracy) and gates BL-B67 Stage 8.

### Explored with the user

> *"I was hovering, it stayd where it was once it moved for the attack run."*

Constant geometry, so one calibration point only — scale vs boresight not separable from this
sortie.

Calibration method, user's choice between two:

> *"I can point the 9K113 by hand - Petrovich *must not* write axis values then. This would be the
> most reliable measurement of 9K113 vs ASP-17 alignment"* — chosen.
>
> *"I can manipulate the ASP-17 to point at a target, but then 9K113 sight is separate from that
> and I would not move it"* — rejected: calibrates the gunsight, not the missile's line.

Consequence: today `run_sight_servo` writes the AI axis every frame while OBSERV and the align lamp
are on, even with no goal (`hold` dithers). A hands-off switch is needed that suppresses **every**
axis write, while the Lua slew trace (raw 555/566 + gimbal args, all modes) and body-layer's trace
(per-object truth elevation, attitude) keep logging. Two depression angles (near and far target,
hovering) give boresight and scale.
