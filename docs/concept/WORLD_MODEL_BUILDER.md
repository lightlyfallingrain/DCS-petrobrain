# DCS World Model Builder

## Objective

Build a persistent, queryable semantic geographic model of DCS World theatres.

This is the foundational project for the larger Petrobrain system. It should be useful without Petrobrain itself and should not contain Petrovich-specific cognition.

The first milestone is **not** “understand all of Syria/Caucasus perfectly.”

The first milestone is:

> Given a DCS coordinate in one supported theatre, return a useful, verifiably correct description of the surrounding simulated geography.

For example:

```json
{
  "theatre": "Syria",
  "position": {"x": 123456, "z": 654321},
  "elevation_m": 512,
  "nearest_settlement": {
    "name": "Example",
    "distance_m": 620
  },
  "nearest_road": {
    "distance_m": 80,
    "orientation": "N-S"
  },
  "terrain_context": [
    "valley floor",
    "ridge approximately 1.4 km west"
  ]
}
```

Accuracy and provenance matter more than impressive prose.

---

# Core Design

The builder is an **offline/incremental data pipeline**.

```text
DCS installation
   │
   ├── terrain/map assets
   ├── RasterCharts
   ├── terrain configuration
   └── extractable DCS data
   │
   ├───────────────┐
   │               │
   ▼               ▼
DCS extraction   external GIS
                   │
                   ├── OpenStreetMap
                   ├── DEM/elevation
                   └── open imagery/land cover
   │               │
   └───────┬───────┘
           ▼
     reconciliation
           ▼
 semantic features
           ▼
 persistent spatial DB
           ▼
      query API
```

DCS data is authoritative about the simulation.

External data provides names, topology and semantics where it agrees sufficiently with DCS.

---

# Start With Reconnaissance, Not Implementation Assumptions

DCS internals are incompletely documented and change over time.

Before committing to architecture, investigate the currently installed DCS version and build small probes.

Document every finding.

Create something like:

```text
research/
    dcs-terrain-layout.md
    rastercharts.md
    coordinate-systems.md
    runtime-terrain-api.md
    scenery-objects.md
    external-gis.md
```

For every discovery record:

- DCS version tested;
- theatre tested;
- file/API involved;
- exact observation;
- whether documented or inferred;
- reproducible test;
- source/reference.

Do not silently encode forum folklore as fact.

---

# Research Sources

## DCS installation itself

Treat the installed game as primary evidence.

Inspect:

```text
DCS World/
    Mods/
        terrains/
            <terrain>/
```

Community reports identify F10/Mission Editor raster assets under terrain-specific `RasterCharts` directories, sometimes inside archives and commonly using DDS/TIF-related assets.

Do not assume every theatre has identical layout.

Search the installation for:

```text
RasterCharts
terrain
projection
coordinate
roads
surface
map
```

Do not modify the DCS installation.

All extraction should be read-only.

## DCS / Eagle Dynamics forums

Search the ED forums aggressively. Many useful technical details exist only in old modding discussions.

Useful search concepts:

```text
site:forum.dcs.world RasterCharts
site:forum.dcs.world F10 map stored location
site:forum.dcs.world DCS coordinate transformation
site:forum.dcs.world terrain projection
site:forum.dcs.world land.getHeight
site:forum.dcs.world scenery objects export
site:forum.dcs.world road network scripting
site:forum.dcs.world terrain map DDS
site:forum.dcs.world GeoTIFF DCS
site:forum.dcs.world QGIS DCS
```

Particularly relevant starting points include ED Forum discussions titled:

- **F10 map stored location**
- **Coordinate transformation**
- discussions of F10 raster/TPC alignment and terrain mismatch
- DCS scripting/modding threads concerning terrain and scenery

The forum is evidence and leads, not authoritative documentation. Verify claims locally.

## Hoggit DCS World Wiki

Use the Hoggit wiki as a practical reference for the scripting environment.

Research at least:

```text
land.getHeight
land.getSurfaceType
land.isVisible
land.getIP
land.getClosestPointOnRoads
land.findPathOnRoads
coord.LOtoLL
coord.LLtoLO
world.searchObjects
```

Confirm which functions are available in which DCS scripting/export environments.

Do not assume mission scripting APIs are automatically available to an external process.

## Existing community projects

Search GitHub and the ED forums for projects involving:

- DCS moving maps;
- DCS-to-Leaflet/OpenLayers mapping;
- DCS coordinate converters;
- DCS GIS;
- Tacview/DCS coordinate conversion;
- DCS Olympus;
- DCS-gRPC;
- LotATC;
- mission planning tools;
- raster chart mods;
- QGIS + DCS workflows.

