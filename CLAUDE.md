@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `docs/PROCESS.md` for generic engineering heuristics/protocols (decision heuristics, implementation strategy, debugging protocol, dependency policy, autonomy, NOTES.md conventions) — not repeated here.

## Project

Petrobrain: make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems. Guiding principle: **code owns truth, models own interpretation and language** — Petrovich must never be omniscient; his knowledge is bounded by what he could actually perceive.

**Scope: single-player only.** Everything multiplayer (group/coalition scoping, server hosting, other clients) is out of scope until the user says otherwise — don't plan for it, list it as an open question, or add code paths for it. (User direction, 2026-09-13.)

Three-layer architecture, each a separate component with explicit interfaces:

1. **DCS World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads, settlements, terrain, ridges/valleys), built offline from DCS-derived data + OSM/DEM augmentation. DCS geometry is always authoritative; external GIS augments, never overrides.
2. **Mission Interpreter** — understands one specific mission (`.miz` + briefing + world model + player intent) using a capable model, offline/pre-mission. Produces a structured "Mission Understanding," not prose. Must filter out mission-author-only knowledge (hidden triggers, scripted ambushes) before it reaches the crew layer.
3. **Petrobrain Runtime** — low-latency runtime crew cognition (perception, episodic/working memory, attention, dialogue) using a small/fast local model. Memory is explicit application state, never LLM chat history.

