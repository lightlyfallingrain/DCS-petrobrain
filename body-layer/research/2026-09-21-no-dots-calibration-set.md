# No-dots calibration set — ranges, and what the columns can support

**Captured 2026-09-21** by the user, detection-aid dots **off**, at
`win-mac-sync/from-windows/screenshots/no-dots-calibration-images/` (25 PNGs). Replaces the
naked-eye and binocular halves of the contaminated 2026-09-17 ladder. The 9K113 columns of that
ladder remain valid and are not re-shot (user: the dots do not affect the sight views).

Pattern per rung: **map image showing the F10 ruler range, then naked eye, then zoomed view.**
**Approach was at ~60° AOB** — which matters, since aspect drives recognition.

**Altitude: ~750 m MSL but 100–130 m AGL** (user correction, 2026-09-21; the cockpit shows
`ALT 138 R`, the radar altimeter, confirming it). Terrain is therefore ~620–650 m MSL. The
distinction is not cosmetic — three consequences follow, and two of them are reassuring.

| range | depression angle | height foreshortened to |
|---|---|---|
| 0.248 km | 24.9° | 91% |
| 0.509 km | 12.7° | 98% |
| 1.00 km | 6.6° | 99% |
| 1.91–9.28 km | 3.4°–0.7° | ~100% |

**1. The ladder is not constant-geometry**, running from a 24.9° look-down at the nearest rung to
0.7° at the farthest.

**2. But the foreshortening that implies is negligible here** — 9% at the closest rung and ≤2%
beyond 0.5 km. `object_model.apparent_extent_m` deliberately ignores the observer's look-down angle
when foreshortening `height_m`, flagged in `plans/aspect-aware-profiles/plan.md` as *"correct at the
shallow depression angles typical of level cruise, wrong in the limit of looking straight down."*
**This set stays inside that assumption**, so the simplification is safe for fitting against it. A
steep-dive set would not be, and should not be fitted with the same model.

**3. At ~115 m above the targets, ED's own altitude-dependent visibility formula gives 10.4 km** —
`visibility_km = 10 · e^(0.3588 · (detector_km + target_km))`, from
`aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` finding 7. That is
essentially the existing flat `NAKED_EYE_RANGE_CAP_M = 10000`, so **the cap is correct for this
flight profile** and the altitude-dependent improvement the deep read proposed only matters at
higher altitude (600 m → 12.4 km, 2 km → 20.5 km).

**Consequence for grading the top rung:** 9.28 km sits close to that 10.4 km atmospheric limit, so a
"nothing visible" there may be **haze rather than acuity** — a different failure from the one the
thresholds model. Grade it, but do not let it drive the constants.

## The ranges

Read off the F10 ruler in each rung's map image.

| # | range | target |
|---|---|---|
| 1 | 0.248 km | twelve-unit complex |
| 2 | 0.509 km | " |
| 3 | 1.00 km | " |
| 4 | 1.91 km | " |
| 5 | 3.00 km | " |
| 6 | 4.00 km | " |
| 7 | 5.44 km | " |
| 8 | **9.28 km** | **S-300 complex** (SA-10 TR/SR, SA-15, Smerch, BM-27, HL B8M1) |

Rung 8 is a different target group and belongs in its own row, not as the top rung of the vehicle
ladder. It is the tall-mast case the model was 4× short on before aspect-aware profiles landed.

## What each column can and cannot support

**The naked-eye column is sound.** Default cockpit FOV, reproducible. This is the column that
matters most: the naked eye is `check_visibility`'s default optic as of cones slice 1, and the
`LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD` thresholds are meant to be **optic-independent acuity
constants** — fitting them on the unaided column is correct.

**The "binocular" column cannot calibrate `BINOCULAR_OPTIC`** (user, 2026-09-21):

> *"binocular view is not precise, there is no binocular in DCS, it's a zoomed in FOV that I set
> myself. But once I reset and zoom in again, it's not exactly same FOV, just approximately."*

An approximately-reproduced hand-set FOV has an **unknown magnification that varies between shots**.
A per-tier multiplier fitted to it is fitted to an uncontrolled variable.

### This reaches backwards, into constants already shipped

`BINOCULAR_OPTIC`'s per-tier multipliers — **2.42 / 3.50 / 3.00**, in `perception/optics.py` since
cones slice 2A — were derived from the 2026-09-21 BTR-60 four-instrument table, whose "binocular"
column is **this same hand-set zoom**. So those numbers describe *the zoom setting in use that day*,
not a Б-6 6×30. **The model names an instrument it is not calibrated to.**

