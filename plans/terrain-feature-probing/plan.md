# Terrain feature probing — redesign around named-landform knowledge, not LOS

Dated 2026-09-29, revised same day after the consumer was named concretely. Supersedes
`plans/live-terrain-sampling/design-input.md` as the design; that file stays as the record of the
user's original LOS-driven scheme, most of which does not survive below.

### Goal

Give Petrovich the ability to reference named terrain features in crew callouts — *"contact, three
o'clock, 2 km, at the foot of the hill"*, *"armor, ten o'clock, next valley"* — and, later
(explicitly not this plan), to take terrain-relative navigation instructions from the pilot
(*"follow that valley"*, *"stay north of ridge"*). Line of sight is not touched by this plan
(`plans/dcs-driven-los/plan.md`, X-B29 already removed that dependency).

### Effort/value verdict — the consumer changes the shape of the build, not just its priority

Two user decisions landed while this plan was drafted and they reorder everything below:

1. **`getSurfaceType` is dropped.** Considered and rejected: DCS's own enum
   (`LAND/SHALLOW_WATER/WATER/ROAD/RUNWAY`) doesn't answer "desert/forest/plain/settlement", and
   OSM's `landcover`/`settlement` polygons already do (44,811 + 26,182 rows, already wired into
   `body-layer/src/belief/enrichment.py`'s `inside_landcover`). No new grid kind, no new field,
   nothing to build.
2. **The consumer is named, concretely**: crew-facing spatial reference in callouts, with a later
   (unbuilt) navigational want. This settles the "what consumes it" question the first draft of
   this plan had left open, and it changes the design in three ways at once:

**A. The scale is landmark-scale, not curvature-noise-scale.** A hill or valley a pilot calls out
by name is hundreds of metres to kilometres across — not the fine local relief M6's checkerboard
problem was fighting at 500 m. This is real evidence for the user's own instinct that spacing could
relax, and it changes *which* grid answers the question, not just how coarse it can be (see C).

**B. The representation needs axis + relationship, not a per-cell flag — and M6's existing
`LineString` output already has both, unmodified.** *"At the foot of the hill"* needs a position
relative to a landform (foot vs. slope vs. crest), and *"next valley"* needs an ordering along a
bearing. Checked against what `terrain/features.py::to_stored_features` actually emits, not
assumed: each ridge/valley is a `LineString` — an ordered principal-axis polyline through a
connected curvature component — carrying `elevation_range_m`, `orientation_deg`, and `cell_count`
tags. That is:

   - **An axis with direction, already**, for the deferred *"follow that valley"* — `points[0]`
     to `points[-1]` is an ordered line, not a blob, precisely because `extract_components`
     projects cells onto the principal axis and sorts by that projection before storing them.
   - **A line with a side-of test, already available elsewhere in this codebase** for the deferred
     *"stay north of ridge"* — `geometry.signed_side_of_polyline(p, points)` exists today and is
     already proven on exactly this kind of `LineString`, for coastline's `"sea"`/`"land"` side
     determination (`query/describe.py`'s `nearest_coastline`). Reusable unchanged against a
     ridge/valley `LineString`.
   - **A cheap, existing-data approximation for "foot"/"crest"**, for *now*: compare the query
     point's own elevation (`describe_position`'s `elevation.dcs_m`, already computed) against the
     feature's stored `elevation_range_m` tag. Near the low end of the range and near the line ->
     "at the foot"; near the high end -> "on the ridge"/"crest"; in between -> "on the slope of".
     No new extraction, no footprint polygon — this reuses a field M6 already stores and has never
     been read by anything.

   **What this representation cannot do, stated plainly**: it has no true footprint/extent boundary
   (so "foot" is an elevation-band approximation along a line, not a mapped edge), and no stable
   per-landform name (`name` is `None` on every ridge/valley row today; each is anonymous,
   distinguishable only by `source_ref` like `"valley_3"` — fine for *"next valley"*'s ordering, not
   for a proper name if one is ever wanted). Neither gap blocks either consumer, so neither is built
   here.

   **The two consumers do not pull apart.** Checked, not assumed, per the instruction to verify
   rather than guess: the callout use needs distance + bearing + elevation-band comparison against
   the existing tags; the deferred navigation use needs the ordered polyline (already the axis) and
   `signed_side_of_polyline` (already built, already proven on this exact geometry shape
   elsewhere). One representation, unmodified, answers both. **No fork, no representation decision
   forced by this plan** — the existing M6 output already carries what both consumers need.

