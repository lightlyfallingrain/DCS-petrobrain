### Performance Review

Batch: AC-B12 (Export.lua module split) + AC-B13 (AI-wheel stop-hook fix), commits `6919c86d`,
`0812e98f`, `c304dcc5` against pre-split `fab32110`. Reviewer already approved
(`plans/ac-b12-export-modules/review.md`, including the "Re-review" round). This pass checks only
runtime cost risk on `Export.lua`'s hot path (`LuaExportAfterNextFrame`, every DCS frame), per the
plan's own flagged risk: "Known, already-accepted per-frame cost patterns ... are unchanged by this
split ... Performance Reviewer should not re-flag these as new."

**Scope note on the harness**: no `lua5.1` binary exists on this machine (confirmed:
`which lua5.1` fails). `luac5.1` (compiler/disassembler) is present and used for bytecode-level
proof. For the one timing number below, I used the stock `lua` binary available here, which
reports itself as **Lua 5.5.1** — not DCS's embedded 5.1. I also ran the same benchmark under
`luajit -joff` (interpreter path, JIT disabled) as a cross-check; it reported no difference
between the two addressing modes, which I judged *not* representative of PUC-Rio Lua 5.1's
GETGLOBAL (hash-table lookup in `_G`) vs. GETUPVAL (direct slot access) distinction, since
LuaJIT's interpreter internals diverge from PUC Lua's reference implementation. The Lua 5.5 number
is reported as a **qualitative ratio**, not a 5.1 absolute figure — both VMs share the same
fundamental addressing-mode shape (hash-keyed globals vs. array-indexed upvalues/locals), so the
ratio should be in the same ballpark, but this is inferred, not measured on the target VM. **The
benchmark can fail**: a bug that made both call paths resolve to the same storage (e.g. a typo
reusing the global for both cases) would print a 1.00x ratio for the wrong reason, which is exactly
why the result was double-checked against the independent bytecode proof (GETGLOBAL count is a
mechanical fact, not a timing artifact) before relying on either number.

### What was measured vs. inferred

- **Measured (bytecode, exact)**: disassembled `push_ptt_state` pre-split
  (`/tmp/export_pre_split.lua:693`, extracted from `fab32110`) vs. post-split
  (`Petrobrain/ptt_ics.lua:53`) with `luac5.1 -l -p`. Same 101 instructions, same shape. The only
  change: `client` and `safe_call` access went from `GETUPVAL` (slot 0/1, direct) to `GETGLOBAL`
  (constant-indexed hash lookup in `_G`) at every reference. Confirmed the same pattern holds for
  `call_if`'s own call sites in the new `Export.lua` loader (`LuaExportAfterNextFrame`): `call_if`,
  `commands`, `ptt_ics`, `sight`, etc. are all `GETUPVAL` there (they are top-level locals of the
  loader chunk), so the `call_if` indirection itself adds no *new* global lookups — only the
  helpers moved into `core.lua` and read as bare globals from the other seven module files do.
- **Measured (timing, Lua 5.5, qualitative ratio only)**: a tight loop calling a function 2×10^7
  times through an upvalue vs. through a bare global. Three runs: 1.34x, 1.19x, then a `luajit
  -joff` run at 1.00x (discounted, see above). Absolute per-call delta in the Lua 5.5 runs: ~3-6 ns.
- **Inferred, not measured**: the DCS-specific absolute frame-time cost. No live-DCS profiling tool
  exists in this repo (confirmed in `.claude/agent-memory/performance-reviewer/
  project_aircraft_layer_hotspots.md` — this is a standing, repo-wide gap, not something this pass
  could close). The arithmetic below (lookup count × per-lookup ns) is therefore an order-of-
  magnitude estimate, not a DCS measurement.

### Findings

#### Cross-module helper calls: upvalue → global (`safe_call`, `debug_log`, `json_escape_string`, `fmt_num_or_null`, `encode_scalar`, `extract_json_*`, `client`, the two wheel-button constants)

- **Location**: every module file (`ptt_ics.lua`, `sight.lua`, `ai_pilot_wheel.lua`, `telemetry.lua`,
  `petrovich.lua`, `effectors.lua`) calling `core.lua`'s helpers by bare name, per `core.lua`'s own
  documented design (published via `_G.NAME = NAME` so existing function bodies and the Lua test
  harness's extraction regex both keep working unchanged).
- **Risk**: each such call site changed from a direct upvalue slot read to a hash lookup in `_G`.
  Counted call sites in the per-frame (not-5-Hz-gated) functions: `run_sight_servo`/
  `sight_servo_tick` (~6-8 `safe_call`/frame in the steady "closed" branch, per the existing
  `export-lua-per-frame-closures-are-established-pattern` memory, unchanged by this split),
  `run_ai_pilot_wheel` (~3-5 `safe_call`/frame depending on correction-phase branch),
  `push_ptt_state`/`push_spu8_state` (2 each), `release_pending_search` (1, conditional),
  `push_slew_trace` (early-exit `safe_call` when `SLEW_DEBUG` is off). Roughly 15-20 global lookups
  added per frame in the typical steady state, against a measured ~3-6 ns/lookup delta (Lua 5.5
  proxy) → on the order of 100-300 ns added per frame. Against DCS's own observed per-frame
  cadence (`Export.lua`'s header comment: ~8 ms/frame live-measured in an earlier stage, i.e.
  ~125 Hz), this is roughly 0.001-0.004% of one frame's budget.
- **Action**: **MONITOR**, not NOW. This is an order of magnitude *below* the already-accepted cost
  of this file's own per-frame `safe_call(function() ... end)` closure-allocation pattern (heap
  allocation + GC pressure per closure, vs. a hash lookup that touches no heap at all) — the
  existing `export-lua-per-frame-closures-are-established-pattern` and
  `export-lua-per-frame-push-functions` memories already judged that heavier, pre-existing pattern
  as not worth fixing in this project phase. Root `CLAUDE.md`'s "no hard real-time budget in this
  phase" applies directly: this project is not yet in the Petrobrain Runtime phase where a
  per-frame budget exists to violate. No credible scenario at today's or any near-term scale makes
  this visible as cockpit stutter.
