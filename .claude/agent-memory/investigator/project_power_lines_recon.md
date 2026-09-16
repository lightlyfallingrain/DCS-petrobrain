---
name: project_power_lines_recon
description: Syria power-line/pylon extraction recon — scn5 scene-file string table confirms models exist, world.searchObjects(SCENERY) is the recommended live-probe path, not yet run.
metadata:
  type: project
---

Session 2026-09-13, DCS 2.9.29.27278, Syria. Question: can power-line
pylon/wire geometry be extracted from DCS itself (exact positions), since
OSM is rejected (~1km off DCS ground truth)?

**Static catalog confirmed (reproduced-locally):** Syria's own
`Mods/terrains/Syria/Models/*/StructTable.sht` (plain text) declares real
power-line models: `power_trans_line_big` + `power_pole_wooden`
(`Environment/StructTable.sht`), `power_plant_01` (`Misc/`),
`power_trans_station`/`Power_generator_01`/`bengal_power_hub` (`Small/`),
`electric_box` (`HouseDetails/`). Grepping for `pylon`/`opora`/`mast` finds
nothing — Syria's own naming convention is `power_trans_line_big`/
`power_pole_wooden`, don't grep the "obvious" English/Russian words first.

**New file-format finding: `Scenes/<Terrain>.scn5` is the per-terrain
scenery *placement* database** (`landscape5::Scene5File` header, distinct
from `Communication.ref`-style per-category model *catalogs* which are
`landscape4::lReferenceFile`, and distinct from `surface/<Terrain>.surface5`
which is the terrain elevation mesh, already ruled out for elevation in the
M7 relitigation note — don't confuse the two `*5` files, `Scene5File` vs
`surface5`, they're unrelated formats despite the similar name). Syria's
`Scenes/Syria.scn5` is 5.5GB. Header decoded: offset 0x20 = length-prefixed
format-id string `landscape5::Scene5File`; then uint32 `9`, uint32
`15289` (= string-table entry count), then a length-prefixed
(uint32-LE-length + ASCII, no terminator) string table — this is a global
model-name dictionary, confirmed by finding `power_trans_line_big`/
`power_pole_wooden` in it exactly once each (dedup'd). Placement-record
format past the string table (position/rotation/string-index) is NOT
decoded — would be a multi-session RE effort like the M5 `.routes` decode
but ~180x the file size; treat as a timeboxed fallback only, same posture as
`Syria.surface5`, not a first choice.

**Recommended path: live probe, not file RE.**
`world.searchObjects(Object.Category.SCENERY, volume, handler)` is
Hoggit-documented (`DCS_func_searchObjects`, `DCS_Class_Scenery_Object`,
`DCS_func_getCategory`) — SceneryObject inherits `getTypeName`/`getPoint`/
`getName` from `Object`; volume Sphere form is
`{id=world.VolumeType.SPHERE, params={point=..., radius=...}}` (literal
doc example, confirmed). `world.getAirbases()` also documented — used as a
coordinate-free way to anchor search spheres (no verified real-world
power-line location exists to convert, since OSM is the rejected source).
Probe script written but NOT YET RUN:
`world-model/tools/dcs-mission-probe/power_line_scenery_probe.lua`.

**WebFetch hallucination caught this session:** a WebFetch summary of
`DCS_func_getTypeName` echoed my own query term `power_trans_line_big` back
as if it were a literal wiki example — it wasn't; the summarizing model
mirrored my prompt wording. Don't trust a WebFetch/WebSearch summary that
suspiciously repeats your exact query string as a "page quote" — re-fetch
with a neutral prompt or find the literal page text before citing it.