**C. Landmark-scale terrain is static theatre geography, and fog-of-war is very likely the wrong
frame for it.** Nothing about a hill's location changes mid-sortie. The only reason
`design-input.md`'s live in-flight probing existed was LOS's need for range-dependent accuracy,
which is gone. Checked against the actual pipeline rather than assumed: `build/pipeline.py`'s
terrain-semantics stage (`ingest_terrain`) **only ever runs when `probe_output_path` is supplied**
— gated on the DCS-probe grid specifically, never on the always-present SRTM grid. `syria-full`
(the real theatre, per `world-model/ROADMAP.md`'s M7 entry) has full SRTM coverage already
(591,732/639,216 points, 92.6%, at **1,000 m** storage spacing) and **has never had `ingest_terrain`
run against it at all** — M7's own scope explicitly deferred "M6's terrain classifier" for the
whole-theatre build. **So the actual gap is not "no live data source exists" — it is "the
already-existing whole-theatre SRTM grid has never been fed to the ridge/valley classifier."**
That is an offline, one-command, no-sortie fix.

**Recommendation: drop live in-flight probing from this plan entirely.** Run `ingest_terrain`
against the SRTM base grid theatre-wide, offline, once. If 1,000 m turns out too coarse for
landmark-scale detection (see "What must be validated" below), the cheapest lever is re-ingesting
SRTM at a finer *storage* spacing — `DEFAULT_SRTM_GRID_SPACING_M` is an ingest-time choice, and
SRTM's own native resolution (~30-90 m) is far finer than what is currently stored, per
`build/pipeline.py`'s own comment — **not** a new live DCS probe. The M8 probe store and
`add_probe_chunk` stay exactly as built, unexercised by this plan, available to a future consumer
that genuinely needs finer-than-SRTM or in-flight-accumulated terrain data. None exists today.

### What survives from `plans/live-terrain-sampling/design-input.md`

Almost nothing, and that is the honest finding, not a gap in this plan. The tiered fine/medium/
coarse/9K113-FOV scheme, the separate probe-store SQLite file, the "never resample coarser" rule,
and the fog-of-war framing itself were all sized for LOS-at-range or for in-flight densification.
With the consumer now named as static landmark-scale callouts, none of that machinery is the right
shape — it already exists (M8), untouched, for whenever a real consumer needs it.

### Affected Modules / Files

- `world-model/src/build/pipeline.py` — un-gate the terrain-semantics stage from
  `probe_output_path`: run `ingest_terrain` against whatever `"elevation"` grid is present
  (SRTM-primary for a theatre build) rather than only the DCS-probe grid. Small, mechanical change
  to an existing conditional; `ingest_terrain` itself is untouched.
- `world-model/src/terrain/curvature.py` — `DEFAULT_CURVATURE_THRESHOLD_M` almost certainly needs a
  new empirical value for 1,000 m SRTM data (tuned at 500 m today); `DEFAULT_MIN_CELL_COUNT`
  likewise. Offline retune against real `syria-full` data, mirroring M6 Stage 2's own sweep
  methodology exactly — no structural change, a constant plus a research note.
- `world-model/src/query/describe.py` — add bearing to feature-info dataclasses (reusing
  `geometry.bearing_deg`, already implemented, currently unused by `describe_position` for any
  feature kind) and a new bearing-sector, distance-ordered query (e.g.
  `nearest_features_in_bearing(conn, kinds, x, z, bearing_deg, half_width_deg, limit=N)`) for
  *"next valley"*'s ordering. **This is the same gap `body-layer/BACKLOG.md`'s BL-B14 already
  named for roads/water** ("no such bearing... a `describe_position` change in world-model") — do
  it once, generically over feature kind, rather than twice. See Decision 2.
- `body-layer/src/belief/enrichment.py` — new semantic-fact shape carrying bearing + a foot/slope/
  crest label derived from the elevation-band comparison above. Follows the same
  `_proximity_text`/`NEAR_RADIUS_M` pattern ridge/valley already uses; extends rather than forks it.
- `body-layer/src/belief/speech.py` — wording for the new fragments (o'clock/bearing phrasing,
  "at the foot of", "next valley"), same cheap-wording-change class as `BL-B14`'s already-shipped
  items.
- **Not touched by this plan**: `world-model/src/probe_store/` (M8, all of it), `aircraft-layer`
  (no new Hook script, no new endpoint — nothing live-probing related), `terrain/features.py`
  (representation is reused unmodified, per the verdict above), `query/line_of_sight.py`.

### Implementation Plan

1. **Stage 1 — un-gate ridge/valley extraction from the probe grid; run it against `syria-full`'s
   real SRTM data, offline.** Mechanical pipeline change plus one real rebuild. **Flyable/checkable
   acceptance, no sortie needed**: `syria-full.sqlite` gains real `ridge`/`valley` rows for the
   first time ever (currently zero, in any built theatre); `tools/inspect_terrain.py` run against
   the result shows whether 1,000 m spacing resolves anything landmark-scale, or whether it's too
   coarse/too noisy to be useful — this is the empirical check the "what must be validated" section
   below requires, and it costs a rebuild, not a flight.
2. **Stage 2 — retune the curvature threshold for whatever Stage 1's real data shows**, following
   M6 Stage 2's own sweep-and-record methodology. If 1,000 m proves structurally inadequate (not
   just needing a different threshold — genuinely too coarse to resolve a landmark-scale feature at
   all), the fallback is a finer SRTM *storage* spacing re-ingest (still fully offline, no DCS
   probe), not a live-probing build. Record whichever outcome in a research note per this
   subproject's own convention.