- **Mitigation, if ever revisited**: cache each module's own frequently-used `core` helpers as
  local upvalues at the top of that module file (`local safe_call = safe_call` right after
  `core.lua` loads, inside each consuming module) — converts every subsequent reference in that
  file back to a cheap local/upvalue access at the cost of one extra line per helper per module.
  Cheap, mechanical, and exactly the kind of change that belongs in the single pass this project's
  own memory already earmarks for "if/when Petrobrain Runtime's real-time budget phase begins" —
  not worth doing piecemeal now.

#### `call_if` indirection in the loader

- **Location**: `Export.lua`'s `call_if(mod, method, ...)`, called ~8 times in the unconditional
  per-frame section of `LuaExportAfterNextFrame` and ~9 more times in the 5 Hz-gated section.
- **Risk**: adds one extra `CALL` into `call_if` itself, plus (inside it) an `EQ` nil-check,
  `GETTABLE` (hash lookup by string key in the small per-module table — `ptt_ics`, `sight`, etc.,
  each holding a handful of entries, not the full `_G`), `VARARG`, `TAILCALL` — roughly 5 extra VM
  instructions per guarded call, confirmed by disassembling `call_if` and its call sites. The
  operands (`mod`, the method-name string constant) are themselves `GETUPVAL`s inside the loader,
  not globals (confirmed by disassembly), so this indirection adds no *new* global-lookup cost on
  top of the one above — it's a separate, smaller cost.
- **No per-call allocation**: `call_if`'s `...` forwarding (`return mod[method](...)`) is a direct
  tail-call forward in Lua 5.1/5.5, not boxed into a table (`{...}`/`table.pack` patterns were
  grepped for across every new/changed file — none found outside comments).
- **Action**: MONITOR. ~17 call sites × ~5 instructions each is on the order of a few hundred
  nanoseconds per frame, same order of magnitude as the global-lookup finding above and for the
  same reason not a credible risk in this phase.

#### `dofile` load-time cost (one-time)

- **Location**: `Export.lua`'s `load_module`, called 7 times (after `core`) at script (re)load,
  i.e. once per mission start/restart, not per frame.
- **Risk**: none credible. Eight small `dofile`s vs. one large file is a few extra filesystem
  opens and `luac`-equivalent parses, on the order of milliseconds at worst, against a DCS mission
  load that already takes several seconds. This is explicitly a one-time cost the plan's own
  "Load mechanism" section accepts in exchange for relieving the 200-local ceiling.
- **Action**: APPROVED, no further check needed.

#### Shared `list_indication(6)` read

- **Location**: `Export.lua`'s `LuaExportAfterNextFrame`, 5 Hz-gated section: `local helperai_raw =
  safe_call(petrovich.get_helperai_indication)`, then passed as a parameter to both
  `ai_pilot_wheel.update_ai_pilot_wheel_overlay(helperai_raw, t)` and
  `petrovich.push_indication(t, helperai_raw)`.
- **Verified**: survived the split intact. Read `petrovich.lua`'s `push_indication(t, raw)`
  (consumes `raw` directly, does not call `list_indication` again — its own header comment states
  this explicitly, "not a second device read") and `ai_pilot_wheel.lua`'s
  `update_ai_pilot_wheel_overlay(raw, t)` (same — consumes the passed `raw`, no
  `list_indication` call in that function; confirmed by grep, the only other `list_indication`
  references in that file are in comments). This is the fix the `flight-control-p1-perframe-
  indication-read` memory requested in a prior batch; nothing in this split reintroduces the
  duplicate read it fixed.
- **Action**: APPROVED.

#### Everything else flagged by the plan as pre-existing and unchanged

Confirmed by spot-check (not re-derived from scratch, per the plan's own request not to re-flag
these): `run_sight_servo`'s per-frame `safe_call(function()...end)` closures, the repeated
uncached `GetDevice(0)` reads across `push_ptt_state`/`push_spu8_state`/`push_slew_trace`-adjacent
functions, and the 5 Hz `LoGetWorldObjects` full-iteration send in `telemetry.lua` are all moved
verbatim, same shape, same call count. No new allocation, no new full-dataset iteration, no new
redundant query introduced by the split itself.

### Verdict

APPROVED — MONITOR

The split's two new cost sources (global-lookup promotion for cross-module helpers; the `call_if`
indirection) are both real, mechanically confirmed by bytecode diff, and both roughly two to three
orders of magnitude below the per-frame closure-allocation pattern this codebase already accepts
in the same function. Root `CLAUDE.md`'s "no hard real-time budget in this phase" governs here —
there is no budget to violate yet. Monitor only: if/when the Petrobrain Runtime phase opens a real
per-frame budget, re-open this file as one pass (per the existing `export-lua-per-frame-closures-
are-established-pattern` memory's own note) and apply the "cache core's helpers as local upvalues
per module" mitigation above alongside whatever else that pass finds, rather than patching this
one finding in isolation now.
