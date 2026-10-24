# aircraft-layer/CLAUDE.md

Subproject instructions for the Aircraft Layer. Augments root `CLAUDE.md` — read that first for overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only within `aircraft-layer/`.

See `WORKFLOW.md` in this directory for deploy/run steps (Export.lua deployment, collector invocation, firewall, LAN query). See `plans/aircraft-layer/plan.md` and `plans/aircraft-layer/implementation.md` for design rationale and stage-by-stage history.

## What this is

Live, LAN-reachable telemetry pipeline (read path: DCS → `Export.lua` → collector → LAN API) plus four write-adjacent channels: in-cockpit text display (`POST /text/push` → collector → loopback UDP → a DCS Hook-state overlay, BL-2.5), a Petrovich AI-Wheel search trigger (`POST /command/petrovich_search` → collector → loopback UDP → `Export.lua`'s inbound listener, BL-6), spoken-audio playback (`POST /audio/play` → collector → `winsound`, playing directly on this box — BL-10 first slice, `plans/tts-voice-output/plan.md` — the first write path with no DCS-side listener at all; `POST /audio/stop` is its interrupt-only sibling, `plans/inbound-speech/plan.md` Stage 3 follow-up — no body, forwards straight to `AudioPlaybackSender.interrupt`, clears the queue and stops in-flight playback without enqueueing anything new), and a mission-start signal (a DCS Hook script's `onSimulationStart` → collector loopback UDP → `GET /mission_start/latest`, `plans/bl15-mission-start/plan.md`, BL-15 Stage 1) — one event per mission (re)start, not per poll, carrying a sequence counter and a best-effort theatre string so body-layer can detect a genuine restart (the F10 radio-menu command channel that was once the first channel running the opposite direction was removed by `plans/default-crew-pipeline/plan.md`, BL-B96 — voice commands are the only player-command surface now). Kinematic state, world objects, and Petrovich's indication text remain read-only; every write path carries only a small, fixed vocabulary (an opaque display string, a search mode, or a base64 WAV blob) — no aircraft state, no free-form commands, no code, no general-purpose remote-exec surface. **One deliberate exception, user direction 2026-10-21 (`BL-B66`, `plans/9k113-effectors/plan.md`):** the `cockpit_switch` op writes *any* clickable cockpit control (`performClickableAction(device, cmd, value)`, shape-validated only) — *"Allow any cockpit switch. That gives us much more freedom later and even now with experimenting. This is LAN only and switch behaviour is limited to DCS."* It is a cockpit-control write, not code execution; the command socket stays loopback-only. Switches, contacts, and aircraft commanding remain out of scope, deferred to follow-on milestones (`plans/aircraft-layer/plan.md` "Follow-on Milestones").

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
- **`winsound` is Windows-only stdlib — the first Windows-only import this codebase has needed**
  (`collector/audio_sender.py`, BL-10 first slice, `plans/tts-voice-output/plan.md`). Guarded with
  a static `if sys.platform == "win32":`/`else:` split, not a runtime `try`/`except
  ImportError`: mypy specially recognizes `sys.platform` comparisons and skips type-checking the
  branch that's statically unreachable for the platform it runs on, so `mypy --strict` passes on
  the Mac dev machine with no `# type: ignore` needed — confirmed live; the `try`/`except
  ImportError` alternative does **not** get this treatment, since `winsound`'s typeshed stub
  exists on every platform but reports every member as "no attribute" outside
  `sys.platform == "win32"`, so referencing `winsound.PlaySound` inside a bare `try` still fails
  `--strict` on the Mac. On non-Windows, the fallback `_WinsoundPlayer` raises `RuntimeError` from
  both methods — caught and logged by the caller like any other playback failure, never crashing
  the process.
- **The `cockpit_switch` channel (`plans/9k113-effectors/plan.md`, BL-B66 Stage 1)** is the one write path with no fixed vocabulary — see the "What this is" section above for the invariant it departs from. `POST /command/cockpit_switch` (`{"device", "cmd", "value"}`) forwards to `Export.lua`'s `handle_cockpit_switch_command`, which writes via `GetDevice(device):performClickableAction(cmd, value)` after shape validation only. **Its own readback, `GET /cockpit_switch/latest` (`schema.cockpit_switch.CockpitSwitchState`), is removed** (`plans/effector-sequences/plan.md` Stage 4, "readback by need" option B, decided "remove") — replaced by two generic cockpit-arg read paths, neither of which is specific to the six switches that feed used to carry:
  - **Continuous**: `GET /watched_args/latest` (`schema.watched_args.WatchedArgsState`, wire key `"watch_id"`) serves a small, body-layer-declared set of args `Export.lua` polls at its own export tick and sends only on change; `POST /command/watch_args` (`{"watch_id", "args"}`) installs that set, replacing it whole.
  - **One-shot**: `POST /query/read_args` (`{"args"}`) is this layer's first **synchronous** write path — it blocks the HTTP worker thread while the collector's `ArgReadBroker` round-trips a `read_args` command through `Export.lua`'s `handle_read_args_command`, answered on the same frame it arrives (wire key `"read_id"`), and returns `{"t", "values"}` or `504` on timeout/`503` when unconfigured or at capacity (`collector.arg_read_broker.MAX_OUTSTANDING_READS`).

  `Export.lua`'s own `parse_arg_list` bounds both ops identically (≤ 64 args, each 0..4095, whole-op reject on any bad token) — the same bound `schema.watched_args.MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER` state on the Python side, held equal by `tests/test_export_lua_constants_parity.py`. An old deployed `Export.lua`'s cockpit-switch line (wire key `"missl_pw"`) is dropped at DEBUG by the collector rather than parsed — that feed no longer exists on this side.

