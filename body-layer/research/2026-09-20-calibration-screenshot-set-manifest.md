> **CORRECTION 2026-09-21 — this set is contaminated as evidence about unaided visibility.**
> The 52 PNGs described below were captured with DCS's **"detection aid dots" enabled** (user,
> 2026-09-21): DCS draws a small dark dot at a target to make it findable at long range. So
> "targets are visible only as faint marks on the horizon in the longer-range frames — that
> faintness *is* the measurement" is **wrong as stated**: part of what was measured is the aid.
> Everything in "What was derived from them" is therefore fitted to aided data and awaits a
> dots-off re-shoot before any constant is re-derived
> (`2026-09-21-calibration-target-decided.md`, `body-layer/tests/fixtures/vision_calibration.json`).
>
> The "If the directory has emptied" method section is still correct and still the right protocol —
> with one line added to it: **detection aid dots must be OFF.** That is the whole lesson here.
> This note was written specifically to record what an opaque image set contained before it could
> vanish, and it recorded everything visible in the frames; the setting that invalidated them was
> not in the frames at all. **Capture conditions that live outside the artefact have to be asked
> for, not read off it.**

# The vision-calibration screenshot set — what it is, recorded before it disappears

**Date recorded:** 2026-09-20 · **Images captured:** 2026-09-17, 15:05:33 → 15:29:57
**Location:** `win-mac-sync/from-windows/screenshots/` — **ephemeral, not a permanent directory**
(user, 2026-09-20: it "may empty")

## Why this file exists

52 PNG screenshots sat in a sync directory for three days, invisible to every search and every
agent, because **images are opaque to grep and to a knowledge graph**. They are the source data
behind the merged vision-range calibration, and if the directory had emptied first — which the user
says it may — nothing in the repository would have recorded that they ever existed, what they
showed, or what was derived from them.

**The convention this establishes:** anything dropped in `win-mac-sync/` is a *delivery mechanism*,
not storage. Findings get written to a dated `research/` note while the files are still there. The
note must carry the content, not merely a list of filenames, because filenames survive nothing.

## What the set is

The **screenshot ladder** that `perception/visibility.py`'s docstring refers to and that pass 2 of
the vision-range calibration was derived from (`2026-09-17-vision-range-calibration-pass2.md`). It
is paired observations at a series of ranges:

| kind | count | size | what it shows |
|---|---|---|---|
| F10 map view | 10 | < 2 MB | the target complex with the ruler measuring true range |
| operator cockpit | 42 | 2–14 MB | the same targets seen from the gunner's seat at that range |

The pairing is the method: the map view fixes the true distance, the cockpit view records what was
actually visible at it. Sizes differ by an order of magnitude because the cockpit frames are
detail-dense and were kept lossless — **which is the whole point.** Pass 1 used JPEG captures whose
compression artefacts hid a full recognition tier and invalidated a merged calibration; pass 2 was
re-shot losslessly for that reason.

## The mission, from the map frames

Twelve units in a line on flat desert, at **31°37'22"N 40°12'05"E**, ownship 750 m:

`SA-3` · `SA-3 TR` · `ZU-23 U` · `ZSU-23-1` · `BMP-1` · `T-72B` · `BTR-70` · `Ural` · `BM-21` ·
`AK` × 3 (infantry)

That composition is worth keeping: it is the mission the Stage 6 sortie card asks to reuse, and it
gives known types at measurable ranges — which is what the detection-range block depends on.

## What the cockpit frames show

The **operator's station**, not the pilot's: the PKI sight ring dominates the view, with the
instrument panel below and the 9K113 cueing legends visible at the right (`ALIGN TO 9K113`,
`ALIGN FOR LAUNCH`, `BREAK LEFT` / `BREAK RIGHT` / `BREAK 180`, `HDG LOS`, `CBTM`). Radar altitude
reads ~202 m, IAS 0 — the aircraft is stationary, which is correct for a calibration ladder where
range must be exact.

The Petrobrain overlay window is present in every frame but **empty**, which dates the set to
before the overlay carried contact text.

Targets are visible only as faint marks on the horizon in the longer-range frames. That faintness
*is* the measurement.

## What was derived from them

The three angular-radius constants now in `perception/visibility.py` —
`LOWRES_ANGULAR_RADIUS_RAD` 0.003, `MEDRES` 0.014, `HIRES` 0.028 — plus the 10 km range cap, and
the finding that matters most: **read as apparent angular size, the unaided and magnified columns
land on the same thresholds**, so an optic supplies magnification and nothing else. That is what
makes the detection-cones milestone small, and it came from this set.

## If the directory has emptied

Nothing here needs re-shooting unless the constants are re-derived. If a future pass does need new
captures, the method is above: paired map-and-cockpit frames at each range, **lossless PNG only**,
aircraft stationary, and the same twelve-unit complex so the numbers stay comparable.
