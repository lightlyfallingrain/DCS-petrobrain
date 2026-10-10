---
name: bl13-crew-query-path
description: BL-13 Stages 1-3 (slotted report/describe) — the group full-roster leak through a filter, non-deterministic modal class, parent_class_of vs profile_for, infantry as an unbounded cohesion bridge, and the singular/plural count fold.
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

**~~`belief.groups` cohesion is erratic at test-fixture scales~~ — CORRECTED by the review, and the
real behaviour is worse than "erratic".** It is deterministic, and traceable to
`_OP_CLASS_COHESION_BACKSTOP`: `OP_INFANTRY` is `EAGER`, which drops the absolute backstop to
`math.inf` for a pair where **either** member is infantry. So **an infantry contact acts as an
unbounded bridge that merges non-infantry contacts** — armour at 1 km and a truck at 3 km do not
cohere alone, but add an infantry contact at 7 km and all three become one group. That is why the
observations looked random. Standing advice unchanged (do not build a fixture that depends on a group
*not* forming) but the reason is now known; filed as a body-layer backlog item.

**`ruff format .` rewrites Python code blocks inside Markdown** (it reformatted
`body-layer/research/2026-10-05-security-audit.md`). Run each subproject's own documented form
(`ruff format src tests`), which is narrower than the `.` the orchestrator's prompt may give.

**Round 2 (the review's required fix).** The summary's count-clause fold spoke a plural noun against
a singular count — *"One trucks"*. General lesson extracted to
[[feedback-guard-fixture-must-not-pick-a-degenerate-case]]; two things specific to this module:

- **`_summary_count_clause` had three noun sites and only one inflected.** The review named one
  (`"at least one units"`); enumerating the function found a second (`"about one units"`, via a
  floored midpoint when a `cardinality` interval's `lo` is zero). They are now one `_unit_word`
  helper whose docstring carries the enumeration, so a fourth cannot be added quietly.
- **A renderer that substitutes a word into an already-built clause needs the number handed to it.**
  `_summary_count_clause` now returns `tuple[str, int]` — clause plus the number it spoke — because
  only it knows which branch ran, and re-deriving the number from the rendered string would be a
  second place to disagree.

**The worktree has no `.venv`.** Use the main checkout's binaries by absolute path
(`/Users/sg/Code/DCS-petrobrain/<subproject>/.venv/bin/...`) with `cwd` inside the worktree's own
subproject directory. Also: the worktree sandbox **refuses a compound Bash command whose program
name is a shell variable** (`V=.../bin && $V/ruff ...`) as unverifiable — run the gates as separate
plain commands with the path spelled out.
