---
name: cockpit-mask-gate-cost
description: Measured cost of the cockpit-mask observability gate (body_relative_direction + is_visible) on body-layer's per-tick belief path
metadata:
  type: project
---

`belief.contacts._callout_may_speak` (sortie-2026-09-26-fixes, Fix A) calls
`perception.geometry.body_relative_direction` + `perception.cockpit_mask.is_visible` once per
contact per tick, unconditionally (gated only on `ownship is not None`, not on watch/attention).

**Measured** (not estimated), `body-layer/.venv`, `PYTHONPATH=src:../world-model/src`, 20,000
simulated ticks x 55 contacts:
- 1.44 us per contact-call (vector rotation + a handful-of-breakpoints table lookup, no allocation
  beyond the returned `BodyRelativeDirection` dataclass).
- 0.079 ms per tick at 55 contacts -- 0.008% of the 1 Hz (1000 ms) poll budget.

**Same shape applies to `perception.visibility`'s detection-time gate** (same primitive, different
call site -- per-candidate at ingest, not per-existing-contact at tick) -- not separately measured
here but expect the same per-call cost.

**Verdict at current scale (1 Hz poll, 52-55 contacts, this project's largest recorded sortie):
non-issue.** Would only become worth re-measuring if a future higher-frequency runtime phase
(Petrobrain Runtime, once it has its own hard budget) inherits the same unconditional-per-tick
shape at a much higher poll rate -- even then, back-of-envelope stays trivial (55 x 1.44us ~ 0.08ms)
against any plausible per-tick budget.

See also [[optic-policy-dict-copy-cost]] for the sibling measurement on `optic_policy.decide()`'s
per-call dict copies, and [[watch_reporting_scale_notes]] for the unpruned-contact-set growth
pattern this gate write (`Contact.last_observable_sim`, refreshed every tick for every contact) is
one more instance of.
