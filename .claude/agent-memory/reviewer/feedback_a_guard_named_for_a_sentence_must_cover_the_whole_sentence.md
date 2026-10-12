---
name: feedback_a_guard_named_for_a_sentence_must_cover_the_whole_sentence
description: BL-12 Stage 4's extent guard suppressed the spoken heading but not the clock/range bearing, though the plan named both as unspeakable for an over-wide group -- found by executing the render path with real enrichment, not by reading the guard's own test.
metadata:
  type: feedback
---

`plans/group-contact-identity/plan.md` amendment A6's Stage 4 row: *"do not speak a heading or a
single bearing for a group wider than one believable bearing."* The implementer's extent guard
(`_GROUP_SPOKEN_EXTENT_GUARD_M` in `body-layer/src/belief/speech.py`) only gated the direction
clause (`", moving {compass}"`). The pre-existing clock/range clause
(`", {clock} o'clock, {range}"`, same function, a few lines above) had no extent condition at all
-- unconditional before this stage, still unconditional after, because nothing in the stage's own
log named it as in scope.

**Why this was invisible by reading the committed tests.** The one test that exercises the guard
(`test_render_group_disclosure_extent_guard_suppresses_the_direction_clause`) calls
`render_group_disclosure` with **no `EnrichmentContext`**, so `nearest_relative_now` is `None` and
the clock/range clause never fires regardless of extent -- the test cannot distinguish "the clause
is gated" from "the clause never ran." It takes constructing the over-wide scene *with* enrichment
supplied to see `"Group, 12 o'clock, very close."` come out for a group the plan says has no
single bearing to give.

**The general lesson**: when a plan states a guard's purpose as a sentence with more than one
clause ("no heading **or** bearing"), check every rendering branch that produces any clause the
sentence names, not only the one the implementation log's commit message talks about. A guard
named for a fact pattern is a claim about the whole pattern; verifying only the half that got a
docstring and a test leaves the other half's absence of coverage looking like "not applicable"
rather than "not done." The way to catch it is the same move as [[feedback_tabulate_only_reachable_rows]]
and the standing "grep for the new mechanism's own call site, not the file list" check in this
role's system prompt: construct the scenario the plan's own worked example names, with every
input (here, enrichment) the real code path needs to reach the clause in question, and read the
actual rendered string -- not just the one assertion the committed test happens to make.
