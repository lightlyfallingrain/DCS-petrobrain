> **CORRECTION 2026-09-21 — the ladder this document derives from is contaminated, and two of its
> conclusions no longer hold.**
>
> 1. **The screenshots were captured with DCS's "detection aid dots" ENABLED** (user, 2026-09-21).
>    DCS draws a small dark dot at a target to make it findable at long range. Every grade in the
>    ladder below therefore records what was visible *with that aid*, not unaided visibility, and is
>    **optimistic by an unmeasured amount that grows with range**. The constants derived here
>    (`LOWRES` 0.003 / `MEDRES` 0.014 / `HIRES` 0.028 / cap 10000) were fitted to aided data. **Do
>    not derive new constants from this ladder without re-shooting with the aid off** — a dots-off
>    re-shoot is the one remaining precondition for threshold recalibration
>    (`2026-09-21-calibration-target-decided.md`). The fixture carries the same warning
>    (`body-layer/tests/fixtures/vision_calibration.json`, `_comment`); the tests over it still pass
>    and are kept as a regression guard against the model as fitted, but they are **no longer
>    evidence about human visibility**.
>
>    Note what the contamination does *not* explain: the 2026-09-21 sortie found the model sees too
>    *little* at the presence tier. The aid biases this data optimistic, which would push the model
>    the other way — so the presence shortfall is a separate error, not a consequence of the dots.
>    See `2026-09-21-first-cones-sortie-results.md`.
>
> 2. **"`BINOCULAR_RANGE_MULTIPLIER = 4.0` survived untouched" is no longer true.** The constant is
>    **retired** (cones slice 2A). A single magnification applied uniformly to all three tiers is
>    the premise that measurement killed: presence scales sub-linearly with magnification while
>    class and type scale supra-linearly
>    (`2026-09-21-aspect-magnification-and-distinctiveness.md` Finding 2). `perception/optics.py`
>    now carries per-tier multipliers instead (`BINOCULAR_OPTIC` 2.42 / 3.50 / 3.00), and
>    `visibility.py` no longer declares the constant at all.
>
> **Why the contamination was plausible to miss:** the capture protocol was rigorous about the
> thing that had burned Pass 1 — compression — and lossless PNG was treated as settling the
> "is the instrument honest" question. An in-sim visibility aid is a *different* instrument defect
> in the same place, and nothing in the images announces it. Everything else below stands: the
> method, the cross-optic apparent-angular-size agreement, and the Pass 1 correction are unaffected.

# Vision range calibration — Pass 2 (lossless screenshot ladder)

**Date:** 2026-09-17
**Subject:** `body-layer/src/perception/visibility.py` — recognition-tier range constants
**Source data:** `win-mac-sync/from-windows/screenshots/` (52 lossless PNGs, gitignored;
transcribed into `body-layer/tests/fixtures/vision_calibration.json` as the `png-2026-09-17` set)
**Supersedes:** the Pass 1 finding in `2026-09-17-vision-range-calibration.md` — see
"Correction to Pass 1" below. That document's central claim was an artefact of JPEG compression.

## What was captured

One target complex, photographed at nine ranges as ownship closed from 8.89 km to 503 m. Flat
desert, unobstructed, clear weather, Syria, 2020-06-01 ~0802–0825, ownship ~750 m MSL / ~195–200 m
radar altitude, hovering to slow forward flight.

Twelve units, laid out in a line roughly 200 m end to end (first frame is an F10 map showing the
roster): SA-3 launcher, SA-3 TR radar, ZU-23 on a Ural, ZSU-23-x, BMP-1, BTR-70, T-72B, Ural,
BM-21, and three AK infantry.

Each range contributes five frames: an F10 map view carrying the ruler's ground-truth range and
bearing, then the same scene through four optics — **naked eye** (unaided cockpit view),
**binocular** (the zoomed cockpit view), **9K113 wide**, and **9K113 narrow**. At the closest
ranges the narrow sight needed several frames to cover the whole line.

Grading was done from native-resolution crops of the original 3840×2160 frames, not from a
downscaled view — at 8.89 km the targets occupy a handful of pixels, and downscaling alone is
enough to erase them.

## The ladder

