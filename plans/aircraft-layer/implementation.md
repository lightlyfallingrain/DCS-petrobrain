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

---

### Implementation Summary (standing debug-logging facility)

After the socket-require fix, stage 3 progressed: Export.lua connected but the collector still received zero samples (silent per-frame skip — no way to see why). User generalized the lesson from two consecutive silent-failure incidents (unguarded `require` aborting the whole script; now a `LoGetSelfData()` shape mismatch dropping every sample) into a standing rule: DCS-interfacing code must ship with flag-gated debug logging from the start, not bolted on reactively. Recorded as `[[feedback_dcs_debug_logging_preemptive]]`.

Replaced the earlier one-shot temporary dump hack with a permanent facility in `Export.lua`:
- `DEBUG` flag checked once at load time via presence of `Saved Games\DCS\Scripts\aircraft_layer_debug.flag` (any content, even empty).
- `debug_log(msg)` — appends timestamped lines to `Saved Games\DCS\Logs\aircraft_layer_debug.log`, no-op when `DEBUG` is false (checked first, so the branch is cheap when off).
- `debug_dump(label, value)` — recursive table-shape dumper (keys, types, values, depth-limited to 3), used once per mission to dump `LoGetSelfData()`'s actual raw shape.
- Logging added at every currently-silent failure point: `try_connect` success/failure (with the underlying socket error), incomplete-sample skip (with every field's resolved value so a shape mismatch is immediately visible), and `client:send` failure (with the underlying error).

### Files Changed
- `aircraft-layer/dcs-export/Export.lua` — added the `DEBUG`/`debug_log`/`debug_dump` facility; instrumented `try_connect`, the incomplete-sample skip branch, and the send-failure branch; replaced the earlier temporary one-shot dump with a call to `debug_dump`. Updated the module docstring to document the flag file and log path as a standing feature, not a one-off.
- Canonical fix copied to `win-mac-sync/to-windows/aircraft-layer/Export.lua`.

### Tests Added
- None — Export.lua only, validated live per the module's existing test philosophy.

### Checks
- Not re-run (no `.py` changes this pass).

### Notable Discoveries
- This facility is intended to stay in `Export.lua` permanently (unlike the one-shot dump it replaces) — future DCS-interfacing changes to this file should extend it (add `debug_log` calls at new failure points) rather than hand-rolling another temporary dump.

---

### Implementation Summary (stage 3 sample-skip bug fix — safe_call dropped yaw)

Debug log from the flag-gated facility (`67da687`) showed connection succeeding and `LoGetSelfData()`'s shape matching the existing nested-`Position.p.*` guess — not a shape-mismatch bug as suspected. Actual cause: `safe_call(fn)` used `local ok, a, b = pcall(fn)`, forwarding only 2 of `pcall`'s return values. `LoGetADIPitchBankYaw()` returns 3 (pitch, bank, yaw); the 3rd (yaw) was silently truncated every call, so `yaw` was always `nil` and every sample failed the completeness check and got skipped forever.

### Files Changed
- `aircraft-layer/dcs-export/Export.lua` — `safe_call` now captures/forwards 3 pcall return values (`local ok, a, b, c = pcall(fn)` / `return a, b, c`).
- `aircraft-layer/src/collector/__main__.py`, `aircraft-layer/src/collector/server.py` — added `--debug` CLI flag (DEBUG-level logging) and debug-level logging of every received/parsed line, used to isolate this from a connection-level issue.
- Canonical fix copied to `win-mac-sync/to-windows/aircraft-layer/Export.lua`.

### Tests Added
- None — Export.lua only; collector debug logging is diagnostic tooling, not exercised by unit tests.

### Checks
- Not re-run (no `.py` logic changed, only logging).

### Result
Live DCS test now streams samples end-to-end (`eeb7afd`). User re-ran on the Windows box: `win-mac-sync/from-windows/collector.log` shows continuous `TelemetrySample` output — position/altitude/speed/pitch/bank/yaw all changing plausibly across ~15s of flight (altitude descending 73→58m, IAS ~51-55 m/s, pitch/bank/yaw tracking a turn). `aircraft_layer_debug.log` (323KB) confirms no more skip events. One known gap: `altitude_radar_m` is `None` in every sample — the radar-altimeter field is never populated; not yet investigated, flag for stage 3 completion or later.

### Notable Discoveries
- The debug facility's value was immediate and exactly as intended: pinned the true cause (return-arity truncation, not a field-shape mismatch) on the first log, instead of another guess-fix-redeploy cycle.

---

### STATUS AS OF 2026-09-07 — stage 3 sample flow confirmed, cross-check + stage 4 remain

Branch: `feature/aircraft-layer-telemetry`, HEAD = `eeb7afd` ("Fix Export.lua safe_call dropping yaw, add collector --debug flag"). Working tree clean.

**Where things stand:** stage 3 (live DCS mission test) — connectivity and end-to-end sample flow are both confirmed working. Two bugs found and fixed along the way:
1. `require("socket")` aborted Export.lua's entire load (fixed in `b51fc94`).
2. `safe_call`'s pcall-forwarding truncated yaw to `nil`, causing every sample to fail the completeness check (fixed in `eeb7afd`, confirmed via live collector output).

**Not yet done:**
1. Stage 3's remaining piece — cross-check streamed telemetry values against cockpit instruments in a live mission (only log-level plausibility checked so far, not instrument-verified).
2. Investigate why `altitude_radar_m` is always `None`.
3. Stage 4 — Mac-facing HTTP API — per `plans/aircraft-layer/plan.md`.

No other work is in flight on this branch.

---

### Implementation Summary (stage 4 — Mac-facing HTTP API)

Implemented plan stage 4: `GET /telemetry/latest` and `GET /telemetry/since/<timestamp>`, stdlib `http.server`-only, LAN-facing (`0.0.0.0`, unlike the collector's loopback-only Export.lua listener). Not yet exercised against a live DCS mission or across an actual LAN hop — that's stage 3's remaining piece plus a first real Mac->Windows `curl` check, both still open.

### Files Changed
- `aircraft-layer/src/api/__init__.py` (new), `aircraft-layer/src/api/server.py` (new) — `TelemetryAPIServer` (mirrors `CollectorServer`'s open/close/context-manager shape) wrapping `http.server.ThreadingHTTPServer`; route handlers `_handle_latest`/`_handle_since` are plain functions returning JSON-able values, separated from the `BaseHTTPRequestHandler` glue so they're testable without spinning up a real socket if ever needed (tests currently exercise the real server anyway, see below). Default `0.0.0.0:7791`.
- `aircraft-layer/src/schema/__init__.py` — added `TelemetrySample.to_dict()`, the API's serialization boundary; kept next to `from_dict`/`from_json_line` since the module's docstring already claims to be "the single place the wire format is defined."
- `aircraft-layer/src/collector/__main__.py` — now starts both `CollectorServer` and `TelemetryAPIServer` in one process on separate threads, sharing one `TelemetryCache`. Added `--api-host`/`--api-port`; kept `--host`/`--port` (now documented as specifically the Export.lua listener) and renamed the old `--interval` to `--dump-interval` for clarity now that there are two servers to disambiguate from.
- `aircraft-layer/pyproject.toml` — added `api` to the ruff-isort `known-first-party` list (same cwd-classification reason as `schema`/`collector`).
- `aircraft-layer/WORKFLOW.md` (new) — deploy steps, collector invocation, Windows Firewall `netsh` rule for the API port (7791; the Export.lua port needs none, loopback-only), and example `curl` queries. Written now (a stage-4 plan requirement) rather than deferred to stage 6's `CLAUDE.md` pass.
- `aircraft-layer/tests/test_api.py` (new) — spins up a real `TelemetryAPIServer` on an OS-assigned port (`port=0`) in a background thread per test, queries it with `urllib.request` (stdlib only, consistent with the rest of this subproject's no-dependency policy).

### Tests Added
- `test_api.py`: `/telemetry/latest` returns JSON `null` on an empty cache and the most recent sample after pushes; `/telemetry/since/<t>` returns only later samples in chronological order, an empty list when nothing changed, and 400 on a non-numeric timestamp; unknown paths return 404.

### Checks
- ruff format --check aircraft-layer/src aircraft-layer/tests: pass
- ruff check aircraft-layer/src aircraft-layer/tests: pass
- mypy --strict aircraft-layer/src aircraft-layer/tests (from `aircraft-layer/`): pass
- pytest aircraft-layer/tests -q: pass (26 passed, up from 20)

### Notable Discoveries
- `ThreadingHTTPServer.shutdown()` is the intended cross-thread stop mechanism (unlike `CollectorServer.close()`, which just closes the listening socket out from under a blocking `accept()`) — `TelemetryAPIServer.close()` uses it directly rather than replicating the collector's socket-close pattern, since `http.server` already provides the safer primitive.
- Stage 4 plan text says "confirm reachability from the Mac over LAN with a plain `curl`" and "measure DCS frame-time impact" (stage 5) — neither done this pass; this was a same-machine (offline, no DCS) implementation pass only. Both remain open alongside stage 3's cockpit cross-check.

---

### Live LAN reachability confirmed (stage 4 plan requirement closed)

Synced current `aircraft-layer/src/` (incl. new `api/`) + `pyproject.toml` to `win-mac-sync/to-windows/aircraft-layer/` (previous copy there was stale, predated stage 4). User opened the `netsh advfirewall` rule for port 7791, ran `python -m collector --debug` on the Windows box (`192.168.0.85`) against a live Mi-24P mission, then curled from the Mac side of the LAN:

- `GET http://192.168.0.85:7791/telemetry/latest` -> 200, single current sample.
- `GET http://192.168.0.85:7791/telemetry/since/0` -> 200, ~100-sample array (full ring buffer, `DEFAULT_BUFFER_SIZE`), chronological, `dcs_model_time_s` spanning ~0.84s of flight at the expected ~5ms-per-sample (200 Hz-ish receipt cadence at whatever the current export rate actually is — worth reconciling against the plan's nominal "5 Hz" once stage 5 measures the real rate, since consecutive `dcs_model_time_s` deltas in the sample look closer to ~8-10ms than 200ms).

This closes stage 4's "confirm reachability from the Mac over LAN with a plain curl" requirement. `altitude_radar_m` still `None` in every sample (known gap, stage 3 leftover, not investigated this pass).

**Remaining open items, unchanged in kind:** stage 3's cockpit-instrument cross-check, `altitude_radar_m` investigation, stage 5 frame-time measurement (now also: reconcile actual observed export rate against the plan's nominal 5 Hz).

---

### Stage 3 cockpit cross-check complete

User read two live samples against cockpit instruments.

First pass (mission running, not paused) showed a bank mismatch (pipeline -3.8°, cockpit ~+15° right) that looked like a real bug — sign flipped and 4x off. Flagged it but declined to guess a fix given the two readings weren't from the same instant.

Second pass: user paused the mission (so telemetry and cockpit reading are effectively simultaneous) and re-queried `/telemetry/latest`:

| Field | Pipeline | Cockpit | Verdict |
|---|---|---|---|
| bank | `bank_rad=0.28762784600258` = **+16.5° right** | +15° right | match |
| IAS | `ias_mps=42.729324993147` = **153.8 km/h** | ~150 km/h | match |
| heading | `heading_true_rad=0.24266052246094` = **13.9°** | ~020° | close, acceptable |
| alt MSL | `altitude_msl_m=176.39450073242` = **176.4 m** | ~170 m baro | close |
| alt AGL | `altitude_agl_m=176.39450073242` (== MSL exactly) | radar ~190 m | 14 m off, unresolved |

The first pass's bank mismatch was confirmed to be a **timing artifact** (comparing two different instants during active maneuvering, not a pipeline bug) — resolved by the paused re-test, no code change needed.

Closes stage 3's "cross-check streamed telemetry values against cockpit instruments" requirement. Two known gaps remain, deliberately *not* investigated this pass (root cause unclear, need more data to isolate):
1. `altitude_agl_m` is bit-identical to `altitude_msl_m` in every sample seen so far (this test and the earlier live-flow test), regardless of aircraft position. Plausible innocent explanation (terrain elevation ~0m under this flight path, so AGL≈MSL by definition) vs. `LoGetAltitudeAboveGroundLevel()` not behaving as documented — undetermined without an independent ground-elevation reading at that DCS position (e.g. a World Model Builder terrain query) or a flight over known non-flat terrain.
2. `altitude_radar_m` is still always `None` — same undetermined status, and likely related to #1 (radar altimeter and AGL should agree; both are off from the ~190m cockpit radar reading in the same direction).

### Stage 3 status: DONE (both original plan bullets — connectivity/sample-flow, cockpit cross-check — confirmed). Stage 4: DONE (API implemented + live LAN reachability confirmed). Remaining for the plan: stage 5 (frame-time measurement, reconcile actual export rate vs. nominal 5 Hz), stage 6 (CLAUDE.md, root Module Responsibilities bullet), plus the two altitude gaps above as follow-up investigation (not blocking, not scoped to a specific stage yet).

---

### Altitude gap #1 resolved (shoreline artifact confirmed, not a bug)

User's hypothesis from the prior cross-check — that MSL==AGL was specific to that sortie's near-sea-level shoreline location, not a pipeline bug — confirmed by flying over elevated coastal terrain and re-querying:

```
altitude_msl_m: 440.59271240234
altitude_agl_m: 91.699523925781
```

`alt_agl` now correctly diverges from `alt_msl` (~349m difference, consistent with terrain elevation under this position), matching the cockpit screenshot's terrain (forested hills, altitude gauges reading well above ground level). **Gap #1 closed: `LoGetAltitudeAboveSeaLevel`/`LoGetAltitudeAboveGroundLevel` both behave as documented; the earlier identical values were a real feature of that flight's shoreline location, not a bug.**

`altitude_radar_m` is still `null` in this same sample, now isolated as a standalone issue — no longer explainable by the shoreline coincidence, since this position has genuine AGL (~92m) where a radar altimeter should read valid.

**User decision: not investigating further.** `altitude_agl_m` measures the same physical quantity radar alt would (height above the terrain directly below), and it's confirmed working correctly (previous entry). Consumers should use `altitude_agl_m` as the AGL/radar-alt-equivalent value; `altitude_radar_m`/`LoGetRadarAltimeter()`'s always-null behavior is deprioritized, not scheduled for further debugging. No code change — the field stays in the schema (harmless if it starts working later; downstream code should not depend on it being non-null).

---

### Stage 5, part 1: export-rate bug found and fixed (real, not the shoreline kind)

Before the frame-time A/B test, chased the export-rate discrepancy flagged since the first live LAN test (`8f818ba`'s log entry): consecutive samples' `received_wall_clock_s` deltas looked like ~8ms, not the coded 200ms (`EXPORT_INTERVAL_S`, 5 Hz).

Instrumented both export callbacks in `Export.lua` with bounded (`ACTIVITY_LOG_LIMIT=40`) debug logging: `LuaExportActivityNextEvent` (logs requested `t` -> `next`) and the point in `LuaExportAfterNextFrame` where a sample is actually about to be sent. Two live runs on the Windows box, `aircraft_layer_debug.log` synced back each time:

- **Before the fix:** `ActivityNextEvent` fired exactly on the requested 0.2s schedule (`t=0, 0.2, 0.4, 0.6...`) — the documented mechanism itself works. But `AfterNextFrame` fired on *every DCS frame* regardless (`t=0, 0.023, 0.032, 0.039...`, ~8ms apart) — its return value doesn't gate `AfterNextFrame` at all, despite research finding 1 and this file's own comments describing it that way. Root cause: a wrong assumption about DCS's Export API, not a code typo.
- **Fix:** `Export.lua` — added `local last_export_t = -1`; `LuaExportAfterNextFrame` now returns immediately if `t - last_export_t < EXPORT_INTERVAL_S`, before any of the `LoGetSelfData`/altitude/speed reads or socket work, and sets `last_export_t = t` when it proceeds. This is the actual 5 Hz throttle; `LuaExportActivityNextEvent` is kept only because DCS requires the callback to exist, not because it does any gating.
- **After the fix (re-tested live):** `AfterNextFrame send #N` lines land at `t=0, 0.202, 0.403, 0.609, 0.813, 1.02, 1.228...` — ~200ms apart, matching `EXPORT_INTERVAL_S` exactly. Confirmed fixed.
- Updated both the top-of-file docstring and the `LuaExportActivityNextEvent` comment to record this — a future reader relying on "documented throttle mechanism" would reintroduce the same wrong assumption.
- Practical implication: every frame between stage 2 and this fix was doing the full self-data/altitude/speed/JSON-encode/socket-send workload, not once per 200ms as designed — meaning all earlier live tests (stage 3, stage 4, both cross-checks) ran at unthrottled per-frame rate, not 5 Hz. Doesn't invalidate their findings (correctness of field values/API shape doesn't depend on call rate), but the frame-time measurement stage 5 exists to do would have been measuring the wrong thing had it run before this fix.

### Files Changed
- `aircraft-layer/dcs-export/Export.lua` — `last_export_t` throttle in `LuaExportAfterNextFrame`; bounded diagnostic logging in both export callbacks (kept in, capped at 40 calls, harmless going forward); corrected the two comments that mischaracterized `LuaExportActivityNextEvent` as a throttle.
- Canonical fix copied to `win-mac-sync/to-windows/aircraft-layer/Export.lua`.

### Tests Added
- None — Export.lua only, validated live per the module's existing test philosophy.

### Checks
- ruff format --check / ruff check / mypy --strict / pytest aircraft-layer/{src,tests}: all pass (26 tests, unchanged — no `.py` logic touched).

**Next:** stage 5 part 2 — now that the export rate is actually 5 Hz, measure DCS frame-time impact (Export.lua active vs. inactive) and confirm the delta-since-last-query behavior across consecutive polls including "nothing changed."

---

### Stage 5, part 2: frame-time + delta-query validation complete

**Frame-time impact:** user measured with the Nvidia FPS overlay, Export.lua present vs. removed from `Saved Games\DCS\Scripts\`. FPS jumped 110-140 in both configurations, no visible difference attributable to Export.lua (variance tracked scene complexity). Per the plan's own guidance ("if negligible at 5 Hz, don't raise the rate speculatively"), staying at `EXPORT_INTERVAL_S = 0.2`.

**Delta-since-last-query, live:** two `/telemetry/since/<t>` polls a few seconds apart during sustained flight (`since.log`, `since2.log`), each returning the full 100-sample ring buffer. `received_wall_clock_s` deltas between consecutive returned samples are consistently ~200-207ms across the whole ~20s window in both polls — confirms the stage-5-part-1 fix holds under sustained real flight, not just the short debug burst. Both polls' entries are correctly ordered and their overlapping tail/head region is consistent with a shared ring buffer sampled at two different moments. The specific back-to-back-same-cursor "nothing changed" empty-array case wasn't re-demonstrated live (the two polls used different-enough cursors that both returned data) — not re-tested live since it's already covered by `test_since_nothing_changed_returns_empty_list` in `tests/test_api.py`.

### Stage 5: DONE. Only stage 6 remains on the plan (aircraft-layer/CLAUDE.md, root CLAUDE.md Module Responsibilities bullet).
