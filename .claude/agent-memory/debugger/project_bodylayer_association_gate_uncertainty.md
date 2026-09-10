---
name: bodylayer-association-gate-uncertainty
description: association_over_time's spatial gate must budget both sides' position uncertainty, not just the incoming percept's, or ambiguity self-snowballs.
metadata:
  type: project
---

`body-layer/src/belief/association_over_time.spatial_gate_radius_m` (percept<->contact
spatial gate) originally summed only the *incoming* percept's `uncertainty_radius_m`,
treating a contact's stored `last_position` as exact. It is not — `last_position` was itself
set from an earlier percept with its own uncertainty (naked-eye's bearing/range bucket
quantisation especially, since `naked_eye_source._quantise_bearing` re-anchors its 30° clock
buckets to the *current* ownship heading every poll, so two consecutive readings of a truly
identical real position can legitimately land in different buckets — a jump up to a full
bucket-width, not the half-bucket the uncertainty model assumes for one reading).

**Why this was severe, not just imprecise**: `ContactStore.ingest`'s decision rule is
"two-or-more passing candidates -> always spawn a new contact, never a best-match tiebreak"
(a deliberate anti-guessing invariant — do not change this rule to fix duplication bugs).
Once a single missed spatial-gate match spawns a second contact for the same real object, that
second contact becomes a permanent extra ambiguity candidate for every future percept near
that position — so one transient gate miss turns into a monotonic one-new-contact-per-poll
runaway for the rest of the session. This is how a live session produced 20 `Contact` records
for 6 real objects (2026-09-09, `plans/classification-refinement/debug.md`).

**Fix pattern**: `Contact` now carries `last_position_uncertainty_m` (set from
`uncertainty_radius_m(percept)` on both `from_percept` and `record`), and
`spatial_gate_radius_m` sums both sides' uncertainty plus the existing
`GATE_GROWTH_RATE_MPS * elapsed_s` growth term. Any future change to this gate's radius
formula should preserve this "both sides carry error" symmetry — do not go back to
single-sided budgeting.

**General lesson for this codebase**: whenever a perception channel re-derives its own
quantised/bucketed output fresh every poll (not carried forward from the previous reading),
assume consecutive readings of the *same* real value can disagree by up to a full
quantisation step, not half — any downstream gate/threshold comparing consecutive readings
needs to budget that full-step worst case on both sides being compared, not just one.
