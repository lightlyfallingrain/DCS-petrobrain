---
name: project_m10_junction_review
description: M10 road-junction review — APPROVED WITH MINOR FIXES; missing ROADMAP.md entry was the only required fix; canonical-store-safety claim independently verified via file mtime/size.
metadata:
  type: project
---

M10 (`world-model/src/roadnet/junctions.py`, grid-bucketed union-find over road
endpoints/interior vertices, degree = endpoint(1 arm) + interior-attachment(2 arms), emitted at
degree >= 3) reviewed clean on algorithm correctness: bucketing math (cell_size = 3x tolerance,
3x3 neighbourhood scan) provably can't miss a same-tolerance pair across a bucket boundary since
cell_size >> tolerance guarantees at most 1-bucket-index separation. Arm-counting, singleton-drop,
and the documented ~32/3,634 coincident-route false-positive population all checked out against
the actual source and are honestly documented in the module docstring, not swept under the rug.

**Only required fix: `world-model/ROADMAP.md` had no M10 entry**, despite the plan's own Stage 5
explicitly requiring one and `implementation.md` claiming "all 5 stages" done. `grep -in
"m10\|junction"` on ROADMAP.md and todo/todo.md both came back empty. Lesson: always grep the
target ROADMAP.md for the milestone name/number, don't trust an implementer's "all N stages done"
summary — this is a distinct check from the plan-vs-diff scope check, since the file that's missing
an edit doesn't show up in `git diff --stat` as a problem (it shows up as an *absence*).

**Verified a self-reported process-note claim by filesystem inspection, not by re-reading the
report.** Implementer's report said a full `latakia-20km` rebuild ran on its own initiative
(caught mid-run by a concurrent architect session) and claimed it did NOT touch the canonical
`data/world-model/latakia-20km.sqlite`. Checked directly: canonical file was 8,994,816 bytes /
mtime Sep 5, but the reported rebuild's own numbers were 9,805,824 bytes — mismatch confirms the
rebuild went to a different output path, corroborating the claim independently rather than taking
it on faith. Same technique as [[project_stale_backlog_close_review]]'s "re-derive the numbers
yourself" discipline, applied to a build-safety claim instead of a bugfix claim.
