---
name: export-lua-new-helper-can-make-an-earlier-function-stale
description: When adding a new Lua constant/function mid-file in Export.lua, check whether an EARLIER-declared function now needs it too -- the "must stay below its locals" rule bites in both directions, not just for new code.
metadata:
  type: feedback
---

When a plan adds a new pure function or constant to `Export.lua` and asks for an *existing*
per-frame debug/trace function to also read it (BL-B80 v3, Stage 6: `push_slew_trace` gained
`mark_az_raw`/`mark_el_raw`/`mark_clipped`, needing the new `sight_mark_is_clipped` and
`ASP17_FIELD_*`/`MARK_*` constants), check where that existing function is declared relative to
the new names -- not just where the new names themselves are declared relative to each other.

**Why:** Lua has no hoisting. `push_slew_trace` was declared early in the file (right after
`safe_call`), long before `sight_mark_is_clipped`/the mark constants (declared much later,
grouped with `run_sight_servo`'s own constants). Adding a reference to them inside
`push_slew_trace` without moving it would have reproduced the exact "local read as global, nil at
call time" bug this same function caused once before (2026-09-21, per its own comment) -- and this
project has a parametrized regression test for exactly this
(`tests/test_dcs_export_lua_local_order.py`, `GETGLOBAL` vs. declared-locals diff across every
`dcs-export/*.lua` file). That test is what caught it here, run deliberately after the edit, not
by inspection.

**How to apply:** Whenever a plan says "function X also needs constant/helper Y", before writing
the edit, `grep -n` both names in `Export.lua` and compare line numbers. If X is declared above Y,
X's whole definition has to move below Y (not just the one line that now references it) --
cut-and-reinsert the comment-plus-function block as a unit, same as any other function in this
file that was found calling a `local` declared below itself. Then run
`test_dcs_export_lua_local_order.py` by name (not just the full suite) to confirm, since it is the
one test purpose-built to catch this and is cheap enough to always run after any `Export.lua` edit
that adds a cross-reference between two existing pieces of the file.

See also [[sight_clip_to_field_body_deg-margin-reduced-call-shape]] for a related v3 Stage 6
discovery in the same function.