3. **Stage 3 — bearing + ordered-along-bearing query in `describe_position`.** Wire
   `geometry.bearing_deg` into the ridge/valley (and, since it's the same mechanism, road/water —
   coordinate with BL-B14 rather than duplicating) feature-info dataclasses; add the bearing-sector
   nearest-N query for *"next valley"*. Pure query-layer addition, no store schema change, no new
   extraction.
4. **Stage 4 — the callout itself.** `enrichment.py`/`speech.py` wiring for foot/slope/crest
   phrasing and o'clock bearing, using Stage 3's new fields. **Flyable acceptance**: fly near a real
   extracted ridge/valley and confirm a callout like the user's own examples is producible from the
   pipeline's actual output, not a hand-built fixture.
5. **Not this plan**: navigation (*"follow that valley"*, *"stay north of ridge"*) — no stage, no
   API surface, no speculative field. The representation chosen above (unmodified M6 output) is
   confirmed able to answer both `signed_side_of_polyline`-style side questions and axis-following
   later, but nothing is built toward it now, per the instruction not to half-build a surface
   nobody reads yet.

### What must be validated before trusting it

Two real unknowns, neither assumable:

- **Does 1,000 m SRTM spacing resolve landmark-scale ridges/valleys at all, or does the classifier
  need retuning (or a finer re-ingest) to say anything useful?** M6's own finding (500 m grid)
  correctly caught the single most dominant peak/trough in-bbox but missed secondary ones and
  checkerboarded on rough terrain; whether a *coarser* grid does better (fewer, bigger, more
  landmark-appropriate components) or worse (loses real hills between samples) is genuinely
  unknown until Stage 1's real rebuild is looked at with `inspect_terrain.py`, exactly as M6 Stage 2
  looked at 500 m.
- **Whether `syria-full`'s SRTM coverage is dense enough everywhere a pilot might fly** — 92.6%
  point coverage per M7's own numbers, with the gap's spatial distribution not re-checked here.

### Risks & Unknowns

- **Curvature threshold retuning may take more than one pass**, same as M6's own 3.0 m -> 20.0 m
  multi-point sweep — this is expected work, not a sign the approach is wrong.
- **The foot/slope/crest elevation-band approximation can be wrong at the edges of a component's
  `elevation_range_m`** (e.g., a long ridge whose ends sit much lower than its middle) — flagged as
  an approximation, not a mapped boundary, from the start; acceptable for a callout, not for
  anything that needs to be exact.
- **Bearing-sector "next valley" ordering needs a concrete half-width** (how wide a cone counts as
  "that direction") — a design constant, not yet chosen; see Decision 3.
