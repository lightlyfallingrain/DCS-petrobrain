---
name: position-belief-error-model
description: Findings behind the 2026-09-24 precise-position-belief plan — the range bucket returns its upper bound, the hybrid channel is truth-exact, and why ED's range ladder is derivable but its clock ladder is not
metadata:
  type: project
---

Three facts found while planning `plans/precise-position-belief/plan.md`, none of them
stated in any doc at the time.

**1. `naked_eye_source._quantise_range_m` returns the bucket's UPPER BOUND, not its
midpoint.** Every naked-eye range is therefore biased *long* by up to a full bucket
width (500 m at 3 km, 1000 m at 6 km). The current position model is not
"conservative" — it is systematically wrong in one direction. Do not repeat the claim
that quantisation is a safe/pessimistic error model.

**2. `perception/hybrid_source.py` does not quantise at all.** It writes
`associate()`'s `bearing_deg`/`range_m`, computed from the matched world object's true
x/z — so belief already receives a **truth-exact** position on the scope channel,
budgeted only by the `SCOPE_UNCERTAINTY_M = 300.0` placeholder. This is the largest
live omniscience hole in body-layer. Any future "precision = omniscience" argument has
to account for the fact that precision without an error model is already shipped there.

**3. ED's `OP_D*` range ladder is derivable as an error model; the `OP_A*H` clock
ladder is not.** The range ladder coarsens with range (100 m steps to 1 km, then 500 m,
then 1000 m — 10-33% of range, ~17% typical), which is the signature of an estimation
error that grows with range. The clock is a uniform 30° at every range because there
are twelve hours on a clock face, not because of any perceptual mechanism. So the range
vocabulary carries information about ability and the bearing vocabulary carries only
word count.

**Why:** these three together are the case for replacing quantisation-as-error-model,
and they invert the current model's anisotropy — today's `_naked_eye_uncertainty_m`
makes bearing error (776 m at 3 km) larger than range error (500 m), when physically it
is the reverse by several times.

**How to apply:** when touching `association_over_time.py`, `contacts.py`, or either
perception source's geometry, check these before reasoning from the existing constants.
Also: deriving a cross-range sigma from apparent angular size alone gives ~2.3 mrad
(7 m at 3 km) — that is the same ~100x-too-tight magnitude Stage 3b-i rev.2 was reverted
for. Pointing precision is not acuity. See [[feedback_provenance_confidence_pattern]]
for the declared-vs-derived constant discipline this plan follows.