## Commands

```sh
ruff format aircraft-layer/src aircraft-layer/tests   # format
ruff check aircraft-layer/src aircraft-layer/tests    # lint
cd aircraft-layer && .venv/bin/mypy src                 # type check (strict) -- CWD-only config discovery, see below
pytest aircraft-layer/tests -q                           # test
for f in aircraft-layer/dcs-export/*.lua; do luac5.1 -p "$f" || echo "FAIL $f"; done   # Lua syntax
```

**`mypy` must run from inside the subproject.** Its config discovery is CWD-only, so
`mypy aircraft-layer/src` from the repo root silently drops `strict` and the CWD-relative `mypy_path`
(root `CLAUDE.md`, "Subprojects"). Measured on world-model, 2026-10-09: the root form reports a
phantom `scipy-stubs` import error on a tree that `cd world-model && .venv/bin/mypy src` calls
clean. All five subprojects carried the broken form until then; `brain-layer/CLAUDE.md` did not,
which is the shape to match.

Run a single test: `pytest aircraft-layer/tests/test_file.py::test_name -q`.

**In `Export.lua`, a function that uses a `local` must be defined *below* that local's
declaration.** Lua has no hoisting: a name referenced before its `local` appears compiles as a
**global** lookup, which is `nil` at call time. `push_ptt_state` was written above `safe_call` and
therefore called `nil` on every frame — the trigger published nothing at all, and from the capture
process's side that is indistinguishable from a talk control nobody pressed (2026-09-23). **The
syntax is valid, so `luac5.1 -p` passes it**; this is precisely the failure that check cannot see.
`luacheck` would catch it as an undefined-global access, and is not currently installed.

**But it IS mechanically detectable without `luacheck`, found and verified independently
2026-10-06**: the bug has an exact bytecode signature, because a name referenced before its `local`
compiles to a `GETGLOBAL`.

```sh
luac5.1 -l -p <file> | grep -oE 'GETGLOBAL.*; [A-Za-z_]+' | awk '{print $NF}' | sort -u
```

That lists every global the chunk reads. **A name in that list that is one of the script's own
helpers is the bug.** A clean result is exclusively Lua stdlib (`pcall`, `string`, `table`,
`ipairs`, `type`, `tostring`, `math`) plus genuine DCS APIs — `log`, `net`, `require` in Hook state;
`coalition`, `coord`, `Unit`, `StaticObject`, `Object`, `world`, `timer` in the scripting state.
A mechanical ruling-out rather than an eyeball, for one command.

**Two caveats, the first of which matters more than the technique:**

- **`luac -p` on the outer file proves nothing about the half that actually runs.** A
  `dostring_in`-bridged chunk lives inside a string literal, and `luac` does not look inside
  strings — so that half has been going unchecked entirely. Extract the literal to its own file and
  check it separately (in `petrobrain-unit-id-join-probe-hook.lua` the bridged `PROBE_CODE` is
  lines 197-398, between `[==[` and `]==]`).
- A global that *should* be read (a real DCS API) and one that should not (your own helper) look
  identical to the tool. The check is only as good as knowing which names belong.

**Lua syntax check (`luac5.1 -p`)** parses without executing — it catches syntax errors in `Export.lua`, the Hook scripts, and probes before a DCS launch, and nothing more (`DCS`/`net`/`log`/`Lo*` exist only inside DCS, so behaviour still needs a live run). Must be **Lua 5.1** specifically, the version DCS embeds; a newer `luac` accepts syntax DCS rejects. Install: `sudo apt install lua5.1` (WSL/Debian).

## Testing

