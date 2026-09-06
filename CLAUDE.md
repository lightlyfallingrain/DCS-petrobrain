@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `docs/PROCESS.md` for generic engineering heuristics/protocols (decision heuristics, implementation strategy, debugging protocol, dependency policy, autonomy, NOTES.md conventions) — not repeated here.

## Project

Petrobrain: make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems. Guiding principle: **code owns truth, models own interpretation and language** — Petrovich must never be omniscient; his knowledge is bounded by what he could actually perceive.

Three-layer architecture, each a separate component with explicit interfaces:

1. **DCS World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads, settlements, terrain, ridges/valleys), built offline from DCS-derived data + OSM/DEM augmentation. DCS geometry is always authoritative; external GIS augments, never overrides.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model + player intent) using a capable model, offline/pre-mission. Produces a structured "Mission Understanding," not prose. Must filter out mission-author-only knowledge (hidden triggers, scripted ambushes) before it reaches the crew layer.
3. **Petrobrain Runtime** — low-latency runtime crew cognition (perception, episodic/working memory, attention, dialogue) using a small/fast local model. Memory is explicit application state, never LLM chat history.

Full rationale: `docs/concept/PETROBRAIN_SYSTEM.md`. Per-layer draft designs (status: draft/provisional, revise as earlier layers mature): `docs/concept/WORLD_MODEL_BUILDER.md`, `docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Current priority

**World Model Builder only** (`world-model/`). Do not implement Mission Interpreter or Petrobrain runtime behavior yet — those depend on what the World Model proves possible. See `world-model/ROADMAP.md` for milestone status.

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory. Currently: `world-model/CLAUDE.md` (see also `world-model/docs/CONVENTIONS.md` for its working rules: DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access).

## Agents

8 agent roles live in `.claude/agents/`: the 7 template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — see `AGENTS.md` for role sequences) plus a project-specific `investigator`. All default to `claude-sonnet-5`, except `dod` which uses `claude-haiku-4-5-20251001` (cheap final gate). For architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override rather than relying on its sonnet default.

**Skip `performance-reviewer` and `security` for now** — this phase is an offline single-user local pipeline with no hot path and no untrusted-input surface yet. Do not insert them into the default role sequence from `AGENTS.md`. Only run either when the user explicitly asks for it.

**`investigator`** is this project's recon role, needed because much of the World Model Builder depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability). It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain: **Architect invokes it proactively whenever a plan would otherwise depend on an unverified DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only role. It writes dated findings to `world-model/research/` per the format in `docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

## Session Start

1. Read `todo/todo.md`
2. Identify the next actionable milestone (first non-completed, non-deferred section with open items)
3. Show that milestone and its subitems to the user
4. Ask what they want to work on

## Milestone Completion

Before marking a milestone done in `world-model/ROADMAP.md`, answer one question in the DoD report or todo.md update: does this milestone's completion change what the next milestone should be, or invalidate an assumption downstream milestones rely on? One line is enough — this is the project's inspect-and-adapt checkpoint, tied to milestone boundaries rather than a calendar.

## Verification

Run the active subproject's format/lint/type/test commands after every code change and always before a commit — see `world-model/CLAUDE.md` "Commands" for the current list (ruff format/check, mypy --strict, pytest). This is the same sequence the pre-commit hook enforces mechanically — stating it here prompts self-verification earlier, during implementation, instead of only at commit time.

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create and checkout a feature branch before starting any implementation task.** Name the branch after the feature using kebab-case (e.g., `feature/hyg-data-pipeline`, `fix/floating-origin-precision`). Never implement directly on `main`. **Always branch from local `main`** — checkout `main` first, then create the branch. Do not use `origin/main` as the branch point.
- Do not merge without user approval.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.

## Definition of Done

- Feature implemented as planned
- All checks pass (format, lint, type check, test — see Verification)
- Core logic tested, no regressions
- All Reviewer required fixes addressed
- **All new/modified files staged and committed** — run `git status` and confirm a clean working tree before declaring any task, bug, or feature complete. Stage new files immediately after creating them; never stage build artifacts, generated output, or `.gitignore`d files.

## Backlog Management

`todo/todo.md` is the source of truth. States: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` decision needed · `[>]` deferred.

- Read before starting work; prefer Current Focus tasks
- Do not start `[?]` or `[>]` tasks without instruction
- Update state as work progresses; do not delete tasks; do not exceed task scope
