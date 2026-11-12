---
name: noise-field-sweeps-need-an-ensemble
description: body-layer range error has THREE draws -- field (salt seam), z_look (keyed by poll_key=t_sim) and per-look bearing noise (keyed by observation_id); a harness that salts only the field and reuses t_sim/ids holds one draw per cell, which faked BL-B110's "long-gap" STOP (BL-B108 2026-10-31, BL-B110 2026-11-03)
metadata:
  type: feedback
---

**To measure a rate from `perception/estimation.py`'s range error, sweep an ensemble of field
realisations (salt the field seed). Also redraw the two terms the salt does not reach: use a
unique `observation_id` and a distinct `t_sim` per trial. Do not vary `bias_object_id`, and do
not only rotate the scene.**

**Why, first time (BL-B108 round 2):** the reviewer reported "same-optic 10/10 two contacts,
cross-optic 0/10" across 10 bias draws. But `bias_object_id` keys only the *bearing* bias. The
range draw depends only on geometry, optic class and poll key, so those were 10 copies of one draw:
always 10/10 or 0/10, never in between.

Rotating the scene samples one realisation with only ~12 effective samples at a 30° length
scale, so those rates jumped non-monotonically with the length scale.

A salted ensemble (100–400 realisations) showed what one realisation had hidden:
- The "always two" same-optic case actually failed 4–22% of the time.
- The main loop's hypothesis that the separation came from a shared realised error was wrong:
  realised ρ was 0.23, and the separation came from the narrow hypothesis gate.

**Why, second time (BL-B110 Stage 0 → sixth architect pass, 2026-11-03):**
`test_expected_area_trigger.py` salted the field per trial but kept `t_sim` = 0/`gap_s` and the
ids `"first"`/`"second"`. That left `z_look` (keyed by `optic:poll_key`) and the per-look bearing
noise (keyed by `look:{observation_id}`) as **one fixed draw per gap cell**. The unaided `z_look`
at `t_sim = 600` happens to be +2.83σ. The result was a "long-gap stationary STOP" (25–27% at
600 s, 3–7% at 6 s), which the user held Stage 2 on. Resampled, the rate was 15–20% at **every**
gap. The problem was real but differently shaped, and the "gap-dependent escape" fix the plan had
named would have targeted an artifact.

**How to apply:**
- In probes, monkeypatch `est._field_value` to append a salt to `field_name`, **and** give each
  trial a unique observation id and a time offset (`t0 = trial * 1e-3`).
- In tests, use the `_FIELD_REALISATION_SALT` seam plus per-trial ids and times. Do not salt the
  production hashes: that would change flight draws.
- **When a measured rate varies along an axis the model says it should not** (gap, at zero
  growth), suspect a fixed draw before designing a fix for that axis. Check the axis's own hash
  keys first.
- A pinned-scenario test is a statement about one realisation. Any length-scale or seed change
  can flip it, as `test_hybrid_source.py`'s scope test did.
- `test_relative_distance_sweep.py`'s cross-time helpers carried the same artifact as of
  2026-11-03. BL-B110 Stage 1b fixes it there too.
- Related: [[project-correlated-range-error-gate-and-fold]],
  [[reproduce-the-fix-sketch-not-just-the-defect]] (this pass prototyped the fix by
  monkeypatching the real code, then ran the full suite against it).
