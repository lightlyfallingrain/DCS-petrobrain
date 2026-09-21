# M9 — tactical landmarks recon: settlement extents + road-junction derivability

**Date:** 2026-09-12
**DCS version:** 2.9.29.27278 (per M0) — this session used already-extracted local
files (`world-model/data/raw/dcs/syria/`, `world-model/data/world-model/latakia-20km.sqlite`),
no live DCS access. `DCS_INSTALL_PATH`/`DCS_SAVED_GAMES_PATH` are unset in this
environment — not on the DCS machine this session.
**Theatre:** Syria (whole-theatre `towns.lua`/file-listing check; `latakia-20km`
persistent store for the road-junction check)

### Question

Two narrow DCS-internals questions blocking the tactical-landmarks milestone plan:

1. Does the installed Syria terrain ship ANY file that gives settlements an
   area/extent (bounding box, radius, polygon) rather than just a `towns.lua`
   center point — or is OSM the only path to settlement boundary polygons?
2. Can road intersections be derived purely geometrically from `.routes`'
   already-decoded point arrays (coincident endpoints/interior points across
   separate route polylines), without needing the unresolved `.rn4` trailer
   field?

### Findings

**Q1 — no DCS-native settlement-extent source exists.**

- **`towns.lua`'s schema is confirmed to carry only three keys, theatre-wide,
  no extent field of any kind.** A full-file key scan of the local copy
  (`world-model/data/raw/dcs/syria/map/towns.lua`, 112,750 bytes) finds
  exactly `{latitude, longitude, display_name}` (plus the file's own
  `towns`/`gettext`/`_` scaffolding) — zero occurrences of `radius`, `bbox`,
  `extent`, `polygon`, `boundary`, or similar across all ~1,186 entries. —
  **evidence: reproduced-locally** — **source:** ad hoc Python key-scan
  against the local file this session.

  > **CORRECTION 2026-09-21 — "~1,186 entries" is the count this project already retracted
  > once.** `towns.lua` has exactly **1,182 entry lines** (1,151 unique names — 31 are
  > duplicates); 1,186 was that line count *minus one*, and there were never 4 unparseable
  > entries (`2026-09-03-m5-recon.md` addendum, findings 30 and 31, which say so in those words).
  > **The finding itself is unaffected** — no extent field exists, whatever the denominator. The
  > figure was reintroduced nine days after being corrected, which is the part worth noticing:
  > a retracted number in an addendum does not stop circulating just because the addendum exists.
- **No other file under `Mods/terrains/Syria/` (or any shared/`_Common`-style
  terrain location) is plausibly a settlement-extent source, by filename.**
  Grepped the full theatre file listing
  (`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`, ~7.5k entries) for
  `zone|city|cities|town|settlement|boundary|polygon|region|area|border|
  district|admin` under `Mods/terrains/Syria/` — the only hit is `towns.lua`
  itself. There is no `_Common` terrain directory shared across theatres in
  the install (checked: `Mods/terrains/<Theatre>/` are each self-contained;
  no sibling dir holds shared zone/settlement data). — **evidence:
  reproduced-locally (filename listing)** — this is necessarily a
  filename-level check, not file-content, for anything not already
  extracted/read.
- **The two other files under `map/` (`Syria.gn4`, `Syria.sup5`) are not
  settlement data.** Both are proprietary, undocumented ED binary formats
  used for the F10 paper-map/graticule rendering pipeline (`.sup5` is the
  same family already reverse-engineered in M2's RasterCharts investigation
  — `2026-09-03-m2-rastercharts-recon.md` — where it was confirmed to be a
  general-purpose ED engine manifest/index type, not registration or extent
  data, and every `Map/<Terrain>.sup5` across all installed theatres shares
  that same header signature).
  > **CORRECTION 2026-09-21 — the M2 note says neither of those things.** Both halves of this
  > parenthesis upgrade an explicitly-hedged inference into a "confirmed" fact:
  > - M2 (session 2) records *"absence of registration data specifically inside `.sup5` **remains
  >   unconfirmed, not ruled out**"* — only the first 64 bytes of the file were ever read, with
  >   615,152 bytes left unread — and describes the manifest/index reading as *"inference from
  >   naming/sibling-pattern only, **not content inspection**."*
  > - **No other theatre's `.sup5` header was ever parsed**, so "every `Map/<Terrain>.sup5` across
  >   all installed theatres shares that same header signature" has no evidence behind it at all.
  >
  > This does not change M9's conclusion — `.sup5` is still not a settlement-extent source on the
  > available evidence, and the bullet's own evidence tag correctly says `inferred`. What went
  > wrong is between the tag and the prose: **the citation supplied the confidence the evidence
  > line withheld.** A hedge survives one hop and dies on the second, which is exactly what a
  > knowledge-graph query does to a document — it hands you the sentence, not the qualifier three
  > paragraphs away in the file it cites.

  `.gn4` is undocumented anywhere community-wide
  and was not decoded this session (out of scope: its directory/naming
  strongly implies map-display graphics, not semantic town-boundary data,
  and M2 already established this file family doesn't carry extent
  semantics). — **evidence: forum-claim-unverified for `.gn4`'s exact
  purpose; inferred (by naming/co-location/prior `.sup5` finding) that
  neither is a settlement-extent source** — **source:**
  `2026-09-03-m2-rastercharts-recon.md`, this session's file listing.
