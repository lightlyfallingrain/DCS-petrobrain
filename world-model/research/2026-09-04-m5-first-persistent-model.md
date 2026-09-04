# M5 — First persistent model: milestone summary

**Date:** 2026-09-04
**DCS version:** 2.9.29.27278 (per M0)
**Theatre / region:** Syria, `latakia-20km` (centre DCS x=44934.892 z=5685.076, half-extent
10,000 m, +3,000 m eastward offset from the Latakia ARP per Stage 0's census — see
`2026-09-04-m5-stage0-census.md`).

This is a synthesizing close-out note for the whole M5 milestone, per Stage 6 of
`plans/m5-first-persistent-model/checklist.md`. It does not repeat the six per-stage notes'
content — it summarizes what M5 delivered, the final live-store numbers, what stayed
out of scope, and the two real defects found and fixed along the way. Full detail, exact
numbers, and worked derivations live in the per-stage notes and in
`plans/m5-first-persistent-model/implementation.md` (the complete decision log); this note
links to them rather than duplicating them.

## What M5 set out to do

Per `world-model/ROADMAP.md`'s M5 entry: build a small persistent geographic DB (~20×20 km
test region) covering elevation, roads, settlements, water, and named places, and implement
`describe_position(...)` as the first real query surface over it — the point where the World
Model Builder stops being six independent M1-M4 diagnostics and becomes one theatre-scoped,
queryable store.

## What was built

- **Persistent store** (`src/store/`) — stdlib `sqlite3`, one file per region
  (`data/world-model/<theatre>.sqlite`), R\*Tree spatial index, geometry stored as JSON
  `[[x,z],...]` in DCS x/z metres (not WKB, not GeoPackage). QGIS access goes through a
  `tools/export_geojson.py` export rather than a native GeoPackage writer. Decision origin:
  Stage 0/1 of this milestone's planning (`plan.md` "Locked decisions"); the spatial-storage
  question itself was deferred here all the way from M3 (`2026-09-03-m3-osm-overlay.md`).
- **DCS-native roadnet parser** (`src/roadnet/`) — parses `Mods/terrains/Syria/roads/Syria.routes`
  directly (float64-triple polylines behind a `landscape4::`-prefixed binary container,
  scan-forward resync over the container rather than naive sequential trailer-parsing) instead
  of live-probing `land.getClosestPointOnRoads`/`findPathOnRoads`. Format decoded in
  `2026-09-03-m5-roadnet-file-recon.md` and `2026-09-04-m5-roadnet-byte-decode.md`; ingest and
  container implementation in Stage 2 of `implementation.md`.
- **Elevation / surface_type grid** (`src/probe/` + `dcs_data`/`store` ingest) — a 41×41,
  500 m-spaced live-DCS probe grid (1,681 points) over the region, `land.getHeight` +
  `getSurfaceType` per point, reached via an incremental ladder (100-200 → ~500 → 1,681 points)
  rather than jumped to directly. Built and validated in Stage 3
  (`2026-09-04-m5-stage3-smoke-rung.md`) and Stage 4.
- **`describe_position(theatre, x, z)` query contract** (`src/query/`) — the milestone's actual
  deliverable per the ROADMAP entry. JSON-serializable, every claim carries provenance and
  `position_uncertainty_m` side by side (never a collapsed value), DCS wins over OSM when both
  answer, absence is always an explicit `null` (never a guess). Full field list in
  `checklist.md`'s "Data contract" section; behavior validated point-by-point in Stage 4.
- **Towns/beacons ingest** (`src/dcs_data/`) — regex Lua parsers for `towns.lua` (a **list**, not
  a dict — 31 duplicate names, all real places at different coordinates) and `beacons.lua`
  (`{x, y, z}` where the middle value is elevation), sourced from
  `2026-09-03-m5-nodes-lua-probe.txt`. Runway/airfield points are derived from ILS/PRMG beacon
  pairs within one `airfield_group` (never cross-paired across systems), carrying generous,
  explicitly non-surveyed uncertainty (runway 300 m, airfield 500-1000 m) — beacon antennas are
  not runway thresholds and `positionGeo` is never used to validate anything (would be circular,
  per M1 Finding 2).

