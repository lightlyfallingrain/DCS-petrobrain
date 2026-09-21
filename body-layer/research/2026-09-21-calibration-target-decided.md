# The calibration target — decided

**User decision, 2026-09-21.** This question had been open since 2026-09-20 and was blocking
threshold recalibration.

## The decision

**Calibrate against what the user can see on the monitor, in DCS.** And then **calibrate conditions
— foliage, weather, dusk, dark — the same way**, as further measurements rather than as a different
target.

User's words: *"we have no other calibration instrument after all and how DCS models weather,
foliage, etc can also only be calibrated from DCS missions on what I see… So, really, it's a
combination of A and B."*

## Why the question was posed wrongly

It was put as a choice between two targets:

- **A** — match what the player sees on a monitor.
- **B** — match a real crewman in a real cockpit, treating monitor observations as biased evidence
  about that (no foliage or camouflage in the test scenario makes the monitor *easier*; screen
  resolution and FOV compression make it *harder*; knowing where to look makes it easier; a 27-inch
  panel against binocular human vision makes it harder — and the biases do not cancel in any
  quantifiable way).

**That framing was wrong.** A and B are not competing targets. A is the **instrument**; B's concerns
are **conditions**, and conditions are measured with the same instrument.

The decisive point is the user's: *there is no other instrument.* "What a real crewman sees" is not
measurable in this project. Neither — and this is the part that settles it — is **how DCS models
foliage, haze, dusk or rain**. Those are properties of the simulator, and the only way to learn them
is to fly in them and look. A model calibrated against an imagined real cockpit would be calibrated
against nothing at all.

## The consequence that makes this more than a compromise

**Condition modifiers measured as ratios are more robust than the baseline they sit on.**

Suppose the monitor is biased against reality by some unknown factor *k* — resolution, field of
view, the absent foliage, the operator knowing where to look. Every absolute range inherits *k*.
But a modifier measured as a ratio does not:

```
foliage_factor = range_with_foliage / range_clear      ≈ unbiased in k
```

The *k* largely cancels. So the conditions work transfers even where the absolute baseline does not,
and it is worth doing on the monitor **regardless of how the absolute-realism question ever
resolves**. It is not blocked behind that question, and it never was.

This also means the two halves have different confidence and should be recorded as such: the
baseline carries the monitor's unknown bias, and the modifiers largely do not.

## What this unblocks, and what it does not

**Unblocked:** the calibration-target question no longer gates threshold recalibration. Two of the
four blockers were cleared by slice 2A (tier-dependent magnification, silhouette distinctiveness);
this clears the third.

**Scope narrowed 2026-09-21 (user):** the dots affect the **naked-eye and binocular columns only**
— the 9K113 views are unaffected, so `9k113_wide` and `9k113_narrow` remain valid data. The re-shoot
covers two of the four columns, not all four, and the sight's own calibration survives intact. That
matters for the deferred 9K113 optic slice, which already has its calibration ground truth.

**Still blocking:** the 2026-09-17 calibration ladder was shot with **DCS detection-aid dots
enabled** and overstates unaided visibility by an unmeasured amount that grows with range
(`body-layer/tests/fixtures/vision_calibration.json` carries the warning). A **dots-off re-shoot is
now the only remaining precondition** for recalibration.

## What the conditions work needs, when it happens

Not scoped here, but the shape follows from the decision — each is a ratio against the clear-day
baseline, measured the same way:

- **Foliage and camouflage** — the case the user has repeatedly flagged as making real spotting
  harder, and the one the current test scenario (flat desert, unconcealed vehicles) most conspicuously
  lacks.
- **Weather and haze** — note ED's own fog model is a *time series* (`fog2.manual`), so anything
  built here must sample rather than read once (`aircraft-layer/research/
  2026-09-20-dcs-install-detection-deep-read.md`).
- **Dusk and dark** — and note from the same deep read that **time of day is already available from
  `Export.lua` alone** (`LoGetMissionStartTime()` + `LoGetModelTime()`), with sun elevation being
  ordinary astronomy from the mission date and ownship position. No new channel needed.
