# No-dots calibration set — ranges, and what the columns can support

**Captured 2026-09-21** by the user, detection-aid dots **off**, at
`win-mac-sync/from-windows/screenshots/no-dots-calibration-images/` (25 PNGs). Replaces the
naked-eye and binocular halves of the contaminated 2026-09-17 ladder. The 9K113 columns of that
ladder remain valid and are not re-shot (user: the dots do not affect the sight views).

Pattern per rung: **map image showing the F10 ruler range, then naked eye, then zoomed view.**
Ownship ~750 m throughout. **Approach was at ~60° AOB** — which matters, since aspect drives
recognition.

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

Option 3 is worth weighing seriously: the 9K113 columns of the old ladder are uncontaminated and its
magnifications are documented, so it is the only magnified instrument in this project with both
valid data and a known specification.

## Grades

**Not yet recorded.** Grading was deliberately not done from these files by the assistant: they are
served at 2000×1125, downscaled from the 3840×2160 originals — half linear resolution, a comparable
loss to the JPEG artifacts that hid roughly one tier in the superseded set. Grades must come from
the originals, at native resolution, by the user.
