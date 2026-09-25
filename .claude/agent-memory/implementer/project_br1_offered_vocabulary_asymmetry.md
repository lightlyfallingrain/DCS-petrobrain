---
name: br1-offered-vocabulary-asymmetry
description: When to wire an "offered set" through the wire payload (like PICK) vs. a duplicated module constant (like CONFIRM) across the brain-layer/body-layer boundary
metadata:
  type: project
---

BR-1 Stage 2's security review found `belief/brain_reply.py`'s `_validate_confirm` checked a
`CONFIRM <token>` against body's *entire* `DISPATCHED_COMMAND_TOKENS` (~30) instead of the narrower
`CLASSIFY_COMMAND_VOCABULARY` (7) the model was actually shown — unlike `_validate_pick`, which
already only accepts an id the payload itself offered.

**The deciding question when closing this kind of asymmetry: does the offered set vary per call?**
`PICK`'s candidate list genuinely does (a different set of contacts every escalation), which is why
it belongs on the wire (`EscalationPayload`). A classify/confirm vocabulary that is a fixed module
constant (same 7 tokens every single call) does not — wiring a call-invariant constant through every
payload is pure overhead with no correctness benefit. The proportionate fix there is a body-owned
duplicate constant (`OFFERED_CONFIRM_VOCABULARY` in `belief/brain_reply.py`, mirroring
`prompts.CLASSIFY_COMMAND_VOCABULARY` value-for-value) — the same duplication-across-the-module-
boundary shape this codebase already uses in the other direction (brain-layer duplicates
`DISPATCHED_COMMAND_TOKENS` as a curated subset, module independence forbids the import either way).
Document the drift risk and its failure direction (a stricter check only ever over-refuses to
`ASK`, never under-validates) directly in the duplicated constant's own docstring, since there is no
test that can compare the two literals across the module boundary.

See [[project_pb2_stage0_scope_channel_repair]] for the sibling generalization (single-item guard
-> multi-item) that also needed care about what generalizes safely and what doesn't.
