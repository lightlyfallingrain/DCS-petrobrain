---
name: project-f10-command-vocabulary-stage6-7
description: F10 command vocabulary Stage 6/7 (dispatch + docs) implementation notes
metadata:
  type: project
---

Implemented Stage 6 (`body-layer/src/belief/crew_console.py` dispatch) and Stage 7 (docs) of
`plans/f10-command-vocabulary/plan.md`; Stages 1-5 (attention.py RelativeSector/wedge_deg,
contacts.py add_area/reproject_relative_areas, logger.py tick wiring, tools.py scan_area params,
Hook Lua + ALLOWED_COMMANDS) were already committed and matched the plan on inspection -- no
rework needed.

`_handle_scan` (replacing `_handle_scan_forward`) mirrors `belief/console.py`'s existing
`_handle_scan_area` handler's register-then-trigger shape almost exactly -- that BL-6 handler was
already the reference implementation for D5's contract, just for the typed `scan-area` command.
Dispatch uses two lookup tables (`_RELATIVE_SCAN_TOKENS`, `_BEARING_SCAN_TOKENS`) rather than a
14-branch if/elif, matching `belief.utterance`'s ordered-table idiom.

Removing `scan_forward` (not aliased, per plan D4) broke 4 pre-existing tests outright since the
token no longer dispatches at all -- rewrote them to the new vocabulary; this is expected fallout
of an approved plan decision, not a "don't modify existing tests" violation.

Found one doc beyond the plan's named Stage 7 list that was genuinely stale:
`aircraft-layer/CLAUDE.md`'s Structure bullet for `petrobrain-f10-commands-hook.lua` still said
"three fixed items: Watch Nearest/Scan Forward/Cancel Task" after Stage 5's Hook-script commit --
fixed it alongside `WORKFLOW.md`'s deploy section (same file class, same genuinely-wrong bar).

Final counts: body-layer 520 tests (was 506, +14), aircraft-layer 109 unchanged (docs-only touch).