- **`add_probe_chunk`/M8 now has no scheduled consumer at all.** Recorded plainly rather than
  quietly abandoned: it remains correct, tested infrastructure for a live/fine-grained terrain need
  that no current plan asks for. Not a defect of this plan; a note for whoever next reaches for it.

### Second-order effect

This gives M6's ridge/valley extraction its first real output in the actual theatre (`syria-full`),
not just the small `latakia-20km` test region — closing a gap M7 explicitly deferred rather than
solved. It also means a future navigation plan (*"follow that valley"*) starts from real,
already-extracted geometry rather than nothing, and this plan has checked (not assumed) that the
representation it inherits can carry that later use — so that plan is a query/behavior addition,
not a re-extraction. It narrows `docs/concept/PETROBRAIN_RUNTIME.md`'s "expanding known-area
bubble" section to apply only to genuinely dynamic/fine-grained future needs, since the
landmark-naming need that section partly motivated is now served offline instead.

### Decisions — SETTLED (user, 2026-09-29), except one that turned out to be a question

- ~~**Confirm dropping live in-flight probing**~~ **SETTLED: dropped.** The user's own reasoning,
  which names why the live design existed at all and why it dies with LOS:

  > *"The slowly accumulating probe model was primarily for the very fine mesh that LOS would have
  > required. That would take tons of time and disk space if built into world model for the whole
  > theatre. If we process a more sparse grid directly into ridges and valleys etc, then that's a
  > viable one time operation cost."*

  So live accumulation was never the point — it was the only affordable way to get a *very fine*
  mesh, and LOS was the only consumer needing one. Landform extraction needs far less, and a
  one-time offline pass is affordable. `plans/live-terrain-sampling/design-input.md` is superseded
  for this purpose; M8's probe store stays built and unexercised for whenever something genuinely
  needs finer-than-SRTM or in-flight terrain.

- ~~**Bearing mechanism: coordinate with BL-B14**~~ **SETTLED: build it once here, and retire
  BL-B14's separate item.** User: *"Ok to retire BL-B14 when doing this."* So this plan's bearing
  work is generic across feature kinds — roads and water included, not ridge/valley only — and
  `body-layer/BACKLOG.md`'s BL-B14 road/water bearing entry closes when it lands rather than being
  built twice.

- **Storage spacing: 1000 m is rejected.** User: *"1000 m is too coarse, an entire mountain can fit
  inside it."* Correct, and it means Stage 1's un-gating alone is not sufficient — the classifier
  would run, but over a grid too coarse to resolve what it is looking for.

  **The distinction that keeps this cheap, raised after the plan was written:** the resolution the
  curvature classifier *processes* at and the resolution the store *keeps* need not be the same.
  SRTM is 30-90 m native, so a finer ingest costs no new data acquisition — and if the fine grid is
  consumed to produce ridge/valley `LineString` features and then **not stored**, the disk cost is
  the features, not the mesh. That is exactly the user's "process a more sparse grid directly into
  ridges and valleys" as a one-time operation. Sizing for reference: `grid_sample` is 12.2 MB of the
  589 MB store at 1000 m; ~210 MB at 250 m; ~1.3 GB at 100 m — all of which is avoidable for the
  landform purpose if the working grid is transient.

  **Open, and the thing Stage 1 must answer with real output:** what processing spacing actually
  resolves a landform a pilot would name, and whether M6's curvature thresholds (tuned at 500 m)
  need retuning at that spacing. `tools/inspect_terrain.py` against the first real run is how M6
  settled this before.

- **"Next valley" — the sector question was malformed, and the underlying ambiguity is real.**
  The plan proposed a bearing-sector half-width. Put to the user, he asked what that meant, and
  restating it surfaced that his example admits two readings needing different machinery:

  1. **Ordering along a ray** — from ownship, landforms crossing the bearing to the contact at
     increasing range; *"next"* = the second one out. This is what a sector half-width is for:
     how wide a wedge counts as "that direction".
  2. **Adjacency** — ownship is in one valley, the contact is in the one over the ridge. *"Next"*
     means neighbouring, not further along a line. **No sector at all** — it needs valley-to-valley
     adjacency, which is a different derived relation and not currently produced by anything.

  His phrasing (*"armor, 10 o'clock, next valley"*) reads as (2). **Unresolved pending his answer**;
  do not build either until it is settled, since (2) needs a relation M6 does not emit today.
