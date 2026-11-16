---
name: export-lua-module-split-cross-file-sharing
description: aircraft-layer/dcs-export/Export.lua's split into dofile-loaded modules (AC-B12) has two concrete cross-file hazards worth checking first on any future Lua-side DCS Export split -- shared-helper access across dofile'd chunks, and the Lua test harness's hardcoded per-function file path.
metadata:
  type: project
---

`AC-B12` (`plans/ac-b12-export-modules/plan.md`) splits `aircraft-layer/dcs-export/Export.lua`
(one 3,200-line chunk, exactly 200 top-level locals -- Lua 5.1's hard per-chunk ceiling) into eight
`dofile`-loaded module files. Two findings worth checking first on any similar future split,
Lua-side DCS Export script or otherwise:

**1. `dofile`-loaded chunks do not share locals -- a plain Lua global table is the standard, and
simplest, cross-module channel.** Each `dofile`'d file is its own chunk with its own local scope;
nothing is implicitly shared. The design that worked: each module file ends `return M` (its own
table of functions/state the loader or a later-loaded module needs), and the *loader* (the
remaining `Export.lua`) holds references to every module's returned table as its own locals, used
to build the four `LuaExportStart`/`Stop`/`ActivityNextEvent`/`AfterNextFrame` callbacks by
dispatching into each module in the **exact existing per-frame/5 Hz-gated order** -- every ordering
comment in the original file states *why* that order matters (command handling ahead of the 5 Hz
throttle; several functions must run every frame regardless of the throttle; one `list_indication`
read is shared by two consumers within the same tick), so the split must preserve it exactly, not
just preserve each function's own correctness in isolation.

A inbound-command dispatch table (op name -> handler) is built **once, after every handler-owning
module has loaded**, directly from those modules' returned tables -- no self-registering registry.
Simpler, and the one load-order constraint (`commands.lua` loads last) is explicit and visible in
one place rather than implicit in registration timing.

**2. The Lua test harness extracts named functions out of a *hardcoded* file path, and at least one
function per test file can land in a different module than its sibling in the same test.** This
project's `test_*_lua.py` files each duplicate a small `_extract_lua_function(name)` helper that
slices `local function {name}(...) ... end` out of one fixed `_EXPORT_LUA` path and runs it under a
real Lua interpreter. Before any split, grep every such test file for **every** name it extracts,
not just the one the test file is named after -- `test_ptt_lua.py` extracted both `safe_call`
(shared/core) and `push_ptt_state` (feature-specific) from the same hardcoded path;
`test_payload_lua.py` did the same for `json_escape_string` + `push_payload_state`. Each such test
needs **two** file paths after the split, not a simple one-path rename. Two other tests in the same
family (`test_dcs_export_lua_syntax.py`, `test_dcs_export_lua_local_order.py`) already glob
`dcs-export/*.lua` and needed **no** change at all -- check which pattern a given test uses before
assuming every Lua test needs editing.

See also [[export-lua-200-local-ceiling]] (why the split was needed at all) and
`aircraft-layer/CLAUDE.md`'s "a `local` referenced above its declaration compiles as a global"
note (the cross-module-global-read check, `test_dcs_export_lua_local_order.py`, correctly does
**not** flag a legitimate cross-module global read -- it only flags a name the *same* file also
declares `local`).
