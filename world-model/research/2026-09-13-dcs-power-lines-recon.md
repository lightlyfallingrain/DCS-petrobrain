# Power-line (pylon/wire) geometry: can DCS itself supply exact positions?

**Date:** 2026-09-13
**DCS version:** 2.9.29.27278 (installed, `autoupdate.cfg`)
**Theatre:** Syria

### Question

The user wants power lines modeled as a low-level wire hazard and navigation
landmark for Mi-24 flight, but only sourced from DCS's own ground truth —
OSM power-line positions are rejected because they're off by ~1km vs DCS
terrain (consistent with the project's general OSM-vs-DCS residual, see
`2026-09-03-m2-rastercharts-recon.md` / M7 findings on real-world-vs-DCS
offsets). Can pylon/tower and line geometry be extracted from DCS itself,
with exact DCS x/z, for Syria?

### Findings

- **Syria's own model catalog contains real power-line/pylon/substation
  models, as plain-text declarations.** `Mods/terrains/Syria/Models/*/StructTable.sht`
  are readable Lua-ish tables (not opaque) declaring the per-category asset
  catalog. Confirmed entries relevant to this question — **evidence:
  reproduced-locally** — **source:** grep over
  `Mods/terrains/Syria/Models/*/StructTable.sht`:
  - `Environment/StructTable.sht`: `power_pole_wooden` (crash model
    `pole_crash`, `life=5`), `power_trans_line_big` (crash model
    `power_trans_line_big_crash`, `life=20`, `maxSlope=20`).
  - `Small/StructTable.sht`: `Power_generator_01`, `power_trans_station`,
    `bengal_power_hub`.
  - `Misc/StructTable.sht`: `power_plant_01` (crash `power_plant_01_crash`).
  - `HouseDetails/StructTable.sht`: `electric_box`.
  - No hits anywhere for `pylon`, `opora`, `mast`, `tower` (other than
    unrelated `NDB_high_tower`, `light_tower`, `water_tower`,
    `un_tower`, clock/city towers) — so the Syria catalog's own naming
    convention for HV lines is `power_trans_line_big` / `power_pole_wooden`,
    not the words a first-pass grep would guess.
  - These are model-catalog *declarations* (geometry/crash-behaviour
    metadata), not per-instance placements — a `StructTable.sht` entry says
    "this model exists and can be placed," not "it is placed at (x, y, z)
    N times." Placement is a separate, unread system (see below).

- **The per-instance scenery placement database exists, is binary, and
  independently references the same power-line model names — but its
  placement-record format is undecoded.** `Mods/terrains/Syria/Scenes/Syria.scn5`
  (5,524,894,992 bytes) self-identifies at offset 0x20 as
  `landscape5::Scene5File` — **evidence: reproduced-locally**. Its header
  (offsets 0x00–0x44) is: uint32 `2`, uint32 `0x30`(48), uint32
  `0x06574000`(106,127,360 — plausibly a following-section byte length),
  16 zero bytes, then a length-prefixed string
  `landscape5::Scene5File` (22 chars, matches its own length prefix), then
  uint32 `9`, then uint32 `15,289`, then a length-prefixed string table
  (each entry: uint32 length + ASCII bytes, no terminator) beginning
  `townwall`, `fence_wall_crash`, `fanar`, `small_crash`,
  `israel_town_house_01`, … — 15,289 entries total, i.e. a global string
  pool, almost certainly the model-name dictionary the placement records
  further into the file reference by index rather than by re-embedding the
  string. `power_trans_line_big_crash` appears once at byte offset 8598,
  `power_pole_wooden` once at byte offset 14865, and `power_trans_line_big`
  (bare, no `_crash` suffix) once at byte offset 565438, each exactly once
  — consistent with a deduplicated string table, and notably placed
  *immediately adjacent* to other short strings `wire`, `wire_straight`,
  `fn_support`, `fn_support_chair` in the same table region (byte
  565400–565664) — plausibly sub-part/component names of the
  `power_trans_line_big` prefab (pylon + wire span rendered as one
  composite mesh with named LOD/attachment parts), though this is
  **inferred**, not confirmed — no placement record was decoded to check
  whether `wire`/`fn_support` are independently-positioned objects or just
  internal mesh-part labels.
  - This confirms the names are wired into the terrain's own scene
    database (not vestigial/unused catalog entries), which is suggestive
    but **not proof** that instances are actually placed on the Syria map
    — no instance/placement record (position, rotation, string-table
    index) was located or decoded. Decoding the placement-record format of
    a 5.5GB heterogeneous binary is a substantially larger undertaking than
    the `.routes`/`.rn4` road-format decode (`2026-09-04-m5-roadnet-byte-decode.md`)
    — same order of magnitude as the M7 `Syria.surface5` elevation-mesh
    dead end (`2026-09-05-m7-terrain-mesh-elevation-relitigation.md`), which
    was explicitly not pursued for exactly this cost reason.

