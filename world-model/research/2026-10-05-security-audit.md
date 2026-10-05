# world-model security audit — 2026-10-05

Mode 3 full-subproject audit. Target `main` @ `19143fa`. 72 Python files, ~12.3k lines in `src/`,
plus `tools/` and the committed run documentation.

**Threat model this is judged against** (stated up front, because severity is meaningless without
it): an offline build pipeline run by one user on their own machine, producing a `.sqlite` that
`body-layer` then opens **in-process on a live ~5 Hz flight tick**; a LAN-only, no-auth HTTP seam
to `mission-interpreter`; inputs that are semi-trusted but unvalidated (a DCS install, a 1 GB
Geofabrik download, SRTM tiles from a third-party mirror, DCS mission probe output); and a repo
**intended to go public open-source**. There are no credentials anywhere in this subproject and no
remote adversary in the current deployment. So the dangerous failure here is almost never "attacker
gains control" — it is **a wrong geographic answer the consumer cannot tell is wrong**, which in
this project is the no-omniscience invariant breaking in the quiet direction.

Accordingly §1 (provenance) is the substance of this audit. §5 lists what is explicitly **not** a
problem, so the rest reads as a filtered list.

Every behavioural claim below marked **[verified]** was reproduced by executing it, not inferred
from reading. Two claims that came back from a first pass were found overstated and are corrected
in place (2.3, 2.8) — noted so the list's error bar is visible.

---

## 0. What prompted this, and what the prior pass got wrong

`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` §3 measured, on a real
sortie: of 14,703 admitted contacts, **11,268 (77 %) were admitted on world-model's offline
SRTM-grid LOS primitive with its 12 m tolerance**, not on DCS's live verdict — the path the user
ruled obsolete for live use the same day.

`plans/dcs-driven-los/security-deep-analysis.md:109-121` had already named this exact mechanism and
rated it **low probability / low impact**, closing with "no action required now". Both halves were
wrong, and the reasoning error is reusable, so it is worth naming:

- **Probability** was assessed as "low — the Hook script would have to fail". The fallback does not
  require a *failure*; it fires whenever a unit has no fresh verdict this poll, which on a consumer
  loop running at ~0.7 Hz instead of 5 Hz is the **normal** case. The analysis enumerated the
  failure modes correctly and never asked what the steady state looked like.
- **Impact** was assessed as "low — reverts to the pre-existing, already-reviewed 12 m primitive".
  That rested on the primitive being an acceptable answer, and the user's direction that same day
  removed the premise: *"With DCS LOS, the item '12 m LOS tolerance' becomes obsolete and
  incorrect."* An impact rating that depends on another component's acceptability goes stale when
  that acceptability is withdrawn, and nothing re-ran it.

