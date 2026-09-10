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
| World Model | **Good enough, gate lifted 2026-09-06.** M0–M8 done. M9 (OSM augmentation) deferred, unscheduled. | [`world-model/ROADMAP.md`](world-model/ROADMAP.md) |
| Aircraft Layer | **Core done, merged 2026-09-07.** DCS I/O pipeline (telemetry, world objects, Petrovich indication text, text-overlay write channel) live and stable. A few small tuning items open. | [`aircraft-layer/ROADMAP.md`](aircraft-layer/ROADMAP.md) |
| Body Layer | **In progress — BL-5 done, BL-5a blocked pending an Architect decision.** Contact memory, classification, world enrichment, attention/events, and the deterministic tool API are all built and merged; the text-mode crew-interaction milestone (BL-5a) found a duplicate-contact bug that a later, already-merged fix likely resolves — needs re-verification, not new debugging. | [`body-layer/ROADMAP.md`](body-layer/ROADMAP.md) |
| Mission Interpreter | Not started. | — |

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
