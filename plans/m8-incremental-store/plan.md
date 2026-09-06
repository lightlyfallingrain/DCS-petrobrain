### Goal

Give the World Model Builder the ability to accumulate probe-tier data (fine elevation,
`surface_type`, ridge/valley) chunk-by-chunk into a **separate, persistent probe store** that
survives base-store rebuilds — plus a tri-state coverage model a later Petrobrain Runtime
milestone can drive — without touching M7's whole-theatre one-pass base build.

### Revision note (post-review)

The user reviewed the first draft and made four decisions; **this plan is now final** —
nothing below is pending user input.

1. **OSM/Geofabrik is split out of this milestone entirely.** The first draft was one
   milestone with two tracks. OSM is now **M9** (`plans/m9-osm-geofabrik/plan.md`), deferred
   and unscheduled, with its dependency question unresolved by design. M8 is probe-store work
   only.
2. **Two stores, not one store with a `grid.tier` column** — user-proposed against the first
   draft's in-file tier design, evaluated below, **adopted**. The decisive factor is lifecycle:
   probe data is not rebuildable from `data/raw/` and must not live in a file whose documented
   contract is delete-and-recreate.
3. **Chunk size 5,000 m, probe spacing 100 m — locked.** These were the recommended defaults;
   the user confirmed them. They remain module constants with CLI overrides, but the defaults
   are decided, not open.
4. **Base-store per-layer append is dropped from M8.** The first draft carried it as a
   severable final stage. It is removed from this plan entirely, keeping M8 tightly scoped to
   the probe store. `todo/todo.md`'s "Incremental per-layer pipeline builds" backlog item stays
   open and untouched for a later milestone — it is **not** folded in here.
5. **New probe-tier kinds must be addable without a schema migration** (added after the four
   decisions above). The raster and vector storage shapes were already generic-by-`kind`,
   mirroring the base store, and needed no change. One place *was* narrower than the
   requirement and is now fixed: **coverage is keyed `(kind, chunk_ix, chunk_iz)`**, not by
   chunk alone, and every write is scoped by `kind`. See "Extensibility" and the tri-state
   decision for why.

### Scope boundary

World Model Builder side only, verified against synthetic/fixture calls. Explicitly **not** in
M8: Petrobrain Runtime in any form (root `CLAUDE.md` still blocks it); the live DCS-mission →
store data channel (`PETROBRAIN_RUNTIME.md` names that as a separate open blocker); probe
throttling or look-ahead policy; any change to the base tier (roads/settlements/airfields/
beacons/navaids stay exactly as M7 built them); base-store per-layer append (see revision note
4).

---

## Storage architecture: two stores

**Decision: the probe tier lives in its own `.sqlite`** — `data/world-model/<region>.sqlite`
(base, unchanged) alongside `data/world-model/<region>-probe.sqlite` (new; e.g.
`syria-full-probe.sqlite`). The evaluation against the alternative in-file `grid.tier` design,
recorded here because it is the reasoning a future reader will want:

### 1. Lifecycle mismatch is the decisive argument

The base store's documented contract is *"always rebuilt from `data/raw/`, never patched in
place"* (`writer.open_for_build`, `schema.py`'s version note, and the concept doc's "keep raw
extracted data separate from derived data so the database can be rebuilt"). A schema bump, a
DCS update, or a roadnet fix means `rm` and a ~450 s rebuild.

Probe-tier data is the opposite: **it is not rebuildable from anything on disk.** Its source is
a live DCS mission that no longer exists. It represents accumulated flight time and is the most
expensive-to-reacquire artifact the project would hold.

Putting non-reproducible data inside a file whose lifecycle is "delete and recreate from raw"
is a design contradiction, and a permanently load-bearing one: every future base rebuild would
have to remember to preserve probe rows across a `DROP`/recreate. With two stores the base
rebuild simply doesn't touch the probe store, and that safety requires discipline from nobody.

It also fits the cross-machine workflow: the base store is a 461 MB artifact regenerable on the
Windows box, while the probe store is small and irreplaceable and is what actually wants
backing up or syncing (`data/world-model-backups/` already exists in `world-model/.gitignore`).
In a single store, appending one chunk would mean touching a 461 MB file.