- **`MissionGenerator/nodes.lua`/`nodesMap.lua` were already ruled out** in a
  prior session (`2026-09-03-m5-recon.md` Findings 27-28): `nodes.lua` is not
  a road/waypoint graph, and `nodesMap.lua`'s single `theatre.nodesMapBorders`
  field is one whole-theatre bounding box (mission-generator working
  envelope), not per-settlement extents, and was separately falsified as even
  a theatre-extent source in `2026-09-05-m7-syria-theatre-extent.md`. Not
  re-investigated this session — citing the settled prior finding.

**Conclusion: no DCS-native settlement-extent source exists.** Every terrain
Lua/data file under `Mods/terrains/Syria/` has now been either read in full
(`towns.lua`, `nodes.lua`, `nodesMap.lua`, `entry.lua`) or ruled out by
filename/prior-format-decode (`.gn4`/`.sup5`, `.rn4`/`.routes` — road
geometry, not settlement polygons). OSM (geofabrik, per the deferred M9 plan)
remains the only path to real settlement boundary polygons for Syria.

**Q2 — road junctions ARE derivable purely geometrically from `.routes`
point arrays, at effectively zero tolerance (bit-exact float64 coincidence),
no `.rn4` trailer field needed.**

Ran directly against the already-built `latakia-20km.sqlite` persistent store
(3,266 `road` features, each `geom_json` a `.routes`-derived point-array
polyline, `source_ref` citing its originating `.routes` byte offset per
`2026-09-04-m5-roadnet-byte-decode.md`'s parser) — no live DCS or raw-file
walk needed, since the store already holds every relevant point coordinate
extracted from `Syria.routes`.

- **Endpoint-to-endpoint junctions**: of 6,532 route endpoints (start+end of
  3,266 roads), a grid-bucketed all-pairs proximity scan found **1,315
  distinct endpoint pairs at exactly 0.0 m separation** (bit-identical
  float64 x/z) — vs. only **85 pairs in the 1.4–5.0 m range** and *none*
  between 0.0 and 1.4 m. The gap between "exact" and "1.4 m+" is clean: there
  is no continuum of near-misses requiring a tolerance decision, just
  bit-exact matches (true junctions) and unrelated nearby endpoints (not
  junctions). — **evidence: reproduced-locally**.
- **Endpoint-to-interior-point junctions (T-junctions)**: same technique
  against every interior vertex (not just endpoints) of every other route
  found **3,700 pairs** where one road's endpoint lands exactly (`< 1e-6 m`)
  on a non-endpoint vertex of a different road — i.e. a road terminating
  mid-span of another, the classic T-junction case that endpoint-only
  matching would miss. — **evidence: reproduced-locally**.
- **Three concrete examples (DCS x/z metres, `latakia-20km` region, feature
  ids from the local store)**:
  1. **4-way endpoint cluster** at `(x=54552.8857, z=-3538.5341)` — road
     feature ids 3671 (start), 3672 (end), 3703 (end), 3704 (start) all share
     this exact coordinate pair-wise (all pairwise distances `0.0`).
  2. **3-way endpoint cluster** at `(x=51292.1999, z=120.2702)` — feature ids
     125 (start), 176 (start), 733 (end), again exact `0.0` pairwise.
  3. **T-junction** — feature 127's end vertex `(x=45848.5384, z=2829.3583)`
     lands exactly on feature 720's interior vertex index 1 (of 10 total
     points), distance `< 1e-6 m`.
- **No tolerance beyond float64 exact-equality is needed.** The 85
  near-but-not-exact matches in the 1.4–5 m band look like coincidental
  proximity of unrelated road endpoints (e.g. parallel roads a few metres
  apart), not junctions with slightly-differing authored coordinates — they
  were not individually visually/topologically confirmed as non-junctions
  this session, so treat that specific claim as **inferred**, not
  fully verified.

**Conclusion: junctions are geometrically derivable from `.routes` alone, via
exact (bit-identical, effectively 0 m tolerance) coordinate matching between
one route's endpoint and another route's endpoint or interior vertex.** This
is strong evidence DCS's own road-authoring tool snapped junction vertices to
shared coordinates rather than storing them as independently-surveyed
near-duplicates — a materially better result than the "small tolerance
needed" the question anticipated. The `.rn4` trailer's unresolved per-point
int32 field (speculated "is-intersection" in
`2026-09-04-m5-roadnet-byte-decode.md`) is **not needed** for this purpose.

### Reproducible Test

Both checks used short ad hoc Python scripts against files already present in
this checkout — no DCS access, nothing persisted as a repo artifact (trivial
to reconstruct from the recipe below).