The goal is not necessarily to depend on these projects. They may contain solved projection, extraction or coordinate-registration problems.

Check licenses before reusing code.

---

# Coordinate Systems Are a First-Class Problem

Do not build semantic extraction before coordinate registration is understood.

The model will probably need at least:

```text
DCS local coordinates (x/z)
WGS84 latitude/longitude
raster pixel/tile coordinates
external GIS coordinates
```

DCS theatres may use different projection parameters or origins.

Build explicit transforms:

```python
dcs_to_wgs84(theatre, x, z)
wgs84_to_dcs(theatre, lat, lon)

dcs_to_raster(theatre, x, z, layer)
raster_to_dcs(theatre, px, py, layer)
```

Do not scatter coordinate math throughout the application.

Create a dedicated coordinate subsystem and test it.

## Validation

Create known control points such as:

- runway thresholds;
- airfield reference points;
- distinctive road intersections;
- coastlines;
- bridges;
- prominent geographic features.

For each:

```text
DCS coordinate
F10 raster location
lat/lon
OSM location
error distance
```

Generate an error report.

A transform that “looks about right” is insufficient.

---

# DCS Raster Charts

Investigate how F10/Mission Editor raster charts are structured.

Questions to answer:

1. Where are the assets for each theatre?
2. What formats are used?
3. Are there multiple scales/zoom levels?
4. How are tiles indexed?
5. Where is georeferencing stored?
6. Are mipmaps relevant?
7. Is the F10 display combining raster and vector/generated layers?
8. Are labels baked into imagery or rendered separately?
9. Do raster layers accurately correspond to actual DCS terrain?

Community reports indicate `Mods/terrains/<terrain>/RasterCharts` as an important location and also report projection/registration complications.

Build a small raster inspection tool before attempting semantic extraction.

Desired output:

```text
theatre: Syria
layers:
    ...
tiles:
    ...
pixel dimensions:
    ...
estimated geographic extent:
    ...
projection:
    ...
```

If practical, generate a stitched preview for debugging.

---

# External GIS

## OpenStreetMap

OSM is likely the most useful augmentation source for:

- place names;
- settlement boundaries;
- roads;
- road classes;
- rivers;
- railways;
- bridges;
- land use;
- notable structures.

Respect the OpenStreetMap ODbL licence and attribution requirements.

Do not assume OSM represents the historical period portrayed by DCS.

OSM is **reference data**, not game truth.

## Elevation

Investigate suitable openly licensed DEM sources, for example Copernicus DEM or other public elevation products covering the theatre.

Compare external DEM elevation against DCS elevation.

This serves two purposes:

1. geographic alignment validation;
2. determining where real-world terrain semantics are safe to import.

Store the difference:

```text
elevation_dcs
elevation_external
delta
```

Large systematic disagreement should lower confidence in real-world-derived semantics.

## Imagery / land cover

If needed later, investigate open sources such as Copernicus/Sentinel-derived products.

Avoid building the project around Google Maps/Google satellite imagery. It is useful for manual investigation but its licensing and caching/derivative restrictions make it a poor foundation for a persistent/distributable dataset.

Do not add imagery processing until structured sources prove insufficient.

---

# Data Fusion and Provenance

Never collapse “DCS says X” and “real world says X” into one undocumented fact.

Represent evidence.

Example:

```yaml
feature:
  id: settlement_00142
  type: settlement

  dcs_geometry:
    polygon: ...

  external_matches:
    - source: osm
      osm_id: ...
      name: Al-Qusayr
      geometry: ...
      match_score: 0.87

  semantics:
    preferred_name: Al-Qusayr

  provenance:
    geometry: dcs
    name: osm

  confidence:
    geometry: high
    identity_match: high
```

This makes disagreement manageable.

A useful principle:

> **Use DCS to answer “where is it in the simulation?”  
> Use external GIS to help answer “what is it?”**

---

# Semantic Terrain Features

The final model should eventually represent more than roads and towns.

Potential derived features:

```text
ridge
ridgeline
valley
hill
saddle
slope
basin
pass
coast
river corridor
urban area
forest/treeline
agricultural area
open terrain
road junction
bridge
airfield
prominent landmark
```

Do not attempt all of these initially.

## Elevation-derived features

Once a DCS elevation grid can be generated, investigate GIS algorithms for:

- slope;
- aspect;
- curvature;
- watershed;
- ridgeline extraction;
- valley extraction;
- prominence;
- terrain segmentation.

Prefer established GIS algorithms/libraries over LLM inference.

A ridge should be a geometric feature with coordinates, orientation and extent, not merely generated text.

Example:

```yaml
feature:
  id: ridge_381
  type: ridge
  geometry: LineString(...)
  elevation_range_m: [620, 790]
  orientation_deg: 145
```

