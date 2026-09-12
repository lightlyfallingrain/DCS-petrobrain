### Goal

Fill the `nearest_settlement` / `inside_settlement` / `nearest_water` gap M7 leaves `null`
theatre-wide by parsing the 7 already-downloaded Geofabrik `.osm.pbf` country extracts covering
Syria's real-world theatre footprint with `pyosmium`, feeding them through M3's existing
`OsmFeatureSet` → `ingest_osm` → store pipeline (unchanged), so settlement boundary *polygons*
(not just DCS's `towns.lua` center points) become queryable.

> **Status: active (reopened 2026-09-13).** Supersedes the 2026-09-06 deferred version of this
> file (recoverable via `git log -- plans/m9-osm-geofabrik/plan.md`). The dependency question
> that version left open is resolved (`pyosmium`, user-approved); this revision also reverses
> that version's Design Decision 1 (mandatory `osmium-tool` clip) for a different reason than it
> was written for — see "What changed from the deferred plan" below.

Reconnaissance already on file, read but not re-litigated here:
`research/2026-09-06-m8-geofabrik-osm-recon.md` (original Geofabrik/format recon) and
`research/2026-09-12-m9-tactical-landmarks-recon.md` (confirms zero DCS-native settlement-extent
source exists anywhere in the installed Syria terrain — OSM is the only path).

### What changed from the deferred plan (read this before Stage 0)

The deferred version's central open question was "hand-roll a `.pbf` parser, or take a new
dependency" — driven by the fear that a hand-rolled node-ID→(lat,lon) resolution pass would blow
up in memory over a ~612 MB Turkey extract. That question is now closed: **pyosmium**, whose C++
side handles node-location indexing internally (`SimpleHandler.apply_file(...,
locations=True, idx="sparse_mem_array")` — a memory-efficient index, not a naive Python dict),
so the memory-blowup concern that justified the deferred plan's Design Decision 1 ("bbox-clipping
with `osmium-tool` is mandatory... over a raw ~612 MB Turkey extract that is tens of millions of
nodes — a memory blowup") no longer holds as stated.

That does **not** mean skip clipping — it means the justification changes. Reading actual file
sizes now on disk (`ls -la data/raw/osm/`): Cyprus 37 MB, Jordan 31 MB, Lebanon 52 MB, Syria
82 MB, Iraq 90 MB, Israel-and-Palestine 119 MB, **Turkey 646 MB**. Syria's DCS theatre only
touches Turkey's southern strip — most of a 646 MB nationwide extract's node/way graph is
irrelevant. Indexing it in full 7 times (once per country, unfiltered) wastes real time on a
pipeline stage with no incremental-rebuild mechanism (`todo/todo.md`'s "Incremental per-layer
pipeline builds" backlog item, considered and dropped for M8, still not built — a rule-tuning
iteration means a full re-parse every time). **Decision: keep the pre-clip step, but as a
time/wasted-work optimization, not a memory-safety requirement** — same tool (`osmium-tool`),
same "user-run prerequisite, not a project dependency" framing the deferred plan already used
for it (GPLv3 CLI, invoked via `subprocess`, never imported/linked — same category as DCS itself,
not a second entry in `pyproject.toml`, so this does not re-trigger AGENTS.md's
new-dependency-escalation rule).

Also newly confirmed by reading current code (not assumed from the deferred plan's framing):
**the query surface needs zero changes.** `query/describe.py`'s `nearest_settlement` already
calls `store.reader.nearest_feature(conn, ["settlement"], x, z)` — geom-type-agnostic, works
identically whether a `settlement` row is a `Point` or a `Polygon`. `inside_settlement` already
calls `store.reader.containing_polygons(conn, ["settlement"], x, z)`, which already filters to
`geom_type == "Polygon"` and does real point-in-ring containment
(`store/reader.py:230`). Both already return `None` when no polygon/no nearby point exists —
the absence-not-null convention this milestone needs is already in place, not something to add.
This machinery has existed, unexercised, since M5 (`store/schema.py`'s `Polygon` geom_type,
`store/reader.py`'s `containing_polygons`) — it was simply never fed real polygon data because
Overpass was never run against Syria in `build_region`. **This milestone is entirely a data-
sourcing problem, not a query-surface problem** — narrower scope than the deferred plan's file
list implied (it listed `describe_position` changes as still-open; they are not).

### Affected Modules / Files

- `world-model/src/osm/pbf.py` *(new)* — `pyosmium`-based `.osm.pbf` → `OsmFeatureSet`
  (`osm/features.py`'s existing dataclasses, unchanged). The only new parsing code.
- `world-model/src/osm/features.py` — unchanged. `load_features`'s docstring gains a note that
  it is the Overpass-era path, superseded by `osm/pbf.py` for real builds.
- `world-model/src/osm/overpass.py` — untouched, kept for `tools/inspect_osm_overlay.py`
  diagnostic continuity, marked superseded on the pipeline path.
- `world-model/src/build/ingest_osm.py` — **no logic change expected**, but `_classify_way`'s
  four rules (road/water/settlement via `highway`/`waterway`+`natural=water`/`landuse`+`place`)
  were written against Overpass-narrowed results and have never run against a raw extract's full
  tag vocabulary. Re-validate against real data in Stage 4; only touch the file if real tags
  reveal a gap.
- `world-model/src/build/pipeline.py` — `build_region` gains `osm_pbf_path: Path | None = None`
  alongside the existing `osm_cache_path: Path | None`; Stage 3 branches: `osm_pbf_path` present
  → `osm.pbf.load_features`, else fall back to the existing `osm_cache_path`/`load_features`
  path (keeps existing Overpass-cache-based tests/tooling unaffected — additive, not a
  replacement).
- `world-model/pyproject.toml` — adds `pyosmium` to `dependencies`.
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` *(new)* — the exact `osmium-tool` extract+merge
  commands (with the theatre bbox in lat/lon, derived once from `syria-full`'s region corners via
  `coordinates.dcs_to_wgs84` and written down as fixed numbers, not recomputed at build time) and
  which machine runs them. Mirrors `M7_RUN_INSTRUCTIONS.md`'s execution-boundary precedent —
  clipping/merging/the full-theatre pipeline run are **user-run steps**, not something this
  session executes (per this project's standing rule against running real full-theatre
  builds/large external processing itself).
- `world-model/tests/test_osm_pbf.py` *(new)* — parser tests against a tiny committed fixture
  `.pbf` (hand-built via `osmium-tool` or pyosmium's own writer from a handful of synthetic
  nodes/ways covering each of the four classification rules plus one relation, so
  `relations_skipped` stays exercised).
- `world-model/tests/test_ingest_osm.py` *(new — none currently exists; `ingest_osm.py`'s
  classification logic has zero direct test coverage today, confirmed by grep)* — exercise
  `_classify_way`/`_ingest_node`/`_ingest_way` against realistic tag combinations, independent of
  the Overpass-vs-pbf source question.

### Design decisions

**1. Pre-clip + merge with `osmium-tool`, done once per extract set, is a user-run
prerequisite** (not a project dependency, not something the pipeline invokes). Rationale above.
Concretely: `osmium extract -b <lon_min>,<lat_min>,<lon_max>,<lat_max> --strategy=smart -o
<country>-clipped.osm.pbf <country>-260911.osm.pbf` per country, then `osmium merge
*-clipped.osm.pbf -o syria-theatre.osm.pbf`. `--strategy=smart` matters: it completes ways whose
nodes straddle the bbox edge, avoiding the "way references a node pyosmium's index never saw"
failure mode a naive bbox cut would hit at the Turkey/Syria border specifically (the theatre's
most bbox-edge-heavy country by construction).

**2. `osm/pbf.py` processes exactly one pre-clipped, pre-merged file.** Same contract the
deferred plan already committed to — the Python side never juggles 7 separate country files or
re-derives the theatre bbox; it takes one path. `SimpleHandler` subclass with `locations=True,
idx="sparse_mem_array"` resolves way geometry inline; a way whose nodes are still unresolved
after that (shouldn't happen post-`--strategy=smart`, but must be handled, not assumed away) is a
**counted skip** (`ways_skipped_unresolved_nodes` on `OsmFeatureSet` or an equivalent stat),
following the `relations_skipped`-precedent this project already uses for "unsupported construct,
not silent drop."

**3. Everything M3 built downstream of `OsmFeatureSet` stays exactly as-is.** No schema change
(`Polygon` geom_type already exists, `SCHEMA_VERSION` stays 3), no `describe.py` change (already
generic over geom_type, confirmed above), `ingest_osm.py` unchanged unless Stage 4's real-tag
validation finds a gap. The seam this milestone adds is a single new function,
`osm.pbf.load_features(pbf_path) -> OsmFeatureSet`, parallel to the existing
`osm.features.load_features(cache_path) -> OsmFeatureSet`.

**4. Water and named-place ingestion ride along for free — no separate scoping decision
needed.** `_classify_way` and `_ingest_node` already classify `waterway`/`natural=water` and
`place`+`name` nodes in the same pass as settlement ways; there is no code path that produces
settlement polygons without also producing whatever water/named-place features the same extract
tags support. Restricting this pass to "settlement polygons only" would mean throwing away
already-computed classifications for no savings — so water and named-place are in scope by
construction, not as an added feature.

**5. Multipolygon relations remain an explicit, counted skip** — same as M3's original scope.
This matters concretely for settlement coverage: real-world large-city administrative boundaries
are frequently mapped as `type=multipolygon`/`type=boundary` *relations* with inner/outer rings,
not simple closed ways, so they will **not** produce a `settlement` polygon this pass — only
smaller settlements/villages/`landuse` parcels mapped as plain closed ways will. This is a real,
documented coverage gap (see Risks), not a bug, and not blocking: partial polygon coverage is
still strictly more than the theatre-wide `null` M7 leaves today.

**6. OSM rows never overwrite DCS rows** (unchanged invariant from the deferred plan) —
`provenance={"geometry": "osm", "name": "osm"}`, ~1,300 m M1 uncertainty, land beside DCS's
`road`/`named_place` rows exactly as `nearest_road` vs `nearest_road_osm` already does.

### Implementation Plan

1. **Derive and document the theatre clip bbox.** One-off script using
   `coordinates.dcs_to_wgs84("Syria", ...)` against `syria-full`'s four region corners
   (`build/region.py`) to get a lat/lon bounding box; pad it the same way `syria-full` itself was
   padded (some margin, not a knife-edge cut against DCS's own extent uncertainty). Write
   `M9_OSM_RUN_INSTRUCTIONS.md` with the exact numbers and the `osmium extract`/`merge` commands.
   Hand this to the user to run (`brew install osmium-tool` + the commands) — do not run
   multi-hundred-MB external processing in this session.
2. **`osm/pbf.py` + fixture tests**, independent of the real merge finishing. A tiny synthetic
   `.pbf` fixture (few nodes/ways covering road/water/settlement/named_place + one relation)
   proves the parser end-to-end without waiting on the real 7-country merge. Verify `pyosmium`
   actually installs in the real dev environment before relying on it (flagged as a risk below —
   this session's sandboxed tool environment could not resolve `pyosmium` from PyPI even with an
   explicit index URL, while a plain `pip install requests` against the same index succeeded;
   root cause not established, but web search confirms pyosmium ships wheels through at least
   cp313 and claims cp314 support, so treat this as this-session's-sandbox-specific until proven
   otherwise on the real machine).
3. **Wire `osm_pbf_path` into `build_region`** (Stage 3, additive alongside `osm_cache_path`).
4. **Validate against the real Syria-only extract first** (`syria-260911.osm.pbf`, 82 MB, clipped
   to itself trivially or used as-is since it's the smallest and already theatre-relevant) before
   touching the 646 MB Turkey file: control-point check per this project's testing convention
   (a known real place, e.g. Latakia, should land inside or very near an OSM settlement polygon
   if one exists in this extract) and a `_classify_way` real-tag audit — log actual
   `ways_skipped_unclassified` counts and inspect a sample of skipped tags to confirm the four
   rules aren't missing an obviously-common case.
5. **Full merged-theatre run.** Once the user has produced the merged/clipped
   `syria-theatre.osm.pbf`, run the full `build_region("syria-full", ...)` rebuild with
   `osm_pbf_path` set. Measure: feature counts by kind, store size delta vs. M7's 461 MB baseline,
   `describe_position` p99 delta vs. M7's already-flagged 803 ms tail (this is a real risk, not
   a formality — see Risks).
6. **Write findings to `research/`** (extract coverage, skip counts, store growth, query-latency
   delta) and update `world-model/ROADMAP.md`'s M9 entry to done.

### Risks & Unknowns

- **`pyosmium` install verification is outstanding.** This session's sandbox could not resolve it
  from PyPI (explicit-index-url install of `requests` worked; `pyosmium` did not, "no versions
  found"). Confirm on the actual dev machine before Stage 2 is considered complete — if it
  genuinely lacks a wheel for the project's Python version, that is an escalation-worthy
  dependency-decision reopening, not something to route around silently.
- **Multipolygon-relation settlements are invisible this pass** (Design Decision 5) — large
  cities mapped as relations get no polygon; only closed-way-mapped villages/landuse parcels do.
  Real, bounded, documented — not a blocker, but don't report "settlement polygons done" as
  uniform coverage.
- **`_classify_way`'s rules are unvalidated against real extract tags** — they were written
  against Overpass-narrowed results in a query that no longer runs. Stage 4 exists specifically
  to close this before the full Turkey-scale run.
- **Store growth / query-tail risk carries forward from M7.** M7's `describe_position` p99 was
  already 803 ms and flagged as a followup, not fixed. A large new polygon layer risks pushing
  that further; measure in Stage 5, don't assume it's fine.
- **No incremental per-layer rebuild exists** (`todo/todo.md` backlog item, dropped from M8) —
  every `_classify_way` rule tweak in Stage 4 costs a full pipeline rebuild. Accepted cost for
  this milestone; still on the backlog, not being scheduled here.
- **OSM is not period-accurate for DCS's Syria** (unchanged from the deferred plan) — post-2011
  conflict changed the real region; this is reference "what is it" data, never game truth.
- **`osmium-tool`'s `--strategy=smart` behavior at the Turkey/Syria border is unverified** beyond
  its documented purpose — if it still produces ways with dangling/unresolved node references,
  Design Decision 2's counted-skip path is the safety net, but the resulting settlement/road
  coverage right at that border may be thinner than elsewhere. Worth a spot-check in Stage 5, not
  a blocker.

### Second-order effect

Unblocks Mission Interpreter's MI-2 world-enrichment stage, which needs settlement-extent
reasoning for tactical narrative (`plans/mission-interpreter/plan.md`,
`plans/world-model-tactical-landmarks/plan.md`) — MI-2 can now query `inside_settlement` and get
a real polygon-backed answer for at least partial theatre coverage instead of a permanent `null`.
It does not unblock or narrow anything else on the roadmap; M10 (junctions) and the LOS
generalization already merged are independent of this data source.