**Q1**: `set(re.findall(r'(\w+)\s*=', open(<towns.lua>).read()))` against
`world-model/data/raw/dcs/syria/map/towns.lua`; `grep -iE
'zone|city|cities|town|settlement|boundary|polygon|region|area|border|
district|admin'` against `Mods/terrains/Syria/`-scoped lines of
`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`.

**Q2**: against `world-model/data/world-model/latakia-20km.sqlite`:
```python
import sqlite3, json
from collections import defaultdict
from math import floor

con = sqlite3.connect("data/world-model/latakia-20km.sqlite")
rows = con.execute("select id, geom_json from feature where kind='road'").fetchall()
roads = {fid: json.loads(g) for fid, g in rows}

# endpoints: (fid, which, x, z); interior index test excludes idx in {0, len-1}
# grid-bucket at 50m cells, scan 3x3 neighborhood, threshold on euclidean
# distance in the (x, z) plane -- see Findings for exact counts/thresholds.
```
Full script bodies are reconstructable from the Findings section (grid cell
size 50 m, 3×3 neighbor search, distance thresholds 1e-6 / 1.0 / 5.0 m as
described above).

### Possible Approaches

**Q1 (settlement extents)**: proceed with the already-deferred M9 OSM
(geofabrik) plan for polygon boundaries — nothing found this session changes
that plan's premise. Two secondary options worth Architect's consideration,
neither DCS-native:
1. **Synthetic radius from town density/name-clustering** — approximate a
   settlement's "extent" as a radius derived from nearby `towns.lua` point
   density (e.g. distance to nearest other named point) as a cheap fallback
   when OSM coverage is thin for a given theatre (e.g. Kola). Crude, but
   needs no new dependency and generalizes across all theatres, unlike OSM
   coverage which the M8 recon already flagged as regionally uneven.
2. **Road-network-derived settlement footprint** — since Q2 confirms road
   junction topology is cheaply derivable, a settlement's built-up extent
   could be approximated as the convex hull (or road-density hot-spot) of
   the local road-junction cluster around its `towns.lua` point, entirely
   DCS-native, no OSM dependency. Untested this session; flagged as a
   promising but unverified idea, not a recommendation.

**Q2 (road junctions)**: GO — build junction detection directly on the
existing `latakia-20km`/`syria-full` stores' `road` features using exact
(or near-zero, e.g. `< 1 cm`) coordinate-equality clustering across distinct
`road` feature endpoints/interior vertices. No new DCS extraction or `.rn4`
trailer decoding is needed for this milestone. A production implementation
should:
1. Union-find/cluster endpoints (and interior vertices flagged as junction
   candidates) by exact coordinate equality (or a tiny epsilon, e.g. 1 cm, to
   absorb any floating-point noise from the parser's `float64` reads —
   this session saw effectively-zero, not merely small, distances, so 1 cm
   is generous headroom, not a load-bearing tolerance decision).
2. A junction node = a coordinate shared by ≥3 distinct road-feature
   endpoints/vertices (or by exactly 2 where one is a T-junction against the
   other's interior) — degree-2 endpoint-to-endpoint matches where both
   routes only continue through each other (no branching) may just be an
   artifact of how DCS splits one physical road into multiple `.routes`
   polylines, not a real intersection; Architect should decide whether
   degree-2 coincidences count as "junctions" for the tactical-landmarks
   feature, or should be filtered out as same-road continuations.

### Unresolved

- **The 85 near-(1.4–5 m)-but-not-exact endpoint pairs were not individually
  characterized** — plausibly coincidental proximity of unrelated roads
  (e.g. parallel carriageways), but this was not confirmed by inspecting
  their actual road geometry/context. Low priority: doesn't block Q2's
  overall conclusion, since the exact-match population alone is already
  enough evidence and volume (1,315 + 3,700 pairs) for junction detection.
- **Q2's check used only the `latakia-20km` region's already-extracted
  store, not a fresh, independent walk of the raw `Syria.routes` file.**
  This is a reasonable trust boundary (the store's road features are
  themselves a direct, previously-validated decode of `.routes`, per
  `2026-09-04-m5-roadnet-byte-decode.md` and `2026-09-04-m5-stage4-
  validation.md`), but if Architect wants belt-and-suspenders confirmation
  against a wholly independent parse (e.g. to rule out a store-build-time
  bug rather than a `.routes`-format fact), that would need a fresh
  `iter_routes` walk restricted to the same bbox and a re-check — not done
  this session because the store already gave a clean, decisive answer.
- **Whether degree-2 endpoint coincidences represent real intersections or
  are an artifact of how DCS splits single physical roads into multiple
  `.routes` polylines** is a design question for Architect (see Possible
  Approaches item 2), not resolved here.
- **`.gn4`'s exact format/purpose remains fully undocumented** — not decoded
  this session, on the judgment that its co-location with the already-solved
  `.sup5` family and its clear "map display" naming make it low-priority
  for the settlement-extent question specifically. If Architect ever wants
  F10-map-derived data for a different reason, this would need its own
  investigation.
