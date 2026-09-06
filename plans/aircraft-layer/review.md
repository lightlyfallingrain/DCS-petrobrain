### Review Summary

Reviewed `feature/aircraft-layer-telemetry` (stages 1-2 of `plans/aircraft-layer/plan.md`
only, per implementation.md — stage 3 live-DCS test and stage 4 Mac API deliberately
deferred) against the plan and root `CLAUDE.md`. Scope: `aircraft-layer/dcs-export/Export.lua`,
`src/schema/`, `src/collector/` (cache, TCP server, debug CLI), `tests/`.

Ran the full check sequence myself from repo root: `ruff format --check`, `ruff check`,
`mypy --strict`, `pytest` — all pass (20 tests), matching implementation.md's claims exactly.

Plan-fidelity check: Export.lua is push-only and never listens (confirmed by reading the
file — no listening socket, no request-handling branch); no new dependency anywhere
(`pyproject.toml` has `dependencies = []`, stdlib-only imports throughout); both
`dcs_model_time_s` and `received_wall_clock_s` are present on every `TelemetrySample` and
populated at the correct point (Export.lua's own clock vs. the collector's receipt time,
not conflated); collector binds `127.0.0.1` only, no LAN-facing surface introduced yet;
5 Hz throttle implemented via the documented `LuaExportActivityNextEvent` mechanism, not a
busy-loop or frame-count guess. No stage-4 API scaffolding was added ahead of schedule —
scope matches stages 1-2 exactly, no drift.

The flagged unresolved risk (`LoGetSelfData()` sub-field shape) is reasonable defensive
coding, not scope creep: `safe_call`/`pcall` wraps the actual DCS API calls, and the
nested-then-flat `Position.p.x`-vs-`Position.x` fallback is ordinary (non-pcall-needing)
Lua table indexing that correctly yields `nil` on a wrong guess. The subsequent
completeness check (`x == nil or ... or ias == nil or tas == nil`, though notably not
including `hdg` — see below) causes the sample to be silently skipped rather than sending
malformed data or crashing the export callback. This fails safe as claimed.

One correctness gap found in the collector's TCP accept loop (below) that isn't covered by
the "needs a live DCS instance" exemption — it's a plain socket-programming issue,
reproducible and testable without DCS, and should be fixed before stage 3's live test
rather than being discovered as a mysterious collector crash mid-mission.

### Required Fixes

- **`CollectorServer.serve_forever`/`_handle_connection` (`src/collector/server.py:76-103`)
  is not resilient to an abrupt client disconnect.** `_handle_connection`'s `conn.recv()`
  loop only handles a *graceful* close (`chunk == b""`). An ungraceful disconnect —
  `ConnectionResetError`/`ConnectionAbortedError`, which is the common case on Windows when
  DCS is force-quit, crashes, or a mission ends abruptly mid-write — raises out of
  `_handle_connection`, past the `try/finally` in `serve_forever` (which only closes the
  socket and logs, it does not swallow the exception), and out of `serve_forever` itself,
  killing the whole collector process. This directly contradicts the module's own stated
  design intent ("accept connections ... until interrupted... re-accepts after each
  disconnect", `server.py:76-82`) and the plan's framing of the collector as the long-running,
  trusted local process. Given stage 3 is exactly the scenario most likely to surface this
  (mission restarts, DCS exits), fix now: catch `OSError` around the accept-loop's per-connection
  handling in `serve_forever`, log, and continue back to `accept()`. Add a unit test using a
  real socket pair (bind a `CollectorServer` to an ephemeral port, connect, send a partial
  line, then abort the connection) to confirm the accept loop survives and can accept a
  second connection afterward — this doesn't require DCS to test.

### Optional Refinements

- `_handle_connection`'s `buffered` string has no upper bound — a peer that sends bytes
  with no `\n` indefinitely (only plausible from a misbehaving/malicious client, not the
  trusted Export.lua) grows unbounded. Low priority since the socket is loopback-only,
  fed by a script this project controls — but worth a max-length guard before this pattern
  is ever reused for a LAN-facing listener (it should not be, per plan decision 2, but
  flagging for anyone who copies this module as a template for stage 4's HTTP server).
- Root `CLAUDE.md`'s "Module Responsibilities" section still has no `aircraft-layer/`
  bullet. The plan itself already flags this as stage 6/DoD work, not this pass's scope —
  not a blocker here, just confirming it's still open before DoD closes stage 1-2.
- `Export.lua`'s `encode_json_line` uses `tostring(value)` for numeric encoding with no
  guard against Lua producing `"nan"`/`"inf"` (not valid JSON) if a DCS export function ever
  returns a non-finite number. Extremely unlikely for kinematic state in a running mission;
  not worth blocking on, but worth a one-line note in `WORKFLOW.md` once stage 3 either
  confirms it's a non-issue or surfaces it.

### Verdict

APPROVED WITH MINOR FIXES

The one required fix is small, self-contained, and testable without a live DCS instance —
fix it and add the reconnection-resilience test before proceeding to stage 3 (a crash
mid-live-test would otherwise be misdiagnosed as a DCS/Lua problem rather than a Python
socket-handling gap). Everything else — plan fidelity, provenance/timestamp invariant,
loopback-only binding, no new dependency, schema validation boundaries, defensive Export.lua
field access — checks out clean.

### Review Confidence

Full read — all changed/new files in `aircraft-layer/` were read in full (Export.lua,
schema, cache, server, `__main__`, both test files, `pyproject.toml`, `.gitignore`), and
the full format/lint/type/test sequence was run directly rather than trusted from
implementation.md's report.

Separately (not part of this feature's scope but caught while checking `git status`): an
untracked `.claude/agent-memory/implementer/project_aircraft_layer_stage1_2.md` and a
modified `.claude/agent-memory/implementer/MEMORY.md` are not staged. This is the same
recurring gap noted in prior reviews (M4, M5 Stage 5, M6, M8) — stage these before DoD.
