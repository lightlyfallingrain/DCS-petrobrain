---
name: fold-displacement-never-retires
description: body-layer's Contact.fold_displacement_m resets only on an unambiguous look, and in a dense scene no look is ever unambiguous — measured growing 132.7 to 239.0 m over 60 ticks with zero resets.
metadata:
  type: project
---

`Contact.fold_displacement_m` (`body-layer/src/belief/contacts.py`, BL-12 Stage 3.5) resets to
`0.0` only on an unambiguous resolution — object-permanence continuity, or exactly one passing
gate candidate. **In a scene dense enough for `groups._cluster_contacts`'s relative cohesion
term to bind, no resolution is ever unambiguous**, so the budget accumulates with `+=` and
never retires. Measured 2026-10-13 over 60 ticks of continued re-observation: 132.7 → 172.5 →
192.3 → … → **239.0 m**, zero resets. `Contact.position.radius_m()` floors at **120.0 m** in
the same run, so covariance offers no retiring bound either.

**Why:** the two conditions are the same condition. Ambiguity (≥2 passing gate candidates) is
what makes a fold happen, and spatial density is what makes the relative term bind — so any
geometry where a fold-driven cohesion defect is reachable is a geometry where the budget
cannot retire. `BL-B58` shipped the `+=` semantics with its own Risks line calling
accumulate-not-replace *"a stated assumption, not measured against a real repeat-fold
incident"*; it now is measured.

**How to apply:** any design that reads this field as a *correction term* inherits an
unbounded, monotonically growing quantity — do not assume a self-retiring budget. That ruled
out the whole bounded-discount family for `BL-B59` (every fraction of the pair threshold fixed
the first tick and failed by t=25). It also means Stage 3.5's own admission penalty grows, so
a genuine joiner refused admission to a group it belongs in is a predicted-but-unobserved
symptom that would read as under-merging and be blamed on the wrong mechanism. Recheck note on
`body-layer/ROADMAP/BL-B58.md`; probes and the full trace in
`plans/group-retention-hysteresis/scratchpad/`.
