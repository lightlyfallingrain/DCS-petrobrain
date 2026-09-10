---
name: feedback-escalate-gate-policy-changes
description: don't patch association_over_time.py's gate sizing or ContactStore's ambiguity policy as a Debugger -- both are load-bearing trade-offs, escalate to Architect
metadata:
  type: feedback
---

When a live-acceptance bug traces back to `belief/association_over_time.py`'s spatial gate
sizing or `belief/contacts.py`'s `ContactStore.ingest` ambiguity rule (see
[[project_association_gate_fragility]]), do not apply a speculative parameter tweak or policy
change as a Debugger fix, even if a "smallest possible" version seems obvious. Both are
explicitly documented, deliberate design decisions with known trade-offs already flagged in prior
review docs (`plans/classification-refinement/review.md`). A fix in either direction reliably
reopens a failure mode in the other direction (narrower gate -> single-object jitter misses;
wider gate -> cross-object ambiguity runaway).

**Why**: confirmed 2026-09-10 -- investigated a live "40+ duplicate contacts" bug that looked
identical to an already-fixed bug (7581928), reproduced it empirically (two real objects ~870m
apart, 60 polls -> 120 contacts), and found the only "fixes" available were (a) shrink the gate
(reopens the original bug) or (b) make the "ambiguity -> always spawn new" invariant
self-limiting (changes a named, deliberate `plans/pb2-contact-memory/plan.md` Stage 1 decision).
Wrote up the finding and escalated rather than patching -- per this project's own Debugger role
constraint ("if the fix requires architectural change, stop and escalate").

**How to apply**: if a future session asks you to "just fix" a duplicate/merge bug in this area,
reproduce and document root cause per the Debugging Procedure, but stop short of editing
`spatial_gate_radius_m`'s formula or `ContactStore.ingest`'s decision rule without an Architect
plan. Do report the concrete numeric evidence (gate width vs. real object spacing at the ranges
involved) so the Architect isn't starting from zero.
