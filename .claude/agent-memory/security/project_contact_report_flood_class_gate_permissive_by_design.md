---
name: contact-report-flood-class-gate-permissive-by-design
description: contacts_plausibly_same's class check passes freely for OP_GROUPSOMETHING contacts (the ~99%+ real-world case) because class_compatibility("unknown") != "incompatible" -- this is inherited from the already-production-trusted passes_gate, not a new weakness introduced by the suppression feature.
metadata:
  type: project
---

`belief.association_over_time.contacts_plausibly_same` (new, `plans/contact-report-flood/plan.md`
Stage 1, commit `c3bf79b`) is a conjunction: `class_compatibility(...) == "incompatible"` short-circuits
to reject, then a 3-sigma Mahalanobis test on summed, own-elapsed-inflated covariances must also
pass. `class_compatibility` returns `"unknown"` (not `"incompatible"`) whenever either side's raw
classification resolves to `None` via `_op_class_of`, and `OP_GROUPSOMETHING`
(`object_model.DEFAULT_OP_CLASS`) always resolves to `None`. Since `OP_GROUPSOMETHING` was ~99.7%
of real belief rows in the sortie-1004 snapshot, the class gate essentially never rejects in
practice -- the spatial test alone is the operative guard for almost every real suppression
decision.

**This is not new risk from this feature.** The identical `class_compatibility` posture, the
identical `GATE_SIGMA_THRESHOLD = 3.0`, and the identical covariance model already govern the
production percept-vs-contact merge decision in `ContactStore.ingest` (`passes_gate`) today.
`contacts_plausibly_same` reuses that exact, already-calibrated gate for a second purpose
(contact-vs-contact, for `CalloutScheduler`'s `CONTACT_DETECTED` merge-echo suppression) rather
than inventing a looser one. Measured against real sortie-1004 data in the implementation commit:
17 of 34 foundings still speak, and same-poll peers are excluded by a separate, load-bearing
`other.first_seen_sim < this_contact.first_seen_sim` condition that specifically prevents mutual
suppression of genuinely-simultaneous distinct contacts.

**How to apply:** when this gate (or `passes_gate`) comes up again in a future review, don't
re-flag "class check passes for GROUPSOMETHING" as a new finding on its own -- it's the existing,
accepted production posture. The residual edge case worth a standing risk note (not a blocker) is
elapsed-time covariance growth on a long-`tracked`-but-not-yet-`lost` contact making the spatial
gate looser over time; this mirrors [[project_elapsed_time_inflation_quadratic_dt_composition]] and
[[project_body_layer_bounded_growth_accepted_pattern]]'s general shape (an accepted, bounded,
documented tradeoff) rather than an unbounded one.

APPROVED 2026-10-05 (deep analysis, `fix/contact-report-flood`, tip `3884840`).
