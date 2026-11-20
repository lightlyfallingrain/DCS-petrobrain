---
name: lift-vector-u8-floor-removed-but-not-grepped-everywhere
description: BL-16 lift-vector stage 1 plan — U8's final "no floor" answer was applied to the four places the amendment named, but at least three more mentions of the 50 km/h floor (two diagrams, the kept-table, the tests list, the Risks entry) were missed; grep the whole plan for the superseded value, not just the amendment's own fix-list.
metadata:
  type: project
---

Plan `plans/flight-lift-vector/plan.md` answered U8 ("the commanded-speed floor in LV-1") twice:
first the architect recommended keeping a 50 km/h floor, then the user overruled it same-day with
"no floor" — a short paragraph appended at the very end of Decisions Requiring User Input, telling
the implementer to apply "no floor" "wherever the plan above still says 'floored at 50 km/h' or
'until LV-3'" and naming four locations (Affected Modules, the LV-1 build, the Co-moving table, the
LV-1 card's low-speed rows).

**Why this matters:** `grep -n "50 km/h\|floor"` over the whole plan found the floor still described
as live protection in at least seven places, three of which the amendment's own fix-list did not
name: diagram 5 (the λ-blend stateDiagram, "λ = 1 throughout and the commanded speed floored at
50 km/h"), diagram 6 (delivery flowchart, "commanded floor 50 km/h" on the LV-1 node), the
"Removed and kept" table's `MIN_IAS_KMH` row, the Tests section ("a take at 40 km/h is accepted and
flown to the 50 km/h floor"), and — the one that actually matters for risk — the Risks & Unknowns
entry itself, which still reads "the commanded floor keeps the law from being asked to go there"
after the floor was removed. That sentence is now false and nobody reading only the Risks section
would know it.

**How to apply:** when a plan's closing Decision answer overrides a value that was threaded through
diagrams, tables and a risks list earlier in the same document, do not trust the amendment's own
named fix-list to be complete. Grep the superseded value/phrase across the whole plan file and check
every hit against the final answer, especially the Risks & Unknowns section — a stale risk entry
that describes a removed mitigation as if it still existed is worse than no risk entry, because it
reads as settled when it is the opposite of settled. See also
[project_bl16_mode1_recut_u6_reopens_settled_e9](project_bl16_mode1_recut_u6_reopens_settled_e9.md)
for the sibling failure (a late answer reopening an already-closed E) and
[project_bl17_user_decision_narrows_e5_and_grep_derisks_r7](project_bl17_user_decision_narrows_e5_and_grep_derisks_r7.md)
for the general habit of grepping a plan's own stated risk before accepting its framing.

Secondary finding in the same pass: a fully-specified, independent user rule (switch SAU H/K/T/B on
at hand-back to the player) was recorded in `explore-notes.md` with its effectors already named, but
the plan explicitly scopes it out ("independent of this law and not part of this plan") with no
`[[ID]]` or named stage to carry it, and it appears nowhere in `BL-16.md`, `todo/todo/` or
`todo/backlog/`. A settled, concrete rule with no destination is a quieter version of the same
failure as a `deferred` row whose target doesn't mention the expectation.