## Final live-store numbers

From the corrected, probe-inclusive rebuild of `data/world-model/latakia-20km.sqlite`
(`2026-09-04-m5-stage5-perf.md` Measurement 1-2; post-Stage-4-fix feature counts from the
Correction section of `implementation.md`):

| metric | value |
|---|---|
| feature counts | `airfield=1, named_place=108, navaid=8, road=3266 (3136 OSM + 130 DCS), runway=2, settlement=338, water=117` |
| roadnet stats | `routes_found_whole_file=14,833, routes_in_region=130, resync_events=14,833, sync_loss_events=220, bytes_covered=2,249,111,022 (99.90% of 2,251,462,776)` |
| probe grid coverage | `points_expected=1,681, points_received=1,681` (100%); `surface_type_counts={WATER: 412, LAND: 1236, ROAD: 29, RUNWAY: 4}` |
| `.sqlite` file size | 8,982,528 bytes (8.57 MB) |
| full rebuild wall time | 430.9 s (~7.2 min), dominated ~2 orders of magnitude by the `.routes` walk |
| `describe_position` latency (100 sampled points) | mean 89.0 ms, median 71.3 ms, p95 223.7 ms, p99 275.0 ms |
| `.routes` walk peak memory footprint | ~22.5 MB (flat, does not scale with the 2.25 GB input — streaming claim confirmed) |

