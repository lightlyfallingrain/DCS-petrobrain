# M7 full-theatre build — run instructions

Per `plans/m7-full-theatre-pipeline/plan.md`'s "Execution boundary": nobody but the user
builds the real full-theatre `syria-full.sqlite`. This doc is the required deliverable for
that boundary — the implementer/reviewer/DoD verify the pipeline code against small fixtures
only (see `tests/test_pipeline_build_region.py`, `tests/test_build_validate.py`); the real
build, its real feature counts, wall time, and file size are the user's own result.

This doc covers **Stage 1 only** (DCS-native vector layers: roads, towns, beacons — no OSM,
no elevation). Stage 2's SRTM/elevation-probe run instructions are a separate follow-up once
Stage 2 lands.

## 1. Check the raw files are staged

Stage 1 needs exactly the same three raw files M5 already used for `latakia-20km` — they are
**whole-theatre files already, not region-clipped** (M5 found this incidentally: `.routes` is
walked in full regardless of region bbox, and `towns.lua`/`beacons.lua` are parsed in full
before being clipped). If you already built `latakia-20km`, you very likely already have these
staged and **no new Windows/WSL round-trip is needed for Stage 1**:

```sh
ls world-model/data/raw/dcs/syria/map/towns.lua
ls world-model/data/raw/dcs/syria/map/beacons.lua
ls world-model/data/raw/dcs/syria/roads/Syria.routes
```

If any are missing, stage them the same way M5 did (read-only copy from the DCS installation's
`Mods/terrains/Syria/...`, via the `wsl-probe-sync` workflow in `world-model/WORKFLOW.md` if
extracting fresh from the Windows machine, or a direct copy if you already have them).

**No OSM cache is needed or used** — M7 drops OSM from scope entirely (see the plan's
clarification 2). Do not pass `--osm-cache` when building `syria-full`.

## 2. Run the build

From `world-model/`, with the venv active:

```sh
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes
```

This writes `data/world-model/syria-full.sqlite` (gitignored, like every other built store).
Expect the `.routes` walk to take roughly the same wall time Stage 0's census measured
(~430 s) — it is the same full-file walk, just now also constructing and inserting
`StoredFeature` rows instead of just counting them, and this time also parsing/inserting the
whole (unclipped) `towns.lua`/`beacons.lua` gazetteer.

The build prints a per-`kind` feature count summary and skip notices for the layers Stage 1
doesn't populate (`osm: skipped`, `probe: skipped`) — those are expected, not failures; M7
Stage 2 fills in elevation/`surface_type` later, and OSM is out of scope for the whole
milestone.

## 3. Validate the build

From `world-model/`, with the venv active:

```sh
.venv/bin/python tools/validate_m7_stage1.py
```

This checks the freshly-built `data/world-model/syria-full.sqlite` against:

- **Road count sanity**: the `road`-kind feature count should land within 5% of Stage 0's real
  full-theatre census (14,833 routes — see
  `world-model/research/2026-09-05-m7-stage0-roadnet-census.md`). A count far outside that band
  means something changed between Stage 0's measurement-only walk and Stage 1's real build (a
  bug, not an expected variance) and is worth investigating before moving on.
- **Coordinate control points**: `tests/control_points.py`'s four scattered points (Damascus,
  Latakia, Beirut, Aleppo) transform to within their published real-world ARP's expected
  residual — this doesn't depend on the store's contents (see
  `tests/test_describe_position.py`'s control-point tests, which already pin this in CI), but
  re-running it here confirms the same theatre/projection is in play for the real build.
- **Spot checks**: `describe_position` at each of those same four points reports whether a
  nearest road/settlement was found and at what distance — a human-scannable sanity check, not
  an exact-value assertion (Stage 1 has no independent ground truth for "the nearest road to
  this specific point"). If every point comes back with no nearest road at all, something is
  wrong with the roadnet layer; if some do and some don't (e.g. a point that's actually far from
  any real road), that's expected, not a failure.

The script prints a JSON report to stdout. There is no automatic pass/fail exit code beyond the
"store doesn't exist yet" case — read the report and use judgement, the same way M5's Stage 4
validation note did.

## 4. Record the result

Once you've run the build and the validation script, note the real numbers (feature counts,
wall time, file size, validation output) — either directly in a new dated
`world-model/research/` note (mirroring M5/M7 Stage 0's convention) or by reporting them back
so they can be written up. This is the actual Definition-of-Done evidence for M7 Stage 1 — an
agent-produced or agent-reported full-theatre store/count does not satisfy it, per the plan's
"Execution boundary".
