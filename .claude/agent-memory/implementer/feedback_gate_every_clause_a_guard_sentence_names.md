---
name: feedback_gate_every_clause_a_guard_sentence_names
description: BL-12 Stage 4's extent guard only gated the direction clause, not the pre-existing clock/range clause a few lines above it in the same function, though the plan's own words named both -- compute the gate condition once and apply it to every clause the sentence covers, in the same pass that adds the guard.
metadata:
  type: feedback
---

When a plan states a guard's purpose as a sentence with more than one clause ("do not speak a
heading **or a single bearing**"), and the function you are editing has more than one place that
produces a clause the sentence names, gate all of them in the same change -- not just the one
clause the commit's own motivation happens to be about.

**What happened**: Stage 4 added `_GROUP_SPOKEN_EXTENT_GUARD_M` and used it to gate the trailing
`", moving {compass}"` direction clause in `_render_full_group_composition`. The clock/range
clause (`", {clock} o'clock, {range}"`) sits a few lines above it in the same function, predates
the guard, and was never touched -- so it stayed unconditional. The plan's own Stage 4 row named
both ("a heading **or a single bearing**"), but the implementation log never mentions the
clock/range clause at all, because the task in front of the implementer at the time was "add a
direction clause with a guard," not "make the function obey the guard's full stated scope."

**How to apply**: before adding a guard whose justification is a sentence naming more than one
fact ("do not speak X or Y"), grep the function (and any sibling that shares it) for every place
that could produce each named fact, not just the place the new code is going. Compute the gate
condition once as a local, and thread it through every site, in the same commit -- a guard added
half-covered looks, to a reader of just the diff and the new test, like a guard that works.

**Why the existing test could not catch this**: the one committed test for the guard called the
render function with no `EnrichmentContext`, so the clock/range clause's own precondition
(`nearest_relative_now is not None`) was never true regardless of extent -- the test exercised "the
clause never ran," not "the clause is gated." Any guard test for a clause gated behind an
`if some_data is not None:` needs that data actually supplied, or it is proving nothing about the
gate at all. See [[feedback_shared_fixture_position_becomes_load_bearing]] for the related
general habit of constructing the scenario with every input the real path needs, not the minimum
the assertion happens to require.
