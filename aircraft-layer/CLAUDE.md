# aircraft-layer/CLAUDE.md

Subproject instructions for the Aircraft Layer. Augments root `CLAUDE.md` — read that first for overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only within `aircraft-layer/`.

See `WORKFLOW.md` in this directory for deploy/run steps (Export.lua deployment, collector invocation, firewall, LAN query). See `plans/aircraft-layer/plan.md` and `plans/aircraft-layer/implementation.md` for design rationale and stage-by-stage history.

## What this is

Live, LAN-reachable telemetry pipeline (read path: DCS → `Export.lua` → collector → LAN API) plus one narrow write-back channel for in-cockpit text display (`POST /text/push` → collector → loopback UDP → a DCS Hook-state overlay). Kinematic state, world objects, and Petrovich's indication text remain read-only; text display is the only inbound direction, and it carries opaque display strings only — no aircraft state, no commands, no code. Switches, contacts, and aircraft commanding remain out of scope, deferred to follow-on milestones (`plans/aircraft-layer/plan.md` "Follow-on Milestones").

This is a **live-process/networked service, not an offline batch pipeline** — different testing shape from `world-model/`: no fixture-replayable DCS state, correctness of the live path is validated by hand against a running mission and the cockpit, not by unit tests alone.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`). No dependencies — stdlib only (`http.server`, `socket`, `json`, `argparse`), consistent with `world-model/`'s dependency policy.
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- **Wire protocol: newline-delimited JSON, no library on the Lua side.** `Export.lua` hand-rolls its own minimal JSON encoder (LuaSocket has no JSON codec) and pushes one line per sample over a loopback TCP socket to the collector. Collector→LAN hop is a stdlib `http.server` JSON polling API. No WebSocket/push transport — polling is sufficient for crew-cognition-rate consumption, not a flight-control loop (plan decision 4).
- **Export throttle lives in `Export.lua`, not the collector.** `LuaExportAfterNextFrame` fires every DCS frame regardless of the `LuaExportActivityNextEvent` return value (contrary to the DCS-documented mechanism — see `plans/aircraft-layer/implementation.md` stage 5 part 1); the actual 5 Hz gate is a `last_export_t` check at the top of `LuaExportAfterNextFrame` itself. Do not rely on `LuaExportActivityNextEvent`'s return value to throttle anything.
- **Every sample carries both `dcs_model_time_s` (DCS's own sim clock, stops/resets across pause/restart) and `received_wall_clock_s`** (collector's wall-clock at parse time) — required by the project's provenance/timestamp invariant. DCS's model clock keeps advancing while the mission is paused; Export.lua keeps exporting throughout pause too (confirmed live, see implementation.md).
- **No delta/since-query endpoint** — `GET /telemetry/since/<t>` was implemented then dropped post-stage-5: its receipt-time cursor returned every motionless sample as "new" during a live pause test, and the body/brain consumer can just poll `/latest` on its own schedule. Only `GET /telemetry/latest` exists. Don't reintroduce a ring buffer/delta endpoint without a concrete consumer need for gap-free history (episodic memory might eventually be that need — not yet).
- **`GET /world_objects/latest`** (`plans/pb1-perception-logger/plan.md` stage 3) is `LoGetWorldObjects`'s raw, global, unfiltered ground truth — no coalition filter, no detection/interpretation logic. It exists so body-layer's `HybridPerceptionSource` has candidate positions to associate a real detection against (`perception.association`); this layer does not do that filtering or association itself. Position is lat/lon/altitude (not DCS x/y/z, unlike `/telemetry/latest`) since that's what `LoGetWorldObjects` itself returns — DCS x/z conversion happens on the consumer side (world-model's `coordinates` module), not here. **Own-aircraft identity is flagged, not filtered here**: each object carries `is_ownship` (`bool | None` — `None` only when `LoGetPlayerPlaneId()` itself failed that poll, never coerced to `False`), set in `Export.lua` by comparing the object's `LoGetWorldObjects` key against `LoGetPlayerPlaneId()`. The player's own aircraft is still present in the snapshot; body-layer filters on the flag (`todo/todo.md` backlog item, replacing an earlier 50 m proximity heuristic that had a false-negative window during troop insertion/close formation).
- **`GET /petrovich_indication/latest`** (`plans/pb1-perception-logger/plan.md` stage 4) is `list_indication(HELPERAI_DEVICE_ID)`'s parsed classification text — the real, live-confirmed Petrovich detection-existence signal body-layer's `HybridPerceptionSource` gates on. `Export.lua` pushes the raw recursive `-----...-----\n<name>\n<value-if-any>\nchildren are {...}` dump verbatim (zero Lua-side tree parsing); `aircraft-layer/src/schema/petrovich_indication.py` flattens it into a `{leaf_name: text}` record (at minimum `middle_list_text`/`lower_list_text`/`lower_lower_list_text`) server-side. No numeric field exists anywhere in this feed — confirmed live across ~4000 samples; bearing/range are never derivable from Petrovich's own systems, only from `/world_objects/latest` via association.

## Commands

```sh
ruff format aircraft-layer/src aircraft-layer/tests   # format
ruff check aircraft-layer/src aircraft-layer/tests    # lint
mypy aircraft-layer/src                                 # type check (strict)
pytest aircraft-layer/tests -q                           # test
for f in aircraft-layer/dcs-export/*.lua; do luac5.1 -p "$f" || echo "FAIL $f"; done   # Lua syntax
```

Run a single test: `pytest aircraft-layer/tests/test_file.py::test_name -q`.

**Lua syntax check (`luac5.1 -p`)** parses without executing — it catches syntax errors in `Export.lua`, the Hook scripts, and probes before a DCS launch, and nothing more (`DCS`/`net`/`log`/`Lo*` exist only inside DCS, so behaviour still needs a live run). Must be **Lua 5.1** specifically, the version DCS embeds; a newer `luac` accepts syntax DCS rejects. Install: `sudo apt install lua5.1` (WSL/Debian).

## Testing

- `tests/test_schema.py`, `tests/test_cache.py` — fixture-based unit tests, no live DCS needed (schema parsing/validation, cache bookkeeping).
- `tests/test_api.py` — spins up a real `TelemetryAPIServer` on an OS-assigned port in a background thread, queries it with stdlib `urllib.request`.
- `tests/test_text_sender.py` — `TextOverlaySender` against a real throwaway UDP socket (well-formed datagram, truncation to `MAX_LINE_LENGTH`, a send to a closed port not raising).
- `tests/test_text_push_api.py` — `POST /text/push` against a real `TelemetryAPIServer` with a recording `TextOverlaySender` double (valid push, missing/invalid/empty `text`, non-JSON body, unconfigured `text_sender` → 503).
- `Export.lua`, the overlay Hook script/`.dlg` pair, and the live Export.lua↔collector↔API path have **no automated test** — correctness there depends on a real DCS process and socket peer, validated manually against a running mission (procedure in `WORKFLOW.md`) and cross-checked against cockpit instrument readings/the overlay window itself. Mirrors `world-model/`'s M4/M5 pattern of real-fixture-only validation for anything requiring a live DCS instance.
- **Always include a paused-state check alongside any moving-aircraft check** when testing a new DCS-interfacing feature live — the export-rate bug (stage 5 part 1) and the dropped delta-query endpoint (post-stage-5) were both real bugs invisible to in-flight-only testing and caught only by pausing the mission mid-test.

## Structure

- `dcs-export/Export.lua` — canonical, version-controlled Windows Export.lua script. Deployed by copying to `Saved Games\DCS\Scripts\Export.lua` on the Windows box; never edit the deployed copy in place. A synced copy lives at `win-mac-sync/to-windows/aircraft-layer/Export.lua` for machines using that sync folder instead of a direct repo checkout.
- `src/schema/` — the telemetry wire format and typed record (`TelemetrySample`), including parsing/validation. Single source of truth for field names/units. `world_objects.py` is the `LoGetWorldObjects` sibling schema (`WorldObjectSample`/`WorldObjectsSnapshot`); `petrovich_indication.py` is the `list_indication(HELPERAI_DEVICE_ID)` sibling (`PetrovichIndicationSample`, plus its own from-scratch recursive-descent tree parser, `parse_indication_text`). Both re-exported from `schema/__init__.py`.
- `src/collector/` — loopback TCP listener receiving the Export.lua feed (`server.py`), most-recent-sample caches (`cache.py`: `TelemetryCache`/`WorldObjectsCache`/`PetrovichIndicationCache`), process entrypoint wiring both servers together (`__main__.py`).
- `src/api/` — the LAN-facing API: `GET /telemetry/latest`, `GET /world_objects/latest`, `GET /petrovich_indication/latest`, `POST /text/push` (BL-2.5, `plans/dcs-text-panel-output/plan.md` — the one inbound/write path, forwards to `collector.text_sender.TextOverlaySender`).
- `src/collector/text_sender.py` — `TextOverlaySender`: fire-and-forget loopback UDP sender to the overlay Hook script (BL-2.5). `send_line` never raises — a missing listener (DCS not running, or running without the overlay script loaded) is an expected state, not an error, same posture as the `/latest` endpoints' empty-cache case.
- `dcs-export/petrobrain-overlay-hook.lua` + `dcs-export/petrobrain-overlay.dlg` — canonical Hook-state overlay script + widget/skin definition (BL-2.5), deployed to `Saved Games\DCS\Scripts\Hooks\`. Modeled on DCS-SRS's own installed overlay; unverified against a live DCS session as of authorship (`plans/dcs-text-panel-output/plan.md` Stage 2 is user-only). **Single-message mode (2026-09-10 user decision):** a pushed line calls `message_text:clear()` before `addText()`, so a new message replaces whatever is shown immediately rather than accumulating a scrollback — the panel is mostly a debug tool for now, not a design the scrollback/duration machinery (`DEFAULT_DURATION_S`) was reworked around.
- `tests/` — automated tests per "Testing" above.
- `WORKFLOW.md` — deploy/run/firewall/query steps for the live cross-machine path, including the overlay Hook script deploy (BL-2.5).
