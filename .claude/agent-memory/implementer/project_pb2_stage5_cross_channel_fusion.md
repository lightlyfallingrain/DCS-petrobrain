---
name: pb2-stage5-cross-channel-fusion
description: PB-2 Stage 5 validation-only findings — gate radius depends on the new percept's own range, certainty is pure-recency not quality
metadata:
  type: project
---

PB-2 Stage 5 (`plans/pb2-contact-memory/plan.md`) was validation-only: `test_cross_channel_fusion.py`
added, no `belief/`/`perception/` production code touched — every acceptance criterion was already
testable against Stages 1-4's existing code.

Two things worth remembering for future gate/decay fixture work:

1. **`passes_gate`'s spatial radius uses the *new* percept's own `uncertainty_radius_m`, not the
   founding/contact's.** A negative (should-not-merge) fixture that separates two objects by range
   along the same bearing can accidentally fail if the *far* object is naked-eye-sourced — its
   range-derived uncertainty grows with range (≈649m at range=1600m) and can exceed the separation
   you intended as a gap. Separate by bearing instead of range when constructing a
   should-not-merge cross-channel fixture, mirroring [[project_pb2_stage1_belief_core]]'s existing
   note about ambiguous-merge fixture geometry.

2. **`decay.certainty_of` is pure `now_sim - last_seen_sim` recency, with no notion of which
   channel or which observation's own uncertainty was tighter.** "Certainty reflects the better
   observation" (plan's Stage 5 wording) currently means "reflects the most recent contributor,"
   full stop — a wider-uncertainty scope observation arriving after a tighter naked-eye one fully
   resets certainty to "observed". `Contact.last_class_raw` behaves the same way (last-writer-wins,
   no fusion). This is a documented finding, not a bug — if a future milestone wants
   quality-weighted certainty/classification, that's new behavior for whoever next touches
   `decay.py`/`Contact.record`, not something to retrofit into a validation stage.
