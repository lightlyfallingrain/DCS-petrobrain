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
2. **Mission Interpreter** (`mission-interpreter/`) — understands one specific mission (`.miz` +
   briefing + world model + player intent), offline/pre-mission. MI-0–MI-6 done, the last planned
   stage; no BL-7 consumer wired up yet.
3. **Body Layer / Petrobrain Runtime** (`body-layer/`, fed by `aircraft-layer/`) — low-latency
   runtime crew cognition: perception, episodic/working memory, attention, dialogue. Memory is
   explicit application state, never LLM chat history.

Per-layer design docs (status: draft/provisional): `docs/concept/WORLD_MODEL_BUILDER.md`,
`docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Status by subproject

| Subproject | Status | Roadmap |
|---|---|---|
| World Model | **M0–M10 done, all query surfaces (settlement boundaries, road junctions, LOS) serving Mission Interpreter via HTTP.** M10 junctions-streaming-fix (merged 2026-09-13) resolves the OOM-kill that ended the user's `syria-full` rebuild at Stage 5; user's next rebuild is expected to complete Stage 5 and is the natural follow-up validation. Multi-theatre support (Afghanistan/Caucasus/Kola) is backlog, needed soonish — architecture already generalizes (per-theatre registries), Kola has a real elevation-source gap (SRTM has no coverage above 60°N). | [`world-model/ROADMAP.md`](world-model/ROADMAP.md) |
| Aircraft Layer | **Core done, merged 2026-09-07.** DCS I/O pipeline (telemetry, world objects, Petrovich indication text, text-overlay write channel, F10 radio-menu command input merged 2026-09-13) live and stable. A few small tuning items open. | [`aircraft-layer/ROADMAP.md`](aircraft-layer/ROADMAP.md) |
| Body Layer | **BL-7 done (merged 2026-09-13).** BL-0 through BL-7 complete: contact memory, classification, world enrichment, attention/events, the deterministic tool API (frozen at twelve tools since BL-6), text-mode crew interaction, Petrovich command/verification (`scan_area`/`get_task_status`/`cancel_task`, BL-6), and mission-phase tracking/relevance (BL-7, monotonic waypoint sequencing via Mission Interpreter MI-6 output, phase-proximity tie-break within attention tiers). Live-DCS acceptance of BL-6's search effector deferred to user; BL-7's live acceptance (real MI-6 end-to-end) also deferred. F10 radio-menu command input merged 2026-09-13 (mechanism live-accepted; command refinement deferred until the full pipeline works). BL-8 (memory layer interfaces) deliberately last, gated on BL-2..BL-7 real-flight experience. | [`body-layer/ROADMAP.md`](body-layer/ROADMAP.md) |
| Mission Interpreter | **MI-0–MI-6 done — the last planned Mission Interpreter stage.** MI-0, MI-1, MI-1.5, MI-2, MI-3, MI-4 (capable-model synthesis with `qwen3:14b`, merged 2026-09-12), MI-5 (player questions, text console MVP, merged 2026-09-12), and MI-6 (runtime compilation into the compact `RuntimeMissionUnderstanding`, 2026-09-12) complete. Consumed by body-layer's BL-7 (mission phase and relevance, merged 2026-09-13). | [`mission-interpreter/ROADMAP.md`](mission-interpreter/ROADMAP.md) |

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