**What survives, and it is most of the value.** The *shape* findings do not depend on knowing the
magnification:

- presence scales **sub-linearly** with magnification while class scales **supra-linearly** — the
  finding that retired the single-multiplier model;
- the **distinctiveness clamp** (infantry class range = presence range at every instrument);
- **aspect drives recognition, not detection** (presence identical at every AOB).

Each is a ratio *between* columns or *within* one, and is unaffected by the absolute magnification
being unknown.

**What does not survive:** the claim that 2.42 is a Б-6 6×30 minus a 0.67 stabilisation penalty.
That derivation was already withdrawn once as circular (see
`2026-09-21-aspect-magnification-and-distinctiveness.md`); this removes its remaining footing. The
value may still be a reasonable *effective* multiplier for "a magnified view" — it is simply not
attributable to a named instrument.

## Resolution: anchor the zoom to the 9K113 wide (user decision, 2026-09-21)

> *"The binocular FOV has been approximately same, though not exact. The 9K113 wide is close enough
> and very stable, we can use that to calibrate the binoculars and then apply a factor."*

This inverts the dependency and fixes the provenance problem without new data. Rather than
calibrating an uncontrolled view directly, **measure it against a stable instrument with a published
specification** and express it as a ratio.

Worked from the BTR-60 table's **AOB 90° rows**, so aspect matches between the two columns:

| tier | zoom ÷ 9K113 wide | 9K113 wide multiplier | derived zoom multiplier | currently shipped |
|---|---|---|---|---|
| presence | 0.682 | 3.55 | **2.42** | 2.42 |
| class | 0.500 | 7.00 | **3.50** | 3.50 |
| type | 0.462 | 6.50 | **3.00** | 3.00 |

**The numbers do not move** — same data, different route. **The provenance does**, and that was the
defect. `BINOCULAR_OPTIC`'s multipliers now express as *"0.68 / 0.50 / 0.46 of the 9K113 wide's
measured effect"*, anchored to a documented ×3.3 stabilised sight whose own calibration column is
uncontaminated. They no longer rest on a zoom setting nobody can reproduce.

**The per-tier ratios differ, and that is signal rather than noise.** 0.68 at presence against 0.46
at type says a lower-magnification view loses proportionally *more* at the recognition tiers than at
detection — which is the sub-linear-presence / supra-linear-class finding arriving from a third
independent direction.

**The procedure this gives for future sets:** capture the zoom column *alongside* the 9K113 wide at
the same ranges and aspect, take the ratio, multiply by the sight's own multipliers. The anchor stays
stable even when the zoom drifts between sessions, so the drift stops mattering.

**One consequence worth noting:** this makes the 9K113's calibration data load-bearing *before* the
9K113 slice exists (it is deferred in `todo/todo.md`). That is fine — the data is already captured
and uncontaminated — but the deferred slice now has a second reason to be built, and its columns
must not be discarded as belonging only to a future milestone.

## Recommendation for the next set

**Fix the zoom to a repeatable setting** before capturing another magnified column, or the same
problem recurs. Options, cheapest first:

1. **Capture the FOV itself.** If the zoom level can be read or set numerically, record it per shot
   and the magnification follows.
2. **Derive it from the screenshots.** Two units of known map position subtend a known true angular
   separation; their pixel separation across a frame of known width gives the FOV directly. Fiddly
   but needs no new capture — the map image in each rung already carries the positions.
3. **Give up on a magnified column** for threshold work and calibrate only the naked eye, taking the
   optic multipliers from the 9K113's *specified* magnifications (×3.3 / ×10) instead, which are
   real instrument figures rather than a user-set view.

**Superseded by the resolution above**, which takes option 3's insight — the 9K113 is the only
magnified instrument here with both valid data and a documented specification — and uses it as an
*anchor* rather than a replacement, keeping the zoom column usable instead of discarding it.

## Grades

**Not yet recorded.** Grading was deliberately not done from these files by the assistant: they are
served at 2000×1125, downscaled from the 3840×2160 originals — half linear resolution, a comparable
loss to the JPEG artifacts that hid roughly one tier in the superseded set. Grades must come from
the originals, at native resolution, by the user.
