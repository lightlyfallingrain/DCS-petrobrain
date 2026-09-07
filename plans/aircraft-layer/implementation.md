### Implementation Summary

Implemented stages 1-2 of `plans/aircraft-layer/plan.md` on branch
`feature/aircraft-layer-telemetry`: scaffolded `aircraft-layer/` as an
independent sibling subproject to `world-model/`, and built the one-way
kinematic push end-to-end except the live DCS test (stage 3) and the
Mac-facing HTTP API (stage 4), both explicitly deferred.

### Files Changed
- `aircraft-layer/pyproject.toml` (new) — mirrors `world-model/pyproject.toml`: mypy strict config, pytest `testpaths=["tests"]`/`pythonpath=["src"]`, and an explicit `known-first-party` ruff-isort list (`schema`, `collector`) for the same cwd-dependent-classification reason documented in `world-model/pyproject.toml`'s comment. No dependencies — stdlib only, per plan decision 4.
- `aircraft-layer/.gitignore` (new) — venv/cache/pycache patterns; no `data/` entry needed at this stage (plan's Invariant Check: no persistent store yet, just an in-memory cache).
- `aircraft-layer/dcs-export/Export.lua` (new) — canonical Export.lua. Throttles to 5 Hz via `LuaExportActivityNextEvent`, reads `LoGetSelfData`/`LoGetADIPitchBankYaw`/altitude/airspeed functions, hand-rolls a flat JSON-line encoder, pushes over a loopback TCP client connection opened in `LuaExportStart` (with a 5s reconnect cooldown if the collector isn't up yet). Never listens — plan decision 2.
- `aircraft-layer/src/schema/__init__.py` (new) — `TelemetrySample` frozen dataclass + `TelemetryParseError`. `from_json_line`/`from_dict` validate every required field is present and numeric (explicitly rejecting `bool`, since `bool` is an `int` subclass in Python and would otherwise silently pass `isinstance(x, int | float)`), and treat the one optional field (`alt_radar`) as `None` whether it's JSON `null` or simply absent from the line.
- `aircraft-layer/src/collector/cache.py` (new) — `TelemetryCache`: `push`/`latest`/`since(cursor_wall_clock_s)` over a `deque(maxlen=...)` ring buffer. `since` is a plain `>` filter over `received_wall_clock_s`; documented limitation: a cursor older than the buffer's oldest retained sample silently misses evicted samples rather than erroring.
- `aircraft-layer/src/collector/server.py` (new) — `CollectorServer`: binds loopback-only (`127.0.0.1:7790` default), accepts one connection at a time in a loop (Export.lua reconnects once per mission via its own `LuaExportStart`/`Stop`), buffers partial reads across `\n` boundaries, and drops+logs any line that fails to parse rather than crashing the accept loop.
- `aircraft-layer/src/collector/__main__.py` (new) — `python -m collector` debug-dump entry point: opens the server on a background thread, prints `cache.latest()` on an interval. This is the "local script reading the collector's in-memory state" stage 2 calls for, ready for the user to run during the stage 3 live-mission test.
- `aircraft-layer/tests/test_schema.py`, `aircraft-layer/tests/test_cache.py` (new) — see below.

### Tests Added
- `test_schema.py` — full-field parse of a valid line; null vs. absent `alt_radar` both resolve to `None`; whitespace/newline stripping; rejection of empty lines, invalid JSON, non-object JSON, a missing required field, a non-numeric required field, a `bool` value for a numeric field, and a non-numeric optional field; `from_dict` accepts plain `int` values and coerces to `float`.
- `test_cache.py` — `latest()` on empty/non-empty cache; `since()` returns only samples strictly after the cursor, in chronological order, and returns `[]` (not an error) when nothing changed; ring-buffer eviction drops the oldest entries beyond `buffer_size`; `buffer_size < 1` raises `ValueError`.

### Checks
- ruff format --check aircraft-layer/src aircraft-layer/tests: pass
- ruff check aircraft-layer/src aircraft-layer/tests: pass
- mypy --strict aircraft-layer/src aircraft-layer/tests (run from repo root and from `aircraft-layer/`, both pick up `aircraft-layer/pyproject.toml`'s strict config correctly — unlike `world-model/`'s cwd-sensitivity, no `known-first-party`-style mypy issue showed up here): pass
- pytest aircraft-layer/tests -q: pass (20 passed)

No global `ruff`/`mypy`/`pytest` install exists on this machine; ran all three via `world-model/.venv/bin/{ruff,mypy,pytest}` — that venv's tools are standalone and don't pull in `world-model`'s own dependencies (pyproj/pillow), so this is safe reuse, not a hidden coupling between the two subprojects.

### Notable Discoveries
- Unlike `world-model/`'s documented mypy cwd-sensitivity (`project_worldmodel_mypy_path_cwd` memory), `aircraft-layer/`'s mypy run was cwd-independent in this session — both `mypy aircraft-layer/src` from repo root and `mypy src tests` from inside `aircraft-layer/` succeeded cleanly. Worth re-checking once this subproject has more inter-package imports; the difference may just be that `schema`/`collector` don't yet exercise the same cross-package resolution paths that tripped `world-model`.
- `Export.lua`'s exact `LoGetSelfData()` sub-field structure (`Position.p.x/.y/.z` vs. a flat `Position.x/.y/.z`; whether `Heading` is top-level) is documented on the Hoggit wiki per the investigator's research doc but was not independently verified against the installed DCS version this session (no Windows-box access from this agent). The script is written defensively — `pcall`-guarded field access, tries the nested `Position.p.*` shape first and falls back to a flat `Position.*` — and simply skips sending a sample if the shape doesn't match rather than erroring. This is exactly what plan stage 3 (live DCS mission test) exists to confirm or correct; flagging so the reviewer/DoD doesn't mistake the pcall guards for defensive-programming overkill — they're covering a genuinely unverified assumption.
- The plan's stage 2 bullet "verify end-to-end via a local script on the Windows box reading the collector's in-memory state (or a debug stdout dump)" was interpreted as calling for the debug-dump tooling to be built now (it's infrastructure, not the live-mission test itself) even though actually running it against DCS is stage 3's job. `aircraft-layer/src/collector/__main__.py` is that tooling, unexercised against a real Export.lua in this session.
- No `aircraft-layer/CLAUDE.md` or `WORKFLOW.md` written yet (stage 6, explicitly out of scope for this pass) — anyone reading `aircraft-layer/` cold before that stage lands should look to `plans/aircraft-layer/plan.md` and this file for the stack/design rationale in the meantime.

---

### Implementation Summary (review fix follow-up)

Addressed the one required fix from `plans/aircraft-layer/review.md` for the stage 1-2 review: `CollectorServer.serve_forever` did not catch `OSError` around per-connection handling, so an abrupt Export.lua disconnect (e.g. `ConnectionResetError` on Windows when DCS force-quits/crashes) propagated out of `_handle_connection` and crashed the whole long-running collector process instead of looping back to `accept()` — contradicting the module's own docstring claim that the loop re-accepts after each disconnect.

### Files Changed
- `aircraft-layer/src/collector/server.py` — wrapped the `self._handle_connection(conn)` call in `serve_forever` with `except OSError:` that logs a warning (`exc_info=True`) and falls through to the existing `finally: conn.close()`, then loops back to `accept()`. No other logic changed.

### Tests Added
- None. The reviewer's own note characterized this as a live-connection failure-mode fix best exercised by the stage 3 live DCS mission test (per the module's existing test philosophy: `_handle_connection`/`serve_forever` correctness depends on a real socket peer, not unit tests — only `TelemetryCache` and `TelemetrySample` are unit-tested). Left the optional unbounded-`buffered`-string guard out of scope for this pass per the reviewer's own framing (low risk on trusted loopback; worth revisiting before stage 4 exposes this code on the LAN).

### Checks
- ruff format --check aircraft-layer/src aircraft-layer/tests: pass
- ruff check aircraft-layer/src aircraft-layer/tests: pass
- mypy --strict aircraft-layer/src aircraft-layer/tests (run from inside `aircraft-layer/`): pass
- pytest aircraft-layer/tests -q: pass (20 passed, unchanged from stage 1-2 — no new tests added)

### Notable Discoveries
- None beyond what stage 1-2's entry already flagged. Committed as its own small commit (`Catch OSError per-connection in collector serve_forever`) separate from the reviewer's own review artifacts, which were committed separately to keep review-record commits distinct from code-fix commits.

---

### Implementation Summary (stage 3 live-test bug fix)

Stage 3 live DCS mission test blocked immediately: collector confirmed listening, Export.lua never connected. User's `Saved Games\DCS\Logs\dcs.log` pinned it exactly:

```
ALERT   EDCORE (Main): Can't execute Lua file C:\Users\simon\Saved Games\DCS\Scripts\Export.lua - error loading module 'socket' from file 'F:\Games\DCS World\bin-mt\lua-socket.dll':
	The specified procedure could not be found.
```

Root cause: `require("socket")` at the top of `Export.lua` was unguarded, and it fails in this DCS install's Export environment because `lua-socket.dll` only exports `luaopen_socket_core`, not the plain `luaopen_socket` entry point Lua's `require` looks up for module name `"socket"`. Since the failure happens at module load time (top level, not inside any `LuaExportStart`/`LuaExportActivityNextEvent` callback), the entire script aborted before any callback function was even defined — so DCS never called anything in it, and nothing ever attempted to connect. This matches the investigator's research doc claim that LuaSocket "ships with" the Export environment (true — the DLL is present and loadable) but that claim didn't extend to *which* require name works, which stage 3 was specifically meant to verify and did.

### Files Changed
- `aircraft-layer/dcs-export/Export.lua` — changed `local socket = require("socket")` to `local socket = require("socket.core")`, with a comment recording why. No other change needed: every method this script calls (`socket.tcp()`, `:settimeout`, `:connect`, `:send`, `:close`) is a `socket.core` primitive: `socket.core` is the primitive tcp/udp core, `socket.lua` (the layer `require("socket")` normally loads) only adds convenience wrappers (`socket.connect`, `socket.bind`, `socket.select` helpers) this script never used.
- Canonical fix copied to `win-mac-sync/to-windows/aircraft-layer/Export.lua` for redeploy (per this project's copy-out-never-edit-in-place cross-machine convention).

### Tests Added
- None — this is Export.lua, which per the module's own stated test philosophy is validated by the live DCS mission test, not unit tests.

### Checks
- Not re-run (no `.py` changes this pass).

### Notable Discoveries
- An unguarded top-level `require()` failure in Export.lua is silent from the collector's point of view: no connection attempt, no error visible anywhere except `dcs.log`. Worth remembering for any future Export.lua dependency: DCS logs load failures only to `dcs.log`, never to the collector or any process this pipeline controls. Next step once connectivity is confirmed: continue stage 3 (cross-check telemetry values against cockpit instruments, confirm/correct the `LoGetSelfData()` field-shape assumption noted in stage 1-2's entry).
