---
name: multi-theatre-afghanistan-plan
description: Multi-theatre support plan (Afghanistan first) — what's already generalized, the real gap found, and why Caucasus/Kola should be cheap.
metadata:
  type: project
---

Planned 2026-10-05 on `feature/multi-theatre-afghanistan` (`plans/multi-theatre-afghanistan/plan.md`),
built on the 2026-10-04 investigator recon (`world-model/research/2026-10-04-multi-theatre-
afghanistan-caucasus-recon.md`).

**The store/query layer needed zero changes** — `Region.theatre` is already stored and read back,
`describe_position(conn, theatre, x, z, ...)` already takes `theatre` as a caller argument, and
`RegionDefinition` already supports rectangular half-extents (added for Kola's elongation, see
`[[project_m8_plan_shape]]`-adjacent research `2026-09-05-m7-kola-square-vs-rectangle-stress-test.md`).
Everything that needed fixing was either (a) two Syria-hardcoded artifacts nobody had hit yet
(`EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT` exact-match guards, `pipeline.py`'s literal
`"Syria.routes"` provenance string) or (b) registry entries (`THEATRE_PROJECTIONS`, `REGIONS`).

**The real gap was on the runtime/consumer side, not the pipeline side.** Mission-interpreter
already extracts `mission["theatre"]` from a real `.miz` (confirmed against an actual sample) and
already threads it through to the `--emit-compact` artifact body-layer loads at startup for BL-7
(`mission_phase.py`'s `load_mission_understanding`) — but nothing used that value to pick which
world-model `.sqlite`/`--theatre` to query with. `body-layer/src/logger.py`'s `--theatre` and
`--world-model-db` were both separate, required, hand-typed flags, with **no mismatch guard**:
`describe_position` never cross-checks the caller-supplied `theatre` string against the store's own
built `Region.theatre` row before calling `dcs_to_wgs84(theatre, x, z)` — pointing the wrong
`--theatre` at the wrong store silently produces a plausible-looking, wrong lat/lon for every
contact, with nothing to catch it. The plan's Stage 5 closes both: derive theatre/db from the
mission-understanding artifact when explicit flags are omitted, and add a `store.reader.
load_only_region(conn)` check (already a same-tier import next to `open_world_model` — no new
coupling) that fails loudly on a theatre/store mismatch regardless of how theatre was resolved.

**`coord_probe.lua` (the M1 live-verification script) is theatre-agnostic as written** — no Syria-
specific code, directly reusable for Afghanistan/Caucasus/Kola's own live `coord.LOtoLL` checks,
just needs a mission built on the new terrain.

**Flagged to the user per this role's own standing instruction**: this plan is "cross-theatre
generalization," the exact example this role's header names as architecturally complex/high-risk
enough to warrant an opus override — flagged in the handback, plan was produced at sonnet default
depth per the dispatch's model choice, not re-invoked at opus.

**How to apply:** when Caucasus/Kola are planned next, Stages 1–5's shape should repeat almost
unchanged with each theatre's own numbers (dict entries, its own live-probe run, no new store/query/
body-layer code) — if a Caucasus or Kola plan finds itself touching `store/`, `query/describe.py`, or
body-layer's resolution logic again, that's a signal something about this plan's generalization
claim was wrong, not that those theatres are just "harder."