Graded against the presence/class/type lattice `classification.py` already defines:
`nothing` → `marginal_speck` → `speck_no_class` (presence) → `class_recognizable` →
`type_recognizable`.

| Range | Naked eye | Binocular | 9K113 wide | 9K113 narrow |
|---|---|---|---|---|
| 8.89 km | marginal speck | speck, no class | speck, no class | class |
| 6.58 km | marginal speck | speck, no class | speck, no class | class |
| 5.04 km | marginal speck | speck, no class | speck, no class | class |
| 3.99 km | marginal speck | speck, no class | speck, no class | class |
| 2.99 km | speck, no class | speck, no class | speck, no class | **type** |
| 1.99 km | speck, no class | **class** | **class** | type |
| 1.50 km | speck, no class | class | class | type |
| 1.00 km | speck, no class | **type** | class | type |
| 0.503 km | **class** | type | **type** | type |

Bold marks each column's first appearance of a tier — the boundaries the constants are derived
from.

## The key result: one threshold set, magnification supplies the rest

Read as *apparent* angular size (true angular size × the optic's magnification), the four columns
collapse onto a single set of tier thresholds. For a 7 m vehicle:

| Tier | Naked eye | Binocular (×4) |
|---|---|---|
| class | 7 / 503 = **0.0139 rad** | 7 / 1990 × 4 = **0.0141 rad** |
| presence | 7 / 2990 = 0.0023 rad (bound) | 7 / 8890 × 4 = 0.0032 rad (bound) |

The two class figures agree to within 2%. That is the whole calibration in one line: **the tier
thresholds are properties of the eye, and the optic only multiplies the angle.** It is also why
this milestone did not need a per-optic dimension in `visibility.py` — retuning three angular
constants was sufficient, and `BINOCULAR_RANGE_MULTIPLIER = 4.0` survived untouched.

The 9K113 columns fall out of the same model: narrow resolves class at 8.89 km, implying roughly
18× magnification, and wide resolves class at ~2 km, implying roughly 4× — the same apparent-size
thresholds, different glass. Those two columns are recorded in the fixture but not modelled in
code; they are the founding evidence for the deferred "attention direction and detection cones"
milestone, which owns the per-optic split.

## Constants, before and after

Derived from the binocular column (the channel `visibility.py` models), using the module's own
`range = size / threshold × multiplier` formula and a 7 m reference vehicle.

| Constant | Was | Now | Derivation | Effect on a 7 m vehicle |
|---|---|---|---|---|
| `HIRES_ANGULAR_RADIUS_RAD` | 0.02 | **0.028** | type first resolved at 1000 m, not 1500 m | type range 1400 m → 1000 m |
| `MEDRES_ANGULAR_RADIUS_RAD` | 0.008 | **0.014** | class first resolved at 1990 m, not 2990 m | class range 3500 m → 2000 m |
| `LOWRES_ANGULAR_RADIUS_RAD` | 0.0043 | **0.003** | presence still unmistakable at 8890 m (bound, not boundary) | presence range 6511 m → 9333 m |
| `NAKED_EYE_RANGE_CAP_M` | 5000 | **10000** | 8.89 km observations were being clipped by the cap | cap no longer binds ground vehicles |
| `BINOCULAR_RANGE_MULTIPLIER` | 4.0 | 4.0 | unchanged — validated by the cross-optic agreement above | — |

**The old constants were wrong in both directions at once**, which is why no single-sign
correction would have fixed them:

- The classification tiers were far too generous — class claimed out to 3.5 km where the player
  resolves it at 2 km.
- The presence tier was too strict, and the 5 km cap stricter still — a row of ground vehicles is
  plainly visible at 8.89 km, and the old gate rejected it outright.

Both are no-omniscience violations. The second is the one that gets overlooked: Petrovich failing
to see what the player can plainly see is as wrong as him seeing through terrain, and it is the
failure mode that makes a crew member feel blind rather than psychic.

## Correction to Pass 1

`2026-09-17-vision-range-calibration.md` concluded that **class was never resolvable through
binoculars at any tested range, down to 895 m**, and recommended making `medres`/`hires`
unreachable. That conclusion is **false**, and the mechanism is instructive.

Pass 1's images were compressed JPEGs. At 955 m and 895 m they showed only presence; this lossless
ladder shows *type* at 1000 m — a better grade at a **longer** range. No property of the scene
explains that. Compression loss does: the artefacts erase exactly the low-contrast, few-pixel
detail that distinguishes a turret from a hull.

Pass 1 was not careless about this — it graded conservatively and labelled every row
"JPEG-compressed screenshot; real in-game visibility is likely marginally better." The error was
in the size of the correction assumed: "marginally" was doing far too much work. The gap was a
full tier, and a full tier was enough to invert the conclusion from "the code over-claims class by
3–5×" to "the code over-claims class by ~1.8× and under-claims presence by 1.4×."

The Pass 1 rows are kept in the fixture as `source_set: "jpeg-2026-09-17"` with
`authoritative: false`, and `test_jpeg_set_is_excluded_and_understates` pins the contradiction so
nobody folds them back in as extra data.

**Transferable lesson:** a lossy screenshot is not conservative evidence for a perception
threshold, it is *wrong* evidence. When the measurement is "how few pixels of detail survive,"
the codec is part of the instrument. Capture lossless or do not capture.

## Defect surfaced by the retune

Widening the detection envelope exposed a real contact-association defect, now tracked in
`body-layer/ROADMAP.md` and pinned by a strict `xfail` in
`tests/test_mock_flight_chain.py::test_two_real_objects_stay_two_contacts`.

In the canonical mock flight, two real objects 400 m apart (a Ural at x=1400, infantry at x=1800)
used to end as two contacts. With the calibrated envelope the infantry is first seen at ~2 km
instead of ~1.6 km, where the naked-eye range bucket is coarse enough that its implied position
overlaps the truck's contact. `ContactStore.ingest` merges rather than founding a second contact —
and `object_id` continuity then keeps that false merge alive for the whole flight, even as the
range closes and the two separate cleanly.

This is precisely the false-merge risk BL-2.6 flagged when the symmetric gate widened. Seeing
further means seeing more coarsely first, so every contact now enters the store through a
wider-uncertainty door. Worth fixing before the envelope is widened again by a longer ladder.

## `object_type` provenance (carried forward from Pass 1)

`object_model.profile_for` resolves only raw `LoGetWorldObjects` type strings. The `object_type`
values in the fixture are DCS F10 map *display labels*, which is what the screenshots provide, and
several do not resolve: the hyphenation and abbreviation differ (`"T-62"` vs raw `"T-62M"`,
`"BMD1"` vs `"BMD-1"`), and the SA-10/SA-15/HL B8M1 entries have no keyword at all. Unresolved
types fall back to `DEFAULT_SIZE_M = 5.0` / `DEFAULT_OP_CLASS`.

The fixture therefore records each object's `size_m` as independently-known ground truth rather
than reading it back from `profile_for`, and the derivations above use 7.0 m for the reference
armored vehicle on that basis. The lookup gap is real and still open — it means a live sortie
against these same unit types would compute thresholds from a 5.0 m default rather than their true
size — but it does not affect this calibration, which never calls `profile_for`.

## Known gaps

- **Nothing beyond 8.89 km.** `LOWRES_ANGULAR_RADIUS_RAD` is an upper bound, not a measured
  boundary — presence was still obvious at the farthest range photographed. A longer ladder would
  push it lower again, and `NAKED_EYE_RANGE_CAP_M = 10000` is a sanity bound, not a measurement.
- **Nothing below 503 m.** The unaided column reaches only `class` at its closest point, so the
  naked-eye type threshold is unmeasured.
- **One condition.** Flat desert, unobstructed, clear, one theatre, one time of day, one altitude
  band. Nothing here calibrates contrast against cluttered or vegetated backgrounds, haze, dusk,
  night, or rain — `min_contrast_f` / `min_fog_transparency` remain entirely unaddressed, as
  `visibility.py`'s own docstring has always admitted.
- **One target size band.** Every derivation uses the 7 m armored reference. Infantry (1.8 m)
  ranges follow from the formula, not from measurement: the ladder shows infantry as stalks at
  1.99 km through binoculars, consistent with a 2400 m presence threshold, but the class and type
  boundaries for infantry were never isolated.
- **Static targets.** Everything was parked. Movement is a strong real-world detection cue and is
  not modelled at all.
