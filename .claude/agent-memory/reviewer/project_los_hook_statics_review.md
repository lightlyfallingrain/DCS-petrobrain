---
name: los-hook-statics-review
description: APPROVED W/ REQUIRED FIXES; new pcalls converted a loud failure into a silent one, asymmetric with an existing counter.
metadata:
  type: project
---

`fix/los-hook-statics` (301e869), aircraft-layer LOS Hook enumerating statics alongside units.
Verdict APPROVED WITH REQUIRED FIXES.

**The finding worth carrying: adding `pcall` around a previously-unprotected call can be an
observability regression, and the giveaway is an asymmetric counter.** The branch added
`static_enum_failures` for `coalition.getStaticObjects` failing per side — and correctly argued
that without it a total statics failure would look exactly like the old unit-only behaviour. The
*same* commit wrapped `coalition.getGroups`/`getUnits`/`isExist`/`getID` in `pcall` with **no**
equivalent counter. Before, those errors propagated out of the `dostring_in` chunk and
`pollAndSend` logged `LOS poll failed:`. After, a side's units silently vanish. **When a change
adds a failure counter for one branch of a symmetric pair, grep the other branch for one.** The
asymmetry is the signal; neither half reads as wrong on its own.

**The justification was also false in a way that matters.** The log said an error "inside
`onSimulationFrame` takes the mission with it". The chunk runs in the *mission-scripting* state via
`net.dostring_in`, behind two `pcall`s. Delete-X-and-ask-if-Y-holds again: the change is right, the
reason is wrong, and the wrong reason is what licenses the next silent swallow.

**Technique that settled the `isExist`-advisory trade in one read:** don't reason about whether a
stale verdict is harmful — find the join's *iteration direction*. body-layer's
`_resolve_los_by_unit_name` loops over `GET /world_objects/latest`'s live objects and looks each
name up in the verdict dict, so a verdict for a dead object is never *consulted*, not merely
discarded. That is stronger than the implementer's "never joined" and settles the remembered-contact
case too.

**A counter-semantics change can be load-bearing for the instrumentation, not just cosmetic.**
Moving the name fetch above the bubble counter made `#candidates == objects_in_wedge`
unconditionally, so `sightlines_computed < objects_in_wedge` became a *pure* cap test instead of one
confounded with name-lookup failures. The implementer framed it only as "joinable population". When
judging a rename-less semantic shift, check whether it is what makes a downstream measurement
decisive — grep for consumers first (here: log lines and a `to_dict` echo only, nothing branching).

**A duplicated constant becomes a required fix when it has zero readers.** `PLAYER_BUBBLE_RADIUS_M`
was declared, cited in two comments, and read by no code; the real bound was a re-typed literal in
the bridged chunk. Contrast `HOUR_DEFAULT`/`FOV_DEFAULT_DEG`, duplicated the same way but *live* —
and serving a genuinely different situation (bad inbound value vs. no command yet), so collapsing
them would couple two values that are equal only by coincidence. Duplication severity is about
readers and about whether the two uses are the same concept, not about the literal matching.

See also [[docstring_so_clause_delete_the_mechanism]], [[every_guard_entry_needs_a_failing_counterfactual]].
