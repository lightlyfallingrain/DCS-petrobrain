# aircraft-layer/CLAUDE.md

Subproject instructions for the Aircraft Layer. Augments root `CLAUDE.md` — read that first for overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only within `aircraft-layer/`.

See `WORKFLOW.md` in this directory for deploy/run steps (Export.lua deployment, collector invocation, firewall, LAN query). See `plans/aircraft-layer/plan.md` and `plans/aircraft-layer/implementation.md` for design rationale and stage-by-stage history.

## What this is

Live, LAN-reachable, read-only telemetry pipeline: DCS process → `Export.lua` (in-process, Windows) → local collector process (Windows) → LAN-facing JSON API (Windows→Mac/anywhere on LAN). Kinematic state only (position, attitude, heading, speed, altitude) — switches, contacts, and commanding are out of scope, deferred to follow-on milestones (`plans/aircraft-layer/plan.md` "Follow-on Milestones").

This is a **live-process/networked service, not an offline batch pipeline** — different testing shape from `world-model/`: no fixture-replayable DCS state, correctness of the live path is validated by hand against a running mission and the cockpit, not by unit tests alone.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`). No dependencies — stdlib only (`http.server`, `socket`, `json`, `argparse`), consistent with `world-model/`'s dependency policy.
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- **Wire protocol: newline-delimited JSON, no library on the Lua side.** `Export.lua` hand-rolls its own minimal JSON encoder (LuaSocket has no JSON codec) and pushes one line per sample over a loopback TCP socket to the collector. Collector→LAN hop is a stdlib `http.server` JSON polling API. No WebSocket/push transport — polling is sufficient for crew-cognition-rate consumption, not a flight-control loop (plan decision 4).
- **Export throttle lives in `Export.lua`, not the collector.** `LuaExportAfterNextFrame` fires every DCS frame regardless of the `LuaExportActivityNextEvent` return value (contrary to the DCS-documented mechanism — see `plans/aircraft-layer/implementation.md` stage 5 part 1); the actual 5 Hz gate is a `last_export_t` check at the top of `LuaExportAfterNextFrame` itself. Do not rely on `LuaExportActivityNextEvent`'s return value to throttle anything.
- **Every sample carries both `dcs_model_time_s` (DCS's own sim clock, stops/resets across pause/restart) and `received_wall_clock_s`** (collector's wall-clock at parse time) — required by the project's provenance/timestamp invariant. DCS's model clock keeps advancing while the mission is paused; Export.lua keeps exporting throughout pause too (confirmed live, see implementation.md).
- **No delta/since-query endpoint** — `GET /telemetry/since/<t>` was implemented then dropped post-stage-5: its receipt-time cursor returned every motionless sample as "new" during a live pause test, and the body/brain consumer can just poll `/latest` on its own schedule. Only `GET /telemetry/latest` exists. Don't reintroduce a ring buffer/delta endpoint without a concrete consumer need for gap-free history (episodic memory might eventually be that need — not yet).

## Commands

```sh
ruff format aircraft-layer/src aircraft-layer/tests   # format
ruff check aircraft-layer/src aircraft-layer/tests    # lint
mypy aircraft-layer/src                                 # type check (strict)
pytest aircraft-layer/tests -q                           # test
```

Run a single test: `pytest aircraft-layer/tests/test_file.py::test_name -q`.

## Testing

- `tests/test_schema.py`, `tests/test_cache.py` — fixture-based unit tests, no live DCS needed (schema parsing/validation, cache bookkeeping).
- `tests/test_api.py` — spins up a real `TelemetryAPIServer` on an OS-assigned port in a background thread, queries it with stdlib `urllib.request`.
- `Export.lua` and the live Export.lua↔collector↔API path have **no automated test** — correctness there depends on a real DCS process and socket peer, validated manually against a running mission (procedure in `WORKFLOW.md`) and cross-checked against cockpit instrument readings. Mirrors `world-model/`'s M4/M5 pattern of real-fixture-only validation for anything requiring a live DCS instance.
- **Always include a paused-state check alongside any moving-aircraft check** when testing a new DCS-interfacing feature live — the export-rate bug (stage 5 part 1) and the dropped delta-query endpoint (post-stage-5) were both real bugs invisible to in-flight-only testing and caught only by pausing the mission mid-test.

## Structure

- `dcs-export/Export.lua` — canonical, version-controlled Windows Export.lua script. Deployed by copying to `Saved Games\DCS\Scripts\Export.lua` on the Windows box; never edit the deployed copy in place. A synced copy lives at `win-mac-sync/to-windows/aircraft-layer/Export.lua` for machines using that sync folder instead of a direct repo checkout.
- `src/schema/` — the telemetry wire format and typed record (`TelemetrySample`), including parsing/validation. Single source of truth for field names/units.
- `src/collector/` — loopback TCP listener receiving the Export.lua feed (`server.py`), most-recent-sample cache (`cache.py`), process entrypoint wiring both servers together (`__main__.py`).
- `src/api/` — the LAN-facing telemetry API (`GET /telemetry/latest` only).
- `tests/` — automated tests per "Testing" above.
- `WORKFLOW.md` — deploy/run/firewall/query steps for the live cross-machine path.
