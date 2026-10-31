---
name: noise-field-sweeps-need-an-ensemble
description: body-layer's range error is ONE fixed field realisation keyed by geometry/optic/poll -- varying bias_object_id or rotating the scene does not give new draws, so "10/10" or "0/10" are one draw; salt the field seed to get honest rates (BL-B108, 2026-10-31)
metadata:
  type: feedback
---

**To measure a rate from `perception/estimation.py`'s down-range error, sweep an ensemble of field
realisations (salt the field seed). Do not vary `bias_object_id`, and do not only rotate the
scene.**

**Why:** in `BL-B108` round 2 the reviewer reported "same-optic 10/10 two contacts, cross-optic
0/10" across 10 bias draws. But `bias_object_id` keys only the *bearing* bias. The range draw
depends only on geometry, optic class and poll key, so those were 10 copies of one draw: always
10/10 or 0/10, never in between.

Rotating the scene samples one realisation with only ~12 effective samples at a 30° length
scale, so those rates jumped non-monotonically with the length scale.

A salted ensemble (100–400 realisations) showed what one realisation had hidden:
- The "always two" same-optic case actually failed 4–22% of the time.
- The main loop's hypothesis that the separation came from a shared realised error was wrong:
  realised ρ was 0.23, and the separation came from the narrow hypothesis gate.

**How to apply:**
- In probes, monkeypatch `est._field_value` to append a salt to `field_name`.
- In tests, use the `_FIELD_REALISATION_SALT` seam the amendment adds.
- A pinned-scenario test is a statement about one realisation. Any length-scale or seed change
  can flip it, as `test_hybrid_source.py`'s scope test did.
- Related: [[project-correlated-range-error-gate-and-fold]],
  [[reproduce-the-fix-sketch-not-just-the-defect]] (this pass prototyped the fix by
  monkeypatching the real code, then ran the full suite against it).