Full rationale: `docs/concept/PETROBRAIN_SYSTEM.md`. Per-layer draft designs (status: draft/provisional, revise as earlier layers mature): `docs/concept/WORLD_MODEL_BUILDER.md`, `docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Current priority

Root `ROADMAP.md` is the entry point for what's done and what's next: it gives the cross-subproject
status and links to each subproject's own `ROADMAP.md` (`world-model/ROADMAP.md`,
`aircraft-layer/ROADMAP.md`, `body-layer/ROADMAP.md`), which is that subproject's source of truth
for milestone status, decisions, and backlog — read those, don't infer status from this file.
`todo/todo.md` no longer duplicates milestone narrative; it only holds items not yet assigned to
one subproject's roadmap (cross-cutting backlog, session-scoped notes) and User priority tasks.
(Deliberately not restated here: two copies of the same fact drift out of sync as milestones
complete — see the roadmap files' own "Keeping this current" note for how that's enforced at merge
time.)

## Subprojects

Each major component under this repo may carry its own `<subproject>/CLAUDE.md` with stack/testing/structure specifics that augment (and, where stated, override) this file — Claude Code loads nested `CLAUDE.md` files automatically when working inside that directory. Currently:

**Module independence**: each subproject should be able to run on its own, with its own venv/dependencies. **body-layer ↔ world-model is the sole exception** — body-layer imports world-model's `query`/`coordinates` packages in-process (not over HTTP), a deliberate coupling because the two are treated as a pair, at least for now (see `plans/body-layer/plan.md` "Seams" and `body-layer/CLAUDE.md` "Tech stack"). Do not introduce a similar in-process cross-subproject import elsewhere without the same explicit justification — the default is HTTP/JSON across a subproject boundary (as aircraft-layer ↔ body-layer already does), not a shared import.
- `world-model/CLAUDE.md` (see also `world-model/docs/CONVENTIONS.md` for its working rules: DCS reconnaissance, provenance/confidence, cross-machine workflow, read-only DCS access).
- `aircraft-layer/CLAUDE.md` — live DCS I/O pipeline (Export.lua → Windows collector → LAN API). See also `aircraft-layer/WORKFLOW.md` for the cross-machine deploy/run workflow.
- `body-layer/CLAUDE.md` — Petrovich's belief-state process (contacts, attention, perception ingestion, the brain-facing API). BL-x milestone status: see `todo/todo.md` "Current Focus", not this line — `plans/body-layer/plan.md` has the full milestone series.

## Agents

8 agent roles live in `.claude/agents/`: the 7 template roles (architect, implementer, reviewer, debugger, performance-reviewer, security, dod — see `AGENTS.md` for role sequences) plus a project-specific `investigator`. All use `claude-sonnet-5`. **`dod` was raised from `claude-haiku-4-5-20251001` to sonnet on
2026-09-20** (user direction) after a run of errors in its acceptance cards — commands that had
never been executed, a card with no commands in it at all, and twice a fabricated example. The
cheap-final-gate saving was not worth a gate that reports work as verified when it was not; its own
role file now carries the run-it-before-you-write-it rule alongside the model change, since the
model was only half the problem. For architecturally complex or high-risk planning (coordinate system design, spatial schema, cross-theatre generalization), re-invoke architect with an explicit opus model override rather than relying on its sonnet default.

**Skip `performance-reviewer` and `security` for now** — this phase is an offline single-user local pipeline with no hot path and no untrusted-input surface yet. Do not insert them into the default role sequence from `AGENTS.md`. Only run either when the user explicitly asks for it.

**`investigator`** is this project's recon role, needed because much of the World Model Builder depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability). It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain: **Architect invokes it proactively whenever a plan would otherwise depend on an unverified DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only role. It writes dated findings to the `research/` directory of whichever module the finding is about (e.g. `world-model/research/`, `aircraft-layer/research/`), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

## Session Start

1. Read root `ROADMAP.md` for the cross-subproject picture, then the `ROADMAP.md` of whichever
   subproject looks most active (its Status table row is the pointer).
2. Read `todo/todo.md` for any User priority tasks and cross-cutting/unscoped backlog items.
3. Identify the next actionable milestone (first non-done, non-deferred/blocked item in the
   relevant subproject's roadmap).
4. Show that milestone and its subitems to the user.
5. Ask what they want to work on.

## Milestone Completion

Before marking a milestone done in a subproject's `ROADMAP.md` (`world-model/ROADMAP.md`,
`aircraft-layer/ROADMAP.md`, `body-layer/ROADMAP.md`), answer one question in the DoD report or the
roadmap update itself: does this milestone's completion change what the next milestone should be,
or invalidate an assumption downstream milestones rely on? One line is enough — this is the
project's inspect-and-adapt checkpoint, tied to milestone boundaries rather than a calendar.

## Knowledge graph

A queryable graph over the current-state design documentation lives in `graphify-out/` (gitignored,
built from the `graphify-corpus/` mirror). **Query it before concluding something is undocumented** —
this project's recurring failure is not missing documentation but failing to find documentation that
already exists, and occasionally finding a superseded version instead.

```sh
.claude/scripts/gq.sh "<question>"   # query, then list the sources to read
graphify path "<node A>" "<node B>"  # shortest path between two concepts
graphify explain "<node>"            # plain-language explanation
```

**Use `gq.sh`, not `graphify query` directly — a PreToolUse hook enforces this.** The graph says *where* to look; it does not say what
the text says. Edge annotations quote fragments, and a fragment can lose its tense — the first build
cited "a standing no-omniscience violation" from a passage whose next sentence records the fix. The
wrapper ends every answer with the source files already assembled, so reading them is one step
rather than a decision, and re-renders annotations as `fragment@path` so they stop reading as
claims. That is the mechanism; the rule on its own was forgotten within the hour it was written.

Install the hooks once per clone: `.claude/scripts/install-git-hooks.sh`. They keep the graph's
structural spine current per commit (AST over changed `.py`, ~1.5s, captures docstrings) and record
that a semantic rebuild is owed when docs change. **The rebuild order at merge is load-bearing —
documents first, graph second, merge third** — because a graph built from stale documents launders
the staleness rather than merely lagging it. Rebuild after a merge with `/graph-refresh`. Full reasoning: `docs/PROCESS.md`, "Keeping the
knowledge graph honest".

## Verification

Run the active subproject's format/lint/type/test commands after every code change and always before a commit — see that subproject's own `CLAUDE.md` "Commands" section for the current list (`world-model/CLAUDE.md`, `aircraft-layer/CLAUDE.md`, or `body-layer/CLAUDE.md`; each has its own equally-canonical list, ruff format/check + mypy --strict + pytest in each case). A change touching more than one subproject needs each touched subproject's own commands run, not just one. This is the same sequence `.claude/scripts/commit-quality-gate.sh` enforces mechanically per-subproject at commit time — stating it here prompts self-verification earlier, during implementation, instead of only at commit time.

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create and checkout a feature branch before starting any implementation task.** Name the branch after the feature using kebab-case (e.g., `feature/hyg-data-pipeline`, `fix/floating-origin-precision`). Never implement directly on `main`. **Always branch from local `main`** — checkout `main` first, then create the branch. Do not use `origin/main` as the branch point.
- Do not merge without user approval.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.
- **Non-code, cross-cutting updates that aren't part of the current milestone** (skill/config edits, backlog notes, cross-milestone bookkeeping) belong in a disposable `git worktree` on `main`, not in the active feature branch's working directory — see `.claude/skills/merge.md` for the worktree pattern. This avoids two problems at once: bundling unrelated history into a feature branch's commits, and racing a background Architect/Implementer/Reviewer/DoD agent that may still be working in that same checkout (those agents run without worktree isolation by default).

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
