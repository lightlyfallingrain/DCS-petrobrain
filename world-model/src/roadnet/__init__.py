"""DCS-native road network extraction: `.routes` (whole-theatre road
centerline geometry) and `.rn4` (road/taxiway segment *type* vocabulary).

**Format provenance.** Byte-exact decode against real local files --
`world-model/research/2026-09-04-m5-roadnet-byte-decode.md` (the
authoritative note; both sessions), preceded by
`world-model/research/2026-09-03-m5-terrain-file-formats.md` (first-round
header characterization, superseded on offsets/structure). DCS version
2.9.29.27278 (per M0). Files: `Mods/terrains/<Terrain>/roads/<Terrain>.routes`
(whole-theatre) and `<Terrain>.rn4` / per-airfield `AirfieldsTaxiways/
<Airfield>.rn4` (type vocabulary + topology).

**Container.** Both file types share one `landscape4::` container: a fixed
8xint32 header (`[2, 48, <byte-count>, 0, 0, 0, 0, 0]` -- the byte-count
field is unreliable for `.routes`, see below), then a length-prefixed ASCII
class name (`landscape4::lRoutesFile` or `landscape4::lRoadNetwork`), then a
format-specific body. `container.py` holds the primitives shared by both:
header/class-name assertion, length-prefixed strings, the `[int32 N][N x
float64 xyz]` point-block schema, and the scan-forward resync technique
(`find_next_point_block`) that both `.routes`' per-route trailer and
`.rn4`'s post-topology-table region require to walk past without decoding.

**What is decoded, per file:**

- `routes.py` (`.routes`): the position array and the direction (unit
  tangent) array for every route -- centerline geometry with per-point
  heading "for free", no need to numerically differentiate the polyline.
  Each route's *trailer* (per-point cumulative arc-length, an int32 flags
  array, a bounded float32 array, then an undecoded ~64-byte-per-point
  region) is treated as an opaque, skippable blob located by scan-forward,
  never parsed field-by-field -- it is not needed for M5's `nearest_road`.
- `rn4.py` (`.rn4`): the string table (road/taxiway *type* names, e.g.
  `taxiway_24m`, `runway_65m`) and the topology table immediately after it
  (8xint32 rows; column 6 is a confirmed string-table type index).

**Explicit non-goals -- do not chase these into M5:**

- `.rn4`'s adjacency/graph section (the int32-pair region between the
  topology table and any embedded geometry) is **not decoded**. Nothing in
  `describe_position` asks "can I drive from here to there"; this is
  M6/pathfinding scope (plan.md Decision 8).
- Topology rows are **not joined** to `.routes` geometry blocks, or to any
  geometry embedded in `.rn4` itself. No topology row has been confirmed to
  reference a specific geometry block by any field, and guessing the join
  (e.g. by row order or positional proximity) is explicitly rejected --
  road `subtype`/`name` ship `null` in M5 (plan.md Decision 7). `rn4.py` is
  used only for the type vocabulary and a sanity read of the topology rows.
- `.rn4`'s own embedded route-style geometry blocks (present for airfield
  files past the adjacency section, per byte-decode session 2) are **not
  extracted** -- that is the deferred airfield-taxiway-geometry work
  (plan.md, "Airfield taxiway/runway geometry -- still DEFERRED to M6+").

A future reader must not have to guess that the trailer and the adjacency
section are intentionally opaque -- that is the point of stating it here,
at the package boundary, mirroring `coordinates/__init__.py`'s convention.
"""