### 2. It eliminates the "newest grid wins" bug class rather than avoiding it

The hazard found while planning: `reader._load_grid_meta` resolves grids with
`WHERE kind = ? ORDER BY id DESC LIMIT 1`, and **every** grid read inherits it (`sample_grid`,
`load_full_grid`, `grid_spacing_m`, `grid_provenance`). Add a probe elevation grid to an M7
store and that small grid answers for the whole theatre; M7's 591,732-point SRTM baseline goes
silently dark, with no error.

- **Tier column**: every one of those call sites becomes a latent bug until individually
  audited and given a tier filter. Miss one and the failure is invisible and catastrophic. The
  column also does not *prevent* two probe-tier grids coexisting — it only lets correct code
  distinguish them.
- **Two stores**: the base store's `grid` table physically cannot contain a probe row, so
  existing code that opens only the base store is correct *by construction*, unmodified. The
  worst residual failure mode inverts from "theatre elevation silently blanked" to "probe data
  not consulted" — visible and benign.

**Could the bug recur inside the probe store?** Only if it ever held multiple overlapping grid
revisions per kind. The design forecloses this: the probe store holds **exactly one grid row
per kind** (one sparse theatre-wide grid, chunk-filled), enforced by a `UNIQUE(kind)`
constraint rather than by convention. Re-probing a chunk upserts cells in place; changing probe
spacing is an explicit "discard and re-probe" event, not a second grid row. `ORDER BY id DESC
LIMIT 1` then stays trivially correct because there is only ever one candidate — an enforced
invariant, not an intention.

### 3. Query complexity is relocated, not removed — stated plainly

`describe_position` still needs probe-then-base fallback resolution. That logic is inherent to
having two elevation sources of different resolution and does not disappear; it changes from a
`WHERE tier = ?` filter to a schema-qualified table reference.

What keeps this from being a real cost: **reads use `ATTACH DATABASE`**, so `describe_position`
keeps its existing single-`conn` signature and every current caller compiles unchanged.
`sample_grid` becomes "try `probe.grid`, fall back to `main.grid`" — same branch, different
qualifier. **Writes use a direct connection to the probe store only**, never attaching the base
store, so a chunk write physically cannot modify base data.

New cost, stated honestly: a second file to locate, version-check, and handle the absence of. A
missing probe store must degrade to base-only — the project's existing absence-as-absence
convention, needing no new concept, but genuinely one more thing.

### 4. Deployment and consumers

- **Gitignore**: no change needed. `world-model/.gitignore` already ignores `data/world-model/`
  and `*.sqlite` at directory level (verified).
- **Existing consumers unchanged**: `open_region_db`, `tools/export_geojson.py`,
  `tools/validate_m7_stage*.py`, `tools/measure_m7_stage4_perf.py`, `tools/inspect_terrain.py`
  all open the base store and keep working. Only probe-aware consumers open both. Much smaller
  blast radius than a base-schema bump, which would have invalidated every built `.sqlite` and
  forced a ~450 s `syria-full` rebuild on the Windows machine before anything could be tested.
- **What "a world model" is** does change: one theatre is now up to two files, resolved by
  convention from the base path so callers keep passing one path.

### 5. Idempotency scope

The probe store's idempotency axis is **(chunk, kind)**: its `feature` table (ridge/valley)
carries `chunk_ix`/`chunk_iz` alongside the generic `kind`, and re-probing replaces that
chunk's features *of that kind only* — never another kind's features in the same chunk. This is
self-contained — it needs nothing from the base store, which is part of why base-store
per-layer append could be cleanly dropped from M8 (revision note 4) without affecting anything
here.

### 5a. Extensibility: everything is keyed by a generic `kind` string

Probe-tier data types beyond the three named now (fine elevation, `surface_type`, ridge/valley)
must be addable **without a schema migration**. The design satisfies this by mirroring the
conventions the base store already uses, with no new abstraction invented for it:

