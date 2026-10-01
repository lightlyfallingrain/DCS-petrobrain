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
- **Probe store** (`probe_store/`): fine elevation and `surface_type` accumulated chunk by chunk
  via `build.pipeline.add_probe_chunk`, plus a tri-state coverage record (`unqueried` /
  `queried_with_data` / `queried_void`) per `(kind, chunk_ix, chunk_iz)`. Chunks are 5,000 m
  squares anchored at the DCS x/z origin (`store.chunks`), independent of any region's own
  boundary — the same probe store outlives a region being redefined.
  **Ridge/valley terrain features left this list on `feature/landform-geomorphons`
  (2026-10-01/02)**: geomorphons classification needs a whole SRTM tile plus a multi-kilometre
  margin as its processing window (native ~90 m resolution, ~1.8 km margin at default
  settings) — a 5 km probe chunk cannot supply that context, so there is no chunk-scoped
  equivalent of the old watershed-era `ingest_terrain_chunk`. `add_probe_chunk`'s grid/
  `surface_type` chunk ingestion is unaffected; its `"ridge"`/`"valley"` coverage now stays
  `UNQUERIED` forever, and `ProbeChunkReport.terrain_stats`/`terrain_skipped` are kept for shape
  compatibility but always come back `None`/`True`. Ridge/valley features are instead produced
  theatre- or region-wide, per SRTM tile, by `build.ingest_terrain.ingest_terrain` and stored on
  the **base** store, not the probe store — see `world-model/ROADMAP.md`'s `WM-B6` entry.

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
`probe_spacing_m`, and the base store's `SCHEMA_VERSION` at the time it was created. This is
checked on **both** paths that open a probe store, not just one:

- **Write path**: every subsequent `probe_store.writer.open_probe_store` call (i.e. every
  `build.pipeline.add_probe_chunk`) re-checks all four against what's being requested and raises
  `ValueError` on any mismatch. See that function's docstring and
  `tests/test_probe_store.py`'s `test_open_probe_store_raises_on_*` tests.
- **Read path**: `query.describe.describe_position`'s `ATTACH` never goes through
  `open_probe_store` — it attaches the file directly — so it has its own check,
  `probe_store.schema.check_probe_paired_with_base`, called right after `ATTACH` alongside
  `check_probe_schema_version`. It compares the attached probe store's identity meta against the
  `theatre` being queried and the live base connection's own `schema_version`. A mismatch on
  either check is treated identically: `DETACH` and fall back to base-only, the same
  degrade-to-absent behaviour as a missing probe store file — never a crash, and never a silent
  cross-theatre or stale-lattice answer. See `tests/test_describe_position.py`'s
  `test_describe_position_probe_store_wrong_theatre_falls_back_to_base` and its two siblings
  (chunk-lattice mismatch, stale base schema version).

Both checks exist because they close different halves of the same risk: writing with the wrong
identity would corrupt the probe store's own meta, while reading with an unchecked identity
would silently answer from the wrong store entirely — a base store for one theatre queried
against a probe store built for another, matching `PROBE_SCHEMA_VERSION` and all, with no error
and no visible signal. This was found in review and is exactly the "opening a mismatched pair
must fail loudly" risk the plan's "Risks & Unknowns" names as the main new risk the two-store
split introduces.

## Performance

`tools/measure_m8_probe_chunk_perf.py` times one full 2,601-point chunk write and 100
`describe_position` calls with the probe store attached, against a small locally generated
store (never a real `syria-full` build — see the plan's Implementation Plan step 5 and
`M7_RUN_INSTRUCTIONS.md`'s precedent for why a real full-theatre run stays a user-run job). A
representative local run (pre-`landform-geomorphons`, when `add_probe_chunk` still did
chunk-scoped ridge/valley classification): ~23 ms for one `add_probe_chunk` call (probe ingest +
grid upsert + chunk-scoped ridge/valley classification), ~0.4 ms mean for a probe-attached
`describe_position` call — both far inside the ~72 s a Mi-24 at 250 km/h takes to cross one
5 km chunk. Since `feature/landform-geomorphons` removed chunk-scoped terrain extraction (see
"What lives where" above), `add_probe_chunk`'s cost is now just the grid/`surface_type`
ingest + upsert; the figure above is kept as a pre-change baseline rather than re-measured, since
nothing in this doc currently depends on an exact updated number.
