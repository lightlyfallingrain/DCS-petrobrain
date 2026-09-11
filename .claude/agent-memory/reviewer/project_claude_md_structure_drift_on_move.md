---
name: project_claude_md_structure_drift_on_move
description: When code moves between subprojects, check the losing subproject's CLAUDE.md Structure section for stale descriptions of the old location, even if the plan didn't list a CLAUDE.md update.
metadata:
  type: project
---

Cross-subproject refactor world-model-los-generalization (2026-09-12) moved
`line_of_sight_clear`'s algorithm from `body-layer/src/perception/geometry.py`
into `world-model/src/query/line_of_sight.py`. The module's own docstring was
correctly updated to describe the new delegation, but
`body-layer/CLAUDE.md`'s Structure section (which describes
`perception/geometry.py` in detail, including the sample_grid-vs-
describe_position deviation) was left describing the pre-move behavior as if
it still lived there. The plan's Affected Modules list never named the
CLAUDE.md file, so nothing forced the Implementer to touch it.

**Why:** CLAUDE.md Structure sections often restate implementation detail
(not just top-level module boundaries) for exactly the modules most likely to
move in a refactor — the more detailed the entry, the more likely it goes
stale silently when the code it describes moves elsewhere.

**How to apply:** whenever a review involves code moving between files or
subprojects, grep the losing (and gaining) subproject's CLAUDE.md Structure
section for the old function/module name, not just check whether the plan
listed a CLAUDE.md update. Flag drift even when the plan didn't call for the
edit — CLAUDE.md accuracy is a project invariant on its own, not scoped by
what one plan happened to list.
