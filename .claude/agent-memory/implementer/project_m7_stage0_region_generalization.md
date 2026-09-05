---
name: m7-stage0-region-generalization
description: M7 Stage 0 results — RegionDefinition rectangular generalization surface area and full-theatre roadnet census numbers
metadata:
  type: project
---

M7 Stage 0 (2026-09-05) generalized `world-model/src/build/region.py`'s `RegionDefinition` from
a single square `half_extent_m` to independent `half_extent_x_m`/`half_extent_z_m`, and
registered a `syria-full` region (centre `(-38239.9, 35166.9)`, half-extents `(413672.3,
385608.0)` m) from the confirmed padded bbox in
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`.

**Why this matters for future field-generalization work**: the plan estimated this as "a small
dataclass change plus updating the two call sites that compute corners/envelope" — that
undercounted the real surface area. `half_extent_m` was read directly (no shared helper) in
`ingest_towns.py`, `ingest_beacons.py`, `ingest_osm.py`, `ingest_roadnet.py`, `pipeline.py`, and
the persisted `store.models.Region`/`schema.py`/`writer.py`/`reader.py` (a DB column, required
`SCHEMA_VERSION` bump 1->2 — safe since stores are always rebuilt from `data/raw/`, never
migrated live). Renaming/splitting a widely-read dataclass field in this codebase should be
expected to touch every direct reader, not just the "logical" call sites a plan names — check
with `grep -rn <field_name> world-model/src` before estimating scope. See
[[verify_full_suite_not_just_new_files]] for the related "ruff/mypy can surface pre-existing
drift you didn't touch" pattern — this is the sibling lesson for a deliberate rename instead.

**Full-theatre roadnet census** (`tools/census_m7_stage0_roadnet.py`, measurement-only, no
store build): against the real 2.25GB `Syria.routes`, `syria-full`'s padded bbox contains
**all 14,833 routes** (`routes_in_region == routes_found_whole_file`), only 2 flagged
`clipped`. `sync_loss_events` = 220 (~1.48%), identical to M5's Latakia-derived whole-file rate
— confirms this is a `.routes`-parser property, not a bbox artifact. Wall time 431.4s, in line
with M5's 446s baseline for the bare walk, despite materializing `StoredFeature` objects for
virtually the whole file this time (unlike Latakia's 20x20km clip which discarded almost
everything). Implication: Stage 1's "remove the bbox clip for full-theatre roadnet" will not
change road counts — the rectangular bbox already captures everything.

**DCS axis convention** (useful for any code touching `RegionDefinition`/`dcs_to_wgs84`): DCS
x maps predominantly to latitude (north), z to longitude (east) for Syria's tmerc projection —
confirmed empirically (`dcs_to_wgs84("Syria", 100000, 0)` moves lat far more than lon, and vice
versa for z). Don't assume x=east/z=north by variable-name intuition.
