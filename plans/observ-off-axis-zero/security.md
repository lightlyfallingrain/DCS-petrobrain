## Security Deep Analysis: observ-off-axis-zero

### Dependency Status
No dependency change. Pure Lua logic edit inside `Export.lua`, plus a Python test file; no new
package, no new inbound wire path, no schema change (correctly judged by debug.md/review.md —
no `EXPORT_SCRIPT_VERSION` bump needed).

### Scope note
LAN-only, single-user threat model (root `CLAUDE.md` scope direction, 2026-10-21). This change
touches neither a listening socket nor an LLM-readable text path — it is internal servo logic
inside the existing DCS Export.lua hook. Scaled accordingly: no CVE search, no port-scan surface
review. Mode 2 steps actually applicable here are: arbitrary-code-execution patterns, globals/leaks,
and pcall coverage on the new write.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `Export.lua:1339` `sight_was_observ_on` | new module-level state | Declared `local`, confirmed by grep (`grep -n 'sight_was_observ_on'`) — no global leak. Reset in `LuaExportStop` (line 1825), matching the existing reset pattern for the rest of the `sight_*` block. | None |
| `Export.lua:1374-1383` `sight_observ_transition` | new pure function | No I/O, no DCS API call, no `loadstring`/`dofile`/`net.dostring_in` — takes two booleans, returns two booleans. Zero execution risk by construction. | None |
| `Export.lua:1449-1450` `sight_point_quiet(0.0, 0.0)` call on the edge | new call site, existing function | `sight_point_quiet` (line ~1158) is the sole writer of `CMD_AI_AZ`/`CMD_AI_ELEV` in the file (confirmed by grep, matching debug.md's and review.md's own grep) and already wraps both `SetCommand` calls in `pcall` (lines 1160-1161, pre-existing). The new call site inherits that guard — it does not bypass it, and no new unguarded `SetCommand`/`GetDevice` call was introduced. | None |
| `Export.lua:1412-1413` edge decision placement | runs at top of every frame, before `dt`/other state touched | Confirmed by direct read (lines 1395-1423): the write only fires inside the existing `if not observ_on then ... return end` branch, and the whole point of the fix is to *stop* a stale non-zero value persisting while OBSERV is off. Nothing in the diff lets the axis be driven while OBSERV is off — the change is strictly in the opposite direction (one write, then silence). | None |
| whole diff | secrets / credentials | `git diff` grepped for password/secret/api.?key/token: no hits. | None |
| whole diff | dynamic code execution, shell-out, network, file-write patterns | `loadstring`/`dofile`/`net.dostring_in`/`os.execute`/`io.popen`/`socket.` all absent from the diff; no new `open(...)` in write mode. | None |
| `run_sight_servo` call site | frame-stall / error-propagation risk inside `LuaExportAfterNextFrame` | The new code adds two local-variable assignments and one already-`pcall`-guarded function call to a function that already ran every frame; no new unguarded call, no new blocking operation, no change to how `observ_on` itself is read (still `safe_call`-wrapped, pre-existing, line 611). No new frame-stall or unhandled-error surface. | None |

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Passed to Reviewer
None beyond what `review.md` already recorded (the failed-OBSERV-read edge case and the
restart-test coverage gap are correctness/robustness points, already surfaced there as Optional
Refinements, not security findings).

### Backlog
No finding produced here that needs an ID — nothing identified that requires fixing, deferring, or
tracking. Nothing filed.