- **`world.searchObjects(Object.Category.SCENERY, volume, handler)` is
  documented and is the standard way real DCS terrain-object recon projects
  get exact coordinates for placed scenery, without touching the binary
  format.** — **evidence: documented (Hoggit World DCS Scripting wiki)**,
  cross-checked across three pages/searches this session:
  - `DCS_func_searchObjects`: confirmed literal signature
    `world.searchObjects(table/enum Object.Category, volume searchVolume, ObjectSearchHandler Handler, any data)`;
    volume shapes Segment/Box/Sphere/Pyramid; for Sphere the literal
    example on the page uses `{id = world.VolumeType.SPHERE, params = {point = ..., radius = ...}}`;
    handler receives `(foundItem, val)` and returns `true` to keep
    searching.
  - `DCS_Class_Scenery_Object`: class description "Represents all objects
    placed on the map. Bridges, buildings, etc."; inherits `isExist,
    destroy, getCategory, getTypeName, getDesc, hasAttribute, getName,
    getPoint, getPosition, getVelocity, inAir` from `Object`; has its own
    `getLife` and static `SceneryObject.getDescByName`.
  - `Object.Category` enum (via search-engine synthesis of Hoggit content,
    not a raw page fetch — see caveat below) = `{UNIT, WEAPON, STATIC,
    SCENERY, BASE}`.
  - `world.getAirbases()` returns an array of `Airbase` objects (also
    Object-derived, so `getPoint()`/`getName()` work on them) —
    used in the probe below as a coordinate-free way to anchor search
    volumes, since we deliberately have no verified real-world power-line
    location to convert (that's the whole reason OSM is rejected).
  - **Caveat on evidence strength:** one WebFetch summary of
    `DCS_func_getTypeName` echoed back the search string `'power_trans_line_big'`
    as if it were a literal example on the page — this reads as the
    fetch's summarizing model mirroring my own prompt wording rather than
    genuine page content, and is **not** trusted as a citation. The
    underlying claim it was attached to ("`getTypeName()` returns a
    human-readable 3D model name for scenery objects, not a numeric id")
    is separately supported by the `DCS_Class_Scenery_Object` page's own
    description and by general community usage, but "the wiki literally
    shows `power_trans_line_big` as an example" should be treated as
    **not true** — this is the AI-summarization hallucination risk
    Investigator's sourcing rules exist to catch.
  - `forum.dcs.world` 403'd on fetch as usual (see `forum-dcs-world-fetch.md`
    memory) — not treated as an unread gap; not blocking here since the
    Hoggit citations above are sufficient to design a probe.
  - None of this has been exercised against the installed 2.9.29.27278
    Syria terrain in this session — **no live probe has been run yet.**

### Reproducible Test

Static-file findings: reproduced with plain `grep`/`dd`/`xxd` against
`$DCS_INSTALL_PATH/Mods/terrains/Syria/Models/*/StructTable.sht` and
`$DCS_INSTALL_PATH/Mods/terrains/Syria/Scenes/Syria.scn5` (read-only, no
DCS install writes). Byte offsets above are stable for this exact
`Syria.scn5` (5,524,894,992 bytes, this install version) only.

Live-probe (not yet run): `world-model/tools/dcs-mission-probe/power_line_scenery_probe.lua`.
Stage A discovery probe — searches a 20km-radius sphere around each of the
first 3 airbases `world.getAirbases()` returns, logging every
`Object.Category.SCENERY` object whose `getTypeName()` matches a
power-infrastructure keyword (`power_trans_line`, `power_pole`,
`power_plant`, `power_trans_station`, `power_generator`, `power_hub`,
`electric_box`) to `Saved Games/DCS/Logs/power_line_probe_matches.jsonl`
(exact DCS x/y/z, `getPoint()`), plus every *distinct* `getTypeName()` seen
(matched or not) to `power_line_probe_typenames.jsonl`, as a discovery
catalog in case the actual placed-object naming differs from the
`StructTable.sht` catalog names (e.g. if `wire`/`fn_support` turn out to be
independently placed rather than mesh-internal parts). Full run instructions
(io/lfs sandbox prerequisite, mission-editor trigger setup, incremental
airbase-count ladder, what to do with each possible outcome) are in the
script's header comment. Not run by Investigator — DCS access from this
session is direct-machine (per the skill's precondition check, both
`$DCS_INSTALL_PATH` and `$DCS_SAVED_GAMES_PATH` resolved), but running a
mission is a manual/in-game step per project convention (Investigator
designs probes, doesn't fly missions).

### Possible Approaches

1. **Recommended: live probe via `world.searchObjects(Object.Category.SCENERY, ...)`.**
   Same "live-probe over binary-format RE" choice the project already made
   for M4 elevation (`land.getHeight`, no offline heightmap) and partially
   for M9 (junctions derived from `.routes` rather than a hypothetical
   settlement-extent file that doesn't exist). Cheap to test (one mission
   run), gives exact `getPoint()` coordinates directly in DCS x/y/z (no
   projection-residual risk at all, unlike OSM), and the documentation
   evidence is solid (Hoggit, cross-checked on 3 separate pages). Run the
   Stage A probe above first; if it confirms hits, a full-theatre chunked
   sweep (all airbases + a grid of spheres covering the M7 bbox away from
   any airbase, using the same `timer.scheduleFunction` chunking pattern
   Stage 5 junction-streaming established) is the natural follow-on. Open
   risk: `world.searchObjects` over a 20km sphere has never been exercised
   against this install — cost/latency per call is unknown; the probe's
   run instructions call this out explicitly and ask the runner to stop
   and report rather than push through an apparent hang.

2. **Fallback if Stage A comes back empty:** widen the keyword list using
   whatever `power_line_probe_typenames.jsonl` actually contains (it logs
   every distinct scenery type name seen, not just matches), then widen the
   search radius and/or airbase count before concluding scenery objects
   don't reach real line placements (airbases may simply not be
   representative anchors — Syria's HV grid may run through population
   centers or along particular road/rail corridors instead).

3. **Not recommended as the primary path, but a real fallback if the live
   probe is unavailable or too costly at full-theatre scale:** decode
   `Syria.scn5`'s placement-record format. The string-table header is now
   understood (length-prefixed strings, 15,289-entry dictionary, confirmed
   byte layout above) — a real head start over a cold start — but the
   instance/placement record schema (position, rotation, string-table
   index, LOD/chunk grouping) past the string table is completely
   undecoded, and the file is ~180x larger than the already
   multi-session `.routes`/`.rn4` road decode. Treat like `Syria.surface5`
   in the M7 relitigation note: a real, timeboxed follow-on if the live
   probe proves insufficient, not the default plan.

4. **Not useful for this question:** `RasterCharts`/`clipmaps` (raster
   imagery only, no vector geometry — per `2026-09-03-m2-rastercharts-recon.md`)
   and F10 map overlays (rendering only, no scripting-exposed geometry
   query found in any prior recon).

### Unresolved

- No live probe has actually been run — everything about
  `world.searchObjects`/`Object.Category.SCENERY` behavior against real
  Syria data (whether it returns any power-line hits at all, how many, at
  what performance cost per sphere) is currently **documented-but-unverified**,
  not confirmed. This is the single most important next step; running
  `power_line_scenery_probe.lua` resolves it directly.
- Whether transmission lines are represented as one long
  `power_trans_line_big` scenery instance per span (giving pylon-spacing
  granularity directly from instance positions) or some other placement
  pattern (e.g. repeated short segments, or a single very long mesh per
  multi-km corridor) is unknown until a probe returns real hits — this
  affects how directly instance positions map to "wire hazard corridor"
  waypoints versus needing inter-instance interpolation.
  Only Stage A pcall failure modes get caught explicitly if API calls
  don't error — a call that "succeeds" but silently returns zero results is
  the actual open case here.
- Whether `wire`/`wire_straight`/`fn_support`/`fn_support_chair` (found
  adjacent to `power_trans_line_big` in the `.scn5` string table) are
  independently placed/queryable scenery objects or purely internal
  mesh-part names is unresolved — resolved automatically if they show up
  (or don't) in the probe's `power_line_probe_typenames.jsonl` discovery
  output.
- The `Object.Category` enum value list (`UNIT, WEAPON, STATIC, SCENERY,
  BASE`) came from a WebSearch synthesis of Hoggit content, not a literal
  page quote — treat as documented-but-secondary-source until the probe's
  first successful `world.searchObjects(Object.Category.SCENERY, ...)` call
  confirms the constant resolves and behaves as expected.
