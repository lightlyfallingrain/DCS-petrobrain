---
name: project_m5_roads_source_reversal
description: M5's road layer moved from live-mission land.* probing to direct parsing of DCS's static .rn4/.routes terrain files; what that changed in the plan and what stayed open
metadata:
  type: project
---

On 2026-09-04 the investigator's byte-decode of DCS's `roads/<Terrain>.rn4` +
`<Terrain>.routes` (`landscape4::` binary containers) reversed M5's road-layer design:
**whole-theatre road centerline geometry is extractable from static files, with zero
live-mission dependency.** Plan revised: `plans/m5-first-persistent-model/plan.md`,
"Revision 2026-09-04".

**Why it mattered structurally, beyond the data source:** roads moved from the
*probe* stage to the *offline* stage. Stage 1 now delivers four of M5's five layers
with no DCS round-trip at all; the live probe shrinks to elevation + surface type,
i.e. M4's already-proven mechanism plus one call. The biggest single risk in M5
(three never-called `land.*` road functions, chunked timer probing, ED's documented
`'rails'`/`'railroads'` inconsistency) was deleted rather than mitigated.

**The three judgment calls made, so they are not re-litigated:**
1. **Road *type* is deferred, not faked.** `.rn4` column 6 is a confirmed string-table
   type index, but the topology-row→geometry-block linkage is unconfirmed, so type and
   geometry are each extractable yet not provably joinable. M5 ships `subtype=null`
   rather than guessing a join. Full graph connectivity is M6/pathfinding scope.
2. **OSM roads kept as a separate comparison layer, not fused as an attribute source.**
   Attaching OSM names/classes onto DCS centerlines needs a proximity heuristic, and
   OSM's ~1.3 km positional error makes that heuristic capable of inventing facts —
   the exact failure class this project cannot detect after the fact. Keeping both
   layers side by side is simpler, needs no new code, and yields a real measurement:
   DCS-vs-OSM road displacement is the M1 terrain-art residual observed on a linear
   feature.
3. **Airfield taxiway/runway `.rn4` geometry deferred to M6+** despite Latakia being an
   airbase — it is outside M5's agreed five layers, and the airfield walker is the
   least-mature part of the finding (67% file coverage, block-separator logic not
   reverse-engineered).

**Two things worth reusing elsewhere:**
- **Scan-forward resync is a legitimate parser design, not a hack**, when a container's
  variable-length trailer is undecoded: search for the next `[count][plausible typed
  payload]` signature and validate. Validated across 15 consecutive routes. Requires a
  cheap pre-filter (first/mid/last element) before full unpack or it is unusably slow.
- **Cross-subsystem validation beats self-consistency.** The live probe's
  `land.getSurfaceType` `ROAD` enum is an *independent* DCS subsystem, so grid cells
  reporting `ROAD` near an extracted centerline confirm the parser decoded real roads.
  This is the roadnet layer's control-point-equivalent, and it costs nothing because
  the probe runs anyway. Prefer this shape of check over eyeballing.

**How to apply:** when a future milestone is about to depend on a live-mission probe,
check first whether the terrain module ships the same data statically — see
[[project_dcs_offline_sources]]. Two of M5's five layers turned out to be static files
after being planned as probes. Storage, region and grid decisions were untouched by
this reversal; see [[project_m5_storage_decision]] and [[project_m5_region_selection]].
