> **Status: REJECTED** — see `body-layer/ROADMAP/BL-W38.md`. Rescued onto `main` 2026-10-26 from the
> unmerged `feature/omniscient-mission-memory` branch (deleted), because that entry cites this plan.

### Goal
Decide where (and whether) a persistent, diffed omniscient world-object store belongs upstream of body-layer's perception filtering — per `todo/todo.md`'s Deferred entry "Persistent omniscient mission-memory store, upstream of perception filtering" (2026-09-09).

### Investigation Result (resolved before finalizing this plan)

The whole value proposition — "diff instead of full re-filter" — depends on whether `LoGetWorldObjects`'s per-object key is a stable identity across polls. This was already flagged unconfirmed in `aircraft-layer/src/schema/world_objects.py`'s docstring, so per architect process step 2 the `investigator` agent was invoked before finalizing anything. Findings written to `aircraft-layer/research/2026-09-09-worldobjects-object-id-stability.md` (staged):

- **Moderate-high confidence, not live-confirmed:** ED's own original export-API text calls the key an "object identificator," and `LoGetObjectById(id)` only makes sense if it stays valid — so it is very unlikely to be a bare Lua `pairs()`-iteration artifact as the schema docstring feared.
- **Real, documented risk:** two distinct DCS id concepts exist (`Unit.getObjectID()` "runtime object Id" vs. `Group/Unit.getID()` "unique mission id") and no source pins which one `LoGetWorldObjects` returns. MIST (a mature, widely-deployed DCS scripting framework) does *not* trust the engine's id across a unit's death — it keeps its own name-indexed lookup and explicit dead-id-collision handling. Best inference: **id is likely stable within one continuous object lifetime, but a kill/AI-regeneration boundary likely mints a new id for what a human would call "the same" unit/slot.**
- **Still open, needs a live sortie before implementation starts:** a two-poll (or longer) continuity check with no deaths, plus an explicit kill→respawn test, reusing the flag-gated debug-log pattern from `aircraft-layer/dcs-export/Export.probe-pb15.lua`.

This is good enough to size the design (below) but not good enough to build against yet — the live sortie is a precondition of implementation, not of planning.

### Placement Validated: aircraft-layer, not body-layer

Confirming the todo.md hypothesis against actual code and CLAUDE.md's invariants:

- `aircraft-layer/src/collector/cache.py` already holds three parallel "most-recent-state" caches (`TelemetryCache`, `WorldObjectsCache`, `PetrovichIndicationCache`), fed by the same connection and read by `aircraft-layer/src/api/server.py`'s `/*/latest` endpoints. A diffed/historical object store is a natural fourth member of that family — same process, same ownership, no new coupling.
- Root CLAUDE.md: "code owns truth, models own interpretation" and body-layer's own CLAUDE.md define `body-layer/src/belief/` as strictly non-omniscient by contract. A ground-truth history store must not live there — confirmed, this rules out body-layer as a home regardless of convenience.
- Root CLAUDE.md "Module independence": aircraft-layer↔body-layer is HTTP/JSON only; body-layer↔world-model in-process import is the sole deliberate exception. Building the store in aircraft-layer and exposing it over a richer `/world_objects/*` endpoint preserves this boundary exactly — body-layer's `naked_eye_source.py`/`hybrid_source.py` keep polling HTTP, unchanged, just against richer upstream data. No better seam exists: world-model is not in this data's path at all (no coordinate/OSM/DEM reconciliation involved), and inventing a fourth subproject purely to hold this store would violate "don't introduce new abstractions without removing a clear duplication."

**Conclusion: todo.md's hypothesis holds.** If/when built, it is aircraft-layer's `collector/` package, alongside `cache.py`, surfaced via `api/server.py`.

### Is There a Concrete Downstream Need Yet?

Checked `plans/body-layer/plan.md`'s milestone series (BL-2 through BL-7) and `todo/todo.md`'s Current Focus:

- BL-3 (world enrichment), BL-4 (attention/events), BL-5 (`get_contact_history` et al.), BL-6 (mission phase/relevance), BL-7 — none call for ground-truth history or continuity. BL-5's `get_contact_history` is explicitly belief-side, backed by `ContactStore`, already non-omniscient and already built.
- BL-2.6 (current work, classification refinement) is also belief-side — it's about `Contact.last_class_raw` oscillation, not omniscient object tracking.
- No perception source currently re-filters at a volume where per-poll full-refilter cost has been observed as a bottleneck (no profiling data, no `NAKED_EYE_MAX_NEW_PER_POLL`-style ceiling being hit).

