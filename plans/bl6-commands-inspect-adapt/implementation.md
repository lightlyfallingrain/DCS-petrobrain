### Implementation Summary

Implemented the locked plan (`plans/bl6-commands-inspect-adapt/plan.md`, commit
`2c98ff9`) in full: the body-layer `PendingIntent`/`TaskStore` command lifecycle
(`scan_area`/`get_task_status`/`cancel_task`), console wiring with an optional
live-effector trigger, and the matching aircraft-layer command channel
(`POST /command/petrovich_search`, `GET /petrovich_wheel/latest`, and the
`Export.lua` wheel-press/long-hold sequencing). All three previously-open
decisions were already resolved in the plan text (Decision 3: `cancel_task`
removes the `AttentionArea` it registered) and implemented as written; no new
decisions needed escalation.

### Files Changed

**body-layer**
- `body-layer/src/belief/tasks.py` *(new)* — `PendingIntent`/`TaskStore`:
  store-minted task ids, `tick(store, now_sim)` resolves `pending` tasks to
  `succeeded` (any `Contact` inside `task.area` with `last_seen_sim >
  task.created_sim`) or `failed` (past `deadline_sim` with nothing found).
  Pure, no DCS I/O.
- `body-layer/src/belief/tools.py` — `scan_area`/`get_task_status`/
  `cancel_task`, plus `DEFAULT_SCAN_DEADLINE_S` (placeholder `60.0`, flagged
  as needing live-sortie calibration per the plan's Risks section).
  `scan_area` takes an explicit `now_sim: float` parameter — the plan's
  listed signature omitted it, but `PendingIntent.created_sim`/
  `deadline_sim` are sim-time (never wall clock, matching every other
  `belief.*` timestamp's replay-determinism requirement), so a caller-supplied
  `now_sim` is structurally necessary; treated as filling an omission in the
  plan's prose, not a deviation from its design. `cancel_task` removes the
  registered `AttentionArea` per Decision 3.
- `body-layer/src/belief/tool_api.py` — three new `ToolSpec` entries with
  the plan-mandated "does not aim Petrovich" / "failed != confirmed empty"
  caveats in their descriptions; updated the module docstring's stale
  "BL-7" freeze-point reference to BL-6.
- `body-layer/src/belief/console.py` — `scan-area <bearing> <range_m>
  <radius_m> <reason> [sector]`, `task-status <id>`, `cancel-task <id>`.
  `Console` gained `tasks: TaskStore` and `aircraft_client:
  AircraftLayerClient | None` fields (the latter mirroring `enrichment`'s
  None-means-unchanged pattern). `scan-area`'s handler calls `tools.scan_area`
  unconditionally, then (if `aircraft_client` is set) calls
  `trigger_petrovich_search("forward")` inside a `try`/`except
  AircraftLayerError` that degrades to "task registered, no live command
  fired." `task-status` optionally appends a raw `wheel.fields` diagnostic
  line, never stored on the `PendingIntent`.
- `body-layer/src/aircraft_client.py` — `trigger_petrovich_search(mode)`
  (`POST /command/petrovich_search`, raises `AircraftLayerError`, mirrors
  `push_text_line`) and `get_petrovich_wheel_latest()` (`GET
  /petrovich_wheel/latest`, mirrors `get_petrovich_indication_latest`).
- `body-layer/src/belief/crew_console.py` — added a reserved, currently-unread
  `aircraft_client: AircraftLayerClient | None` field for parity with
  `Console`'s own field, per the plan's "Console.aircraft_client (or
  CrewConsole's equivalent)" wiring instruction. No player-facing
  `scan_area`-equivalent utterance exists this milestone, so nothing reads it
  yet — documented in the field's own docstring as reserved, not dead code.
- `body-layer/src/logger.py` — `ConsolePerceptionRunner.tasks: TaskStore`,
  ticked via `self.tasks.tick(self.store, ownship.t_sim)` immediately after
  `self.store.tick(...)` in `run_once`. `main()` wires a real
  `AircraftLayerClient` into `Console.aircraft_client` (`--console` branch)
  and `CrewConsole.aircraft_client` (`--crew-text` branch), and passes
  `console_runner.tasks` into `Console`.
- `body-layer/tests/test_tasks.py` *(new)*, extensions to `test_tools.py`,
  `test_console.py`, `test_aircraft_client.py`, `test_tool_api.py` (the
  latter's tool-count assertion updated from "twelve BL-5 tools" to the
  full frozen BL-6 set — an anticipated update per the plan's and
  `tool_api.py`'s own "expected to extend TOOL_SET" documentation, not an
  unrelated test rewrite).

**aircraft-layer**
- `aircraft-layer/dcs-export/Export.lua` — a new loopback UDP command
  listener (`COMMAND_HOST:7793`, a third distinct loopback port alongside
  the existing TCP push port 7790 and the overlay's UDP port 7792),
  `poll_command_socket`/`handle_petrovich_search_command` (menu-open +
  press-down every command, immediate release for `"boresight"`, a
  `pending_release_t` deadline checked every frame for `"forward"`'s long
  press), and a `list_indication(WHEEL_INDICATOR_ID)` (device 10) push
  alongside the existing device-6 push, same throttle/pcall/one-shot-dump
  pattern. Command handling runs every frame, ahead of the 5 Hz export
  throttle, so a queued command or a pending release is never delayed
  behind the telemetry cadence. Syntax-verified with `luac -p` (no live DCS
  session available in this environment — per the plan's Stage 5/6 split,
  build+unit-test now, live-validate against a running mission before this
  stage is considered fully done).
- `aircraft-layer/src/schema/petrovich_wheel.py` *(new)* —
  `PetrovichWheelSample`, reusing `petrovich_indication.py`'s
  `parse_indication_text` against the `"wheel"` top-level key.
- `aircraft-layer/src/schema/__init__.py` — re-exports the new schema.
- `aircraft-layer/src/collector/cache.py` — `PetrovichWheelCache`.
- `aircraft-layer/src/collector/command_sender.py` *(new)* —
  `CommandSender`, mirroring `TextOverlaySender`'s lifecycle but with the
  plan's flagged asymmetry: `send_command` raises `CommandSendError` on a
  failed `sendto`, rather than swallowing it.
- `aircraft-layer/src/collector/server.py` — routes a `"wheel"`-keyed line
  to `PetrovichWheelCache`, alongside the existing `"indication"`/
  `"objects"` routing.
- `aircraft-layer/src/collector/__main__.py` — wires `PetrovichWheelCache`
  and `CommandSender` into `CollectorServer`/`TelemetryAPIServer`, with new
  `--command-host`/`--command-port` CLI flags.
- `aircraft-layer/src/api/server.py` — `POST /command/petrovich_search`
  (validates `mode` against `{"forward", "boresight"}`, `503` if
  unconfigured, `500` on `CommandSendError`, `200 {"ok": true}` otherwise —
  "attempted the call" only) and `GET /petrovich_wheel/latest`.
- `aircraft-layer/tests/test_petrovich_wheel_schema.py`,
  `test_petrovich_wheel_cache.py`, `test_command_sender.py`,
  `test_petrovich_search_api.py` *(all new)* — mirror the existing
  petrovich-indication/text-push test patterns. `test_command_sender.py`'s
  raise-on-failure test uses a `_FailingSocket` double rather than a real
  closed-port send, since (per `test_text_sender.py`'s own comment) a UDP
  send to a closed port does not reliably raise synchronously on the first
  call — a real-socket test would be flaky, not a faithful exercise of the
  documented failure path.

### Tests Added

- `test_tasks.py` — success on a post-creation in-area contact, ignores a
  pre-creation contact, timeout at deadline, ignores an out-of-area contact,
  cancel stops future resolution, unknown-id cancel returns `False`,
  `tick` idempotence for a repeated `now_sim`.
- `test_tools.py` (BL-6 section) — `scan_area` registers a watch area +
  pending task, honors a custom deadline, `get_task_status` unknown/known
  id, `cancel_task` cancels + removes the area, unknown-id cancel.
- `test_console.py` — `scan-area` enrichment guard, usage message, task
  creation without a live client, trailing-sector parsing, live-trigger
  success/failure degradation (via a `_RecordingAircraftClient` double),
  `task-status` unknown/usage/pending/live-wheel-diagnostic, `cancel-task`
  unknown id + cancel-and-remove-area.
- `test_aircraft_client.py` — `get_petrovich_wheel_latest` parses correctly,
  `trigger_petrovich_search` posts the mode and raises on an unreachable
  host.
- `test_tool_api.py` — extended the frozen tool-set assertion to the full
  BL-6 set.
- `test_petrovich_wheel_schema.py` — wire-format parsing/validation
  (missing/invalid fields, round-trip `to_dict`).
- `test_petrovich_wheel_cache.py` — empty/latest-wins behavior.
- `test_command_sender.py` — well-formed datagram for both modes, lazy
  socket open, raise-on-failed-send via a failure-injecting double.
- `test_petrovich_search_api.py` — valid/invalid mode, missing/non-JSON
  body, unconfigured-sender 503, send-failure 500, `/petrovich_wheel/latest`
  empty/populated.

### Checks

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass
- pytest -q: pass (437 passed)

**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass
- pytest -q: pass (90 passed)

### Notable Discoveries

- The plan's listed `scan_area` signature (`store, tasks, center, radius_m,
  reason, deadline_s=..., sector=None`) omits `now_sim`, unlike every other
  sim-time-consuming function in `belief.tools`. Added it rather than
  reading the omission as intentional — `PendingIntent.created_sim`/
  `deadline_sim` cannot be computed without a caller-supplied sim time
  without breaking BL-0's replay-determinism invariant (never derive a
  timestamp from wall clock). Flagged here since it's a real, if small,
  deviation from the plan's literal text.
- `belief.crew_console.CrewConsole` gained an `aircraft_client` field that
  no command currently reads. The plan's wording ("Console.aircraft_client
  (or CrewConsole's equivalent)") reads as wanting wiring parity between the
  two consoles' `--console`/`--crew-text` branches, but no player-facing
  `scan_area`-equivalent utterance exists in this milestone's scope — kept
  the field for the wiring symmetry the plan asked for for, documented as
  reserved rather than silently adding scope (no new grammar/utterance
  handling was built).
- `Export.lua`'s new command-handling code could not be live-tested in this
  environment (no DCS instance available) — verified only with `luac -p`
  syntax checking, consistent with this subproject's existing "no automated
  test for the live Export.lua path" posture (`aircraft-layer/CLAUDE.md`
  Testing section). The plan's Stage 6 (end-to-end live acceptance: real
  `SRCH FWD` firing, `list_indication(10)` state transition, `task-status`
  eventually reporting `succeeded` from a real detection) is unchanged as
  the user's own follow-up, per this project's execution-boundary rule.
