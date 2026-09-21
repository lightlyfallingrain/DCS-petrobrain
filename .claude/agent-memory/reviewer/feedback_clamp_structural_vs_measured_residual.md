---
name: clamp-structural-vs-measured-residual
description: When a model's clamp/formula reproduces a measured RATIO but not the measured ABSOLUTE figure, check whether the delta is a documented "known unmodelled residual" before flagging it.
metadata:
  type: feedback
---

In cones slice 2A (`plans/detection-cones-slice2/plan.md`, commit `ba4e40f`), the distinctiveness
clamp (`class = min(presence, ...)`) was verified by hand-computing infantry's class/presence at
each optic. The *structural* collapse (class == presence, ratio 1.00) reproduced exactly as
claimed at every optic. The *absolute* computed presence figures (e.g. binocular 1452 m) did not
match the decisions doc's directly-measured presence (2.0 km) — this is not a bug: the decisions
doc (`body-layer/research/2026-09-21-slice2-model-decisions.md`) explicitly flags this as a "known
unmodelled residual" (a single per-optic multiplier is somewhat wrong for one class of object
either way, since binocular 2.42 was BTR-60-derived, not infantry-derived).

**Why:** a reviewer sweeping/verifying clamp arithmetic can mistake "doesn't match the measured
absolute number" for a regression when the plan's own math never claimed absolute reproduction —
only the structural ratio the clamp exists to guarantee. Re-deriving from the model's own formula
and comparing *that* against research-doc "known residual" notes, rather than against the raw
measured figures directly, avoids a false-positive required-fix here.

**How to apply:** before flagging a clamp/formula output that differs from a measured value cited
in a research doc, check whether that same doc already names the discrepancy as an accepted,
documented residual. If so, verify the *structural* property the plan actually promises (e.g.
`type <= class <= presence`, or a ratio saturating to 1.0) rather than the absolute number.
