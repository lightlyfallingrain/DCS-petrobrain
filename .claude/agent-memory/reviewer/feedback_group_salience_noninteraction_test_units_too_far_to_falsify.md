---
name: feedback-group-salience-noninteraction-test-units-too-far-to-falsify
description: emitter-visibility's "an emitter must not widen group_salient_ids for its non-firing neighbours" test placed both units at 9km, beyond even the relaxed RESOLUTION threshold -- two separate mutations that would break the real invariant both passed the full suite unchanged
metadata:
  type: feedback
---

On `feature/emitter-visibility`, the plan's Risks section named a specific regression to pin: "an
emitter must not widen `group_salient_ids` for its non-firing neighbours... or one AAA gun makes a
whole convoy visible." The implementer wrote
`test_emitter_does_not_widen_group_salience_for_a_non_emitting_neighbour`, placing both the burning
unit and its healthy neighbour at 9 km.

**Mutation-tested it per the standing "verify by mutation, per entry, not per set" practice** (see
root reviewer role instructions) and found the test does not falsify: two separate mutations --
widening `salient_ids` by `emitter_by_object_id.keys()`, and (closer to the real worry) unioning
`salient_ids` with every candidate's id whenever any emitter is present anywhere in the poll -- both
left the full 1998-test suite green. The reason: `group_salience.py`'s relaxed `RESOLUTION_ANGULAR_
RADIUS_RAD` threshold for a 7 m vehicle is ~5469 m, and both test units sit at 9 km, well beyond even
the *relaxed* threshold -- group-salience membership makes no observable difference to either unit's
visibility at that range, leak or no leak. The test currently passes only because the code is
structurally correct (`group_salient_ids(candidates, observer, UNAIDED_OPTIC)` takes no `emitter`
parameter at all, confirmed by reading the call site), not because the test would catch a regression
that broke that structural guarantee.

**The general lesson**: a "neighbour is not widened" test needs its neighbour placed *inside the
window the relaxation actually opens* (here, between the tight and the relaxed threshold), not just
"near" the emitter. A neighbour placed outside both thresholds, or inside both, cannot distinguish
leak from no-leak -- the assertion passes either way and reads as a real pin on a skim.

**How to apply:** whenever a non-interaction/non-widening test exists for a threshold-relaxation
mechanism, check where the test's fixture sits relative to the *two* thresholds the relaxation moves
between (not just "far" vs "near") before trusting it, and mutate the production code to actually try
to break it. If the mutation passes silently, the fixture is in the wrong range window, not the
mechanism.
