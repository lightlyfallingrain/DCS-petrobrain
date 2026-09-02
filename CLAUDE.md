# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Petrobrain: make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems. Guiding principle: **code owns truth, models own interpretation and language** — Petrovich must never be omniscient; his knowledge is bounded by what he could actually perceive.

Three-layer architecture, each a separate component with explicit interfaces:

1. **DCS World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads, settlements, terrain, ridges/valleys), built offline from DCS-derived data + OSM/DEM augmentation. DCS geometry is always authoritative; external GIS augments, never overrides.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model + player intent) using a capable model, offline/pre-mission. Produces a structured "Mission Understanding," not prose. Must filter out mission-author-only knowledge (hidden triggers, scripted ambushes) before it reaches the crew layer.
3. **Petrobrain Runtime** — low-latency runtime crew cognition (perception, episodic/working memory, attention, dialogue) using a small/fast local model. Memory is explicit application state, never LLM chat history.

Full rationale: `docs/concept/PETROBRAIN_SYSTEM.md`. Per-layer draft designs (status: draft/provisional, revise as earlier layers mature): `docs/concept/WORLD_MODEL_BUILDER.md`, `docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Current priority

**World Model Builder only** (`world-model/`). Do not implement Mission Interpreter or Petrobrain runtime behavior yet — those depend on what the World Model proves possible. See `world-model/ROADMAP.md` for milestone status.

## Working conventions

- **Reconnaissance before implementation.** DCS internals are incompletely documented and change over versions — verify claims against the installed DCS version and record findings in `world-model/research/` (version, theatre, file/API, exact observation, documented-vs-inferred, reproducible test, source). Do not encode forum folklore as fact.
- **Provenance and confidence are first-class.** Any feature derived from mixing DCS + external GIS data must record source and match confidence per-field, not collapse into one undocumented fact.
- **Cross-machine setup**: DCS World runs on a separate Windows PC; primary development is on this Mac. Manual-copy workflow — see `world-model/WORKFLOW.md`. Raw extracted data lives under `world-model/data/raw/` and is gitignored; never commit it.
- **Read-only against DCS.** Never modify the DCS installation.
- Python 3.11+, type-hinted throughout, `mypy --strict` (see `world-model/pyproject.toml`). Spatial library choices are not yet locked — decide during Milestone 1-2 and record the decision + rationale in `world-model/research/`.
