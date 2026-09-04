---
name: m5-region-selection-lesson
description: Gemerek works for M1-M4 but is empty of DCS content; test regions must be validated for content, not just for transform correctness
metadata:
  type: project
---

**A test region that is fine for coordinate/raster/elevation work can be useless for a content
milestone — check content before reusing it.** Gemerek (DCS x=461319.5, z=29815.4) carried
M1-M4, but for M5 it has **0 DCS-named places within 192 km** (`towns.lua`'s northern coverage
ceiling is ~37.88°N, ~130 km south of Gemerek) and M3 already found **0 OSM waterways** in its
bbox. Two of M5's five layers would ship structurally empty. **User confirmed the move to
Latakia** (2026-09-03): centre **x=41934.892, z=5685.076** = `wgs84_to_dcs("Syria", 35.40109,
35.94868)`, the published OSLK ARP, half-extent 10 km. An M1 published-ARP control point sits
inside it (keeps control-point tests non-circular), the Mediterranean coast guarantees water, and
it holds 2 towns.lua places — Jablah (37876, 3614) and Al Hannadi (50833, 3994). Both survive an
eastward (inland) centre offset up to +3 km; beyond that Jablah drops out.

A third, independent signal corroborated the move: `MissionGenerator/nodesMap.lua`'s
`nodesMapBorders` maxX is 248,852, so Gemerek's x=461,320 is ~212 km outside the mission
generator's envelope too.

**Watch the two Latakia coordinates.** `tests/control_points.py` carries both the ARP-derived
point above and DCS's **in-game** airbase position (x=43237.969, z=5841.165). They differ by
~1.3 km — that gap *is* the M1 terrain-placement residual. Define regions from the ARP-derived
point; use the in-game one as a query sample, never as a region origin.

**Why:** M1-M4 each validated a *transform or extraction mechanism*, which works over empty
terrain. M5 is the first milestone whose deliverable requires the region to contain things.

**How to apply:** before adopting a region for any content-bearing milestone (M5-M7), run a
census first: count towns.lua entries inside it, and check the OSM feature mix by kind. Keep
regions in a `REGIONS` registry mirroring the `THEATRE_PROJECTIONS` /
`THEATRE_RASTER_REGISTRATIONS` pattern so switching is a one-line change, and keep
`gemerek-20km` registered for M1-M4 continuity. Related: [[m5-storage-decision]],
[[dcs-offline-data-sources]].
