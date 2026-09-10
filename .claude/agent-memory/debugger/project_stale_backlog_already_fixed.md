---
name: stale-backlog-already-fixed
description: Verify a bug still reproduces against current code before touching anything — todo.md backlog items can be stale.
metadata:
  type: project
---

The `association.py` DCS-namespace-mismatch backlog item (todo/todo.md, filed 2026-09-09) was
already fixed by commit `23f7157` (PB-2/BL-2 Stage 0, "Score association type-match against
reporting name too") before the fix branch was even cut, but the standalone backlog entry was
never marked done — only a passing mention in the Current Focus summary (line 57) documented the
fix. The related "hybrid_source.py only reads middle_list_text" gap cited in the same item was
also already closed (all five `LIST_TEXT_FIELDS` are read).

**Why:** milestone summaries and standalone backlog items can drift out of sync — a fix landed as
part of a broader milestone's Stage 0 doesn't automatically get the standalone bug-tracking entry
closed.

**How to apply:** always reproduce the reported symptom against current code first (run the exact
function/pairs cited in the bug report) before assuming a fix is needed. If it doesn't reproduce,
check `git log` on the affected file for a commit that already addresses it, check for existing
regression tests covering the cited cases, and if confirmed already fixed, close out the stale
backlog entry with evidence rather than re-implementing or leaving it open. See
[[project_roadnet_resync_validation]] for a similar "verify before assuming broken" pattern in a
different subsystem.
