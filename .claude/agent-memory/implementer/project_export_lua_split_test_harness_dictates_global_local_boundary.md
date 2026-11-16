---
name: export-lua-split-test-harness-dictates-global-local-boundary
description: AC-B12's Export.lua -> dofile-module split -- the existing Lua test harness's `local function NAME(` extraction regex, not architectural taste, decided which shared helpers had to become bare globals vs. which stayed local; same for the exact per-tick call order across the new module boundary.
metadata:
  type: project
---

`AC-B12` (`plans/ac-b12-export-modules/plan.md`) split `aircraft-layer/dcs-export/Export.lua` into
`core.lua`/`telemetry.lua`/`petrovich.lua`/`sight.lua`/`ai_pilot_wheel.lua`/`effectors.lua`/
`ptt_ics.lua`/`commands.lua` under a new `Petrobrain/` subfolder, with `Export.lua` reduced to a
`dofile` loader. Two implementation-specific findings not already in
`[[export-lua-module-split-cross-file-sharing]]` (the architect's own memory on this split):

**1. The seven `tests/test_*_lua.py` files' extraction regex is the real constraint on the
local/global design, not just a thing to update afterward.** Every one of them slices
`local function {name}\(` text out of a file via regex and splices several such slices into one
synthetic Lua script. That regex requirement forces two things that are easy to get backwards:

- A helper used across module files (`safe_call`, `debug_log`, `json_escape_string`,
  `encode_scalar`, `fmt_num_or_null`, `extract_json_*`, `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON`)
  **must still be declared `local function NAME(...)` / `local NAME = value`** in its owning file
  (`core.lua`) for the regex to find it, **and** separately published as a bare global
  (`_G.NAME = NAME`) right before `return M` so other `dofile`'d chunks can call it unqualified --
  not `core.safe_call(...)`. Using the dotted form anywhere a pre-existing function body called the
  bare name would have been a textual change inside a "pure cut-and-paste" stage, and would have
  broken every test harness that assembles a synthetic script from raw extracted text with its own
  stand-in globals (e.g. `test_ptt_lua.py`'s preamble defines a bare `client` table and a bare
  `GetDevice`, never a `core` table).
- Conversely, `function M.on_stop()`/`function M.foo(...)` (no `local function` backing) is
  **invisible to the extraction regex** -- a plan acceptance test that needs to extract a stop hook
  directly (AC-B13's own test, Stage 6) forced converting every `function M.xxx()` in all eight
  files to `local function xxx(...) ... end` + `M.xxx = xxx` at the bottom, for uniformity and so a
  future test can extract any entry point the same way. Decide this up front, not after writing the
  module cut -- re-threading eight files afterward is wasted motion.

**2. `test_dcs_export_lua_local_order.py` (GETGLOBAL vs. locally-declared-name check) is the
free, mechanical proof the global/local split is correct**, run per-file after the split: a name
read as global that the *same file* also declares `local` is a real bug; a name that crosses files
via `_G` is never flagged, because the consuming file never declares it local. Running this test on
every new module file is the cheapest confirmation that the cross-module channel actually works,
cheaper than reasoning about it by hand.

**3. Preserving per-tick call order across a module boundary needs tracing the *exact* original
sequence, not the plan's own illustrative snippet.** The plan's "Load mechanism" pseudocode grouped
`watched_args`/`payload`/`petrovich` pushes all after one `telemetry.send_telemetry_and_world_
objects(t)` call -- but the real file sent the ownship line, then watched-args, then payload, **then**
the world-objects poll (which can null `client` on a failed send), then the two Petrovich feeds
gated on `client ~= nil`. Following the illustrative grouping literally would have meant a failed
world-objects send could retroactively suppress watched-args/payload for a tick they had already
gone out on in the original. Fix: split `telemetry.lua`'s entry point into `send_ownship` (returns a
bool the loader gates everything else on, replacing the single-file version's one shared early
`return`) and a separate `send_world_objects`, called from the loader in the real original order.
**Always diff against the actual line-by-line order in the file being split, not a plan's
illustrative composition** -- the plan says as much ("Illustrative only... the order must not
change"), but it is easy to copy the illustrative snippet's grouping by default.

See also [[export-lua-module-split-cross-file-sharing]] (architect's memory on this same split --
the `dofile`-chunks-share-no-locals mechanism and the hardcoded-test-path hazard) and
`.claude/agent-memory/performance-reviewer/project_export_lua_per_frame_push_functions.md` (why the
per-frame cost patterns this split carries forward unchanged are already accepted).
