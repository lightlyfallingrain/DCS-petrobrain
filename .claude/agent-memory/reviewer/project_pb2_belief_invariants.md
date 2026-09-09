---
name: project_pb2_belief_invariants
description: Load-bearing invariants for body-layer/src/belief/ to re-check on every future PB-2/BL-2 stage review
metadata:
  type: project
---

`body-layer/src/belief/` (PB-2/BL-2, plan `plans/pb2-contact-memory/plan.md`) carries two
invariants that are easy to quietly erode in a later stage and must be independently re-verified
(grep yourself, don't trust the implementer's self-reported grep) on every future stage review:

1. **No truth fields reach belief code.** Only `belief.percept.Percept` (t_sim, source,
   classification_raw, bearing_deg, range_m, ownship_at_observation, observation_id) may drive any
   decision in `belief/`. `Observation.derived_world_position` and `Observation.id`-as-DCS-key must
   never be read outside `percept.py`'s own `percept_of()`. As of Stage 1 this held: grepping
   `derived_world_position`/`object_id` across `belief/*.py` only hits `percept.py`'s docstring and
   its one legitimate discard-on-projection line.
2. **Percept→contact gating has no tiebreak.** `association_over_time.passes_gate` +
   `ContactStore.ingest`: exactly one candidate contact passes both gates → merge; zero or two-or-
   more → always a **new** contact, never a best-match/highest-score merge. This is deliberate
   (ambiguity must be visible/correctable, never a silent guess) — flag any future stage that
   introduces a scoring tiebreak here as a regression against the plan, not an improvement.

**Why:** both are CLAUDE.md's anti-omniscience invariant made mechanical for this module; the plan
explicitly calls out (1) as "not conservatism... the anti-omniscience invariant" and (2) as
"deliberate... no best-match tiebreak."

**How to apply:** on every subsequent belief/ stage review (Stage 2 decay/lifecycle onward), re-run
the same two greps/reads rather than assuming they still hold once decay, certainty, or fusion
logic is added on top.

See also [[project_pb2_placeholder_constants]].
