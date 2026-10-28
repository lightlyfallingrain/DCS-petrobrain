---
name: physical-limit-beats-self-consistent-derivation
description: When checking a flight-measured calibration constant, a sourced hard physical limit it would violate is stronger evidence of error than the derivation's own internal consistency
metadata:
  type: feedback
---

When reviewing a calibration constant derived from flight telemetry plus an assumed rate/parameter
(e.g. `MARK_DEG_PER_UNIT_EL` on the 9K113 elevation mark, derived from measured raw-gauge slope
divided by an assumed commanded 0.5°/s), check whether the derived figure implies anything that
contradicts an independently **sourced** hard limit (here: the periscope manual's `GIMBAL_EL_DOWN_DEG
= -15.0`). If it does — the elevation case derived a −18.4° readback limit, exceeding the sourced
−15° gimbal stop — that is a real defect signal, even if the derivation is internally consistent
(e.g. the same assumed rate reproduces the measured travel time almost exactly).

**Why:** internal consistency between two numbers computed from the same assumption is not
independent confirmation — it agrees by construction. A measured/derived value that violates a
separately sourced physical fact is a stronger, non-circular signal that the assumption (not the
raw measurement) is wrong.

**How to apply:** when a plan or implementation note flags its own calibration ambiguity (as this
one did, in `implementation.md`), don't just read the two candidate derivations side by side — check
each candidate against any already-sourced hard constraint in the codebase (gimbal limits, physical
FOV bounds, manual-derived figures tagged SOURCED in research notes or the knowledge graph). Prefer
the candidate that doesn't violate one. Flag this prominently even when it doesn't block the merge
(the raw clip readings and the root-cause mark-clip check can still be correct and shippable even
while the degree-conversion scale is in question) — see [[project_9k113_el_field_scale_ambiguity]].