**Honest answer: no concrete consumer exists yet.** This is infrastructure ahead of need. Per root CLAUDE.md/AGENTS.md bias against building for hypothetical requirements, and per the M9-deferral precedent the user already set for exactly this kind of "not yet, revisit when something needs it" call:

**Recommendation: do not implement now. Keep this plan as the design-in-waiting; revisit when the trigger below fires.**

### Concrete Revival Trigger

Revisit this milestone when *either*:
1. A live sortie (independent of this plan — can be done opportunistically) confirms or refutes id stability across the kill/respawn boundary, resolving the remaining unknown, **and** a concrete consumer exists; or
2. Any of the following becomes true and is observed, not hypothesized:
   - A perception source's per-poll full-refilter cost is profiled and shown to matter (e.g. a mission with dozens+ of world objects causing visible poll-loop latency).
   - A body-layer feature needs ground-truth continuity Petrovich could not have (e.g. "did this specific object move/die since last exposure" as an internal bookkeeping signal, not a crew-facing fact) — note this would need its own invariant check, since even internal bookkeeping must not leak omniscient facts into belief output.

### If/When Built — Design Notes (for the future Architect pass that revives this)

Recorded now so the revival pass doesn't have to re-derive it:

- **New store type**, not a repurposed `WorldObjectsCache`: e.g. `ObjectHistoryStore` in `collector/`, keyed by the (still only likely-stable) object id, holding last-seen state per id plus a small event log (`appeared`/`updated`/`disappeared`).
- **Id-disappearance must be modeled as ambiguous, not as deletion.** Per the investigation finding: when an id vanishes and a new id appears at the same/nearby position on the next poll, the store must emit a `possible-replacement` event, not silently treat it as one continuous object or as two unrelated ones. This is cheap to build in from the start and expensive to retrofit once consumers exist.
- **Lifetime: in-memory, per-process, no persistence across restart.** Unlike world-model's M8 probe-store precedent (static geographic data with an explicit accumulate-across-sessions requirement), this is live per-mission dynamic state — the aircraft-layer collector process's natural lifetime already matches a mission's, and nothing in the current milestone series needs post-mission replay. Do not add SQLite/disk persistence unless a future need explicitly requires surviving a process restart mid-mission.
- **API shape:** extend rather than break — keep `/world_objects/latest` as-is (cheapest possible consumer path, several call sites already depend on its exact shape) and add a new endpoint (e.g. `/world_objects/history` or `/world_objects/changes`) rather than overloading `/latest`'s contract.
- **Required precondition:** the live sortie above, before any implementation commit.

### Risks & Unknowns
- Object-id stability across the kill/respawn boundary remains genuinely unconfirmed (moderate-high confidence only) — flagged above as the live-sortie precondition.
- If the live sortie later shows ids are *not* stable even within a continuous lifetime (worse than the current best guess), the entire "cheap diff" premise collapses and this becomes a position/attribute-based re-association problem instead — a materially larger design, not a small extension of `cache.py`. Re-plan from scratch if that's what the sortie finds; don't assume the design notes above still apply.
- This plan intentionally produces no code and no branch changes beyond itself — normal for a "defer, documented" outcome.

### Decisions Requiring User Input
- **Performance-reviewer exemption scope.** Root CLAUDE.md currently exempts `performance-reviewer` project-wide as "offline single-user local pipeline, no hot path." Aircraft-layer's live 5-20 Hz poll loop (already handling `WorldObjectsSnapshot` per tick) is arguably closer to a hot path than anything reviewed so far, and this milestone (if revived) would add per-tick diff work to that loop. Flagging per your own instruction rather than unilaterally invoking performance-reviewer or amending the exemption — worth a decision now or at revival time, not decided here.
- **Confirm the "defer, no implementation" outcome itself.** This plan's central recommendation is *not to build anything yet*. If you disagree — e.g. you already have a concrete near-term consumer in mind that didn't surface in the BL-2..BL-7 milestone read above — say so and this plan gets re-scoped into an actual implementation plan instead of a design-in-waiting.
