# M8 — the probe store

Per `plans/m8-incremental-store/plan.md`. Short by design — the plan itself carries the full
rationale; this doc is the "two-file model, lifecycle, backup/sync" deliverable the plan calls
for.

## Two files, not one

Every region now has up to two `.sqlite` files under `data/world-model/`:

| File | Contract | Rebuildable? |
|---|---|---|
| `<region>.sqlite` (base) | `build.pipeline.build_region` — always **delete and recreate** from `data/raw/` | Yes, from raw DCS/OSM/SRTM sources |
| `<region>-probe.sqlite` (probe) | `probe_store.writer.open_probe_store` — **created once, accumulates** across `add_probe_chunk` calls, never deleted by this codebase | **No** — its source is a live DCS mission that no longer exists once flown |

The probe store is the more precious of the two files. A base store rebuild (schema bump, DCS
update, roadnet fix) is a routine ~450 s Windows-box job; losing a probe store is losing
accumulated flight time with no way to regenerate it. If you back up or sync anything from
`data/world-model/` between machines, back up the `-probe.sqlite` files first — the base
`.sqlite` files are disposable by comparison. `data/world-model-backups/` is already gitignored
and exists for this.

## What lives where

- **Base store** (`store/`): roads, settlements, airfields, beacons, navaids, whatever
  whole-theatre elevation/`surface_type` grid a build supplied (SRTM or a stored DCS probe run)
  — everything M1–M7 built. Untouched by M8.
- **Probe store** (`probe_store/`): fine elevation, `surface_type`, and ridge/valley features
  accumulated chunk by chunk via `build.pipeline.add_probe_chunk`, plus a tri-state coverage
  record (`unqueried` / `queried_with_data` / `queried_void`) per `(kind, chunk_ix, chunk_iz)`.
  Chunks are 5,000 m squares anchored at the DCS x/z origin (`store.chunks`), independent of any
  region's own boundary — the same probe store outlives a region being redefined.

## Reading both at once

`query.describe.describe_position` takes an optional `probe_db_path`. When given and the file
exists, it `ATTACH`es the probe store onto the base connection for the duration of the call and
tries the probe store's `elevation`/`surface_type` grids first, falling back to the base store's
own grid wherever the probe store has no data for that exact cell. `elevation.source` /
`surface_type.provenance` report `"probe"` when the probe store answered, so a caller can always
tell which store produced a value; the new `coverage` field reports that position's chunk
coverage status, or `"no_probe_store"` when `probe_db_path` is omitted or the file doesn't exist.
Passing no `probe_db_path` reproduces pre-M8 behaviour exactly.

## Writing a chunk

`build.pipeline.add_probe_chunk(base_db_path, probe_output_path, chunk_ix, chunk_iz)` is the one
entry point. It opens the base store **read-only** (only to confirm its schema version and read
its `theatre`, for the probe store's own drift-detection meta) and writes only to
`<region>-probe.sqlite`; `build_region` and the base store are never touched. There is
deliberately no CLI wrapper yet — the live DCS-mission → chunk-probe-output channel this would
consume is a Petrobrain Runtime concern not yet built (see root `CLAUDE.md`'s current-priority
note and the plan's "Risks & Unknowns": *"The probe store has no real data until a Runtime
milestone exists"*). Until then, `add_probe_chunk` is exercised against synthetic fixture probe
output files, same as the rest of this pipeline's build-time code.

## Drift protection

A probe store records its own identity in `meta` at creation: `theatre`, `chunk_size_m`,
`probe_spacing_m`, and the base store's `SCHEMA_VERSION` at the time it was created. Every
subsequent `open_probe_store` call re-checks all four against what's being requested and raises
`ValueError` on any mismatch — pairing a probe store with a base store rebuilt at a different
schema version, or a different chunk lattice, fails loudly rather than silently mis-placing
chunks. See `probe_store.writer.open_probe_store`'s docstring and
`tests/test_probe_store.py`'s drift tests.

## Performance

`tools/measure_m8_probe_chunk_perf.py` times one full 2,601-point chunk write and 100
`describe_position` calls with the probe store attached, against a small locally generated
store (never a real `syria-full` build — see the plan's Implementation Plan step 5 and
`M7_RUN_INSTRUCTIONS.md`'s precedent for why a real full-theatre run stays a user-run job). A
representative local run: ~23 ms for one `add_probe_chunk` call (probe ingest + grid upsert +
chunk-scoped ridge/valley classification), ~0.4 ms mean for a probe-attached
`describe_position` call — both far inside the ~72 s a Mi-24 at 250 km/h takes to cross one
5 km chunk.
