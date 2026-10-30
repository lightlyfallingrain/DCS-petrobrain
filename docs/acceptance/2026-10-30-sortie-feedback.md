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

## 2. Hand-slew calibration, first attempt (same day, hands-off flag active)

User's words:

> *"first attempt at hand slewing. Target: truck. 9K113 on it and ASP-17 crosshair. At about 9:30 -
> 10:00 mins in the latest mission."*
>
> *"I can easily hand slew the 9K113, but then I have to give control of the aircraft to DCS AI and
> it flies horribly. It's difficult to get to a postion where the DCS AI does not mess up the test
> by bad flying."*

Logs: `dcs-slew-trace-20261030-132230.jsonl` + `aircraft_layer_slew_trace.log` (model time ends
561.7 s, so the user's "9:30-10:00" maps to the last tracked window, ~548-561 s). Hands-off
confirmed in `aircraft_layer_debug.log`; servo_mode `hands_off` throughout. The engaged target
(`engage truck 12 o'clock missiles`) is an `IKARUS Bus` at ~2.85 km. Two tracking windows:
416-443 s and 546-562 s. Mark gauge args (ARG_SIGHT_AZ/ELEV) read 0 throughout -- only 566/555
are usable.

Target truth rotated into the airframe (heading/pitch/bank), against raw 555, 53 samples:

| | boresight (raw) | deg per unit | rms |
|---|---|---|---|
| shipped | 0.83 | 27.0 (1/0.037) | |
| fit | **0.850** | **30.7 (1/0.0325)** | 0.25 deg |

At these depressions (-0.3 to -3.6 deg) the shipped calibration reads ~0.9 deg high, i.e. Petrovich
puts the mark ~0.9 deg low. The fit predicts the morning's -5.85 deg setpoint actually sat at
~-7.3 deg: 1.4 deg low, matching the screenshot. **Scale is weakly constrained**: all points sit
within 3.3 deg of each other and the aircraft was moving (DCS AI flying); a steeper point
(-6 to -10 deg) is needed before shipping a scale. Azimuth agrees to ~0.3 deg (hand-tracking noise).

## 3. Further calibration flights (same day)

**Flight 3 (hand-slew, three targets).** User: *"4:00 BTR-60, 6:55 SA-15, last 30 s rocket propelled
artillery unit ... I'm in the CPG seat and I don't know if the ASP-17 axis update then."* No truth for
the SA-15 or the artillery (neither ever entered Petrovich's simulated FOV, the only truth source
then); the mark was on the ASP-17 azimuth edge for both. The BTR-60 hold (truth reconstructed from
earlier fixes, unit stationary) showed the bus fit still ~0.3-0.5 deg high. The mark *does* update
with the user in the CPG seat.

**Flight 4 (DCS AI Petrovich tracking).** User: *"This time I used the DCS AI Petrovich (via overlay)
to track a target with the 9K113 ... That is a precise track."* No truth logged -- body-layer's
`sight_fov` only lists objects inside Petrovich's own simulated view. Also established: the gimbal
args in the Lua slew trace stay ~0, so the 555/566 mark is the only reading of 9K113 direction.

**Flight 5 (AI Petrovich tracking, `--detection-trace` on).** User: *"BMD-1 from time 1:10"*.
Detection trace gives every object's truth every poll. Object 16790016 (BMD-1) matches the mark's
azimuth to ~0.1 deg -- the tracked unit. 107 unclipped samples, 70-180 s, range 7.1 -> 2.6 km,
truth elevation -1.7 to -14.5 deg (airframe frame, heading/pitch/bank applied):

| | boresight (raw 555) | deg per unit | rms |
|---|---|---|---|
| shipped | 0.83 | 27.0 (1/0.037) | |
| bus hand-slew fit | 0.850 | 30.7 (1/0.0325) | 0.25 deg |
| **AI-track fit** | **0.8333** | **36.14 (1/0.0277)** | **0.006 deg** |

Residuals are flat across every depression band, so the gauge is linear. The hand-slew fit was
off by hand-tracking error and a too-narrow span. With the AI-track calibration the morning's
-5.85 deg setpoint sat at ~-7.9 deg. Derived field: raw clip 1.0 -> +6.0 deg, raw 0.278 -> -20.1
deg. Azimuth: shipped calibration agrees to 0.09 deg rms over this (narrow, -3..+0 deg) span; an
az-scale fit gives 1/0.0362 vs shipped 1/0.039 but the span is too narrow to trust.

Data kept: `aircraft_layer_slew_trace-20261030-140320.log` copy (the Lua log is overwritten on
DCS restarts), `body-layer/logs/*-20261030-140320.jsonl`.

## 4. First flight on the new calibration (hands-off flag removed)

User's words:

> *"Attack run was commanded, but the ASP-17 showed nowhere near the target. The debug view sometimes
> showed Petrovich looking at target, other times something completely else and wrong directions."*

Logs: `body-layer/logs/*-20261030-143312.jsonl`. Engage commands at sim 512.6 (`engage target`),
531.4 (`engage target missiles`), 743.9 (`engage target missiles`), 954.3 (`engage target`).

### Log reading (first pass)

The new calibration holds: in `closed` mode the mark sits on its setpoint to ~0.1 deg. The aim is
the problem. `aim_source` stayed `belief` through both missile runs -- never `seen`.

- Run 1 (531 s): goal azimuth near the nose, goal world elevation climbing +2.5 -> **+72 deg**; setpoint
  pinned at the +20 deg gimbal, mark parked on the ASP-17 top edge; late in the run goal azimuth
  swings to 356 then 251 deg.
- Run 2 (743 s): an MLRS group at bearing ~272 deg, el -2.4 deg in the sim FOV but not admitted
  (`terrain_los`, `range_or_size`); goal drifts 270 -> 301 deg and down to -27 deg over 45 s while the
  aircraft turns 271 -> 294 deg.

### Explored with the user

> *"I'm not sure of the target, I just commanded engage target 12 o'clock nearest. I did get guidance
> to where he believed the target was, but that was way off the actual target."*
>
> *"in debug view sight was pointing to side, also binoculars and naked eye while attack run in
> progress, which sould not happen beside the occasional quick glance around. That should be a
> *quick* glance, not many seconds."*
>
> *"Enganing a target with the 9K113 that he cannot see with 9K113 is utterly pointless. The whole
> point is that he *sees* it AND tracks it with the 9K113. This must work, it is essential. If problem
> is in incorrect belief behaviour, that must be fixed."*

Requirements taken from this:
1. During an ATGM run Petrovich **sees the target through the 9K113 and tracks it** -- the run's
   whole purpose. Aiming the sight from belief alone is pointless.
2. During a run the sight stays on the target; binoculars/naked eye only as a **quick** glance
   around, not many seconds.
3. If the belief aim is what is wrong, the belief behaviour is fixed -- not worked around.

### Run 2 traced (main loop, after the run-1 fix landed on `fix/atgm-run-sight-tracking`)

Triangulating the sight's belief goal rays over 744-787 s puts Petrovich's believed target at one
fixed point: **on the true bearing** (offset purely along the line of sight), but **~700 m short**
(believed ~1.5 km at 745 s vs the group at ~2.2-2.4 km) and **~420 m too high** (believed MSL
~1170 m = ownship altitude at the naked-eye looks, true 750 m). So run 2 has the same altitude
defect as run 1, plus a range error from the naked-eye/binocular looks (662-738 s, 4.7-5.7 km).
Bearing from those looks was good; range, and therefore depression angle, was not. As the
aircraft closed on the believed point the aim swung right and steeply down, never crossing the
real group, so the sight never admitted it.

OBSERV drops at 603.0 s and 788.4 s both coincide with hard bank (-29 deg; +24 -> +58 deg) while
`observ_commanded` stays True -- DCS dropping the sight, not Petrovich. Nothing re-acquires it.
