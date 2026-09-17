---
name: project_f10_scan_naked_eye_fix_approved
description: Live-test fix 89b8b1d (scan-naked-eye-not-9k113) reviewed and approved; console.py's scan-area still drives the 9K113 under the same name, backlogged not required.
metadata:
  type: project
---

Reviewed commit `89b8b1d` on `fix/scan-naked-eye-not-9k113` (body-layer only): removed the 9K113
effector call from `crew_console._handle_scan` (Scan vs Observ glossary distinction) and stopped
Cancel Task from speaking a task id (`render_cancel_readback`). APPROVED, no required fixes.

**Why:** two defects found on the milestone's first live F10 test, fixed in a small, well-scoped
commit with genuinely-strengthened test rewrites (not just renamed assertions).

**How to apply:** when reviewing effector-removal fixes, grep *every* caller of the removed
function, not just the one the bug report named — `console.py`'s typed `scan-area` debug command
still calls `trigger_petrovich_search("forward")` under the same "Scan" name and has the identical
Scan/Observ semantic mismatch this commit fixed on the F10 path. It's pre-existing and out of this
commit's disclosed scope, so it was recorded as optional/backlog, not required — but it's exactly
the kind of "other callers" gap worth surfacing even when out of scope. Also: verifying a
docstring's "safe to read the captured reference" claim means reading the actual `replace()`/
mutation call, not trusting the prose — see [[project_bl7_mission_phase_minor_fixes]] and the
earlier stale-captured-area bug in this same milestone (`plans/f10-command-vocabulary/review.md`'s
first round) for why this project has already shipped this exact bug class once.
