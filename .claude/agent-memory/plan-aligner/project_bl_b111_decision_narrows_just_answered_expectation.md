---
name: bl-b111-decision-narrows-just-answered-expectation
description: BL-B111 — an Architect Decision (feasibility gate) can reopen the exact silent-fold failure an expectation answered minutes earlier was written to close; check open Decisions against expectation wording, not just against each other.
metadata:
  type: project
---

BL-B111 (expected-area look): Decision 1 ("don't open a check when A's belief area has outgrown
one binocular sweep — too wide to look at, so fold silently as today") is reasonable and the
plan-check agreed with it, but it reintroduces, for that one case, exactly the silent-fold failure
E9 ("the look happens whenever the question honestly arises, not on a narrow numeric trigger") was
written against two sections earlier in the same `alignment.md`. The Architect's own Decision list
disclosed the cost plainly (0% -> 100% heard-twice regression if not excluded), so this was not
hidden — but nothing forced a check against the expectation's own wording, only against the
acceptance numbers.

Same file also had Decision 2 resolve a conflict between two of the user's own "as recommended"
answers given the same day (Q5 "budget spent -> B new" vs Q2/BL-B114 "hold and look, silent if
can't" for the echo case) by quietly narrowing Q5's scope to exclude the echo case.

**Why:** A plan can be fully self-consistent — every Decision justified, every number fenced — and
still, in one named case, undo the expectation it was supposed to deliver. The Architect's own
"Decisions" section is where this is most likely to hide, because by the time a Decision is
written it already reads as settled engineering, not as a second pass at the goal check's wording.

**How to apply:** When a plan carries open "Decisions," re-read each one against the goal check's
expectation list by wording, not only by acceptance-number fences. A Decision that recommends
*not* doing the thing in one sub-case is a second trigger-narrowing, even when phrased as a
feasibility limit rather than a numeric gate — bring it back to the user in the expectation's own
terms (here: "E9 restated" and "E1's named exception"), not just as the Decision's own framing.
Also check whether two of the user's *already-answered* goal-check questions conflict in a
sub-case the goal check didn't anticipate (budget-spent x echo here) — that is a finding worth a
question, not silent inheritance through the plan's resolution of it.

See [[project_bl_b110_clean_trace]], [[project_staged_by_measurement_can_hide_a_scope_decision]].
