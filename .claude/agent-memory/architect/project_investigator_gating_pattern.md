---
name: project_investigator_gating_pattern
description: Recurring pattern for this project — plans gate on a user-run WSL probe when DCS internals are genuinely unknown, not just unverified
metadata:
  type: project
---

This project (DCS World Model Builder) repeatedly hits a distinction worth keeping separate:

1. **Unverified-but-plausible claims** (M1's case: pydcs's tmerc parameters were a strong community-derived hypothesis) — architect can plan provisional implementation stages against the best current evidence, with a `confidence: Literal["provisional","confirmed"]` field, and a later stage closes the gap via a live probe.
2. **Genuinely unknown** (M2's case: RasterCharts tile format, `.sup5` purpose) — there is no fallback hypothesis to implement against provisionally. The plan must gate a hard Stage 0 on the user running a probe script before any parsing/implementation code is written, rather than guessing a format (e.g. assuming DDS) and rewriting later.

**Why:** Root CLAUDE.md forbids encoding unverified claims as fact; the project's cross-machine workflow (`world-model/WORKFLOW.md`) means the architect/investigator cannot run WSL probes directly — probes are written and staged, but require the user to deploy them via `win-mac-sync/run-wsl/` on the Windows machine.

**How to apply:** When planning a milestone that depends on DCS internals, always invoke investigator first (per root CLAUDE.md's Agents section). If investigator returns "confirmed" facts, plan normally. If it returns "unresolved gap, no prior art," write the plan with an explicit Stage 0 = user runs the already-prepared probe script, and make later stages branch on the probe's findings rather than picking one branch to implement now. See [[project_m2_rastercharts_plan]] for a concrete instance.
