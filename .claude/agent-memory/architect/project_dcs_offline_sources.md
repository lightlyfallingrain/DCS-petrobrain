---
name: dcs-offline-data-sources
description: towns.lua is a plain-text DCS-authoritative gazetteer readable offline; MissionGenerator/nodes.lua is NOT a road graph — check the terrain tree before planning a live probe
metadata:
  type: project
---

**Before planning a live-mission probe, check whether the DCS terrain tree already ships the
data as a plain file.** `Mods/terrains/Syria/map/towns.lua` is unencrypted, declared as a single
global `towns = { ... }` (preceded by `local gettext = require("i_18n")` / `local _ =
gettext.translate`), with entries of the form
`["Aleppo"] = { latitude = .., longitude = .., display_name = _("Aleppo")}` — a
DCS-authoritative name+point gazetteer with **no category, type, radius, or extent field**, and
it mixes cities, villages, military units, landmarks and commercial POIs undifferentiated. Read
via read-only WSL `cat` (`tools/wsl/probe_syria_terrain_lua.sh`); no mission, no io/lfs sandbox
edit, no probe-scale risk.

**Two hard numbers, both verified against the 2026-09-03 probe capture — do not re-derive:**
exactly **1,182 entries**, all matching a fully-anchored strict regex with zero failures (the
once-cited "1,186" was a line count, not an entry count — there were never missing entries); and
**only 1,151 unique names — 31 duplicates** (`Yeniyurt` ×3, `Army Vehicle Training Ground` ×4,
~22 Turkish village names ×2). Any name-keyed dict, unique constraint, `DISTINCT name`, or
dedup-by-name step silently destroys 31 real places.

**`MissionGenerator/nodes.lua` is NOT a road/waypoint graph — lead closed negative.** It is a
global `missionNodes` table of 9 named AI-campaign strategic zones (Adana, Damascus, Aleppo,
Palmyra, Beirut, Cyprus, H3, Efrat, Hatai), each with one `redPos`/`bluePos` DCS x/z pair and AI
unit-template name lists. No edges, no topology. `nodesMap.lua` is one line —
`theatre.nodesMapBorders = { -257003.95, -419498.88, 248852.05, 368981.13 }` (minX, minZ, maxX,
maxZ) — the mission generator's working envelope, *not* a documented terrain extent; useful as
corroboration only. Consequence: **DCS-authoritative road geometry has no offline source**; it
requires the live-mission `land.getClosestPointOnRoads` / `findPathOnRoads` route.

**Why:** M4's working assumption was "names come from OSM"; discovering towns.lua overturned it
mid-plan and made the DCS-authoritative/OSM-augments split real rather than aspirational for the
name layer. Offline files are strictly cheaper and more reliable than the live-mission route —
but the nodes.lua result shows the terrain-tree check can also come back empty, and a plan should
sequence such a lead as a gate rather than absorb it as an assumption.

**How to apply:** when a milestone needs a new data class, enumerate the terrain tree first and
only fall back to Mission Scripting. One open caveat still carried: it is **unresolved** whether
towns.lua lat/lon are DCS in-game label positions (uncertainty ≈0) or real-world gazetteer
coordinates (uncertainty ≈1.3 km, the M1 art-placement envelope). Related:
[[m5-region-selection-lesson]].
