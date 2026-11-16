---
name: ac-b12-export-lua-module-split-global-lookup-cost
description: AC-B12's Export.lua module split turned every cross-module helper call (safe_call, debug_log, json_escape_string, client, ...) from a GETUPVAL into a GETGLOBAL -- measured real but negligible, MONITOR not NOW
metadata:
  type: project
---

`dofile`-loaded Lua chunks share no locals, so `AC-B12`'s split (`plans/ac-b12-export-modules/
plan.md`) publishes `core.lua`'s per-frame helpers (`safe_call`, `debug_log`, `debug_dump`,
`fmt_num_or_null`, `encode_scalar`, `json_escape_string`, `extract_json_*`, `client`,
`WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON`) as bare globals (`_G.NAME = NAME`) so the other seven
module files' function bodies — and the Lua test harness's `local function NAME(` extraction
regex — keep reading them by a bare name unchanged.

**Mechanically confirmed by `luac5.1 -l -p` bytecode diff** (pre-split `fab32110`'s
`push_ptt_state` vs. post-split `Petrobrain/ptt_ics.lua`'s): every reference to `client`/`safe_call`
changed from `GETUPVAL` (direct slot access, upvalue of the enclosing chunk) to `GETGLOBAL`
(hash-table lookup in `_G`, by constant string key). Same instruction count (101), only the
addressing mode changed. The loader's own `call_if(mod, method, ...)` indirection in the new
`Export.lua` does **not** add to this — `call_if`, `commands`/`ptt_ics`/`sight`/etc. are all
`GETUPVAL` inside `LuaExportAfterNextFrame` (top-level locals of the loader chunk), confirmed the
same way. `call_if` itself adds a separate, smaller cost: ~5 extra VM instructions per guarded call
(an `EQ` nil-check, a `GETTABLE` on the small per-module table, `VARARG`, `TAILCALL`), no new
allocation (`{...}`/`table.pack` grepped for, none found — `...` forwards directly in a tail call).

**Timed the ratio, not DCS's absolute cost** — no `lua5.1` binary exists in this environment
(`luac5.1`, compiler/disassembler only, is present). Used the stock `lua` here (reports itself as
Lua 5.5.1) for a tight-loop upvalue-vs-global call microbenchmark: ~1.19-1.34x per-call ratio,
~3-6 ns absolute delta. Cross-checked with `luajit -joff` (interpreter path): reported 1.00x,
judged **not representative** of PUC-Rio 5.1's hash-based globals table (LuaJIT's interpreter
internals diverge enough from reference Lua that a null result there doesn't contradict the 5.5
number) — don't cite the luajit number as evidence this is free; cite the bytecode diff and the
5.5 ratio instead, both reported with their caveats.

**Verdict: MONITOR, not NOW.** ~15-20 such lookups added per frame in the typical steady state
(mostly inside `run_sight_servo`/`run_ai_pilot_wheel`, which already carry 6-8 per-frame
`safe_call(function()...end)` *closures* each — see [[export-lua-per-frame-closures-are-
established-pattern]]) × ~3-6 ns ≈ 100-300 ns/frame added. Two to three orders of magnitude below
the closure-allocation cost this codebase already accepts in the same functions (a GC-pressure
heap allocation vs. a stack-only hash lookup), and root `CLAUDE.md`'s "no hard real-time budget in
this phase" governs — there is no budget this could violate yet.

**How to apply**: if a future stage re-opens `Export.lua`'s per-frame cost as one pass (the
existing closures memory already earmarks this for "if/when Petrobrain Runtime's real-time budget
phase begins"), the cheap mitigation for *this* finding specifically is: `local safe_call =
safe_call` (etc.) once per module file, right after load, converting every subsequent reference in
that file back to a local/upvalue access. One line per helper per module, not attempted here —
this split's own `review.md` and `implementation.md` both treat "no textual change to moved
function bodies" as load-bearing for the test harness, so doing this now would have been scope
creep on a plan explicitly scoped as "no behaviour change except AC-B13."
