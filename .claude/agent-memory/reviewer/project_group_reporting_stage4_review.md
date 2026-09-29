---
name: group-reporting-stage4-review
description: group-reporting (Stages 1-4 + sparse-scene backstop) reviewed APPROVED WITH MINOR FIXES — code correct, ROADMAP.md left stale after a same-branch fix landed, and two real (documented but unsurfaced) disclosure risks worth naming before flying.
metadata:
  type: project
---

Reviewed `feature/group-reporting` @ `e34443d` against `main` @ `f940867` (2026-09-29). 1349
passed/4 xfailed, ruff/mypy clean, matches implementation.md's own numbers exactly.

**Finding worth generalizing: a ROADMAP.md milestone entry can go stale *within the same branch*,
not just relative to a merge.** The group-reporting entry described the n=2 cohesion tautology as
"not fixed here... a mechanism decision for the next design pass" — true when that paragraph was
written, but two later commits on the *same branch* (`9ecedaf`/`b0f9518`) actually fixed exactly that
case with the `GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M` mechanism. Nobody went back to update the
roadmap prose after the fix landed. Lesson: when a plan/roadmap entry names an open risk, check
whether a *later commit in the same branch* already closed it before trusting the entry's framing —
`git log --oneline <base>..<tip>` costs nothing and would have caught this immediately. See
[[m8-probe-store-read-path-drift-gap]] for a similar "check the commit sequence, not just the
prose" lesson in a different module.

**Real, distinct residual risk this branch does NOT fix and should be told to the user before
flying**: the backstop only covers exactly-2-tracked-contacts. At 3+ tracked contacts spread
kilometres apart with nothing else in the scene, the *relative*-gap rule alone still merges
dissimilar unit types into one `Group` (confirmed by reading `_cluster_contacts`, and pinned by two
of the branch's own tests needing workarounds/rewrites: `test_report_all_groups_and_truncates_
multiple_contacts`, `test_2c_transcript_fixture_renders_four_lines_not_seven`). Because `render_
group_disclosure`'s threat-leading clause reports clock/range from the *nearest* member, not the
*leading* (threat) member, this can produce a genuinely misleading "Danger, ZSU-23-4... 3 o'clock,
1 kilometre" when the ZSU-23-4 is actually elsewhere. Separately, `CrewConsole._handle_report`
resolves a filtered-in contact's full `Group` and speaks all of it via `render_group_disclosure`,
so a scoped "report clock 3" can name a contact outside the requested sector. Both were honestly
documented by the implementer in `implementation.md`'s Notable Discoveries, but neither had reached
anything the user would read before flying (ROADMAP.md, once fixed, is the right place) — verified
by code reading, not just by trusting the implementer's own flag.

**Technique note**: "grep for the new mechanism's own call site" (the standing check from
`plans/precise-position-belief/`) generalizes to a second form here — when an implementation log
flags an open risk as "confirmed directly, not theorised," re-derive the confirmation yourself by
reading the actual gating code (`len(contacts) < 3` in `_cluster_contacts`) rather than trusting the
narrative description of where the boundary sits. The narrative was accurate here, but the habit is
what catches it when it drifts.
