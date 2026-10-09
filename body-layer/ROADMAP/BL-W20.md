# BL-W20 — Vision range calibration

- [x] **Vision range calibration (perception-tier, no BL number — the PB-1.5/`visibility.py`
  lineage).** #status/done **Done 2026-09-17.** `perception/visibility.py`'s recognition-tier range constants
  are no longer guesses: they are derived from a nine-range screenshot ladder (503 m to 8.89 km,
  one 12-unit complex on flat desert, four optics per range, each range's ground truth taken from
  an F10 ruler frame). Dataset: `body-layer/tests/fixtures/vision_calibration.json`
  (`png-2026-09-17` records). Derivation and full ladder:
  `body-layer/research/2026-09-17-vision-range-calibration-pass2.md`.

  **What changed.** `MEDRES_ANGULAR_RADIUS_RAD` 0.008 → 0.014 (class range for a 7 m vehicle
  3500 m → 2000 m), `HIRES` 0.02 → 0.028 (type 1400 m → 1000 m), `LOWRES` 0.0043 → 0.003
  (presence 6511 m → 9333 m), `NAKED_EYE_RANGE_CAP_M` 5000 → 10000.
  `BINOCULAR_RANGE_MULTIPLIER` stayed at 4.0. The old constants were wrong in **both** directions
  at once — over-claiming classification while under-claiming presence — which is why they read as
  plausible for so long. Note the cap no longer matches `association.RANGE_CAP_M` (5000):
  deliberately decoupled, since one number now has data behind it and the other does not.

  **The result that made a per-optic model unnecessary.** Read as apparent angular size (true
  angular size × magnification), the unaided and binocular columns land on the *same* tier
  thresholds — class at ~0.014 rad from both, agreeing to within 2%. The tiers are properties of
  the eye; the optic only multiplies the angle. So retuning three constants was sufficient, and
  the 2026-09-17 decision to defer the per-optic dimension holds. The 9K113 wide/narrow columns
  are recorded in the fixture as founding evidence for the deferred "attention direction and
  detection cones" item below, which owns that split.

  **Pass 1 (the same day) reached the opposite conclusion and was wrong.** It graded compressed
  JPEGs of a similar scene and concluded class was never resolvable through binoculars at any
  range down to 895 m — recommending `medres`/`hires` be made unreachable. The lossless ladder
  shows class at 1.99 km and type at 1.00 km. The JPEG rows are kept in the fixture as
  `authoritative: false`, with `test_jpeg_set_is_excluded_and_understates` pinning the
  contradiction (a *better* grade at a *longer* range) so nobody folds them back in. Lesson worth
  carrying: for a perception threshold, a lossy screenshot is not conservative evidence, it is
  wrong evidence — the codec is part of the instrument.

  **Still open, deliberately.** `LOWRES` is an upper bound, not a measured boundary — presence was
  still unmistakable at 8.89 km, the farthest range photographed, so a longer ladder would push it
  lower again and `NAKED_EYE_RANGE_CAP_M` remains a sanity bound rather than a measurement.
  Nothing below 503 m, so the unaided type threshold is unmeasured. One condition only (flat
  desert, unobstructed, clear, one theatre/time/altitude band) — contrast, haze, dusk, night and
  cluttered backgrounds are untouched, and `min_contrast_f`/`min_fog_transparency` remain
  unaddressed. Every derivation uses a 7 m armored reference; infantry ranges follow from the
  formula, not from measurement. All targets were static, and movement is a strong real detection
  cue this does not model.