Natural-language descriptions can be generated later.

---

# Spatial Storage

Use a storage format that supports real spatial queries.

Candidates to investigate:

- GeoPackage;
- SQLite + SpatiaLite;
- PostGIS;
- FlatGeobuf/GeoParquet plus an application index.

For an initial local single-user application, prefer the simplest solution that gives:

- spatial indexes;
- points, lines and polygons;
- metadata/provenance;
- easy inspection with GIS tools such as QGIS;
- no required server process.

GeoPackage is therefore a strong initial candidate, but validate library/tooling support before committing.

Keep raw extracted data separate from derived data so the database can be rebuilt.

## Incremental, on-demand probe-tier data (post-M7, proposed)

> **Status: proposed, not implemented.** Raised 2026-09-06 after WM-M7 (full-theatre pipeline)
> completed. Depends on an open question in `PETROBRAIN_RUNTIME.md` ("World model acquisition:
> incremental, on-demand probing") that must be resolved first. Recorded here because it changes
> a storage/schema assumption this section otherwise leaves implicit.

WM-M7 split the theatre's data into two cost tiers, though the split wasn't named explicitly at the
time:

- **Base tier** — roads, settlements, airfields, beacons, navaids. Cheap: parsed directly from
  DCS-native files (`.routes`, `towns.lua`, `beacons.lua`), no live-mission access needed. WM-M7
  builds this whole-theatre in one pass (~450s for Syria) and there is no reason to make it
  incremental — it is already cheap at full scale.
- **Probe tier** — elevation, `surface_type`, and WM-M6's derived ridge/valley classification. The
  only tier that ever needs a live DCS mission probe (`land.getHeight`/`land.getSurfaceType`),
  which is comparatively expensive and slow. WM-M7 sidesteps this for elevation specifically by
  using SRTM (an external DEM) as the full-theatre baseline instead of a live probe grid — but
  `surface_type` and ridge/valley have no such external substitute, and stay theatre-wide
  `"unavailable"` in the WM-M7 build as a result (see
  `world-model/research/2026-09-06-m7-stages-1-2-3-full-build-results.md`).

The proposal: rather than ever running one theatre-wide live probe for the probe tier (expensive,
and mostly wasted — a player, especially in a helicopter, is unlikely to need probe-tier
resolution outside a small operating area), fill it **incrementally, chunk by chunk, driven by
where a player has actually flown**. This mirrors the project's existing "Petrovich's knowledge
is bounded by what he could perceive" principle (root `CLAUDE.md`), applied to the world model
itself rather than to contact/perception state.

This needs three things the current schema/pipeline don't have:

1. **A chunk grid for the probe tier**, independent of the degree-based SRTM tiling already in
   use — fixed-size square tiles in DCS x/z metres. Tile size is a real tuning decision (probe
   call overhead vs. granularity) for a later Architect pass, not decided here.
2. **A tri-state coverage status per chunk**: `unqueried` / `queried-with-data` / `queried-void`
   (a probed cell can legitimately have no data — e.g. `land.getSurfaceType` over open water —
   and that must stay distinguishable from "never asked," per this project's absence-as-absence
   convention already used in `query/describe.py`).
3. **Upsert-into-existing-store support.** `build.pipeline`'s `build_region` currently deletes
   and recreates the whole `.sqlite` on every invocation (see `todo/todo.md`'s "Incremental
   per-layer pipeline builds" backlog item, raised during WM-M7 DoD acceptance testing for a
   different reason — dev-workflow convenience). This proposal needs the same underlying
   capability, just with a second trigger: a running Petrobrain Runtime session writing newly
   probed chunks into a store that already exists, not only a developer re-running one layer.

Ridge/valley classification (WM-M6) fits this well without new work: it is already a local
discrete-Laplacian computation over a chunk's own elevation grid (`src/terrain/`), so running it
per-arriving-chunk instead of once over a whole pre-built region is a scope reduction, not a
redesign.

This is about avoiding **probe cost** (live DCS-mission calls are the expensive step), not
runtime memory — SQLite + R*Tree already answers `describe_position` via spatial index without
loading the whole store, established by WM-M5/WM-M7's own latency measurements. Do not motivate this
change by a memory-footprint argument; it doesn't hold.

Suggested conceptual layout:

```text
data/
    raw/
        dcs/
        osm/
        dem/
    processed/
        theatre-name/
    world-model/
        theatre-name.gpkg
```

Do not commit huge generated datasets to Git by default.

---

# Query Interface

Design the World Model around questions downstream agents need.

Initial API candidates:

```python
describe_position(theatre, dcs_x, dcs_z)

nearest_features(
    theatre,
    dcs_x,
    dcs_z,
    types=None,
    radius_m=5000
)

features_between(
    theatre,
    point_a,
    point_b
)

terrain_profile(
    theatre,
    point_a,
    point_b
)

describe_relationship(
    theatre,
    point_a,
    point_b
)
```

Later:

```python
terrain_context(...)
line_of_sight_context(...)
route_context(...)
landmarks_near(...)
describe_area(...)
```

Keep the API deterministic.

It should return structured data. Natural language is a presentation layer.

---

# Suggested Initial Milestones

## Milestone 0 — Repository and research notebook

Create:

```text
README.md
docs/
research/
src/
tests/
tools/
data/
```

Record DCS installation/version and installed theatres.

Do not write a large framework yet.

## Milestone 1 — One coordinate

Choose one theatre, preferably whichever is easiest to inspect locally.

Prove:

```text
DCS x/z
    ↕
lat/lon
    ↕
known real-world location
```

Measure error.

## Milestone 2 — Raster understanding

Read the theatre's RasterCharts.

Determine:

- tile hierarchy;
- dimensions;
- scales;
- registration.

Render a known DCS coordinate onto the raster.

## Milestone 3 — OSM overlay

Download a small OSM region around a known location.

Transform it into the DCS/raster coordinate space.

Generate a diagnostic overlay.

Do roads/coastlines/settlements line up?

Quantify differences.

## Milestone 4 — DCS elevation

Create an extraction/probing mechanism that can sample DCS terrain elevation over a small region.

Generate a grid.

Compare it with an external DEM.

## Milestone 5 — First persistent model

Build a small geographic database for perhaps a 20 × 20 km test region containing:

- elevation;
- roads;
- settlements;
- water;
- named places.

Implement:

```python
describe_position(...)
```

## Milestone 6 — Terrain semantics

Add one useful derived feature class, probably ridges/valleys.

Test whether the resulting descriptions are actually useful from an Mi-24 cockpit perspective.

## Milestone 7 — Full theatre pipeline

Only after the small region works reliably should the builder process an entire theatre.

---

# Testing Philosophy

This project can easily produce convincing but wrong geography.

Build visual and quantitative diagnostics early.

For every pipeline stage, make it possible to inspect the result.

Examples:

- map overlay PNG;
- QGIS-loadable layer;
- coordinate control-point table;
- elevation difference map;
- unmatched OSM features;
- DCS-vs-OSM road displacement statistics;
- query examples with known expected answers.

A human should be able to look at a generated map and say whether the model is sane.

Automated tests should include known geographic control points.

---

# Things Not To Do Yet

Do not initially:

- build the Petrovich dialogue system;
- add speech recognition/TTS;
- build vector embeddings of geography;
- ask an LLM to continuously interpret map screenshots;
- process every DCS theatre;
- infer every possible terrain semantic;
- create an elaborate distributed architecture;
- make external real-world data authoritative;
- modify DCS files.

The first objective is evidence:

> Can we construct a reliable semantic spatial model that maps DCS coordinates to meaningful simulated geography?

---

# Information Claude Should Actively Investigate

When working on this project, do not rely solely on this document.

Search current sources when necessary.

Priority research areas:

1. Current DCS terrain directory structures.
2. Current RasterCharts formats and indexing.
3. Theatre coordinate/projection definitions.
4. `coord.LOtoLL` / `coord.LLtoLO` availability and limitations.
5. `land.*` scripting functions and execution contexts.
6. Export.lua versus mission scripting environment limitations.
7. Existing coordinate-conversion implementations.
8. Existing moving-map/GIS projects.
9. Extractability of roads/scenery/vector information from terrain files.
10. Suitable open GIS/DEM sources and their licences.
11. Spatial Python libraries and formats appropriate to the implementation.

Useful source categories:

- Eagle Dynamics forums;
- DCS installation files;
- Hoggit DCS World Wiki;
- GitHub;
- DCS community project documentation;
- OpenStreetMap documentation;
- Copernicus/open elevation documentation;
- GIS/QGIS/GDAL documentation.

When forum posts disagree, reproduce the behavior against the installed DCS version.

---

# Definition of Success for Version 0.1

Version 0.1 does not need AI.

It succeeds if, for a selected test region, this works reliably:

```python
context = world.describe_position(
    theatre="Syria",
    dcs_x=...,
    dcs_z=...
)
```

and returns enough verified structure that a later system could truthfully say something like:

> Position is on the western side of the valley, approximately 700 metres south of the village, close to the north-south road. A ridge rises roughly 1.5 km to the west.

The important words are **truthfully** and **reliably**.

Once that foundation exists, Mission Interpreter and Petrobrain become much more tractable.