DCS-vs-OSM road centerline displacement (in-bbox, 200-point sample): median 5.30 m, p90 47.0 m —
roughly two orders of magnitude tighter than M1's ~1.0-1.3 km *point-object* placement-error
figure, explained in Stage 4 Finding 2 as expected once the comparison is centerline-to-centerline
rather than point-to-point (two independent digitizations of the same road plausibly agree far
more closely than one hand-placed building's absolute position).

## What stayed out of scope (deferred to M6+)

- **`.rn4` graph decoding beyond type vocabulary.** Row→geometry join is unconfirmed; road
  type/subtype is `null` throughout M5 by design (a test pins `subtype is None`). `.routes`
  alone was sufficient for M5's roads deliverable.
- **Airfield taxiways/structures.** Only runway/airfield points derived from ILS/PRMG beacon
  pairs are in the store; no taxiway or building-footprint geometry.
- **SRTM tile fetch for Latakia.** No local SRTM `.hgt` tile is staged for this theatre/region
  (`data/raw/dem/` only has Gemerek's M4 tile) — `--srtm-tile` was left unset throughout M5,
  which degrades to an absent SRTM-delta stat rather than an error, per
  `build.pipeline.build_region`'s contract. Accepted M5 deferral, not a gap.
- **Per-route resync/plausibility audit across the whole theatre.** The denormalized-garbage fix
  (see below) closes the one failure mode actually observed, but does not prove every one of the
  remaining 14,833 whole-file routes is geometrically sound in every other way (e.g. a
  false-positive resync match that happens to decode into small-but-normal-magnitude,
  envelope-compliant values would still slip through). `implementation.md`'s Correction section
  recommends a systematic per-route smoothness/plausibility audit (abnormal point-to-point jumps,
  excessive exact-duplicate points) over the full whole-theatre walk as a future, not-M5-scoped
  task.
- **`build_world_model.py`'s `--probe-output` CLI ergonomics gap.** No registered default exists
  for `latakia-20km` (unlike `--towns`/`--beacons`/`--osm-cache`/`--routes`), so an
  under-specified rebuild silently produces a smaller store rather than erroring — flagged in
  Stage 5, not fixed (out of that stage's measurement-only scope). Left as an open M6+ backlog
  item: a registered default, or a loud warning when a rebuild would drop rows relative to the
  store it's about to overwrite.

## What we learned — two real defects found and fixed this milestone

**1. `pyproj.Transformer` rebuilt on every call (performance).** `src/coordinates/` was
constructing a fresh `Transformer` per coordinate-transform call — invisible at M1-M4's scale,
surfaced only once M5's OSM ingest ran at real scale (13,618 elements in the Stage 0 widened
Overpass fetch). Fixed with `functools.cache` on the Transformer-construction path. See agent
memory `project_pyproj_transformer_perf.md` for the pattern; not re-derived in a dedicated
research note since it was a straightforward perf fix caught and closed within Stage 1/2.

**2. Roadnet resync denormalized-float validation gap (correctness, real production defect).**
`roadnet/container.py`'s `_triple_plausible` validated `math.isfinite` plus wide magnitude bounds
but never rejected denormalized/subnormal float64 values (e.g. `1.36211130863e-312`) — finite,
near-zero, and therefore "plausible" by the old check despite never being a genuine DCS
coordinate. This let scan-forward resync accept false-positive garbage blocks as real routes. One
confirmed real instance (`id=3711`, `route:3311@464953201`) landed inside the live Latakia store,
where its garbage geometry caused `describe_position(0.0, 0.0)`'s `nearest_road` (DCS) to resolve
to a misleading, specific-looking **0.0 m** — not a crash, not a null, a plausible-wrong answer,
exactly the failure mode Stage 4's validation gate exists to catch. Root cause and fix are
recorded in full in `implementation.md`'s Stage 4 "Correction" section (later same-day Debugger
pass): `_triple_plausible` now rejects any coordinate component that is nonzero but has magnitude
below `1e-6`, matching a filter that already existed in the exploratory recon script
(`2026-09-04-m5-roadnet-byte-decode.md` Session 2) but had never made it into the production
validator. Post-fix, the whole-file route count dropped by 28 (of which only 1 fell inside the
Latakia bbox) — direct evidence the false-positive risk Stage 2 had flagged as open was real
across the full theatre file, not a one-off. Two regression tests pin the exact garbage literals
from this feature (`test_roadnet_container.py`, `test_roadnet_routes.py`).

Both defects share a pattern worth carrying into M6: **numbers that "look done" (row counts,
building successfully, plausible-looking query answers) are not sufficient evidence of
correctness** — both were only caught by inspecting real data/output directly rather than trusting
a pipeline's own summary or a passing-looking spot-check. Stage 4 and Stage 5's own notes make the
same point independently (the `--probe-output` grid-drop regression in Stage 5 was caught the same
way).

## Per-stage notes (not repeated above)

- `2026-09-03-m5-recon.md`, `2026-09-03-m5-roadnet-file-recon.md`,
  `2026-09-03-m5-terrain-file-formats.md`, `2026-09-04-m5-roadnet-byte-decode.md` — pre-Stage-0
  format/recon investigation behind the roadnet and terrain-file decisions.
- `2026-09-04-m5-stage0-census.md` — region selection, Overpass widened fetch, gate pass.
- `2026-09-04-m5-stage3-smoke-rung.md` — probe-grid incremental ladder, live DCS round-trip.
- `2026-09-04-m5-stage4-validation.md` — full correctness validation against the real store,
  including both findings above in original form plus the later same-day correction.
- `2026-09-04-m5-stage5-perf.md` — the numbers reproduced in the table above, with full
  methodology and the mmap/RSS-vs-footprint memory-metric explanation.
- `plans/m5-first-persistent-model/implementation.md` — complete stage-by-stage decision log,
  the authoritative source if any number or claim above needs more detail than this summary
  carries.

## Milestone verification (Stage 6 close-out)

- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (strict, run from `world-model/`): pass
- `pytest world-model/tests -q`: pass — see `plans/m5-first-persistent-model/implementation.md`
  for the exact count as of this close-out.