- **Raster-shaped data** routes through `grid.kind` + `grid_sample`, exactly M5's base-store
  `grid` pattern. A new raster kind is one new `grid` row with a new `kind` value plus an ingest
  function — no `ALTER TABLE`, no new table, no per-kind columns. `UNIQUE(kind)` scopes the
  one-grid-per-kind invariant *per kind*, so it constrains without blocking new kinds.
- **Vector-shaped data** routes through the `feature` table using the same `StoredFeature`
  shape as the base store — generic `kind`, `geom_type`, JSON geometry, `provenance` and
  `confidence` dicts. A new vector kind is a new `kind` value plus an ingest function.
- **Coverage** is keyed `(kind, chunk_ix, chunk_iz)` — see the tri-state decision below for why
  the `kind` component is load-bearing rather than cosmetic.

No table, column, or index is named after elevation, surface type, ridge or valley. Nothing
speculative is added for hypothetical kinds either — the requirement is that the existing three
route through a generic, string-keyed extension point, and they do.

### 6. Simplicity and reviewability

The probe store is greenfield: new schema file, new module, standalone tests, and **zero
modifications to M7-validated write paths**. Review reduces to "does the new store work" plus
"is the base store untouched". The tier-column design would instead have threaded changes
through `schema.py`, `models.py`, `writer.py` and `reader.py`, all validated against a 461 MB
store that takes 450 s to rebuild on another machine. Per the project's decision heuristics
(*prefer simple, debuggable solutions*; *prefer stable, predictable behavior*), the split wins
on both.

### Honest cost summary

Two stores is not free: two files to manage, two schema versions, an ATTACH on the read path, a
path-resolution story, and a new drift risk if a probe store is paired with a base store built
at a different extent. What it buys — probe data surviving base rebuilds, the newest-wins bug
class made structurally impossible, and M7-validated code left untouched — outweighs that,
primarily because of the lifecycle argument in §1, which no amount of care in a single-store
design fully solves.

---

### Locked parameters

| Parameter | Value | Note |
|---|---|---|
| Chunk size | **5,000 m** | Square, in DCS x/z metres |
| Probe spacing | **100 m** | 51×51 = 2,601 samples per chunk |
| Probe store path | **`data/world-model/<region>-probe.sqlite`** | e.g. `syria-full-probe.sqlite` |
| Chunk lattice anchor | DCS x/z origin | `chunk_ix = floor(x / 5000)` |
| Grids per kind in probe store | Exactly 1 | Enforced by `UNIQUE(kind)` |
| Coverage key | `(kind, chunk_ix, chunk_iz)` | New kinds start correctly `unqueried` |

Both numeric values stay module constants with CLI overrides — the *defaults* are decided, the
knobs remain. Rationale: at 100 m a 5 km chunk is 2,601 `land.getHeight` calls, the same order
as M5's proven 1,681-point probe, and a Mi-24 at ~250 km/h crosses one in ~72 s, leaving room
for a look-ahead ring. 10 km chunks would quadruple per-chunk probe cost (10,201 calls) for
coarser granularity. `CHUNK_SIZE_M` must remain an integer multiple of the probe spacing so
chunk edges land on cell boundaries — assert this, don't assume it.

### Affected Modules / Files

**New — the probe store (the bulk of the work)**

- `world-model/src/store/chunks.py` — pure functions for the theatre-anchored chunk lattice:
  `chunk_index_for(x, z)`, `chunk_bounds(ix, iz)`, `chunks_covering(bbox)`. No SQL, no I/O; the
  piece most worth exhaustive unit tests.
- `world-model/src/probe_store/schema.py` — DDL + its own independent `SCHEMA_VERSION`:
  `meta`, `chunk_coverage` (PK `(kind, chunk_ix, chunk_iz)`), `grid` (generic `kind`, with
  `UNIQUE(kind)`), `grid_sample`, `feature` (generic `kind` + `chunk_ix`/`chunk_iz`, + R*Tree).
  No table or column is named after a specific probe kind — see "Extensibility" above.
