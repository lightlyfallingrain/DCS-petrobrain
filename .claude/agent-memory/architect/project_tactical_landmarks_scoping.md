---
name: tactical-landmarks-scoping
description: 2026-09-12 plan resolving whether world-model content is rich enough for Mission Interpreter — ridge/valley/flat, settlement boundaries, road junctions, other landmarks
metadata:
  type: project
---

Plan: `plans/world-model-tactical-landmarks/plan.md`. Triggered by the user reassessing
world-model content richness before MI-2 (Mission Interpreter's world-enrichment stage).

**Durable facts worth remembering for future world-model planning:**

- **Settlement extent has no DCS-native source.** `towns.lua` has exactly 3 keys
  (`latitude`, `longitude`, `display_name`) theatre-wide — verified by full-file key scan
  during this session's investigator run. OSM (via M9/geofabrik) is the only path to
  settlement boundary polygons. Don't re-investigate this; it's settled.
- **Road junctions are cheaply derivable from the existing `.routes`-based `road` layer,
  zero new dependency.** DCS's road-authoring tool snaps junction vertices to bit-identical
  coordinates — confirmed against the real `latakia-20km.sqlite` store (1,315 exact
  endpoint-endpoint pairs at 0.0 m, 3,700 endpoint-on-interior-vertex T-junction matches, clean
  gap before the next-nearest band at 1.4-5 m). No need for the unresolved `.rn4` trailer
  field once speculated as "is-intersection" — pure geometric vertex-clustering over
  already-parsed data suffices. See `world-model/research/2026-09-12-m9-tactical-landmarks-recon.md`.
- **M6's curvature classifier already computes a third class, `CurvatureClass.NEITHER`**
  (`terrain/curvature.py`), but `terrain/features.py`'s `extract_components` only groups
  RIDGE/VALLEY into features. Decided: don't build a new "flat" feature class — a flat area
  isn't a meaningful line the way ridge/valley are, and `nearby_ridges`/`nearby_valleys` both
  being `None` already means "flat" under the project's absence-as-absence rule. This should
  be a documentation clarification in `describe.py`, not new code, if it comes up again.
- **`kind="water"` features exist ONLY via `build/ingest_osm.py`** — no DCS-native vector
  water source exists in the store today (`nearest_water` is `None` theatre-wide, same gap
  class as settlements). This means anything built on "road crosses water" (e.g. bridge
  detection) is gated on M9 (OSM) landing first, not purely DCS-native like junctions are.
  Don't assume a DCS-native water layer exists without rechecking if this changes.
- **M9 (OSM/geofabrik augmentation) was reopened** by explicit user decision mid-session:
  "should M9 exist at all" is resolved to yes whenever scoping shows OSM is needed for
  landmark data DCS-native sources don't cover (settlement boundaries qualified). The
  remaining open sub-decision from M9's own plan (`plans/m9-osm-geofabrik/plan.md`) is still
  real and unresolved: `.osm.pbf` parsing — stdlib hand-roll vs `pyosmium` (world-model's
  first native-extension dependency if chosen). Don't silently pick one.
- **Store already supports everything settlement-polygon ingestion needs**:
  `store.reader.containing_polygons`/`point_in_polygon` and `build/ingest_osm.py`'s
  Polygon-emitting closed-way classification are M3-era code that already works — M9 is
  "feed it real data via a `.pbf` parser", not "build settlement polygon support from
  scratch". Don't re-derive this if re-scoping M9 again later.
- **`PositionDescription` is additive-only by design** — MI-2 (or any consumer) can build
  against today's schema and get richer answers later with zero client-side change, so none
  of this needs to block a downstream consumer's own build-out. Useful precedent for future
  "is X ready enough to build on" questions in this project.