- `tests/test_schema.py`, `tests/test_cache.py` — fixture-based unit tests, no live DCS needed (schema parsing/validation, cache bookkeeping).
- `tests/test_api.py` — spins up a real `TelemetryAPIServer` on an OS-assigned port in a background thread, queries it with stdlib `urllib.request`.
- `tests/test_text_sender.py` — `TextOverlaySender` against a real throwaway UDP socket (well-formed datagram, truncation to `MAX_LINE_LENGTH`, a send to a closed port not raising).
- `tests/test_text_push_api.py` — `POST /text/push` against a real `TelemetryAPIServer` with a recording `TextOverlaySender` double (valid push, missing/invalid/empty `text`, non-JSON body, unconfigured `text_sender` → 503).
- `tests/test_audio_sender.py` — `AudioPlaybackSender`'s queue/preempt logic (BL-10 first slice, `plans/tts-voice-output/plan.md`) against a fake `WavPlayer` double, never the real `winsound` call: FIFO ordering, urgent-preemption (queued routine lines dropped, in-flight playback interrupted via `stop()`), a failing `play()` call not killing the worker loop, temp-file write/cleanup, plus (`plans/inbound-speech/plan.md` Stage 3 follow-up) `interrupt()` directly: queued lines dropped and in-flight playback stopped with nothing new enqueued, and a clean no-op when nothing is playing/queued.
- `tests/test_audio_play_api.py` — `POST /audio/play` against a real `TelemetryAPIServer` with a recording `AudioPlaybackSender` double, direct structural copy of `test_text_push_api.py`'s pattern (valid push + urgent-flag threading, missing/invalid/empty `audio_b64`, invalid base64, non-bool `urgent`, non-JSON body, unconfigured `audio_sender` → 503).
- `tests/test_audio_stop_api.py` (`plans/inbound-speech/plan.md` Stage 3 follow-up) — `POST /audio/stop` against a real `TelemetryAPIServer` with a recording `AudioPlaybackSender` double: forwards to `interrupt()`, no request body read; unconfigured `audio_sender` → 503. Simpler than `test_audio_play_api.py` since this endpoint takes no body.
- `Export.lua`, the overlay Hook script/`.dlg` pair, and the live Export.lua↔collector↔API path have **no automated test** — correctness there depends on a real DCS process and socket peer, validated manually against a running mission (procedure in `WORKFLOW.md`) and cross-checked against cockpit instrument readings/the overlay window itself. Mirrors `world-model/`'s `WM-M4`/`WM-M5` pattern of real-fixture-only validation for anything requiring a live DCS instance.
- **Always include a paused-state check alongside any moving-aircraft check** when testing a new DCS-interfacing feature live — the export-rate bug (stage 5 part 1) and the dropped delta-query endpoint (post-stage-5) were both real bugs invisible to in-flight-only testing and caught only by pausing the mission mid-test.

## Structure

