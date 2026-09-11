---
name: project_mission_interpreter_planning
description: Mission Interpreter plan (2026-09-12) — open decisions, blocker, and design shape for the not-yet-built second Petrobrain layer.
metadata:
  type: project
---

Plan written 2026-09-12: `plans/mission-interpreter/plan.md`, subproject `mission-interpreter/`
(not yet implemented — plan only). Investigator resolved `.miz` internal structure first
(`mission-interpreter/research/2026-09-12-miz-file-structure.md`): briefing text is externalized
to `l10n/DEFAULT/dictionary` via `DictKey_...` ids, not inline in `mission`; author-only knowledge
has real structural markers (`Group.hidden`/`hiddenOnPlanner`/`hiddenOnMFD`,
`MovingGroup.lateActivation`); `triggers` (zone geometry) and `trigrules` (condition→action logic,
where scripted ambushes live) are separate top-level keys. Recommended parser: pydcs's `dcs.lua`
subpackage (hand-written recursive-descent, no Lua VM), not a hand-rolled regex parser.

**Why:** nothing existed for this layer before this session — no code, no prior `.miz` research
anywhere in the repo, and no sample `.miz` file reachable from the Mac dev machine or checked into
the repo. The whole `mission`-table schema is community-reverse-engineered (no official ED docs;
pydcs has a known open issue where a DCS patch broke its parsing assumptions) — treat as an
ongoing format-drift risk, not a one-time gap.

**How to apply:** Four decisions were surfaced to the user rather than resolved silently (see the
plan's "Decisions Requiring User Input"): (1) new dependency — vendor/depend on pydcs's `dcs.lua`
subpackage, LGPL-3.0; (2) world-model query transport for this subproject — in-process import
(body-layer's precedent) vs. a new HTTP wrapper, since CLAUDE.md's module-independence rule frames
body-layer↔world-model as "the sole exception" and doesn't obviously extend to an offline batch
consumer; (3) capable-model choice/hosting for the MI-4 synthesis stage (local Ollama vs. cloud) —
gates MI-4 only, not MI-0-MI-3; (4) player-intent input form, proposed as a typed console
prompt/response loop (BL-5a precedent) but flagged as reversible, not escalated. **Blocking
prerequisite for MI-0/MI-1**: a real `.miz` sample file does not exist anywhere in this repo —
needs one exported from the Windows DCS box (or hand-built in the Mission Editor) before parser
work can start; same access-gated class as `body-layer/ROADMAP.md`'s F10-menu backlog item, but
resolvable without a live DCS session, just one-time Mission Editor export access. See
[[project_module_independence_rule]] for the boundary precedent this plan's Decision 2 weighs
against.
