---
name: recurring-predicate-granularity-mismatch
description: When several review rounds each strengthen a predicate and a hole remains, the predicate is one granularity coarser than what it governs; raise it as a process signal, not a code fix.
metadata:
  type: project
---

**A multi-round fix that keeps strengthening a predicate is evidence the predicate is the wrong
*shape*, not that it is too weak.** `feature/sortie-refinements` (2026-10-06) spent three review
rounds on `belief.speech.may_be_callout_keeper(store, contact)`, which elects one member of a
watched group while the scheduler consumes the rest's events *of a kind*. Every round's fix was
correct and none closed the hole, because the residual failure is a per-**event** question
(*does the keeper have an event of this kind this tick?*) that a `(store, contact)` predicate cannot
express at all. Filed as `BL-B41`; the real fix is re-keying the election per `(group, kind)`.

**The tell is available from round 1 and reads as a strength: the predicate's parameter list.** If a
fix for "the governed thing was wrongly dropped" needs another condition, check whether the
predicate's arguments can even *see* the dropped thing before adding it.

**Why this belongs in DoD's memory rather than only in NOTES:** the symptom the reviews actually
caught was prose — docstrings asserting "N lines becomes one" when it can become zero. That is the
same family as [[project_recurring_prose_count_of_a_code_set]] (now 5th+ occurrence), and treating
it as a prose defect each time hides the design defect underneath. **Two occurrences of the
granularity version so far**: this one, and the merged `fix/callout-observability-gate`'s matching
silence mode — which is the *same* election, by a second trigger, and is filed together with
`BL-B41` precisely so the per-event redesign is not done twice.

**How to apply:** when a feature arrives at DoD having taken 3+ rounds on one predicate/gate, say so
as a **process** signal in the report: the granularity check belongs at Architect, where the
quantifier is chosen, not at Reviewer, where only the condition is visible. If a third occurrence
appears, that is the argument for an explicit Architect-stage question — *what is the unit of the
thing this gate governs, and does the gate take it as an argument?* Related:
[[project_recurring_multiround_threshold_widening]], which is the same multi-round shape with a
different cause (a real threshold genuinely needing widening, each round caught by running the real
subsystem) — distinguish them by asking whether the last round's fix was *wrong* (widening) or
*correct but insufficient* (granularity).
