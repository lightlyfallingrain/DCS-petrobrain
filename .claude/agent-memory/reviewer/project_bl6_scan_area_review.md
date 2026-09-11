---
name: project_bl6_scan_area_review
description: BL-6 scan_area/get_task_status/cancel_task review outcome and the copyrighted-PDF-in-git finding
type: project
---

BL-6 (`plans/bl6-commands-inspect-adapt/plan.md`) implementation reviewed 2026-09-11:
APPROVED WITH MINOR FIXES. `belief.tasks`/`belief.tools.scan_area` stayed pure/DCS-I/O-free as
required; the live effector trigger and wheel-state diagnostic read are correctly confined to
`console.py`'s handlers. The two hard constraints (observation/engagement separation — only wheel
buttons 3001/3015 ever pressed, never 3020/3009/3010; `cancel_task` removes its `AttentionArea`)
are both exercised by real tests, not just asserted in docstrings — check for this pattern
(constraint asserted in prose vs. actually tested) on any future milestone touching this same
wheel-command surface.

**Why:** this is a good template for what "test coverage adequate for hard constraints" looks
like in this project — grep the actual DCS button/command codes used in `Export.lua`'s new code
against the constraint's forbidden list, don't just trust the docstring's claim.

**Non-obvious finding, worth checking again:** the Implementer committed a 16.25 MB
third-party copyrighted DCS module PDF (`docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf`,
added in `663c7f3` mid-investigation, not part of the final plan's Affected Modules list) into
git history, in the wrong module (`docs/concept/` is architecture-docs, not research material) —
required fix. Research findings from manual cross-checks belong in `aircraft-layer/research/*.md`
as extracted notes (which the Implementer's investigator work already did correctly), not as a
raw binary scan. Watch for this pattern again: an investigator/probe session that reaches for a
real reference manual is liable to commit the whole file rather than citing/extracting from it.

**Also caught:** a docstring citing the wrong file for "where the frozen tool-set contract lives"
(`tool_api.py` said `docs/concept/PETROBRAIN_RUNTIME.md` §3.3, correct answer is
`plans/body-layer/plan.md` §3.3 — the same docstring's own next line has the correct citation).
Worth a quick grep of any new "§3.3"/"frozen surface" doc-reference claim against the actual file.
