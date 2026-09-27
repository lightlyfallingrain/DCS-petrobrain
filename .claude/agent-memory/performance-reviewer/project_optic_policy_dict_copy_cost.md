---
name: optic-policy-dict-copy-cost
description: Measured cost of optic_policy.decide()'s per-call dict(...) copies of never-pruned per-contact maps, at 55/300/1000 contacts
metadata:
  type: project
---

`belief.optic_policy.decide()`'s `SCANNING` branch runs `is_worth_a_look` over `targets` (list
comprehension) and, on committing/starting a look, copies `OpticState`'s per-contact dicts
(`attempted_at_range_m`, `attempted_at_time_sim`, and -- since sortie-2026-09-26-fixes Fix B --
`pending_attempted_at_range_m`) via `dict(...)`, unconditionally per call. These maps are never
pruned (contacts accumulate for the process lifetime -- Security flagged this pattern independently
for memory; this is the same pattern's runtime-cost side).

**Measured** (`body-layer/.venv`, `PYTHONPATH=src:../world-model/src`, 2000 calls per size):
- 55 contacts (this project's largest recorded sortie): 0.084 ms/call
- 300 contacts (a long multi-sortie session): 0.447 ms/call
- 1000 contacts (well beyond anything a real sortie/session has produced): 1.460 ms/call

Linear in contact count, as expected. Even the 1000-contact synthetic case is 0.15% of the 1 Hz
poll budget.

**Verdict: non-issue at any realistic scale for this project's current phase.** Revisit only if
session length or contact-count assumptions change materially (e.g. a long-running campaign-style
process that never restarts), not proactively.

See [[cockpit-mask-gate-cost]] for the sibling per-tick gate measurement from the same review.
