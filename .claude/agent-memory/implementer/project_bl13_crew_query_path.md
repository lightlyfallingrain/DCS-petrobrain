---
name: bl13-crew-query-path
description: BL-13 Stages 1-3 (slotted report/describe) — the group full-roster leak through a filter, non-deterministic modal class, and parent_class_of vs profile_for.
metadata:
  type: project
---

BL-13 Stages 1–3, `feature/bl13-crew-query-path`. Full account:
`plans/crew-query-path/implementation.md`.

**`render_group_full_disclosure` names a group's FULL roster, so any filter applied upstream of it
leaks.** Measured: three contacts at two o'clock at 1/3/7 km cohere into one `Group`, and
`report two o'clock near` answered *"Armor, truck and infantry, 2 o'clock, 1 kilometre."* The
renderer is right for the unfiltered report it was written for. **Why this matters beyond BL-13:**
any future work that narrows a report's scope has to check what the renderer does with the scope,
not just that the scope is right. The plan did not anticipate it, and Stage 2 alone would have
shipped visibly wrong answers.

**Corollary that shaped the tests:** a filter's effect is not readable off the spoken sentence while
a roster renderer is in the path — a spoken assertion would be testing `belief.groups` cohesion
instead. Extracting `_report_scope` (the in-scope facts as a named, holdable thing) was what made
the filter testable at all, and the summary needed it anyway.

**`classification.parent_class_of` and `object_model.profile_for` are NOT interchangeable for a
believed classification.** `profile_for` keyword-matches *type* names:
`profile_for("BMP-2") == "OP_ARMORED"` but `profile_for("OP_ARMORED")` and `profile_for("OP_SRSAM")`
both return `DEFAULT_OP_CLASS`. A `class`-level belief holds the `OP_*` value itself, so only the
lattice walk resolves both forms. Consequence worth checking:
**`speech._is_air_defence` uses `profile_for`, so it does not recognise a class-level SAM.**
Pre-existing; not touched. Also `parent_class_of("ZSU-23-4")` is `None` — the lattice does not
resolve that string.

**`max(set(xs), key=xs.count)` is not a deterministic modal.** Set iteration resolves a tie by hash
order. Here the modal class was suppressed from the air-defence clause, so the tie silently decided
whether a SAM got named. Weight by the thing the wording claims (believed unit count, not contact
count — the user's own mock is 1-1 by contacts and 6-1 by units) and break ties explicitly.

**A "name it once" suppression plus a "drop it when long" budget can silence the thing entirely.**
The air-defence clause skipped the dominant class to avoid a duplicate; the dominant-class clause is
the budget's second drop; a scene whose modal class was `OP_LRSAM` lost the long-range SAM
altogether. Fix: recompute the suppression per budget candidate. **An unconditional-suppression
probe passed against the full original test set** — the interaction of two independently-tested
rules had no coverage. Worth probing wherever a conditional mention meets a conditional drop.

**`belief.groups` cohesion is erratic at test-fixture scales** — two contacts 2 km apart did not
group, two at clock 12 and clock 3 did, three at 1/3/7 km did. Do not build a fixture that depends
on a group *not* forming.

**`ruff format .` rewrites Python code blocks inside Markdown** (it reformatted
`body-layer/research/2026-10-05-security-audit.md`). Run each subproject's own documented form
(`ruff format src tests`), which is narrower than the `.` the orchestrator's prompt may give.
