---
name: voice-command-completeness-stages1-5-approved
description: Review outcome for voice-command-completeness Stages 1-5 (report families, numeric bearing, o'clock scans, compass-gaze fix) — APPROVED, no required fixes.
metadata:
  type: project
---

Reviewed on `feature/binocular-optic` (which had absorbed voice-command-completeness), scoped to
Stages 1-5 only — the sibling binocular-optic milestone in the same branch was already reviewed
separately (`plans/binocular-optic/review.md`) and was out of scope.

APPROVED, no required fixes. `body-layer` pytest 1076 passed/4 xfailed, `audio-adapter` pytest 179
passed/1 skipped — both matched the implementer's claimed numbers exactly on independent re-run.

**Two things worth direct execution rather than reading, because the brief specifically asked for
them and both turned out correct but untested:**

1. `logger._active_gaze`'s absolute→relative conversion (`legs_within_wedge` fed a heading-rotated
   relative center) at the 350°→0°→10° compass wrap. The modulo formula
   `(absolute_center - heading + 180) % 360 - 180` has no discontinuity there — confirmed by
   running it, not just reading it. No test exercises this wrap case though (existing tests only
   cover heading 0 and 90).
2. `_handle_report`'s multi-contact grouping+truncation seam — `group_facts` (test_callouts.py) and
   `render_report`'s truncation (test_speech.py, hand-built strings) are each unit-tested in
   isolation but nothing wires them together through the real `handle_command("report_all", ...)`
   path with more than one contact. Built a 5-contact scenario by hand through the real dispatch;
   grouping/sort/cap/"And more." all correct. No regression test for this seam exists.

Both filed as optional refinements, not required — matches this role's recurring caution
([[feedback_boundary_only_tested_via_fixture]]-adjacent: a seam being *correct* today doesn't mean
it's *guarded*) but here the code was independently verified correct, which is what kept it out of
Required.

**A real but harmless dataclass-invariant gap**: `ScanPlan.__post_init__` doesn't forbid
`fixed_look` co-existing with `commanded_sector`/`commanded_legs` — only `commanded_sector` vs
`commanded_legs` mutual exclusivity is checked. `tests/test_gaze.py` directly constructs that
uncovered combination to prove `gaze_at`'s tie-break (`fixed_look` always wins), so it's exercised
and intentional, not an oversight — but no production call site can reach it (`fixed_look_at()`
always zeroes the other two; `logger._apply_active_gaze` replaces the whole plan rather than
merging). Worth tightening if `ScanPlan` ever gets a third construction site.

Git hygiene was clean on this branch: `git log main...feature/binocular-optic` showed no bundled
side-quest commits, rename (`handle_f10_command`→`handle_command`) left no stale references outside
one historical docstring mention, and `todo/todo.md`'s two Stage-5-closing backlog entries were
both correctly flipped to `[x]` with a "Closed by Stage 5" note rather than silently deleted.
