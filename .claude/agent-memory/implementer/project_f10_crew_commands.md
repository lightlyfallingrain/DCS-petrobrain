---
name: f10-crew-commands-stages-1-3
description: F10 radio-menu command input (Hook->collector reverse UDP direction) implementation notes
metadata:
  type: project
---

Implemented `plans/f10-crew-commands/plan.md` Stages 1-3 on
`feature/f10-crew-commands` (2026-09-13). Stage 4 is live-DCS, user-run.

- **First Hook-to-collector inbound UDP direction** in aircraft-layer —
  every prior channel was either DCS->collector (TCP, Export.lua) or
  collector->Hook/Export.lua (UDP, `TextOverlaySender`/`CommandSender`).
  New port 7794, `F10CommandReceiver` (loopback listener, mirrors
  `CollectorServer`'s open()/serve_forever()/close() shape run on its own
  background thread from `__main__.py`, not a thread it owns itself).
- **`F10CommandQueue` is the first bounded-FIFO event-queue cache** in
  `collector/cache.py` — every other cache there is a single-slot "latest"
  cache. `drain_all` uses repeated `popleft()`, not snapshot-then-clear, so
  a concurrent `push` from the receiver thread can't be silently dropped
  between the snapshot and the clear.
- **No aircraft-layer `.venv` exists.** Ran its ruff/mypy/pytest via
  `body-layer/.venv`'s interpreter (stdlib-only subproject, no dependency
  conflict). See also [[project_worldmodel_no_dep_tooling]] for the
  parallel world-model situation.
- **`--crew-text`'s `aircraft_client`/`ConsolePerceptionRunner.tasks` were
  already wired/ticked** before this feature (BL-6 left `aircraft_client`
  as a reserved unused field on `CrewConsole`; `ConsolePerceptionRunner`
  always builds+ticks a `TaskStore`). So `scan_forward`/`cancel_task`
  needed zero new plumbing beyond passing `tasks=crew_runner.tasks` into
  `CrewConsole(...)` — verify reachability before assuming a wiring gap,
  per the orchestrator's own instruction to check this first.
- **`missionCommands.removeItem` (non-ForGroup) is NOT independently
  live-probed** by the research doc — only `addCommand`/`addSubMenu` were
  (research doc run 2). Used anyway (wrapped in `pcall`) per explicit user
  instruction for idempotent F10 registration; Stage 4's live
  "mission-restart check" is what actually confirms it works.
- **Plan's Stage 2 manual-check text (`curl -X POST .../f10_commands`) was
  simply wrong** — this channel has no POST endpoint, the receiver is
  loopback UDP. Corrected in WORKFLOW.md to a `python3 -c` UDP `sendto`
  one-liner per the orchestrator's explicit override. Worth re-reading a
  plan's own manual-check prose against its Affected Modules section
  before trusting it verbatim.
