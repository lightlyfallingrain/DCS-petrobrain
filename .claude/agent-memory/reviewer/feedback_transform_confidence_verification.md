---
name: feedback-transform-confidence-verification
description: How to check a coordinate-transform "confirmed" confidence label instead of trusting the field name
metadata:
  type: feedback
---

When reviewing any coordinate-transform or geodesy-derived feature in this project, don't
trust a `confidence="confirmed"` (or similar) label at face value just because the field
exists. Open the cited `world-model/research/` note and check there's an actual reproducible
number behind it (residual against a live-install probe, control-point error measurement,
etc.), and re-run the diagnostic/report tool yourself to confirm the numbers in code match
the numbers in the research note.

Why: the project invariant explicitly forbids encoding unverified claims as fact, and a
confidence field that's just asserted without a checkable number defeats the purpose of the
provenance/confidence pattern (see [[project_m1_coordinate_transform_review]] for a case
where this was actually earned, as a positive reference point for what "earned" looks like).

How to apply: for any future World Model Builder milestone with a confidence/provenance
field, trace it back to the research note, verify the number is real and reproducible, and
only then accept the label in review.
