# M7 Stage 0 — full-theatre roadnet census

Date: 2026-09-05
Status: findings recorded after generalizing `RegionDefinition` to rectangular half-extents,
registering `syria-full`, and running the real `.routes` walk over its full padded bbox via
`tools/census_m7_stage0_roadnet.py`. This is a measurement/census stage only, per
`plans/m7-full-theatre-pipeline/plan.md` Stage 0 and the plan's "Execution boundary" (no
`.sqlite` store was built).

## 1. Region

`syria-full`, registered in `build.region.REGIONS`, from the confirmed padded bbox in
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`:

- centre: x = -38,239.9, z = 35,166.9
- half-extents: `half_extent_x_m` = 413,672.3, `half_extent_z_m` = 385,608.0
- bbox: x in [-451,912.2, 375,432.4], z in [-350,441.1, 420,774.9]
- footprint: ~827.3 x 771.2 km (aspect ratio ~1.07)

## 2. Roadnet census

Ran `.venv/bin/python tools/census_m7_stage0_roadnet.py` against the real, locally-staged
`data/raw/dcs/syria/roads/Syria.routes` (2,251,462,776 bytes), reusing `build.ingest_roadnet`
unchanged with `syria-full`'s bbox:

| Metric | Value |
|---|---|
| `routes_found_whole_file` | 14,833 |
| `routes_in_region` | 14,833 |
| `routes_in_region_clipped` | 2 |
| `resync_events` | 14,833 |
| `sync_loss_events` | 220 (~1.48%) |
| `bytes_covered` | 2,249,111,022 |
| wall time | 431.4 s |

**Every route in the file falls inside `syria-full`'s padded bbox** (`routes_in_region ==
routes_found_whole_file` == 14,833) -- confirming the confirmed extent plus +30 km/side padding
is generous enough to contain the entire known roadnet with no coverage loss. Only **2 of
14,833 routes** are flagged `clipped` (a point of the route lies outside the bbox), meaning the
padding margin is comfortable rather than tight -- the vast majority of the roadnet sits well
inside the boundary, not hugging it.

`sync_loss_events` (220, ~1.48%) is identical to M5's previously-measured whole-file rate
(`world-model/research/2026-09-04-m5-roadnet-stage2.md`, 220/14,833) -- expected, since this is
a property of the `.routes` file itself (parser resync loss during the walk), not of the region
bbox being applied afterward.

> **CORRECTION 2026-09-21 — the citation above points at a file that does not exist.**
> `world-model/research/2026-09-04-m5-roadnet-stage2.md` has never existed; the only M5 roadnet
> notes are `2026-09-03-m5-roadnet-file-recon.md` and `2026-09-04-m5-roadnet-byte-decode.md`.
> **The 220/14,833 figures are real and the claim is correct** — they are recorded in
> `2026-09-04-m5-stage4-validation.md` (Correction table) and `2026-09-04-m5-stage5-perf.md`.
> Only the source pointer is wrong.
>
> Kept rather than silently repointed, because this is the failure mode a citation is supposed to
> prevent and instead performed: a filename reconstructed from the milestone's own naming pattern
> (`m5-roadnet-` + `stage2`) reads exactly like a real one, and nothing in the sentence signals
> that the source was recalled rather than opened. A reader following it finds nothing; a reader
> not following it is more convinced than they should be.

This is the same ~1.5% known, accepted gap the plan's "Deferred /
Out of Scope" section already tracks (the full-theatre resync audit is a separate follow-up
task, not part of M7).

Wall time (431.4 s) is consistent with M5 Stage 5's standalone-walk baseline (446 s) despite this
run also constructing and clipping full `StoredFeature` objects for essentially the entire file
(syria-full covers virtually the whole theatre, unlike Latakia's 20x20 km clip) -- no perf
regression from the rectangular bbox generalization.

## 3. Implication for Stage 1

Since `routes_in_region` already equals the whole-file total, Stage 1's planned "remove the bbox
clip for full-theatre ingest" has no observable effect on the roadnet layer specifically -- the
current rectangular bbox already captures every route. This does not change Stage 1's scope
(towns.lua/beacons.lua still benefit from being read in full rather than clipped), but is worth
noting so Stage 1 doesn't expect a road-count change purely from removing the clip.

## Reproducible test

```sh
cd world-model
.venv/bin/python tools/census_m7_stage0_roadnet.py
```

Not part of the pipeline -- a throwaway measurement script per the plan's Stage 0. Reads only;
writes no `.sqlite` file.
