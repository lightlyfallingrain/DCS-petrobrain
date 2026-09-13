### Implementation Summary

Implemented Stages 1-3 of `plans/f10-crew-commands/plan.md` on
`feature/f10-crew-commands`. Stage 4 (live DCS acceptance) is user-run and
was not attempted.

**Stage 1 (aircraft-layer, collector-side inbound channel).** A new
Hook-to-collector loopback UDP direction (the reverse of the existing
collector-to-Hook `TextOverlaySender`/`CommandSender` channels):
`schema.F10CommandEvent` (wall-clock-only provenance, no `dcs_model_time_s`
-- the Hook cannot cheaply attach DCS's sim clock), `collector.cache.
F10CommandQueue` (a bounded FIFO event queue -- `push`/`drain_all`, not
`push`/`latest`, since two F10 selections inside one poll interval must
both survive; `drain_all` uses repeated `popleft()` rather than
snapshot-then-clear so a concurrent `push` from the receiver thread is
never silently lost), `collector.f10_command_receiver.F10CommandReceiver`
(a loopback UDP listener on port 7794, validates every datagram against a
fixed `ALLOWED_COMMANDS = ("watch_nearest", "scan_forward",
"cancel_task")` before enqueueing), and `GET /f10_commands/poll` (drains
the queue, oldest first, `[]` not `null` -- the one endpoint on this API
that mutates state on every call). Wired into `collector/__main__.py`
behind new `--f10-host`/`--f10-port` flags (default `127.0.0.1:7794`).

**Stage 2 (body-layer consumption).** `AircraftLayerClient.get_f10_commands`
polls `GET /f10_commands/poll` (raises `AircraftLayerError` on transport
failure like every other `get_*`, but returns `[]` rather than `None` on
an empty response, since this endpoint's response is always a list).
`CrewConsole` gains a `tasks: TaskStore | None = None` field and
`handle_f10_command(token, now_sim) -> list[str]`, dispatching through the
same `_print` funnel `handle_line`/`drain_events` already use:
- `watch_nearest` -> a new `_nearest_contact_id` helper (scans
  `get_contacts(store, now_sim, enrichment=...)` for the minimum
  `facts["relative_now"]["range_m"]`; returns `None` without `enrichment`
  or without contacts) + `set_attention(..., "watch", ...)`.
- `scan_forward` -> the bare AI-Wheel trigger
  (`aircraft_client.trigger_petrovich_search("forward")`), **not**
  `belief.tools.scan_area` -- an F10 button has no geometry/reason to
  supply, and fabricating placeholder values for `scan_area`'s
  `bearing_deg`/`range_m`/`radius_m`/`reason` would be invented-not-derived
  behavior. This was verified reachable before implementing: `logger.py`'s
  `--crew-text` branch already wires `CrewConsole(aircraft_client=
  aircraft_client, ...)` (pre-existing, BL-6's reserved field), so no
  additional wiring was needed for this call to work.
- `cancel_task` -> cancels the most-recently-created still-`pending` task
  in `self.tasks` (`TaskStore.tasks` is insertion order, so `pending[-1]`),
  regardless of source, via `belief.tools.cancel_task`.

`logger.py` gains `--f10-commands` (only meaningful with `--crew-text`,
same additive-no-op posture as `--overlay`) and a `_poll_f10_commands`
helper called from `_run_crew_text_poll_loop` right after `drain_events`,
wrapped in its own `try/except AircraftLayerError` (log-and-continue) so
one failed poll never stops the loop. `main()`'s `--crew-text` branch now
also wires `CrewConsole(tasks=crew_runner.tasks, ...)` -- the same
`TaskStore` `ConsolePerceptionRunner.run_once` already ticks every poll.

**Stage 3 (the Hook script, Lua-only).**
`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`: registers
F10 -> Other -> Petrovich (three fixed items) via
`net.dostring_in("scripting", ...)` at `onSimulationStart` (idempotently --
`missionCommands.removeItem({"Petrovich"})`, wrapped in `pcall`, before
`addSubMenu`/`addCommand`, per the orchestrator's explicit instruction so a
second `onSimulationStart` cannot duplicate entries), polls the same
bridge at 1 Hz gated to run only between `onSimulationStart`/
`onSimulationStop` (poll timer reset to 0 at every `onSimulationStart`),
and forwards drained tokens to the collector's new port 7794 as one fixed
`{"command": "<token>"}` JSON datagram per token. Both `dostring_in`
snippets (`REGISTRATION_CODE`, `POLL_CODE`) are fixed string literals
baked in at authoring time -- never built from network input. Uses
`"scripting"`, not `"mission"`/`a_do_script`, per the research doc's run 2
finding that `"mission"`'s `a_do_script` never actually executed the
registration code. Mirrors `petrobrain-overlay-hook.lua`'s
`package.path`/`cpath` extension and `Scripts\JSON.lua` reuse verbatim.
Kept as its own file (not an extension of the overlay Hook script) since
this channel runs the opposite direction with a different lifecycle
trigger. Syntax-checked with `luac5.1 -p` (Lua 5.1, matching DCS's embedded
version) -- no automated behavioral test, same posture as every other Hook
script in this project (correctness needs a live DCS session).

`aircraft-layer/WORKFLOW.md` gains a "Deploy the F10 commands Hook script"
section (the `autoexec.cfg` opt-in -- try
`net.allow_dostring_in = { "scripting" }` alone first per the plan's Stage
4, falling back to the research doc's known-working superset if that
fails; the port-7794 entry; a no-DCS-required manual `python3 -c` UDP-send
check per the orchestrator's explicit deviation from the plan's stale
`curl -X POST` example -- there is no POST endpoint for this channel, the
receiver is loopback UDP) and updates to "Run the collector"/"Query from
the Mac".

### Deviations from the plan

- **Manual verification command.** The plan's Stage 2 text says "a
  developer can `curl -X POST .../f10_commands`" -- this is inconsistent
  with the plan's own Affected Modules section (a UDP receiver, no POST
  endpoint) and was corrected per the orchestrator's explicit instruction:
  `WORKFLOW.md` now documents a one-line `python3 -c` UDP `sendto` instead.
- No other deviations. `trigger_petrovich_search("forward")` reachability
  was verified before implementing Stage 2 (see above) rather than
  assumed; no additional wiring was required.

### Files Changed

**aircraft-layer**
- `src/schema/f10_command.py` *(new)* — `F10CommandEvent`, wall-clock-only provenance.
- `src/schema/__init__.py` — re-exports `F10CommandEvent`/`F10CommandParseError`.
- `src/collector/cache.py` — adds `F10CommandQueue` (bounded FIFO event queue).
- `src/collector/f10_command_receiver.py` *(new)* — `F10CommandReceiver`, loopback UDP listener + `ALLOWED_COMMANDS`.
- `src/api/server.py` — adds `GET /f10_commands/poll`.
- `src/collector/__main__.py` — wires `F10CommandQueue`/`F10CommandReceiver`, new `--f10-host`/`--f10-port` flags.
- `dcs-export/petrobrain-f10-commands-hook.lua` *(new)* — the Hook script.
- `WORKFLOW.md` — new deploy section + collector/query section updates.
- `CLAUDE.md` — "What this is"/Tech stack/Structure updated for the new inbound direction and provenance exception.
- `tests/test_f10_command_schema.py`, `tests/test_f10_command_queue.py`, `tests/test_f10_command_receiver.py`, `tests/test_f10_command_api.py` *(new)*.

**body-layer**
- `src/aircraft_client.py` — adds `get_f10_commands`.
- `src/belief/crew_console.py` — adds `tasks` field, `handle_f10_command`, `_nearest_contact_id`, three private handlers.
- `src/logger.py` — adds `--f10-commands` flag, `_poll_f10_commands`, wires `CrewConsole(tasks=...)`.
- `CLAUDE.md` — documents the above.
- `tests/test_aircraft_client.py` — adds `get_f10_commands` tests.
- `tests/test_crew_console.py` — adds `handle_f10_command` tests for all three tokens plus guard-clause cases.

### Tests Added

**aircraft-layer**
- `test_f10_command_schema.py` — `F10CommandEvent.from_dict`/`to_dict`, missing/non-string/empty `command` field.
- `test_f10_command_queue.py` — empty drain, oldest-first drain-and-empty, `maxlen` drops oldest.
- `test_f10_command_receiver.py` — real loopback UDP: well-formed enqueue, all three allowed tokens, unrecognized token dropped, malformed JSON dropped, non-object JSON dropped, missing `command` field dropped, queue bound respected.
- `test_f10_command_api.py` — empty queue -> `[]`, drains oldest-first, drains only once (second poll empty), unconfigured queue -> `[]` (not 503).

**body-layer**
- `test_aircraft_client.py` — `get_f10_commands` parses the list; raises on unreachable host.
- `test_crew_console.py` — unrecognized token -> `[]`; `watch_nearest` without enrichment / with empty store -> "no contact to watch"; `watch_nearest` selects the nearer of two contacts by range (via a monkeypatched `EnrichmentContext`, mirroring `test_console.py`'s own fixture pattern); `scan_forward` without/with a configured `aircraft_client`, including the failed-trigger degrade path; `cancel_task` without `tasks` configured / with none pending / cancelling the most-recently-created pending task while an older one stays `pending`; overlay push via the shared `_print` funnel.

### Checks

**aircraft-layer/** (via `body-layer/.venv`, stdlib-only so no conflict; no aircraft-layer `.venv` exists yet — see agent memory `project_worldmodel_no_dep_tooling`-style note, first observed for this subproject)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass, 14 source files
- `pytest -q`: pass, 109 passed
- `luac5.1 -p` on every `dcs-export/*.lua` (11 files, Lua 5.1.5): pass

**body-layer/** (`.venv`, mypy run from inside `body-layer/` per its CLAUDE.md CWD note)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass, 30 source files
- `pytest -q`: pass, 488 passed

### Notable Discoveries

- **No `aircraft-layer/.venv` exists.** Ran its format/lint/type/test commands via `body-layer/.venv`'s interpreter instead — safe because aircraft-layer is stdlib-only (no dependencies to conflict with body-layer's `pyproj`).
- **`trigger_petrovich_search("forward")` was already reachable in `--crew-text` mode** before this feature — `logger.py`'s `--crew-text` branch already passed `aircraft_client=aircraft_client` into `CrewConsole` for BL-6's reserved field. No wiring gap to close, contrary to what the orchestrator's instructions flagged as a possible scope expansion.
- **`ConsolePerceptionRunner.tasks` already exists and is already ticked** in both `--console` and `--crew-text` modes (`TaskStore = field(default_factory=TaskStore)`, ticked in `run_once`) — `CrewConsole.tasks` only needed wiring to the existing instance, not a new store or a new tick call site.
- **`missionCommands.removeItem` (non-`ForGroup` form) was not independently live-probed** by the research doc — only `addCommand`/`addSubMenu` were. Used per the orchestrator's explicit instruction and wrapped in `pcall` as a defensive guard; Stage 4's live "mission-restart check" is what actually confirms it prevents duplication rather than merely not erroring.
