---
name: project-bl16-parked-u3-contradicts-ep5
description: BL-16 parked-mode plan check — an Architect "Decisions Requiring User Input" recommendation (U3) contradicted a goal-check expectation (E-P5), and the plan's own traceability table hid it by citing U3 as the thing that "closes" E-P5.
metadata:
  type: project
---

BL-16 parked-mode (mode 2) plan check, 2026-11-15. Generalizable shape, not specific to this
feature.

**The traceability table cited the exact recommendation that contradicts the expectation as the
thing that satisfies it.** E-P5 ("Petrovich never undoes the player... does not fight it," covering
a player-driven mode change on the wheel) was marked "closed by Stage P2's 'assume no player mode
change' posture (**U3**)." Reading U3 itself: its recommendation is *"always reassert at once"* —
i.e., when the player presses the wheel himself, cycle it straight back. That is fighting the
player, which is literally what E-P5 names as the one thing never to do. The table's phrasing
("closed by... posture") made this read as resolved when it was the opposite.

**The user's own narrowing answer (Q4) did not license this.** Q4 said to assume the *player*
won't change modes, but that DCS does so automatically in some situations, and Petrovich should
cycle back toward his goal in the DCS-driven case. U3 extended "reassert at once" to the player
case too — a case Q4 explicitly said to assume away, not one Q4 said to override. The Architect's
own U3 text noticed this ("Q4 explicitly assumed this case away") but still recommended overriding
the player for that exact case, and the traceability table then cited U3's recommendation as what
satisfies the expectation it contradicts.

**Lesson for future plan-aligner passes:** when a traceability table cites a "Decisions Requiring
User Input" item (a `U<n>`) as the thing that closes an expectation, read the `U<n>`'s own
recommendation text against the expectation's wording directly — do not trust the table's framing.
A `U<n>` is, by definition, not yet decided; citing it as "closing" something is a stronger claim
than the plan has earned, and the recommendation attached to it can be the opposite of what the
expectation requires. This is the same shape as
[[project_bl_b111_decision_narrows_just_answered_expectation]] (a feasibility gate reopening a
settled expectation) but one step earlier in the pipeline: there, a Decision narrowed an
expectation; here, an open, unaccepted Recommendation was already being used in the traceability
table as if it were a Decision that closed the row.

See [[project_bl16_late_requirement_and_recommendation_drift]] for the same feature's prior pass
catching an Architect recommendation (D-e) that contradicted an earlier settled Decision — this is
the same author-level pattern recurring one plan revision later, now against a goal-check
expectation instead of an earlier Decision.