- `dcs-export/Export.lua` — canonical, version-controlled Windows Export.lua script. Deployed by copying to `Saved Games\DCS\Scripts\Export.lua` on the Windows box; never edit the deployed copy in place. A synced copy lives at `win-mac-sync/to-windows/aircraft-layer/Export.lua` for machines using that sync folder instead of a direct repo checkout.
- `src/schema/` — the telemetry wire format and typed record (`TelemetrySample`), including parsing/validation. Single source of truth for field names/units. `world_objects.py` is the `LoGetWorldObjects` sibling schema (`WorldObjectSample`/`WorldObjectsSnapshot`); `petrovich_indication.py` is the `list_indication(HELPERAI_DEVICE_ID)` sibling (`PetrovichIndicationSample`, plus its own from-scratch recursive-descent tree parser, `parse_indication_text`). Re-exported from `schema/__init__.py`.
- `src/collector/` — loopback TCP listener receiving the Export.lua feed (`server.py`), most-recent-sample caches (`cache.py`: `TelemetryCache`/`WorldObjectsCache`/`PetrovichIndicationCache`/`PetrovichWheelCache`), `text_sender.py`/`command_sender.py` (collector-to-Hook/Export.lua UDP senders), process entrypoint wiring every server/sender/receiver together (`__main__.py`).
- `src/api/` — the LAN-facing API: `GET /telemetry/latest`, `GET /world_objects/latest`, `GET /petrovich_indication/latest`, `GET /petrovich_wheel/latest`, `POST /text/push` (BL-2.5, forwards to `collector.text_sender.TextOverlaySender`), `POST /command/petrovich_search` (BL-6, forwards to `collector.command_sender.CommandSender`), `POST /audio/play` (BL-10 first slice, `plans/tts-voice-output/plan.md` — forwards to `collector.audio_sender.AudioPlaybackSender.play_audio`, `{"audio_b64", "urgent"}`, `503` when unconfigured, never propagates a `500` since `play_audio` never raises), `POST /audio/stop` (`plans/inbound-speech/plan.md` Stage 3 follow-up — no request body, forwards to `AudioPlaybackSender.interrupt`, same `503`-when-unconfigured/never-`500` posture as `/audio/play`), `GET /watched_args/latest` + `POST /command/watch_args` (`plans/effector-sequences/plan.md` Stage 4 — the continuous cockpit-arg readback, replacing `GET /cockpit_switch/latest`), `POST /query/read_args` (same plan/stage — the one *synchronous* endpoint on this API, blocking on `collector.arg_read_broker.ArgReadBroker.read`).
- `src/collector/text_sender.py` — `TextOverlaySender`: fire-and-forget loopback UDP sender to the overlay Hook script (BL-2.5). `send_line` never raises — a missing listener (DCS not running, or running without the overlay script loaded) is an expected state, not an error, same posture as the `/latest` endpoints' empty-cache case.
- `src/collector/audio_sender.py` (BL-10 first slice, `plans/tts-voice-output/plan.md`) — `AudioPlaybackSender`: a background worker thread draining a `queue.Queue` of temp `.wav` paths, playing each one via a `WavPlayer` (`_WinsoundPlayer` on Windows, a `RuntimeError`-raising stand-in elsewhere — see the Tech stack note above). Unlike `TextOverlaySender`/`CommandSender`, this has no UDP/DCS-side listener at all — it plays audio directly on this box. `play_audio(audio, urgent)` never raises (Decision 5's never-raises posture); `urgent=True` clears any queued routine lines and interrupts in-flight playback (`_interrupt_playback`, one small function so the still-unverified `SND_PURGE` mechanism can change after a live test without touching queue logic) before enqueueing its own file. `interrupt()` (`plans/inbound-speech/plan.md` Stage 3 follow-up, `POST /audio/stop`'s collaborator) is that same `_clear_queue`/`_interrupt_playback` pair with the enqueue dropped — `play_audio`'s own `urgent=True` branch now just calls `self.interrupt()` rather than duplicating the two calls. `play_audio`/`/audio/play` also take an optional `correlation_id` (`plans/voice-latency-instrumentation/plan.md` Stage 4) — this is the one piece of the whole voice chain with no prior observability at all, so the worker thread logs `enqueue`/`playback-start`/`playback-finish` at `INFO` (existing stdlib `logging`, no new file) against it when supplied; `None` (no id given) logs nothing extra.
- `dcs-export/petrobrain-overlay-hook.lua` + `dcs-export/petrobrain-overlay.dlg` — canonical Hook-state overlay script + widget/skin definition (BL-2.5), deployed to `Saved Games\DCS\Scripts\Hooks\`. Modeled on DCS-SRS's own installed overlay; unverified against a live DCS session as of authorship (`plans/dcs-text-panel-output/plan.md` Stage 2 is user-only). **Single-message mode (2026-09-10 user decision):** a pushed line calls `message_text:clear()` before `addText()`, so a new message replaces whatever is shown immediately rather than accumulating a scrollback — the panel is mostly a debug tool for now, not a design the scrollback/duration machinery (`DEFAULT_DURATION_S`) was reworked around.
- `dcs-export/petrobrain-line-of-sight-hook.lua` — canonical Hook-state DCS-driven line-of-sight script (`plans/dcs-driven-los/plan.md`, X-B29), deployed to `Saved Games\DCS\Scripts\Hooks\`. Polls `net.dostring_in("scripting", ...)` at 1 Hz, and **enumerates both AI units (`coalition.getGroups()` → `grp:getUnits()`) and static objects (`coalition.getStaticObjects()`)** across all three coalition sides — the statics half added 2026-10-06 (`BL-11` Stage 4; before it, 278 of 404 objects in the measured sortie's mission, 68.8%, could never receive a verdict, "static" in DCS meaning placed without AI or waypoints rather than decorative). Both populations go through one shared `considerCandidate` filter (10 km bubble → commanded look-direction wedge → not ownship) into one nearest-first-sorted candidate list, so **a static is indistinguishable from a unit on the wire** and the body-layer join (by `unit_name`) needs no change. The join key is `getName()` and must stay so: `Unit:getObjectID()` does not exist on `StaticObject`, so no integer key spans both. Two independent engine calls per sightline, published as two never-pre-ANDed fields (`world.searchObjects`/`SEGMENT` for buildings, `land.isVisible` for terrain). Sends to the collector on loopback UDP 7796 (`src/schema/line_of_sight.py`); listens on 7797 for inbound look-direction commands. Unverified against a live DCS session as of the statics change — live behaviour needs Windows and a running mission.
- `tests/` — automated tests per "Testing" above.
- `WORKFLOW.md` — deploy/run/firewall/query steps for the live cross-machine path, including the overlay Hook script deploy (BL-2.5) and the mission-start Hook script deploy (`plans/bl15-mission-start/plan.md`, BL-15 Stage 1 — including its `autoexec.cfg` opt-in, now that bullet's canonical home since `BL-B96` removed the F10 commands Hook that originally carried it, and its own no-DCS-required manual UDP-send check).
