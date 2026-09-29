---
name: terrain-feature-probing
description: Redesign of live terrain probing around ridge/valley knowledge (not LOS) — the M8 pipeline was already built and unused, and the real consumer needs far less than the original tiered scheme
metadata:
  type: project
---

`plans/terrain-feature-probing/plan.md` (2026-09-29), redirected from `plans/live-terrain-sampling/
design-input.md` once the user chose DCS-driven LOS (X-B29) and terrain probing lost its urgency.

- **`build.pipeline.add_probe_chunk` (M8) was already fully built and tested, and had zero live
  callers** — it ingests a chunk's elevation+surface_type, writes tri-state coverage, and re-runs
  M6's curvature classifier per chunk, all unmodified by this plan. The entire gap between "M6 has
  never produced a ridge/valley feature in any built theatre" and having one was the missing live
  data path (Hook script + collector endpoint + Mac-side puller), not the storage/classification
  layer. Always `grep -rn add_probe_chunk` before assuming a probe-store feature needs new
  plumbing below the collector.
- **The only real consumer (`body-layer/src/belief/enrichment.py`, `NEAR_RADIUS_M["ridge"/
  "valley"] = 1000.0`) needs a coarse 1 km ambient-proximity fact, not tactical masking.** This
  single number is why the original four-tier fine/medium/coarse/9K113-FOV scheme
  (`design-input.md`) was over-built once LOS stopped being the customer — check what a feature's
  actual consumer gates on before sizing a data pipeline for it.
- **M6's curvature threshold (`DEFAULT_CURVATURE_THRESHOLD_M = 20.0`) was tuned empirically against
  a 500 m grid**, and its own research note (`world-model/research/2026-09-05-m6-terrain-
  semantics.md`) says the checkerboard noise it fights is a genuine Nyquist-floor signature that a
  denser grid would address — not yet validated against the M8-locked 100 m spacing, because no
  live probe has ever produced real 100 m data. Don't assume finer spacing fixes it; the first live
  sortie under this plan is the first chance to look, and a retune may be needed exactly as M6's
  own Stage 2 needed one.
- **`getSurfaceType` (DCS's own LAND/WATER/ROAD/RUNWAY/SHALLOW_WATER enum) has zero consumers
  anywhere in body-layer or mission-interpreter**, despite being ingested since M5. It does not
  answer "desert/forest/plain/settlement" — OSM `landcover`/`settlement` polygons already do, and
  are already wired into `enrichment.py`'s `inside_landcover`. Don't let a user's "or is that
  already in world model?" question about terrain character be answered by `getSurfaceType`; check
  OSM landcover first — it's the richer, already-wired source.
- Related: [[project_dcs_driven_los_design]], [[project_dcs_driven_los_revision]],
  M8 store facts in [[project_grid_tier_hazard]].

**REVISED same day, after the user named the actual consumer** (crew-facing callouts — "at the
foot of the hill", "next valley" — plus a later, explicitly-deferred navigation want — "follow
that valley", "stay north of ridge"). This changed the plan more than the priority:

- **M6's existing `LineString` ridge/valley representation (ordered principal-axis polyline +
  `elevation_range_m`/`orientation_deg`/`cell_count` tags) already carries what both the callout
  and the later navigation consumer need — checked, not assumed.** The ordered polyline is already
  an axis (serves "follow"); `geometry.signed_side_of_polyline` already exists and is already
  proven on this exact geometry shape for coastline's sea/land side (serves "stay north of");
  `elevation_range_m` already lets a query point be compared against the feature's own height band
  for a foot/slope/crest approximation (serves "at the foot of"). No representation change, no
  fork between the two consumers. Before assuming a stored feature's shape can't support a
  use case, read what `to_stored_features`/`extract_components` actually emit and what else in the
  codebase already operates on that shape (`geometry.py` had both primitives this needed, already
  built for an unrelated feature).
- **The real gap was never "no data source" — it was that `build/pipeline.py`'s terrain-semantics
  stage only ever runs when `probe_output_path` (the DCS-probe grid) is supplied, never against the
  always-present whole-theatre SRTM grid.** `syria-full` has had full SRTM coverage since M7
  (591,732/639,216 points, 1,000 m spacing) and M7 explicitly deferred running M6's classifier
  against it. Once the named consumer turned out to be static, landmark-scale geography (not
  fine/dynamic LOS-grade terrain), the fix became "un-gate an existing offline pipeline stage and
  run it once" — no live probing, no sortie, no new Hook script. Always check whether an
  already-built offline pass is one small gate away from answering a "we need live data" ask
  before designing new live infrastructure.
- **A named use case ("3 o'clock, at the foot of the hill") and an existing but unwired backlog
  item (BL-B14, body-layer's bearing gap for roads/water) turned out to need the exact same
  missing primitive** (`geometry.bearing_deg` wired into `describe_position`'s feature-info
  output, which already has the bearing function but has never used it for any feature kind).
  Build such a mechanism generically once rather than per-feature-kind, and check sibling backlog
  items for the same gap before building a narrow version.