The standing backlog item **`WM-B3`** ("Measured data-quality figures need to reach their consumers,
not just a research note", still `[ ]`, "no fix scoped yet") is the general form. Findings 1.1-1.4
are its concrete, now-flight-confirmed instances and **1.6 is the fix that closes all of them at
once**. I am not re-filing WM-B3; I am scoping it.

---

## 1. Provenance, confidence and authoritativeness — fix now

The measuring stick is `src/query/describe.py:5-12`, this package's own contract:

> 1. Every geographic claim carries its provenance and its positional uncertainty, side by side
>    -- never collapsed into one undocumented fact.
> 3. Absence is reported as absence -- a `None` field, never a guess.

`describe_position` honours rule 1 thoroughly — thirteen `*Info` dataclasses, each carrying
`provenance` + `confidence` + `position_uncertainty_m`, and `grid_provenance()` exists precisely so
an SRTM grid is never reported as DCS-probed. That is the context for what follows: this is not a
subproject that neglected provenance. It is one that implemented provenance carefully in one
function and shipped siblings that drop it.

### 1.1 — `line_of_sight_clear` returns a bare `bool`. HIGH.

`src/query/line_of_sight.py:125-170`

```python
def line_of_sight_clear(conn, theatre, observer, target, *, samples=20) -> bool:
```

The return value carries **no source, no tolerance, no uncertainty, and no record of how many
samples were skipped for missing data**. A caller cannot distinguish any of:

- "clear, every sample had elevation from an SRTM grid with ±11.52 m stddev"
- "clear, because every interior sample returned `None` and was skipped" (`:164-166`, `continue`)
- "clear, within 12 m of being blocked"

The second is the worst and is not hypothetical: outside the built grid's coverage — and
`syria-full` has 7.4 % void cells (`points_sampled 591,732/639,216`) — **every sample can be skipped
and the function returns `True`**, i.e. "no evidence of terrain" rendered as "sightline is clear".
The docstring is explicit and correct that absence must not manufacture an outcome *either way*;
the `bool` return type then makes it do exactly that, because `True` is the admitting value at the
consumer.

**It is lost across a subproject boundary too**, so this is not body-layer-local:

| consumer | what it receives |
|---|---|
| `body-layer/src/perception/visibility.py:789` (gate 4 fallback) | bare `bool` |
| `world-model/src/api/server.py:203` | `{"clear": bool}` |
| `mission-interpreter/src/world_enrich/world_model_client.py:126-131` | asserts `isinstance(clear, bool)`, returns it |

The distinction *is* recoverable post-hoc, but only from `detection_trace`'s `live_los_clear`
column (`body-layer/src/perception/detection_trace.py:167`) — which is how §3 of the sortie analysis
computed the 77 %. Nothing in-band records it, and world-model could not supply it if asked.

**Fix:** return a frozen dataclass instead of `bool` — `clear: bool`, `source: str` (the store's own
`grid.provenance`), `tolerance_m: float`, `samples_evaluated: int`, `samples_skipped_no_data: int`.
`samples_evaluated == 0` then becomes a reportable fact rather than a `True`. Three call sites
change; `/line_of_sight`'s JSON gains fields rather than changing shape, so `world_model_client`
keeps working off `result["clear"]`.

### 1.2 — `_TERRAIN_TOLERANCE_M = 12.0` is a one-theatre calibration applied to every theatre. HIGH.

`src/query/line_of_sight.py:122`

The constant is sized, carefully and with 75 lines of justification, to **`syria-full`'s** measured
SRTM-vs-DCS error (`mean -7.19 m, stddev 11.52 m`, M7 theatre-wide). That derivation is sound. The
defect is that nothing ties the constant to the theatre or the source it was derived from:

- **Not keyed on theatre.** `Afghanistan` is a registered theatre
  (`src/coordinates/projections.py:52-70`) with a full build
  (`research/2026-10-05-afghanistan-theatre-build.md`, 5,721,763 SRTM points). That note's line 119
  records the DCS-probe cross-check as **"not attempted this session"** — Afghanistan's error has
  never been measured, and Syria's number silently governs its LOS. Not a theoretical drift: M4's
  Gemerek measurement was **stddev 28.02 m** (`ROADMAP.md` M4 entry), **2.4× the figure the constant
  is sized to**. Regional variance of that magnitude is already in this project's own data.
- **Not keyed on data source.** `grid.provenance` distinguishes `"srtm"` from `"dcs_probe"` and
  `store.reader.grid_provenance()` exists to read it — `line_of_sight_clear` never calls it. A
  DCS-probe grid (tighter error budget by construction) gets the same slack sized for SRTM. The
  constant's own comment anticipates this as future work; the finding is that today's code applies
  a *Syria/SRTM* number to *any* theatre and *any* provenance.
- **Not discoverable by a caller.** Module-private, not a parameter, not in the HTTP response, not
  in any return type. A consumer deciding whether to trust a verdict cannot learn it was loosened
  at all, let alone by how much.

HIGH rather than MEDIUM because the airframe argument that makes 12 m acceptable (*"the hind almost
never attacks from hover"*, user direction 2026-09-28) is an argument about **Syria + Mi-24P +
SRTM**, and the code applies the number outside all three without saying so.

### 1.3 — `ElevationInfo.confidence` is hardcoded `"high"` for a value known to be ±11.5 m. MEDIUM.

`src/query/describe.py`, the base-store branch:

```python
confidence="high" if dcs_elevation_m is not None else "unavailable",
```

`"high"` here means only "a number was returned" — the same literal whether the number came from a
DCS probe or from SRTM at 11.52 m stddev. And **there is no numeric uncertainty field on
`ElevationInfo` at all**: it has `source`, `confidence`, `external_m`, `delta_m`, `coverage`, with
`external_m`/`delta_m` documented as permanently `None`.

Grepping `src/` for any measured vertical-error figure returns nothing. `11.52` appears in
`ROADMAP.md` and five research notes and in **zero lines of code**; `grid.stats_json` holds only
counts (`points_expected`, `points_sampled`, `points_void_or_uncovered`, `tiles_used`). So rule 1's
"positional uncertainty, side by side" is satisfied for every *feature* field and unsatisfied for
the *elevation* field — the one the LOS gate consumes.

### 1.4 — Unknown positional uncertainty is reported as zero uncertainty. MEDIUM.

`src/query/describe.py`, **11 occurrences** (`:427,441,469,488,502,515,532,547,562,735,765`):

```python
position_uncertainty_m=feature.position_uncertainty_m or 0.0,
```

The source is `float | None` (`store/models.py:105`) over a nullable column
(`store/schema.py:59`); the target field is non-optional `float`
(`describe.py:208,224,240,254,269,284,293,305,316,339,355`). So a NULL uncertainty is delivered as
**0.0 m — a positive claim of perfect positional knowledge** — rather than "unknown". That is rule
3 inverted, and it matters behaviourally: `describe.py:115` instructs callers to hedge within
`position_uncertainty_m` of a feature (`nearest_coastline`'s `side` is explicitly unreliable there)
and body-layer's terrain qualifier does. At 0.0 nobody hedges.

Every current ingest path sets the field, so this is **latent, not live** — it fires on a store
built by older code, a partially written store, or any future ingest that omits it, and there is no
representation of "unknown" for it to fire into. The same module is otherwise scrupulous here
(`describe.py:392,396` use `.get(key, "unknown")`; `ingest_towns.py:21-23` deliberately *downgrades*
confidence rather than overclaim), which is what makes this read as an oversight.

**Fix:** `float | None` end-to-end.

### 1.5 — A `.routes` route that fails its own sanity check is stored as DCS-authoritative. HIGH.

`src/roadnet/routes.py:160-174`

```python
if not _directions_plausible(directions):
    stats.sync_loss_events += 1

stats.routes_found += 1
...
if bbox is None or _route_intersects_bbox(points, bbox):
    yield route
```

The failed check increments a counter and **falls through**. The route is yielded identically to a
valid one, and `src/build/ingest_roadnet.py:111-113` writes *every* yielded route as:

```python
provenance={"geometry": "dcs"},
confidence={"geometry": "high"},
position_uncertainty_m=0.0,
```

— the strongest provenance claim this store can make, asserted over a polyline the parser itself
judged implausible, with `orientation_deg` (`ingest_roadnet.py:106`) derived from exactly that data.
`sync_loss_events` surfaces only as an aggregate in `RoadnetIngestStats`.

**This has already happened in real data.** `src/roadnet/container.py:51-59` documents it: road
feature `id=3711`, `source_ref "route:3311@464953201"`, in the Latakia store, caught by a separate
validation pass (`research/2026-09-04-m5-stage4-validation.md` Finding 1), not by this counter. Two
weaknesses compound: `_directions_plausible` samples only indices `{0, len//2, len-1}`
(`routes.py:83`), and `_is_unit_vector`'s tolerance is `1e-3` on magnitude-squared (`routes.py:72-77`).

**Fix:** carry the flag on `RoutePolyline` so `ingest_roadnet` can write
`confidence={"geometry": "low"}`, a non-zero `position_uncertainty_m`, and a
`tags["directions_implausible"]` marker for that one feature. `source_ref` already cites the exact
byte offset, so the provenance channel exists and is good — only the confidence value is wrong.

### 1.6 — The pipeline computes the error figure its consumers need, and discards it. HIGH — and this is the fix for 1.1-1.3.

`src/build/validate.py:192-210`, `compare_probe_to_srtm`, returns an `ElevationAlignmentReport` with
mean/median/stddev/min/max of the DCS-vs-SRTM delta, correctly counting `points_skipped` rather than
letting voids skew it. **Its only caller is `tools/validate_m7_stage2_elevation.py`, which prints it
to stdout, which a human pastes into a research note.** Nothing writes it into the store.

That is the whole mechanism of `WM-B3`, visible in one call graph: the number
`_TERRAIN_TOLERANCE_M` is derived from is produced by this pipeline, in this subproject, and then
exists only as prose. Three weeks later a consumer treated the grid as exact and a real AAA
detection was missed.

**The fix is cheap and resolves 1.1, 1.2, 1.3 and WM-B3 together:**

1. `build.pipeline` writes the `ElevationAlignmentReport` summary into the elevation `grid` row's
   existing `stats_json` — no schema bump, it is already a JSON blob.
2. `store.reader` gains `grid_vertical_error_m(conn, kind)` beside `grid_provenance` /
   `grid_spacing_m`.
3. `ElevationInfo` gains `vertical_stddev_m: float | None` populated from it.
4. `line_of_sight_clear` derives its tolerance from the store rather than a module constant, and a
   store with no measured figure gets an explicit, *reported* "unmeasured" posture instead of
   Syria's number.

After that, a theatre built without a probe cross-check **cannot silently inherit another theatre's
error budget**, which is the actual defect in 1.2.

### 1.7 — A rejected probe store is reported as "no probe store". MEDIUM.

`src/query/describe.py:582-591`

```python
except ValueError:
    conn.execute("DETACH DATABASE probe")
```

`check_probe_paired_with_base` raises with a precise diagnosis — `probe_store/schema.py:227-233`
lists the mismatched fields by name — and it is discarded without a log line. `query/describe.py`
imports no logger at all. Downstream, `coverage` is reported as `_NO_PROBE_STORE = "no_probe_store"`
(`describe.py:156`), so **"a probe store for the wrong theatre was found and refused" reaches the
pilot-facing layer as "there is no probe store"**. The degradation behaviour is right (degrade, do
not crash); the *record* of it is missing, which is the same gap as 1.1 one level up.

**Fix:** `logger.warning` with the mismatch dict, and a distinct coverage string
(`probe_store_rejected`) so a consumer can tell the two apart.

### 1.8 — Missing SRTM tiles silently reduce coverage, with no requested-vs-found record. MEDIUM.

`src/build/pipeline.py:635-637`, `src/build/ingest_terrain.py:337` and `:175-176` all filter the
tile list by `p.exists()` and continue. A full-theatre build where some `.hgt` tiles failed to
download therefore **completes normally, reports `srtm_skipped = False`, and writes an elevation
grid and a ridge/valley layer with holes in them**.

`SrtmIngestStats.points_void_or_uncovered` (`ingest_srtm.py:66-69`) counts the *symptom*, which is
good — but `TerrainIngestStats.tiles_total` (`ingest_terrain.py:116`) counts only the tiles that
*existed*, so the requested-vs-found delta is unrecoverable from either the build report or the DB.
A 7.4 % void rate is indistinguishable from "SRTM genuinely has no data there".

**Fix:** a `requested_tiles` / `tiles_missing` pair in each stats dataclass plus a
`logger.warning` naming the absent files. The cache key is unaffected —
`combined_tile_hash(existing_paths)` changes with the set, so there is no stale-reuse risk here.

### 1.9 — Cache identity omits the theatre projection, and the one hand-maintained version key has already been missed once. MEDIUM.

`src/osm_cache/schema.py:32-43`, `src/terrain_cache/schema.py:35-54`

Both caches invalidate on a thorough key (source content hash, extractor/classifier version, cache
schema version, region name, centre and half-extents) and compare **all-or-nothing, never partial**.
Two gaps:

**(a) Neither key includes the theatre's projection.** Every cached geometry is DCS x/z produced by
`dcs_to_wgs84(theatre, …)`, so the projection parameters are part of the data's identity. This is
live, not theoretical: **Afghanistan's parameters changed on 2026-10-05** — the 2026-10-04 beacon
fit (`FE -300149.9912, FN -3759656.9499`) was superseded by the round values now at
`projections.py:58-60`. Nothing was invalidated. `EXTRACTOR_VERSION = 2`
(`build/ingest_terrain.py:96`) and `CLASSIFIER_VERSION = 5` (`build/ingest_osm.py:152`) are
hand-maintained ints that nobody is prompted to bump when a projection is refitted. The shift was
0.051 m this time; what made that harmless was luck, not the invalidation key.

**(b) The hand-maintained key has already failed.** `src/build/ingest_osm.py:136-144` records it in
the code's own words:

> `3 -> 4`: the re-review fix to `_ingest_ring`'s hole-containment fallback (commit 638239a) changed
> both this module's ring geometry output and `OsmIngestStats`' fields, **but landed without the
> bump this comment requires**. A `CLASSIFIER_VERSION = 3` cache can therefore hold the invalid
> hole/outer-ring pairings that fix removed, and **would have been served as a hit**. (That specific
> transition happens to raise `TypeError` in `load_cached_stats` instead, because the fix also
> *removed* a stats field — an accident of that one change, not the invalidation working.)

So the procedural guard failed once and an unrelated accident caught it. `terrain_cache` already
does this the structural way, tracking all twelve geometry/classifier knobs as individual meta
fields; `osm_cache` collapses `MIN_AREA_M2`, `SIMPLIFY_TOLERANCE_M` and
`_OSM_POSITION_UNCERTAINTY_M` (`ingest_osm.py:113,121,125`) behind one integer.

**Fix:** add `projection_proj4_sha256` (a hash of `TmercParams.to_proj4()`) to both `META_FIELDS` —
which also closes (a)'s theatre gap, since two theatres cannot share a proj4 string — and promote
`osm_cache`'s three constants to `OsmCacheMeta` fields so (b)'s class of error becomes structural
rather than procedural.

### 1.10 — Unknown surface-type code collapses into "absent". LOW.

`src/query/describe.py:641` and `:654`: `_SURFACE_TYPE_LABELS.get(int(code))` with no default, so
any code outside 1-5 becomes `None` — "unknown enum value" reported as "no surface type". The write
side already does this correctly: `build/ingest_probe.py:160-162,273-275` uses
`.get(code, f"UNKNOWN_{code}")`. Mirror the ingest convention on the read side.

### 1.11 — `raster.dcs_to_tile_pixel` strips a `"provisional"` registration's confidence. LOW.

`src/raster/registration.py:112-134` returns a bare `tuple[int, int, int, int]`;
`src/raster/__init__.py:71-89` a bare `tuple[TileId, int, int]`. `RasterRegistration` carries
`source` and `confidence`, and Syria's is `confidence="provisional"` with the z-axis fitted from
**two** control points at a **~9 % residual** (`registration.py:85-93`). None reaches the caller,
and `tools/inspect_raster.py:142-160` prints the result as a definite mapping. LOW because `raster/`
has no pipeline consumer today — only a diagnostic tool. Listed because it is the same failure as
1.1 in a module nobody is watching, and will matter if M2's raster line resumes.

Two smaller things in the same module: `raster/__init__.py:66-68` decodes a DDS via
`Image.open(...).convert("RGB")` and never asserts the result is 1024×1024, although
`_TILE_PIXELS = 1024` is hardcoded into every pixel calculation (`registration.py:132-133`) — a
differently-sized tile yields wrong pixel math rather than an error. And a coordinate outside the
fitted sheet yields a **negative** tile index with no range check (`registration.py:129-134`); the
docstring warns only about `px`/`py` leaving 0-1023.

---

## 2. Live-tick and read-path robustness — fix now

The store is opened in-process by `body-layer` on the flight loop. An exception there is a dead poll
loop, which this project has been bitten by before.

### 2.1 — `check_schema_version` is never called on any read path, and a comment claims otherwise. MEDIUM.

`src/store/schema.py:104` has exactly one caller: `src/build/pipeline.py:839`, inside the
probe-attach path of a *build*. It is not called by `api/__main__.py`, not by `describe_position`,
and `grep -rn 'schema_version' body-layer/src` returns **nothing** —
`body-layer/src/perception/geometry.py:56-65` (`open_world_model`) is a bare connect with no
validation.

`src/store/reader.py:394-405` states the opposite:

> `None` for a grid row written before this field existed (schema version 2 or earlier), **which
> `check_schema_version` already refuses to open**, so in practice this is only `None` when no grid
> of `grid_kind` exists.

That safety claim is false on every read path. A stale version-2 store opens silently,
`grid_provenance` returns `None`, and `elevation.source` reads `"unavailable"` while `dcs_m` still
returns a real number from a grid of unknown provenance — a provenance failure produced by a comment
that stopped being true. A *compatible-looking* older schema produces wrong answers with no error at
all; an incompatible one surfaces as an `OperationalError` mid-tick instead of a startup refusal.

**Fix:** call `check_schema_version(conn)` at open time in `api/__main__.py` and in
`open_world_model`, and correct the `reader.py` comment either way.

### 2.2 — The LAN API opens the store read-write, and creates it if the path is wrong. MEDIUM. [verified]

`src/api/__main__.py:46`

```python
conn = sqlite3.connect(args.db, check_same_thread=False)
```

`api/server.py:11-13` says this surface is "entirely read-only", and `build/pipeline.py:777-779`
already provides the right helper:

```python
def open_region_db(db_path: Path) -> sqlite3.Connection:
    """Open an already-built `.sqlite` read-only for querying."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
```

The entrypoint does not use it. Two consequences:

- The only read-write handle in the system sits behind a no-auth socket bound to `0.0.0.0`. Nothing
  writes today, so this is defence-in-depth — but it is the authoritative store, rebuilt only by a
  450-second full-theatre pass.
- **[verified]** A mistyped `--db` silently creates an empty database and the server starts cleanly;
  the first query then raises `OperationalError: no such table: meta`.

**Fix:** use `open_region_db` (plus `check_same_thread=False`) and call `check_schema_version`.
`mode=ro` also fails loudly on a missing file instead of creating one.

### 2.3 — The `f"file:{path}?mode=ro"` read-only guard is bypassable two ways. MEDIUM. [verified]

Five sites: `build/pipeline.py:406`, `build/pipeline.py:779`, `osm_cache/reader.py:44`,
`tools/export_geojson.py:105`, and `body-layer/src/perception/geometry.py:65`.

Interpolating a path into a URI means the path's own content is parsed as URI syntax. **Both
bypasses below were reproduced by execution**; a first pass reported the `?` case as failing loudly,
which is true only for some suffixes — it depends on where SQLite's parser lands, so the honest
statement is that *neither* form is reliably safe:

```python
# query-parameter form: SQLite takes the FIRST mode=, the appended one becomes a separate key
p = "/tmp/ovr.sqlite?mode=rwc&x=1"
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c.execute("CREATE TABLE t(a)")      # succeeds; the file is created

# fragment form: SQLite treats #… as a URI fragment and discards the ?mode=ro entirely
p = "/tmp/frag.sqlite#x"
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c.execute("CREATE TABLE t(a)")      # succeeds; /tmp/frag.sqlite created read-write
```

`#` is a legal filename character on Windows, which is where the DCS side of this project runs.

Exploitability today is low — these paths are operator/CLI supplied. It is MEDIUM because of what
stands between it and external data: `body-layer/src/perception/geometry.py:65` builds its path from
`args.world_model_dir / f"{theatre.lower()}-full.sqlite"`, where `theatre` is a raw `.miz`-derived
string. The 2026-10-05 fix at `body-layer/src/logger.py:1949` validates it against
`THEATRE_PROJECTIONS` **membership**, which is strict and does block both forms — so that
already-filed finding is correctly closed. But that one membership check is the only thing holding,
and world-model's own helpers stay bypassable for the next consumer without it.

**Fix:** `Path(db_path).resolve().as_uri() + "?mode=ro"` at all five sites.

### 2.4 — `ATTACH DATABASE` opens read-write even over a `mode=ro` main connection. LOW. [verified]

`src/query/describe.py:583`. The bound parameter is **not** URI-interpreted, so there is no
injection — verified: a `?mode=…` in the string is taken literally and produced a file named
`probe.sqlite?mode=rwc`. But the attached database is opened read-write regardless of the main
connection's mode — verified by creating a table in the attached DB over a `mode=ro` main
connection. Nothing in `src/` writes to it, so this is hardening, not a live bug: attach
`file:…?mode=ro` instead.

### 2.5 — An unbounded bind list reaches SQLite on the query path. MEDIUM.

`src/store/reader.py:186-203`, `features_in_bbox`:

```python
candidate_ids = [row[0] for row in conn.execute(
    "SELECT id FROM feature_bbox WHERE max_x >= ? AND min_x <= ? ...", (...))]
...
placeholders = ",".join("?" for _ in candidate_ids)
query = "... FROM feature WHERE id IN " f"({placeholders})"
```

The R*Tree query is **not filtered by kind** — the kind filter lands in the *second* query — so
`candidate_ids` is every feature of every kind whose bbox overlaps the box, each becoming one SQL
bind parameter, with no cap. `nearest_feature` (`reader.py:328-335`) escalates to a **30 km** radius
(a 60×60 km box) when nothing is found nearer, and `describe_position` makes ~8 such calls per
position (`describe.py:667-744`), against a store with 77,381 area features and 2,010,767 vertices.

The limit is build-dependent, not fixed: **[verified]** 250,000 on the SQLite 3.53.4 bundled here,
but 32,766 on stock SQLite ≥3.32 and 999 below it. On a differently-built Python this raises
`OperationalError: too many SQL variables` **from inside the flight loop**, on a sparse-region query
— i.e. exactly where the escalation fires. A hard failure, not a slowdown.

**Fix:** join `feature` in the R*Tree query so the kind filter prunes before ids are materialized,
or chunk the `IN` list. Either removes the dependence on a build-specific limit.

### 2.6 — Unvalidated `kinds` on the LAN endpoint materializes the whole store. MEDIUM.

`src/api/server.py:177-180`

```python
kinds_param = params.get("kinds")
kinds = kinds_param.split(",") if kinds_param is not None else None
matches = find_place_by_name(conn, text, kinds)
```

`find_place_by_name` defaults to `PLACE_KINDS` but accepts any list and passes it to
`store.reader.all_features` — documented as "no bbox filtering … the whole store is always wanted",
with no `LIMIT` and a `json.loads` per row. So one unauthenticated request,
`?text=a&kinds=landcover,water,settlement,road`, deserializes every geometry in the store (~2 M
vertices by the project's own `vertices_after_simplify` figure) into Python tuples. The server is
deliberately single-threaded (`HTTPServer`, not `ThreadingHTTPServer`), so that request blocks every
other one for its duration, and it binds `0.0.0.0` by default.

**Fix:** restrict `kinds` to `PLACE_KINDS` — all the route is documented to serve — and cap the
result count. The server already validates `theatre` loudly for the same "don't silently answer the
wrong question" reason.

### 2.7 — `nan`/`inf` query params produce an unhandled exception and no response. MEDIUM. [verified]

`_require_float` (`src/api/server.py:104-112`) uses bare `float()`, which accepts `"nan"`, `"inf"`
and `"-inf"`. These do **not** raise in `dcs_to_wgs84` — verified, they propagate as `(nan, nan)` /
`(inf, inf)` — and reach `store/chunks.py:39`:

```python
return math.floor(x / chunk_size_m), math.floor(z / chunk_size_m)
```

Verified end-to-end against a live server: `GET /describe_position?x=nan&z=0&theatre=Syria` raises
`ValueError` and `?x=inf` raises `OverflowError: cannot convert float infinity to integer`. In both
cases `do_GET` has no catch-all, so the client gets
`http.client.RemoteDisconnected: Remote end closed connection without response` — no status, no
error body, indistinguishable from a network fault — while the full traceback goes to the process
log. The server itself survives (a following request returned 404 normally).

**Fix:** `math.isfinite()` in `_require_float` (→ 400), and a 500-returning catch-all around the
three handlers.

### 2.8 — The flight-time startup guard accepts a half-built store. LOW. [corrected]

`body-layer/src/logger.py:1976`

```python
if built_region is not None and built_region.theatre != theatre:
```

A first pass reported this as accepting "any file SQLite can open". That overstates it: an empty or
foreign file has no `region` table, `load_only_region` raises `sqlite3.OperationalError`, and the
surrounding `except (sqlite3.Error, OSError)` at `:1974` turns it into a clean `parser.error`. That
path is fine.

The real gap is narrower and still reachable: a store with a **valid schema but no `region` row**
returns `None` and passes the guard. That state is produced by any build that died between
`open_for_build` (which calls `create_schema`) and `insert_region` — a 450-second full-theatre pass
interrupted early. The flight then starts and every query fails later.

**Fix:** reject `built_region is None` as well, and call `check_schema_version` in the same guard
(2.1). The two together turn both into one loud startup error.

### 2.9 — `json.loads` on store content is unguarded, four columns per row, on the hot path. LOW-MEDIUM.

`src/store/reader.py:90-106`

```python
assert isinstance(geom_json, str)      # stripped under python -O
...
geometry: list[Point] = [(pt[0], pt[1]) for pt in json.loads(geom_json)]
tags=json.loads(tags_json),
provenance=json.loads(provenance_json),
confidence=json.loads(confidence_json),
```

A malformed `geom_json` raises `JSONDecodeError`; `[1,2]` instead of `[[1,2]]` raises
`TypeError: 'int' object is not subscriptable`; a `tags_json` that decodes to a list explodes later
at `feature.tags.get(...)` (`reader.py:213-215`, `describe.py:422,456,493,516,528-529,543-544`).
**The four `isinstance` assertions are the only type validation and vanish under `-O`.** Same
pattern unguarded in `osm_cache/reader.py:93-100` and `terrain_cache/reader.py:85-91`.

Nothing here is exploitable — stdlib `json`, no `eval` — so the realistic impact is an uncaught
exception inside the 5 Hz tick rather than code execution. But the honest statement is that a
corrupt store is detected **only by crashing, at an arbitrary point**, with no schema check upstream
to have caught it first (2.1).

Separately, none of the 17 `json.loads` sites in `src/` pass `parse_constant`. Python's `json`
accepts the non-standard bare literals `NaN`, `Infinity`, `-Infinity`, so a probe line or cached
value containing `NaN` parses to `float('nan')`, **passes every `is None` check**, becomes a sample
indistinguishable from a measured one, and then reads `False` in every comparison forever after.
Relevant at `elevation/dcs_grid.py:46,91`, `roadnet/extract.py:91,96`, `osm/features.py:167`.

**Fix:** `check_schema_version` in `open_world_model`; raise a typed `StoreCorruptError` from
`_row_to_feature` so the tick can degrade deliberately; `parse_constant=` on the file-parsing sites.

---

## 3. Untrusted build-time input

### 3.1 — No integrity verification on the largest untrusted input. MEDIUM, before public release.

`RUN.md:62` and `:301`:

```bash
curl -L -O "https://download.geofabrik.de/${path}-latest.osm.pbf"
```

~1 GB across seven extracts, handed to libosmium's zlib+protobuf decoder in C++
(`src/osm/pbf.py:313-315`, `locations=True, idx="sparse_mem_array"`). No checksum, although
**Geofabrik publishes an `.md5` beside every extract**; no decompressed-size or ratio cap; and `-L`
follows redirects with no `--proto-redir '=https'`, so a redirect to plain HTTP would be followed.
SRTM `.hgt` tiles come from the viewfinderpanoramas.org mirror with the same absence of verification
(and are a third-party-reprocessed SRTM derivative, as `elevation/dem.py:19-22` honestly records).

`sha256_file` (`osm_cache/hashing.py:17-25`) and `combined_tile_hash`
(`terrain_cache/hashing.py:15-27`) exist and are good, but they are **cache-invalidation keys only**
— never compared against a known-good digest. There is no checksum manifest in the repo and none in
the run instructions.

Impact is bounded: `.hgt` is raw int16 and `.pbf` goes through pyosmium, so the realistic outcome is
*wrong terrain*, not code execution. MEDIUM rather than higher only because the current operator is
the repo owner on his own machine — but these instructions are what strangers will run.

**Fix:** add `curl -O .../${path}-latest.osm.pbf.md5 && md5sum -c` to RUN.md §2.1 and
`--proto '=https' --proto-redir '=https'` to both `curl` lines. One documentation edit, no code.

### 3.2 — Grid spacing is unvalidated, and a negative value writes a silently empty elevation grid. MEDIUM.

`--srtm-grid-spacing-m` is a bare `type=float` (`tools/build_world_model.py:87-89`) feeding
`src/build/pipeline.py:196-197`:

```python
n_rows = round(2 * region.half_extent_x_m / spacing_m) + 1
n_cols = round(2 * region.half_extent_z_m / spacing_m) + 1
```

- `1` on `syria-full` → 827,345 × 771,217 ≈ 6.4e11 cells; the allocation at `ingest_srtm.py:99`
  exhausts memory immediately. The cost is quadratic in the spacing and the module's own docstring
  flags row-count sizing as "a real, undecided-by-this-module concern".
- `0` → `ZeroDivisionError`.
- A **negative** value → negative `n_rows`; `range()` yields nothing; `samples = []`; and
  `insert_grid` (`store/writer.py:159-167`, guarded by `if row < len(grid.samples)`) inserts
  **zero** samples. The build then writes a `grid` row with a negative `n_rows`, no error, and
  `srtm_skipped` still `False` — **a silently empty elevation grid presented as built**. That is
  also a §1-class finding: every downstream `sample_grid` returns `None`, and per 1.1 an
  all-`None` LOS check returns `True`.

**Fix:** one guard in `probe_grid_for_region` — `if spacing_m <= 0 or n_rows * n_cols > CAP: raise`
— covers all three.

### 3.3 — File-supplied counts used as allocation sizes, with the cap already written but not applied. LOW-MEDIUM.

`src/roadnet/container.py:154-165`, `read_point_block`:

```python
n, points_offset = read_int32(buf, offset)
if n < 0: raise ContainerFormatError(...)
end = points_offset + n * _TRIPLE_SIZE
if end > len(buf): raise ContainerFormatError(...)
points = [_TRIPLE.unpack_from(buf, points_offset + i * _TRIPLE_SIZE) for i in range(n)]
```

Bounded only by buffer length. `find_next_point_block` already enforces
`_MAX_PLAUSIBLE_N = 20_000` (`container.py:65`); the strict reader does not. On `Syria.routes`
(2.25 GB) a corrupt `N` up to ~93 M passes the bounds check and materializes ~93 M tuples. Its
production caller is the direction array at `routes.py:154`.

Same class, same module family:

- `rn4.py:63-68`, `read_string_table`: `count` from the file drives `range(count)` with no upper
  bound and **no `count < 0` check** — `range(-1)` is empty, so a sign-flipped count returns
  `strings=[]` with `pos` unadvanced; `type_name_for_row` then returns `None` for every row, which
  is the **same value M5 deliberately ships for "type not joined yet"**
  (`ingest_roadnet.py:5-8`), making a total parse failure indistinguishable from an intended
  deferral. `read_point_block` rejects `n < 0` explicitly; this should too. (Low impact today —
  nothing in `src/` imports `rn4`.)
- `rn4.py:87-94`, `iter_topology_rows`: `if not (row[1] == 1 and row[4] == 2): return` — a corrupt
  byte truncates the table silently, with no row count and no way to tell the sentinel from
  corruption, although the docstring records the sentinel as carrying `column 4 == 3`.
- `osm/pbf.py:241-250`, `area()`: `way()` eight lines above guards
  `if not node_ref.location.valid()` and counts `ways_skipped_unresolved_nodes`; `area()` reads
  `node_ref.location.lat` with neither guard nor counter. On an incomplete multipolygon this either
  aborts a 25-30 minute pass with no partial accounting, or yields placeholder coordinates. The
  asymmetry is the finding; which outcome occurs was not verified.
- `elevation/dcs_grid.py:106-113`: `surface_type=int(surface_type)` on one line,
  `height_m=height_m` / `x=record["x"]` uncast on the adjacent ones, into fields annotated `float`.
  A probe emitting `"height_m": "123"` puts a `str` in a `float` field.
- `roadnet/extract.py:95-109`, `read_manifest`: `bbox=tuple(data["bbox"])` with no length or type
  check. The manifest *is* the provenance record, so a corrupt one reports false provenance rather
  than failing.
- `osm/features.py:184-186`: a self-documented uncounted drop (`# … dropped without a count`),
  contradicting the counted-skip convention the same file argues for at `:93-100`.

**Fix:** apply the existing `_MAX_PLAUSIBLE_N` in `read_point_block`; add `count < 0` to
`read_string_table`; mirror `way()`'s guard and counter into `area()`; cast or validate
`dcs_grid`'s floats. All small and local.

### 3.4 — Memory held across a full-theatre build. LOW.

`ingest_srtm.py:99` holds the full grid (~2.5 M cells at the 500 m default — fine) and
`insert_grid` writes all of it in **one transaction** (`store/writer.py:159-168`), so the
journal/WAL grows to the whole grid. `pipeline.py:653` and `ingest_terrain.py:338` load **every**
SRTM tile simultaneously (`SrtmTile.from_file` → `read_bytes()` plus an `array` copy,
`dem.py:81,90-91`): 158 tiles for `afghanistan-full` ≈ 455 MB at SRTM3, ≈ 4 GB if anyone stages
SRTM1. `ingest_roadnet.py:87-115` accumulates the whole in-region road layer in one list before a
single insert — notable because OSM, terrain and junctions were all explicitly converted to
streaming callbacks for exactly this reason (`ingest_terrain.py:321-334` cites a measured 29 GB
extrapolation). Roadnet is the one stage left unstreamed.

Also: `osm/pbf.py:339-346`, `load_features` passes `batch_size=sys.maxsize` — documented as "not
recommended for theatre-scale extracts", and `stream_features` is the bounded path the pipeline
uses, so this is a named trap rather than a defect. But `osm/features.py:161` has a function of the
*same name*, so reaching for the wrong one gets unbounded accumulation silently.

### 3.5 — `urlopen` body read is unbounded. LOW.

`src/osm/overpass.py:99-100`, `body = response.read()` with no `Content-Length` cap. HTTPS to a
hardcoded URL, exactly one call, cache-first, no retry (good discipline, documented as a hard
constraint), and superseded on the pipeline path by `osm/pbf.py`. Listed for completeness; the same
class as an accepted audio-adapter finding.

---

## 4. Public-release items (not security defects in the current deployment)

- **`DEFAULT_HOST = "0.0.0.0"`** (`src/api/server.py:88`) — every interface, no auth, no rate limit.
  Intended and documented, mirroring `aircraft-layer`. For a public repo the safer default is
  `127.0.0.1` with `--host` opting into LAN, which is also what a stranger running this on a shared
  network would want. Same note I filed against `run-brain.sh` previously.
- **`--out` is unvalidated and the write is destructive.** `tools/build_world_model.py:90` →
  `store/writer.py:29-33`: `mkdir(parents=True)`, then `if db_path.exists(): db_path.unlink()`, with
  no check that the file being deleted is even a world-model store. Three siblings are created
  beside it. Current call paths are safe — `--out` is structurally separate from all nine input
  flags, so nothing derives a write target from a DCS path — so the read-only-against-DCS invariant
  holds today by construction, enforced by **convention rather than a guard**. Cheap fix: refuse to
  unlink a file with no `meta.schema_version` row.
- **Developer paths in three committed research notes** — `/home/sg/winHome/Saved Games/DCS`
  (`research/2026-09-02-m0-dcs-install.md:7`, `research/2026-10-05-afghanistan-theatre-build.md:18`)
  and `/home/sg/Dropbox/Documents/win-mac-sync/run-wsl/...` in a traceback
  (`research/2026-09-03-m5-terrain-files-deep-probe-raw.txt:50-56`). No credentials, nothing
  exploitable — a username and a Dropbox layout. Worth one scrubbing pass before the repo goes
  public; docs should prefer `$DCS_SAVED_GAMES_PATH` in examples, as `tools/wsl/*.sh` already do.
- **Related, not committed but shipped in every built store:** `insert_source(..., raw_path=str(path))`
  writes the builder's absolute local paths into the `source` table
  (`pipeline.py:316,340,366,533,562,646,682,862`). Harmless while `.sqlite` files are gitignored,
  but a distributed prebuilt store would carry the builder's directory layout. Awareness, not a
  change.
- **`world-model/data/renders/*.png`** (4 files) are committed although `data/` reads as gitignored
  — `world-model/.gitignore` covers `data/raw/`, `data/processed/`, `data/world-model/`,
  `data/world-model-backups/`, `*.sqlite`, `*.osm.pbf`, so this is intentional. Derived relief
  renders, not location-identifying. Not a security issue; flagged once because redistributing
  ED-derived terrain renders is a **licensing** question for a public repo.

---

## 5. Explicitly NOT a problem

Checked and clean, so the findings above read as a filtered list rather than everything examined.

- **No dynamic code execution anywhere in `src/`.** Grepped `eval`/`exec`/`pickle`/`marshal`/
  `__import__`/`importlib`/`subprocess`/`shell=True`/`os.system`/`yaml.load`: zero hits in `src/`.
  The only `subprocess` uses are two measurement tools
  (`tools/measure_m5_stage5_perf.py:199`, `tools/measure_m7_stage4_perf.py:232`), both list-argv,
  `shell=False`.
- **Lua is parsed, never executed.** `dcs_data/towns.py` uses one fully-anchored regex;
  `dcs_data/beacons.py` uses field regexes over line-delimited blocks. `src/dcs_data/__init__.py:3-7`
  states this as the module contract and the code matches. No `lupa`. A hostile `towns.lua` cannot
  execute.
- **No archive handling at all.** No `zipfile`/`tarfile`/`gzip`/`extractall` in `src/`, so there is
  no zip-slip surface here. `.hgt` tiles are unzipped by the user with their own tool, outside this
  codebase; PBF decompression is inside libosmium (3.1).
- **No secrets, tokens, API keys or credentials** anywhere in `src/` or `tools/`. Grepped
  `api[_-]?key|secret|password|token|BEGIN (RSA|OPENSSH|PRIVATE)` across all tracked
  `world-model` files: zero hits. No GIS/tile provider requiring a key is used.
- **SQL is not injectable.** Every f-string reaching a cursor is either a `?`-placeholder count
  (`store/reader.py:127,154,171,207`, `probe_store/reader.py:59`, `probe_store/writer.py:231-235`)
  or a `schema=` identifier where **every caller passes a hardcoded literal** — `"main"` or
  `"probe"`, set in `describe_position`, never from an HTTP param, CLI arg or DB content. All DDL is
  module-level constants via `executescript`. No `LIMIT`/`ORDER BY` is ever built from input. Safe
  today, fragile by construction, since an identifier cannot be parameterized — a one-line
  `if schema not in {"main", "probe"}: raise` would close it structurally rather than by call-site
  discipline.
- **DCS inputs are opened read-only, always.** `towns.py:80` / `beacons.py:190` `read_text`;
  `routes.py:119` `open("rb")` + `mmap.ACCESS_READ` (never loading the 2.25 GB file);
  `dem.py:81` `read_bytes`. All eleven writes in `src/` go to caller-chosen output paths or
  siblings derived from them; `with_name`/`stem` derivation cannot escape the output directory.
  `tools/wsl/*.sh` write only into `wsl-output` and copy samples *out* — no `rm`/`mv`/`sed -i`/
  `chmod`/`eval` touching the install, variables quoted.
- **Region names and theatre names cannot reach a path unvalidated.**
  `tools/build_world_model.py:78` uses `choices=sorted(REGIONS.keys())`, and `region.name` is only
  ever a parameterized SQL value. An unknown theatre raises at `coordinates/__init__.py:21-28`. SRTM
  filenames go through a strict `^([NS])(\d{2})([EW])(\d{3})\.hgt$` (`dem.py:31`). OSM tags never
  reach a path.
- **`position_uncertainty_m=0.0` for DCS-native roads** (`ingest_roadnet.py:113`) is correct, not an
  instance of 1.4: DCS geometry is authoritative by project invariant, so zero is the honest value.
  1.5 is about a route that *failed its own check* inheriting that claim.
- **`ingest_srtm` reports absence as absence.** Voids and uncovered cells stay `None` and are
  counted — no zero-fill, no guess. `dem.py:118-147` raises on a void rather than interpolating
  across it, and `frombytes` is guarded by an exact size check (`dem.py:84`), so the
  odd-length-truncation class that bit `scale_wav_volume` cannot occur here.
- **No bare `except:`, no `except Exception:`, no `contextlib.suppress` anywhere in `src/`.** The
  one `except BaseException` (`pipeline.py:516-525`) closes a connection and **re-raises**. Every
  other handler is narrow and counted: `ingest_srtm.py:127-129`, `ingest_probe.py:103-105`,
  `validate.py:215-219` (all `ValueError` from `height_at`, counted in
  `points_void_or_uncovered`/`srtm_points_skipped`/`points_skipped`); `routes.py:153-158`
  (`ContainerFormatError` → `sync_loss_events`); `ingest_osm.py:361-365` (`UnicodeEncodeError` is
  the predicate's purpose); `coordinates/__init__.py:24` and `raster/registration.py:105`
  (`KeyError` → a better-worded `ValueError`). The one exception to "counted" is 1.7.
- **Counted-skip channels exist and are populated** where they matter: `OsmFeatureSet`'s
  `relations_skipped`/`ways_skipped_unresolved_nodes`, `StreamFeaturesResult`, `ExtractManifest`'s
  walk counters, `RoutePolyline.byte_offset` → `source_ref` (which is how road id=3711 was traced).
  `beacons.py:125-141` raises naming the missing fields and keeps an absent `frequency` as `None`
  rather than `0.0`; `towns.py:90-92` raises on any unparseable in-table line;
  `ingest_probe.py` uses `.get(code, f"UNKNOWN_{code}")`; `ingest_beacons.py:204-205` counts
  unpaired localizer/glideslope; `ingest_junctions.py:160-170` writes down its own residual
  assumption. These are the opposite of silent defaulting, and they are why 1.4/1.5/1.10/3.3 read as
  gaps in a deliberate convention rather than an absent one.
- **Cache correctness, the parts that are right:** both caches compare all-or-nothing never
  partial (`cache_meta_matches`), `built_at` is excluded from both, hashing is by content not
  path/mtime, and `osm_cache`'s atomicity contract (`os.replace` at `writer.py:105` only after a
  clean pass) means a crash leaves nothing at the canonical path. `terrain_cache`'s
  per-tile-transaction design with a separate `build_complete` axis is the right answer for a
  resumable cache. 1.9 is about the key's *contents*, not its mechanism.
- **`divides_between`** (`query/divides.py`) is honest about its own failure direction: a fragment
  gap undercounts, its only consumer treats anything but exactly `1` as "say nothing", so the
  degradation is silence rather than a false claim. Bbox-bounded, elevation never sampled.
- **`build/validate.py`** — every skip counted, provenance allow-listed to
  `frozenset({"srtm","dcs_probe"})` (`:249`) with `"unavailable"` explicitly not-ok, no I/O, no SQL
  construction. **`build/region.py`**, **`store/chunks.py`**, **`src/geometry/`** — frozen
  dataclasses and pure functions; degenerate bbox raises (`chunks.py:62-63`).
  **`store/writer.py:88-100`** — a generic geometry backstop raising on empty/under-length geometry
  at the one place every producer passes through. **`probe_store/writer.py:30-91`** — identity-drift
  detection on reopen, closes the connection before raising, and refuses a spacing change rather
  than mutating a grid.
- **No file path in the parsers is built from parsed file content.** `raster.TileId.filename`'s
  regex is fully anchored (`raster/__init__.py:24-27`) and admits no separator or `..`; everything
  else takes `Path` from its caller.
- **No unbounded `while` loops in the binary parsers.** `routes._walk`, `rn4.iter_topology_rows` and
  `find_next_point_block` all advance strictly; termination verified.
- **Region centres** (`build/region.py:96-185`) are DCS game-world coordinates, not real-world
  positions of the user.

---

## 6. Summary

**Fix now**

1. **1.6** — write `compare_probe_to_srtm`'s measured error into the store. This is the fix for
   1.1, 1.2, 1.3 and the open `WM-B3`, and it is the item that changes what comes next.
2. **1.1** — `line_of_sight_clear` returns a provenance-carrying result instead of a bare `bool`.
3. **1.2** — stop applying Syria's tolerance to unmeasured theatres.
4. **1.5** — stop storing an implausible route as DCS-authoritative, high-confidence, zero-uncertainty.
5. **2.1 + 2.8** — `check_schema_version` on the read path, and reject a region-less store at
   startup. One combined startup error removes a class of mid-flight failure.
6. **2.2** — the LAN API opens the store `mode=ro` via the helper that already exists.
7. **3.2** — validate `spacing_m`; a negative value currently writes a silently empty elevation grid.

**Fix soon** — 1.4, 1.7, 1.8, 1.9, 1.10, 2.3, 2.4, 2.5, 2.6, 2.7, 2.9.

**Fix before public release** — 3.1 (download integrity + protocol pinning), 3.3 (parser caps), §4
(`0.0.0.0` default, unvalidated `--out`, developer paths).

**Suggested backlog IDs** — highest existing is `WM-B8`, so new items start at `WM-B9`. §1 as a whole
is the scoping of the already-open `WM-B3` and should attach there rather than take a new ID.

**Milestone-impact line.** 1.6 is the finding that changes direction. Until the elevation grid's
measured error lives in the store, every consumer that reads elevation must choose between trusting
it as exact or hardcoding a constant copied from a research note — and this project has now paid for
that twice, three weeks apart, in the same gate. Everything else here is ordinary hardening.