- `world-model/src/probe_store/models.py` — `Chunk`, `ChunkStatus` enum.
- `world-model/src/probe_store/writer.py` — `open_probe_store` (creates on first use, unlike
  the base store's delete-and-recreate), `upsert_grid_samples(kind, ...)`,
  `upsert_chunk_coverage(kind, ix, iz, status)`, `replace_chunk_features(kind, ix, iz, ...)` —
  every write scoped by `kind` so one kind's re-probe never disturbs another's.
- `world-model/src/probe_store/reader.py` — `chunk_status(kind, ix, iz)` (returns
  `ChunkStatus`, never `None`), `chunks_in_bbox(kind, ...)`, `sample_probe_grid(kind, x, z)`.
- `world-model/src/probe_store/paths.py` — the one place mapping a base-store path to its
  `-probe.sqlite` sibling, so no consumer hardcodes the convention.

**Modified — deliberately minimal**

- `world-model/src/query/describe.py` — optionally ATTACH the probe store; probe-then-base
  fallback for `elevation`/`surface_type`; report which store answered; new `coverage` field
  carrying the chunk's tri-state status. Degrades to today's exact behaviour when the probe
  store is absent.
- `world-model/src/build/pipeline.py` — new `add_probe_chunk(...)` entry point writing only to
  the probe store. `build_region` **untouched**.
- `world-model/src/build/ingest_probe.py` — accept a chunk-scoped probe output.
- `world-model/src/build/ingest_terrain.py` — classify over one chunk's local elevation window
  rather than a whole region grid.

**Docs/tests**

- `world-model/tests/` — `test_store_chunks.py`, `test_probe_store.py`,
  `test_probe_chunk_pipeline.py`; extensions to `test_describe_position.py`.
- `world-model/CLAUDE.md` — record the two-store decision in Tech Stack, matching the existing
  per-milestone decision entries.
- `world-model/docs/M8_PROBE_STORE.md` — the two-file model, each file's lifecycle, and the
  backup/sync implication. Short.

### Design decisions

**Theatre-anchored chunk lattice.** `chunk_ix = floor(x / CHUNK_SIZE_M)` anchored at the DCS
x/z origin, so a chunk index is computable from a position alone with no store lookup and stays
stable across regions, rebuilds and region redefinition. (Python's `//` floors correctly for
negatives, which Syria has on both axes.) Deliberately unlike `probe_grid_for_region`, whose
SW-corner origin moves whenever a region is redefined — fine for a one-pass build, wrong for a
persistent coverage record.

**Tri-state coverage, keyed per (kind, chunk), with absence meaning `unqueried`.** Syria at
5 km is ~166×154 ≈ 25,500 chunks — cheap to materialize, but materializing would make "unbuilt
store" and "never probed" distinguishable only by whether someone ran a materialization step.
So: no row → `unqueried`; `queried_with_data` and `queried_void` are always explicit rows.
`chunk_status(kind, ix, iz)` returns `ChunkStatus` and never `None`, keeping the tri-state
total at the API surface — the same discipline `describe_position` rule 3 applies to features.
`queried_void` is a real outcome: a probe can run over a chunk and legitimately yield nothing
storable, and that must never read back as "not asked yet".

**The `kind` component of the coverage key is load-bearing, not cosmetic.** A coverage row
keyed by chunk alone asserts "this chunk was probed" — a claim that is only meaningful relative
to *what* was probed. Add a fourth probe-tier kind later and every chunk already marked
`queried_with_data` would falsely claim coverage for a kind that was never asked about, and
correcting that would require exactly the schema migration this design is meant to avoid.
Keying `(kind, chunk_ix, chunk_iz)` from the start costs one PK column and makes a new kind
start life correctly `unqueried` everywhere. It also sharpens `queried_void`: the concept doc's
own example — `land.getSurfaceType` over open water — is a per-kind outcome, since elevation
for that same chunk may well have data.

**One sparse grid per kind, filled chunk by chunk.** `grid_sample`'s `(grid_id, row, col)` PK
is already sparse and upsertable, so a chunk write is an `INSERT OR REPLACE` batch into a
pre-declared grid. Coverage lives in the `chunk_coverage` table where it belongs, rather than being
inferred from which grid rows exist.

**M6's classifier runs per-chunk unchanged.** It is already a local discrete-Laplacian
computation over a local grid neighbourhood (`src/terrain/`), so running it per arriving chunk
is a scope reduction, not a redesign.

### Implementation Plan

1. **Chunk lattice, pure functions only.** `store/chunks.py` + tests: negative coordinates
   (Syria's SW quadrant), the chunk-size/probe-spacing divisibility assertion, and
   `chunk_index_for(centre_of(chunk_bounds(ix, iz))) == (ix, iz)` round-trips. No schema, no
   I/O — independently verifiable, and everything else depends on it being right.
2. **Probe store schema + writer/reader primitives.** Greenfield; `UNIQUE(kind)` on `grid` from
   the start; `executemany` for cell writes from the start. Round-trip tests: create → upsert
   chunk → re-upsert the same chunk → assert cell counts stable rather than doubled, and that
   `feature` and its R*Tree stay in step. **Extensibility test**: register a second, invented
   raster kind and a second vector kind through the same generic paths and assert both store,
   read back, and report coverage independently — no `ALTER TABLE`, and re-probing one kind
   leaves the other's rows and coverage untouched. The invented kinds live in the test only,
   never in `src/`.
3. **Read integration.** ATTACH-based probe-then-base fallback in `sample_grid`;
   `describe_position` reports which store answered plus chunk coverage. **Control-point test**:
   a base store with an SRTM grid plus a probe store with one chunk must return the probe value
   inside the chunk and the SRTM value outside, each correctly labelled — and must behave
   exactly as today when the probe store is absent.
4. **`add_probe_chunk(...)`.** Ingest one chunk-scoped probe output: upsert samples, mark the
   chunk, run M6's classifier over that chunk's local elevation window, replace that chunk's
   ridge/valley features. Driven by a synthetic fixture probe file — no live DCS, the same way
   M7 verified pipeline code against fixtures.
5. **Performance sanity, not a full-theatre run.** Measure append-one-chunk latency and
   `describe_position` with the probe store attached, against a locally generated store. Do
   **not** run a full `syria-full` rebuild locally — that is the Windows machine's job
   (`world-model/docs/M7_RUN_INSTRUCTIONS.md` precedent); write run instructions instead.

### Risks & Unknowns

- **Two stores can drift out of alignment.** A probe store built against one region's geometry,
  then paired with a base store rebuilt at a different extent, would silently mis-place chunks.
  Mitigation: the probe store's `meta` records theatre, chunk size, probe spacing and the base
  store's schema version; opening a mismatched pair must fail loudly. This is the main new risk
  the split introduces and it needs an explicit test.
- **The `ORDER BY id DESC` hazard still exists in the base store's reader.** The split means
  nothing can currently trigger it, but it stays a live trap for any future change that adds a
  second grid of one kind. Leave a pointed comment at `_load_grid_meta`; the `UNIQUE(kind)`
  precedent could later be applied there too.
- **Chunk size is reasoned, not measured** — from M5's probe size and Mi-24 groundspeed, not
  from a live probe. Now locked as a default, but changing it later means re-probing, not
  merely rebuilding. Treat a future change as a data-migration event.
- **ATTACH adds failure modes**: a probe store with a mismatched schema version, a locked file,
  or a stale path. All must degrade to base-only with an explicit signal, never a silent partial
  answer.
- **Chunk/probe-grid alignment has no natural enforcement point.** If the probe grid origin and
  the chunk lattice disagree by a fraction of a cell, chunk writes land off-by-one and the error
  is nearly invisible. Assert the relationship at grid-creation time and fail loudly.
- **Probe-store feature deletion must take the R*Tree with it.** Replacing a chunk's ridge/
  valley features orphans `feature_bbox` rows unless both are deleted in one transaction — an
  orphan yields a stale bbox hit whose `feature` join fails. Assert row-count parity in tests.
- **Two-file backup/sync discipline is now a user-facing concern.** The probe store is the
  irreplaceable one. State this in `M8_PROBE_STORE.md` rather than leaving it implicit.
- **The probe store has no real data until a Runtime milestone exists.** M8 ships a tested,
  fixture-verified capability whose first real use is gated on the live-probe channel being
  solved elsewhere. That is intended, but it means M8's acceptance testing cannot include a
  real accumulated-coverage run.
