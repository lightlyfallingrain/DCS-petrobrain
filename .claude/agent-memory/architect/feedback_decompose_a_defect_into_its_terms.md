---
name: decompose-a-defect-into-its-terms
description: When a backlog entry names the mechanism of a defect, measure each term's contribution separately before adopting the instrument it proposes — twice now the named cause was the minor one.
metadata:
  type: feedback
---

**Before adopting the instrument a defect report names, decompose the symptom into its terms
and measure each one's share.** A `threshold` compared against a `gap` has two sides, and a
report naming one of them is a hypothesis, not a measurement.

**Why:** `BL-B59` stated its mechanism as *"position drift shifts the median nearest-neighbour
gap, which tightens the relative threshold, which drops a real member"* — and named retention
hysteresis as the instrument on that basis. Measured across the same fold tick the entry
itself cited: the threshold tightened **13.6 %** (195.6 → 169.0 m) while the gap grew
**170 %** (72.1 → 194.6 m). The named cause was the minor term. Because the dominant term was
a *discrete, attributable, already-measured* artifact (`Contact.fold_displacement_m` = 132.7 m)
rather than boundary noise, the correct instrument was to **subtract the artifact**, not to
widen a band — and every band-widening variant, including the project's own established 1.5×
factor, failed five ticks after appearing to work. This is the same shape as `BL-B58`, whose
own option-3 sketch was measured to be a **no-op** by the preceding Architect pass: two
consecutive entries in one mechanism, each naming a cause that the arithmetic did not support.

**How to apply:** when a plan's brief hands you a mechanism and an instrument, print both
sides of the comparison before and after the event, as a two-row table with percentage change.
If the named term is not dominant, the instrument is probably wrong, and say so in the plan's
§2 rather than building it. Related: a sweep over a proposed constant is only a calibration
curve if *some* value works — if every value fails, that rules out the family and is the more
valuable finding. See `plans/group-retention-hysteresis/plan.md` §2a–§2d.
