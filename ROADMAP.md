# Petrobrain — Roadmap

## Goal

Make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems.
Petrovich must never be omniscient — his knowledge is bounded by what he could actually perceive.
Guiding principle: **code owns truth, models own interpretation and language.** Full rationale:
`docs/concept/PETROBRAIN_SYSTEM.md`.

## Architecture

Three layers, each a separate subproject with an explicit interface:

1. **World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads,
   settlements, terrain, elevation), built offline from DCS-derived data + external DEM/OSM
   augmentation. DCS geometry is always authoritative.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model +
   player intent), offline/pre-mission. Not started yet.
3. **Body Layer / Petrobrain Runtime** (`body-layer/`, fed by `aircraft-layer/`) — low-latency
   runtime crew cognition: perception, episodic/working memory, attention, dialogue. Memory is
   explicit application state, never LLM chat history.

Per-layer design docs (status: draft/provisional): `docs/concept/WORLD_MODEL_BUILDER.md`,
`docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Status by subproject

| Subproject | Status | Roadmap |
|---|---|---|
| World Model | **Ready for MI-2 onwards (M0–M10, M9 merged 2026-09-12).** Mission Interpreter's world-enrichment stage (MI-2) can now query settlement *boundaries* via `inside_settlement`; all query surfaces ready. Next unblocking: MI-2 (needs M9's data + world-model HTTP server for cross-process access). | [`world-model/ROADMAP.md`](world-model/ROADMAP.md) |
| Aircraft Layer | **Core done, merged 2026-09-07.** DCS I/O pipeline (telemetry, world objects, Petrovich indication text, text-overlay write channel) live and stable. A few small tuning items open. | [`aircraft-layer/ROADMAP.md`](aircraft-layer/ROADMAP.md) |
| Body Layer | **In progress — BL-6 done, tool-set frozen.** Contact memory, classification, world enrichment, attention/events, the deterministic tool API (now frozen at twelve tools as of BL-6, moved from the originally-planned BL-7), text-mode crew interaction, and Petrovich command/verification (`scan_area`/`get_task_status`/`cancel_task`, BL-6, merged 2026-09-11) are all built and merged. Live-DCS acceptance of BL-6's new aircraft-layer effector is the user's own deferred follow-up. | [`body-layer/ROADMAP.md`](body-layer/ROADMAP.md) |
| Mission Interpreter | **In progress.** MI-0, MI-1, MI-1.5, MI-2, and MI-3 (schema + mechanical field mapping + epistemic tagging, merged 2026-09-12) all done. MI-4 (capable-model synthesis) next, gated on Decision 3 (model choice/hosting). | [`mission-interpreter/ROADMAP.md`](mission-interpreter/ROADMAP.md) |

## Keeping this current

Each subproject's `ROADMAP.md` is the source of truth for that subproject's milestone status —
this file only tracks the cross-subproject picture. `todo/todo.md` no longer duplicates milestone
narrative; it holds only items that don't yet belong to one subproject's roadmap (cross-cutting
backlog, session-scoped notes) and User priority tasks.

The `/merge` skill (`.claude/skills/merge.md`) and the DoD agent (`.claude/agents/dod.md`) both
require the relevant `ROADMAP.md` (and, for a cross-subproject change, this file) to be updated
*in the same push* as any merge — a roadmap update is part of finishing a merge, not a follow-up
task. If a roadmap file and `todo/todo.md`/another roadmap ever disagree, treat that as a bug in
the update discipline, not as ambiguity to guess through — fix the stale one immediately.
